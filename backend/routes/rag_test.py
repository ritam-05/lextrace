import asyncio
import uuid
from datetime import datetime

import fitz  # PyMuPDF
from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.database import Database
from backend.rag_engine.chunker import LegalDocumentChunker
from backend.rag_engine.embeddings import RAGService
from backend.rag_engine.generator import ActionPlanGenerator
from backend.services.arbitrator import Arbitrator
from backend.services.operative_isolator import isolate_operative_section
from backend.services.paragraph_segmenter import segment_pages_into_paragraphs
from backend.services.zone_extractor import ZoneExtractor

router = APIRouter()

chunker = LegalDocumentChunker()
rag_service = RAGService(batch_size=16)
generator = ActionPlanGenerator()
arbitrator = Arbitrator()


@router.post("/upload")
async def process_judgment(file: UploadFile = File(...)):
    """
    Complete pipeline with Regex + RAG parallel execution + Arbitration.
    Both extract their own fields and are preserved in the output.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    print(f"\nReceived Document: {file.filename}")
    document_id = f"doc_{uuid.uuid4().hex[:8]}"

    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_text = [page.get_text() for page in doc]
        raw_text = "\n".join(pages_text)
        doc.close()

        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract readable text from the PDF. It may be a scanned image requiring OCR.")

        print(f"Extracted {len(raw_text)} characters of raw text.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF Parsing Failed: {str(e)}")

    try:
        from backend.services.utils import PageText

        pages = [PageText(page=i + 1, text=text) for i, text in enumerate(pages_text)]
        paragraphs = segment_pages_into_paragraphs(pages)
        if not paragraphs:
            raise HTTPException(status_code=400, detail="No paragraphs extracted from PDF.")

        operative_section = isolate_operative_section(paragraphs)
        operative_text = (
            "\n\n".join([p.text for p in paragraphs[operative_section.start_para_index :]])
            if operative_section.detected
            else raw_text
        )

        print(f"✅ Operative section isolated: {operative_section.marker_matched}")
    except Exception as e:
        print(f"⚠️ Could not isolate operative section: {e}. Using full text.")
        from backend.services.utils import PageText

        pages = [PageText(page=i + 1, text=text) for i, text in enumerate(pages_text)]
        paragraphs = pages
        operative_text = raw_text
        operative_section = None

    try:
        print("\n🔄 Starting parallel extraction (Regex + RAG)...")

        def run_regex_extraction():
            try:
                print("  [REGEX] Starting metadata extraction...")
                zone_extractor = ZoneExtractor([paragraph.to_dict() for paragraph in paragraphs])
                regex_output = zone_extractor.extract_all()
                print("  [REGEX] ✅ Completed metadata extraction")
                return regex_output
            except Exception as e:
                print(f"  [REGEX] ❌ Extraction failed: {e}")
                return {}

        async def run_rag_extraction():
            try:
                print("  [RAG] Starting semantic extraction with LLM...")
                parent_documents, child_chunks = chunker.process_document(operative_text, document_id)
                rag_service.ingest_document(parent_documents, child_chunks)

                semantic_query = (
                    "What are the final operational directives, orders, deadlines issued by the court, "
                    "and which specific departments are instructed to take action?"
                )
                keyword_query = (
                    "directed directs ordered orders mandate hereby shall instructed "
                    "timeline days weeks months within forthwith immediately period "
                    "department ministry authority respondent committee board "
                    "compliance strict affidavit report execution disposed decree"
                )

                retrieved_context = rag_service.retrieve_context(
                    semantic_query=semantic_query,
                    keyword_query=keyword_query,
                    top_k=5,
                )

                if not retrieved_context:
                    raise Exception("Failed to retrieve context")

                rag_output = generator.generate(context=retrieved_context, hard_facts={})
                print("  [RAG] ✅ Completed semantic extraction with LLM")
                return rag_output
            except Exception as e:
                print(f"  [RAG] ❌ Extraction failed: {e}")
                return {}

        regex_output, rag_output = await asyncio.gather(
            asyncio.to_thread(run_regex_extraction),
            run_rag_extraction(),
        )

        print("\n⚖️ Starting arbitration...")
        arbitration_results = arbitrator.arbitrate_all(regex_output, rag_output)
        arbitration_summary = arbitrator.generate_arbitration_summary(arbitration_results)

        print("  ✅ Arbitration Complete:")
        print(f"     - Dual-Verified: {arbitration_summary['dual_verified_count']}")
        print(f"     - Mismatches: {arbitration_summary['mismatch_count']}")
        print(f"     - Single-Source: {arbitration_summary['single_source_count']}")
        print(f"     - Average Confidence: {arbitration_summary['average_confidence']}")

        db = Database.get_db()
        try:
            extraction_record = {
                "document_id": document_id,
                "filename": file.filename,
                "extraction_type": "arbitration_result",
                "regex_output": regex_output,
                "rag_output": rag_output,
                "arbitration_results": {
                    field_name: {
                        "field_name": result.field_name,
                        "final_value": result.final_value,
                        "state": result.state,
                        "confidence": result.confidence,
                        "regex_value": result.regex_value,
                        "rag_value": result.rag_value,
                        "regex_source": result.regex_source,
                        "rag_source": result.rag_source,
                        "notes": result.notes,
                    }
                    for field_name, result in arbitration_results.items()
                },
                "arbitration_summary": arbitration_summary,
                "status": "pending_human_review",
                "created_at": datetime.utcnow().isoformat(),
            }

            db.extractions.insert_one(extraction_record)
            print("✅ Extraction and arbitration results saved to MongoDB")
        except Exception as e:
            print(f"❌ Failed to save to MongoDB: {e}")

        return {
            "status": "success",
            "document_id": document_id,
            "filename": file.filename,
            "message": "Extraction complete. Awaiting human verification.",
            "verification_endpoint": f"/api/verify/{document_id}",
            "regex_output": regex_output,
            "rag_output": rag_output,
            "arbitration_summary": arbitration_summary,
            "fields_requiring_review": [
                field_name for field_name, result in arbitration_results.items() if result.state == "mismatch"
            ],
        }
    finally:
        rag_service.delete_document_data(document_id)

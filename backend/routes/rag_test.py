import asyncio
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.database import Database
from backend.rag_engine.chunker import LegalDocumentChunker
from backend.rag_engine.embeddings import RAGService
from backend.rag_engine.generator import ActionPlanGenerator
from backend.services.arbitrator import Arbitrator
from backend.services.operative_isolator import isolate_operative_section
from backend.services.paragraph_segmenter import segment_pages_into_paragraphs
from backend.services.pdf_reader import extract_pdf_text
from backend.services.regex_extractor import extract_case_type
from backend.services.zone_extractor import ZoneExtractor
from backend.services.appeal_scorer import AppealScorer

router = APIRouter()

chunker = LegalDocumentChunker()
rag_service = RAGService(batch_size=16)
generator = ActionPlanGenerator()
arbitrator = Arbitrator()


def _is_missing_judge_name(value: object) -> bool:
    if not isinstance(value, str):
        return True

    normalized = value.strip().lower()
    return normalized in {"", "not specified", "error", "not available", "n/a", "na", "none", "null"}


def _fallback_judge_name_from_last_page(paragraphs: list) -> str | None:
    if not paragraphs:
        return None

    last_page = max(paragraph.page for paragraph in paragraphs)
    last_page_paragraphs = [
        paragraph.to_dict()
        for paragraph in paragraphs
        if paragraph.page == last_page
    ]

    if not last_page_paragraphs:
        return None

    bench_result = ZoneExtractor(last_page_paragraphs).extract_all().get("bench", {})
    bench_value = bench_result.get("value")
    return bench_value.strip() if isinstance(bench_value, str) and bench_value.strip() else None


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
        pages, ocr_used, page_count = extract_pdf_text(pdf_bytes)
        raw_text = "\n\n".join(page.text for page in pages if page.text.strip())

        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract readable text from the PDF. It may be a scanned image requiring OCR.")

        print(f"Extracted {len(raw_text)} characters of raw text.")
        print(f"OCR fallback used: {ocr_used}")

        header_chunk = raw_text[:1250]
        print(" [LLM] Extracting basic metadata from the first 1000 characters...")
        header_metadata = generator.extract_basic_metadata(header_chunk)
        print(f" [LLM] Header Metadata: {header_metadata}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF Parsing Failed: {str(e)}")

    try:
        paragraphs = segment_pages_into_paragraphs(pages)
        if not paragraphs:
            raise HTTPException(status_code=400, detail="No paragraphs extracted from PDF.")

        operative_section = isolate_operative_section(paragraphs)
        operative_paragraphs = (
            paragraphs[operative_section.start_para_index :]
            if operative_section.detected
            else paragraphs
        )
        operative_text = (
            "\n\n".join([p.text for p in operative_paragraphs])
            if operative_section.detected
            else raw_text
        )

        if _is_missing_judge_name(header_metadata.get("Name_of_the_judge")):
            fallback_judge_name = _fallback_judge_name_from_last_page(paragraphs)
            if fallback_judge_name:
                header_metadata["Name_of_the_judge"] = fallback_judge_name
                print(f" [REGEX] Judge name fallback from last page: {fallback_judge_name}")

        print(f"Operative section isolated: {operative_section.marker_matched}")
    except Exception as e:
        print(f"Could not isolate operative section: {e}. Using full text.")
        paragraphs = pages
        operative_paragraphs = pages
        operative_text = raw_text
        operative_section = None

    try:
        print("\n Starting parallel extraction (Regex + RAG)...")

        def run_regex_extraction():
            try:
                print("  [REGEX] Starting metadata extraction...")
                zone_extractor = ZoneExtractor([paragraph.to_dict() for paragraph in paragraphs])
                regex_output = zone_extractor.extract_all()
                case_number_result = regex_output.get("case_number") or {}
                case_type_result = extract_case_type(
                    case_number=case_number_result.get("value") or "",
                    source_paragraph=case_number_result.get("source"),
                )
                regex_output["case_type"] = case_type_result
                print("  [REGEX] Completed metadata extraction")
                return regex_output
            except Exception as e:
                print(f"  [REGEX] Extraction failed: {e}")
                return {}

        async def run_rag_extraction():
            try:
                print("  [RAG] Starting semantic extraction with LLM...")
                parent_documents, child_chunks = chunker.process_document(
                    operative_text,
                    document_id,
                    source_paragraphs=operative_paragraphs,
                )
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

                retrieval_result = rag_service.retrieve_context(
                    semantic_query=semantic_query,
                    keyword_query=keyword_query,
                    top_k=5,
                    include_sources=True,
                )
                retrieved_context = retrieval_result.get("context", "")

                if not retrieved_context:
                    raise Exception("Failed to retrieve context")

                rag_output = generator.generate(context=retrieved_context, hard_facts={})
                rag_output["RAG_Source_Pages"] = retrieval_result.get("source_pages", [])
                rag_output["RAG_Source_Chunks"] = retrieval_result.get("source_chunks", [])
                
                # --- NEW HYBRID APPEAL LOGIC ---
                if "Appeal_Risk_Signals" in rag_output:
                    print("  [RAG] Calculating deterministic appeal score...")
                    appeal_evaluation = AppealScorer.evaluate(rag_output["Appeal_Risk_Signals"])
                    
                    # Ensure Action_Plan exists to avoid KeyError
                    if "Action_Plan" not in rag_output:
                        rag_output["Action_Plan"] = {}
                        
                    # Inject the computed result directly into the Action Plan
                    rag_output["Action_Plan"]["Consideration_for_Appeal"] = appeal_evaluation["appeal_consideration"]
                    rag_output["Action_Plan"]["Appeal_Justification"] = appeal_evaluation["reasons"]
                    rag_output["Action_Plan"]["Appeal_Risk_Score"] = appeal_evaluation["score"]
                    rag_output["Action_Plan"]["LLM_Context"] = appeal_evaluation["llm_summary"]
                    
                    # Clean up the raw signals so the frontend and database only see the processed result
                    del rag_output["Appeal_Risk_Signals"]
                # --------------------------------

                print("  [RAG] Completed semantic extraction with LLM")
                return rag_output
            except Exception as e:
                print(f"  [RAG] Extraction failed: {e}")
                return {}

        regex_output, rag_output = await asyncio.gather(
            asyncio.to_thread(run_regex_extraction),
            run_rag_extraction(),
        )

        print("\nStarting arbitration...")
        arbitration_results = arbitrator.arbitrate_all(regex_output, rag_output)
        arbitration_summary = arbitrator.generate_arbitration_summary(arbitration_results)

        print("   Arbitration Complete:")
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
                "ocr_used": ocr_used,
                "page_count": page_count,
                "header_metadata": header_metadata,
                "regex_output": regex_output,
                "rag_output": rag_output,
                "arbitration_results": {
                    field_name: {
                        "field_name": result.field_name,
                        "final_value": result.final_value,
                        "state": result.state,
                        "confidence": result.confidence,
                        "similarity": result.similarity,
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
                "created_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
            }

            db.extractions.insert_one(extraction_record)
            print(" Extraction and arbitration results saved to MongoDB")
        except Exception as e:
            print(f" Failed to save to MongoDB: {e}")

        # Build arbitration_results in desired format for API response
        arbitration_results_formatted = {
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
        }

        return {
            "status": "success",
            "document_id": document_id,
            "ocr_used": ocr_used,
            "page_count": page_count,
            "header_metadata": header_metadata,
            "arbitration_results": arbitration_results_formatted,
            "arbitration_summary": arbitration_summary,
            "regex_output": regex_output,
            "rag_output": rag_output,
            "verification_status": "pending_human_review",
            "created_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        }
    finally:
        rag_service.delete_document_data(document_id)

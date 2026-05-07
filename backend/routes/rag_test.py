import asyncio
import re
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


DIRECTIVE_KEYWORD_RE = re.compile(
    r"\b(" 
    r"direct(?:ed|s|ive|ives|ion|ions)?|"
    r"order(?:ed|s|ing)?|"
    r"shall|must|required|ensure|comply|compliance|"
    r"within|forthwith|immediately|"
    r"days?|weeks?|months?|deadline|time\s+limit|"
    r"affidavit|report|submit|file|produce|deposit|pay|release|implement|appoint|constitute"
    r")\b",
    re.IGNORECASE,
)


def _retrieval_depth(page_count: int) -> int:
    """Use wider retrieval for long judgments where orders may span many pages."""
    if page_count >= 100:
        return 18
    if page_count >= 70:
        return 15
    if page_count >= 30:
        return 12
    return 5


def _tail_page_limit(page_count: int) -> int:
    """Include more final pages for long judgments without flooding the LLM."""
    if page_count >= 100:
        return 12
    if page_count >= 70:
        return 10
    if page_count >= 30:
        return 8
    return 4


def _format_paragraph_context(paragraphs: list, max_chars: int) -> str:
    parts = []
    current_page = None
    total_chars = 0

    for paragraph in paragraphs:
        text = getattr(paragraph, "text", "").strip()
        page = getattr(paragraph, "page", None)
        if not text:
            continue

        prefix = f"\n\n[Page {page}]\n" if page != current_page else "\n\n"
        entry = f"{prefix}{text}"
        if total_chars + len(entry) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 500:
                parts.append(entry[:remaining])
            break

        parts.append(entry)
        total_chars += len(entry)
        current_page = page

    return "".join(parts).strip()


def _final_pages_context(paragraphs: list, page_count: int) -> str:
    selected_pages = set(_final_page_numbers(paragraphs, page_count))
    selected_paragraphs = [
        paragraph
        for paragraph in paragraphs
        if getattr(paragraph, "page", None) in selected_pages
    ]
    return _format_paragraph_context(selected_paragraphs, max_chars=14000)


def _final_page_numbers(paragraphs: list, page_count: int) -> list[int]:
    pages = sorted({getattr(paragraph, "page", None) for paragraph in paragraphs})
    pages = [page for page in pages if isinstance(page, int)]
    if not pages:
        return []

    return pages[-_tail_page_limit(page_count):]


def _source_page_window_context(paragraphs: list, source_pages: list[int]) -> str:
    if not source_pages:
        return ""

    selected_pages = {
        page + offset
        for page in source_pages
        if isinstance(page, int)
        for offset in (-1, 0, 1)
    }
    selected_paragraphs = [
        paragraph
        for paragraph in paragraphs
        if getattr(paragraph, "page", None) in selected_pages
    ]
    return _format_paragraph_context(selected_paragraphs, max_chars=10000)


def _directive_focus_context(paragraphs: list, page_count: int) -> str:
    """Pull paragraphs that contain order language, plus close neighbors."""
    if page_count < 30 or not paragraphs:
        return ""

    selected_keys: set[tuple[int | None, int | None]] = set()
    selected_paragraphs = []

    for index, paragraph in enumerate(paragraphs):
        text = getattr(paragraph, "text", "").strip()
        if not text or not DIRECTIVE_KEYWORD_RE.search(text):
            continue

        start = max(0, index - 1)
        end = min(len(paragraphs), index + 2)
        for candidate in paragraphs[start:end]:
            candidate_key = (
                getattr(candidate, "page", None),
                getattr(candidate, "para_index", None),
            )
            if candidate_key in selected_keys:
                continue
            selected_keys.add(candidate_key)
            selected_paragraphs.append(candidate)

    return _format_paragraph_context(selected_paragraphs, max_chars=12000)


def _build_large_document_context(
    retrieved_context: str,
    operative_paragraphs: list,
    source_pages: list[int],
    page_count: int,
) -> str:
    """
    Large judgments need both semantic hits and the actual closing order pages.
    Retrieval alone can miss later directions when the operative portion spans
    multiple pages, while tail pages alone can miss departments named nearby.
    """
    if page_count < 30:
        return retrieved_context

    directive_focus = _directive_focus_context(operative_paragraphs, page_count)
    sections = []
    if directive_focus:
        sections.append(f"[Directive-focused operative paragraphs]\n{directive_focus}")

    if retrieved_context.strip():
        sections.append(f"[Retrieved directive/deadline passages]\n{retrieved_context.strip()}")

    source_window = _source_page_window_context(operative_paragraphs, source_pages)
    if source_window:
        sections.append(f"[Pages around retrieved evidence]\n{source_window}")

    final_pages = _final_pages_context(operative_paragraphs, page_count)
    if final_pages:
        sections.append(f"[Final operative pages]\n{final_pages}")

    combined = "\n\n---\n\n".join(section for section in sections if section.strip())
    return combined[:28000]


def _large_document_source_pages(
    source_pages: list[int],
    operative_paragraphs: list,
    page_count: int,
) -> list[int]:
    pages = []
    directive_pages = {
        getattr(paragraph, "page", None)
        for paragraph in operative_paragraphs
        if getattr(paragraph, "text", "").strip()
        and DIRECTIVE_KEYWORD_RE.search(getattr(paragraph, "text", ""))
    }
    for page in [*source_pages, *_final_page_numbers(operative_paragraphs, page_count)]:
        if isinstance(page, int) and page not in pages:
            pages.append(page)
    for page in sorted(page for page in directive_pages if isinstance(page, int)):
        if page not in pages:
            pages.append(page)
    return pages


def _large_document_source_chunks(
    existing_chunks: list[dict],
    operative_paragraphs: list,
    page_count: int,
) -> list[dict]:
    if page_count < 30:
        return existing_chunks

    selected_pages = set(_final_page_numbers(operative_paragraphs, page_count))
    synthetic_chunks = []
    for index, paragraph in enumerate(operative_paragraphs):
        page = getattr(paragraph, "page", None)
        text = getattr(paragraph, "text", "").strip()
        if page not in selected_pages or not text:
            continue
        synthetic_chunks.append(
            {
                "child_id": f"operative_context_{index}",
                "parent_id": "large_document_context",
                "page": page,
                "score": None,
                "text": text[:1000],
            }
        )
        if len(synthetic_chunks) >= 80:
            break

    for index, paragraph in enumerate(operative_paragraphs):
        page = getattr(paragraph, "page", None)
        text = getattr(paragraph, "text", "").strip()
        if page in selected_pages or not text or not DIRECTIVE_KEYWORD_RE.search(text):
            continue
        synthetic_chunks.append(
            {
                "child_id": f"directive_context_{index}",
                "parent_id": "large_document_context",
                "page": page,
                "score": None,
                "text": text[:1000],
            }
        )
        if len(synthetic_chunks) >= 120:
            break

    return [*existing_chunks, *synthetic_chunks]


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
        operative_text = raw_text

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

                retrieval_top_k = _retrieval_depth(page_count)
                print(f"  [RAG] Retrieval depth selected for {page_count} pages: top_k={retrieval_top_k}")

                retrieval_result = rag_service.retrieve_context(
                    semantic_query=semantic_query,
                    keyword_query=keyword_query,
                    top_k=retrieval_top_k,
                    include_sources=True,
                )
                retrieved_context = retrieval_result.get("context", "")
                source_pages = retrieval_result.get("source_pages", [])

                if not retrieved_context:
                    raise Exception("Failed to retrieve context")

                extraction_context = _build_large_document_context(
                    retrieved_context=retrieved_context,
                    operative_paragraphs=operative_paragraphs,
                    source_pages=source_pages,
                    page_count=page_count,
                )
                print(
                    "  [RAG] Extraction context prepared: "
                    f"{len(extraction_context)} chars from {len(source_pages)} source pages"
                )

                rag_output = generator.generate(context=extraction_context, hard_facts={})
                rag_output["RAG_Source_Pages"] = _large_document_source_pages(
                    source_pages,
                    operative_paragraphs,
                    page_count,
                )
                rag_output["RAG_Source_Chunks"] = _large_document_source_chunks(
                    retrieval_result.get("source_chunks", []),
                    operative_paragraphs,
                    page_count,
                )
                
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

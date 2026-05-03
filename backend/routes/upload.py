import hashlib

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from backend.services.operative_isolator import isolate_operative_section
from backend.services.paragraph_segmenter import segment_pages_into_paragraphs
from backend.services.pdf_reader import extract_pdf_text
from backend.services.utils import (
    EmptyPDFError,
    InvalidPDFError,
    OCRFailureError,
    PasswordProtectedPDFError,
    logger,
)


router = APIRouter()

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


def _validate_pdf_upload(file: UploadFile, payload: bytes) -> None:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    if not filename.endswith(".pdf") and content_type not in {
        "application/pdf",
        "application/x-pdf",
    }:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported.",
        )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF is empty.",
        )

    if len(payload) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF exceeds maximum size of 20MB.",
        )

    if not payload.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid PDF.",
        )


def _doc_id(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:24]


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    include_pages: bool = Query(
        default=True,
        description="Include page-wise extracted text.",
    ),
    include_paragraphs: bool = Query(
        default=False,
        description="Include paragraph-wise text with page mapping. Use only when the UI needs highlighting maps.",
    ),
    include_operative_paragraphs: bool = Query(
        default=False,
        description="Include operative section paragraph text instead of only operative metadata.",
    ),
) -> dict:
    payload = await file.read()
    _validate_pdf_upload(file, payload)

    doc_id = _doc_id(payload)

    try:
        pages, ocr_used, page_count = extract_pdf_text(payload)
        paragraphs = segment_pages_into_paragraphs(pages)
        if not paragraphs:
            raise EmptyPDFError("No paragraphs could be segmented from extracted text.")

        operative_section = isolate_operative_section(paragraphs)

    except PasswordProtectedPDFError as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc)) from exc
    except InvalidPDFError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except EmptyPDFError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except OCRFailureError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OCR fallback failed: {exc}",
        ) from exc

    logger.info(
        "text_extraction_summary doc_id=%s ocr_used=%s page_count=%s para_count=%s operative_detected=%s marker=%s",
        doc_id,
        ocr_used,
        page_count,
        len(paragraphs),
        operative_section.detected,
        operative_section.marker_matched,
    )

    full_text = "\n\n".join(page.text for page in pages if page.text.strip())

    response = {
        "doc_id": doc_id,
        "ocr_used": ocr_used,
        "stats": {
            "page_count": page_count,
            "paragraph_count": len(paragraphs),
            "character_count": len(full_text),
        },
        "full_text": full_text,
        "operative_section": operative_section.to_dict(
            include_paragraphs=include_operative_paragraphs
        ),
    }

    if include_pages:
        response["pages"] = [page.to_dict() for page in pages]
    if include_paragraphs:
        response["paragraphs"] = [paragraph.to_dict() for paragraph in paragraphs]

    return response

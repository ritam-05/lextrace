import fitz

from backend.services.ocr import ocr_pdf_bytes
from backend.services.sanitizer import sanitize_text
from backend.services.utils import (
    EmptyPDFError,
    InvalidPDFError,
    OCRFailureError,
    PageText,
    PasswordProtectedPDFError,
)


MIN_DOCUMENT_TEXT_CHARS = 10


def _open_pdf(pdf_bytes: bytes) -> fitz.Document:
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise InvalidPDFError("Uploaded file is not a readable PDF.") from exc


def extract_pdf_text(pdf_bytes: bytes) -> tuple[list[PageText], bool, int]:
    """
    Extract text from a PDF.

    Embedded text is attempted for the full document first. If that produces no
    usable text, the whole PDF is OCR'd and the OCR output is returned in the
    same page structure so downstream extraction stays unchanged.
    """
    document = _open_pdf(pdf_bytes)
    try:
        if document.needs_pass:
            raise PasswordProtectedPDFError("Password-protected PDFs are not supported.")

        page_count = document.page_count
        if page_count == 0:
            raise EmptyPDFError("PDF contains no pages.")

        digital_pages: list[PageText] = []

        for page_index in range(page_count):
            page_number = page_index + 1
            page = document.load_page(page_index)
            digital_text = sanitize_text(page.get_text("text") or "")
            digital_pages.append(PageText(page=page_number, text=digital_text))

        digital_text_length = sum(len(page.text.strip()) for page in digital_pages)
        if digital_text_length >= MIN_DOCUMENT_TEXT_CHARS:
            return digital_pages, False, page_count

        try:
            ocr_page_texts = ocr_pdf_bytes(pdf_bytes)
        except OCRFailureError:
            raise

        pages = [
            PageText(page=index, text=sanitize_text(text))
            for index, text in enumerate(ocr_page_texts, start=1)
        ]

        if not any(page.text.strip() for page in pages):
            raise EmptyPDFError("No extractable text found in PDF.")

        return pages, True, page_count
    finally:
        document.close()

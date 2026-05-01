import fitz

from backend.services.ocr import ocr_pdf_page
from backend.services.sanitizer import sanitize_text
from backend.services.utils import (
    EmptyPDFError,
    InvalidPDFError,
    OCRFailureError,
    PageText,
    PasswordProtectedPDFError,
)


MIN_DIGITAL_TEXT_CHARS = 10


def _open_pdf(pdf_bytes: bytes) -> fitz.Document:
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise InvalidPDFError("Uploaded file is not a readable PDF.") from exc


def extract_pdf_text(pdf_bytes: bytes) -> tuple[list[PageText], bool, int]:
    """
    Extract text from a PDF.

    Digital text is preferred per page. If a page has little/no embedded text,
    OCR is attempted for that page so mixed digital/scanned PDFs are handled.
    """
    document = _open_pdf(pdf_bytes)
    try:
        if document.needs_pass:
            raise PasswordProtectedPDFError("Password-protected PDFs are not supported.")

        page_count = document.page_count
        if page_count == 0:
            raise EmptyPDFError("PDF contains no pages.")

        pages: list[PageText] = []
        ocr_used = False

        for page_index in range(page_count):
            page_number = page_index + 1
            page = document.load_page(page_index)
            digital_text = sanitize_text(page.get_text("text") or "")

            if len(digital_text) >= MIN_DIGITAL_TEXT_CHARS:
                pages.append(PageText(page=page_number, text=digital_text))
                continue

            ocr_used = True
            try:
                ocr_text = sanitize_text(ocr_pdf_page(pdf_bytes, page_number))
            except OCRFailureError:
                raise

            best_text = ocr_text if len(ocr_text) >= len(digital_text) else digital_text
            pages.append(PageText(page=page_number, text=best_text))

        if not any(page.text.strip() for page in pages):
            raise EmptyPDFError("No extractable text found in PDF.")

        return pages, ocr_used, page_count
    finally:
        document.close()

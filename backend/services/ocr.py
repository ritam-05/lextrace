from io import BytesIO
from pathlib import Path
import os
import shutil

from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract

from backend.services.utils import OCRFailureError, logger


def _first_existing_path(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _configure_tesseract() -> None:
    if shutil.which("tesseract"):
        return

    tesseract_path = _first_existing_path(
        [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
    )
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)


def _find_poppler_path() -> str | None:
    if shutil.which("pdftoppm"):
        return None

    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = [
        Path(r"C:\Program Files\poppler\Library\bin"),
        Path(r"C:\Program Files\poppler\bin"),
    ]

    if local_app_data:
        winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        candidates.extend(winget_packages.glob("oschwartz10612.Poppler_*/*/Library/bin"))

    poppler_bin = _first_existing_path(
        [candidate for candidate in candidates if (candidate / "pdftoppm.exe").exists()]
    )
    return str(poppler_bin) if poppler_bin else None


_configure_tesseract()
POPPLER_PATH = _find_poppler_path()


def ocr_image(image: Image.Image) -> str:
    """Run Tesseract OCR on a PIL image."""
    try:
        return pytesseract.image_to_string(image, lang="eng")
    except Exception as exc:
        raise OCRFailureError(f"Tesseract OCR failed: {exc}") from exc


def ocr_pdf_page(pdf_bytes: bytes, page_number: int, dpi: int = 300) -> str:
    """OCR a single 1-based PDF page using pdf2image and Tesseract."""
    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
            fmt="png",
            thread_count=1,
            poppler_path=POPPLER_PATH,
        )
    except Exception as exc:
        raise OCRFailureError(
            "PDF page rasterization failed. Ensure Poppler is installed and available."
        ) from exc

    if not images:
        raise OCRFailureError(f"No raster image produced for page {page_number}.")

    logger.info("Running OCR fallback for page=%s", page_number)
    return ocr_image(images[0])


def ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 300) -> list[str]:
    """OCR every page of a PDF. Kept available for full-document OCR fallback."""
    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            fmt="png",
            thread_count=1,
            poppler_path=POPPLER_PATH,
        )
    except Exception as exc:
        raise OCRFailureError(
            "PDF rasterization failed. Ensure Poppler is installed and available."
        ) from exc

    extracted: list[str] = []
    for index, image in enumerate(images, start=1):
        logger.info("Running OCR fallback for page=%s", index)
        extracted.append(ocr_image(image))
    return extracted


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

import logging
from dataclasses import asdict, dataclass
from typing import Any


LOGGER_NAME = "lextrace.stage1"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = get_logger()


@dataclass(frozen=True)
class PageText:
    page: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Paragraph:
    page: int
    para_index: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperativeSection:
    detected: bool
    start_para_index: int | None
    marker_matched: str | None
    paragraphs: list[Paragraph]

    def to_dict(self, include_paragraphs: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "detected": self.detected,
            "start_para_index": self.start_para_index,
            "marker_matched": self.marker_matched,
        }
        if include_paragraphs:
            payload["paragraphs"] = [paragraph.to_dict() for paragraph in self.paragraphs]
        return payload


class ExtractionError(Exception):
    """Base class for deterministic extraction failures."""


class InvalidPDFError(ExtractionError):
    """Raised when the uploaded file cannot be parsed as a PDF."""


class PasswordProtectedPDFError(ExtractionError):
    """Raised when a PDF is encrypted and cannot be opened."""


class EmptyPDFError(ExtractionError):
    """Raised when no text can be extracted from a PDF."""


class OCRFailureError(ExtractionError):
    """Raised when OCR fallback is required but fails."""

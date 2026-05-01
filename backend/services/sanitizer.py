import re


CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
HYPHENATED_LINEBREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")


def sanitize_text(text: str) -> str:
    """Normalize PDF/OCR text while preserving paragraph-breaking newlines."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = CONTROL_CHARS_RE.sub(" ", normalized)
    normalized = HYPHENATED_LINEBREAK_RE.sub(r"\1\2", normalized)

    lines = []
    for line in normalized.split("\n"):
        compacted = MULTI_SPACE_RE.sub(" ", line).strip()
        lines.append(compacted)

    normalized = "\n".join(lines)
    normalized = EXCESS_NEWLINES_RE.sub("\n\n", normalized)
    return normalized.strip()


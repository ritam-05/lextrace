import re

from backend.services.utils import PageText, Paragraph


BLANK_LINE_RE = re.compile(r"\n\s*\n+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?:;])\s+(?=[A-Z(])")


def _split_long_block(text: str, max_chars: int = 1800) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = SENTENCE_BOUNDARY_RE.split(text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def segment_pages_into_paragraphs(pages: list[PageText]) -> list[Paragraph]:
    """Segment sanitized page text into global paragraphs while preserving page origin."""
    paragraphs: list[Paragraph] = []
    para_index = 0

    for page in pages:
        blocks = [block.strip() for block in BLANK_LINE_RE.split(page.text) if block.strip()]
        if not blocks and page.text.strip():
            blocks = [page.text.strip()]
        if len(blocks) == 1:
            lines = [line.strip() for line in page.text.splitlines() if line.strip()]
            if len(lines) > 1:
                blocks = lines

        for block in blocks:
            normalized = re.sub(r"\s*\n\s*", " ", block).strip()
            normalized = re.sub(r"\s{2,}", " ", normalized)
            for chunk in _split_long_block(normalized):
                if chunk:
                    paragraphs.append(
                        Paragraph(page=page.page, para_index=para_index, text=chunk)
                    )
                    para_index += 1

    return paragraphs

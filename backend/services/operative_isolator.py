import re

from backend.services.utils import OperativeSection, Paragraph


OPERATIVE_MARKERS: tuple[str, ...] = (
    "in the result",
    "for the foregoing reasons",
    "we accordingly",
    "it is hereby ordered",
    "ORDER :",
    "JUDGMENT :",
    "the petition is allowed",
    "the petition is dismissed",
    "the appeal is allowed",
    "disposed of in terms",
    "the writ petition is",
    "accordingly directed",
    "petition stands rejected",
    "petition is rejected",
    "petition stands allowed",
    "stands disposed of",
)


def _marker_pattern(marker: str) -> re.Pattern[str]:
    escaped = re.escape(marker.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    escaped = escaped.replace(r"\:", r"\s*:")
    return re.compile(escaped, flags=re.IGNORECASE)


MARKER_PATTERNS = tuple((marker, _marker_pattern(marker)) for marker in OPERATIVE_MARKERS)


def isolate_operative_section(paragraphs: list[Paragraph]) -> OperativeSection:
    """
    Locate the operative section using Indian legal disposition markers.

    Markers in the latter part of the document are preferred because headings
    such as "JUDGMENT :" can appear before facts and arguments.
    """
    if not paragraphs:
        return OperativeSection(False, None, None, [])

    preferred_start = max(0, int(len(paragraphs) * 0.4))
    candidate_ranges = (
        paragraphs[preferred_start:],
        paragraphs,
    )

    for candidate_range in candidate_ranges:
        for paragraph in candidate_range:
            for marker, pattern in MARKER_PATTERNS:
                if pattern.search(paragraph.text):
                    return OperativeSection(
                        detected=True,
                        start_para_index=paragraph.para_index,
                        marker_matched=marker,
                        paragraphs=paragraphs[paragraph.para_index :],
                    )

    return OperativeSection(False, None, None, [])

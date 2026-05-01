import re
from dataclasses import dataclass

from backend.services.utils import ExtractedField, OperativeSection, Paragraph


@dataclass(frozen=True)
class RegexPattern:
    pattern_id: str
    pattern: re.Pattern[str]
    confidence: float
    group: str = "value"


FIELD_NAMES = (
    "case_number",
    "judgment_date",
    "court_name",
    "parties",
    "deadline_raw",
)


CASE_NUMBER_PATTERNS = (
    RegexPattern(
        "case_number.criminal_petition_001",
        re.compile(
            r"\b(?P<value>Criminal\s+Petition\s+(?:No\.?|Nos\.?)?\s*[\w./-]+(?:\s*(?:of|/)\s*\d{4})?)\b",
            re.IGNORECASE,
        ),
        0.93,
    ),
    RegexPattern(
        "case_number.wp_c_001",
        re.compile(
            r"\b(?P<value>W\.?\s*P\.?\s*\(?C\)?\.?\s*(?:No\.?|Nos\.?)\s*[\w./-]+(?:\s*(?:of|/)\s*\d{4})?)\b",
            re.IGNORECASE,
        ),
        0.92,
    ),
    RegexPattern(
        "case_number.civil_appeal_001",
        re.compile(
            r"\b(?P<value>Civil\s+Appeal\s+(?:No\.?|Nos\.?)\s*[\w./-]+(?:\s*(?:of|/)\s*\d{4})?)\b",
            re.IGNORECASE,
        ),
        0.92,
    ),
    RegexPattern(
        "case_number.criminal_appeal_001",
        re.compile(
            r"\b(?P<value>Criminal\s+Appeal\s+(?:No\.?|Nos\.?)\s*[\w./-]+(?:\s*(?:of|/)\s*\d{4})?)\b",
            re.IGNORECASE,
        ),
        0.92,
    ),
    RegexPattern(
        "case_number.slp_001",
        re.compile(
            r"\b(?P<value>(?:S\.?\s*L\.?\s*P\.?|Special\s+Leave\s+Petition)\s*(?:\(?[A-Z]+\)?\s*)?(?:No\.?|Nos\.?)\s*[\w./-]+(?:\s*(?:of|/)\s*\d{4})?)\b",
            re.IGNORECASE,
        ),
        0.9,
    ),
    RegexPattern(
        "case_number.writ_petition_001",
        re.compile(
            r"\b(?P<value>Writ\s+Petition\s*(?:\(?[A-Z]+\)?\s*)?(?:No\.?|Nos\.?)\s*[\w./-]+(?:\s*(?:of|/)\s*\d{4})?)\b",
            re.IGNORECASE,
        ),
        0.9,
    ),
)


DATE_PATTERNS = (
    RegexPattern(
        "judgment_date.pronounced_on_001",
        re.compile(
            r"\bPronounced\s+on\s*:?\s*(?P<value>\d{1,2}[./-]\d{1,2}[./-]\d{4})\b",
            re.IGNORECASE,
        ),
        0.94,
    ),
    RegexPattern(
        "judgment_date.dated_this_001",
        re.compile(
            r"\bDATED\s+THIS\s+THE\s+(?P<value>\d{1,2}(?:st|nd|rd|th)?\s+DAY\s+OF\s+"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})\b",
            re.IGNORECASE,
        ),
        0.9,
    ),
    RegexPattern(
        "judgment_date.numeric_slash_001",
        re.compile(r"\b(?P<value>\d{1,2}/\d{1,2}/\d{4})\b"),
        0.88,
    ),
    RegexPattern(
        "judgment_date.numeric_dot_001",
        re.compile(r"\b(?P<value>\d{1,2}\.\d{1,2}\.\d{4})\b"),
        0.88,
    ),
    RegexPattern(
        "judgment_date.numeric_dash_001",
        re.compile(r"\b(?P<value>\d{1,2}-\d{1,2}-\d{4})\b"),
        0.88,
    ),
    RegexPattern(
        "judgment_date.day_month_001",
        re.compile(
            r"\b(?P<value>\d{1,2}(?:st|nd|rd|th)?\s+"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{4})\b",
            re.IGNORECASE,
        ),
        0.86,
    ),
    RegexPattern(
        "judgment_date.month_day_001",
        re.compile(
            r"\b(?P<value>(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})\b",
            re.IGNORECASE,
        ),
        0.86,
    ),
)


COURTS = (
    "Supreme Court of India",
    "Allahabad High Court",
    "Andhra Pradesh High Court",
    "Bombay High Court",
    "Calcutta High Court",
    "Chhattisgarh High Court",
    "Delhi High Court",
    "Gauhati High Court",
    "Gujarat High Court",
    "Himachal Pradesh High Court",
    "High Court of Jammu and Kashmir and Ladakh",
    "Jharkhand High Court",
    "Karnataka High Court",
    "Kerala High Court",
    "Madhya Pradesh High Court",
    "Madras High Court",
    "Manipur High Court",
    "Meghalaya High Court",
    "Orissa High Court",
    "Patna High Court",
    "Punjab and Haryana High Court",
    "Rajasthan High Court",
    "Sikkim High Court",
    "Telangana High Court",
    "Tripura High Court",
    "Uttarakhand High Court",
)


COURT_PATTERNS = tuple(
    RegexPattern(
        f"court_name.{re.sub(r'[^a-z0-9]+', '_', court.lower()).strip('_')}_001",
        re.compile(rf"\b(?P<value>{re.escape(court)})\b", re.IGNORECASE),
        0.96,
    )
    for court in COURTS
) + (
    RegexPattern(
        "court_name.high_court_of_karnataka_at_bengaluru_001",
        re.compile(
            r"\b(?:IN\s+THE\s+)?(?P<value>HIGH\s+COURT\s+OF\s+KARNATAKA(?:\s+AT\s+BENGALURU)?)\b",
            re.IGNORECASE,
        ),
        0.97,
    ),
    RegexPattern(
        "court_name.high_court_of_state_001",
        re.compile(
            r"\b(?:IN\s+THE\s+)?(?P<value>High\s+Court\s+of\s+(?:Judicature\s+at\s+)?"
            r"(?:Allahabad|Andhra\s+Pradesh|Bombay|Calcutta|Chhattisgarh|Delhi|Gauhati|Gujarat|"
            r"Himachal\s+Pradesh|Jammu\s+and\s+Kashmir\s+and\s+Ladakh|Jharkhand|Karnataka|Kerala|"
            r"Madhya\s+Pradesh|Madras|Manipur|Meghalaya|Orissa|Patna|Punjab\s+and\s+Haryana|"
            r"Rajasthan|Sikkim|Telangana|Tripura|Uttarakhand)(?:\s+at\s+[A-Z][A-Za-z]+)?)\b",
            re.IGNORECASE,
        ),
        0.82,
    ),
)


PARTY_PATTERNS = (
    RegexPattern(
        "parties.versus_001",
        re.compile(
            r"\b(?P<value>[A-Z][A-Za-z0-9 .,&'()/-]{2,80}?\s+v(?:s\.?|\.?)\s+"
            r"[A-Z][A-Za-z0-9 .,&'()/-]{2,80})\b",
            re.IGNORECASE,
        ),
        0.82,
    ),
    RegexPattern(
        "parties.in_matter_001",
        re.compile(
            r"\b(?P<value>In\s+the\s+matter\s+of\s+[A-Z][A-Za-z0-9 .,&'()/-]{2,160})\b",
            re.IGNORECASE,
        ),
        0.78,
    ),
)


DEADLINE_PATTERNS = (
    RegexPattern(
        "deadline.within_duration_001",
        re.compile(
            r"\b(?P<value>within\s+\d+\s+(?:day|days|week|weeks|month|months))\b",
            re.IGNORECASE,
        ),
        0.88,
    ),
    RegexPattern(
        "deadline.duration_from_001",
        re.compile(
            r"\b(?P<value>\d+\s+(?:day|days|week|weeks|month|months)\s+from(?:\s+the\s+date\s+of)?(?:\s+[A-Za-z ]{1,60})?)\b",
            re.IGNORECASE,
        ),
        0.78,
    ),
)


PATTERNS_BY_FIELD: dict[str, tuple[RegexPattern, ...]] = {
    "case_number": CASE_NUMBER_PATTERNS,
    "judgment_date": DATE_PATTERNS,
    "court_name": COURT_PATTERNS,
    "parties": PARTY_PATTERNS,
    "deadline_raw": DEADLINE_PATTERNS,
}


def _clean_value(value: str) -> str:
    return re.sub(r"\s{2,}", " ", value).strip(" \t\n\r.,;")


def _title_if_upper(value: str) -> str:
    if not value.isupper():
        return value
    titled = value.title()
    return re.sub(r"\b(Of|At|And)\b", lambda match: match.group(1).lower(), titled)


def _empty_field() -> ExtractedField:
    return ExtractedField(value=None, pattern_id=None, confidence=0.0, source=None)


def _search_field(
    field_name: str,
    paragraphs: list[Paragraph],
    operative_section: OperativeSection,
) -> ExtractedField:
    search_space = paragraphs
    if field_name in {"case_number", "judgment_date", "court_name", "parties"}:
        header_count = min(len(paragraphs), 40)
        search_space = paragraphs[:header_count] + paragraphs[header_count:]
    if field_name == "deadline_raw" and operative_section.detected:
        search_space = operative_section.paragraphs + [
            paragraph
            for paragraph in paragraphs
            if paragraph.para_index < (operative_section.start_para_index or 0)
        ]

    for paragraph in search_space:
        for regex_pattern in PATTERNS_BY_FIELD[field_name]:
            match = regex_pattern.pattern.search(paragraph.text)
            if not match:
                continue
            value = _clean_value(match.group(regex_pattern.group))
            if field_name == "court_name":
                value = _title_if_upper(value)
            if value:
                return ExtractedField(
                    value=value,
                    pattern_id=regex_pattern.pattern_id,
                    confidence=regex_pattern.confidence,
                    source=paragraph,
                )

    return _empty_field()


def _extract_parties_from_between_and(paragraphs: list[Paragraph]) -> ExtractedField:
    header = paragraphs[:40]
    between_index = next(
        (
            index
            for index, paragraph in enumerate(header)
            if re.fullmatch(r"\s*BETWEEN\s*:?\s*", paragraph.text, re.IGNORECASE)
        ),
        None,
    )
    if between_index is None:
        return _empty_field()

    petitioner: Paragraph | None = None
    respondent: Paragraph | None = None
    for paragraph in header[between_index + 1 :]:
        if petitioner is None and "PETITIONER" in paragraph.text.upper():
            petitioner = paragraph
            continue
        if re.fullmatch(r"\s*AND\s*:?\s*", paragraph.text, re.IGNORECASE):
            continue
        if petitioner is not None and "RESPONDENT" in paragraph.text.upper():
            respondent = paragraph
            break
        if petitioner is not None and respondent is None and re.match(r"\s*\d+\s*\.", paragraph.text):
            respondent = paragraph
            break

    if not petitioner or not respondent:
        return _empty_field()

    petitioner_name = re.split(r"\bW/O\b|\bS/O\b|\bD/O\b|\.{3,}\s*PETITIONER", petitioner.text, flags=re.IGNORECASE)[0]
    respondent_name = re.split(r"\bHAL\b|\bW/O\b|\bS/O\b|\bD/O\b|\.{3,}\s*RESPONDENTS?", respondent.text, flags=re.IGNORECASE)[0]
    respondent_name = re.sub(r"^\s*\d+\s*\.\s*", "", respondent_name)

    value = f"{_clean_value(petitioner_name)} v. {_clean_value(respondent_name)}"
    if len(value) <= 5:
        return _empty_field()

    return ExtractedField(
        value=value,
        pattern_id="parties.between_and_001",
        confidence=0.86,
        source=petitioner,
    )


def extract_metadata(
    paragraphs: list[Paragraph],
    operative_section: OperativeSection,
) -> dict[str, ExtractedField]:
    """Extract deterministic metadata with source paragraph and pattern IDs."""
    metadata = {
        field_name: _search_field(field_name, paragraphs, operative_section)
        for field_name in FIELD_NAMES
    }
    header_parties = _extract_parties_from_between_and(paragraphs)
    if header_parties.value:
        metadata["parties"] = header_parties
    return metadata

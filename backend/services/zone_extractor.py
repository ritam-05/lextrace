import re
from dataclasses import dataclass
from typing import Any


ROLE_KEYWORDS = {
    "PETITIONER",
    "RESPONDENT",
    "APPELLANT",
    "APPLICANT",
    "CLAIMANT",
    "PLAINTIFF",
    "DEFENDANT",
    "ACCUSED",
    "COMPLAINANT",
    "PROSECUTION",
    "STATE",
    "REVENUE",
    "ASSESSEE",
    "OPERATIONAL CREDITOR",
    "FINANCIAL CREDITOR",
    "CORPORATE DEBTOR",
    "LAND OWNER",
    "HUSBAND",
    "WIFE",
    "ELECTION PETITIONER",
    "RETURNED CANDIDATE",
    "REVISION PETITIONER",
    "REVISION RESPONDENT",
    "DECREE HOLDER",
    "JUDGMENT DEBTOR",
    "INTERVENOR",
    "INTERVENER",
    "THIRD PARTY",
}

PETITIONER_ROLES = {
    "PETITIONER",
    "PETITIONERS",
    "APPELLANT",
    "APPELLANTS",
    "APPLICANT",
    "APPLICANTS",
    "CLAIMANT",
    "CLAIMANTS",
    "PLAINTIFF",
    "PLAINTIFFS",
    "ASSESSEE",
    "OPERATIONAL CREDITOR",
    "FINANCIAL CREDITOR",
    "LAND OWNER",
    "HUSBAND",
    "WIFE",
    "ELECTION PETITIONER",
    "REVISION PETITIONER",
    "DECREE HOLDER",
}

RESPONDENT_ROLES = {
    "RESPONDENT",
    "RESPONDENTS",
    "DEFENDANT",
    "DEFENDANTS",
    "ACCUSED",
    "COMPLAINANT",
    "PROSECUTION",
    "STATE",
    "REVENUE",
    "CORPORATE DEBTOR",
    "RETURNED CANDIDATE",
    "REVISION RESPONDENT",
    "JUDGMENT DEBTOR",
    "INTERVENOR",
    "INTERVENER",
    "THIRD PARTY",
}

ROLE_VARIANTS = sorted(
    ROLE_KEYWORDS
    | PETITIONER_ROLES
    | RESPONDENT_ROLES
    | {f"{role}S" for role in ROLE_KEYWORDS if not role.endswith("S")},
    key=len,
    reverse=True,
)

ROLE_RE = re.compile(
    r"(?:\.{2,}|-{2,})?\s*\b("
    + "|".join(re.escape(role) for role in ROLE_VARIANTS)
    + r")\b\.?",
    re.IGNORECASE,
)
ADVOCATE_RE = re.compile(
    r"\(?\s*(?:BY|THROUGH|FOR)\s+[^.;\n\r]*(?:ADVOCATE|ADV\.?|COUNSEL)?\)?",
    re.IGNORECASE,
)
DATE_VALUE_RE = re.compile(
    r"("
    r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|"
    r"\d{1,2}(?:ST|ND|RD|TH)?\s+(?:DAY\s+OF\s+)?"
    r"(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|"
    r"JUL(?:Y)?|AUG(?:UST)?|SEP(?:TEMBER)?|SEPT|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)"
    r",?\s+\d{2,4}|"
    r"(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|"
    r"JUL(?:Y)?|AUG(?:UST)?|SEP(?:TEMBER)?|SEPT|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)"
    r"\s+\d{1,2}(?:ST|ND|RD|TH)?,?\s+\d{2,4}"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ZoneParagraph:
    index: int
    page: int
    text: str

    @property
    def source(self) -> dict[str, Any]:
        return {"page": self.page, "paragraph_text": self.text}


@dataclass(frozen=True)
class SpanCandidate:
    value: str
    paragraph: ZoneParagraph
    start: int
    end: int
    score: int = 1


class BaseExtractor:
    TOP_FIELD_LIMIT = 45
    PARTY_SCAN_LIMIT = 90
    HEADER_LIMIT = 30

    def __init__(self, paragraphs: list[dict[str, Any]] | list[ZoneParagraph]):
        self.paragraphs = self._normalize_paragraphs(paragraphs)
        self.header_zone = self._header_zone(self.paragraphs)
        self.body_zone = self._body_zone(self.paragraphs, self.header_zone)

    def extract_case_number(self) -> dict[str, Any]:
        return self._empty_field()

    def extract_case_type(self, case_number: str | None = None) -> str:
        text = (case_number or "").upper()
        if "CRIMINAL" in text:
            return "Criminal Petition"
        if "CIVIL" in text:
            return "Civil Case"
        if "WRIT" in text or "W.P" in text or "WP" in text:
            return "Writ Petition"
        if "APPEAL" in text:
            return "Appeal"
        if "PETITION" in text:
            return "Petition"
        return ""

    def extract_judgment_date(self) -> dict[str, Any]:
        return self._empty_field()

    def extract_bench(self) -> dict[str, Any]:
        return self._empty_field()

    def extract_court_name(self) -> dict[str, Any]:
        return self._empty_field()

    def extract_parties(self) -> dict[str, dict[str, Any]]:
        return PartyExtractor(self.paragraphs).extract()

    def extract_all(self) -> dict[str, Any]:
        case_number = self.extract_case_number()
        parties = self.extract_parties()
        fields = {
            "case_number": case_number,
            "case_type": self.extract_case_type(case_number.get("value")),
            "judgment_date": self.extract_judgment_date(),
            "bench": self.extract_bench(),
            "court_name": self.extract_court_name(),
            "petitioner": parties["petitioner"],
            "respondent": parties["respondent"],
        }
        return self.validate_fields(fields)

    def validate_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        if "JUSTICE" in fields["case_number"].get("value", "").upper():
            fields["case_number"] = self._empty_field()
        if "COURT" in fields["bench"].get("value", "").upper():
            fields["bench"] = self._empty_field()
        if re.search(r"\bNO\.?\b", fields["court_name"].get("value", ""), re.IGNORECASE):
            fields["court_name"] = self._empty_field()

        values = {
            key: self._normalize_text(value["value"])
            for key, value in fields.items()
            if isinstance(value, dict) and value.get("value")
        }
        for key, value in list(values.items()):
            for other_key, other_value in values.items():
                if key == other_key or not value or not other_value:
                    continue
                if value == other_value or (len(value) > 12 and value in other_value):
                    fields[key] = self._empty_field()
                    break
        return fields

    def find_anchor_window(self, keyword: str, window_size: int = 4) -> list[ZoneParagraph]:
        keyword_upper = keyword.upper()
        seen: set[int] = set()
        paragraphs: list[ZoneParagraph] = []
        for index, paragraph in enumerate(self.paragraphs):
            if keyword_upper not in paragraph.text.upper():
                continue
            start = max(0, index - window_size)
            end = min(len(self.paragraphs), index + window_size + 1)
            for candidate in self.paragraphs[start:end]:
                if candidate.index in seen:
                    continue
                seen.add(candidate.index)
                paragraphs.append(candidate)
        return paragraphs

    @staticmethod
    def _normalize_paragraphs(
        paragraphs: list[dict[str, Any]] | list[ZoneParagraph],
    ) -> list[ZoneParagraph]:
        normalized: list[ZoneParagraph] = []
        for paragraph in paragraphs:
            if isinstance(paragraph, ZoneParagraph):
                if paragraph.text.strip():
                    normalized.append(
                        ZoneParagraph(
                            index=len(normalized),
                            page=paragraph.page,
                            text=paragraph.text.strip(),
                        )
                    )
                continue

            text = str(paragraph.get("text", "")).strip()
            if not text:
                continue
            normalized.append(
                ZoneParagraph(
                    index=len(normalized),
                    page=int(paragraph.get("page") or 0),
                    text=text,
                )
            )
        return normalized

    @classmethod
    def _header_zone(cls, paragraphs: list[ZoneParagraph]) -> list[ZoneParagraph]:
        if not paragraphs:
            return []
        first_page = paragraphs[0].page
        return [paragraph for paragraph in paragraphs if paragraph.page == first_page][
            : cls.HEADER_LIMIT
        ]

    @staticmethod
    def _body_zone(
        paragraphs: list[ZoneParagraph], header_zone: list[ZoneParagraph]
    ) -> list[ZoneParagraph]:
        header_indexes = {paragraph.index for paragraph in header_zone}
        return [paragraph for paragraph in paragraphs if paragraph.index not in header_indexes]

    @staticmethod
    def _empty_field() -> dict[str, Any]:
        return {"value": "", "source": {}}

    @staticmethod
    def _field(candidate: SpanCandidate | None) -> dict[str, Any]:
        if not candidate:
            return {"value": "", "source": {}}
        return {"value": candidate.value, "source": candidate.paragraph.source}

    @staticmethod
    def _best(candidates: list[SpanCandidate]) -> SpanCandidate | None:
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item.score, -len(item.value)))

    @staticmethod
    def _clean_span(text: str, start: int, end: int) -> tuple[str, int, int]:
        while start < end and text[start] in " \t\r\n:;,.()[]{}-":
            start += 1
        while end > start and text[end - 1] in " \t\r\n:;,.()[]{}-":
            end -= 1
        return re.sub(r"\s+", " ", text[start:end]).strip(), start, end

    @staticmethod
    def _clean_value(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" \t\r\n:;,.()[]{}-")

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().upper()

    @staticmethod
    def _stop_at(value: str, boundaries: tuple[str, ...]) -> str:
        earliest: int | None = None
        for boundary in boundaries:
            match = re.search(rf"\b{re.escape(boundary)}\b", value, re.IGNORECASE)
            if match and match.start() > 0:
                earliest = match.start() if earliest is None else min(earliest, match.start())
        if earliest is not None:
            value = value[:earliest]
        return BaseExtractor._clean_value(value)

    @staticmethod
    def _strip_role_label(value: str) -> str:
        match = BaseExtractor._find_role_label(value)
        if match:
            value = value[: match.start()]
        value = ADVOCATE_RE.sub(" ", value)
        return BaseExtractor._clean_value(value)

    @staticmethod
    def _find_role_label(value: str) -> re.Match[str] | None:
        label = re.search(ROLE_RE.pattern + r"\s*$", value, re.IGNORECASE)
        if label and value[: label.start()].strip():
            return label
        for match in ROLE_RE.finditer(value):
            prefix = value[max(0, match.start() - 6) : match.start()]
            if (
                match.start() > 0
                and (
                    re.search(r"\.{2,}|-{2,}", prefix)
                    or re.search(r"\.{2,}|-{2,}", match.group(0))
                )
            ):
                return match
        return None

    @staticmethod
    def _role_side(role: str) -> str:
        role = role.upper()
        if role in PETITIONER_ROLES:
            return "petitioner_side"
        if role in RESPONDENT_ROLES:
            return "respondent_side"
        if any(token in role for token in ("PETITIONER", "APPELLANT", "APPLICANT")):
            return "petitioner_side"
        if any(token in role for token in ("RESPONDENT", "DEFENDANT", "STATE")):
            return "respondent_side"
        return ""

    def _anchor_between_and(self) -> list[tuple[SpanCandidate, SpanCandidate]]:
        anchors: list[tuple[SpanCandidate, SpanCandidate]] = []
        paragraphs = self.paragraphs[: self.PARTY_SCAN_LIMIT]
        for paragraph in paragraphs:
            for between in re.finditer(r"\bBETWEEN\s*:?", paragraph.text, re.IGNORECASE):
                after_between = paragraph.text[between.end() :]
                and_match = re.search(r"\bAND\s*:?", after_between, re.IGNORECASE)
                if and_match:
                    and_start = between.end() + and_match.start()
                    anchors.append(
                        (
                            SpanCandidate(between.group(0), paragraph, between.start(), between.end()),
                            SpanCandidate(
                                and_match.group(0),
                                paragraph,
                                and_start,
                                and_start + len(and_match.group(0)),
                            ),
                        )
                    )
                    continue
                for later in paragraphs[paragraph.index + 1 : paragraph.index + 16]:
                    and_match = re.search(r"\bAND\s*:?", later.text, re.IGNORECASE)
                    if and_match:
                        anchors.append(
                            (
                                SpanCandidate(between.group(0), paragraph, between.start(), between.end()),
                                SpanCandidate(and_match.group(0), later, and_match.start(), and_match.end()),
                            )
                        )
                        break
        return anchors

    def _slice_between(self, start: SpanCandidate, end: SpanCandidate) -> list[SpanCandidate]:
        if start.paragraph.index == end.paragraph.index:
            value, value_start, value_end = self._clean_span(start.paragraph.text, start.end, end.start)
            return [SpanCandidate(value, start.paragraph, value_start, value_end)] if value else []

        block: list[SpanCandidate] = []
        value, value_start, value_end = self._clean_span(
            start.paragraph.text, start.end, len(start.paragraph.text)
        )
        if value:
            block.append(SpanCandidate(value, start.paragraph, value_start, value_end))

        for paragraph in self.paragraphs[start.paragraph.index + 1 : end.paragraph.index]:
            value, value_start, value_end = self._clean_span(paragraph.text, 0, len(paragraph.text))
            if value:
                block.append(SpanCandidate(value, paragraph, value_start, value_end))

        value, value_start, value_end = self._clean_span(end.paragraph.text, 0, end.start)
        if value:
            block.append(SpanCandidate(value, end.paragraph, value_start, value_end))
        return block

    def _slice_after(self, anchor: SpanCandidate, max_paragraphs: int = 10) -> list[SpanCandidate]:
        block: list[SpanCandidate] = []
        value, value_start, value_end = self._clean_span(
            anchor.paragraph.text, anchor.end, len(anchor.paragraph.text)
        )
        if value:
            block.append(SpanCandidate(value, anchor.paragraph, value_start, value_end))

        for paragraph in self.paragraphs[anchor.paragraph.index + 1 : anchor.paragraph.index + max_paragraphs]:
            if re.search(r"\b(THIS\s+PETITION|THIS\s+APPEAL|ORDER|JUDGMENT|PRAYER|FACTS)\b", paragraph.text, re.IGNORECASE):
                break
            value, value_start, value_end = self._clean_span(paragraph.text, 0, len(paragraph.text))
            if value:
                block.append(SpanCandidate(value, paragraph, value_start, value_end))
            if self._find_role_label(value):
                break
        return block

    def _party_from_block(self, block: list[SpanCandidate]) -> SpanCandidate | None:
        if not block:
            return None
        value = self._strip_role_label(" ".join(item.value for item in block))
        if not value:
            return None
        source = block[0].paragraph
        return SpanCandidate(value, source, block[0].start, block[0].start + len(value))

    def _between_and_parties(self) -> dict[str, dict[str, Any]]:
        parties = {"petitioner": self._empty_field(), "respondent": self._empty_field()}
        for between, and_anchor in self._anchor_between_and():
            petitioner = self._party_from_block(self._slice_between(between, and_anchor))
            respondent = self._party_from_block(self._slice_after(and_anchor))
            if petitioner:
                parties["petitioner"] = self._field(petitioner)
            if respondent:
                parties["respondent"] = self._field(respondent)
            if petitioner or respondent:
                return parties
        return parties


class PartyExtractor:
    TOP_V_PATTERN_LIMIT = 20
    PARTY_SCAN_LIMIT = 90
    INVALID_VALUE_RE = re.compile(
        r"\b(?:COURT|JUSTICE|WORKMAN|PETITIONER-WORKMAN|RESPONDENT-COMPANY|"
        r"HIM|THE\s+WORKMAN|SAID\s+WORKMAN|COMPANY|MANAGEMENT)\b",
        re.IGNORECASE,
    )
    VS_RE = re.compile(
        r"(?<![A-Z])(?:V\.?|VS\.?|VERSUS)(?![A-Z])|[\-‐‑‒–—]\s*VERSUS\s*[\-‐‑‒–—]",
        re.IGNORECASE,
    )
    HARD_STOP_RE = re.compile(
        r"\b(?:THIS\s+PETITION|THIS\s+APPEAL|THIS\s+APPLICATION|ORDER|JUDGMENT|"
        r"JUDGEMENT|PRAYER|FACTS|HEARD\s+ON|JUDGMENT\s+ON|JUDGEMENT\s+ON)\b",
        re.IGNORECASE,
    )
    TRAILING_LEGAL_RE = re.compile(
        r"\b(?:VERSUS|APPELLANT(?:S)?|PETITIONER(?:S)?|RESPONDENT(?:S)?|"
        r"DEFENDANT(?:S)?|PLAINTIFF(?:S)?|APPLICANT(?:S)?)\b\s*$",
        re.IGNORECASE,
    )

    def __init__(self, paragraphs: list[dict[str, Any]] | list[ZoneParagraph]):
        self.paragraphs = BaseExtractor._normalize_paragraphs(paragraphs)

    def extract_between_and(self) -> dict[str, dict[str, Any]] | None:
        for between, and_anchor in self._between_and_anchors():
            petitioner = self._candidate_from_block(
                self._slice_between(between, and_anchor)
            )
            respondent = self._candidate_from_block(self._slice_after(and_anchor))
            result = self._result(petitioner, respondent)
            if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
                return result
        return None

    def extract_v_pattern(self) -> dict[str, dict[str, Any]] | None:
        split_line = self._extract_split_line_v_pattern()
        if split_line and self.validate(
            split_line["petitioner"]["value"], split_line["respondent"]["value"]
        ):
            return split_line

        for paragraph in self.paragraphs[: self.TOP_V_PATTERN_LIMIT]:
            text = self._normalized_vs_text(paragraph.text)
            for match in re.finditer(r"\bv\.", text, re.IGNORECASE):
                left = text[: match.start()]
                right = text[match.end() :]
                petitioner_value = self.clean_text(self._last_party_line(left))
                respondent_value = self.clean_text(self._first_party_line(right))
                petitioner = (
                    SpanCandidate(
                        petitioner_value,
                        paragraph,
                        max(0, match.start() - len(petitioner_value)),
                        match.start(),
                    )
                    if petitioner_value
                    else None
                )
                respondent = (
                    SpanCandidate(
                        respondent_value,
                        paragraph,
                        match.end(),
                        match.end() + len(respondent_value),
                    )
                    if respondent_value
                    else None
                )
                result = self._result(petitioner, respondent)
                if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
                    return result
        return None

    def extract_role_based(self) -> dict[str, dict[str, Any]] | None:
        petitioner: SpanCandidate | None = None
        respondent: SpanCandidate | None = None

        for paragraph in self.paragraphs[: self.PARTY_SCAN_LIMIT]:
            for match in ROLE_RE.finditer(paragraph.text):
                role = match.group(1).upper()
                side = BaseExtractor._role_side(role)
                if not side or not self._looks_like_role_label(paragraph.text, match):
                    continue

                start = self._role_value_start(paragraph.text, match.start())
                value = self.clean_text(paragraph.text[start : match.start()])
                if not self._valid_single_value(value):
                    continue

                candidate = SpanCandidate(value, paragraph, start, match.start())
                if side == "petitioner_side" and petitioner is None:
                    petitioner = candidate
                elif side == "respondent_side" and respondent is None:
                    respondent = candidate

            if petitioner and respondent:
                result = self._result(petitioner, respondent)
                if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
                    return result

        result = self._result(petitioner, respondent)
        if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
            return result
        return None

    def clean_text(self, text: str) -> str:
        text = ADVOCATE_RE.sub(" ", text)
        text = re.sub(
            r"\b(?:CRIMINAL|CIVIL|WRIT|MISC(?:ELLANEOUS)?|FIRST|SECOND)?\s*"
            r"(?:APPEAL|PETITION|APPLICATION|CASE)?\s*NO\.?\s*\d+.*?\b(?:19|20)\d{2}\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(?:W\.P\.C\.T\.|W\.P\.A\.|W\.P\.|C\.R\.R\.|C\.O\.|CRAN|CRA|CAN|FMAT|FMA|MAT|SA)"
            r"\s*(?:NO\.?)?\s*\d+.*?\b(?:19|20)\d{2}\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"^\s*IN\s+THE\s+.*?COURT.*?\b(?:DATE|DATED)\s*:?.*?\b(?:19|20)\d{2}\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"^\s*IN\s+THE\s+.*?COURT\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.split(
            r"\b(?:R/AT|R/O|RESIDING\s+AT|RESIDENT\s+OF|ADDRESS|AGED\s+ABOUT|"
            r"THROUGH|REPRESENTED\s+BY)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        text = re.sub(r"\.{2,}|[\-‐‑‒–—]{2,}|_{2,}", " ", text)
        text = re.sub(r"[\-‐‑‒–—]+", " ", text)
        text = re.sub(r"^\s*(?:BETWEEN|AND)\s*:?", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*\d+\s*[.)]\s*", " ", text)
        text = self.TRAILING_LEGAL_RE.sub(" ", text)
        text = re.split(
            r"\b(?:DATED|BEFORE|CORAM|JUDGMENT|JUDGEMENT|ORDER|HEARD\s+ON|"
            r"THIS\s+PETITION|THIS\s+APPEAL)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return re.sub(r"\s+", " ", text).strip(" \t\r\n:;,.()[]{}-")

    def validate(self, petitioner: str, respondent: str) -> bool:
        if not self._valid_single_value(petitioner):
            return False
        if not self._valid_single_value(respondent):
            return False
        if re.search(r"\bNO\.?\b", petitioner, re.IGNORECASE):
            return False
        if re.search(r"\bCOURT\b", respondent, re.IGNORECASE):
            return False
        if len(petitioner) > 150 or len(respondent) > 150:
            return False
        return BaseExtractor._normalize_text(petitioner) != BaseExtractor._normalize_text(
            respondent
        )

    def extract(self) -> dict[str, dict[str, Any]]:
        for extractor in (
            self.extract_between_and,
            self.extract_v_pattern,
            self.extract_role_based,
        ):
            result = extractor()
            if result:
                return result
        return {"petitioner": self._empty_field(), "respondent": self._empty_field()}


class RobustPartyExtractor(PartyExtractor):
    """Party extractor that scores weak candidates instead of returning empty."""

    def validate(self, petitioner: str, respondent: str) -> bool:
        return bool(self.clean_text(petitioner)) or bool(self.clean_text(respondent))

    def extract(self) -> dict[str, dict[str, Any]]:
        candidates: list[tuple[int, dict[str, dict[str, Any]]]] = []
        for weight, extractor in (
            (40, self.extract_between_and),
            (35, self.extract_v_pattern),
            (30, self.extract_versus_block),
            (20, self.extract_role_based),
        ):
            result = extractor()
            if result and (result["petitioner"]["value"] or result["respondent"]["value"]):
                candidates.append((weight + self._result_score(result), result))

        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
        return self._closest_role_candidate()

    def _result_score(self, result: dict[str, dict[str, Any]]) -> int:
        score = 0
        petitioner = result["petitioner"]["value"]
        respondent = result["respondent"]["value"]
        if petitioner:
            score += 5
        if respondent:
            score += 5
        if petitioner and respondent:
            score += 10
        for value in (petitioner, respondent):
            if self.INVALID_VALUE_RE.search(value):
                score -= 5
            if len(value) > 150:
                score -= 5
        if petitioner and respondent and BaseExtractor._normalize_text(petitioner) == BaseExtractor._normalize_text(respondent):
            score -= 10
        return score

    def _closest_role_candidate(self) -> dict[str, dict[str, Any]]:
        petitioner: SpanCandidate | None = None
        respondent: SpanCandidate | None = None
        for paragraph in self.paragraphs[: self.PARTY_SCAN_LIMIT]:
            for match in ROLE_RE.finditer(paragraph.text):
                start = self._role_value_start(paragraph.text, match.start())
                value = self.clean_text(paragraph.text[start : match.start()])
                if not value:
                    continue
                candidate = SpanCandidate(value, paragraph, start, match.start())
                side = BaseExtractor._role_side(match.group(1))
                if side == "petitioner_side" and petitioner is None:
                    petitioner = candidate
                elif side == "respondent_side" and respondent is None:
                    respondent = candidate
            if petitioner or respondent:
                break
        return self._result(petitioner, respondent)

    def extract_versus_block(self) -> dict[str, dict[str, Any]] | None:
        for index, paragraph in enumerate(self.paragraphs[: self.PARTY_SCAN_LIMIT]):
            if not re.fullmatch(
                r"\s*[\-‐‑‒–—]?\s*VERSUS\s*[\-‐‑‒–—]?\s*",
                paragraph.text,
                re.IGNORECASE,
            ):
                continue
            before = self._nearby_party_block(index - 1, step=-1)
            after = self._nearby_party_block(index + 1, step=1)
            petitioner = self._candidate_from_block(before)
            respondent = self._candidate_from_block(after)
            result = self._result(petitioner, respondent)
            if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
                return result

        merged = "\n".join(paragraph.text for paragraph in self.paragraphs[: self.PARTY_SCAN_LIMIT])
        match = re.search(r"[\-‐‑‒–—]?\s*VERSUS\s*[\-‐‑‒–—]?", merged, re.IGNORECASE)
        if not match:
            return None
        left = self.clean_text(self._last_party_line(merged[: match.start()]))
        right = self.clean_text(self._first_party_line(merged[match.end() :]))
        source = self._source_for_merged_offset(match.start())
        result = self._result(
            SpanCandidate(left, source, 0, len(left)) if left and source else None,
            SpanCandidate(right, source, 0, len(right)) if right and source else None,
        )
        if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
            return result
        return None

    def _between_and_anchors(self) -> list[tuple[SpanCandidate, SpanCandidate]]:
        anchors: list[tuple[SpanCandidate, SpanCandidate]] = []
        paragraphs = self.paragraphs[: self.PARTY_SCAN_LIMIT]
        for paragraph in paragraphs:
            for between in re.finditer(r"\bBETWEEN\s*:?", paragraph.text, re.IGNORECASE):
                local_and = re.search(
                    r"\bAND\s*:?", paragraph.text[between.end() :], re.IGNORECASE
                )
                if local_and:
                    and_start = between.end() + local_and.start()
                    anchors.append(
                        (
                            SpanCandidate(
                                between.group(0), paragraph, between.start(), between.end()
                            ),
                            SpanCandidate(
                                local_and.group(0),
                                paragraph,
                                and_start,
                                and_start + len(local_and.group(0)),
                            ),
                        )
                    )
                    continue

                for later in paragraphs[paragraph.index + 1 : paragraph.index + 16]:
                    and_match = re.search(r"\bAND\s*:?", later.text, re.IGNORECASE)
                    if and_match:
                        anchors.append(
                            (
                                SpanCandidate(
                                    between.group(0),
                                    paragraph,
                                    between.start(),
                                    between.end(),
                                ),
                                SpanCandidate(
                                    and_match.group(0),
                                    later,
                                    and_match.start(),
                                    and_match.end(),
                                ),
                            )
                        )
                        break
        return anchors

    def _slice_between(
        self, start_anchor: SpanCandidate, end_anchor: SpanCandidate
    ) -> list[SpanCandidate]:
        if start_anchor.paragraph.index == end_anchor.paragraph.index:
            value, start, end = BaseExtractor._clean_span(
                start_anchor.paragraph.text, start_anchor.end, end_anchor.start
            )
            return [SpanCandidate(value, start_anchor.paragraph, start, end)] if value else []

        block: list[SpanCandidate] = []
        value, start, end = BaseExtractor._clean_span(
            start_anchor.paragraph.text,
            start_anchor.end,
            len(start_anchor.paragraph.text),
        )
        if value:
            block.append(SpanCandidate(value, start_anchor.paragraph, start, end))

        for paragraph in self.paragraphs[
            start_anchor.paragraph.index + 1 : end_anchor.paragraph.index
        ]:
            value, start, end = BaseExtractor._clean_span(paragraph.text, 0, len(paragraph.text))
            if value:
                block.append(SpanCandidate(value, paragraph, start, end))

        value, start, end = BaseExtractor._clean_span(
            end_anchor.paragraph.text, 0, end_anchor.start
        )
        if value:
            block.append(SpanCandidate(value, end_anchor.paragraph, start, end))
        return block

    def _slice_after(self, anchor: SpanCandidate) -> list[SpanCandidate]:
        block: list[SpanCandidate] = []
        value, start, end = BaseExtractor._clean_span(
            anchor.paragraph.text, anchor.end, len(anchor.paragraph.text)
        )
        if value:
            block.append(SpanCandidate(value, anchor.paragraph, start, end))

        for paragraph in self.paragraphs[anchor.paragraph.index + 1 : anchor.paragraph.index + 10]:
            if self.HARD_STOP_RE.search(paragraph.text):
                break
            value, start, end = BaseExtractor._clean_span(paragraph.text, 0, len(paragraph.text))
            if value:
                block.append(SpanCandidate(value, paragraph, start, end))
            role_match = BaseExtractor._find_role_label(value)
            if role_match and BaseExtractor._role_side(role_match.group(1)) == "respondent_side":
                break
        return block

    def _candidate_from_block(self, block: list[SpanCandidate]) -> SpanCandidate | None:
        if not block:
            return None
        raw_text = " ".join(item.value for item in block)
        role_match = BaseExtractor._find_role_label(raw_text)
        if role_match:
            raw_text = raw_text[: role_match.start()]
        value = self.clean_text(raw_text)
        if not self._valid_single_value(value):
            return None
        return SpanCandidate(value, block[0].paragraph, block[0].start, block[0].start + len(value))

    def _nearby_party_block(self, start_index: int, step: int) -> list[SpanCandidate]:
        block: list[SpanCandidate] = []
        index = start_index
        scanned = 0
        while 0 <= index < len(self.paragraphs) and scanned < 8:
            paragraph = self.paragraphs[index]
            scanned += 1
            if self.HARD_STOP_RE.search(paragraph.text):
                break
            value, start, end = BaseExtractor._clean_span(paragraph.text, 0, len(paragraph.text))
            if value:
                if step < 0:
                    block.insert(0, SpanCandidate(value, paragraph, start, end))
                else:
                    block.append(SpanCandidate(value, paragraph, start, end))
            if BaseExtractor._find_role_label(value):
                break
            index += step
        return block

    def _source_for_merged_offset(self, offset: int) -> ZoneParagraph | None:
        running = 0
        for paragraph in self.paragraphs[: self.PARTY_SCAN_LIMIT]:
            end = running + len(paragraph.text)
            if running <= offset <= end:
                return paragraph
            running = end + 1
        return self.paragraphs[0] if self.paragraphs else None

    def _extract_split_line_v_pattern(self) -> dict[str, dict[str, Any]] | None:
        for index, paragraph in enumerate(self.paragraphs[: self.TOP_V_PATTERN_LIMIT]):
            if not self.VS_RE.fullmatch(paragraph.text.strip()):
                continue
            if not (0 < index < len(self.paragraphs) - 1):
                continue

            petitioner_paragraph = self.paragraphs[index - 1]
            respondent_paragraph = self.paragraphs[index + 1]
            petitioner_value = self.clean_text(petitioner_paragraph.text)
            respondent_value = self.clean_text(respondent_paragraph.text)
            return self._result(
                SpanCandidate(
                    petitioner_value,
                    petitioner_paragraph,
                    0,
                    len(petitioner_paragraph.text),
                )
                if petitioner_value
                else None,
                SpanCandidate(
                    respondent_value,
                    respondent_paragraph,
                    0,
                    len(respondent_paragraph.text),
                )
                if respondent_value
                else None,
            )
        return None

    def _normalized_vs_text(self, text: str) -> str:
        return self.VS_RE.sub("v.", text)

    def _last_party_line(self, text: str) -> str:
        parts = [part.strip() for part in re.split(r"[\n\r]+", text) if part.strip()]
        if not parts:
            return text
        return parts[-1]

    def _first_party_line(self, text: str) -> str:
        parts = [part.strip() for part in re.split(r"[\n\r]+", text) if part.strip()]
        return parts[0] if parts else text

    def _role_value_start(self, text: str, role_start: int) -> int:
        prefix = text[:role_start]
        boundary_matches = list(
            re.finditer(
                r"\b(?:BETWEEN|AND|VERSUS|VS\.?|V\.)\b\s*:?", prefix, re.IGNORECASE
            )
        )
        if boundary_matches:
            return boundary_matches[-1].end()

        line_break = max(prefix.rfind("\n"), prefix.rfind("\r"))
        if line_break >= 0:
            return line_break + 1
        return 0

    def _looks_like_role_label(self, text: str, match: re.Match[str]) -> bool:
        role = match.group(1).upper()
        if role == "STATE" and re.search(r"\bSTATE\s+OF\b", text[match.start() : match.end() + 8], re.IGNORECASE):
            return False
        suffix = text[match.end() : match.end() + 40]
        prefix = text[max(0, match.start() - 8) : match.start()]
        if re.search(r"\.{2,}|-{2,}", prefix):
            return True
        if not suffix.strip() or re.match(r"^\s*[).,;:]*\s*$", suffix):
            return True
        return False

    def _valid_single_value(self, value: str) -> bool:
        return (
            bool(value)
            and len(value.strip()) >= 3
            and len(value.strip()) <= 150
            and not self.INVALID_VALUE_RE.search(value)
        )

    def _result(
        self,
        petitioner: SpanCandidate | None,
        respondent: SpanCandidate | None,
    ) -> dict[str, dict[str, Any]]:
        return {
            "petitioner": self._field(petitioner),
            "respondent": self._field(respondent),
        }

    @staticmethod
    def _empty_field() -> dict[str, Any]:
        return {"value": "", "source": {}}

    @staticmethod
    def _field(candidate: SpanCandidate | None) -> dict[str, Any]:
        if not candidate:
            return {"value": "", "source": {}}
        return {"value": candidate.value, "source": candidate.paragraph.source}


class CalcuttaPartyExtractor(RobustPartyExtractor):
    CASE_PREFIX_RE = (
        r"W\.P\.C\.T\.|W\.P\.A\.|W\.P\.|C\.R\.R\.|C\.O\.|CRAN|CRA|CAN|FMAT|FMA|MAT|SA"
    )
    CASE_FRAGMENT_RE = re.compile(
        rf"\b(?:{CASE_PREFIX_RE})\s*(?:No\.?)?\s*\d+.*?(?:\b(?:19|20)\d{{2}}\b|(?=[A-Z][a-z]))",
        re.IGNORECASE,
    )
    LIST_PREFIX_RE = re.compile(
        r"^\s*\d+\s+(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+)?"
        r"(?:\d+\s+)?(?:[a-z]\.){1,4}\s*",
        re.IGNORECASE,
    )
    VS_VARIANT_RE = re.compile(
        r"\s*[\-‐‑‒–—]?\s*(?:VS\.?|Vs\.?|vs\.?|V\.|v\.)\s*[\-‐‑‒–—]?\s*",
        re.IGNORECASE,
    )

    def extract(self) -> dict[str, dict[str, Any]]:
        for extractor in (
            self.extract_between_and,
            self.extract_v_pattern,
            self.extract_role_based,
        ):
            result = extractor()
            if result:
                return result
        return {"petitioner": self._empty_field(), "respondent": self._empty_field()}

    def extract_v_pattern(self) -> dict[str, dict[str, Any]] | None:
        split_line = self._extract_split_line_v_pattern()
        if split_line and self.validate(
            split_line["petitioner"]["value"], split_line["respondent"]["value"]
        ):
            return split_line

        for paragraph in self.paragraphs[: self.TOP_V_PATTERN_LIMIT]:
            text = self.clean_line(paragraph.text)
            if " v. " not in text:
                continue
            parts = text.split(" v. ", maxsplit=1)
            if len(parts) != 2:
                continue

            petitioner_value = self.clean_party(parts[0])
            respondent_value = self.clean_party(parts[1])
            result = self._result(
                SpanCandidate(
                    petitioner_value,
                    paragraph,
                    max(0, paragraph.text.find(parts[0].strip())),
                    max(0, paragraph.text.find(parts[0].strip())) + len(parts[0].strip()),
                )
                if petitioner_value
                else None,
                SpanCandidate(
                    respondent_value,
                    paragraph,
                    max(0, paragraph.text.find(parts[1].strip())),
                    max(0, paragraph.text.find(parts[1].strip())) + len(parts[1].strip()),
                )
                if respondent_value
                else None,
            )
            if self.validate(result["petitioner"]["value"], result["respondent"]["value"]):
                return result
        return None

    def clean_line(self, text: str) -> str:
        text = self.VS_VARIANT_RE.sub(" v. ", text)
        text = re.sub(r"^\s*\d+.*?\b(?:19|20)\d{2}\b", " ", text)
        text = self.LIST_PREFIX_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    def clean_party(self, text: str) -> str:
        text = self.CASE_FRAGMENT_RE.sub(" ", text)
        text = re.sub(rf"\b(?:{self.CASE_PREFIX_RE})\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*of\s+(?:19|20)\d{2}\b", " ", text, flags=re.IGNORECASE)
        text = ADVOCATE_RE.sub(" ", text)
        text = re.sub(r"\.{2,}|[\-‐‑‒–—]{2,}|_{2,}", " ", text)
        text = re.sub(r"[\-‐‑‒–—]+", " ", text)
        text = re.split(
            r"\b(?:JUDGMENT|JUDGEMENT|HEARD\s+ON|ORDER|NO\.?\s*\d+)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        text = re.sub(r"^\s*(?:&\s*)?(?:Ors?\.?|Others)\s*", " ", text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip(" \t\r\n:;,.()[]{}-")

    def clean_text(self, text: str) -> str:
        return self.clean_party(self.clean_line(text))

    def validate(self, petitioner: str, respondent: str) -> bool:
        if not super().validate(petitioner, respondent):
            return False
        if re.search(r"\bW\.P\.|\bW\.P\.A\.|\bW\.P\.C\.T\.", petitioner, re.IGNORECASE):
            return False
        if re.search(r"\bNo\.?\b", respondent, re.IGNORECASE):
            return False
        if len(petitioner) > 150 or len(respondent) > 150:
            return False
        return True


class SupremeCourtExtractor(BaseExtractor):
    CASE_NO_RE = re.compile(
        r"\((CRIMINAL\s+APPEAL\s+NO\.?\s*\d+[^)]*?\bOF\s+(?:19|20)\d{2})\)",
        re.IGNORECASE,
    )
    CASE_STYLE_RE = re.compile(
        r"^\s*(?!.*\bCOURT\b)(?!.*\bREPORTS\b)(.+?)\s+v(?:s\.?|\.|ersus)?\s+(.+?)\s*$",
        re.IGNORECASE,
    )
    BENCH_RE = re.compile(r"\[([^\]]*?\bJ{1,2}\.?)\]", re.IGNORECASE)

    def extract_case_number(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[: self.TOP_FIELD_LIMIT]:
            for match in self.CASE_NO_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                candidates.append(SpanCandidate(value, paragraph, start, end, 40 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_case_type(self, case_number: str | None = None) -> str:
        text = (case_number or "").upper()
        if "CRIMINAL" in text and "APPEAL" in text:
            return "Appeal"
        return super().extract_case_type(case_number)

    def extract_court_name(self) -> dict[str, Any]:
        source = self._first_indicator_paragraph(("S.C.R.", "SUPREME COURT REPORTS", "SUPREME COURT"))
        if not source:
            source = self.paragraphs[0] if self.paragraphs else None
        if not source:
            return self._empty_field()
        return {"value": "SUPREME COURT OF INDIA", "source": source.source}

    def extract_bench(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[: self.TOP_FIELD_LIMIT]:
            for match in self.BENCH_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                value = self._clean_value(value)
                if value:
                    candidates.append(SpanCandidate(value, paragraph, start, end, 35 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_judgment_date(self) -> dict[str, Any]:
        title = self._case_title_candidate()
        start_index = title.paragraph.index if title else 0
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[start_index : min(len(self.paragraphs), start_index + 8)]:
            for match in DATE_VALUE_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                candidates.append(SpanCandidate(value, paragraph, start, end, 30 - abs(paragraph.index - start_index)))
        return self._field(self._best(candidates))

    def extract_parties(self) -> dict[str, dict[str, Any]]:
        return PartyExtractor(self.paragraphs).extract()

    def _case_title_candidate(self) -> SpanCandidate | None:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[: self.TOP_FIELD_LIMIT]:
            text = self._clean_value(paragraph.text)
            if len(text) > 160:
                continue
            if self.CASE_STYLE_RE.match(text):
                candidates.append(SpanCandidate(text, paragraph, 0, len(paragraph.text), 40 - paragraph.index))
        return self._best(candidates)

    def _first_indicator_paragraph(self, indicators: tuple[str, ...]) -> ZoneParagraph | None:
        for paragraph in self.paragraphs[:30]:
            upper = paragraph.text.upper()
            if any(indicator in upper for indicator in indicators):
                return paragraph
        return None


class KarnatakaHCExtractor(BaseExtractor):
    COURT_RE = re.compile(
        r"\bIN\s+THE\s+HIGH\s+COURT.*?(?=\bDATED\b|\bBEFORE\b|\bCORAM\b|$)",
        re.IGNORECASE | re.DOTALL,
    )
    CASE_NO_RE = re.compile(
        r"\b(?:MISCELLANEOUS|CRIMINAL|CIVIL|WRIT|W\.?P\.?|M\.?F\.?A\.?|R\.?F\.?A\.?)\b"
        r"(?:(?!\b(?:DATED|BEFORE|BETWEEN|CORAM|JUSTICE|IN\s+THE)\b).){0,150}?"
        r"\bNO\.?\s*[:.-]?\s*\d+[\w./()-]*"
        r"(?:(?!\b(?:DATED|BEFORE|BETWEEN|CORAM|JUSTICE|IN\s+THE)\b).){0,80}?"
        r"\b(?:19|20)\d{2}\b",
        re.IGNORECASE | re.DOTALL,
    )
    DATE_RE = re.compile(
        r"\bDATED\b(?:(?!\b(?:BEFORE|BETWEEN|CORAM|JUSTICE)\b).){0,100}?"
        + DATE_VALUE_RE.pattern,
        re.IGNORECASE | re.DOTALL,
    )
    BENCH_RE = re.compile(
        r"\b(HON(?:'|`|\.)?\s*BLE\.?\s+.*?JUSTICE\s+[A-Z][A-Z.\s]{1,90})",
        re.IGNORECASE | re.DOTALL,
    )

    def extract_case_number(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[: self.TOP_FIELD_LIMIT]:
            for match in self.CASE_NO_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(), match.end())
                value = self._trim_to_year(value)
                if "JUSTICE" not in value.upper():
                    candidates.append(SpanCandidate(value, paragraph, start, end, 45 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_court_name(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[:25]:
            for match in self.COURT_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(), match.end())
                value = self._stop_at(value, ("DATED", "BEFORE", "CORAM"))
                candidates.append(SpanCandidate(value, paragraph, start, end, 35 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_judgment_date(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.find_anchor_window("DATED", 2):
            for match in self.DATE_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                candidates.append(SpanCandidate(value, paragraph, start, end, 40 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_bench(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.find_anchor_window("JUSTICE", 3):
            for match in self.BENCH_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                value = self._stop_at(
                    value,
                    ("CRIMINAL", "CIVIL", "WRIT", "MISCELLANEOUS", "BETWEEN", "DATED", "ORDER", "JUDGMENT"),
                )
                if value and "COURT" not in value.upper():
                    candidates.append(SpanCandidate(value, paragraph, start, end, 40 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_parties(self) -> dict[str, dict[str, Any]]:
        return PartyExtractor(self.paragraphs).extract()

    @staticmethod
    def _trim_to_year(value: str) -> str:
        value = re.sub(r"\s+", " ", value)
        year_matches = list(re.finditer(r"\b(?:19|20)\d{2}\b", value))
        if year_matches:
            value = value[: year_matches[-1].end()]
        return value.strip(" \t\r\n:;,.")


class CalcuttaHCExtractor(BaseExtractor):
    COURT_RE = re.compile(r"\bIN\s+THE\s+HIGH\s+COURT\s+AT\s+CALCUTTA\b", re.IGNORECASE)
    CASE_PREFIX_RE = (
        r"W\.P\.C\.T\.|W\.P\.A\.|W\.P\.|C\.R\.R\.|C\.O\.|CRAN|CRA|CAN|FMAT|FMA|MAT|SA"
    )
    CASE_NO_RE = re.compile(
        rf"\b((?:{CASE_PREFIX_RE})\s*(?:No\.?)?\s*\d+.*?\b(?:19|20)\d{{2}}\b)",
        re.IGNORECASE | re.DOTALL,
    )
    CASE_TYPE_MAP = {
        "W.P.A.": "Writ Petition (Appellate Side)",
        "W.P.C.T.": "Writ Petition (CAT matters)",
        "W.P.": "Writ Petition",
        "C.R.R.": "Criminal Revision",
        "C.O.": "Civil Order",
        "CRAN": "Criminal Appeal (Application)",
        "CRA": "Criminal Appeal",
        "CAN": "Civil Application",
        "FMAT": "First Misc Appeal",
        "MAT": "Misc Appeal",
        "FMA": "First Appeal",
        "SA": "Second Appeal",
    }
    BENCH_RE = re.compile(r"\b(JUSTICE\s+[A-Z][A-Z\s.]{1,80})", re.IGNORECASE)
    DATE_RE = re.compile(
        r"\b(?:JUDGEMENT|JUDGMENT|HEARD)\s+ON\b.{0,80}?" + DATE_VALUE_RE.pattern,
        re.IGNORECASE | re.DOTALL,
    )
    VS_RE = re.compile(r"(?<![A-Z])(?:V\.?|VS\.?|VERSUS)(?![A-Z])", re.IGNORECASE)

    def extract_case_number(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[:20]:
            for match in self.CASE_NO_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                value = self._clean_calcutta_case_number(value)
                if value:
                    candidates.append(SpanCandidate(value, paragraph, start, end, 40 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_case_type(self, case_number: str | None = None) -> str:
        case_number = case_number or self.extract_case_number().get("value", "")
        prefix = self._case_prefix(case_number)
        return self.CASE_TYPE_MAP.get(prefix, "")

    def extract_court_name(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.paragraphs[:25]:
            for match in self.COURT_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(), match.end())
                candidates.append(SpanCandidate(value, paragraph, start, end, 40 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_judgment_date(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.find_anchor_window("ON", 3):
            for match in self.DATE_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                candidates.append(SpanCandidate(value, paragraph, start, end, 35 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_bench(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self.find_anchor_window("JUSTICE", 3):
            for match in self.BENCH_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                value = self._stop_at(value, ("C.R.R", "C.O", "VS", "JUDGMENT", "JUDGEMENT", "HEARD"))
                if value and "COURT" not in value.upper():
                    candidates.append(SpanCandidate(value, paragraph, start, end, 35 - paragraph.index))
        return self._field(self._best(candidates))

    def extract_parties(self) -> dict[str, dict[str, Any]]:
        return CalcuttaPartyExtractor(self.paragraphs).extract()

    def extract_all(self) -> dict[str, Any]:
        case_number = self.extract_case_number()
        parties = self.extract_parties()
        fields = {
            "case_number": case_number,
            "case_type": self.extract_case_type(case_number.get("value")),
            "judgment_date": self.extract_judgment_date(),
            "bench": self.extract_bench(),
            "court_name": self.extract_court_name(),
            "petitioner": parties["petitioner"],
            "respondent": parties["respondent"],
        }
        return self.validate_fields(fields)

    @classmethod
    def _case_prefix(cls, case_number: str) -> str:
        match = re.search(rf"({cls.CASE_PREFIX_RE})", case_number, re.IGNORECASE)
        if not match:
            return ""
        prefix = match.group(1).upper()
        for known_prefix in cls.CASE_TYPE_MAP:
            if prefix == known_prefix:
                return known_prefix
        return prefix

    @staticmethod
    def _clean_calcutta_case_number(value: str) -> str:
        value = re.sub(r"\s+", " ", value)
        year_match = re.search(r"\b(?:19|20)\d{2}\b", value)
        if year_match:
            value = value[: year_match.end()]
        return value.strip(" \t\r\n:;,.")

    def _split_line_vs_parties(self) -> dict[str, dict[str, Any]] | None:
        for index, paragraph in enumerate(self.paragraphs[: self.PARTY_SCAN_LIMIT]):
            if not self.VS_RE.fullmatch(paragraph.text.strip()) or not (0 < index < len(self.paragraphs) - 1):
                continue
            petitioner_paragraph = self.paragraphs[index - 1]
            respondent_paragraph = self.paragraphs[index + 1]
            petitioner = self._clean_value(petitioner_paragraph.text)
            respondent = self._clean_value(respondent_paragraph.text)
            if not petitioner and not respondent:
                return None
            return {
                "petitioner": {"value": petitioner, "source": petitioner_paragraph.source} if petitioner else self._empty_field(),
                "respondent": {"value": respondent, "source": respondent_paragraph.source} if respondent else self._empty_field(),
            }
        return None

    def _vs_title_candidate(self) -> SpanCandidate | None:
        candidates: list[SpanCandidate] = []
        for index, paragraph in enumerate(self.paragraphs[: self.PARTY_SCAN_LIMIT]):
            if self.VS_RE.fullmatch(paragraph.text.strip()) and 0 < index < len(self.paragraphs) - 1:
                previous = self._clean_value(self.paragraphs[index - 1].text)
                next_value = self._clean_value(self.paragraphs[index + 1].text)
                if previous and next_value:
                    value = f"{previous} Vs. {next_value}"
                    candidates.append(SpanCandidate(value, paragraph, 0, len(paragraph.text), 40 - index))
                continue

            if self.VS_RE.search(paragraph.text) and len(paragraph.text) < 180:
                match = self.VS_RE.search(paragraph.text)
                if match and paragraph.text[: match.start()].strip() and paragraph.text[match.end() :].strip():
                    value = self._clean_value(paragraph.text)
                    candidates.append(SpanCandidate(value, paragraph, 0, len(paragraph.text), 40 - index))
        return self._best(candidates)


class GenericExtractor(KarnatakaHCExtractor):
    CASE_NO_RE = re.compile(
        r"\b(?:CRIMINAL|CIVIL|WRIT|MISC(?:ELLANEOUS)?|APPEAL|REGULAR|SPECIAL\s+LEAVE|"
        r"S\.?L\.?P\.?|W\.?P\.?|C\.?R\.?P\.?|R\.?F\.?A\.?|M\.?F\.?A\.?)\b"
        r"(?:(?!\b(?:DATED|DATE|PRONOUNCED|BEFORE|BETWEEN|CORAM|HON|JUSTICE|IN\s+THE)\b).){0,150}?"
        r"\bNO\.?\s*[:.-]?\s*\d+[\w./()-]*"
        r"(?:(?!\b(?:DATED|DATE|PRONOUNCED|BEFORE|BETWEEN|CORAM|HON|JUSTICE|IN\s+THE)\b).){0,90}?"
        r"\b(?:19|20)\d{2}\b",
        re.IGNORECASE | re.DOTALL,
    )
    COURT_RE = re.compile(
        r"\bIN\s+THE\s+.{0,180}?COURT.{0,180}?(?=\bDATED\b|\bDATE\b|\bBEFORE\b|\bCORAM\b|$)",
        re.IGNORECASE | re.DOTALL,
    )
    DATE_RE = re.compile(
        r"\b(?:DATED|DATE|PRONOUNCED)\b(?:(?!\b(?:BEFORE|BETWEEN|CORAM|JUSTICE)\b).){0,100}?"
        + DATE_VALUE_RE.pattern,
        re.IGNORECASE | re.DOTALL,
    )


class UnifiedExtractor(BaseExtractor):
    CASE_PATTERNS = [
        re.compile(
            r"\b((?:FIRST|SECOND).*?APPEAL\s+NO\.?\s*\d+.*?\b(?:19|20)\d{2}\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b((?:W\.P\.C\.T\.|W\.P\.A\.|W\.P\.|C\.R\.R\.|C\.O\.|CRAN|CRA|CAN|FMAT|FMA|MAT|SA)"
            r"\s*No\.?\s*\d+.*?\b(?:19|20)\d{2}\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b((?:CRIMINAL|CIVIL|WRIT|MISC(?:ELLANEOUS)?|APPEAL)"
            r"(?:(?!\b(?:DATED|DATE|CORAM|BEFORE|JUSTICE|COURT|BETWEEN)\b).){0,150}?"
            r"\bNO\.?\s*\d+.*?\b(?:19|20)\d{2}\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ]
    COURT_RE = re.compile(
        r"\bIN\s+THE\s+.*?COURT.*?(?=\bDATED\b|\bCORAM\b|\bBEFORE\b|$)",
        re.IGNORECASE | re.DOTALL,
    )
    BENCH_PATTERNS = [
        re.compile(r"\bCORAM\s*:\s*(.*?J{1,2}\.?)", re.IGNORECASE | re.DOTALL),
        re.compile(
            r"\b(HON(?:'|`|\.)?\s*BLE\.?\s+.*?JUSTICE\s+[A-Z][A-Z.\s]{1,90})",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(r"\b(JUSTICE\s+[A-Z][A-Z.\s]{1,80})", re.IGNORECASE),
    ]
    DATE_PATTERNS = [
        re.compile(r"\bDATE\s*:\s*" + DATE_VALUE_RE.pattern, re.IGNORECASE | re.DOTALL),
        re.compile(r"\bDATED\b.{0,100}?" + DATE_VALUE_RE.pattern, re.IGNORECASE | re.DOTALL),
        re.compile(
            r"\bPRONOUNCED\s+ON\s*:?\s*(.*?\b(?:19|20)\d{2}\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ]
    CALCUTTA_CASE_TYPE_MAP = CalcuttaHCExtractor.CASE_TYPE_MAP

    def __init__(
        self,
        paragraphs: list[dict[str, Any]] | list[ZoneParagraph],
        court_type: str = "generic",
    ):
        super().__init__(paragraphs)
        self.court_type = court_type

    def extract_case_number(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self._header_windows(max_size=4):
            text_before_with = re.split(r"\bWITH\b", paragraph.text, maxsplit=1, flags=re.IGNORECASE)[0]
            for pattern_index, pattern in enumerate(self.CASE_PATTERNS):
                for match in pattern.finditer(text_before_with):
                    group_index = 1 if match.lastindex else 0
                    value, start, end = self._clean_span(
                        text_before_with, match.start(group_index), match.end(group_index)
                    )
                    value = self._clean_case_number(value)
                    if not value or "JUSTICE" in value.upper() or self._has_multiple_case_numbers(value):
                        continue
                    score = 100 + ((len(self.CASE_PATTERNS) - pattern_index) * 30) - len(value) - paragraph.index
                    score += self._court_priority_bonus(value)
                    candidates.append(SpanCandidate(value, paragraph, start, end, score))
        return self._field(self._best(candidates))

    def extract_case_type(self, case_number: str | None = None) -> str:
        text = (case_number or self.extract_case_number().get("value") or "").upper()
        prefix = CalcuttaHCExtractor._case_prefix(text)
        if prefix:
            return self.CALCUTTA_CASE_TYPE_MAP.get(prefix, "")
        if "FIRST" in text and "APPEAL" in text:
            return "First Appeal"
        if "SECOND" in text and "APPEAL" in text:
            return "Second Appeal"
        if "CRIMINAL" in text and ("APPEAL" in text or "CRA" in text):
            return "Criminal Appeal"
        if "CRIMINAL" in text:
            return "Criminal Petition"
        if "CIVIL" in text:
            return "Civil Case"
        if "WRIT" in text or "W.P" in text:
            return "Writ Petition"
        if "APPEAL" in text:
            return "Appeal"
        if "MISC" in text:
            return "Miscellaneous Case"
        return super().extract_case_type(case_number)

    def extract_court_name(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for paragraph in self._header_windows(max_size=4):
            for match in self.COURT_RE.finditer(paragraph.text):
                value, start, end = self._clean_span(paragraph.text, match.start(), match.end())
                value = self._stop_at(value, ("DATED", "DATE", "CORAM", "BEFORE"))
                upper_value = value.upper()
                if value and "NO." not in upper_value and (
                    "HIGH COURT" in upper_value or "SUPREME COURT" in upper_value
                ):
                    candidates.append(
                        SpanCandidate(value, paragraph, start, end, 80 - len(value) - paragraph.index)
                    )
        return self._field(self._best(candidates))

    def extract_bench(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        search_paragraphs = self._header_anchor_sources(("CORAM", "JUSTICE", "HON", "BEFORE"), 3)
        for paragraph in search_paragraphs:
            for pattern_index, pattern in enumerate(self.BENCH_PATTERNS):
                for match in pattern.finditer(paragraph.text):
                    group_index = 1 if match.lastindex else 0
                    value, start, end = self._clean_span(
                        paragraph.text, match.start(group_index), match.end(group_index)
                    )
                    value = self._stop_at(
                        value,
                        ("DATED", "DATE", "CRIMINAL", "CIVIL", "WRIT", "BETWEEN", "VERSUS", "ORDER", "JUDGMENT"),
                    )
                    if value and "COURT" not in value.upper():
                        candidates.append(
                            SpanCandidate(
                                value,
                                paragraph,
                                start,
                                end,
                                120 + ((len(self.BENCH_PATTERNS) - pattern_index) * 20) - (len(value) // 2),
                            )
                        )
        return self._field(self._best(candidates))

    def extract_judgment_date(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        search_paragraphs = self._header_anchor_sources(("DATE", "DATED", "PRONOUNCED"), 3)
        for paragraph in search_paragraphs:
            for pattern_index, pattern in enumerate(self.DATE_PATTERNS):
                for match in pattern.finditer(paragraph.text):
                    group_index = 1 if match.lastindex else 0
                    value, start, end = self._clean_span(
                        paragraph.text, match.start(group_index), match.end(group_index)
                    )
                    value = self._stop_at(value, ("CORAM", "BEFORE", "BETWEEN", "JUSTICE"))
                    if value:
                        candidates.append(
                            SpanCandidate(value, paragraph, start, end, 70 - len(value) - pattern_index)
                        )
        return self._field(self._best(candidates))

    def extract_parties(self) -> dict[str, dict[str, Any]]:
        if self.court_type == "calcutta":
            return CalcuttaPartyExtractor(self.header_zone).extract()
        parties = PartyExtractor(self.header_zone).extract()
        if parties["petitioner"]["value"] or parties["respondent"]["value"]:
            return parties
        return PartyExtractor(self._header_windows(max_size=4)).extract()

    def validate_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        fields = super().validate_fields(fields)
        header_indexes = {paragraph.index for paragraph in self.header_zone}
        for key in ("case_number", "judgment_date", "bench", "court_name", "petitioner", "respondent"):
            value = fields.get(key, {})
            if not isinstance(value, dict) or not value.get("value"):
                continue
            source_text = value.get("source", {}).get("paragraph_text", "")
            source_page = value.get("source", {}).get("page")
            if not self._source_in_header_zone(source_page, source_text, header_indexes):
                fields[key] = self._empty_field()

        for key in ("case_number", "judgment_date", "bench", "court_name", "petitioner", "respondent"):
            value = fields.get(key, {})
            if isinstance(value, dict) and len(value.get("value", "")) > 180:
                fields[key] = self._empty_field()
        case_number = fields.get("case_number", {}).get("value", "")
        if case_number and self._has_multiple_case_numbers(case_number):
            fields["case_number"] = self._empty_field()

        date_value = fields.get("judgment_date", {}).get("value", "")
        if case_number and date_value and self._date_year_mismatches_case_year(case_number, date_value):
            fields["judgment_date"] = self._empty_field()

        court_name = fields.get("court_name", {}).get("value", "")
        if court_name and not re.search(r"\b(?:HIGH|SUPREME)\s+COURT\b", court_name, re.IGNORECASE):
            fields["court_name"] = self._empty_field()

        if re.search(r"\bNO\.?\b", fields.get("petitioner", {}).get("value", ""), re.IGNORECASE):
            fields["petitioner"] = self._empty_field()
        if re.search(r"\bCOURT\b", fields.get("respondent", {}).get("value", ""), re.IGNORECASE):
            fields["respondent"] = self._empty_field()
        for party_key in ("petitioner", "respondent"):
            party_value = fields.get(party_key, {}).get("value", "")
            if self._invalid_party_value(party_value):
                fields[party_key] = self._empty_field()
        return fields

    def _anchor_union(self, anchors: tuple[str, ...], window_size: int) -> list[ZoneParagraph]:
        seen: set[int] = set()
        paragraphs: list[ZoneParagraph] = []
        for anchor in anchors:
            for paragraph in self._find_header_anchor_window(anchor, window_size):
                if paragraph.index in seen:
                    continue
                seen.add(paragraph.index)
                paragraphs.append(paragraph)
        return paragraphs or self.header_zone

    def _header_anchor_sources(
        self, anchors: tuple[str, ...], window_size: int
    ) -> list[ZoneParagraph]:
        sources = self._anchor_union(anchors, window_size)
        seen = {(paragraph.index, paragraph.text) for paragraph in sources}
        for window in self._header_windows(max_size=4):
            upper_text = window.text.upper()
            if not any(anchor.upper() in upper_text for anchor in anchors):
                continue
            key = (window.index, window.text)
            if key in seen:
                continue
            seen.add(key)
            sources.append(window)
        return sources or self.header_zone

    def _header_windows(self, max_size: int = 3) -> list[ZoneParagraph]:
        windows: list[ZoneParagraph] = []
        for start in range(len(self.header_zone)):
            for size in range(1, max_size + 1):
                chunk = self.header_zone[start : start + size]
                if not chunk:
                    continue
                text = " ".join(paragraph.text for paragraph in chunk if paragraph.text.strip())
                if not text:
                    continue
                windows.append(
                    ZoneParagraph(
                        index=chunk[0].index,
                        page=chunk[0].page,
                        text=text,
                    )
                )
        return windows

    def _find_header_anchor_window(self, keyword: str, window_size: int) -> list[ZoneParagraph]:
        keyword_upper = keyword.upper()
        seen: set[int] = set()
        paragraphs: list[ZoneParagraph] = []
        for index, paragraph in enumerate(self.header_zone):
            if keyword_upper not in paragraph.text.upper():
                continue
            start = max(0, index - window_size)
            end = min(len(self.header_zone), index + window_size + 1)
            for candidate in self.header_zone[start:end]:
                if candidate.index in seen:
                    continue
                seen.add(candidate.index)
                paragraphs.append(candidate)
        return paragraphs

    def _source_in_header_zone(
        self, source_page: int | None, source_text: str, header_indexes: set[int]
    ) -> bool:
        if not source_text:
            return False
        if any(
            paragraph.index in header_indexes
            and paragraph.page == source_page
            and paragraph.text == source_text
            for paragraph in self.header_zone
        ):
            return True
        for window in self._header_windows(max_size=4):
            if window.page == source_page and window.text == source_text:
                return True
        return False

    @staticmethod
    def _clean_case_number(value: str) -> str:
        value = re.sub(r"\s+", " ", value)
        year_matches = list(re.finditer(r"\b(?:19|20)\d{2}\b", value))
        if year_matches:
            value = value[: year_matches[-1].end()]
        return value.strip(" \t\r\n:;,.()[]{}-")

    @staticmethod
    def _has_multiple_case_numbers(value: str) -> bool:
        return len(re.findall(r"\bNO\.?\s*\d+", value, re.IGNORECASE)) > 1

    @staticmethod
    def _date_year_mismatches_case_year(case_number: str, date_value: str) -> bool:
        case_years = re.findall(r"\b(?:19|20)\d{2}\b", case_number)
        date_years = re.findall(r"\b(?:19|20)\d{2}\b", date_value)
        if not case_years or not date_years:
            return False
        return case_years[-1] != date_years[-1]

    @staticmethod
    def _invalid_party_value(value: str) -> bool:
        if not value or len(value.strip()) < 3 or len(value.strip()) > 150:
            return True
        return bool(
            re.search(
                r"\b(?:HIM|THE\s+WORKMAN|WORKMAN|PETITIONER-WORKMAN|"
                r"RESPONDENT-COMPANY|MANAGEMENT|COMPANY)\b",
                value,
                re.IGNORECASE,
            )
        )

    def _court_priority_bonus(self, value: str) -> int:
        upper = value.upper()
        if self.court_type == "calcutta" and re.search(
            r"(W\.P\.C\.T\.|W\.P\.A\.|W\.P\.|C\.R\.R\.|C\.O\.|CRAN|CRA|CAN|FMAT|FMA|MAT|SA)",
            upper,
        ):
            return 12
        if self.court_type in {"karnataka", "bombay"} and re.search(
            r"(CRIMINAL|CIVIL|WRIT|MISC|FIRST|SECOND|APPEAL)", upper
        ):
            return 8
        return 0


class RobustExtractor(UnifiedExtractor):
    """Balanced extractor with zone priority, scoring, and soft validation."""

    GENERIC_CASE_RE = re.compile(
        r"\b([A-Z. ]{0,40}NO\.?\s*\d+.*?\b(?:19|20)\d{2}\b)",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(
        self,
        paragraphs: list[dict[str, Any]] | list[ZoneParagraph],
        court_type: str = "generic",
    ):
        super().__init__(paragraphs, court_type=court_type)
        self.relaxed_zone = self._relaxed_zone()

    def extract_case_number(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for zone_name, zone in self._zone_order():
            for paragraph in self._zone_windows(zone, max_size=4):
                text_before_with = re.split(
                    r"\bWITH\b", paragraph.text, maxsplit=1, flags=re.IGNORECASE
                )[0]
                for pattern_index, pattern in enumerate(
                    [*self.CASE_PATTERNS, self.GENERIC_CASE_RE]
                ):
                    for match in pattern.finditer(text_before_with):
                        group_index = 1 if match.lastindex else 0
                        value, start, end = self._clean_span(
                            text_before_with,
                            match.start(group_index),
                            match.end(group_index),
                        )
                        value = self._clean_case_number(value)
                        if not value:
                            continue
                        score = self._zone_score(zone_name)
                        score += 3 if re.search(r"\bNO\.?\b", value, re.IGNORECASE) else 0
                        score += 2 if re.search(r"\b(?:19|20)\d{2}\b", value) else 0
                        score += 1 if re.search(
                            r"\b(?:APPEAL|WRIT|PETITION|CRIMINAL|CIVIL)\b",
                            value,
                            re.IGNORECASE,
                        ) else 0
                        score -= 2 if len(value) > 120 else 0
                        score -= 4 if "JUSTICE" in value.upper() else 0
                        score -= 3 if self._has_multiple_case_numbers(value) else 0
                        score += self._court_priority_bonus(value)
                        score -= pattern_index
                        score -= paragraph.index // 10
                        candidates.append(SpanCandidate(value, paragraph, start, end, score))
            if candidates and zone_name in {"header", "relaxed"}:
                break
        return self._field(self._best(candidates))

    def extract_court_name(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        fallback_re = re.compile(
            r"\b(?:IN\s+THE\s+)?(?:HIGH|SUPREME)\s+COURT\b[^\n\r]{0,120}",
            re.IGNORECASE,
        )
        for zone_name, zone in self._zone_order():
            for paragraph in self._zone_windows(zone, max_size=4):
                for pattern in (self.COURT_RE, fallback_re):
                    for match in pattern.finditer(paragraph.text):
                        value, start, end = self._clean_span(
                            paragraph.text, match.start(), match.end()
                        )
                        value = self._stop_at(value, ("DATED", "DATE", "CORAM", "BEFORE", "NO."))
                        value = re.split(r"\bNO\.?", value, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,.;:")
                        value = re.split(
                            r"\b(?:FIRST|SECOND|CRIMINAL|CIVIL|WRIT|MISC(?:ELLANEOUS)?|APPEAL|PETITION)\b",
                            value,
                            maxsplit=1,
                            flags=re.IGNORECASE,
                        )[0].strip(" ,.;:")
                        if not value:
                            continue
                        upper = value.upper()
                        score = self._zone_score(zone_name)
                        score += 3 if "COURT" in upper else 0
                        score += 2 if upper.startswith("IN THE") else 0
                        score += 3 if "HIGH COURT" in upper or "SUPREME COURT" in upper else 0
                        score -= 3 if zone_name == "full" else 0
                        score -= 3 if "NO." in upper else 0
                        score -= len(value) // 80
                        candidates.append(SpanCandidate(value, paragraph, start, end, score))
            if candidates and zone_name == "header":
                break
        return self._field(self._best(candidates))

    def extract_bench(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        for zone_name, zone in self._zone_order():
            for paragraph in self._zone_anchor_sources(zone, ("CORAM", "JUSTICE", "HON", "BEFORE"), 3):
                for pattern_index, pattern in enumerate(self.BENCH_PATTERNS):
                    for match in pattern.finditer(paragraph.text):
                        group_index = 1 if match.lastindex else 0
                        value, start, end = self._clean_span(
                            paragraph.text, match.start(group_index), match.end(group_index)
                        )
                        value = self._stop_at(
                            value,
                            ("DATED", "DATE", "CRIMINAL", "CIVIL", "WRIT", "BETWEEN", "VERSUS", "ORDER", "JUDGMENT"),
                        )
                        if not value:
                            continue
                        score = self._zone_score(zone_name)
                        score += 3 if re.search(r"\b(?:JUSTICE|J{1,2}\.?)\b", value, re.IGNORECASE) else 0
                        score += 2 if "CORAM" in paragraph.text.upper() else 0
                        score -= 4 if "COURT" in value.upper() else 0
                        score -= pattern_index
                        candidates.append(SpanCandidate(value, paragraph, start, end, score))
            if candidates and zone_name == "header":
                break
        return self._field(self._best(candidates))

    def extract_judgment_date(self) -> dict[str, Any]:
        candidates: list[SpanCandidate] = []
        case_number = self.extract_case_number().get("value", "")
        for zone_name, zone in self._zone_order():
            for paragraph in self._zone_anchor_sources(zone, ("DATE", "DATED", "PRONOUNCED"), 3):
                for pattern_index, pattern in enumerate(self.DATE_PATTERNS):
                    for match in pattern.finditer(paragraph.text):
                        group_index = 1 if match.lastindex else 0
                        value, start, end = self._clean_span(
                            paragraph.text, match.start(group_index), match.end(group_index)
                        )
                        value = self._stop_at(value, ("CORAM", "BEFORE", "BETWEEN", "JUSTICE"))
                        if not value:
                            continue
                        score = self._zone_score(zone_name)
                        score += 3 if re.search(r"\b(?:DATE|DATED|PRONOUNCED)\b", paragraph.text, re.IGNORECASE) else 0
                        score += 2 if re.search(r"\b(?:19|20)\d{2}\b", value) else 0
                        score -= 3 if case_number and self._date_year_mismatches_case_year(case_number, value) else 0
                        score -= pattern_index
                        candidates.append(SpanCandidate(value, paragraph, start, end, score))
            if candidates and zone_name == "header":
                break
        if candidates:
            return self._field(self._best(candidates))
        return self._field(self._best(self._unanchored_date_candidates()))

    def extract_parties(self) -> dict[str, dict[str, Any]]:
        candidates: list[tuple[int, dict[str, dict[str, Any]]]] = []
        for zone_name, zone in self._zone_order():
            for source in (zone, self._zone_windows(zone, max_size=4)):
                extractor_class = CalcuttaPartyExtractor if self.court_type == "calcutta" else RobustPartyExtractor
                result = extractor_class(source).extract()
                if not (result["petitioner"]["value"] or result["respondent"]["value"]):
                    continue
                candidates.append((self._zone_score(zone_name) + self._party_score(result), result))
            if candidates and zone_name == "header":
                break
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
        return {"petitioner": self._empty_field(), "respondent": self._empty_field()}

    def validate_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        for key in ("case_number", "judgment_date", "bench", "court_name", "petitioner", "respondent"):
            value = fields.get(key, {})
            if isinstance(value, dict) and value.get("value") and len(value["value"]) > 220:
                value["value"] = value["value"][:220].strip(" ,.;:")
        return fields

    def extract_all(self) -> dict[str, Any]:
        fields = super().extract_all()
        if not any(
            fields[key]["value"]
            for key in ("case_number", "judgment_date", "bench", "court_name", "petitioner", "respondent")
        ):
            fallback = self._best_text_fallback()
            if fallback:
                fields["court_name"] = self._field(fallback)
        return fields

    def _zone_order(self) -> list[tuple[str, list[ZoneParagraph]]]:
        return [("header", self.header_zone), ("relaxed", self.relaxed_zone), ("full", self.paragraphs)]

    @staticmethod
    def _zone_score(zone_name: str) -> int:
        return {"header": 30, "relaxed": 15, "full": -10}.get(zone_name, -10)

    def _relaxed_zone(self) -> list[ZoneParagraph]:
        page_numbers: list[int] = []
        for paragraph in self.paragraphs:
            if paragraph.page not in page_numbers:
                page_numbers.append(paragraph.page)
            if len(page_numbers) == 2:
                break
        return [paragraph for paragraph in self.paragraphs if paragraph.page in set(page_numbers)]

    @staticmethod
    def _zone_windows(zone: list[ZoneParagraph], max_size: int = 3) -> list[ZoneParagraph]:
        windows: list[ZoneParagraph] = []
        for start in range(len(zone)):
            for size in range(1, max_size + 1):
                chunk = zone[start : start + size]
                text = " ".join(paragraph.text for paragraph in chunk if paragraph.text.strip())
                if text:
                    windows.append(ZoneParagraph(index=chunk[0].index, page=chunk[0].page, text=text))
        return windows

    def _zone_anchor_sources(
        self, zone: list[ZoneParagraph], anchors: tuple[str, ...], window_size: int
    ) -> list[ZoneParagraph]:
        seen: set[tuple[int, str]] = set()
        sources: list[ZoneParagraph] = []
        for index, paragraph in enumerate(zone):
            if not any(anchor.upper() in paragraph.text.upper() for anchor in anchors):
                continue
            start = max(0, index - window_size)
            end = min(len(zone), index + window_size + 1)
            for candidate in zone[start:end]:
                key = (candidate.index, candidate.text)
                if key not in seen:
                    seen.add(key)
                    sources.append(candidate)
        for window in self._zone_windows(zone, max_size=4):
            if any(anchor.upper() in window.text.upper() for anchor in anchors):
                key = (window.index, window.text)
                if key not in seen:
                    seen.add(key)
                    sources.append(window)
        return sources or zone[:20]

    def _unanchored_date_candidates(self) -> list[SpanCandidate]:
        candidates: list[SpanCandidate] = []
        for zone_name, zone in self._zone_order():
            for paragraph in zone[:30]:
                for match in DATE_VALUE_RE.finditer(paragraph.text):
                    value, start, end = self._clean_span(paragraph.text, match.start(1), match.end(1))
                    candidates.append(SpanCandidate(value, paragraph, start, end, self._zone_score(zone_name) - 5))
            if candidates:
                break
        return candidates

    @staticmethod
    def _party_score(result: dict[str, dict[str, Any]]) -> int:
        score = 0
        for side in ("petitioner", "respondent"):
            value = result[side]["value"]
            source = result[side]["source"].get("paragraph_text", "")
            if value:
                score += 5
            if re.search(r"\b(?:V(?:S\.?|\.)|VERSUS)\b", source, re.IGNORECASE):
                score += 3
            if re.search(r"\b(?:PETITIONER|RESPONDENT|APPELLANT)\b", source, re.IGNORECASE):
                score += 2
            if re.search(r"\b(?:WORKMAN|HIM|PETITIONER-WORKMAN|RESPONDENT-COMPANY)\b", value, re.IGNORECASE):
                score -= 5
        return score

    def _best_text_fallback(self) -> SpanCandidate | None:
        for paragraph in [*self.header_zone, *self.relaxed_zone, *self.paragraphs]:
            value = self._clean_value(paragraph.text)
            if len(value) >= 3:
                return SpanCandidate(value[:180], paragraph, 0, min(len(paragraph.text), 180), -50)
        return None


class MasterExtractor:
    SUPREME = "supreme"
    KARNATAKA = "karnataka"
    CALCUTTA = "calcutta"
    BOMBAY = "bombay"
    GENERIC = "generic"

    def __init__(self, paragraphs: list[dict[str, Any]]):
        self.paragraphs = BaseExtractor._normalize_paragraphs(paragraphs)

    def detect_court_type(
        self, paragraphs: list[dict[str, Any]] | list[ZoneParagraph] | None = None
    ) -> str:
        normalized = (
            self.paragraphs
            if paragraphs is None
            else BaseExtractor._normalize_paragraphs(paragraphs)
        )
        first_page = self._first_page_top(normalized)
        text = "\n".join(paragraph.text for paragraph in first_page).upper()

        if (
            "S.C.R." in text
            or "SUPREME COURT REPORTS" in text
            or re.search(r"\b[A-Z][A-Z .,&-]+\s+V\.?\s+[A-Z][A-Z .,&-]+\b", text)
        ):
            return self.SUPREME

        if "HIGH COURT OF KARNATAKA" in text and (
            "DHARWAD BENCH" in text or "BENGALURU" in text or "BANGALORE" in text
        ):
            return self.KARNATAKA

        if "HIGH COURT OF JUDICATURE AT BOMBAY" in text:
            return self.BOMBAY

        if (
            "HIGH COURT AT CALCUTTA" in text
            or "APPELLATE SIDE" in text
            or re.search(
                r"(?:W\.P\.C\.T\.|W\.P\.A\.|W\.P\.|C\.R\.R\.|C\.O\.|CRAN|CRA|CAN|FMAT|FMA|MAT|SA)\s*(?:NO\.?)?\s*\d+",
                text,
            )
        ):
            return self.CALCUTTA

        return self.GENERIC

    def extract(self, paragraphs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        normalized = (
            self.paragraphs
            if paragraphs is None
            else BaseExtractor._normalize_paragraphs(paragraphs)
        )
        court_type = self.detect_court_type(normalized)
        return RobustExtractor(normalized, court_type=court_type).extract_all()

    def extract_all(self) -> dict[str, Any]:
        return self.extract()

    @staticmethod
    def _first_page_top(paragraphs: list[ZoneParagraph]) -> list[ZoneParagraph]:
        if not paragraphs:
            return []
        first_page_number = paragraphs[0].page
        first_page = [paragraph for paragraph in paragraphs if paragraph.page == first_page_number]
        return first_page[:30]


class ZoneExtractor(MasterExtractor):
    """Backward-compatible controller used by the FastAPI upload route."""

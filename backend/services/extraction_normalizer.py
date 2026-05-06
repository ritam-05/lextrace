import json
import os
import re
from copy import deepcopy
from typing import Any

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()


class ExtractionNormalizer:
    def __init__(self) -> None:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise ValueError(" SARVAM_API_KEY missing from .env file.")

        self.client = SarvamAI(api_subscription_key=api_key)
        self.model = "sarvam-30b"
    def normalize(
        self,
        extracted: dict[str, Any],
        source_text: str,
        court_type: str = "generic",
    ) -> dict[str, Any]:
        if not self.client or court_type not in {"generic", "district"}:
            return {
                "applied": False,
                "needs_human_review": False,
                "notes": "Normalization skipped for this court type or GROQ_API_KEY is unavailable.",
                "normalized_extraction": extracted,
            }

        prompt = f"""
You are a legal OCR normalizer for Indian court documents.

Task:
- Correct spelling mistakes, broken OCR characters, spacing, and punctuation in extracted fields.
- Do not invent new facts.
- Do not change numeric identifiers, case numbers, or dates unless you are only normalizing punctuation/spacing.
- If a date looks inconsistent, ambiguous, or factually uncertain, keep it exactly as given and set needs_human_review to true.
- Prefer conservative corrections over aggressive rewriting.
- Preserve the same top-level keys and the same overall JSON shape.
- For dictionary fields with a `value` key, only update the `value` string and keep the other metadata intact.
- For list fields, only correct obvious OCR noise in each string item.

Court type: {court_type}

Raw extracted JSON:
{json.dumps(extracted, ensure_ascii=False)}

Source text:
{source_text[:14000]}

Return only valid JSON in this shape:
{{
  "needs_human_review": false,
  "notes": "short note about what was corrected or why nothing changed",
  "normalized_extraction": {{ ...same shape as the raw extracted JSON... }}
}}
"""

        try:
            response = self.client.chat.completions(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                top_p=1,
                temperature=0.0,
            )
            payload = json.loads(response.choices[0].message.content)
            normalized = payload.get("normalized_extraction", extracted)
            normalized = self._district_party_fallback(normalized, source_text, court_type)
            return {
                "applied": True,
                "needs_human_review": bool(payload.get("needs_human_review", False)),
                "notes": str(payload.get("notes", "")),
                "normalized_extraction": self._merge_extraction(deepcopy(extracted), normalized),
            }
        except Exception as exc:
            return {
                "applied": False,
                "needs_human_review": False,
                "notes": f"Normalization failed: {exc}",
                "normalized_extraction": extracted,
            }

    def _merge_extraction(self, original: Any, normalized: Any) -> Any:
        if isinstance(original, dict) and isinstance(normalized, dict):
            merged = dict(original)
            for key, value in normalized.items():
                if key not in original:
                    merged[key] = value
                    continue
                original_value = original[key]
                if isinstance(original_value, dict) and isinstance(value, dict):
                    merged[key] = self._merge_extraction(original_value, value)
                elif isinstance(original_value, dict) and "value" in original_value and isinstance(value, str):
                    updated_field = dict(original_value)
                    updated_field["value"] = value
                    merged[key] = updated_field
                elif isinstance(original_value, list) and isinstance(value, list):
                    merged[key] = value
                elif isinstance(original_value, str) and isinstance(value, str):
                    merged[key] = value
                else:
                    merged[key] = value
            return merged
        return normalized

    def _district_party_fallback(
        self,
        normalized: Any,
        source_text: str,
        court_type: str,
    ) -> Any:
        if court_type != "district" or not isinstance(normalized, dict):
            return normalized

        petitioner = normalized.get("petitioner")
        respondent = normalized.get("respondent")

        petitioner_value = self._field_value(petitioner)
        respondent_value = self._field_value(respondent)
        plural_case = self._looks_plural_party_case(source_text)

        candidate_names = self._district_name_candidates(source_text)
        if plural_case and candidate_names:
            repaired_value = " and ".join(candidate_names[:2]) if len(candidate_names) >= 2 else candidate_names[0]
            if isinstance(petitioner, dict):
                petitioner = dict(petitioner)
                petitioner["value"] = repaired_value
                normalized["petitioner"] = petitioner
            if isinstance(respondent, dict):
                respondent = dict(respondent)
                respondent["value"] = ""
                normalized["respondent"] = respondent
            return normalized

        if self._looks_like_party_noise(petitioner_value):
            if candidate_names:
                if self._looks_plural_party_case(source_text) and len(candidate_names) >= 2:
                    repaired_value = " and ".join(candidate_names[:2])
                else:
                    repaired_value = candidate_names[0]
                if isinstance(petitioner, dict):
                    petitioner = dict(petitioner)
                    petitioner["value"] = repaired_value
                    normalized["petitioner"] = petitioner

        if self._looks_like_party_noise(respondent_value):
            if isinstance(respondent, dict):
                respondent = dict(respondent)
                respondent["value"] = ""
                normalized["respondent"] = respondent

        return normalized

    @staticmethod
    def _field_value(field: Any) -> str:
        if isinstance(field, dict):
            return str(field.get("value", "") or "")
        if isinstance(field, str):
            return field
        return ""

    @staticmethod
    def _looks_like_party_noise(value: str) -> bool:
        if not value:
            return True
        upper = value.upper()
        return bool(
            re.search(r"\b(?:CNR|SUIT|CASE|ORDER|CODE|COURT|DATED|NO\.?|MAT\.?|FILED)\b", upper)
            or len(value.strip()) < 3
        )

    @staticmethod
    def _looks_plural_party_case(source_text: str) -> bool:
        return bool(
            re.search(r"\bboth\s+the\s+petitioners\b", source_text, re.IGNORECASE)
            or re.search(r"\bpetitioner\s+no\.?\s*1\b", source_text, re.IGNORECASE)
            or re.search(r"\bpetitioners\b", source_text, re.IGNORECASE)
        )

    @staticmethod
    def _district_name_candidates(source_text: str) -> list[str]:
        candidates: list[str] = []
        noise = re.compile(
            r"\b(?:COURT|PRESENT|ORDER|DATED|DATE|MAT\.?|SUIT|CASE|CNR|CODE|JUDGE|MAGISTRATE|DISTRICT|APPEAL|PETITION|NO\.?)\b",
            re.IGNORECASE,
        )
        for raw_line in source_text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" \t\r\n:;,.()[]{}-|\"")
            if len(line) < 3 or noise.search(line):
                continue
            if not re.search(r"\b(?:SRI|SHRI|SMT|MRS|MS|MR|DR)\b", line, re.IGNORECASE) and not re.search(
                r"[A-Z][a-z]+\s+[A-Z][a-z]+", line
            ):
                continue
            if line not in candidates:
                candidates.append(line)
        return candidates

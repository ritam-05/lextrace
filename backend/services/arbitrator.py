"""
Arbitration Engine: Compares Regex vs RAG outputs field-by-field and produces confidence-scored verdicts.
"""
import re
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class ExtractedField:
    """Represents a single extracted field with metadata."""
    value: str
    confidence: float
    source: str  # "regex" or "rag"
    para_index: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


@dataclass
class ArbitrationResult:
    """Result of arbitrating a single field between Regex and RAG."""
    field_name: str
    final_value: str
    state: str  # "dual_verified", "mismatch", "single_source_regex", "single_source_rag"
    confidence: float
    regex_value: Optional[str] = None
    rag_value: Optional[str] = None
    regex_source: Optional[Dict[str, Any]] = None
    rag_source: Optional[Dict[str, Any]] = None
    notes: str = ""


class Arbitrator:
    """
    Compares Regex and RAG extractions field-by-field.
    Produces dual-verified/mismatch/single-source verdicts with confidence scores.
    """
    
    # Fields that both Regex and RAG should extract
    OVERLAPPING_FIELDS = {
        "case_number",
        "court_name",
        "bench",
        "judgment_date",
        "petitioner",
        "respondent"
    }
    
    # RAG-only fields (no Regex counterpart)
    RAG_ONLY_FIELDS = {
        "directives",
        "responsible_departments",
        "deadlines"
    }
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison: lowercase, remove extra spaces, punctuation."""
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)  # Collapse whitespace
        text = re.sub(r'[^\w\s]', '', text)  # Remove special chars
        return text
    
    @staticmethod
    def similarity_score(text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0.0 to 1.0)."""
        if not text1 or not text2:
            return 0.0
        
        norm1 = Arbitrator.normalize_text(text1)
        norm2 = Arbitrator.normalize_text(text2)
        
        if norm1 == norm2:
            return 1.0
        
        # Simple Levenshtein-like partial matching
        if norm1 in norm2 or norm2 in norm1:
            return 0.85
        
        # Check for word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if words1 and words2:
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            return overlap
        
        return 0.0
    
    def arbitrate_field(
        self,
        field_name: str,
        regex_output: Optional[Dict[str, Any]],
        rag_output: Optional[Any]
    ) -> ArbitrationResult:
        """
        Arbitrate a single field between Regex and RAG outputs.
        Returns ArbitrationResult with verdict and confidence.
        """
        # Handle regex output (structured dict)
        regex_value = regex_output.get("value") if regex_output else None
        regex_confidence = regex_output.get("confidence", 0.8) if regex_output else 0.0
        
        # Handle RAG output (can be string, list, or dict)
        if isinstance(rag_output, dict):
            rag_value = rag_output.get("value")
            rag_confidence = rag_output.get("confidence", 0.8)
        elif isinstance(rag_output, str):
            rag_value = rag_output if rag_output.strip() else None
            rag_confidence = 0.8
        elif isinstance(rag_output, list):
            rag_value = rag_output if rag_output else None
            rag_confidence = 0.8
        else:
            rag_value = None
            rag_confidence = 0.0
        
        # Both sources found the field
        if regex_value and rag_value:
            similarity = self.similarity_score(regex_value, rag_value)
            
            if similarity >= 0.9:
                # Dual-verified: Strong agreement
                final_value = regex_value  # Prefer Regex (deterministic)
                state = "dual_verified"
                confidence = 0.95
                notes = "Both sources agree with high confidence."
            elif similarity >= 0.7:
                # Partial match: Minor differences
                final_value = regex_value
                state = "dual_verified"
                confidence = 0.85
                notes = f"Both sources match with {similarity:.1%} similarity."
            else:
                # Mismatch: Conflicting values
                final_value = regex_value  # Prefer Regex for review
                state = "mismatch"
                confidence = 0.5
                notes = f"Conflicting values detected. Similarity: {similarity:.1%}. Requires human review."
        
        # Only Regex found the field
        elif regex_value:
            final_value = regex_value
            state = "single_source_regex"
            confidence = 0.70
            notes = "Extracted by Regex only."
        
        # Only RAG found the field
        elif rag_value:
            final_value = rag_value
            state = "single_source_rag"
            confidence = 0.75
            notes = "Extracted by RAG (semantic) only."
        
        # Neither found it
        else:
            final_value = None
            state = "not_found"
            confidence = 0.0
            notes = "Field not found by either extraction method."
        
        # Build source tracking
        regex_source = None
        if regex_output:
            regex_source = {
                "para_index": regex_output.get("para_index"),
                "char_start": regex_output.get("char_start"),
                "char_end": regex_output.get("char_end"),
                "source": regex_output.get("source")
            }
        
        rag_source = None
        if rag_output:
            if isinstance(rag_output, dict):
                rag_source = {
                    "para_indices": rag_output.get("para_indices"),
                    "confidence": rag_output.get("confidence")
                }
            else:
                # For direct values from RAG, we don't have detailed source info
                rag_source = {
                    "para_indices": None,
                    "confidence": rag_confidence
                }
        
        return ArbitrationResult(
            field_name=field_name,
            final_value=final_value,
            state=state,
            confidence=confidence,
            regex_value=regex_value,
            rag_value=rag_value,
            regex_source=regex_source,
            rag_source=rag_source,
            notes=notes
        )
    
    def arbitrate_all(
        self,
        regex_output: Dict[str, Any],
        rag_output: Dict[str, Any]
    ) -> Dict[str, ArbitrationResult]:
        """
        Arbitrate all overlapping fields + combine with single-source fields.
        Returns dict of {field_name: ArbitrationResult}
        """
        results = {}
        
        # 1. Arbitrate overlapping fields
        for field in self.OVERLAPPING_FIELDS:
            regex_field = regex_output.get(field)
            rag_field = rag_output.get(field)  # This is now the direct value
            
            result = self.arbitrate_field(field, regex_field, rag_field)
            results[field] = result
        
        # 2. Add RAG-only fields (auto-marked as single_source_rag)
        for field in self.RAG_ONLY_FIELDS:
            rag_field = rag_output.get(field)  # This is now the direct value
            
            if rag_field:
                result = self.arbitrate_field(field, None, rag_field)
                results[field] = result
        
        return results
    
    def generate_arbitration_summary(
        self,
        arbitration_results: Dict[str, ArbitrationResult]
    ) -> Dict[str, Any]:
        """Generate a summary of arbitration results."""
        dual_verified = sum(1 for r in arbitration_results.values() if r.state == "dual_verified")
        mismatches = sum(1 for r in arbitration_results.values() if r.state == "mismatch")
        single_source = sum(1 for r in arbitration_results.values() if "single_source" in r.state)
        not_found = sum(1 for r in arbitration_results.values() if r.state == "not_found")
        
        avg_confidence = sum(r.confidence for r in arbitration_results.values()) / len(arbitration_results) if arbitration_results else 0.0
        
        return {
            "total_fields": len(arbitration_results),
            "dual_verified_count": dual_verified,
            "mismatch_count": mismatches,
            "single_source_count": single_source,
            "not_found_count": not_found,
            "average_confidence": round(avg_confidence, 2),
            "requires_human_review": mismatches > 0
        }

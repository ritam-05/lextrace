import re
from typing import Optional

from backend.services.utils import logger


# Pattern registry kept for parity with the existing extractor metadata style.
BENCH_PATTERNS: dict[str, str] = {}


def _r(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# Each entry: (compiled_regex, canonical_case_type, pattern_id, confidence)
# First match wins.
_CASE_TYPE_RULES: list[tuple[re.Pattern, str, str, float]] = [
    (_r(r"\bW\.?P\.?H\.?C\.?\b|\bWPHC\b"),
     "Writ Petition (Habeas Corpus)", "CT_WPHC_01", 0.97),
    (_r(r"\bW\.?P\.?\s*\(?PIL\)?|\bPIL\s*WP\b"),
     "Writ Petition (PIL)", "CT_WP_PIL_01", 0.97),
    (_r(r"\bW\.?P\.?\s*\(C\)|\bWPC\b"),
     "Writ Petition (Civil)", "CT_WP_CIVIL_01", 0.95),
    (_r(r"\bW\.?P\.?\s*\(Crl\.?\)|\bWPCRL\b"),
     "Writ Petition (Criminal)", "CT_WP_CRL_01", 0.95),
    (_r(r"\bWRIT\s+PETITION\b|\bW\.?P\.?\b"),
     "Writ Petition", "CT_WP_01", 0.93),
    (_r(r"\bSLP\s*\(Crl\.?\)|\bSLPC?RL\b"),
     "Special Leave Petition (Criminal)", "CT_SLP_CRL_01", 0.97),
    (_r(r"\bSLP\s*\(C\)|\bSLPC\b"),
     "Special Leave Petition (Civil)", "CT_SLP_CIVIL_01", 0.97),
    (_r(r"\bSPECIAL\s+LEAVE\s+PETITION\b|\bSLP\b"),
     "Special Leave Petition", "CT_SLP_01", 0.95),
    (_r(r"\bCRADB\b|\bCRL\.?\s*A\.?\s*DB\b"),
     "Criminal Appeal (Division Bench)", "CT_CRADB_01", 0.97),
    (_r(r"\bCRIMINAL\s+APPEAL\b|\bCRL\.?\s*A\.?\b|\bCRL\.?\s*APPEAL\b"),
     "Criminal Appeal", "CT_CRL_APPEAL_01", 0.95),
    (_r(r"\bCIVIL\s+APPEAL\b|\bC\.?A\.?\s+No\b"),
     "Civil Appeal", "CT_CIVIL_APPEAL_01", 0.95),
    (_r(r"\bCRL\.?\s*REV\.?\s*P\.?\b|\bCRL\.?\s*REVISION\b"),
     "Criminal Revision Petition", "CT_CRL_REV_01", 0.95),
    (_r(r"\bCRR\b"),
     "Criminal Revision", "CT_CRR_01", 0.95),
    (_r(r"\bCRL\.?\s*M\.?C\.?\b"),
     "Criminal Miscellaneous Case", "CT_CRL_MC_01", 0.95),
    (_r(r"\bCRL\.?\s*M\.?A\.?\b"),
     "Criminal Miscellaneous Application", "CT_CRL_MA_01", 0.95),
    (_r(r"\bMAT\.?\s*SUIT\b|\bMATRIMONIAL\s+SUIT\b"),
     "Matrimonial Suit", "CT_MAT_SUIT_01", 0.97),
    (_r(r"\bMFA\b"),
     "Miscellaneous First Appeal", "CT_MFA_01", 0.93),
    (_r(r"\bMACA\b"),
     "Motor Accident Claim Appeal", "CT_MACA_01", 0.95),
    (_r(r"\bMAC\b"),
     "Motor Accident Claim", "CT_MAC_01", 0.93),
    (_r(r"\bRSA\b"),
     "Regular Second Appeal", "CT_RSA_01", 0.95),
    (_r(r"\bRFA\b"),
     "Regular First Appeal", "CT_RFA_01", 0.95),
    (_r(r"\bLPA\b|\bLETTERS\s+PATENT\s+APPEAL\b"),
     "Letters Patent Appeal", "CT_LPA_01", 0.95),
    (_r(r"\bWRIT\s+APPEAL\b|\bW\.?A\.?\s+No\b"),
     "Writ Appeal", "CT_WRIT_APPEAL_01", 0.95),
    (_r(r"\bFIRST\s+APPEAL\b|\bFA\b"),
     "First Appeal", "CT_FA_01", 0.90),
    (_r(r"\bSECOND\s+APPEAL\b|\bSA\b"),
     "Second Appeal", "CT_SA_01", 0.90),
    (_r(r"\bAPPEAL\s+FROM\s+ORIGINAL|\bAS\b"),
     "Appeal from Original Suit", "CT_AS_01", 0.90),
    (_r(r"\bCONT\.?\s*CAS\.?\s*\(C\)|\bCONTEMPT\s+CASE\b"),
     "Contempt Case (Civil)", "CT_CONT_CASE_01", 0.95),
    (_r(r"\bCONTEMPT\s+PETITION\b|\bCONT\.?\s*PET\b"),
     "Contempt Petition", "CT_CONT_PET_01", 0.95),
    (_r(r"\bCIVIL\s+SUIT\b|\b(?<!\w)CS\b"),
     "Civil Suit", "CT_CS_01", 0.90),
    (_r(r"\bORIGINAL\s+SUIT\b|\bO\.?S\.?\b"),
     "Original Suit", "CT_OS_01", 0.90),
    (_r(r"\bTITLE\s+SUIT\b|\bTS\b"),
     "Title Suit", "CT_TS_01", 0.90),
    (_r(r"\bCIVIL\s+ORIGINAL\b|\b(?<!\w)C\.?O\.?\b(?!\w)"),
     "Civil Original", "CT_CO_01", 0.90),
    (_r(r"\bARB\.?\s*P\.?\b|\bARBITRATION\s+PETITION\b"),
     "Arbitration Petition", "CT_ARB_01", 0.95),
    (_r(r"\bEFA\b|\bEXECUTION\s+FIRST\s+APPEAL\b"),
     "Execution First Appeal", "CT_EFA_01", 0.93),
    (_r(r"\bEXECUTION\s+PETITION\b|\b(?<!\w)EP\b(?!\w)"),
     "Execution Petition", "CT_EP_01", 0.90),
    (_r(r"\bTR\.?\s*P\.?\s*\(Crl\.?\)|\bTRANSFER\s+PETITION.*CRL\b"),
     "Transfer Petition (Criminal)", "CT_TP_CRL_01", 0.95),
    (_r(r"\bTR\.?\s*P\.?\s*\(C\)|\bTRANSFER\s+PETITION.*CIV\b"),
     "Transfer Petition (Civil)", "CT_TP_CIV_01", 0.95),
    (_r(r"\bTRANSFER\s+PETITION\b|\bTR\.?\s*P\.?\b"),
     "Transfer Petition", "CT_TP_01", 0.90),
    (_r(r"\bBAIL\s+APPLICATION\b|\bBA\b"),
     "Bail Application", "CT_BAIL_01", 0.93),
    (_r(r"\bREVIEW\s+PETITION\b|\bREV\.?\s*PET\b"),
     "Review Petition", "CT_REV_PET_01", 0.95),
    (_r(r"\bCURATIVE\s+PETITION\b"),
     "Curative Petition", "CT_CURATIVE_01", 0.97),
    (_r(r"\bELECTION\s+PETITION\b|\b(?<!\w)EP\b(?!\w)"),
     "Election Petition", "CT_ELECT_01", 0.95),
    (_r(r"\bMISCELLANEOUS\s+APPLICATION\b|\b(?<!\w)MA\b(?!\w)"),
     "Miscellaneous Application", "CT_MA_01", 0.85),
    (_r(r"\bINTERLOCUTORY\s+APPLICATION\b|\b(?<!\w)IA\b(?!\w)"),
     "Interlocutory Application", "CT_IA_01", 0.85),
]

for _, _, pattern_id, _ in _CASE_TYPE_RULES:
    BENCH_PATTERNS[pattern_id] = pattern_id


def extract_case_type(
    case_number: str,
    source_paragraph: Optional[dict] = None,
) -> dict:
    """
    Derive case type purely from the case number string.
    No LLM. No RAG. No PDF scanning.
    """
    if not case_number or not case_number.strip():
        return {
            "value": None,
            "pattern_id": "NO_MATCH",
            "confidence": 0.0,
            "source": source_paragraph,
        }

    cn = case_number.strip()

    for pattern, case_type, pattern_id, confidence in _CASE_TYPE_RULES:
        if pattern.search(cn):
            logger.debug(
                "[extract_case_type] pattern_id=%s matched '%s' -> '%s'",
                pattern_id,
                cn,
                case_type,
            )
            return {
                "value": case_type,
                "pattern_id": pattern_id,
                "confidence": confidence,
                "source": source_paragraph,
            }

    logger.warning("[extract_case_type] No pattern matched case_number='%s'", cn)
    return {
        "value": None,
        "pattern_id": "NO_MATCH",
        "confidence": 0.0,
        "source": source_paragraph,
    }

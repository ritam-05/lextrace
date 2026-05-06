/**
 * PyMuPDF bounding box coordinates in PDF units.
 */
export interface BBox {
  /** Left X coordinate in PyMuPDF space. */
  x0: number;
  /** Bottom Y coordinate in PyMuPDF space. */
  y0: number;
  /** Right X coordinate in PyMuPDF space. */
  x1: number;
  /** Top Y coordinate in PyMuPDF space. */
  y1: number;
}

/**
 * Human review state for any extracted field or action item.
 */
export type ReviewStatus =
  | "unreviewed"
  | "approved"
  | "edited"
  | "rejected";

/**
 * High-level action classification for a court directive.
 */
export type ActionNature = "Compliance" | "Appeal" | "Advisory";

/**
 * Visual tier derived from a numeric confidence score.
 */
export type ConfidenceTier = "high" | "medium" | "low";

/**
 * Processing lifecycle state for a judgment document.
 */
export type DocumentStatus = "processing" | "pending_review" | "verified";

/**
 * Core extracted judgment metadata.
 */
export interface ExtractedZones {
  /** Parsed case number from the judgment, if available. */
  case_number: string | null;
  /** Parsed case type such as writ, civil, or criminal, if available. */
  case_type: string | null;
  /** Parsed judgment or order date as a display string, if available. */
  judgment_date: string | null;
  /** Parsed court name from the judgment header, if available. */
  /** Parsed bench or judge names associated with the judgment. */
  bench: string[];
  /** Parsed petitioner name or party title, if available. */
  petitioner: string | null;
  /** Parsed respondent name or party title, if available. */
  respondent: string | null;
}

/**
 * Source metadata associated with an extracted field.
 */
export interface ExtractedFieldEvidence {
  /** Confidence score from 0.0 to 1.0 assigned by the producing extractor. */
  confidence: number;
  /** One-indexed source page number when known. */
  source_page: number | null;
}

/**
 * A single extracted field shown in the human review experience.
 */
export interface ReviewField {
  /** Stable identifier for this reviewable field. */
  fieldId: string;
  /** Human-readable label rendered in the review UI. */
  label: string;
  /** Extracted value produced by the arbitration or extraction layer. */
  value: string | null;
  /** Confidence score from 0.0 to 1.0 assigned by the arbitration layer. */
  confidence: number;
  /** One-indexed PDF page number where the source evidence appears. */
  source_page: number;
  /** Bounding box for the source evidence in PyMuPDF coordinates, if locatable. */
  source_bbox: BBox | null;
  /** Current review decision for this field. */
  review_status: ReviewStatus;
  /** Human-edited replacement value after reviewer intervention. */
  edited_value?: string;
}

/** A single court directive - what the court ordered */
export interface KeyDirection {
  id: string;
  text: string;
  review_status: ReviewStatus;
  edited_text?: string;
}

/** A compliance step - what the govt must do */
export interface ComplianceStep {
  id: string;
  text: string;
  review_status: ReviewStatus;
  edited_text?: string;
}

/**
 * A standalone timeline entry.
 * IMPORTANT: timelines are independent of individual
 * directives - they apply to the judgment as a whole.
 */
export interface TimelineEntry {
  id: string;
  text: string;
  review_status: ReviewStatus;
  edited_text?: string;
}

/** Appeal risk analysis from the AI */
export interface AppealAnalysis {
  /** HIGH / MEDIUM / LOW / NOT_APPLICABLE */
  consideration: string;
  /**
   * Supporting reasons behind the appeal recommendation.
   */
  justification: string[];
  /**
   * -1 = no adverse impact, favorable to government
   *  0 = neutral
   *  1-3 = low risk, 4-6 = medium, 7-10 = high risk
   */
  risk_score: number;
}

/** The complete structured action plan for one judgment */
export interface ActionPlan {
  key_directions: KeyDirection[];
  compliance_steps: ComplianceStep[];
  /** Independent section - not attached to any directive */
  timelines: TimelineEntry[];
  responsible_departments: string[];
  nature_of_action: string;
  appeal_analysis: AppealAnalysis;
  llm_context: string;
}

/**
 * Summary metadata for a stored judgment document.
 */
export interface JudgmentDocument {
  /** Unique document identifier from the persistence layer. */
  _id: string;
  /** Original uploaded PDF filename. */
  filename: string;
  /** Extracted case number for list and detail views, if available. */
  case_number: string | null;
  /** ISO timestamp representing when the file was uploaded. */
  upload_date: string;
  /** Current processing or verification status of the document. */
  status: DocumentStatus;
  /** Department associated with the document, if assigned. */
  department: string | null;
  /** Name of the reviewer who verified the document, if any. */
  verified_by: string | null;
  /** ISO timestamp indicating when the document was verified, if any. */
  verified_at: string | null;
}

/**
 * Audit trail entry for a human edit made during review.
 */
export interface AuditEntry {
  /** Identifier of the field or item that was changed. */
  field_id: string;
  /** Original machine-produced value before the human edit. */
  original_value: string | null;
  /** Updated value entered by the reviewer. */
  edited_value: string;
  /** Name of the reviewer who made the edit. */
  reviewer: string;
  /** ISO timestamp of when the edit occurred. */
  timestamp: string;
}

/**
 * Payload submitted when a reviewer completes judgment verification.
 */
export interface VerificationPayload {
  /** Full set of reviewed metadata fields for the document. */
  fields: ReviewField[];
  /** Full structured action plan for the document. */
  action_plan: ActionPlan;
  /** Name of the reviewer completing the verification. */
  reviewer: string;
  /** ISO timestamp indicating when the review was completed. */
  reviewed_at: string;
}

/**
 * PDF page dimensions used to scale coordinate overlays.
 */
export interface PageDimensions {
  /** One-indexed page number in the source PDF. */
  page_number: number;
  /** Native page width in PyMuPDF PDF units. */
  width: number;
  /** Native page height in PyMuPDF PDF units. */
  height: number;
}

/**
 * Page-level text extracted from the uploaded judgment.
 */
export interface UploadPageText {
  /** One-indexed page number for the extracted text. */
  page: number;
  /** Extracted or OCR-generated page text. */
  text: string;
}

/**
 * Paragraph-level extracted text from the uploaded judgment.
 */
export interface UploadParagraph {
  /** Stable paragraph identifier for UI rendering and linking. */
  id: string;
  /** One-indexed page number where the paragraph appears. */
  page: number;
  /** Paragraph text content. */
  text: string;
}

/**
 * Normalized upload response used by the frontend after proxying FastAPI output.
 */
export interface UploadResponse {
  /** Stable document identifier assigned during upload. */
  doc_id: string;
  /** Original uploaded filename. */
  filename: string;
  /** Page-by-page extracted text from the source PDF. */
  page_texts: UploadPageText[];
  /** Paragraph-level extracted text with page associations. */
  paragraphs: UploadParagraph[];
  /** Extracted operative section text, if identified. */
  operative_section: string | null;
  /** Structured case metadata extracted from the PDF. */
  zones: ExtractedZones;
  /** Full structured action plan generated for this judgment. */
  action_plan: ActionPlan;
  /** Optional field-level evidence used to drive the review UI. */
  field_evidence?: Partial<Record<string, ExtractedFieldEvidence>>;
  /** PDF page dimensions used for overlay rendering. */
  page_dimensions: PageDimensions[];
}

/**
 * Standard API error shape used across frontend calls and route handlers.
 */
export interface ApiError {
  /** Human-readable error message intended for UI display. */
  message: string;
  /** HTTP status code associated with the error. */
  status: number;
}

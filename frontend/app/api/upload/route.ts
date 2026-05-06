import { NextResponse } from "next/server";
import type {
  ActionNature,
  ActionPlanItem,
  ReviewStatus,
  UploadResponse,
} from "@/types";

const FASTAPI_BASE_URL = (
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 60_000;

interface UploadRouteError {
  error: string;
  message: string;
  status: number;
}

interface CombinedUploadResponse {
  uploadResponse: UploadResponse;
  actionItems: ActionPlanItem[];
}

interface FastApiErrorPayload {
  detail?: string;
  message?: string;
  error?: string;
}

interface ArbitrationFieldPayload {
  final_value?: string | null;
  confidence?: number;
}

interface RagOutputPayload {
  directives?: unknown;
  responsible_departments?: unknown;
  deadlines?: unknown;
  Action_Plan?: {
    Nature_of_Action?: string;
    Compliance_Required?: string | string[];
    Responsible_Departments?: string | string[];
    Key_Timelines?: string | string[];
  };
}

interface FastApiUploadPayload {
  status?: string;
  document_id?: string;
  header_metadata?: {
    Name_of_the_judge?: string;
    Date_of_order?: string;
    Petitioners?: string[];
    Respondents?: string[];
  };
  arbitration_results?: Record<string, ArbitrationFieldPayload>;
  rag_output?: Record<string, unknown>;
  regex_output?: Record<string, unknown>;
  created_at?: string;
}

function normalizeHeaderValue(value: string | undefined): string | null {
  if (!value || !value.trim()) return null;
  const trimmed = value.trim();
  const invalidValues = ["not specified", "not available", "n/a", "na", "none", "null"];
  if (invalidValues.includes(trimmed.toLowerCase())) return null;
  return trimmed;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function normalizeRagFieldValue(value: unknown): string | null {
  if (isNonEmptyString(value)) {
    const trimmed = value.trim();
    // Treat "not available", "n/a", etc. as invalid
    const invalidValues = ["not available", "n/a", "na", "none", "null", ""];
    if (invalidValues.includes(trimmed.toLowerCase())) {
      return null;
    }
    return trimmed;
  }

  if (Array.isArray(value)) {
    const normalized = value
      .filter(isNonEmptyString)
      .map((item) => item.trim())
      .filter((item) => {
        const invalidValues = ["not available", "n/a", "na", "none", "null"];
        return !invalidValues.includes(item.toLowerCase());
      });
    return normalized.length > 0 ? normalized.join(", ") : null;
  }

  if (typeof value === "object" && value !== null) {
    const candidate = (value as { value?: unknown }).value;
    if (isNonEmptyString(candidate)) {
      const trimmed = candidate.trim();
      const invalidValues = ["not available", "n/a", "na", "none", "null", ""];
      if (invalidValues.includes(trimmed.toLowerCase())) {
        return null;
      }
      return trimmed;
    }
  }

  return null;
}

function getHybridValue(
  ragOutput: Record<string, unknown> | undefined,
  arbitrationResults: Record<string, ArbitrationFieldPayload> | undefined,
  key: string,
): string | null {
  const ragValue = normalizeRagFieldValue(ragOutput?.[key]);
  return ragValue ?? getArbitrationValue(arbitrationResults, key);
}

function getHybridBench(
  ragOutput: Record<string, unknown> | undefined,
  arbitrationResults: Record<string, ArbitrationFieldPayload> | undefined,
): string[] {
  const benchValue = getHybridValue(ragOutput, arbitrationResults, "bench");
  return benchValue
    ? benchValue.split(",").map((item) => item.trim()).filter(Boolean)
    : [];
}

function buildBackendUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (FASTAPI_BASE_URL.endsWith("/api")) {
    return `${FASTAPI_BASE_URL}${normalizedPath}`;
  }

  return `${FASTAPI_BASE_URL}/api${normalizedPath}`;
}

function toErrorResponse(
  message: string,
  status: number,
): NextResponse<UploadRouteError> {
  return NextResponse.json(
    {
      error: message,
      message,
      status,
    },
    { status },
  );
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
      cache: "no-store",
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

async function getUpstreamError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as FastApiErrorPayload;
    return (
      payload.message ??
      payload.detail ??
      payload.error ??
      response.statusText ??
      "Upstream request failed"
    );
  } catch {
    return response.statusText || "Upstream request failed";
  }
}

function getArbitrationValue(
  arbitrationResults: Record<string, ArbitrationFieldPayload> | undefined,
  key: string,
): string | null {
  const value = arbitrationResults?.[key]?.final_value;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function getBench(arbitrationResults: Record<string, ArbitrationFieldPayload> | undefined): string[] {
  const value = getArbitrationValue(arbitrationResults, "bench");
  return value ? [value] : [];
}

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string");
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return [value];
  }

  return [];
}

function normalizeNature(value: string | undefined): ActionNature {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("appeal")) {
    return "Appeal";
  }
  if (normalized.includes("advis")) {
    return "Advisory";
  }
  return "Compliance";
}

function normalizeReviewStatus(value: unknown): ReviewStatus {
  return value === "approved" ||
    value === "edited" ||
    value === "rejected"
    ? value
    : "unreviewed";
}

function normalizeUploadResponse(
  payload: FastApiUploadPayload,
  filename: string,
): UploadResponse {
  const arbitrationResults = payload.arbitration_results;
  const ragOutput = payload.rag_output;
  const headerMetadata = payload.header_metadata;

  return {
    doc_id:
      typeof payload.document_id === "string" ? payload.document_id : "",
    filename,
    page_texts: [],
    paragraphs: [],
    operative_section: null,
    zones: {
      case_number: getHybridValue(ragOutput, arbitrationResults, "case_number"),
      case_type: getHybridValue(ragOutput, arbitrationResults, "case_type"),
      judgment_date: normalizeHeaderValue(headerMetadata?.Date_of_order) ?? getHybridValue(ragOutput, arbitrationResults, "judgment_date"),
      bench: normalizeHeaderValue(headerMetadata?.Name_of_the_judge)
        ? [normalizeHeaderValue(headerMetadata?.Name_of_the_judge) as string]
        : getHybridBench(ragOutput, arbitrationResults),
      petitioner: (headerMetadata?.Petitioners && headerMetadata.Petitioners.length > 0 ? headerMetadata.Petitioners.join(", ") : null) ?? getHybridValue(ragOutput, arbitrationResults, "petitioner"),
      respondent: (headerMetadata?.Respondents && headerMetadata.Respondents.length > 0 ? headerMetadata.Respondents.join(", ") : null) ?? getHybridValue(ragOutput, arbitrationResults, "respondent"),
    },
    page_dimensions: [],
  };
}

function normalizeActionItems(
  payload: FastApiUploadPayload,
  docId: string,
): ActionPlanItem[] {
  const ragOutput = payload.rag_output ?? {};
  const actionPlan = (ragOutput?.Action_Plan ?? {}) as {
    Nature_of_Action?: string;
    Compliance_Required?: string | string[];
    Responsible_Departments?: string | string[];
    Key_Timelines?: string | string[];
  };
  let directives = asStringList((ragOutput as Record<string, unknown>).directives);
  if (directives.length === 0) {
    directives = asStringList(actionPlan?.Compliance_Required);
  }

  const departments =
    asStringList(ragOutput.responsible_departments).length > 0
      ? asStringList(ragOutput.responsible_departments)
      : asStringList(actionPlan?.Responsible_Departments);
  const deadlines =
    asStringList(ragOutput.deadlines).length > 0
      ? asStringList(ragOutput.deadlines)
      : asStringList(actionPlan?.Key_Timelines);
  const nature = normalizeNature(actionPlan?.Nature_of_Action);

  return directives.map((directive, index) => ({
    itemId: `${docId}-action-${index + 1}`,
    directive,
    department:
      departments[index] ?? departments[0] ?? "Not specified",
    deadline: deadlines[index] ?? null,
    deadline_type: deadlines[index] ? "explicit" : "inferred",
    nature,
    confidence: 0.8,
    review_status: "unreviewed",
  }));
}

export async function POST(request: Request): Promise<Response> {
  try {
    const incomingFormData = await request.formData();
    const file = incomingFormData.get("file");

    if (!(file instanceof File)) {
      return toErrorResponse("Missing required 'file' field", 400);
    }

    const uploadFormData = new FormData();
    uploadFormData.append("file", file, file.name);

    const uploadResponse = await fetchWithTimeout(buildBackendUrl("/upload"), {
      method: "POST",
      body: uploadFormData,
    });

    if (!uploadResponse.ok) {
      const message = await getUpstreamError(uploadResponse);
      return toErrorResponse(message, uploadResponse.status);
    }

    const uploadPayload = (await uploadResponse.json()) as FastApiUploadPayload;
    const normalizedUploadResponse = normalizeUploadResponse(
      uploadPayload,
      file.name,
    );

    if (!normalizedUploadResponse.doc_id) {
      return toErrorResponse(
        "Upload succeeded, but no document ID was returned.",
        502,
      );
    }

    const combinedResponse: CombinedUploadResponse = {
      uploadResponse: normalizedUploadResponse,
      actionItems: normalizeActionItems(
        uploadPayload,
        normalizedUploadResponse.doc_id,
      ),
    };

    return NextResponse.json(combinedResponse, { status: 200 });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return toErrorResponse("Upload processing timed out after 60 seconds", 504);
    }

    const message =
      error instanceof Error ? error.message : "Unexpected upload proxy error";

    return toErrorResponse(message, 500);
  }
}

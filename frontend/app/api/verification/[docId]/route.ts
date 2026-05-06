import { NextResponse } from "next/server";
import type { ActionNature, ActionPlanItem, ApiError, ReviewStatus, UploadResponse } from "@/types";

const FASTAPI_BASE_URL = (
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

interface VerificationPayload {
  status?: string;
  document_id?: string;
  header_metadata?: {
    Name_of_the_judge?: string;
    Date_of_order?: string;
    Petitioners?: string[];
    Respondents?: string[];
  };
  created_at?: string;
  arbitration_results?: Record<
    string,
    {
      final_value?: string | null;
      confidence?: number;
      state?: string;
      regex_value?: string | null;
      rag_value?: string | null;
    }
  >;
  rag_output?: Record<string, unknown>;
}

interface VerificationDetailResponse {
  uploadResponse: UploadResponse;
  actionItems: ActionPlanItem[];
  upload_date: string | null;
}

interface VerificationRequestBody {
  reviewer?: string;
  reviewed_at?: string;
  fields?: unknown[];
  action_items?: unknown[];
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
): NextResponse<ApiError> {
  return NextResponse.json({ message, status }, { status });
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

function getArbitrationValue(
  arbitrationResults: VerificationPayload["arbitration_results"],
  key: string,
): string | null {
  const value = arbitrationResults?.[key]?.final_value;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function getHybridValue(
  ragOutput: Record<string, unknown> | undefined,
  arbitrationResults: VerificationPayload["arbitration_results"],
  key: string,
): string | null {
  const ragValue = normalizeRagFieldValue(ragOutput?.[key]);
  return ragValue ?? getArbitrationValue(arbitrationResults, key);
}

function getHybridBench(
  ragOutput: Record<string, unknown> | undefined,
  arbitrationResults: VerificationPayload["arbitration_results"],
): string[] {
  const benchValue = getHybridValue(ragOutput, arbitrationResults, "bench");
  return benchValue
    ? benchValue.split(",").map((item) => item.trim()).filter(Boolean)
    : [];
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

function buildUploadResponse(
  docId: string,
  payload: VerificationPayload,
): UploadResponse {
  const arbitrationResults = payload.arbitration_results;
  const ragOutput = payload.rag_output;
  const headerMetadata = payload.header_metadata;
  return {
    doc_id: docId,
    filename: "Uploaded judgment",
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

function buildActionItems(
  docId: string,
  payload: VerificationPayload,
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
    department: departments[index] ?? departments[0] ?? "Not specified",
    deadline: deadlines[index] ?? null,
    deadline_type: deadlines[index] ? "explicit" : "inferred",
    nature,
    confidence: 0.8,
    review_status: normalizeReviewStatus(undefined),
  }));
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ docId: string }> },
): Promise<Response> {
  try {
    const { docId } = await context.params;

    if (!docId) {
      return toErrorResponse("docId is required", 400);
    }

    const upstreamResponse = await fetch(
      buildBackendUrl(`/verify/${encodeURIComponent(docId)}`),
      {
        method: "GET",
        cache: "no-store",
      },
    );

    const responseBody = await upstreamResponse.text();

    if (!upstreamResponse.ok) {
      try {
        const parsed = JSON.parse(responseBody) as {
          detail?: string;
          message?: string;
        };

        return toErrorResponse(
          parsed.message ?? parsed.detail ?? "Verification proxy request failed",
          upstreamResponse.status,
        );
      } catch {
        return toErrorResponse(
          responseBody || "Verification proxy request failed",
          upstreamResponse.status,
        );
      }
    }

    const payload = JSON.parse(responseBody) as VerificationPayload;
    const detailResponse: VerificationDetailResponse = {
      uploadResponse: buildUploadResponse(docId, payload),
      actionItems: buildActionItems(docId, payload),
      upload_date:
        typeof payload.created_at === "string" ? payload.created_at : null,
    };

    return NextResponse.json(detailResponse, { status: 200 });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unexpected verification proxy error";

    return toErrorResponse(message, 500);
  }
}

export async function POST(
  request: Request,
  context: { params: Promise<{ docId: string }> },
): Promise<Response> {
  try {
    const { docId } = await context.params;
    const payload = (await request.json()) as VerificationRequestBody;

    if (!docId) {
      return toErrorResponse("docId is required", 400);
    }

    if (!payload.reviewer || !payload.reviewed_at) {
      return toErrorResponse("Invalid verification payload", 400);
    }

    const upstreamPayload = {
      field_decisions: {},
      reviewed_by: payload.reviewer,
      notes: "",
    };

    const upstreamResponse = await fetch(
      buildBackendUrl(`/verify/${encodeURIComponent(docId)}/approve`),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(upstreamPayload),
      },
    );

    if (!upstreamResponse.ok) {
      const responseBody = await upstreamResponse.text();
      try {
        const parsed = JSON.parse(responseBody) as {
          detail?: string;
          message?: string;
        };
        return toErrorResponse(
          parsed.message ?? parsed.detail ?? "Verification submit failed",
          upstreamResponse.status,
        );
      } catch {
        return toErrorResponse(
          responseBody || "Verification submit failed",
          upstreamResponse.status,
        );
      }
    }

    return new Response(null, { status: 204 });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unexpected verification proxy error";

    return toErrorResponse(message, 500);
  }
}

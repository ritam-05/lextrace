import { NextResponse } from "next/server";
import type {
  ActionPlan,
  ApiError,
  ExtractedFieldEvidence,
  UploadResponse,
} from "@/types";

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
  regex_output?: Record<string, unknown>;
}

function getRegexFieldEvidence(
  regexOutput: Record<string, unknown> | undefined,
  key: string,
): ExtractedFieldEvidence | undefined {
  const candidate = regexOutput?.[key];
  if (!candidate || typeof candidate !== "object") {
    return undefined;
  }

  const payload = candidate as {
    confidence?: unknown;
    source?: { page?: unknown };
  };

  const confidence =
    typeof payload.confidence === "number" ? payload.confidence : undefined;
  const sourcePage =
    typeof payload.source?.page === "number" ? payload.source.page : null;

  if (confidence === undefined && sourcePage === null) {
    return undefined;
  }

  return {
    confidence: confidence ?? 0,
    source_page: sourcePage,
  };
}

interface VerificationDetailResponse {
  uploadResponse: UploadResponse;
  upload_date: string | null;
}

interface VerificationRequestBody {
  reviewer?: string;
  reviewed_at?: string;
  fields?: unknown[];
  action_plan?: unknown;
}

function buildFieldDecisions(fields: unknown[] | undefined): Record<string, { approved: boolean; edited_value?: string | null }> {
  if (!Array.isArray(fields)) {
    return {};
  }

  return fields.reduce<Record<string, { approved: boolean; edited_value?: string | null }>>((accumulator, item) => {
    if (typeof item !== "object" || item === null) {
      return accumulator;
    }

    const field = item as {
      fieldId?: unknown;
      review_status?: unknown;
      edited_value?: unknown;
      value?: unknown;
    };

    if (typeof field.fieldId !== "string") {
      return accumulator;
    }

    const status = typeof field.review_status === "string" ? field.review_status : "";
    const editedValue = typeof field.edited_value === "string" ? field.edited_value : null;
    const fallbackValue = typeof field.value === "string" ? field.value : null;

    if (status === "approved") {
      accumulator[field.fieldId] = {
        approved: true,
        edited_value: null,
      };
    } else if (status === "edited") {
      accumulator[field.fieldId] = {
        approved: true,
        edited_value: editedValue ?? fallbackValue,
      };
    } else if (status === "rejected") {
      accumulator[field.fieldId] = {
        approved: false,
        edited_value: editedValue,
      };
    }

    return accumulator;
  }, {});
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

function getRegexValue(
  regexOutput: Record<string, unknown> | undefined,
  key: string,
): string | null {
  const candidate = regexOutput?.[key];
  return normalizeRagFieldValue(candidate);
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

function normalizeForTimelineMatch(value: string): string {
  return value.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
}

function inferTimelineStepIndex(
  timelineText: string,
  complianceSteps: string[],
): number | undefined {
  const normalizedTimeline = normalizeForTimelineMatch(timelineText);
  if (!normalizedTimeline) {
    return undefined;
  }

  const matchIndex = complianceSteps.findIndex((stepText) =>
    normalizeForTimelineMatch(stepText).includes(normalizedTimeline),
  );

  return matchIndex >= 0 ? matchIndex + 1 : undefined;
}

interface RagSourceChunk {
  page?: number | null;
  text?: string;
}

function normalizeSourceChunks(value: unknown): RagSourceChunk[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Record<string, unknown> =>
      typeof item === "object" && item !== null,
    )
    .map((item) => ({
      page: typeof item.page === "number" ? item.page : null,
      text: typeof item.text === "string" ? item.text : "",
    }));
}

function normalizeSourcePages(value: unknown): number[] {
  return Array.isArray(value)
    ? value.filter((item): item is number => typeof item === "number")
    : [];
}

function getTokenSet(value: string): Set<string> {
  return new Set(
    normalizeForTimelineMatch(value)
      .split(" ")
      .filter((token) => token.length >= 4),
  );
}

function inferRagSourcePage(
  text: string,
  sourceChunks: RagSourceChunk[],
  fallbackPages: number[],
): number | undefined {
  const queryTokens = getTokenSet(text);
  let bestPage: number | undefined;
  let bestScore = 0;

  for (const chunk of sourceChunks) {
    if (typeof chunk.page !== "number" || !chunk.text) {
      continue;
    }

    const chunkTokens = getTokenSet(chunk.text);
    let sharedTokens = 0;
    for (const token of queryTokens) {
      if (chunkTokens.has(token)) {
        sharedTokens += 1;
      }
    }

    if (sharedTokens > bestScore) {
      bestScore = sharedTokens;
      bestPage = chunk.page;
    }
  }

  return bestPage ?? fallbackPages[0];
}

function buildUploadResponse(
  docId: string,
  payload: VerificationPayload,
): UploadResponse {
  const arbitrationResults = payload.arbitration_results;
  const ragOutput = payload.rag_output;
  const regexOutput = payload.regex_output;
  const headerMetadata = payload.header_metadata;
  return {
    doc_id: docId,
    filename: "Uploaded judgment",
    page_texts: [],
    paragraphs: [],
    operative_section: null,
    zones: {
      case_number: getHybridValue(ragOutput, arbitrationResults, "case_number"),
      case_type: getHybridValue(ragOutput, arbitrationResults, "case_type")
        ?? getRegexValue(regexOutput, "case_type"),
      judgment_date: normalizeHeaderValue(headerMetadata?.Date_of_order) ?? getHybridValue(ragOutput, arbitrationResults, "judgment_date"),
      bench: normalizeHeaderValue(headerMetadata?.Name_of_the_judge)
        ? [normalizeHeaderValue(headerMetadata?.Name_of_the_judge) as string]
        : getHybridBench(ragOutput, arbitrationResults),
      petitioner: (headerMetadata?.Petitioners && headerMetadata.Petitioners.length > 0 ? headerMetadata.Petitioners.join(", ") : null) ?? getHybridValue(ragOutput, arbitrationResults, "petitioner"),
      respondent: (headerMetadata?.Respondents && headerMetadata.Respondents.length > 0 ? headerMetadata.Respondents.join(", ") : null) ?? getHybridValue(ragOutput, arbitrationResults, "respondent"),
    },
    action_plan: buildActionPlan(payload),
    field_evidence: {
      case_type: getRegexFieldEvidence(regexOutput, "case_type"),
    },
    page_dimensions: [],
  };
}

function buildActionPlan(payload: VerificationPayload): ActionPlan {
  const ragOutput = payload.rag_output as {
    Extraction?: {
      Key_Directions?: string[];
    };
    Action_Plan?: {
      Compliance_Required?: string[];
      Key_Timelines?: string[];
      Responsible_Departments?: string[];
      Nature_of_Action?: string;
      Consideration_for_Appeal?: string;
      Appeal_Justification?: string[];
      Appeal_Risk_Score?: number;
      LLM_Context?: string;
    };
    RAG_Source_Pages?: unknown;
    RAG_Source_Chunks?: unknown;
  } | undefined;

  const ragExtraction = ragOutput?.Extraction ?? {};
  const ragPlan = ragOutput?.Action_Plan ?? {};
  const complianceSteps = ragPlan.Compliance_Required ?? [];
  const sourcePages = normalizeSourcePages(ragOutput?.RAG_Source_Pages);
  const sourceChunks = normalizeSourceChunks(ragOutput?.RAG_Source_Chunks);

  return {
    key_directions: (ragExtraction.Key_Directions ?? []).map((text, index) => ({
      id: `dir_${index}`,
      text,
      source_page: inferRagSourcePage(text, sourceChunks, sourcePages),
      review_status: "unreviewed",
    })),
    compliance_steps: complianceSteps.map((text, index) => ({
      id: `comp_${index}`,
      text,
      source_page: inferRagSourcePage(text, sourceChunks, sourcePages),
      review_status: "unreviewed",
    })),
    timelines: (ragPlan.Key_Timelines ?? []).map((text, index) => ({
      id: `tl_${index}`,
      text,
      source_page: inferRagSourcePage(text, sourceChunks, sourcePages),
      related_step_index: inferTimelineStepIndex(text, complianceSteps),
      review_status: "unreviewed",
    })),
    responsible_departments: (ragPlan.Responsible_Departments ?? []).filter(
      (department) => department && department !== "Not Specified",
    ),
    nature_of_action: ragPlan.Nature_of_Action ?? "",
    appeal_analysis: {
      consideration: ragPlan.Consideration_for_Appeal ?? "LOW",
      justification: ragPlan.Appeal_Justification ?? [],
      risk_score: ragPlan.Appeal_Risk_Score ?? 0,
    },
    llm_context: ragPlan.LLM_Context ?? "",
  };
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
      field_decisions: buildFieldDecisions(payload.fields),
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

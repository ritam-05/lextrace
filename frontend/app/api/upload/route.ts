import { NextResponse } from "next/server";
import type {
  ActionPlan,
  ExtractedFieldEvidence,
  UploadResponse,
} from "@/types";

const FASTAPI_BASE_URL = (
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 300_000;

export const maxDuration = 300;

interface UploadRouteError {
  error: string;
  message: string;
  status: number;
}

interface CombinedUploadResponse {
  uploadResponse: UploadResponse;
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

function getRegexValue(
  regexOutput: Record<string, unknown> | undefined,
  key: string,
): string | null {
  const candidate = regexOutput?.[key];
  return normalizeRagFieldValue(candidate);
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

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string");
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return [value];
  }

  return [];
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

function normalizeUploadResponse(
  payload: FastApiUploadPayload,
  filename: string,
): UploadResponse {
  const arbitrationResults = payload.arbitration_results;
  const ragOutput = payload.rag_output;
  const regexOutput = payload.regex_output;
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
      case_type: getHybridValue(ragOutput, arbitrationResults, "case_type")
        ?? getRegexValue(regexOutput, "case_type"),
      judgment_date: normalizeHeaderValue(headerMetadata?.Date_of_order) ?? getHybridValue(ragOutput, arbitrationResults, "judgment_date"),
      bench: normalizeHeaderValue(headerMetadata?.Name_of_the_judge)
        ? [normalizeHeaderValue(headerMetadata?.Name_of_the_judge) as string]
        : getHybridBench(ragOutput, arbitrationResults),
      petitioner: (headerMetadata?.Petitioners && headerMetadata.Petitioners.length > 0 ? headerMetadata.Petitioners.join(", ") : null) ?? getHybridValue(ragOutput, arbitrationResults, "petitioner"),
      respondent: (headerMetadata?.Respondents && headerMetadata.Respondents.length > 0 ? headerMetadata.Respondents.join(", ") : null) ?? getHybridValue(ragOutput, arbitrationResults, "respondent"),
    },
    action_plan: normalizeActionPlan(payload),
    field_evidence: {
      case_type: getRegexFieldEvidence(regexOutput, "case_type"),
    },
    page_dimensions: [],
  };
}

function normalizeActionPlan(payload: FastApiUploadPayload): ActionPlan {
  const ragOutput = payload.rag_output as {
    Extraction?: {
      Key_Directions?: string[];
    };
    Action_Plan?: {
      Compliance_Section?: string[];
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
  const complianceSection = ragPlan.Compliance_Section ?? [];
  const complianceSteps = ragPlan.Compliance_Required ?? [];
  const sourcePages = normalizeSourcePages(ragOutput?.RAG_Source_Pages);
  const sourceChunks = normalizeSourceChunks(ragOutput?.RAG_Source_Chunks);

  const action_plan: ActionPlan = {
    compliance_section: complianceSection,

    key_directions: (ragExtraction.Key_Directions ?? [])
      .map((text: string, i: number) => ({
        id: `dir_${i}`,
        text,
        source_page: inferRagSourcePage(text, sourceChunks, sourcePages),
        review_status: "unreviewed",
      })),

    compliance_steps: complianceSteps
      .map((text: string, i: number) => ({
        id: `comp_${i}`,
        text,
        source_page: inferRagSourcePage(text, sourceChunks, sourcePages),
        review_status: "unreviewed",
      })),

    timelines: (ragPlan.Key_Timelines ?? [])
      .map((text: string, i: number) => ({
        id: `tl_${i}`,
        text,
        source_page: inferRagSourcePage(text, sourceChunks, sourcePages),
        related_step_index: inferTimelineStepIndex(text, complianceSteps),
        review_status: "unreviewed",
      })),

    responsible_departments:
      (ragPlan.Responsible_Departments ?? [])
        .filter((department: string) => department && department !== "Not Specified"),

    nature_of_action: ragPlan.Nature_of_Action ?? "",

    appeal_analysis: {
      consideration:
        ragPlan.Consideration_for_Appeal ?? "LOW",
      justification:
        ragPlan.Appeal_Justification ?? [],
      risk_score:
        ragPlan.Appeal_Risk_Score ?? 0,
    },

    llm_context: ragPlan.LLM_Context ?? "",
  };

  return action_plan;
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
    };

    return NextResponse.json(combinedResponse, { status: 200 });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return toErrorResponse("Upload processing timed out after 5 minutes", 504);
    }

    const message =
      error instanceof Error ? error.message : "Unexpected upload proxy error";

    return toErrorResponse(message, 500);
  }
}

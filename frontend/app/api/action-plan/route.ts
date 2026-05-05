import { NextResponse } from "next/server";
import type { ActionPlanItem, ApiError } from "@/types";

const FASTAPI_BASE_URL = (
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 60_000;

interface ActionPlanRequestBody {
  docId?: string;
  text?: string;
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

export async function POST(request: Request): Promise<Response> {
  try {
    const body = (await request.json()) as ActionPlanRequestBody;

    if (
      typeof body.docId !== "string" ||
      body.docId.trim().length === 0 ||
      typeof body.text !== "string" ||
      body.text.trim().length === 0
    ) {
      return toErrorResponse("docId and text are required", 400);
    }

    const response = await fetchWithTimeout(buildBackendUrl("/rag-test"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        doc_id: body.docId,
        text: body.text,
      }),
    });

    if (!response.ok) {
      let message = response.statusText || "Backend action plan request failed";
      try {
        const payload = (await response.json()) as Partial<ApiError> & {
          detail?: string;
          error?: string;
        };
        message =
          payload.message ??
          payload.detail ??
          payload.error ??
          message;
      } catch {
        // Preserve fallback message if the backend response is not JSON.
      }

      return toErrorResponse(message, response.status);
    }

    const payload = (await response.json()) as ActionPlanItem[];
    return NextResponse.json<ActionPlanItem[]>(payload, { status: 200 });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return toErrorResponse("Action plan processing timed out after 60 seconds", 504);
    }

    const message =
      error instanceof Error ? error.message : "Unexpected action plan error";

    return toErrorResponse(message, 500);
  }
}

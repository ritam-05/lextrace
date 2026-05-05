import { NextResponse } from "next/server";
import type { ApiError } from "@/types";

const FASTAPI_BASE_URL = (
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

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
      buildBackendUrl(`/documents/${encodeURIComponent(docId)}`),
      {
        method: "GET",
        cache: "no-store",
      },
    );

    const contentType =
      upstreamResponse.headers.get("content-type") ?? "application/json";
    const responseBody = await upstreamResponse.text();

    if (!upstreamResponse.ok) {
      try {
        const parsed = JSON.parse(responseBody) as {
          detail?: string;
          message?: string;
        };

        return toErrorResponse(
          parsed.message ??
            parsed.detail ??
            "Document detail proxy request failed",
          upstreamResponse.status,
        );
      } catch {
        return toErrorResponse(
          responseBody || "Document detail proxy request failed",
          upstreamResponse.status,
        );
      }
    }

    return new Response(responseBody, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type": contentType,
      },
    });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unexpected document detail proxy error";

    return toErrorResponse(message, 500);
  }
}

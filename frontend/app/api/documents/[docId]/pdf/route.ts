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
      buildBackendUrl(`/documents/${encodeURIComponent(docId)}/pdf`),
      {
        method: "GET",
        cache: "no-store",
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
          parsed.message ?? parsed.detail ?? "Document PDF proxy request failed",
          upstreamResponse.status,
        );
      } catch {
        return toErrorResponse(
          responseBody || "Document PDF proxy request failed",
          upstreamResponse.status,
        );
      }
    }

    const pdfBytes = await upstreamResponse.arrayBuffer();
    return new Response(pdfBytes, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition":
          upstreamResponse.headers.get("content-disposition") ?? "inline",
      },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unexpected document PDF proxy error";

    return toErrorResponse(message, 500);
  }
}

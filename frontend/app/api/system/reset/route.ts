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

export async function POST(): Promise<Response> {
  try {
    const upstreamResponse = await fetch(buildBackendUrl("/admin/reset"), {
      method: "POST",
      cache: "no-store",
    });

    const responseBody = await upstreamResponse.text();

    if (!upstreamResponse.ok) {
      try {
        const parsed = JSON.parse(responseBody) as {
          detail?: string;
          message?: string;
        };

        return toErrorResponse(
          parsed.message ?? parsed.detail ?? "Reset proxy request failed",
          upstreamResponse.status,
        );
      } catch {
        return toErrorResponse(
          responseBody || "Reset proxy request failed",
          upstreamResponse.status,
        );
      }
    }

    return new Response(responseBody, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type": upstreamResponse.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unexpected reset proxy error";

    return toErrorResponse(message, 500);
  }
}

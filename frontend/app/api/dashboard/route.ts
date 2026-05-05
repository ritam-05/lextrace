import { NextResponse } from "next/server";
import type { ApiError } from "@/types";

export const dynamic = "force-dynamic";

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

export async function GET(request: Request): Promise<Response> {
  try {
    const url = new URL(request.url);
    const status = url.searchParams.get("status") ?? "verified";
    const backendUrl = new URL(buildBackendUrl("/documents"));
    backendUrl.searchParams.set("status", status);

    const upstreamResponse = await fetch(
      backendUrl,
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
          parsed.message ?? parsed.detail ?? "Dashboard proxy request failed",
          upstreamResponse.status,
        );
      } catch {
        return toErrorResponse(
          responseBody || "Dashboard proxy request failed",
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
        : "Unexpected dashboard proxy error";

    return toErrorResponse(message, 500);
  }
}

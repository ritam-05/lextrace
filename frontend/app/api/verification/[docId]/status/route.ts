import { NextResponse } from "next/server";
import type { ApiError, DocumentStatus } from "@/types";

interface StatusPayload {
  status?: DocumentStatus;
}

function toErrorResponse(
  message: string,
  status: number,
): NextResponse<ApiError> {
  return NextResponse.json({ message, status }, { status });
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ docId: string }> },
): Promise<Response> {
  try {
    const { docId } = await context.params;
    const body = (await request.json()) as StatusPayload;

    if (!docId) {
      return toErrorResponse("docId is required", 400);
    }

    if (
      body.status !== "processing" &&
      body.status !== "pending_review" &&
      body.status !== "verified"
    ) {
      return toErrorResponse("Invalid status value", 400);
    }

    return new Response(null, {
      status: 501,
      statusText: "Not Implemented",
      headers: {
        "X-Stub-Reason": "Verification status endpoint not yet wired",
      },
    });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unexpected verification status proxy error";

    return toErrorResponse(message, 500);
  }
}

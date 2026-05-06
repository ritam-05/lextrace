import type {
  ActionPlan,
  ApiError,
  DocumentStatus,
  JudgmentDocument,
  UploadResponse,
  VerificationPayload,
} from "@/types";

interface UploadProxyResponse {
  uploadResponse: UploadResponse;
}

const REQUEST_TIMEOUT_MS = 30_000;

async function parseError(response: Response): Promise<ApiError> {
  try {
    const data = (await response.json()) as Partial<ApiError> & {
      detail?: string;
      error?: string;
    };

    return {
      message:
        data.message ??
        data.detail ??
        data.error ??
        response.statusText ??
        "Request failed",
      status: response.status,
    };
  } catch {
    return {
      message: response.statusText || "Request failed",
      status: response.status,
    };
  }
}

async function request<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(input, {
      ...init,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw await parseError(response);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw {
        message: "Request timed out after 30 seconds",
        status: 408,
      } satisfies ApiError;
    }

    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadDocument(file: File): Promise<UploadProxyResponse> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  return request<UploadProxyResponse>("/api/upload", {
    method: "POST",
    body: formData,
  });
}

export async function generateActionPlan(
  docId: string,
  text: string,
): Promise<ActionPlan> {
  return request<ActionPlan>("/api/action-plan", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ docId, text }),
  });
}

export async function getDocuments(): Promise<JudgmentDocument[]> {
  return request<JudgmentDocument[]>("/api/documents", {
    method: "GET",
  });
}

export async function getDocument(
  docId: string,
): Promise<JudgmentDocument> {
  return request<JudgmentDocument>(
    `/api/documents/${encodeURIComponent(docId)}`,
    {
      method: "GET",
    },
  );
}

export async function submitVerification(
  docId: string,
  payload: VerificationPayload,
): Promise<void> {
  await request<void>(`/api/verification/${encodeURIComponent(docId)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function getDashboardData(): Promise<JudgmentDocument[]> {
  return request<JudgmentDocument[]>("/api/dashboard", {
    method: "GET",
  });
}

export async function updateActionStatus(
  docId: string,
  status: DocumentStatus,
): Promise<void> {
  await request<void>(
    `/api/verification/${encodeURIComponent(docId)}/status`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status }),
    },
  );
}

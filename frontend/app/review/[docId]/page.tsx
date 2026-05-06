import { headers } from "next/headers";

import ReviewClient from "./ReviewClient";
import type { UploadResponse } from "@/types";


interface ReviewPageProps {
  params: Promise<{
    docId: string;
  }>;
}


interface VerificationDetailResponse {
  uploadResponse: UploadResponse;
  upload_date: string | null;
}


async function getBaseUrl(): Promise<string> {
  if (process.env.NEXT_PUBLIC_APP_URL) {
    return process.env.NEXT_PUBLIC_APP_URL;
  }

  const headerStore = await headers();
  const host = headerStore.get("host") ?? "localhost:3000";
  const protocol =
    headerStore.get("x-forwarded-proto") ??
    (host.includes("localhost") || host.startsWith("127.0.0.1") ? "http" : "https");

  return `${protocol}://${host}`;
}


async function getInitialReviewData(docId: string): Promise<{
  uploadResponse: UploadResponse | null;
  uploadedAt: string | null;
}> {
  try {
    const baseUrl = await getBaseUrl();
    const response = await fetch(
      `${baseUrl}/api/verification/${encodeURIComponent(docId)}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return {
        uploadResponse: null,
        uploadedAt: null,
      };
    }

    const payload = (await response.json()) as Partial<VerificationDetailResponse>;

    return {
      uploadResponse: payload.uploadResponse ?? null,
      uploadedAt:
        typeof payload.upload_date === "string" ? payload.upload_date : null,
    };
  } catch {
    return {
      uploadResponse: null,
      uploadedAt: null,
    };
  }
}


export default async function ReviewPage({ params }: ReviewPageProps) {
  const { docId } = await params;
  const initialData = await getInitialReviewData(docId);

  return (
    <ReviewClient
      docId={docId}
      initialUploadResponse={initialData.uploadResponse}
      initialUploadedAt={initialData.uploadedAt}
    />
  );
}

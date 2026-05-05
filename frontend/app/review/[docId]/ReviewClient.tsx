"use client";

import { useEffect, useMemo, useState } from "react";

import FieldPanel from "@/components/review/FieldPanel";
import PdfViewer from "@/components/review/PdfViewer";
import SplitPane from "@/components/review/SplitPane";
import { useReviewStore } from "@/store/reviewStore";
import type { ActionPlanItem, ReviewField, UploadResponse } from "@/types";

interface ReviewSessionPayload {
  uploadResponse: UploadResponse;
  actionItems: ActionPlanItem[];
  uploadedAt: string;
}

interface ReviewClientProps {
  docId: string;
  initialUploadResponse: UploadResponse | null;
  initialActionItems: ActionPlanItem[];
  initialUploadedAt: string | null;
}

function deriveReviewFields(uploadResponse: UploadResponse): ReviewField[] {
  const zones = uploadResponse.zones;
  const defaultPage =
    uploadResponse.paragraphs[0]?.page ?? uploadResponse.page_texts[0]?.page ?? 1;

  const defaultConfidence = 0.75;

  return [
    {
      fieldId: "case_number",
      label: "Case Number",
      value: zones.case_number,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
    {
      fieldId: "case_type",
      label: "Case Type",
      value: zones.case_type,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
    {
      fieldId: "judgment_date",
      label: "Judgment Date",
      value: zones.judgment_date,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
    {
      fieldId: "court_name",
      label: "Court Name",
      value: zones.court_name,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
    {
      fieldId: "bench",
      label: "Bench",
      value: zones.bench.length > 0 ? zones.bench.join(", ") : null,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
    {
      fieldId: "petitioner",
      label: "Petitioner",
      value: zones.petitioner,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
    {
      fieldId: "respondent",
      label: "Respondent",
      value: zones.respondent,
      confidence: defaultConfidence,
      source_page: defaultPage,
      source_bbox: null,
      review_status: "unreviewed",
    },
  ];
}

function RightPanel({
  pdfDataUrl,
  uploadResponse,
}: {
  pdfDataUrl: string | null;
  uploadResponse: UploadResponse | null;
}) {
  const fieldsById = useReviewStore((state) => state.fields);
  const activeFieldId = useReviewStore((state) => state.activeFieldId);
  const fields = useMemo(() => Object.values(fieldsById), [fieldsById]);

  return (
    <div className="h-full bg-slate-100">
      <div className="border-b border-slate-200 bg-white px-6 py-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
          PDF Source
        </p>
        <div className="mt-2 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-slate-900">
              Judgment Source
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {uploadResponse?.filename ?? "Uploaded judgment"}
            </p>
          </div>
        </div>
      </div>

      <PdfViewer
        fileDataUrl={pdfDataUrl}
        pageDimensions={uploadResponse?.page_dimensions ?? []}
        fields={fields}
        activeFieldId={activeFieldId}
      />
    </div>
  );
}

export default function ReviewClient({
  docId,
  initialUploadResponse,
  initialActionItems,
  initialUploadedAt,
}: ReviewClientProps) {
  const initFields = useReviewStore((state) => state.initFields);
  const initActionItems = useReviewStore((state) => state.initActionItems);
  const setActiveField = useReviewStore((state) => state.setActiveField);

  const [uploadResponse, setUploadResponse] = useState<UploadResponse | null>(
    initialUploadResponse,
  );
  const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);
  const [uploadedAt, setUploadedAt] = useState<string | null>(initialUploadedAt);

  useEffect(() => {
    let nextUploadResponse = initialUploadResponse;
    let nextActionItems = initialActionItems;
    let nextUploadedAt: string | null = initialUploadedAt;

    const sessionRaw = window.sessionStorage.getItem("lextrace_session");
    if (sessionRaw) {
      try {
        const session = JSON.parse(sessionRaw) as ReviewSessionPayload;
        if (session.uploadResponse?.doc_id === docId) {
          nextUploadResponse = session.uploadResponse;
          nextActionItems = session.actionItems ?? [];
          nextUploadedAt = session.uploadedAt ?? null;
        }
      } catch {
        nextUploadedAt = initialUploadedAt;
      }
    }

    const storedPdf = window.sessionStorage.getItem("lextrace_pdf_file");
    setPdfDataUrl(storedPdf);
    setUploadResponse(nextUploadResponse);
    setUploadedAt(nextUploadedAt);

    if (nextUploadResponse) {
      initFields(deriveReviewFields(nextUploadResponse));
      setActiveField(null);
    } else {
      initFields([]);
      setActiveField(null);
    }

    initActionItems(nextActionItems ?? []);
  }, [
    docId,
    initActionItems,
    initFields,
    initialActionItems,
    initialUploadResponse,
    initialUploadedAt,
    setActiveField,
  ]);

  return (
    <SplitPane
      left={<FieldPanel docId={docId} uploadedAt={uploadedAt} />}
      right={
        <RightPanel pdfDataUrl={pdfDataUrl} uploadResponse={uploadResponse} />
      }
    />
  );
}

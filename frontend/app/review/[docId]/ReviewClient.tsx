"use client";

import { useEffect, useMemo, useState } from "react";

import FieldPanel from "@/components/review/FieldPanel";
import PdfViewer from "@/components/review/PdfViewer";
import SplitPane from "@/components/review/SplitPane";
import SubmitBar from "@/components/review/SubmitBar";
import { useReviewStore } from "@/store/reviewStore";
import type { ActionPlan, ReviewField, UploadResponse } from "@/types";

interface ReviewSessionPayload {
  uploadResponse: UploadResponse;
  uploadedAt: string;
}

interface ReviewClientProps {
  docId: string;
  initialUploadResponse: UploadResponse | null;
  initialUploadedAt: string | null;
}

function deriveReviewFields(uploadResponse: UploadResponse): ReviewField[] {
  const zones = uploadResponse.zones;
  const fieldEvidence = uploadResponse.field_evidence ?? {};
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
      confidence: fieldEvidence.case_type?.confidence ?? defaultConfidence,
      source_page: fieldEvidence.case_type?.source_page ?? defaultPage,
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

function deriveActionPlanSourceFields(
  actionPlan: ActionPlan | null,
  defaultPage: number,
): ReviewField[] {
  if (!actionPlan) {
    return [];
  }

  const defaultConfidence = 0.75;

  return [
    ...actionPlan.key_directions.map((direction, index) => ({
      fieldId: direction.id,
      label: `Court Directive ${index + 1}`,
      value: direction.edited_text ?? direction.text,
      confidence: defaultConfidence,
      source_page: direction.source_page ?? defaultPage,
      source_bbox: null,
      review_status: direction.review_status,
    })),
    ...actionPlan.compliance_steps.map((step, index) => ({
      fieldId: step.id,
      label: `Required Action ${index + 1}`,
      value: step.edited_text ?? step.text,
      confidence: defaultConfidence,
      source_page: step.source_page ?? defaultPage,
      source_bbox: null,
      review_status: step.review_status,
    })),
    ...actionPlan.timelines.map((timeline, index) => ({
      fieldId: timeline.id,
      label: `Timeline ${index + 1}`,
      value: timeline.edited_text ?? timeline.text,
      confidence: defaultConfidence,
      source_page: timeline.source_page ?? defaultPage,
      source_bbox: null,
      review_status: timeline.review_status,
    })),
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
  const actionPlan = useReviewStore((state) => state.actionPlan);
  const activeFieldId = useReviewStore((state) => state.activeFieldId);
  const fields = useMemo(() => {
    const reviewFields = Object.values(fieldsById);
    const defaultPage =
      uploadResponse?.paragraphs[0]?.page ??
      uploadResponse?.page_texts[0]?.page ??
      1;

    return [
      ...reviewFields,
      ...deriveActionPlanSourceFields(actionPlan, defaultPage),
    ];
  }, [actionPlan, fieldsById, uploadResponse]);

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
  initialUploadedAt,
}: ReviewClientProps) {
  const initFields = useReviewStore((state) => state.initFields);
  const initActionPlan = useReviewStore((state) => state.initActionPlan);
  const setActiveField = useReviewStore((state) => state.setActiveField);

  const [uploadResponse, setUploadResponse] = useState<UploadResponse | null>(
    initialUploadResponse,
  );
  const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);
  const [uploadedAt, setUploadedAt] = useState<string | null>(initialUploadedAt);

  useEffect(() => {
    let nextUploadResponse = initialUploadResponse;
    let nextUploadedAt: string | null = initialUploadedAt;

    const sessionRaw = window.sessionStorage.getItem("lextrace_session");
    if (sessionRaw) {
      try {
        const session = JSON.parse(sessionRaw) as ReviewSessionPayload;
        if (session.uploadResponse?.doc_id === docId) {
          nextUploadResponse = session.uploadResponse;
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
      initActionPlan(nextUploadResponse.action_plan);
      setActiveField(null);
    } else {
      initFields([]);
      setActiveField(null);
    }
  }, [
    docId,
    initActionPlan,
    initFields,
    initialUploadResponse,
    initialUploadedAt,
    setActiveField,
  ]);

  return (
    <SplitPane
      left={(
        <div className="flex h-full min-h-0 flex-col">
          <div className="min-h-0 flex-1">
            <FieldPanel docId={docId} uploadedAt={uploadedAt} />
          </div>
          <SubmitBar docId={docId} />
        </div>
      )}
      right={
        <RightPanel pdfDataUrl={pdfDataUrl} uploadResponse={uploadResponse} />
      }
    />
  );
}

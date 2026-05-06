"use client";

import { useEffect, useMemo, useRef } from "react";

import ActionPlanPanel from "@/components/review/ActionPlanPanel";
import FieldCard from "@/components/review/FieldCard";
import ProgressBar from "@/components/review/ProgressBar";
import { useReviewStore } from "@/store/reviewStore";

interface FieldPanelProps {
  docId: string;
  uploadedAt: string | null;
}

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Session";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Session";
  }

  const formatter = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const parts = formatter.formatToParts(parsed);
  const valueByType = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((part) => part.type === type)?.value ?? "";

  return `${valueByType("year")}-${valueByType("month")}-${valueByType("day")} ${valueByType("hour")}:${valueByType("minute")} IST`;
}

export default function FieldPanel({ docId, uploadedAt }: FieldPanelProps) {
  const fieldsById = useReviewStore((state) => state.fields);
  const activeFieldId = useReviewStore((state) => state.activeFieldId);
  const setActiveField = useReviewStore((state) => state.setActiveField);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const fields = useMemo(() => Object.values(fieldsById), [fieldsById]);

  useEffect(() => {
    if (!activeFieldId) {
      return;
    }

    cardRefs.current[activeFieldId]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [activeFieldId]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-6 py-5 backdrop-blur">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
              Review Session
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
              Case Details
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Document ID: <span className="font-mono">{docId}</span>
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-right">
            <p className="text-xs text-slate-500">{formatTimestamp(uploadedAt)}</p>
          </div>
        </div>

        <div className="mt-5">
          <ProgressBar />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              Extracted Fields
            </h2>
            <span className="text-xs text-slate-400">
              {fields.length} shown
            </span>
          </div>

          <div className="space-y-3">
            {fields.map((field) => (
              <FieldCard
                key={field.fieldId}
                field={field}
                isActive={activeFieldId === field.fieldId}
                onActivate={setActiveField}
                registerRef={(element) => {
                  cardRefs.current[field.fieldId] = element;
                }}
              />
            ))}
          </div>
        </section>

        <ActionPlanPanel />
      </div>
    </div>
  );
}

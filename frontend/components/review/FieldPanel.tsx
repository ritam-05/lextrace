"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import FieldCard from "@/components/review/FieldCard";
import ProgressBar from "@/components/review/ProgressBar";
import { useReviewStore } from "@/store/reviewStore";
import type { ActionPlanItem } from "@/types";

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

  return [
    parsed.getUTCFullYear(),
    pad(parsed.getUTCMonth() + 1),
    pad(parsed.getUTCDate()),
  ].join("-") +
    " " +
    [pad(parsed.getUTCHours()), pad(parsed.getUTCMinutes())].join(":") +
    " UTC";
}

function ActionPlanPanel({ items }: { items: ActionPlanItem[] }) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <section className="rounded-3xl border border-slate-200 bg-slate-50/70">
      <button
        type="button"
        onClick={() => {
          setIsOpen((current) => !current);
        }}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
            Action Plan
          </p>
          <p className="mt-1 text-xs text-slate-400">{items.length} items</p>
        </div>
        <span className="text-sm font-medium text-slate-600">
          {isOpen ? "Hide" : "Show"}
        </span>
      </button>

      {isOpen ? (
        <div className="space-y-3 border-t border-slate-200 px-5 py-4">
          {items.length > 0 ? (
            items.map((item) => (
              <div
                key={item.itemId}
                className="rounded-2xl border border-slate-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {item.edited_directive ?? item.directive}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      {item.department} · {item.nature}
                    </p>
                  </div>
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
                    {item.deadline ?? "No deadline"}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
              No action items were returned for this judgment yet.
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}

export default function FieldPanel({ docId, uploadedAt }: FieldPanelProps) {
  const fieldsById = useReviewStore((state) => state.fields);
  const actionItemsById = useReviewStore((state) => state.actionItems);
  const activeFieldId = useReviewStore((state) => state.activeFieldId);
  const setActiveField = useReviewStore((state) => state.setActiveField);

  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const fields = useMemo(() => Object.values(fieldsById), [fieldsById]);
  const actionItems = useMemo(
    () => Object.values(actionItemsById),
    [actionItemsById],
  );

  const displayedFields = useMemo(() => {
    if (!flaggedOnly) {
      return fields;
    }

    return fields.filter(
      (field) => field.confidence < 0.85 || field.review_status === "unreviewed",
    );
  }, [fields, flaggedOnly]);

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
              Extracted Data Review
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

        <div className="mt-5 flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setFlaggedOnly(false);
            }}
            className={[
              "rounded-full px-3 py-1.5 text-sm font-medium transition",
              !flaggedOnly
                ? "bg-slate-900 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:border-slate-300",
            ].join(" ")}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => {
              setFlaggedOnly(true);
            }}
            className={[
              "rounded-full px-3 py-1.5 text-sm font-medium transition",
              flaggedOnly
                ? "bg-amber-500 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:border-slate-300",
            ].join(" ")}
          >
            Flagged only
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              Extracted Fields
            </h2>
            <span className="text-xs text-slate-400">
              {displayedFields.length} shown
            </span>
          </div>

          <div className="space-y-3">
            {displayedFields.map((field) => (
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

        <div className="mt-8">
          <ActionPlanPanel items={actionItems} />
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { getConfidenceTier } from "@/lib/confidenceColor";
import { useReviewStore } from "@/store/reviewStore";
import type { ReviewField } from "@/types";

interface FieldCardProps {
  field: ReviewField;
  isActive: boolean;
  onActivate: (fieldId: string) => void;
  registerRef?: (element: HTMLDivElement | null) => void;
}

function needsReverification(value: string | null | undefined): boolean {
  if (!value) {
    return true;
  }

  const normalized = value.trim().toLowerCase();
  return [
    "",
    "not available",
    "not shown",
    "not specified",
    "n/a",
    "na",
    "none",
    "null",
    "-",
    "—",
  ].includes(normalized);
}

function getCardTone(
  field: ReviewField,
  isActive: boolean,
  isEditing: boolean,
): string {
  if (isEditing) {
    return "border-blue-500 shadow-[0_0_0_3px_rgba(59,130,246,0.12)]";
  }

  if (field.review_status === "approved") {
    return isActive
      ? "border-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.10)]"
      : "border-emerald-300";
  }

  if (field.review_status === "rejected") {
    return isActive
      ? "border-rose-400 bg-rose-50/60 shadow-[0_0_0_3px_rgba(244,63,94,0.08)]"
      : "border-rose-300 bg-rose-50/40";
  }

  if (field.review_status === "edited") {
    return isActive
      ? "border-blue-500 shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
      : "border-blue-300 bg-blue-50/40";
  }

  if (isActive) {
    return "border-slate-900 shadow-[0_0_0_3px_rgba(15,23,42,0.08)]";
  }

  const tier = getConfidenceTier(field.confidence);
  if (tier === "medium") {
    return "border-amber-300";
  }

  if (tier === "low") {
    return "border-rose-300";
  }

  return "border-slate-200";
}

export default function FieldCard({
  field,
  isActive,
  onActivate,
  registerRef,
}: FieldCardProps) {
  const approveField = useReviewStore((state) => state.approveField);
  const editField = useReviewStore((state) => state.editField);
  const rejectField = useReviewStore((state) => state.rejectField);

  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState(field.edited_value ?? field.value ?? "");

  useEffect(() => {
    if (!isEditing) {
      setDraftValue(field.edited_value ?? field.value ?? "");
    }
  }, [field.edited_value, field.value, isEditing]);

  const currentValue = field.edited_value ?? field.value;
  const shouldShowReverify = needsReverification(currentValue);
  const showApproveRejectActions =
    field.review_status === "unreviewed" || field.review_status === "edited";
  const showEditAfterReject = field.review_status === "rejected";

  return (
    <div
      ref={registerRef}
      role="button"
      tabIndex={0}
      onClick={() => {
        onActivate(field.fieldId);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onActivate(field.fieldId);
        }
      }}
      className={[
        "w-full rounded-2xl border bg-white p-4 text-left transition-all",
        getCardTone(field, isActive, isEditing),
        field.review_status === "rejected" ? "opacity-90" : "",
      ].join(" ")}
    >
      {isEditing ? (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-700">
              {field.label}
            </p>
          </div>

          <div className="space-y-3">
            <p className="text-sm text-slate-400 line-through">
              {field.value ?? "No extracted value"}
            </p>
            <input
              value={draftValue}
              onChange={(event) => {
                setDraftValue(event.target.value);
              }}
              onClick={(event) => {
                event.stopPropagation();
              }}
              className="w-full rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-400 focus:bg-white"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setDraftValue(field.edited_value ?? field.value ?? "");
                setIsEditing(false);
              }}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                editField(field.fieldId, draftValue);
                setIsEditing(false);
              }}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-blue-500"
            >
              Confirm
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">
              {field.label}
            </p>
            {field.review_status === "approved" ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                Approved
              </span>
            ) : field.review_status === "rejected" ? (
              <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700">
                Rejected
              </span>
            ) : field.review_status === "edited" ? (
              <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                Edited
              </span>
            ) : shouldShowReverify ? (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                Please reverify
              </span>
            ) : (
              <span className="text-xs font-medium text-slate-400">
                &nbsp;
              </span>
            )}
          </div>

          <div className="space-y-2">
            <p
              className={[
                "text-base font-medium",
                field.review_status === "rejected" ? "text-slate-500" : "text-slate-900",
              ].join(" ")}
            >
              {currentValue ?? "Not available"}
            </p>
            {field.review_status !== "approved" ? (
              <p className="text-xs text-slate-500">Source: Page {field.source_page}</p>
            ) : null}
          </div>

          {showApproveRejectActions ? (
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  approveField(field.fieldId);
                }}
                className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  rejectField(field.fieldId);
                }}
                className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
              >
                Reject
              </button>
            </div>
          ) : null}

          {showEditAfterReject ? (
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setDraftValue(field.edited_value ?? field.value ?? "");
                  setIsEditing(true);
                }}
                className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
              >
                Edit
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

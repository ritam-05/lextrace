"use client";

import { useMemo } from "react";

import { useReviewStore } from "@/store/reviewStore";
import type { ActionPlan } from "@/types";

function isVerified(status: string): boolean {
  return status === "approved" || status === "edited";
}

function countActionItems(actionPlan: ActionPlan | null): number {
  if (!actionPlan) {
    return 0;
  }

  return (
    actionPlan.key_directions.length +
    actionPlan.compliance_steps.length +
    actionPlan.timelines.length
  );
}

function countVerifiedActionItems(actionPlan: ActionPlan | null): number {
  if (!actionPlan) {
    return 0;
  }

  return [
    ...actionPlan.key_directions,
    ...actionPlan.compliance_steps,
    ...actionPlan.timelines,
  ].filter((item) => isVerified(item.review_status)).length;
}

export default function ProgressBar() {
  const fieldsById = useReviewStore((state) => state.fields);
  const actionPlan = useReviewStore((state) => state.actionPlan);

  const { totalItems, reviewedItems, progressPercent, toneClass } = useMemo(() => {
    const fields = Object.values(fieldsById);
    const total = fields.length + countActionItems(actionPlan);
    const verified =
      fields.filter((field) => isVerified(field.review_status)).length +
      countVerifiedActionItems(actionPlan);
    const percent = total > 0 ? (verified / total) * 100 : 0;

    return {
      totalItems: total,
      reviewedItems: verified,
      progressPercent: percent,
      toneClass:
        percent >= 100
          ? "bg-emerald-600"
          : percent >= 50
            ? "bg-amber-500"
            : "bg-rose-500",
    };
  }, [actionPlan, fieldsById]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-slate-700">
          {reviewedItems} of {totalItems} items verified
        </p>
        <p className="text-xs text-slate-500">
          {Math.round(progressPercent)}%
        </p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={["h-full rounded-full transition-all duration-300", toneClass].join(" ")}
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </div>
  );
}

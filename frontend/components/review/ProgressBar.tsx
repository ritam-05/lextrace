"use client";

import { useMemo } from "react";

import { useReviewStore } from "@/store/reviewStore";

export default function ProgressBar() {
  const fieldsById = useReviewStore((state) => state.fields);

  const { totalFields, verifiedCount, progressPercent, toneClass } = useMemo(() => {
    const fields = Object.values(fieldsById);
    const total = fields.length;
    const verified = fields.filter(
      (field) => field.review_status === "approved" || field.review_status === "edited",
    ).length;
    const percent = total > 0 ? (verified / total) * 100 : 0;

    return {
      totalFields: total,
      verifiedCount: verified,
      progressPercent: percent,
      toneClass:
        percent >= 100
          ? "bg-emerald-600"
          : percent >= 50
            ? "bg-amber-500"
            : "bg-rose-500",
    };
  }, [fieldsById]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-slate-700">
          {verifiedCount} of {totalFields} fields verified
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

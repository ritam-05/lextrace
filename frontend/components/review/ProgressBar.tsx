"use client";

import { useMemo } from "react";

import { useReviewStore } from "@/store/reviewStore";

export default function ProgressBar() {
  const totalCount = useReviewStore((state) => state.totalCount);
  const verifiedCount = useReviewStore((state) => state.verifiedCount);

  const { totalItems, reviewedItems, progressPercent, toneClass } = useMemo(() => {
    const total = totalCount();
    const verified = verifiedCount();
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
  }, [totalCount, verifiedCount]);

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

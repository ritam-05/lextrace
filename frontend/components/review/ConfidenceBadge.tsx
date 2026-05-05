"use client";

import { getConfidenceTier } from "@/lib/confidenceColor";

interface ConfidenceBadgeProps {
  score: number;
}

const tierConfig = {
  high: {
    icon: "✓",
    label: "High",
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  medium: {
    icon: "△",
    label: "Medium",
    className:
      "border-amber-200 bg-amber-50 text-amber-800",
  },
  low: {
    icon: "✕",
    label: "Low",
    className:
      "border-rose-200 bg-rose-50 text-rose-800",
  },
} as const;

export default function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  const tier = getConfidenceTier(score);
  const config = tierConfig[tier];
  const percentage = Math.round(score * 100);

  return (
    <span
      className={[
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold",
        config.className,
      ].join(" ")}
      aria-label={`${config.label} confidence ${percentage} percent`}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
      <span>{percentage}%</span>
    </span>
  );
}

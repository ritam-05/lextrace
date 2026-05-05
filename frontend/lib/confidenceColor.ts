import type { ConfidenceTier } from "@/types";

/**
 * Maps a numeric confidence score to a named confidence tier.
 */
export function getConfidenceTier(score: number): ConfidenceTier {
  if (score >= 0.85) {
    return "high";
  }

  if (score >= 0.6) {
    return "medium";
  }

  return "low";
}

/**
 * Returns the visual token set associated with a confidence tier.
 */
export function getTierColors(
  tier: ConfidenceTier,
): {
  border: string;
  badge: string;
  highlight: string;
  text: string;
} {
  switch (tier) {
    case "high":
      return {
        border: "border-green-500",
        badge:
          "border border-green-500/20 bg-green-500/10 text-green-700 dark:text-green-300",
        highlight: "#22c55e1a",
        text: "text-green-700 dark:text-green-300",
      };
    case "medium":
      return {
        border: "border-amber-500",
        badge:
          "border border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300",
        highlight: "#f59e0b1a",
        text: "text-amber-700 dark:text-amber-300",
      };
    case "low":
      return {
        border: "border-red-500",
        badge:
          "border border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300",
        highlight: "#ef44441a",
        text: "text-red-700 dark:text-red-300",
      };
  }
}

/**
 * Formats a numeric score into a concise label for badges and summaries.
 */
export function getScoreLabel(score: number): string {
  const tier = getConfidenceTier(score);
  const percentage = Math.round(score * 100);
  const label = tier.charAt(0).toUpperCase() + tier.slice(1);

  return `${label} (${percentage}%)`;
}

"use client";

import AppealLegend from "@/components/dashboard/AppealLegend";
import type { AppealAnalysis } from "@/types";

interface AppealAnalysisCardProps {
  appealAnalysis: AppealAnalysis | null | undefined;
}

function getTone(appealAnalysis: AppealAnalysis) {
  if (appealAnalysis.risk_score >= 7) {
    return {
      badge: "bg-red-100 text-red-700",
      recommendation: "High appeal risk. Immediate legal escalation recommended.",
    };
  }

  if (appealAnalysis.risk_score >= 4) {
    return {
      badge: "bg-amber-100 text-amber-700",
      recommendation: "Moderate appeal exposure. Review with counsel before action.",
    };
  }

  return {
    badge: "bg-emerald-100 text-emerald-700",
    recommendation: "Low adverse risk. Proceed with implementation unless new facts emerge.",
  };
}

export default function AppealAnalysisCard({
  appealAnalysis,
}: AppealAnalysisCardProps) {
  if (!appealAnalysis) {
    return null;
  }

  const tone = getTone(appealAnalysis);

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Appeal Consideration
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Executive summary of the verified appeal recommendation.
          </p>
        </div>

        <div className="relative self-start">
          <div className="group relative inline-flex">
            <span
              className={[
                "inline-flex cursor-default rounded-full px-3 py-1 text-xs font-semibold",
                tone.badge,
              ].join(" ")}
            >
              {appealAnalysis.consideration} · Risk {appealAnalysis.risk_score}
            </span>
            <span className="sr-only">
              Hover over the appeal score to view the appeal consideration legend
            </span>
            <AppealLegend className="pointer-events-none invisible absolute right-0 top-[calc(100%+0.75rem)] z-20 w-[18rem] opacity-0 transition-all duration-150 group-hover:visible group-hover:opacity-100 md:w-[20rem]" />
          </div>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Recommendation
          </p>
          <p className="mt-1 text-sm font-medium text-slate-800">
            {tone.recommendation}
          </p>
        </div>

        {appealAnalysis.justification.length > 0 ? (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              Justification
            </p>
            <ul className="mt-2 space-y-2">
              {appealAnalysis.justification.map((point) => (
                <li key={point} className="text-sm leading-6 text-slate-700">
                  {point}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

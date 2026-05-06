"use client";

import type { TimelineEntry } from "@/types";
import { filterApproved } from "@/lib/dashboard-utils";

interface TimelinesSectionProps {
  timelines: TimelineEntry[];
}

function isTimeSensitive(text: string): boolean {
  const normalized = text.toLowerCase();
  return (
    normalized.includes("immediately") ||
    normalized.includes("forthwith") ||
    normalized.includes("urgent") ||
    normalized.includes("within") ||
    normalized.includes("days") ||
    normalized.includes("weeks")
  );
}

export default function TimelinesSection({
  timelines,
}: TimelinesSectionProps) {
  const trustedTimelines = filterApproved(timelines);

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-slate-900">Key Timelines</h2>
        <p className="mt-1 text-sm text-slate-500">
          Verified legal timelines and deadlines relevant to execution.
        </p>
      </div>

      {trustedTimelines.length === 0 ? (
        <p className="text-sm text-slate-500">No verified timelines extracted.</p>
      ) : (
        <div className="space-y-4">
          {trustedTimelines.map((timeline) => {
            const text =
              timeline.review_status === "edited"
                ? timeline.edited_text ?? timeline.text
                : timeline.text;

            return (
              <div
                key={timeline.id}
                className="rounded-xl border border-slate-200 border-l-4 border-l-green-500 bg-white p-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{text}</p>
                    {timeline.related_step_index ? (
                      <p className="mt-2 text-xs text-slate-500">
                        Linked Action: Step {timeline.related_step_index}
                      </p>
                    ) : null}
                  </div>

                  {isTimeSensitive(text) ? (
                    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-700">
                      Time Sensitive
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

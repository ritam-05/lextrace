"use client";

import type { ComplianceStep, TimelineEntry } from "@/types";
import {
  filterTrusted,
  getReviewedText,
  groupActionsByDepartment,
} from "@/lib/dashboard-utils";

interface DepartmentWiseViewProps {
  filename: string;
  caseNumber: string;
  complianceSteps: ComplianceStep[];
  departments: string[];
  timelines: TimelineEntry[];
}

function getLinkedTimelines(
  actionIndex: number,
  timelines: TimelineEntry[],
): TimelineEntry[] {
  return timelines.filter((timeline) => timeline.related_step_index === actionIndex + 1);
}

export default function DepartmentWiseView({
  filename,
  caseNumber,
  complianceSteps,
  departments,
  timelines,
}: DepartmentWiseViewProps) {
  const trustedSteps = filterTrusted(complianceSteps);
  const trustedTimelines = filterTrusted(timelines);
  const groupedActions = groupActionsByDepartment(trustedSteps, departments);

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Department-wise View
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Department ownership for this verified judgment.
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-right">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Judgment
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-800">
            {caseNumber !== "Not available" ? caseNumber : filename}
          </p>
        </div>
      </div>

      {groupedActions.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-700">
            No department-specific action has been verified for this judgment.
          </p>
          <p className="mt-1 text-sm text-slate-500">
            The judgment remains available in the trusted dashboard above.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {groupedActions.map((group) => (
            <div
              key={group.department}
              className="rounded-lg border border-slate-200 bg-slate-50 p-4"
            >
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    Responsible Department
                  </p>
                  <h3 className="mt-1 text-sm font-semibold text-slate-900">
                    {group.department}
                  </h3>
                </div>

                <span className="self-start rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-500">
                  {group.actions.length} verified action
                  {group.actions.length === 1 ? "" : "s"}
                </span>
              </div>

              <div className="mt-4 space-y-3">
                {group.actions.map((action) => {
                  const actionIndex = trustedSteps.findIndex(
                    (step) => step.id === action.id,
                  );
                  const linkedTimelines =
                    actionIndex >= 0
                      ? getLinkedTimelines(actionIndex, trustedTimelines)
                      : [];

                  return (
                    <div
                      key={action.id}
                      className="rounded-lg border border-slate-200 bg-white p-3"
                    >
                      <p className="text-sm leading-6 text-slate-700">
                        {getReviewedText(action)}
                      </p>

                      {linkedTimelines.length > 0 ? (
                        <div className="mt-3 border-t border-slate-100 pt-3">
                          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                            Linked Timeline
                          </p>
                          <ul className="mt-2 space-y-1">
                            {linkedTimelines.map((timeline) => (
                              <li
                                key={timeline.id}
                                className="text-xs leading-5 text-slate-600"
                              >
                                {getReviewedText(timeline)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

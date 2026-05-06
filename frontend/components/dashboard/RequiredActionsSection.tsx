"use client";

import type { ComplianceStep } from "@/types";
import { filterTrusted, getReviewedText, groupActionsByDepartment } from "@/lib/dashboard-utils";

interface RequiredActionsSectionProps {
  complianceSteps: ComplianceStep[];
  departments: string[];
}

export default function RequiredActionsSection({
  complianceSteps,
  departments,
}: RequiredActionsSectionProps) {
  const trustedSteps = filterTrusted(complianceSteps);
  const groupedActions = groupActionsByDepartment(trustedSteps, departments);

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-slate-900">
          Required Actions
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Verified operational checklist for implementation teams.
        </p>
      </div>

      {groupedActions.length === 0 ? (
        <p className="text-sm text-slate-500">No verified compliance actions.</p>
      ) : (
        <div className="space-y-4">
          {groupedActions.map((group) => (
            <div
              key={group.department}
              className="rounded-lg border border-slate-200 bg-slate-50 p-4"
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-slate-800">
                  {group.department}
                </h3>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-500">
                  {group.actions.length} action{group.actions.length === 1 ? "" : "s"}
                </span>
              </div>

              <div className="space-y-3">
                {group.actions.map((action) => (
                  <div key={action.id} className="flex items-start gap-3">
                    <span className="mt-0.5 text-emerald-600" aria-hidden="true">
                      □
                    </span>
                    <p className="text-sm text-slate-700">{getReviewedText(action)}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

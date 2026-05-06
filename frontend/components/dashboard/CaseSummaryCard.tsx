"use client";

import type { ReviewField } from "@/types";
import { getApprovedValue } from "@/lib/dashboard-utils";

interface CaseSummaryCardProps {
  fields: ReviewField[];
  filename: string;
  verifiedAt: string;
  reviewer: string;
}

function formatVerifiedAt(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(parsed);
}

function findField(fields: ReviewField[], ids: string[]): ReviewField | undefined {
  return fields.find((field) => ids.includes(field.fieldId));
}

function SummaryItem({
  label,
  value,
  fullWidth = false,
}: {
  label: string;
  value: string | null;
  fullWidth?: boolean;
}) {
  return (
    <div className={fullWidth ? "md:col-span-2" : ""}>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-sm font-medium text-slate-800">
        {value && value.trim().length > 0 ? value : "Not available"}
      </p>
    </div>
  );
}

export default function CaseSummaryCard({
  fields,
  filename,
  verifiedAt,
  reviewer,
}: CaseSummaryCardProps) {
  const caseNumber = getApprovedValue(findField(fields, ["case_number"]));
  const caseType = getApprovedValue(findField(fields, ["case_type"]));
  const judge = getApprovedValue(findField(fields, ["judge_name", "bench"]));
  const judgmentDate = getApprovedValue(
    findField(fields, ["date_of_order", "judgment_date"]),
  );
  const petitioner = getApprovedValue(findField(fields, ["petitioner"]));
  const respondent = getApprovedValue(findField(fields, ["respondent"]));

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{filename}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Verified on {formatVerifiedAt(verifiedAt)}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              Reviewer
            </p>
            <p className="mt-1 text-sm font-medium text-slate-800">{reviewer}</p>
          </div>
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
            ✓ Verified
          </span>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
        <SummaryItem label="Case Number" value={caseNumber} />
        <SummaryItem label="Case Type" value={caseType} />
        <SummaryItem label="Judge" value={judge} />
        <SummaryItem label="Date of Order" value={judgmentDate} />
        <SummaryItem label="Petitioner" value={petitioner} fullWidth />
        <SummaryItem label="Respondent" value={respondent} fullWidth />
      </div>
    </section>
  );
}

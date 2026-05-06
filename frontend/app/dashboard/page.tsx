"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import AppealAnalysisCard from "@/components/dashboard/AppealAnalysisCard";
import CaseSummaryCard from "@/components/dashboard/CaseSummaryCard";
import DashboardFooter from "@/components/dashboard/DashboardFooter";
import DirectivesSection from "@/components/dashboard/DirectivesSection";
import RequiredActionsSection from "@/components/dashboard/RequiredActionsSection";
import TimelinesSection from "@/components/dashboard/TimelinesSection";
import { resetSystemData } from "@/lib/apiClient";
import {
  filterApproved,
  getApprovedValue,
  safeParseSession,
  type VerifiedSession,
} from "@/lib/dashboard-utils";
import type { ReviewField } from "@/types";

function EmptyState() {
  const router = useRouter();

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div className="text-xs font-medium uppercase tracking-widest text-slate-500">
          LeXTrace / Dashboard
        </div>
        <div className="text-xs font-semibold uppercase tracking-widest text-slate-700">
          Verified Judgment Report
        </div>
        <div className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
          Trusted View
        </div>
      </div>

      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-6">
        <div className="text-center">
          <svg
            className="mx-auto h-14 w-14 text-slate-300"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            aria-hidden="true"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
            <path d="M9 13h6" />
            <path d="M9 17h6" />
          </svg>
          <h1 className="mt-5 text-lg font-medium text-slate-700">
            No verified judgment found
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Complete the review flow to generate a trusted judgment report.
          </p>
          <button
            type="button"
            aria-label="Upload a Judgment"
            onClick={() => {
              router.push("/");
            }}
            className="mt-6 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
          >
            Upload a Judgment
          </button>
        </div>
      </div>
    </main>
  );
}

function findFieldValue(fields: ReviewField[], ids: string[]): string {
  const field = fields.find((item) => ids.includes(item.fieldId));
  return getApprovedValue(field) ?? "Not available";
}

export default function DashboardPage() {
  const router = useRouter();
  const [verifiedSession, setVerifiedSession] = useState<VerifiedSession | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  useEffect(() => {
    const parsedSession = safeParseSession(
      sessionStorage.getItem("lextrace_verified"),
    );
    setVerifiedSession(parsedSession);
    setHasLoaded(true);
  }, []);

  const trustedFields = useMemo(
    () =>
      verifiedSession?.fields.filter(
        (field) =>
          field.review_status === "approved" || field.review_status === "edited",
      ) ?? [],
    [verifiedSession],
  );

  const trustedActionPlan = useMemo(() => {
    if (!verifiedSession) {
      return null;
    }

    return {
      ...verifiedSession.actionPlan,
      key_directions: filterApproved(verifiedSession.actionPlan.key_directions),
      compliance_steps: filterApproved(verifiedSession.actionPlan.compliance_steps),
      timelines: filterApproved(verifiedSession.actionPlan.timelines),
    };
  }, [verifiedSession]);

  const trustedDirections = useMemo(
    () => trustedActionPlan?.key_directions ?? [],
    [trustedActionPlan],
  );

  const trustedCompliance = useMemo(
    () => trustedActionPlan?.compliance_steps ?? [],
    [trustedActionPlan],
  );

  const trustedTimelines = useMemo(
    () => trustedActionPlan?.timelines ?? [],
    [trustedActionPlan],
  );

  const handleSaveDashboard = (): void => {
    if (!verifiedSession) {
      return;
    }

    const html = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>LeXTrace Dashboard</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }
      h1, h2 { color: #0f172a; }
      h1 { margin-bottom: 8px; }
      h2 { margin-top: 28px; margin-bottom: 12px; font-size: 18px; }
      p, li { font-size: 14px; line-height: 1.6; }
      .meta { margin-bottom: 20px; }
      .meta strong { display: inline-block; width: 140px; }
      ul, ol { padding-left: 20px; }
      .badge { display: inline-block; padding: 4px 10px; border: 1px solid #86efac; background: #f0fdf4; color: #166534; border-radius: 999px; font-size: 12px; font-weight: 700; }
    </style>
  </head>
  <body>
    <div class="badge">Verified Judgment Report</div>
    <h1>${verifiedSession.filename}</h1>
    <p>Verified by ${verifiedSession.reviewer} on ${verifiedSession.verifiedAt}</p>

    <div class="meta">
      <p><strong>Case Number:</strong> ${findFieldValue(trustedFields, ["case_number"])}</p>
      <p><strong>Case Type:</strong> ${findFieldValue(trustedFields, ["case_type"])}</p>
      <p><strong>Judge:</strong> ${findFieldValue(trustedFields, ["judge_name", "bench"])}</p>
      <p><strong>Date of Order:</strong> ${findFieldValue(trustedFields, ["date_of_order", "judgment_date"])}</p>
      <p><strong>Petitioner:</strong> ${findFieldValue(trustedFields, ["petitioner"])}</p>
      <p><strong>Respondent:</strong> ${findFieldValue(trustedFields, ["respondent"])}</p>
    </div>

    <h2>Court Directives</h2>
    <ol>
      ${trustedDirections.map((item) => `<li>${item.review_status === "edited" ? item.edited_text ?? item.text : item.text}</li>`).join("") || "<li>No verified directives available.</li>"}
    </ol>

    <h2>Required Actions</h2>
    <ul>
      ${trustedCompliance.map((item) => `<li>${item.review_status === "edited" ? item.edited_text ?? item.text : item.text}</li>`).join("") || "<li>No verified compliance actions.</li>"}
    </ul>

    <h2>Key Timelines</h2>
    <ul>
      ${trustedTimelines.map((item) => {
        const text = item.review_status === "edited" ? item.edited_text ?? item.text : item.text;
        const suffix = item.related_step_index ? ` (Linked Action: Step ${item.related_step_index})` : "";
        return `<li>${text}${suffix}</li>`;
      }).join("") || "<li>No verified timelines extracted.</li>"}
    </ul>

    <h2>Appeal Consideration</h2>
    <p><strong>Consideration:</strong> ${verifiedSession.actionPlan.appeal_analysis.consideration}</p>
    <p><strong>Risk Score:</strong> ${verifiedSession.actionPlan.appeal_analysis.risk_score}</p>
    <ul>
      ${verifiedSession.actionPlan.appeal_analysis.justification.map((point) => `<li>${point}</li>`).join("") || "<li>No justification available.</li>"}
    </ul>

    <h2>AI Analysis Summary</h2>
    <p>${verifiedSession.actionPlan.llm_context || "No AI analysis summary provided."}</p>
  </body>
</html>`;

    const blob = new Blob([html], { type: "application/msword" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${verifiedSession.filename.replace(/\.pdf$/i, "") || "lextrace-dashboard"}.doc`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleReset = async (): Promise<void> => {
    if (isResetting) {
      return;
    }

    const confirmed = window.confirm(
      "This will delete all past backend data, clear the current browser session, and return to the landing page. Continue?",
    );

    if (!confirmed) {
      return;
    }

    setDashboardError(null);
    setIsResetting(true);

    try {
      await resetSystemData();
    } catch (error) {
      setDashboardError(
        error instanceof Error ? error.message : "Reset could not be completed.",
      );
      setIsResetting(false);
      return;
    }

    sessionStorage.removeItem("lextrace_verified");
    sessionStorage.removeItem("lextrace_session");
    sessionStorage.removeItem("lextrace_pdf_file");
    router.replace("/");
    router.refresh();
  };

  if (!hasLoaded) {
    return <main className="min-h-screen bg-slate-50" />;
  }

  if (!verifiedSession) {
    return <EmptyState />;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="fixed inset-x-0 top-0 z-20 h-14 border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-full max-w-6xl items-center justify-between px-6">
          <div className="text-xs font-medium uppercase tracking-widest text-slate-500">
            LeXTrace / Dashboard
          </div>
          <div className="text-center text-xs font-semibold uppercase tracking-widest text-slate-700">
            Verified Judgment Report
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSaveDashboard}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              Save Dashboard
            </button>
            <button
              type="button"
              onClick={() => {
                void handleReset();
              }}
              disabled={isResetting}
              className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isResetting ? "Resetting..." : "New"}
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-6 py-8 pt-20">
        {dashboardError ? (
          <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {dashboardError}
          </div>
        ) : null}

        <CaseSummaryCard
          fields={trustedFields}
          filename={verifiedSession.filename}
          verifiedAt={verifiedSession.verifiedAt}
          reviewer={verifiedSession.reviewer}
        />
        <DirectivesSection
          directives={trustedActionPlan?.key_directions ?? []}
        />
        <RequiredActionsSection
          complianceSteps={trustedActionPlan?.compliance_steps ?? []}
          departments={trustedActionPlan?.responsible_departments ?? []}
        />
        <TimelinesSection timelines={trustedActionPlan?.timelines ?? []} />
        <AppealAnalysisCard
          appealAnalysis={verifiedSession.actionPlan.appeal_analysis}
        />
        <DashboardFooter verifiedAt={verifiedSession.verifiedAt} />
      </div>
    </main>
  );
}

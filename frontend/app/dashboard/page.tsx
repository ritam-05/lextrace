"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import AppealAnalysisCard from "@/components/dashboard/AppealAnalysisCard";
import CaseSummaryCard from "@/components/dashboard/CaseSummaryCard";
import DashboardFooter from "@/components/dashboard/DashboardFooter";
import DirectivesSection from "@/components/dashboard/DirectivesSection";
import RequiredActionsSection from "@/components/dashboard/RequiredActionsSection";
import TimelinesSection from "@/components/dashboard/TimelinesSection";
import {
  safeParseSession,
  type VerifiedSession,
} from "@/lib/dashboard-utils";

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
          ✓ Trusted View
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

export default function DashboardPage() {
  const [verifiedSession, setVerifiedSession] = useState<VerifiedSession | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

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
          <div className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
            ✓ Trusted View
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-6 py-8 pt-20">
        <CaseSummaryCard
          fields={trustedFields}
          filename={verifiedSession.filename}
          verifiedAt={verifiedSession.verifiedAt}
          reviewer={verifiedSession.reviewer}
        />
        <DirectivesSection
          directives={verifiedSession.actionPlan.key_directions}
        />
        <RequiredActionsSection
          complianceSteps={verifiedSession.actionPlan.compliance_steps}
          departments={verifiedSession.actionPlan.responsible_departments}
        />
        <TimelinesSection timelines={verifiedSession.actionPlan.timelines} />
        <AppealAnalysisCard
          appealAnalysis={verifiedSession.actionPlan.appeal_analysis}
        />
        <DashboardFooter verifiedAt={verifiedSession.verifiedAt} />
      </div>
    </main>
  );
}

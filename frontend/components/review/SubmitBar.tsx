"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { currentUser } from "@/lib/auth";
import { submitVerification } from "@/lib/apiClient";
import { useReviewStore } from "@/store/reviewStore";
import {
  finalizeActionPlan,
  finalizeFields,
} from "@/lib/dashboard-utils";
import type { ReviewField, VerificationPayload } from "@/types";

interface SubmitBarProps {
  docId: string;
}

export default function SubmitBar({ docId }: SubmitBarProps) {
  const router = useRouter();
  const fieldsById = useReviewStore((state) => state.fields);
  const actionPlan = useReviewStore((state) => state.actionPlan);
  const allVerified = useReviewStore((state) => state.allVerified);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fields = useMemo(() => Object.values(fieldsById), [fieldsById]);
  const isReadyToSubmit = allVerified() && actionPlan !== null;

  const handleSubmit = async (): Promise<void> => {
    if (!actionPlan || !isReadyToSubmit || isSubmitting) {
      return;
    }

    setErrorMessage(null);
    setIsSubmitting(true);

    const payload: VerificationPayload = {
      fields,
      action_plan: actionPlan,
      reviewer: currentUser.name,
      reviewed_at: new Date().toISOString(),
    };

    try {
      await submitVerification(docId, payload);

      const rawSession = sessionStorage.getItem("lextrace_session");

      const parsedSession = rawSession
        ? JSON.parse(rawSession)
        : null;

      const finalFields = finalizeFields(Object.values(fieldsById));
      const finalActionPlan = finalizeActionPlan(actionPlan);

      const verifiedSession = {
        docId,
        filename:
          parsedSession?.uploadResponse?.filename || "Judgment.pdf",
        verifiedAt: new Date().toISOString(),
        reviewer: currentUser.name,
        fields: finalFields,
        actionPlan: finalActionPlan,
      };

      sessionStorage.setItem(
        "lextrace_verified",
        JSON.stringify(verifiedSession),
      );

      router.push("/dashboard");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Verification could not be submitted.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="sticky bottom-0 border-t border-slate-200 bg-white/95 px-6 py-4 backdrop-blur">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-700">
            Submit the reviewed judgment once all items are verified.
          </p>
          {errorMessage ? (
            <p className="mt-1 text-sm text-rose-600">{errorMessage}</p>
          ) : null}
        </div>

        <button
          type="button"
          aria-label="Submit verified judgment"
          onClick={() => {
            void handleSubmit();
          }}
          disabled={!isReadyToSubmit || isSubmitting}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSubmitting ? "Submitting..." : "Done"}
        </button>
      </div>
    </div>
  );
}

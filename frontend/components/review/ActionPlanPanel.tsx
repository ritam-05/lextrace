"use client";

import { useEffect, useMemo, useState } from "react";

import { useReviewStore } from "@/store/reviewStore";
import type { ReviewStatus } from "@/types";

interface InlineReviewControlsProps {
  status: ReviewStatus;
  originalText: string;
  editedText?: string;
  onApprove: () => void;
  onEdit: (newText: string) => void;
  onReject: () => void;
}

function InlineReviewControls({
  status,
  originalText,
  editedText,
  onApprove,
  onEdit,
  onReject,
}: InlineReviewControlsProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState(editedText ?? originalText);

  useEffect(() => {
    if (!isEditing) {
      setDraftText(editedText ?? originalText);
    }
  }, [editedText, isEditing, originalText]);

  if (isEditing) {
    return (
      <div className="mt-2">
        <textarea
          value={draftText}
          onChange={(event) => {
            setDraftText(event.target.value);
          }}
          className="mt-2 w-full rounded-lg border border-slate-300 p-2 text-xs focus:outline-none focus:ring-1 focus:ring-slate-400"
          rows={2}
        />
        <div className="mt-2 flex justify-end gap-1.5">
          <button
            type="button"
            onClick={() => {
              onEdit(draftText);
              setIsEditing(false);
            }}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50"
          >
            Confirm
          </button>
          <button
            type="button"
            onClick={() => {
              setDraftText(editedText ?? originalText);
              setIsEditing(false);
            }}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (status !== "unreviewed" && status !== "edited") {
    return null;
  }

  return (
    <div className="mt-2 flex justify-end gap-1.5">
      <button
        type="button"
        onClick={onApprove}
        className="rounded-md border border-green-300 px-2 py-1 text-xs text-green-700 transition-colors hover:bg-green-50"
      >
        Approve
      </button>
      <button
        type="button"
        onClick={() => {
          setDraftText(editedText ?? originalText);
          setIsEditing(true);
        }}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50"
      >
        Edit
      </button>
      <button
        type="button"
        onClick={onReject}
        className="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 transition-colors hover:bg-red-50"
      >
        Reject
      </button>
    </div>
  );
}

function getBadgeTone(verifiedCount: number, totalCount: number): string {
  if (totalCount > 0 && verifiedCount === totalCount) {
    return "bg-green-100 text-green-700";
  }

  if (verifiedCount > 0) {
    return "bg-amber-100 text-amber-700";
  }

  return "bg-slate-100 text-slate-500";
}

function getRiskTone(consideration: string): string {
  const normalized = consideration.toUpperCase();
  if (normalized === "HIGH") {
    return "bg-red-100 text-red-700";
  }
  if (normalized === "MEDIUM") {
    return "bg-amber-100 text-amber-700";
  }
  return "bg-green-100 text-green-700";
}

function getRiskBarTone(score: number): string {
  if (score >= 7) {
    return "bg-red-500";
  }
  if (score >= 4) {
    return "bg-amber-500";
  }
  return "bg-green-500";
}

export default function ActionPlanPanel() {
  const actionPlan = useReviewStore((state) => state.actionPlan);
  const approveDirection = useReviewStore((state) => state.approveDirection);
  const editDirection = useReviewStore((state) => state.editDirection);
  const rejectDirection = useReviewStore((state) => state.rejectDirection);
  const approveComplianceStep = useReviewStore((state) => state.approveComplianceStep);
  const editComplianceStep = useReviewStore((state) => state.editComplianceStep);
  const rejectComplianceStep = useReviewStore((state) => state.rejectComplianceStep);
  const approveTimeline = useReviewStore((state) => state.approveTimeline);
  const editTimeline = useReviewStore((state) => state.editTimeline);
  const rejectTimeline = useReviewStore((state) => state.rejectTimeline);

  const [isOpen, setIsOpen] = useState(true);
  const [isContextOpen, setIsContextOpen] = useState(false);

  const totalActionItems = useMemo(() => {
    if (!actionPlan) {
      return 0;
    }

    return (
      actionPlan.key_directions.length +
      actionPlan.compliance_steps.length +
      actionPlan.timelines.length
    );
  }, [actionPlan]);

  const verifiedCount = useMemo(() => {
    if (!actionPlan) {
      return 0;
    }

    return [
      ...actionPlan.key_directions,
      ...actionPlan.compliance_steps,
      ...actionPlan.timelines,
    ].filter((item) => item.review_status !== "unreviewed").length;
  }, [actionPlan]);

  return (
    <section className="mt-4 space-y-3 border-t border-slate-200 pt-4">
      <button
        type="button"
        onClick={() => {
          setIsOpen((current) => !current);
        }}
        className="flex w-full cursor-pointer items-center justify-between py-1 text-left select-none"
      >
        <span className="text-sm font-semibold text-slate-700">
          AI Action Plan
        </span>
        <div className="flex items-center gap-2">
          <span
            className={[
              "rounded-full px-2 py-0.5 text-xs",
              getBadgeTone(verifiedCount, totalActionItems),
            ].join(" ")}
          >
            {verifiedCount} / {totalActionItems} reviewed
          </span>
          <svg
            className={[
              "h-4 w-4 text-slate-500 transition-transform",
              isOpen ? "rotate-180" : "",
            ].join(" ")}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </div>
      </button>

      {!actionPlan ? (
        <p className="py-3 text-center text-xs text-slate-400">
          Action plan not yet generated.
        </p>
      ) : null}

      {actionPlan && isOpen ? (
        <div className="space-y-4">
          {actionPlan.key_directions.length > 0 ? (
            <section>
              <div className="mb-2 flex items-center gap-1.5">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-slate-500"
                >
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                </svg>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                  Court Directives
                </h3>
              </div>

              {actionPlan.key_directions.map((direction, index) => (
                <div key={direction.id} className="mb-2 rounded-lg bg-slate-50 p-3">
                  <div className="flex items-start">
                    <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-medium text-slate-600">
                      {index + 1}
                    </div>
                    <p className="ml-2 flex-1 text-sm text-slate-800">
                      {direction.edited_text ?? direction.text}
                    </p>
                  </div>
                  <InlineReviewControls
                    status={direction.review_status}
                    onApprove={() => approveDirection(direction.id)}
                    onEdit={(text) => editDirection(direction.id, text)}
                    onReject={() => rejectDirection(direction.id)}
                    originalText={direction.text}
                    editedText={direction.edited_text}
                  />
                </div>
              ))}
            </section>
          ) : null}

          <section>
            <div className="mb-2 flex items-center gap-1.5">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-slate-500"
              >
                <path d="M9 11l3 3L22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Required Actions
              </h3>
            </div>

            {actionPlan.nature_of_action ? (
              <span className="mb-2 inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                {actionPlan.nature_of_action}
              </span>
            ) : null}

            <div className="mb-2 flex flex-wrap gap-1">
              {actionPlan.responsible_departments.length === 0 ? (
                <p className="text-xs italic text-slate-400">
                  Department: Not yet assigned
                </p>
              ) : (
                actionPlan.responsible_departments.map((department) => (
                  <span
                    key={department}
                    className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                  >
                    {department}
                  </span>
                ))
              )}
            </div>

            {actionPlan.compliance_steps.map((step, index) => (
              <div key={step.id} className="mb-2 rounded-lg bg-blue-50 p-3">
                <div className="flex items-start">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-200 text-xs font-medium text-blue-700">
                    {index + 1}
                  </div>
                  <p className="ml-2 flex-1 text-sm text-slate-800">
                    {step.edited_text ?? step.text}
                  </p>
                </div>
                <InlineReviewControls
                  status={step.review_status}
                  onApprove={() => approveComplianceStep(step.id)}
                  onEdit={(text) => editComplianceStep(step.id, text)}
                  onReject={() => rejectComplianceStep(step.id)}
                  originalText={step.text}
                  editedText={step.edited_text}
                />
              </div>
            ))}
          </section>

          <section>
            <div className="mb-2 flex items-center gap-1.5">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-amber-500"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Key Timelines
              </h3>
            </div>

            <div className="mb-2 flex items-start gap-1 rounded border border-amber-200 bg-amber-50 p-2">
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="mt-0.5 shrink-0 text-amber-500"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <p className="text-xs italic text-amber-700">
                These timelines apply to the judgment as a whole, not to any
                specific action step.
              </p>
            </div>

            {actionPlan.timelines.length === 0 ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs italic text-amber-600">
                  No specific timelines mentioned.
                </p>
              </div>
            ) : (
              actionPlan.timelines.map((timeline) => (
                <div
                  key={timeline.id}
                  className="mb-2 rounded-lg border border-amber-200 bg-amber-50 p-3"
                >
                  <div className="flex items-start">
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      className="mt-1 shrink-0 text-amber-400"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <p className="ml-1.5 text-sm font-medium text-slate-800">
                      {timeline.edited_text ?? timeline.text}
                    </p>
                    {timeline.related_step_index ? (
                      <span className="ml-2 rounded-full bg-white/70 px-2 py-0.5 text-xs text-amber-700">
                        Step {timeline.related_step_index}
                      </span>
                    ) : null}
                  </div>
                  <InlineReviewControls
                    status={timeline.review_status}
                    onApprove={() => approveTimeline(timeline.id)}
                    onEdit={(text) => editTimeline(timeline.id, text)}
                    onReject={() => rejectTimeline(timeline.id)}
                    originalText={timeline.text}
                    editedText={timeline.edited_text}
                  />
                </div>
              ))
            )}
          </section>

          <section>
            <div className="mb-2 flex items-center gap-1.5">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-slate-500"
              >
                <path d="M12 3v18" />
                <path d="M5 7h14" />
                <path d="M7 7c0 3-2 5-4 6 2 1 4 3 4 6" />
                <path d="M17 7c0 3 2 5 4 6-2 1-4 3-4 6" />
              </svg>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Appeal Consideration
              </h3>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              {actionPlan.appeal_analysis.risk_score === -1 ? (
                <div className="mb-2 rounded border border-green-200 bg-green-50 p-2">
                  <p className="text-xs font-medium text-green-700">
                    ✓ No Adverse Impact - Favorable to Government
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Appeal Risk:</span>
                    <span
                      className={[
                        "rounded-full px-2 py-0.5 text-xs",
                        getRiskTone(actionPlan.appeal_analysis.consideration),
                      ].join(" ")}
                    >
                      {actionPlan.appeal_analysis.consideration}
                    </span>
                  </div>

                  <div className="mb-2 mt-1 h-1.5 rounded-full bg-slate-200">
                    <div
                      className={[
                        "h-full rounded-full transition-all",
                        getRiskBarTone(actionPlan.appeal_analysis.risk_score),
                      ].join(" ")}
                      style={{
                        width: `${Math.max(0, Math.min(100, (actionPlan.appeal_analysis.risk_score / 10) * 100))}%`,
                      }}
                    />
                  </div>
                </>
              )}

              {actionPlan.appeal_analysis.justification.length > 0 ? (
                <>
                  <p className="mb-1 mt-2 text-xs text-slate-500">
                    Justification:
                  </p>
                  <div className="space-y-1">
                    {actionPlan.appeal_analysis.justification.map((point) => (
                      <div key={point} className="flex items-start gap-1">
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className="mt-0.5 shrink-0 text-slate-400"
                        >
                          <path d="m9 18 6-6-6-6" />
                        </svg>
                        <p className="text-xs text-slate-600">{point}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          </section>

          <div>
            <button
              type="button"
              onClick={() => {
                setIsContextOpen((current) => !current);
              }}
              className="mt-2 cursor-pointer text-xs text-slate-400 transition-colors hover:text-slate-600"
            >
              AI Analysis Summary {isContextOpen ? "▴" : "▾"}
            </button>
            {isContextOpen ? (
              <div className="mt-1 rounded bg-slate-50 p-3">
                <p className="text-xs italic leading-relaxed text-slate-600">
                  {actionPlan.llm_context || "No AI analysis summary provided."}
                </p>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

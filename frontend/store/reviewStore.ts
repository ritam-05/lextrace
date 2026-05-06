"use client";

import { create } from "zustand";
import type { ActionPlan, ReviewField } from "@/types";

interface ReviewStore {
  fields: Record<string, ReviewField>;
  actionPlan: ActionPlan | null;
  activeFieldId: string | null;
  isSubmitting: boolean;
  initFields: (fields: ReviewField[]) => void;
  initActionPlan: (plan: ActionPlan) => void;
  setActiveField: (id: string | null) => void;
  approveField: (fieldId: string) => void;
  editField: (fieldId: string, newValue: string) => void;
  rejectField: (fieldId: string) => void;
  approveDirection: (id: string) => void;
  editDirection: (id: string, newText: string) => void;
  rejectDirection: (id: string) => void;
  approveComplianceStep: (id: string) => void;
  editComplianceStep: (id: string, newText: string) => void;
  rejectComplianceStep: (id: string) => void;
  approveTimeline: (id: string) => void;
  editTimeline: (id: string, newText: string) => void;
  rejectTimeline: (id: string) => void;
  setSubmitting: (val: boolean) => void;
  totalFields: () => number;
  totalCount: () => number;
  verifiedCount: () => number;
  allVerified: () => boolean;
  flaggedFields: () => ReviewField[];
}

function isVerifiedItem(item: { review_status: string }): boolean {
  return item.review_status === "approved" || item.review_status === "edited";
}

function countReviewed(plan: ActionPlan | null): number {
  if (!plan) {
    return 0;
  }

  return [
    ...plan.key_directions,
    ...plan.compliance_steps,
    ...plan.timelines,
  ].filter(isVerifiedItem).length;
}

function countActionItems(plan: ActionPlan | null): number {
  if (!plan) {
    return 0;
  }

  return (
    plan.key_directions.length +
    plan.compliance_steps.length +
    plan.timelines.length
  );
}

export const useReviewStore = create<ReviewStore>((set, get) => ({
  fields: {},
  actionPlan: null,
  activeFieldId: null,
  isSubmitting: false,

  initFields: (fields) => {
    const nextFields = fields.reduce<Record<string, ReviewField>>(
      (accumulator, field) => {
        accumulator[field.fieldId] = field;
        return accumulator;
      },
      {},
    );

    set({ fields: nextFields });
  },

  initActionPlan: (plan) => {
    set({ actionPlan: plan });
  },

  setActiveField: (id) => {
    set({ activeFieldId: id });
  },

  approveField: (fieldId) => {
    set((state) => {
      const field = state.fields[fieldId];

      if (!field) {
        return state;
      }

      return {
        fields: {
          ...state.fields,
          [fieldId]: {
            ...field,
            review_status: "approved",
          },
        },
      };
    });
  },

  editField: (fieldId, newValue) => {
    set((state) => {
      const field = state.fields[fieldId];

      if (!field) {
        return state;
      }

      return {
        fields: {
          ...state.fields,
          [fieldId]: {
            ...field,
            review_status: "edited",
            edited_value: newValue,
          },
        },
      };
    });
  },

  rejectField: (fieldId) => {
    set((state) => {
      const field = state.fields[fieldId];

      if (!field) {
        return state;
      }

      return {
        fields: {
          ...state.fields,
          [fieldId]: {
            ...field,
            review_status: "rejected",
          },
        },
      };
    });
  },

  approveDirection: (id) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          key_directions: state.actionPlan.key_directions.map((direction) =>
            direction.id === id
              ? { ...direction, review_status: "approved" }
              : direction,
          ),
        },
      };
    });
  },

  editDirection: (id, newText) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          key_directions: state.actionPlan.key_directions.map((direction) =>
            direction.id === id
              ? {
                  ...direction,
                  review_status: "edited",
                  edited_text: newText,
                }
              : direction,
          ),
        },
      };
    });
  },

  rejectDirection: (id) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          key_directions: state.actionPlan.key_directions.map((direction) =>
            direction.id === id
              ? { ...direction, review_status: "rejected" }
              : direction,
          ),
        },
      };
    });
  },

  approveComplianceStep: (id) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          compliance_steps: state.actionPlan.compliance_steps.map((step) =>
            step.id === id
              ? { ...step, review_status: "approved" }
              : step,
          ),
        },
      };
    });
  },

  editComplianceStep: (id, newText) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          compliance_steps: state.actionPlan.compliance_steps.map((step) =>
            step.id === id
              ? {
                  ...step,
                  review_status: "edited",
                  edited_text: newText,
                }
              : step,
          ),
        },
      };
    });
  },

  rejectComplianceStep: (id) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          compliance_steps: state.actionPlan.compliance_steps.map((step) =>
            step.id === id
              ? { ...step, review_status: "rejected" }
              : step,
          ),
        },
      };
    });
  },

  approveTimeline: (id) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          timelines: state.actionPlan.timelines.map((timeline) =>
            timeline.id === id
              ? { ...timeline, review_status: "approved" }
              : timeline,
          ),
        },
      };
    });
  },

  editTimeline: (id, newText) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          timelines: state.actionPlan.timelines.map((timeline) =>
            timeline.id === id
              ? {
                  ...timeline,
                  review_status: "edited",
                  edited_text: newText,
                }
              : timeline,
          ),
        },
      };
    });
  },

  rejectTimeline: (id) => {
    set((state) => {
      if (!state.actionPlan) {
        return state;
      }

      return {
        actionPlan: {
          ...state.actionPlan,
          timelines: state.actionPlan.timelines.map((timeline) =>
            timeline.id === id
              ? { ...timeline, review_status: "rejected" }
              : timeline,
          ),
        },
      };
    });
  },

  setSubmitting: (val) => {
    set({ isSubmitting: val });
  },

  totalFields: () => {
    return Object.keys(get().fields).length;
  },

  totalCount: () => {
    const state = get();
    return Object.keys(state.fields).length + countActionItems(state.actionPlan);
  },

  verifiedCount: () => {
    const state = get();
    const verifiedFields = Object.values(state.fields).filter(
      (field) => field.review_status === "approved",
    ).length;

    return verifiedFields + countReviewed(state.actionPlan);
  },

  allVerified: () => {
    const total = get().totalCount();
    return total > 0 && get().verifiedCount() === total;
  },

  flaggedFields: () => {
    const state = get();
    return Object.values(state.fields).filter(
      (field) =>
        field.confidence < 0.85 || field.review_status === "unreviewed",
    );
  },
}));

"use client";

import { create } from "zustand";
import type { ActionPlanItem, ReviewField } from "@/types";

interface ReviewStore {
  fields: Record<string, ReviewField>;
  actionItems: Record<string, ActionPlanItem>;
  activeFieldId: string | null;
  isSubmitting: boolean;
  initFields: (fields: ReviewField[]) => void;
  initActionItems: (items: ActionPlanItem[]) => void;
  setActiveField: (id: string | null) => void;
  approveField: (fieldId: string) => void;
  editField: (fieldId: string, newValue: string) => void;
  rejectField: (fieldId: string) => void;
  approveActionItem: (itemId: string) => void;
  editActionItem: (itemId: string, newDirective: string) => void;
  rejectActionItem: (itemId: string) => void;
  setSubmitting: (val: boolean) => void;
  totalFields: () => number;
  totalCount: () => number;
  verifiedCount: () => number;
  allVerified: () => boolean;
  flaggedFields: () => ReviewField[];
}

export const useReviewStore = create<ReviewStore>((set, get) => ({
  fields: {},
  actionItems: {},
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

  initActionItems: (items) => {
    const nextActionItems = items.reduce<Record<string, ActionPlanItem>>(
      (accumulator, item) => {
        accumulator[item.itemId] = item;
        return accumulator;
      },
      {},
    );

    set({ actionItems: nextActionItems });
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

  approveActionItem: (itemId) => {
    set((state) => {
      const item = state.actionItems[itemId];

      if (!item) {
        return state;
      }

      return {
        actionItems: {
          ...state.actionItems,
          [itemId]: {
            ...item,
            review_status: "approved",
          },
        },
      };
    });
  },

  editActionItem: (itemId, newDirective) => {
    set((state) => {
      const item = state.actionItems[itemId];

      if (!item) {
        return state;
      }

      return {
        actionItems: {
          ...state.actionItems,
          [itemId]: {
            ...item,
            review_status: "edited",
            edited_directive: newDirective,
          },
        },
      };
    });
  },

  rejectActionItem: (itemId) => {
    set((state) => {
      const item = state.actionItems[itemId];

      if (!item) {
        return state;
      }

      return {
        actionItems: {
          ...state.actionItems,
          [itemId]: {
            ...item,
            review_status: "rejected",
          },
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
    return (
      Object.keys(state.fields).length + Object.keys(state.actionItems).length
    );
  },

  verifiedCount: () => {
    const state = get();
    const verifiedFields = Object.values(state.fields).filter(
      (field) => field.review_status !== "unreviewed",
    ).length;
    const verifiedActionItems = Object.values(state.actionItems).filter(
      (item) => item.review_status !== "unreviewed",
    ).length;

    return verifiedFields + verifiedActionItems;
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

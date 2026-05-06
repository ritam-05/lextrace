import type {
  ActionPlan,
  ComplianceStep,
  KeyDirection,
  ReviewField,
  TimelineEntry,
} from "@/types";

export interface VerifiedSession {
  docId: string;
  filename: string;
  verifiedAt: string;
  reviewer: string;
  fields: ReviewField[];
  actionPlan: ActionPlan;
}

export function getApprovedValue(field: ReviewField | undefined): string | null {
  if (!field) {
    return null;
  }

  return field.review_status === "edited"
    ? field.edited_value ?? field.value
    : field.value;
}

export function filterApproved<T extends { review_status: string }>(
  items: T[] | undefined | null,
): T[] {
  if (!items) {
    return [];
  }

  return items.filter(
    (item) =>
      item.review_status === "approved" || item.review_status === "edited",
  );
}

export function groupActionsByDepartment(
  actions: ComplianceStep[],
  departments: string[] | undefined,
): Array<{ department: string; actions: ComplianceStep[] }> {
  const trustedActions = filterApproved(actions);
  if (trustedActions.length === 0) {
    return [];
  }

  const normalizedDepartments = (departments ?? []).filter(
    (department) => department.trim().length > 0,
  );

  if (normalizedDepartments.length === 0) {
    return [{ department: "General Compliance", actions: trustedActions }];
  }

  if (normalizedDepartments.length === 1) {
    return [{ department: normalizedDepartments[0], actions: trustedActions }];
  }

  if (normalizedDepartments.length === trustedActions.length) {
    return trustedActions.map((action, index) => ({
      department: normalizedDepartments[index],
      actions: [action],
    }));
  }

  return [
    {
      department: normalizedDepartments.join(", "),
      actions: trustedActions,
    },
  ];
}

export function safeParseSession(rawSession: string | null): VerifiedSession | null {
  if (!rawSession) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawSession) as Partial<VerifiedSession>;

    if (
      typeof parsed.docId !== "string" ||
      typeof parsed.filename !== "string" ||
      typeof parsed.verifiedAt !== "string" ||
      typeof parsed.reviewer !== "string" ||
      !Array.isArray(parsed.fields) ||
      !parsed.actionPlan
    ) {
      return null;
    }

    return parsed as VerifiedSession;
  } catch {
    return null;
  }
}

export function getTrustedDirections(actionPlan: ActionPlan | undefined): KeyDirection[] {
  return filterApproved(actionPlan?.key_directions);
}

export function getTrustedComplianceSteps(
  actionPlan: ActionPlan | undefined,
): ComplianceStep[] {
  return filterApproved(actionPlan?.compliance_steps);
}

export function getTrustedTimelines(actionPlan: ActionPlan | undefined): TimelineEntry[] {
  return filterApproved(actionPlan?.timelines);
}

/**
 * Replace with real auth (NextAuth / Clerk) when ready.
 * Only this file and middleware.ts need to change.
 */
export interface User {
  name: string;
  role: "reviewer" | "department_head";
}

export const currentUser: User = {
  name: "Ananya Sharma",
  role: "reviewer",
};

export function hasAccess(route: "review" | "dashboard"): boolean {
  if (currentUser.role === "reviewer") {
    return route === "review";
  }

  if (currentUser.role === "department_head") {
    return route === "dashboard";
  }

  return false;
}

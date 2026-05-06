"use client";

import type { KeyDirection } from "@/types";
import { filterTrusted, getReviewedText } from "@/lib/dashboard-utils";

interface DirectivesSectionProps {
  directives: KeyDirection[];
}

export default function DirectivesSection({
  directives,
}: DirectivesSectionProps) {
  const trustedDirectives = filterTrusted(directives);

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-slate-900">
          Court Directives
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Verified operative directions extracted from the judgment.
        </p>
      </div>

      {trustedDirectives.length === 0 ? (
        <p className="text-sm text-slate-500">No verified directives available.</p>
      ) : (
        <ol className="space-y-4">
          {trustedDirectives.map((directive, index) => (
            <li key={directive.id} className="flex items-start gap-4">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                {index + 1}
              </span>
              <p className="pt-1 text-sm leading-6 text-slate-700">
                {getReviewedText(directive)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

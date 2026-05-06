"use client";

interface AppealLegendProps {
  className?: string;
}

const legendItems = [
  {
    label: "HIGH",
    description: "Strong appeal consideration. Escalate for legal review.",
    className: "border-red-200 bg-red-50 text-red-700",
    dotClassName: "bg-red-500",
  },
  {
    label: "MEDIUM",
    description: "Moderate appeal exposure. Review carefully before action.",
    className: "border-amber-200 bg-amber-50 text-amber-700",
    dotClassName: "bg-amber-500",
  },
  {
    label: "LOW",
    description: "Low appeal concern. Often favorable for implementation.",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    dotClassName: "bg-emerald-500",
  },
  {
    label: "UNKNOWN",
    description: "Insufficient appeal signals were available.",
    className: "border-slate-200 bg-slate-100 text-slate-700",
    dotClassName: "bg-slate-500",
  },
] as const;

export default function AppealLegend({ className = "" }: AppealLegendProps) {
  return (
    <aside
      className={[
        "w-full max-w-sm rounded-xl border border-slate-200 bg-white p-4 shadow-lg",
        className,
      ].join(" ")}
    >
      <div className="mb-4">
        <p className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
          Appeal Legend
        </p>
        <h2 className="mt-1 text-sm font-semibold text-slate-900">
          Possible Appeal Considerations
        </h2>
      </div>

      <div className="space-y-3">
        {legendItems.map((item) => (
          <div
            key={item.label}
            className={[
              "rounded-lg border px-3 py-3",
              item.className,
            ].join(" ")}
          >
            <div className="flex items-center gap-2">
              <span
                className={["h-2.5 w-2.5 rounded-full", item.dotClassName].join(" ")}
                aria-hidden="true"
              />
              <span className="text-xs font-semibold uppercase tracking-wide">
                {item.label}
              </span>
            </div>
            <p className="mt-2 text-xs leading-5">{item.description}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}

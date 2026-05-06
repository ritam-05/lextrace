"use client";

interface ProcessingStepperProps {
  currentStep: number;
  filename: string;
}

const steps = [
  { label: "Uploading file" },
  { label: "Reading PDF" },
  { label: "Extracting fields" },
  { label: "Generating action plan" },
  { label: "Ready for review" },
] as const;

function DocumentIcon() {
  return (
    <svg
      width={12}
      height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m5 12 4.2 4.2L19 6.5" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className="animate-spin"
      aria-hidden="true"
    >
      <path d="M21 12a9 9 0 1 1-9-9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DotIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
    </svg>
  );
}

function truncateFilename(filename: string): string {
  if (filename.length <= 35) {
    return filename;
  }

  return `${filename.slice(0, 32)}...`;
}

export default function ProcessingStepper({
  currentStep,
  filename,
}: ProcessingStepperProps) {
  return (
    <div className="w-full py-2">
      <div className="inline-flex items-center gap-1.5 mb-6 text-xs text-slate-500 bg-slate-100 rounded-full px-3 py-1">
        <DocumentIcon />
        <span>{`Processing: ${truncateFilename(filename)}`}</span>
      </div>

      <div className="flex flex-col gap-0">
        {steps.map((step, stepIndex) => {
          const isCompleted = stepIndex < currentStep - 1;
          const isCurrent = stepIndex === currentStep - 1;
          const isUpcoming = stepIndex > currentStep - 1;
          const isLast = stepIndex === steps.length - 1;

          return (
            <div key={step.label} className="flex items-start gap-3 relative">
              <div className="relative flex flex-col items-center">
                <div
                  className={[
                    "w-7 h-7 rounded-full flex items-center justify-center",
                    isCompleted
                      ? "bg-green-100 text-green-600"
                      : isCurrent
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-300",
                  ].join(" ")}
                >
                  {isCompleted ? (
                    <CheckIcon />
                  ) : isCurrent ? (
                    <SpinnerIcon />
                  ) : (
                    <DotIcon />
                  )}
                </div>

                {!isLast ? (
                  <div
                    className={[
                      "w-px flex-1 min-h-[24px] mt-1",
                      isCompleted ? "bg-green-300" : "bg-slate-200",
                    ].join(" ")}
                  />
                ) : null}
              </div>

              <div className={isLast ? "" : "pb-6"}>
                <p
                  className={[
                    "text-sm font-medium",
                    isCompleted
                      ? "text-slate-500"
                      : isCurrent
                        ? "text-slate-900"
                        : "text-slate-300",
                  ].join(" ")}
                >
                  {step.label}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

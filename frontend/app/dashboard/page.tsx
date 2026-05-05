export default function DashboardPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-16">
      <div className="w-full max-w-4xl rounded-3xl border border-border/70 bg-card/80 p-10 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
        <h1 className="font-sans text-3xl font-semibold tracking-tight text-foreground">
          Governance Dashboard
        </h1>
        <p className="mt-4 text-muted-foreground">
          Verified judgments and executive summaries will appear here.
        </p>
        {/* TODO: Replace with full dashboard in Step 7 */}
      </div>
    </main>
  );
}

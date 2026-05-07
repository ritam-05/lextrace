"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import UploadCard from "@/components/upload/UploadCard";

export default function HomePage() {
  const router = useRouter();
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    window.sessionStorage.removeItem("lextrace_verified");
    window.sessionStorage.removeItem("lextrace_session");
    window.sessionStorage.removeItem("lextrace_pdf_file");
  }, []);

  useEffect(() => {
    if (!uploadError) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setUploadError(null);
    }, 5_000);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [uploadError]);

  return (
    <main className="min-h-screen flex flex-col bg-slate-50">
      <section className="px-6 pb-10 pt-14">
        <div className="mx-auto w-full max-w-6xl text-center">
          <h1 className="text-5xl font-bold tracking-tight text-slate-900 font-[family-name:var(--font-geist-sans)]">
            LeXTrace
          </h1>
          <div className="mt-8 border-t border-slate-200" />
        </div>
      </section>

      <section className="flex flex-1 items-start justify-center px-6 pt-10">
        <div className="w-full max-w-4xl">
          {uploadError ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-red-700 text-sm flex items-start justify-between gap-3">
              <span>{uploadError}</span>
              <button
                type="button"
                onClick={() => setUploadError(null)}
                className="shrink-0 text-red-500 hover:text-red-700 transition-colors"
                aria-label="Dismiss error"
              >
                X
              </button>
            </div>
          ) : null}

          <div className="w-full rounded-2xl border border-slate-200 bg-white p-12 shadow-sm">
            <UploadCard
              onUploadSuccess={(docId) => {
                router.push(`/review/${docId}`);
              }}
              onUploadError={(msg) => setUploadError(msg)}
            />
          </div>
        </div>
      </section>

      <footer className="fixed bottom-0 left-0 right-0 text-center text-xs text-slate-400 py-3 bg-slate-50 border-t border-slate-100">
        For official government use only · LeXTrace MVP · Made by team Straw Hats
      </footer>
    </main>
  );
}

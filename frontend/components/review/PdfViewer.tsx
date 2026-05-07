"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { getConfidenceTier, getTierColors } from "@/lib/confidenceColor";
import { useReviewStore } from "@/store/reviewStore";
import type { PageDimensions, ReviewField } from "@/types";

import HighlightLayer, { type Highlight } from "./HighlightLayer";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const PAGE_GAP_PX = 24;
const FLASH_DURATION_MS = 1_400;
const LINE_GROUP_THRESHOLD_PX = 6;
const ACTIVE_UNDERLINE_COLOR = "#dc2626";

interface PdfViewerProps {
  fileDataUrl: string | null;
  pageDimensions: PageDimensions[];
  fields: ReviewField[];
  activeFieldId: string | null;
}

interface RelativeRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface TextLine {
  normalized: string;
  text: string;
  rect: RelativeRect;
}

interface HighlightMatch {
  rects: RelativeRect[];
}

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s/-]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function unionRects(rects: RelativeRect[]): RelativeRect {
  const left = Math.min(...rects.map((rect) => rect.left));
  const top = Math.min(...rects.map((rect) => rect.top));
  const right = Math.max(...rects.map((rect) => rect.left + rect.width));
  const bottom = Math.max(...rects.map((rect) => rect.top + rect.height));

  return {
    left,
    top,
    width: right - left,
    height: bottom - top,
  };
}

function overlapScore(query: string, candidate: string): number {
  if (!query || !candidate) {
    return 0;
  }

  if (candidate.includes(query)) {
    return 10 + Math.min(query.length / Math.max(candidate.length, 1), 1);
  }

  if (query.includes(candidate) && candidate.length >= 8) {
    return 8 + Math.min(candidate.length / Math.max(query.length, 1), 1);
  }

  const queryTokens = query.split(" ").filter((token) => token.length >= 3);
  const candidateTokens = new Set(
    candidate.split(" ").filter((token) => token.length >= 3),
  );

  if (queryTokens.length === 0 || candidateTokens.size === 0) {
    return 0;
  }

  let sharedTokens = 0;
  for (const token of queryTokens) {
    if (candidateTokens.has(token)) {
      sharedTokens += 1;
    }
  }

  const coverage = sharedTokens / queryTokens.length;
  if (coverage < 0.6) {
    return 0;
  }

  return coverage * 5;
}

function extractTextLines(pageElement: HTMLDivElement): TextLine[] {
  const textLayer = pageElement.querySelector(".react-pdf__Page__textContent");
  if (!textLayer) {
    return [];
  }

  const pageRect = pageElement.getBoundingClientRect();
  const spans = Array.from(
    textLayer.querySelectorAll("span"),
  ) as HTMLSpanElement[];

  const fragments = spans
    .map((span) => {
      const text = span.textContent?.trim();
      if (!text) {
        return null;
      }

      const rect = span.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        return null;
      }

      return {
        text,
        rect: {
          left: rect.left - pageRect.left,
          top: rect.top - pageRect.top,
          width: rect.width,
          height: rect.height,
        },
      };
    })
    .filter((fragment): fragment is NonNullable<typeof fragment> => Boolean(fragment));

  if (fragments.length === 0) {
    return [];
  }

  const lines: Array<{ top: number; texts: string[]; rects: RelativeRect[] }> = [];

  for (const fragment of fragments) {
    const existingLine = lines.find(
      (line) => Math.abs(line.top - fragment.rect.top) <= LINE_GROUP_THRESHOLD_PX,
    );

    if (existingLine) {
      existingLine.texts.push(fragment.text);
      existingLine.rects.push(fragment.rect);
      continue;
    }

    lines.push({
      top: fragment.rect.top,
      texts: [fragment.text],
      rects: [fragment.rect],
    });
  }

  lines.sort((left, right) => left.top - right.top);

  return lines.map((line) => ({
    normalized: normalizeText(line.texts.join(" ")),
    text: line.texts.join(" "),
    rect: unionRects(line.rects),
  }));
}

function findBestHighlightMatch(
  field: ReviewField,
  pageNumber: number,
  lines: TextLine[],
): HighlightMatch | null {
  const query = normalizeText(field.value ?? field.edited_value ?? "");
  if (!query) {
    return null;
  }

  let bestMatch: HighlightMatch | null = null;
  let bestScore = 0;

  for (let startIndex = 0; startIndex < lines.length; startIndex += 1) {
    const candidateLines: TextLine[] = [];
    const candidateTexts: string[] = [];

    for (
      let endIndex = startIndex;
      endIndex < Math.min(lines.length, startIndex + 3);
      endIndex += 1
    ) {
      const line = lines[endIndex];
      candidateLines.push(line);
      candidateTexts.push(line.text);

      const normalizedCandidate = normalizeText(candidateTexts.join(" "));
      const exactLineBonus = candidateLines.length === 1 ? 1.4 : 0;
      const compactWindowBonus = candidateLines.length === 2 ? 0.5 : 0;
      const score =
        overlapScore(query, normalizedCandidate) +
        (field.source_page === pageNumber ? 0.35 : 0) +
        exactLineBonus +
        compactWindowBonus;

      if (score > bestScore) {
        bestScore = score;
        bestMatch = {
          rects: candidateLines.map((candidateLine) => candidateLine.rect),
        };
      }
    }
  }

  return bestScore >= 3 ? bestMatch : null;
}

export default function PdfViewer({
  fileDataUrl,
  pageDimensions,
  fields,
  activeFieldId,
}: PdfViewerProps) {
  const setActiveField = useReviewStore((state) => state.setActiveField);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const pageHeightsRef = useRef<Record<number, number>>({});
  const flashTimeoutRef = useRef<number | null>(null);

  const [numPages, setNumPages] = useState(0);
  const [pageRenderWidth, setPageRenderWidth] = useState(720);
  const [renderedPages, setRenderedPages] = useState<Record<number, RelativeRect>>(
    {},
  );
  const [highlightsByPage, setHighlightsByPage] = useState<
    Record<number, Highlight[]>
  >({});
  const [flashPageNumber, setFlashPageNumber] = useState<number | null>(null);

  const pageDimensionMap = useMemo(() => {
    return pageDimensions.reduce<Record<number, PageDimensions>>((accumulator, page) => {
      accumulator[page.page_number] = page;
      return accumulator;
    }, {});
  }, [pageDimensions]);

  const activeField = useMemo(() => {
    if (!activeFieldId) {
      return null;
    }

    return fields.find((field) => field.fieldId === activeFieldId) ?? null;
  }, [activeFieldId, fields]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    const updateWidth = (): void => {
      const nextWidth = Math.max(320, Math.min(container.clientWidth - 40, 920));
      setPageRenderWidth(nextWidth);
    };

    updateWidth();

    const resizeObserver = new ResizeObserver(() => {
      updateWidth();
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    pageRefs.current = {};
    pageHeightsRef.current = {};
    setRenderedPages({});
    setHighlightsByPage({});
    setNumPages(0);
    setFlashPageNumber(null);
  }, [fileDataUrl]);

  useEffect(() => {
    const nextHighlightsByPage: Record<number, Highlight[]> = {};

    for (let pageNumber = 1; pageNumber <= numPages; pageNumber += 1) {
      const pageElement = pageRefs.current[pageNumber];
      if (!pageElement) {
        continue;
      }

      const lines = extractTextLines(pageElement);
      if (lines.length === 0) {
        continue;
      }

      const pageHighlights: Highlight[] = [];

      if (activeField) {
        const match = findBestHighlightMatch(activeField, pageNumber, lines);
        if (match) {
          pageHighlights.push(
            ...match.rects.map((rect, rectIndex) => ({
              fieldId: `${activeField.fieldId}::${rectIndex}`,
              targetFieldId: activeField.fieldId,
              kind: "rect" as const,
              rect,
              color: ACTIVE_UNDERLINE_COLOR,
              isActive: true,
            })),
          );
        }
      }

      if (pageHighlights.length > 0) {
        nextHighlightsByPage[pageNumber] = pageHighlights;
      }
    }

    setHighlightsByPage(nextHighlightsByPage);
  }, [activeField, numPages, pageRenderWidth, renderedPages]);

  const activeFieldPageNumber = useMemo(() => {
    if (!activeField) {
      return null;
    }

    for (const [pageNumber, pageHighlights] of Object.entries(highlightsByPage)) {
      if (
        pageHighlights.some(
          (highlight) => highlight.targetFieldId === activeField.fieldId,
        )
      ) {
        return Number(pageNumber);
      }
    }

    return activeField.source_page ?? null;
  }, [activeField, highlightsByPage]);

  useEffect(() => {
    if (!activeFieldId || !activeFieldPageNumber) {
      return;
    }

    const container = scrollContainerRef.current;
    const targetPage = pageRefs.current[activeFieldPageNumber];
    if (!container || !targetPage) {
      return;
    }

    const orderedPageNumbers = Object.keys(pageHeightsRef.current)
      .map(Number)
      .sort((left, right) => left - right);

    const measuredOffset = orderedPageNumbers
      .filter((pageNumber) => pageNumber < activeFieldPageNumber)
      .reduce((total, pageNumber) => {
        return total + (pageHeightsRef.current[pageNumber] ?? 0) + PAGE_GAP_PX;
      }, 0);

    const scrollTop =
      measuredOffset > 0 ? measuredOffset : Math.max(targetPage.offsetTop - 12, 0);

    container.scrollTo({
      top: scrollTop,
      behavior: "smooth",
    });

    setFlashPageNumber(activeFieldPageNumber);

    if (flashTimeoutRef.current) {
      window.clearTimeout(flashTimeoutRef.current);
    }

    flashTimeoutRef.current = window.setTimeout(() => {
      setFlashPageNumber((currentPage) =>
        currentPage === activeFieldPageNumber ? null : currentPage,
      );
    }, FLASH_DURATION_MS);
  }, [activeFieldId, activeFieldPageNumber]);

  useEffect(() => {
    return () => {
      if (flashTimeoutRef.current) {
        window.clearTimeout(flashTimeoutRef.current);
      }
    };
  }, []);

  if (!fileDataUrl) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <div className="max-w-md rounded-3xl border border-dashed border-slate-300 bg-white p-8 shadow-sm">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-400">
            PDF Viewer Unavailable
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            The extracted fields are available, but the PDF bytes are only kept in
            this browser session. Re-upload the judgment to restore the source
            viewer and line highlights.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div ref={scrollContainerRef} className="h-full overflow-y-auto px-5 py-6">
      <Document
        file={fileDataUrl}
        loading={
          <div className="rounded-3xl border border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500 shadow-sm">
            Loading PDF source...
          </div>
        }
        error={
          <div className="rounded-3xl border border-red-200 bg-white px-6 py-10 text-center text-sm text-red-600 shadow-sm">
            The uploaded PDF could not be rendered in the review panel.
          </div>
        }
        onLoadSuccess={({ numPages: loadedPages }) => {
          setNumPages(loadedPages);
        }}
      >
        <div className="mx-auto flex max-w-5xl flex-col gap-6">
          {Array.from({ length: numPages }, (_, index) => {
            const pageNumber = index + 1;
            const renderMetrics = renderedPages[pageNumber];
            const pageMetrics =
              pageDimensionMap[pageNumber] ??
              (renderMetrics
                ? {
                    page_number: pageNumber,
                    width: renderMetrics.width,
                    height: renderMetrics.height,
                  }
                : null);

            return (
              <div
                key={pageNumber}
                ref={(element) => {
                  pageRefs.current[pageNumber] = element;
                }}
                className={[
                  "relative mx-auto rounded-[28px] bg-white p-4 shadow-[0_20px_60px_rgba(15,23,42,0.12)] transition-all duration-300",
                  flashPageNumber === pageNumber
                    ? "ring-4 ring-blue-300 ring-offset-4 ring-offset-slate-100"
                    : "ring-1 ring-slate-200",
                ].join(" ")}
              >
                <div className="mb-3 flex items-center justify-between px-1 text-xs font-medium uppercase tracking-[0.16em] text-slate-400">
                  <span>Page {pageNumber}</span>
                  <span>
                    {highlightsByPage[pageNumber]?.length ?? 0} references
                  </span>
                </div>

                <div className="relative">
                  <Page
                    pageNumber={pageNumber}
                    width={pageRenderWidth}
                    renderAnnotationLayer={false}
                    renderTextLayer
                    onRenderSuccess={() => {
                      const pageElement = pageRefs.current[pageNumber];
                      const canvas = pageElement?.querySelector("canvas");

                      if (!pageElement || !canvas) {
                        return;
                      }

                      pageHeightsRef.current[pageNumber] = pageElement.offsetHeight;
                      setRenderedPages((currentPages) => ({
                        ...currentPages,
                        [pageNumber]: {
                          left: 0,
                          top: 0,
                          width: canvas.clientWidth,
                          height: canvas.clientHeight,
                        },
                      }));
                    }}
                  />

                  {renderMetrics ? (
                    <HighlightLayer
                      highlights={highlightsByPage[pageNumber] ?? []}
                      pdfWidth={pageMetrics?.width ?? renderMetrics.width}
                      pdfHeight={pageMetrics?.height ?? renderMetrics.height}
                      renderWidth={renderMetrics.width}
                      renderHeight={renderMetrics.height}
                      onHighlightClick={(fieldId) => {
                        setActiveField(fieldId);
                      }}
                    />
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </Document>
    </div>
  );
}

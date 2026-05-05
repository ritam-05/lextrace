"use client";

import { clampToPage, scaleBbox } from "@/lib/pdfCoords";
import type { BBox } from "@/types";

interface RectHighlight {
  kind: "rect";
  rect: {
    left: number;
    top: number;
    width: number;
    height: number;
  };
}

interface BBoxHighlight {
  kind: "bbox";
  bbox: BBox;
}

export type Highlight = {
  fieldId: string;
  targetFieldId: string;
  color: string;
  isActive: boolean;
} & (RectHighlight | BBoxHighlight);

interface HighlightLayerProps {
  highlights: Highlight[];
  pdfWidth: number;
  pdfHeight: number;
  renderWidth: number;
  renderHeight: number;
  onHighlightClick: (fieldId: string) => void;
}

export default function HighlightLayer({
  highlights,
  pdfWidth,
  pdfHeight,
  renderWidth,
  renderHeight,
  onHighlightClick,
}: HighlightLayerProps) {
  return (
    <div className="pointer-events-none absolute inset-0">
      {highlights.map((highlight) => {
        const scaledRect =
          highlight.kind === "bbox"
            ? clampToPage(
                scaleBbox(
                  highlight.bbox,
                  pdfWidth,
                  pdfHeight,
                  renderWidth,
                  renderHeight,
                ),
                renderWidth,
                renderHeight,
              )
            : clampToPage(highlight.rect, renderWidth, renderHeight);

        return (
          <button
            key={`${highlight.fieldId}-${scaledRect.left}-${scaledRect.top}`}
            type="button"
            onClick={() => {
              onHighlightClick(highlight.targetFieldId);
            }}
            className={[
              "confidence-highlight pointer-events-auto absolute rounded-sm transition-all duration-200",
              highlight.isActive
                ? "active shadow-[0_0_0_2px_rgba(22,101,52,0.16)]"
                : "hover:opacity-95",
            ].join(" ")}
            style={{
              left: scaledRect.left,
              top: scaledRect.top,
              width: scaledRect.width,
              height: scaledRect.height,
              color: highlight.color,
              background: "transparent",
              borderBottom: `${highlight.isActive ? 3 : 2}px solid ${highlight.color}`,
              opacity: highlight.isActive ? 1 : 0.82,
              boxShadow: highlight.isActive ? `0 0 0 2px rgba(22,101,52,0.16)` : "none",
            }}
            aria-label={`Highlight for ${highlight.targetFieldId}`}
          />
        );
      })}
    </div>
  );
}

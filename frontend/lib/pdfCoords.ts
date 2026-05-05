import type { BBox } from "@/types";

/**
 * Converts a PyMuPDF bounding box into react-pdf overlay coordinates.
 *
 * PyMuPDF uses a bottom-left origin while react-pdf renders with a top-left origin,
 * so the Y axis must be flipped before drawing a highlight.
 *
 * Example:
 * - bbox: { x0: 50, y0: 100, x1: 150, y1: 140 }
 * - pdfWidth: 600, pdfHeight: 800
 * - renderWidth: 300, renderHeight: 400
 * - result: { left: 25, top: 330, width: 50, height: 20 }
 */
export function scaleBbox(
  bbox: BBox,
  pdfWidth: number,
  pdfHeight: number,
  renderWidth: number,
  renderHeight: number,
): { left: number; top: number; width: number; height: number } {
  const scaleX = renderWidth / pdfWidth;
  const scaleY = renderHeight / pdfHeight;

  const left = bbox.x0 * scaleX;
  const top = (pdfHeight - bbox.y1) * scaleY;
  const width = (bbox.x1 - bbox.x0) * scaleX;
  const height = (bbox.y1 - bbox.y0) * scaleY;

  return { left, top, width, height };
}

/**
 * Ensures an overlay rectangle always stays inside the rendered page bounds.
 */
export function clampToPage(
  rect: ReturnType<typeof scaleBbox>,
  pageWidth: number,
  pageHeight: number,
): ReturnType<typeof scaleBbox> {
  const left = Math.max(0, Math.min(rect.left, pageWidth));
  const top = Math.max(0, Math.min(rect.top, pageHeight));
  const maxWidth = Math.max(0, pageWidth - left);
  const maxHeight = Math.max(0, pageHeight - top);
  const width = Math.max(0, Math.min(rect.width, maxWidth));
  const height = Math.max(0, Math.min(rect.height, maxHeight));

  return { left, top, width, height };
}

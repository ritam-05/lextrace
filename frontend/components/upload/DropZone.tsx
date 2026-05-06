"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

interface DropZoneProps {
  onFileSelect: (file: File) => void;
  isDisabled: boolean;
  selectedFile: File | null;
  validationError: string | null;
}

function formatFileSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function WarningIcon() {
  return (
    <svg
      width={12}
      height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-green-500 mb-2"
      aria-hidden="true"
    >
      <path d="m5 12 5 5L20 7" />
    </svg>
  );
}

export default function DropZone({
  onFileSelect,
  isDisabled,
  selectedFile,
  validationError,
}: DropZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleOpenPicker = (): void => {
    if (isDisabled) {
      return;
    }

    fileInputRef.current?.click();
  };

  const handleSelectedFile = (file: File | null): void => {
    if (!file) {
      return;
    }

    if (file.type !== "application/pdf") {
      return;
    }

    onFileSelect(file);
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>): void => {
    handleSelectedFile(event.target.files?.[0] ?? null);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (): void => {
    setIsDragOver(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragOver(false);
    handleSelectedFile(event.dataTransfer.files?.[0] ?? null);
  };

  const zoneClasses = isDragOver
    ? "border-slate-900 bg-slate-50"
    : selectedFile
      ? "border-green-400 bg-green-50"
      : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50";

  return (
    <div>
      <div
        onClick={handleOpenPicker}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          "relative flex flex-col items-center justify-center w-full rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200 min-h-[200px] p-8 text-center",
          zoneClasses,
          isDisabled ? "pointer-events-none opacity-50" : "",
        ].join(" ")}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={handleInputChange}
        />

        {!selectedFile ? (
          <>
            <svg
              width={48}
              height={48}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-slate-400 mb-3"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>

            <p className="text-sm font-medium text-slate-700 mb-1">
              Upload the judgment order for official review
            </p>
            <p className="text-xs text-slate-400">PDF only, up to 50MB.</p>
          </>
        ) : (
          <>
            <SuccessIcon />
            <p className="text-sm font-medium text-slate-800">
              {selectedFile.name}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              {formatFileSize(selectedFile.size)}
            </p>
            <p className="text-xs text-slate-400 mt-2">
              Click to choose a different file
            </p>
          </>
        )}
      </div>

      {validationError ? (
        <p className="mt-2 text-xs text-red-600 flex items-center gap-1">
          <WarningIcon />
          {validationError}
        </p>
      ) : null}
    </div>
  );
}

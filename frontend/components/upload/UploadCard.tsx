"use client";

import { useEffect, useRef, useState } from "react";
import { uploadDocument } from "@/lib/apiClient";
import type { ActionPlanItem, UploadResponse } from "@/types";
import DropZone from "./DropZone";
import ProcessingStepper from "./ProcessingStepper";

interface UploadCardProps {
  onUploadSuccess: (docId: string) => void;
  onUploadError: (message: string) => void;
}

interface CombinedUploadResponse {
  uploadResponse: UploadResponse;
  actionItems: ActionPlanItem[];
}

interface SessionPayload {
  uploadResponse: UploadResponse;
  actionItems: ActionPlanItem[];
  uploadedAt: string;
}

const MAX_FILE_SIZE_BYTES = 52_428_800;

async function fileToBase64(file: File): Promise<string> {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }

      reject(new Error("Failed to read the selected PDF file."));
    };
    reader.onerror = () => {
      reject(new Error("Failed to read the selected PDF file."));
    };
    reader.readAsDataURL(file);
  });
}

export default function UploadCard({
  onUploadSuccess,
  onUploadError,
}: UploadCardProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const timerIdsRef = useRef<number[]>([]);

  const clearTimers = (): void => {
    timerIdsRef.current.forEach((timerId) => window.clearTimeout(timerId));
    timerIdsRef.current = [];
  };

  useEffect(() => {
    return () => {
      clearTimers();
    };
  }, []);

  const resetState = (): void => {
    clearTimers();
    setSelectedFile(null);
    setValidationError(null);
    setIsProcessing(false);
    setCurrentStep(1);
    setUploadError(null);
  };

  const validateSelection = (): string | null => {
    if (!selectedFile) {
      return "Please select a PDF file first.";
    }

    if (selectedFile.type !== "application/pdf") {
      return "Only PDF files are accepted.";
    }

    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      return "File size must be 50MB or less.";
    }

    return null;
  };

  const startStepTimers = (): void => {
    clearTimers();
    setCurrentStep(1);
    timerIdsRef.current = [
      window.setTimeout(() => setCurrentStep(2), 1_500),
      window.setTimeout(() => setCurrentStep(3), 3_500),
      window.setTimeout(() => setCurrentStep(4), 5_500),
    ];
  };

  const handleUpload = async (): Promise<void> => {
    const error = validateSelection();
    setValidationError(error);

    if (error || !selectedFile) {
      return;
    }

    setUploadError(null);
    setIsProcessing(true);
    setCurrentStep(1);
    startStepTimers();

    try {
      const base64Pdf = await fileToBase64(selectedFile);
      window.sessionStorage.setItem("lextrace_pdf_file", base64Pdf);

      const result =
        (await uploadDocument(selectedFile)) as unknown as CombinedUploadResponse;

      if (!result?.uploadResponse?.doc_id) {
        throw new Error("The upload completed, but no document ID was returned.");
      }

      const sessionPayload: SessionPayload = {
        uploadResponse: result.uploadResponse,
        actionItems: result.actionItems ?? [],
        uploadedAt: new Date().toISOString(),
      };

      window.sessionStorage.setItem(
        "lextrace_session",
        JSON.stringify(sessionPayload),
      );

      clearTimers();
      setCurrentStep(5);

      window.setTimeout(() => {
        onUploadSuccess(result.uploadResponse.doc_id);
      }, 600);
    } catch (errorCaught) {
      clearTimers();
      const message =
        errorCaught instanceof Error
          ? errorCaught.message
          : "The judgment could not be processed at this time.";

      setIsProcessing(false);
      setCurrentStep(1);
      setUploadError(message);
      onUploadError(message);
    }
  };

  if (isProcessing) {
    return (
      <ProcessingStepper
        currentStep={currentStep}
        filename={selectedFile?.name ?? ""}
      />
    );
  }

  if (uploadError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 mt-4 text-red-700 text-sm text-center">
        <p>{uploadError}</p>
        <button
          type="button"
          onClick={resetState}
          className="mt-3 text-xs text-red-600 underline cursor-pointer"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div>
      <DropZone
        onFileSelect={(file) => {
          setSelectedFile(file);
          setValidationError(null);
        }}
        isDisabled={isProcessing}
        selectedFile={selectedFile}
        validationError={validationError}
      />

      <button
        type="button"
        onClick={handleUpload}
        disabled={!selectedFile || isProcessing}
        className="w-full mt-4 py-3 px-4 bg-slate-900 hover:bg-slate-700 text-white text-sm font-medium rounded-xl transition-colors duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Upload & Analyse Judgment
      </button>
    </div>
  );
}

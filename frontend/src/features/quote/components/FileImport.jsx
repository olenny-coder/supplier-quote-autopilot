import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui";

const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB

const SUPPORTED_EXTENSIONS = [".csv", ".pdf"];

function FileImport({ onUpload, isUploading = false }) {
  const inputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  const validateFile = (file) => {
    const filename = file.name.toLowerCase();

    const isSupported = SUPPORTED_EXTENSIONS.some((extension) =>
      filename.endsWith(extension)
    );

    if (!isSupported) {
      toast.error("Unsupported file type. Please upload a CSV or PDF file.");
      return false;
    }

    if (file.size > MAX_FILE_SIZE) {
      toast.error("File size cannot exceed 2 MB.");
      return false;
    }

    return true;
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];

    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!validateFile(file)) {
      if (inputRef.current) {
        inputRef.current.value = "";
      }
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    if (!validateFile(file)) return;

    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile || !onUpload) return;

    try {
      await onUpload(selectedFile);
      setSelectedFile(null);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    } catch {
      // Let the parent component handle the error toast.
    }
  };

  return (
    <div className="rounded-2xl border border-border-default bg-surface p-5 shadow-card">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary-soft-fg">
          <svg
            className="h-4.5 w-4.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-content">Import Quotes</h3>
          <p className="mt-0.5 text-xs text-muted">
            Bulk-import supplier quotes from a CSV or PDF document
          </p>
        </div>
      </div>

      <div
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.dataTransfer.dropEffect = "copy";
          setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragging(false);
        }}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative cursor-pointer rounded-xl border-2 border-dashed px-5 py-7 text-center transition ${
          dragging
            ? "border-primary bg-primary-soft/40"
            : selectedFile
            ? "border-success/50 bg-success-soft/30"
            : "border-border-strong hover:border-primary/50 hover:bg-surface-hover"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.pdf"
          onChange={handleFileChange}
          className="hidden"
        />

        {selectedFile ? (
          <div className="flex items-center justify-center gap-2">
            <svg
              className="h-4 w-4 text-success"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-sm font-medium text-content">
              {selectedFile.name}
            </span>
            <span className="text-xs text-subtle">
              ({(selectedFile.size / 1024).toFixed(1)} KB)
            </span>
          </div>
        ) : (
          <div>
            <svg
              className="mx-auto mb-2 h-7 w-7 text-subtle"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 14l-7 7m0 0l-7-7m7 7V3"
              />
            </svg>
            <p className="text-sm text-muted">
              <span className="font-medium text-primary">Click to browse</span>{" "}
              or drag &amp; drop
            </p>
            <p className="mt-1 text-xs text-subtle">CSV or PDF files (max 2 MB)</p>
          </div>
        )}
      </div>

      {selectedFile && (
        <div className="mt-4 flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedFile(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            Clear
          </Button>
          <Button
            type="button"
            size="sm"
            loading={isUploading}
            loadingText="Importing…"
            onClick={handleUpload}
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
              />
            </svg>
            Import Quotes
          </Button>
        </div>
      )}
    </div>
  );
}

export default FileImport;

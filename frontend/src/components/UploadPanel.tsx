import { type DragEvent, type ChangeEvent, useRef, useState } from "react";
import styles from "./UploadPanel.module.css";

interface Props {
  onUpload: (file: File) => void;
  isUploading: boolean;
}

export function UploadPanel({ onUpload, isUploading }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function validate(file: File): string | null {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return "Only PDF files are accepted.";
    }
    if (file.size > 50 * 1024 * 1024) {
      return "File must be under 50 MB.";
    }
    return null;
  }

  function handleFile(file: File) {
    const err = validate(file);
    if (err) {
      setValidationError(err);
      setSelectedFile(null);
    } else {
      setValidationError(null);
      setSelectedFile(file);
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function handleSubmit() {
    if (selectedFile) onUpload(selectedFile);
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>Analyze a Deal</h2>
        <p className={styles.subtitle}>
          Upload an investment memorandum or offering document. The system will
          extract metrics, research the market, score risk, and generate a
          structured investment memo.
        </p>
      </div>

      <div
        className={`${styles.dropzone} ${isDragging ? styles.dragging : ""} ${selectedFile ? styles.hasFile : ""}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        aria-label="Upload PDF"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className={styles.hiddenInput}
          onChange={handleChange}
        />
        {selectedFile ? (
          <div className={styles.fileInfo}>
            <span className={styles.fileIcon}>📄</span>
            <span className={styles.fileName}>{selectedFile.name}</span>
            <span className={styles.fileSize}>
              {(selectedFile.size / 1024).toFixed(0)} KB
            </span>
          </div>
        ) : (
          <div className={styles.placeholder}>
            <span className={styles.uploadIcon}>⬆</span>
            <p>Drag & drop a PDF here, or click to browse</p>
            <p className={styles.hint}>Max 50 MB · PDF only</p>
          </div>
        )}
      </div>

      {validationError && (
        <p className={styles.error}>{validationError}</p>
      )}

      <button
        className={styles.submitBtn}
        onClick={handleSubmit}
        disabled={!selectedFile || isUploading}
      >
        {isUploading ? (
          <span className={styles.spinner}>Uploading…</span>
        ) : (
          "Run Analysis"
        )}
      </button>
    </div>
  );
}

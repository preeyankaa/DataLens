import { useRef, useState } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import "./UploadSection.css";

const API_URL = "http://127.0.0.1:8000";
const ALLOWED = [".csv", ".tsv", ".txt", ".xlsx", ".xlsm"];
const MAX_SIZE = 10 * 1024 * 1024;

const friendlyError = (err) =>
  err.message === "Failed to fetch"
    ? "Could not connect to the backend. Make sure FastAPI is running."
    : err.message;

function UploadSection({ onUploadSuccess }) {
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [error, setError] = useState("");

  const busy = loading || sampleLoading;

  const handleFile = (selectedFile) => {
    setError("");

    if (!selectedFile) return;

    const name = selectedFile.name.toLowerCase();

    if (!ALLOWED.some((ext) => name.endsWith(ext))) {
      setFile(null);
      setError("Please select a CSV or Excel (.xlsx) file.");
      return;
    }

    if (selectedFile.size > MAX_SIZE) {
      setFile(null);
      setError("File size must be less than 10 MB.");
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/api/v1/datasets/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed. Please try again.");
      }

      onUploadSuccess({ ...data, filename: file.name });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSample = async () => {
    setSampleLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/v1/datasets/sample`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load the sample data.");
      }

      onUploadSuccess(data);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSampleLoading(false);
    }
  };

  return (
    <section className="upload-section" id="upload">
      <div className="section-heading">
        <span className="eyebrow">GET STARTED</span>
        <h2>Start with your dataset</h2>
        <p>Upload a CSV or Excel file and let DataLens check its quality.</p>
      </div>

      <div
        className="upload-box"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFile(e.dataTransfer.files[0]);
        }}
      >
        <div className="upload-icon">
          <UploadCloud size={28} />
        </div>

        <h3>Upload your file</h3>
        <p>Drag and drop your file here, or select it from your computer.</p>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.tsv,.txt,.xlsx,.xlsm,text/csv"
          hidden
          onChange={(e) => handleFile(e.target.files[0])}
        />

        <button
          className="upload-button"
          type="button"
          onClick={() => fileInputRef.current.click()}
          disabled={busy}
        >
          Choose file
        </button>

        <p className="upload-note">
          CSV or Excel (.xlsx) · Maximum size: 10 MB
        </p>

        {file && (
          <div className="selected-file">
            <FileSpreadsheet size={20} />
            <span>{file.name}</span>

            <button
              type="button"
              onClick={() => {
                setFile(null);
                setError("");
                fileInputRef.current.value = "";
              }}
            >
              Remove
            </button>
          </div>
        )}

        {file && (
          <button
            className="primary-button"
            type="button"
            onClick={handleUpload}
            disabled={busy}
          >
            {loading ? "Uploading..." : "Upload and analyze"}
            {!loading && <ArrowRight size={17} />}
          </button>
        )}

        {error && <p className="upload-error">{error}</p>}

        <div className="upload-sample">
          <span>No file handy?</span>
          <button
            type="button"
            className="upload-sample-button"
            onClick={handleSample}
            disabled={busy}
          >
            <Sparkles size={15} />
            {sampleLoading ? "Loading sample..." : "Try with sample data"}
          </button>
          <small>
            A small shop's sales file with missing values, duplicates and
            messy spellings, so you can try the full flow.
          </small>
        </div>
      </div>
    </section>
  );
}

export default UploadSection;
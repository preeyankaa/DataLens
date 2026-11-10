import DatasetOverview from "./DatasetOverview";
import CleaningSection from "./CleaningSection";

import { useRef, useState } from "react";
import { UploadCloud, FileSpreadsheet, ArrowRight } from "lucide-react";


function UploadSection() {
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const handleFile = (selectedFile) => {
    setError("");
    setResult(null);

    if (!selectedFile) return;

    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Please select a CSV file.");
      return;
    }

    if (selectedFile.size > 10 * 1024 * 1024) {
      setFile(null);
      setError("File size must be less than 10 MB.");
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "http://127.0.0.1:8000/api/v1/datasets/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed. Please try again.");
      }

      setResult(data);
    } catch (err) {
      setError(
        err.message === "Failed to fetch"
          ? "Could not connect to the backend. Make sure FastAPI is running."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="upload-section" id="upload">
      <div className="section-heading">
        <span className="eyebrow">GET STARTED</span>
        <h2>Start with your dataset</h2>
        <p>Upload a CSV file and let DataLens check its quality.</p>
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

        <h3>Upload your CSV file</h3>
        <p>Drag and drop your file here, or select it from your computer.</p>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => handleFile(e.target.files[0])}
        />

        <button
          className="upload-button"
          type="button"
          onClick={() => fileInputRef.current.click()}
        >
          Choose CSV file
        </button>

        <p className="upload-note">CSV format · Maximum size: 10 MB</p>

        {file && (
          <div className="selected-file">
            <FileSpreadsheet size={20} />
            <span>{file.name}</span>
            <button
              type="button"
              onClick={() => {
                setFile(null);
                setResult(null);
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
            disabled={loading}
          >
            {loading ? "Uploading..." : "Upload and analyze"}
            {!loading && <ArrowRight size={17} />}
          </button>
        )}

        {error && <p className="upload-error">{error}</p>}

        {result && (
        <>
            <DatasetOverview profile={result.profile} />

            <CleaningSection
            datasetId={result.dataset_id}
            profile={result.profile}
            />
        </>
        )}
      </div>
    </section>
  );
}

export default UploadSection;

import { useState } from "react";
import {
  WandSparkles,
  Download,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

function CleaningSection({ datasetId, profile }) {
  const columns = profile?.columns || {};
  const statistics = profile?.numerical_statistics || {};

  const missingColumns = Object.entries(columns).filter(
    ([, details]) => details.missing_count > 0
  );

  const numericalColumns = Object.keys(statistics).filter(
    (name) => !name.toLowerCase().endsWith("_id")
  );

  const [removeDuplicates, setRemoveDuplicates] = useState(true);

  const [selectedMissing, setSelectedMissing] = useState(() => {
    const initial = {};

    Object.entries(columns).forEach(([name, details]) => {
      if (details.missing_count > 0) {
        initial[name] = {
          enabled: true,
          strategy:
            details.data_type === "object" || details.data_type === "str"
              ? "mode"
              : "median",
        };
      }
    });

    return initial;
  });

  const [selectedOutliers, setSelectedOutliers] = useState([]);

  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const [cleanedReady, setCleanedReady] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const buildPayload = () => {
    const missingValues = {};

    Object.entries(selectedMissing).forEach(([name, settings]) => {
      if (settings.enabled) {
        missingValues[name] = {
          strategy: settings.strategy,
        };
      }
    });

    return {
      remove_duplicates: removeDuplicates,
      missing_values: missingValues,
      outlier_columns: selectedOutliers,
    };
  };

  const resetCleaningStatus = () => {
    setPreview(null);
    setCleanedReady(false);
    setSuccess("");
    setError("");
  };

  const handleMissingToggle = (name) => {
    setSelectedMissing((current) => ({
      ...current,
      [name]: {
        ...current[name],
        enabled: !current[name].enabled,
      },
    }));

    resetCleaningStatus();
  };

  const handleStrategyChange = (name, strategy) => {
    setSelectedMissing((current) => ({
      ...current,
      [name]: {
        ...current[name],
        strategy,
      },
    }));

    resetCleaningStatus();
  };

  const handleOutlierToggle = (name) => {
    setSelectedOutliers((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name]
    );

    resetCleaningStatus();
  };

  const handlePreview = async () => {
    setLoading(true);
    setError("");
    setSuccess("");
    setPreview(null);
    setCleanedReady(false);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/v1/datasets/${datasetId}/clean/preview`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(buildPayload()),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Could not generate cleaning preview."
        );
      }

      setPreview(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  // Save the cleaned dataset in the backend
  const handleApplyCleaning = async () => {
    setApplying(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/v1/datasets/${datasetId}/clean/apply`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(buildPayload()),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Could not apply cleaning."
        );
      }

      setCleanedReady(true);
      setSuccess(
        "Cleaning applied successfully. Your cleaned dataset is ready for AI questions."
      );
    } catch (err) {
      setError(err.message || "Could not apply cleaning.");
    } finally {
      setApplying(false);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/v1/datasets/${datasetId}/clean/download`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(buildPayload()),
        }
      );

      if (!response.ok) {
        let message = "Could not download the cleaned dataset.";

        try {
          const data = await response.json();
          if (typeof data.detail === "string") {
            message = data.detail;
          }
        } catch {
          // Keep default error message.
        }

        throw new Error(message);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = "datalens-cleaned.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
      setSuccess("Your cleaned CSV has been downloaded.");
    } catch (err) {
      setError(err.message || "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <section className="cleaning-section" id="cleaning">
      <div className="cleaning-heading">
        <span className="eyebrow">DATA PREPARATION</span>
        <h2>Clean your dataset</h2>
        <p>
          Choose how you want to handle data quality issues.
          Preview the changes before applying them to your dataset.
        </p>
      </div>

      <div className="cleaning-options">
        <div className="cleaning-card">
          <div className="cleaning-card-heading">
            <div>
              <h3>Remove duplicate rows</h3>
              <p>Remove repeated records from your dataset.</p>
            </div>

            <label className="cleaning-toggle">
              <input
                type="checkbox"
                checked={removeDuplicates}
                onChange={(e) => {
                  setRemoveDuplicates(e.target.checked);
                  resetCleaningStatus();
                }}
              />
              <span />
            </label>
          </div>

          <div className="cleaning-divider" />

          <h3>Handle missing values</h3>
          <p>Select columns and choose a filling strategy.</p>

          {missingColumns.length > 0 ? (
            missingColumns.map(([name, details]) => (
              <div className="cleaning-column-row" key={name}>
                <label className="cleaning-column-label">
                  <input
                    type="checkbox"
                    checked={selectedMissing[name]?.enabled ?? false}
                    onChange={() => handleMissingToggle(name)}
                  />
                  <span>
                    <strong>{name}</strong>
                    <small>{details.missing_count} missing values</small>
                  </span>
                </label>

                <select
                  value={selectedMissing[name]?.strategy || "median"}
                  disabled={!selectedMissing[name]?.enabled}
                  onChange={(e) =>
                    handleStrategyChange(name, e.target.value)
                  }
                >
                  {["int64", "float64", "int", "float"].includes(
                    details.data_type
                  ) ? (
                    <>
                      <option value="median">Median</option>
                      <option value="mean">Mean</option>
                      <option value="mode">Mode</option>
                    </>
                  ) : (
                    <option value="mode">Mode</option>
                  )}
                </select>
              </div>
            ))
          ) : (
            <p>No missing values detected.</p>
          )}

          <div className="cleaning-divider" />

          <h3>Handle outliers</h3>
          <p>Choose numerical columns for IQR-based clipping.</p>

          {numericalColumns.length > 0 ? (
            numericalColumns.map((name) => (
              <label className="cleaning-checkbox-row" key={name}>
                <input
                  type="checkbox"
                  checked={selectedOutliers.includes(name)}
                  onChange={() => handleOutlierToggle(name)}
                />
                <span>{name}</span>
              </label>
            ))
          ) : (
            <p>No suitable numerical columns found.</p>
          )}
        </div>

        <div className="cleaning-action-card">
          <div className="cleaning-action-icon">
            <WandSparkles size={24} />
          </div>

          <h3>Ready to clean?</h3>
          <p>
            Generate a preview to see how your dataset will change
            with the selected options.
          </p>

          <button
            className="primary-button"
            type="button"
            onClick={handlePreview}
            disabled={loading || applying}
          >
            {loading ? (
              <>
                <RefreshCw size={17} className="spin-icon" />
                Generating preview...
              </>
            ) : (
              <>
                Preview changes
                <WandSparkles size={17} />
              </>
            )}
          </button>

          <p className="cleaning-note">
            Previewing does not overwrite your original dataset.
          </p>
        </div>
      </div>

      {error && (
        <div className="cleaning-message error-message">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {success && (
        <div className="cleaning-message success-message">
          <CheckCircle2 size={18} />
          {success}
        </div>
      )}

      {preview && (
        <div className="cleaning-preview">
          <div className="cleaning-preview-heading">
            <div>
              <span className="eyebrow">PREVIEW RESULTS</span>
              <h3>Before and after cleaning</h3>
              <p>Review the changes before applying them.</p>
            </div>

            <span className="dataset-status">
              {cleanedReady ? "Cleaning applied" : "Preview ready"}
            </span>
          </div>

          <div className="cleaning-comparison">
            <div className="comparison-card">
              <span>Before</span>
              <strong>{preview.before.rows}</strong>
              <small>Rows</small>
              <p>{preview.before.missing_values} missing values</p>
              <p>{preview.before.duplicate_rows} duplicate rows</p>
            </div>

            <div className="comparison-card after-card">
              <span>After</span>
              <strong>{preview.after.rows}</strong>
              <small>Rows</small>
              <p>{preview.after.missing_values} missing values</p>
              <p>{preview.after.duplicate_rows} duplicate rows</p>
            </div>
          </div>

          <div className="detail-card">
            <h3>Changes made</h3>

            {Object.keys(preview.changes || {}).length > 0 ? (
              <div className="cleaning-changes">
                {Object.entries(preview.changes).map(([name, value]) => (
                  <div className="detail-row" key={name}>
                    <span>{name.replaceAll("_", " ")}</span>
                    <strong>
                      {typeof value === "object"
                        ? Object.entries(value)
                            .map(([key, val]) => `${key}: ${val}`)
                            .join(" · ")
                        : String(value)}
                    </strong>
                  </div>
                ))}
              </div>
            ) : (
              <p>No changes were made with the selected options.</p>
            )}
          </div>

          {preview.preview?.length > 0 && (
            <div className="detail-card">
              <h3>Cleaned data preview</h3>

              <div className="table-scroll">
                <table className="dataset-table">
                  <thead>
                    <tr>
                      {Object.keys(preview.preview[0]).map((key) => (
                        <th key={key}>{key}</th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {preview.preview.map((row, index) => (
                      <tr key={index}>
                        {Object.keys(preview.preview[0]).map((key) => (
                          <td key={key}>{row[key] ?? "—"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="cleaning-buttons">
            <button
              className="primary-button"
              type="button"
              onClick={handleApplyCleaning}
              disabled={applying || cleanedReady}
            >
              {applying ? (
                <>
                  <RefreshCw size={17} className="spin-icon" />
                  Applying cleaning...
                </>
              ) : cleanedReady ? (
                <>
                  <CheckCircle2 size={17} />
                  Cleaning applied
                </>
              ) : (
                <>
                  <WandSparkles size={17} />
                  Apply cleaning
                </>
              )}
            </button>

            <button
              className="primary-button download-cleaned-button"
              type="button"
              onClick={handleDownload}
              disabled={downloading}
            >
              <Download size={18} />
              {downloading ? "Preparing download..." : "Download cleaned CSV"}
            </button>
          </div>

          {cleanedReady && (
            <p className="cleaning-note">
              Your cleaned dataset is saved and available in AI Questions.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default CleaningSection;

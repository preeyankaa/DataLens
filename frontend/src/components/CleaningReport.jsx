import { useCallback, useEffect, useRef, useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  Info,
  Download,
  RefreshCw,
} from "lucide-react";
import "./CleaningReport.css";

const API_URL = "http://127.0.0.1:8000";

const format = (value) => {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
};

function StatCard({ label, before, after, goodWhenLower = false }) {
  const diff = after - before;
  const improved = goodWhenLower ? diff < 0 : false;

  return (
    <div className="crep-stat">
      <span>{label}</span>
      <div className="crep-stat-values">
        <strong>{format(before)}</strong>
        <em>to</em>
        <strong>{format(after)}</strong>
      </div>
      <small className={improved ? "crep-good" : ""}>
        {diff === 0 ? "No change" : `${diff > 0 ? "+" : ""}${format(diff)}`}
      </small>
    </div>
  );
}

export default function CleaningReport({ datasetId }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const lastStamp = useRef(null);

  const load = useCallback(
    async (showSpinner = false) => {
      if (!datasetId) return;
      if (showSpinner) setLoading(true);

      try {
        const response = await fetch(
          `${API_URL}/api/v1/datasets/${datasetId}/clean/report`
        );
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || "Unable to load the cleaning report.");
        }

        const stamp = data.available ? data.applied_at : "none";
        if (stamp !== lastStamp.current || showSpinner) {
          lastStamp.current = stamp;
          setReport(data.available ? data : null);
        }
        setError("");
      } catch (err) {
        setError(err.message || "Something went wrong.");
      } finally {
        if (showSpinner) setLoading(false);
      }
    },
    [datasetId]
  );

  useEffect(() => {
    lastStamp.current = null;
    load(true);
    // pick up a newly applied cleaning without a manual refresh
    const timer = setInterval(() => load(false), 5000);
    return () => clearInterval(timer);
  }, [load]);

  const download = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "datalens_cleaning_report.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="crep">
      <div className="crep-heading">
        <div>
          <span className="crep-eyebrow">
            <ShieldCheck size={14} /> VERIFY YOUR CLEANING
          </span>
          <h3>Cleaning report</h3>
          <p>
            See exactly what changed, with real examples, so nothing is altered
            without you knowing.
          </p>
        </div>

        <div className="crep-actions">
          <button type="button" onClick={() => load(true)} disabled={loading}>
            <RefreshCw size={14} className={loading ? "crep-spin" : ""} />
            Refresh
          </button>
          {report && (
            <button type="button" onClick={download}>
              <Download size={14} />
              Download report
            </button>
          )}
        </div>
      </div>

      {error && <div className="crep-error">{error}</div>}

      {!report && !error && (
        <div className="crep-empty">
          <Info size={22} />
          <p>
            Apply cleaning above and the report will appear here with before
            and after numbers.
          </p>
        </div>
      )}

      {report && (
        <>
          <div className="crep-stats">
            <StatCard
              label="Rows"
              before={report.rows.before}
              after={report.rows.after}
            />
            <StatCard
              label="Empty cells"
              before={report.missing_cells.before}
              after={report.missing_cells.after}
              goodWhenLower
            />
            <StatCard
              label="Duplicate rows"
              before={report.duplicate_rows.before}
              after={report.duplicate_rows.after}
              goodWhenLower
            />
          </div>

          {report.assumptions?.length > 0 && (
            <div className="crep-block">
              <h4>Please check these assumptions</h4>
              {report.assumptions.map((item, i) => (
                <div
                  className={`crep-note crep-${item.level}`}
                  key={i}
                >
                  {item.level === "warning" ? (
                    <AlertTriangle size={16} />
                  ) : (
                    <Info size={16} />
                  )}
                  <div>
                    <strong>{item.column}</strong>
                    <p>{item.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {report.column_checks?.length > 0 && (
            <div className="crep-block">
              <h4>Did any totals change?</h4>
              <p className="crep-sub">
                Compare column totals before and after cleaning. Money should not
                disappear unless you removed rows or filled values.
              </p>
              <div className="crep-table-wrap">
                <table className="crep-table">
                  <thead>
                    <tr>
                      <th>Column</th>
                      <th>Total before</th>
                      <th>Total after</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.column_checks.map((check) => (
                      <tr key={check.column} className={check.flag ? "crep-flag" : ""}>
                        <td>{check.column}</td>
                        <td>{format(check.before_total)}</td>
                        <td>{format(check.after_total)}</td>
                        <td title={check.note}>
                          {check.change_pct > 0 ? "+" : ""}
                          {format(check.change_pct)}%
                          {check.flag && <AlertTriangle size={13} />}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="crep-block">
            <h4>What was changed</h4>
            {report.change_log.length === 0 ? (
              <p className="crep-sub">No changes were made.</p>
            ) : (
              report.change_log.map((entry, i) => (
                <div className="crep-log" key={i}>
                  <div className="crep-log-head">
                    <strong>{entry.column}</strong>
                    <span>{entry.action}</span>
                  </div>
                  <p>{entry.detail}</p>

                  {entry.examples?.length > 0 && (
                    <table className="crep-examples">
                      <thead>
                        <tr>
                          <th>CSV row</th>
                          <th>Before</th>
                          <th>After</th>
                        </tr>
                      </thead>
                      <tbody>
                        {entry.examples.map((example, k) => (
                          <tr key={k}>
                            <td>{example.row}</td>
                            <td>{example.before}</td>
                            <td>{example.after}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))
            )}
          </div>

          <p className="crep-foot">
            Your original upload is never modified. Cleaned on {report.applied_at}.
          </p>
        </>
      )}
    </section>
  );
}
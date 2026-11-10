import {
  FileSpreadsheet,
  AlertTriangle,
  Sparkles,
} from "lucide-react";

function DatasetPreview() {
  return (
    <div className="preview-area">
      <div className="preview-glow"></div>

      <div className="preview-card">
        <div className="preview-top">
          <div className="file-heading">
            <span className="file-icon">
              <FileSpreadsheet size={19} />
            </span>
            <div>
              <strong>sales_data.csv</strong>
              <small>52,341 rows · 18 columns</small>
            </div>
          </div>
          <span className="status-pill">Sample</span>
        </div>

        <div className="health-panel">
          <div>
            <span className="panel-label">Dataset Health</span>
            <div className="health-score">
              74<span>/100</span>
            </div>
            <small className="issue-count">12 sample issues found</small>
          </div>

          <div className="score-ring">
            <div className="score-ring-inner">
              <strong>74</strong>
              <small>Score</small>
            </div>
          </div>
        </div>

        <div className="preview-divider"></div>

        <div className="quality-heading">
          <strong>Data quality overview</strong>
          <span>Illustrative preview</span>
        </div>

        <div className="quality-row">
          <div className="quality-title">
            <span>
              <AlertTriangle size={15} />
              Missing values
            </span>
            <strong>8.4%</strong>
          </div>

          <div className="progress-track">
            <div className="progress-fill missing-fill"></div>
          </div>

          <small>customer_age · rating · discount_pct · email</small>
        </div>

        <div className="quality-stats">
          <div className="mini-stat">
            <strong>1,842</strong>
            <span>Duplicates</span>
          </div>
          <div className="mini-stat">
            <strong>3.7%</strong>
            <span>Outliers</span>
          </div>
          <div className="mini-stat">
            <strong>18</strong>
            <span>Columns</span>
          </div>
        </div>

        <div className="insight-box">
          <span className="insight-icon"><Sparkles size={16} /></span>
          <div>
            <strong>Example insight</strong>
            <p>Mumbai generates the highest revenue in this sample dataset.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DatasetPreview;
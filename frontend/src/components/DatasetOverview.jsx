
function DatasetOverview({ profile }) {
  if (!profile?.overview) return null;

  const overview = profile.overview;
  const columns = profile.columns || {};
  const preview = profile.preview || [];
  const statistics = profile.numerical_statistics || {};

  const formatNumber = (value) =>
    Number(value || 0).toLocaleString("en-IN");

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  };

  const issues = [];

  Object.entries(columns).forEach(([name, details]) => {
    if (details.missing_count > 0) {
      issues.push({
        title: `Missing values in ${name}`,
        description: `${details.missing_count} missing values (${details.missing_percentage}%).`,
      });
    }
  });

  Object.entries(statistics).forEach(([name, stats]) => {
    if (stats.min < 0) {
      issues.push({
        title: `Negative values in ${name}`,
        description: `Minimum value is ${stats.min}. Review whether negative values are valid.`,
      });
    }

    if (name.toLowerCase().includes("age") && stats.max > 120) {
      issues.push({
        title: `Unusually high values in ${name}`,
        description: `Maximum value is ${stats.max}. Review possible invalid ages.`,
      });
    }
  });

  const salesColumn = columns.sales_amount;
  if (salesColumn?.data_type === "str") {
    issues.push({
      title: "Check sales_amount data type",
      description: "This column is stored as text. Check whether it can be converted to numeric values.",
    });
  }

  const invalidDatePreview = preview.some((row) => {
    const value = row.order_date;
    return value && Number.isNaN(Date.parse(value));
  });

  if (invalidDatePreview) {
    issues.push({
      title: "Check order_date format",
      description: "An invalid date was found in the displayed preview. Review date values in the dataset.",
    });
  }

  const metrics = [
    { label: "Total rows", value: formatNumber(overview.total_rows) },
    { label: "Total columns", value: formatNumber(overview.total_columns) },
    { label: "Missing cells", value: formatNumber(overview.missing_cells) },
    { label: "Duplicate rows", value: formatNumber(overview.duplicate_rows) },
  ];

  return (
    <section className="dataset-overview">
      <div className="overview-header">
        <div>
          <span className="eyebrow">DATASET REPORT</span>
          <h2>Dataset Overview</h2>
          <p>Here's what we found in your uploaded dataset.</p>
        </div>
        <span className="dataset-status">Analysis complete</span>
      </div>

      <div className="overview-metrics">
        {metrics.map((metric) => (
          <div className="overview-card" key={metric.label}>
            <p>{metric.label}</p>
            <h3>{metric.value}</h3>
          </div>
        ))}
      </div>

      <div className="overview-details">
        <div className="detail-card">
          <h3>Dataset health information</h3>

          <div className="detail-row">
            <span>Missing values</span>
            <strong>{overview.missing_percentage}%</strong>
          </div>

          <div className="detail-row">
            <span>Total cells</span>
            <strong>{formatNumber(overview.total_cells)}</strong>
          </div>

          <div className="detail-row">
            <span>Memory usage</span>
            <strong>{formatBytes(overview.memory_usage_bytes)}</strong>
          </div>
        </div>

        <div className="detail-card">
          <h3>Issues found</h3>
          <div className="issue-summary">
            <strong>{issues.length}</strong>
            <span>items to review</span>
          </div>
          <p>Review the detected data quality issues before cleaning.</p>
        </div>
      </div>

      <div className="detail-card column-card">
        <h3>Column information</h3>
        <div className="table-scroll">
          <table className="dataset-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Data type</th>
                <th>Missing</th>
                <th>Unique values</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(columns).map(([name, details]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{details.data_type}</td>
                  <td>{details.missing_count}</td>
                  <td>{details.unique_values}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="detail-card">
        <h3>Data quality findings</h3>

        {issues.length > 0 ? (
          <div className="issue-list">
            {issues.map((issue, index) => (
              <div className="issue-item" key={`${issue.title}-${index}`}>
                <div>
                  <strong>{issue.title}</strong>
                  <p>{issue.description}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p>No obvious issues detected by these checks.</p>
        )}
      </div>

      <div className="detail-card column-card">
        <h3>Data preview</h3>
        <p className="table-description">First {preview.length} rows returned by the backend.</p>

        {preview.length > 0 && (
          <div className="table-scroll">
            <table className="dataset-table">
              <thead>
                <tr>
                  {Object.keys(preview[0]).map((key) => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.map((row, index) => (
                  <tr key={index}>
                    {Object.keys(preview[0]).map((key) => (
                      <td key={key}>{row[key] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

export default DatasetOverview;

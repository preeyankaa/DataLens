
import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Plus,
  RefreshCw,
  AlertCircle,
  SlidersHorizontal,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

const CHART_TYPES = [
  { value: "bar", label: "Bar Chart" },
  { value: "horizontal_bar", label: "Horizontal Bar" },
  { value: "line", label: "Line Chart" },
  { value: "area", label: "Area Chart" },
  { value: "pie", label: "Pie Chart" },
  { value: "donut", label: "Donut Chart" },
  { value: "scatter", label: "Scatter Plot" },
  { value: "histogram", label: "Histogram" },
];

const AGGREGATIONS = [
  { value: "sum", label: "Sum" },
  { value: "mean", label: "Average" },
  { value: "count", label: "Count" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
];

const inputStyle = {
  width: "100%",
  padding: "11px 12px",
  border: "1px solid #e3e4eb",
  borderRadius: 9,
  background: "#fff",
  color: "#252638",
  fontSize: 13,
  outline: "none",
};

const labelStyle = {
  display: "block",
  marginBottom: 7,
  color: "#55586b",
  fontSize: 12,
  fontWeight: 600,
};

function InteractiveChartBuilder({
  datasetId,
  version,
  onChartCreated,
}) {
  const [columns, setColumns] = useState([]);
  const [preview, setPreview] = useState([]);
  const [chartType, setChartType] = useState("bar");
  const [xColumn, setXColumn] = useState("");
  const [yColumn, setYColumn] = useState("");
  const [aggregation, setAggregation] = useState("sum");
  const [topN, setTopN] = useState(10);
  const [loadingColumns, setLoadingColumns] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadColumns() {
      if (!datasetId) return;

      setLoadingColumns(true);
      setError("");

      try {
        const response = await fetch(
          `${API_URL}/api/v1/datasets/${datasetId}/versions/${version}`
        );

        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.detail || "Unable to load dataset columns.");
        }

        if (cancelled) return;

        const names = result.column_names || [];
        const rows = result.preview || [];

        setColumns(names);
        setPreview(rows);

        if (names.length) {
          setXColumn((current) =>
            names.includes(current) ? current : names[0]
          );

          const numericColumn = names.find((name) =>
            rows.some((row) => {
              const value = row[name];
              return (
                value !== null &&
                value !== undefined &&
                value !== "" &&
                Number.isFinite(Number(value))
              );
            })
          );

          setYColumn((current) =>
            names.includes(current) ? current : numericColumn || names[0]
          );
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoadingColumns(false);
      }
    }

    loadColumns();

    return () => {
      cancelled = true;
    };
  }, [datasetId, version]);

  const numericColumns = useMemo(() => {
    return columns.filter((column) => {
      const values = preview
        .map((row) => row[column])
        .filter((value) => value !== null && value !== undefined && value !== "");

      return (
        values.length > 0 &&
        values.every((value) => Number.isFinite(Number(value)))
      );
    });
  }, [columns, preview]);

  const requiresNumericMetric = aggregation !== "count";

  const canGenerate =
    Boolean(datasetId) &&
    Boolean(xColumn) &&
    Boolean(yColumn) &&
    (!requiresNumericMetric || numericColumns.includes(yColumn));

  async function generateChart(event) {
    event.preventDefault();

    if (!canGenerate) {
      setError("Choose valid columns for this chart.");
      return;
    }

    setGenerating(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/charts/custom?version=${version}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            chart_type: chartType,
            x_column: xColumn,
            y_column: yColumn,
            aggregation,
            filters: [],
            top_n: Number(topN),
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Unable to generate this chart.");
      }

      if (!result.chart) {
        throw new Error("The API did not return chart data.");
      }

      onChartCreated?.({
        ...result.chart,
        id: `custom-${Date.now()}`,
        custom: true,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div
      className="interactive-builder-card"
      style={{
        background: "#fff",
        border: "1px solid #e9e9f0",
        borderRadius: 14,
        padding: 22,
        marginBottom: 22,
      }}
    >
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 11,
            display: "grid",
            placeItems: "center",
            background: "#f0edff",
            color: "#7166E8",
          }}
        >
          <SlidersHorizontal size={20} />
        </div>

        <div>
          <h3 style={{ margin: 0, fontSize: 16, color: "#252638" }}>
            Build a custom chart
          </h3>
          <p style={{ margin: "5px 0 0", fontSize: 12, color: "#858799" }}>
            Select columns and configure how your data should be visualized.
          </p>
        </div>
      </div>

      {loadingColumns ? (
        <p style={{ color: "#777", fontSize: 13 }}>Loading dataset columns...</p>
      ) : (
        <form onSubmit={generateChart}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              gap: 16,
            }}
          >
            <div>
              <label style={labelStyle}>Chart type</label>
              <select
                style={inputStyle}
                value={chartType}
                onChange={(e) => setChartType(e.target.value)}
              >
                {CHART_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={labelStyle}>X-axis / Category</label>
              <select
                style={inputStyle}
                value={xColumn}
                onChange={(e) => setXColumn(e.target.value)}
              >
                {columns.map((column) => (
                  <option key={column} value={column}>
                    {column}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={labelStyle}>Y-axis / Metric</label>
              <select
                style={inputStyle}
                value={yColumn}
                onChange={(e) => setYColumn(e.target.value)}
              >
                {columns.map((column) => (
                  <option key={column} value={column}>
                    {column}
                    {numericColumns.includes(column) ? " (numeric)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={labelStyle}>Aggregation</label>
              <select
                style={inputStyle}
                value={aggregation}
                onChange={(e) => setAggregation(e.target.value)}
              >
                {AGGREGATIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={labelStyle}>Show top results</label>
              <select
                style={inputStyle}
                value={topN}
                onChange={(e) => setTopN(e.target.value)}
              >
                {[5, 10, 15, 20, 30, 50].map((number) => (
                  <option key={number} value={number}>
                    Top {number}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {requiresNumericMetric && yColumn && !numericColumns.includes(yColumn) && (
            <p style={{ color: "#c56a36", fontSize: 12, marginTop: 12 }}>
              Choose a numeric column for Sum, Average, Minimum or Maximum.
            </p>
          )}

          {error && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                color: "#c34d55",
                fontSize: 13,
                marginTop: 15,
              }}
            >
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
              marginTop: 20,
            }}
          >
            <span style={{ fontSize: 12, color: "#858799" }}>
              Dataset: {version === "original" ? "Original" : "Cleaned"}
            </span>

            <button
              type="submit"
              disabled={!canGenerate || generating || loadingColumns}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                border: 0,
                borderRadius: 9,
                padding: "11px 17px",
                background: "#7166E8",
                color: "#fff",
                fontWeight: 600,
                fontSize: 13,
                cursor: generating ? "wait" : "pointer",
                opacity: !canGenerate || generating ? 0.6 : 1,
              }}
            >
              {generating ? (
                <RefreshCw size={16} className="loading-icon" />
              ) : (
                <Plus size={16} />
              )}
              {generating ? "Generating..." : "Generate chart"}
            </button>
          </div>
        </form>
      )}

      {!loadingColumns && columns.length === 0 && (
        <div style={{ color: "#777", fontSize: 13 }}>
          No columns were found in this dataset.
        </div>
      )}
    </div>
  );
}

export default InteractiveChartBuilder;


import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";

import {
  BarChart3,
  Database,
  Hash,
  Layers,
  RefreshCw,
  TrendingUp,
  AlertCircle,
  Sparkles,
  SlidersHorizontal,
  Lightbulb,
  ArrowUpRight,
  Info,
} from "lucide-react";

import "./ChartsPage.css";

const API_URL = "http://127.0.0.1:8000";

const CHART_COLORS = [
  "#7166E8",
  "#32A6A0",
  "#F2A65A",
  "#E8799B",
  "#5B91D5",
  "#9B83C7",
  "#77B88A",
  "#E5C45C",
  "#8C9BAA",
  "#D28B70",
];

const formatNumber = (value) => {
  if (value === null || value === undefined) return "—";

  if (typeof value === "number") {
    return value.toLocaleString("en-IN", {
      maximumFractionDigits: 2,
    });
  }

  return value;
};

function HeatmapChart({ data }) {
  const xLabels = [...new Set(data.map((item) => item.x))];
  const yLabels = [...new Set(data.map((item) => item.y))];

  const getCell = (x, y) =>
    data.find((item) => item.x === x && item.y === y);

  const getColor = (value) => {
    if (value === null || value === undefined) return "#f1f0f6";

    const intensity = Math.min(Math.abs(value), 1);
    const alpha = 0.12 + intensity * 0.75;

    return value >= 0
      ? `rgba(50, 166, 160, ${alpha})`
      : `rgba(232, 121, 155, ${alpha})`;
  };

  return (
    <div className="heatmap-wrapper">
      <div
        className="heatmap-grid"
        style={{
          gridTemplateColumns: `100px repeat(${xLabels.length}, minmax(55px, 1fr))`,
        }}
      >
        <div className="heatmap-corner" />

        {xLabels.map((label) => (
          <div className="heatmap-axis-label" key={label}>
            {label}
          </div>
        ))}

        {yLabels.map((yLabel) => (
          <div className="heatmap-row-fragment" key={yLabel}>
            <div className="heatmap-y-label">{yLabel}</div>

            {xLabels.map((xLabel) => {
              const cell = getCell(xLabel, yLabel);

              return (
                <div
                  className="heatmap-cell"
                  key={`${xLabel}-${yLabel}`}
                  style={{
                    background: getColor(cell?.value),
                  }}
                  title={`${yLabel} / ${xLabel}: ${cell?.value ?? "N/A"}`}
                >
                  {cell?.value?.toFixed(2) ?? "—"}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <div className="heatmap-legend">
        <span>Negative correlation</span>
        <span className="heatmap-legend-gradient" />
        <span>Positive correlation</span>
      </div>
    </div>
  );
}

function RenderChart({ chart, height = 300 }) {
  if (!chart || !chart.data?.length) {
    return (
      <div className="chart-no-data">
        <Info size={20} />
        <span>Not enough data to display this chart.</span>
      </div>
    );
  }

  if (chart.chart_type === "heatmap") {
    return <HeatmapChart data={chart.data} />;
  }

  if (chart.chart_type === "bar") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={chart.data}
          margin={{ top: 12, right: 12, left: 0, bottom: 55 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="category"
            angle={-30}
            textAnchor="end"
            interval={0}
            tick={{ fontSize: 10 }}
            height={75}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            tickFormatter={(value) =>
              Number(value).toLocaleString("en-IN", {
                notation: "compact",
              })
            }
          />
          <Tooltip formatter={(value) => formatNumber(value)} />
          <Bar
            dataKey="value"
            name={chart.y_label || "Value"}
            fill="#7166E8"
            radius={[5, 5, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chart.chart_type === "donut") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={chart.data}
            dataKey="value"
            nameKey="category"
            cx="50%"
            cy="46%"
            innerRadius={62}
            outerRadius={100}
            paddingAngle={3}
          >
            {chart.data.map((entry, index) => (
              <Cell
                key={`${entry.category}-${index}`}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip formatter={(value) => formatNumber(value)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (chart.chart_type === "line") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chart.data}
          margin={{ top: 12, right: 15, left: 0, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="period"
            tick={{ fontSize: 10 }}
            minTickGap={20}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            tickFormatter={(value) =>
              Number(value).toLocaleString("en-IN", {
                notation: "compact",
              })
            }
          />
          <Tooltip formatter={(value) => formatNumber(value)} />
          <Line
            type="monotone"
            dataKey="value"
            name={chart.y_label || "Value"}
            stroke="#7166E8"
            strokeWidth={2.5}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (chart.chart_type === "scatter") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 15, right: 15, bottom: 15, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            name={chart.x_label || "X"}
            tick={{ fontSize: 10 }}
            tickFormatter={(value) =>
              Number(value).toLocaleString("en-IN", {
                notation: "compact",
              })
            }
          />
          <YAxis
            type="number"
            dataKey="y"
            name={chart.y_label || "Y"}
            tick={{ fontSize: 10 }}
            tickFormatter={(value) =>
              Number(value).toLocaleString("en-IN", {
                notation: "compact",
              })
            }
          />
          <ZAxis range={[35, 35]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter
            data={chart.data}
            fill="#32A6A0"
            fillOpacity={0.65}
          />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (chart.chart_type === "histogram") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={chart.data}
          margin={{ top: 12, right: 12, left: 0, bottom: 55 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="range"
            angle={-30}
            textAnchor="end"
            interval={0}
            tick={{ fontSize: 9 }}
            height={75}
          />
          <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Bar
            dataKey="value"
            name="Records"
            fill="#32A6A0"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <div className="chart-no-data">
      <Info size={20} />
      <span>Unsupported chart type: {chart.chart_type}</span>
    </div>
  );
}

function ChartsPage() {
  const dataset = useOutletContext();
  const datasetId = dataset?.dataset_id;

  const [version, setVersion] = useState("original");
  const [mode, setMode] = useState("ai");
  const [dashboard, setDashboard] = useState(null);
  const [selectedChartId, setSelectedChartId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = async () => {
    if (!datasetId) {
      setError("Dataset information is not available. Please upload a dataset first.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/dashboard?version=${version}`
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || "Unable to generate the dashboard."
        );
      }

      setDashboard(result);

      const firstSelectedId =
        result.dashboard_ai?.selected_chart_ids?.[0] ||
        result.charts?.[0]?.id ||
        "";

      setSelectedChartId(firstSelectedId);
    } catch (err) {
      setDashboard(null);
      setError(
        err.message === "Failed to fetch"
          ? "Unable to connect to the backend. Check whether FastAPI is running."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [datasetId, version]);

  const charts = dashboard?.charts || [];
  const ai = dashboard?.dashboard_ai || {};
  const summary = dashboard?.summary || {};
  const kpis = dashboard?.kpis || [];

  const selectedChart = useMemo(
    () => charts.find((chart) => chart.id === selectedChartId),
    [charts, selectedChartId]
  );

  const aiCharts = useMemo(() => {
    const selectedIds = ai.selected_chart_ids || [];

    if (!selectedIds.length) return charts;

    const selected = selectedIds
      .map((id) => charts.find((chart) => chart.id === id))
      .filter(Boolean);

    return selected.length ? selected : charts;
  }, [charts, ai.selected_chart_ids]);

  if (loading) {
    return (
      <div className="charts-loading">
        <RefreshCw size={28} className="loading-icon" />
        <h3>Preparing your dashboard...</h3>
        <p>Analyzing your dataset and generating useful visualizations.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="charts-error">
        <AlertCircle size={30} />
        <h3>Unable to load dashboard</h3>
        <p>{error}</p>
        <button onClick={fetchDashboard}>
          <RefreshCw size={16} />
          Try again
        </button>
      </div>
    );
  }

  if (!dashboard) return null;

  return (
    <div className="charts-page">
      <div className="charts-page-heading">
        <div>
          <span className="page-eyebrow">DATA VISUALIZATION</span>
          <h1>Charts & Analytics</h1>
          <p>
            Understand your data with AI-powered insights and interactive charts.
          </p>
        </div>

        <button
          className="charts-refresh-button"
          onClick={fetchDashboard}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="charts-toolbar">
        <div>
          <Database size={18} />
          <span>Dataset version</span>
        </div>

        <div className="version-switch">
          <button
            className={version === "original" ? "active" : ""}
            onClick={() => setVersion("original")}
          >
            Original
          </button>
          <button
            className={version === "cleaned" ? "active" : ""}
            onClick={() => setVersion("cleaned")}
          >
            Cleaned
          </button>
        </div>
      </div>

      <div className="charts-summary-grid">
        <div className="charts-summary-card">
          <div className="summary-icon purple">
            <Database size={20} />
          </div>
          <div>
            <span>Total Records</span>
            <h2>{formatNumber(summary.total_rows)}</h2>
          </div>
        </div>

        <div className="charts-summary-card">
          <div className="summary-icon blue">
            <Layers size={20} />
          </div>
          <div>
            <span>Total Columns</span>
            <h2>{formatNumber(summary.total_columns)}</h2>
          </div>
        </div>

        <div className="charts-summary-card">
          <div className="summary-icon green">
            <Hash size={20} />
          </div>
          <div>
            <span>Numeric Columns</span>
            <h2>{formatNumber(summary.numeric_columns)}</h2>
          </div>
        </div>

        <div className="charts-summary-card">
          <div className="summary-icon orange">
            <BarChart3 size={20} />
          </div>
          <div>
            <span>Missing Values</span>
            <h2>{formatNumber(summary.missing_values)}</h2>
          </div>
        </div>
      </div>

      <div className="dashboard-mode-switch">
        <button
          className={mode === "ai" ? "active" : ""}
          onClick={() => setMode("ai")}
        >
          <Sparkles size={16} />
          AI-Generated Dashboard
        </button>

        <button
          className={mode === "custom" ? "active" : ""}
          onClick={() => setMode("custom")}
        >
          <SlidersHorizontal size={16} />
          Customize Dashboard
        </button>
      </div>

      {mode === "ai" ? (
        <>
          <section className="ai-dashboard-intro">
            <div className="ai-intro-icon">
              <Sparkles size={20} />
            </div>

            <div className="ai-intro-content">
              <span className="ai-label">AI DATA ANALYSIS</span>
              <h2>{ai.headline || "Your dataset at a glance"}</h2>
              <p>
                {ai.summary ||
                  "Explore the charts below to understand patterns, comparisons and relationships in your dataset."}
              </p>
            </div>

            <span className="ai-status">
              {ai.ai_generated ? "AI Generated" : "Automated Analysis"}
            </span>
          </section>

          <section className="charts-section">
            <div className="charts-section-heading">
              <div>
                <h2>Key Visualizations</h2>
                <p>
                  Charts selected to highlight useful patterns in your dataset.
                </p>
              </div>
              <span className="chart-count">
                {aiCharts.length} Charts
              </span>
            </div>

            <div className="automatic-charts-grid">
              {aiCharts.map((chart, index) => (
                <article
                  className={`visualization-card chart-size-${chart.size || "medium"}`}
                  key={chart.id || index}
                >
                  <div className="visualization-card-heading">
                    <div>
                      <span className="chart-type-label">
                        {chart.chart_type}
                      </span>
                      <h3>{chart.title}</h3>
                      <p className="chart-subtitle">{chart.subtitle}</p>
                    </div>
                    <TrendingUp size={19} />
                  </div>

                  <RenderChart chart={chart} />

                  <div className="chart-card-footer">
                    <span>{chart.x_label || "Dataset"}</span>
                    <span>{chart.data?.length || 0} data points</span>
                  </div>

                  {chart.insight_hint && (
                    <div className="chart-insight-hint">
                      <Lightbulb size={15} />
                      <span>{chart.insight_hint}</span>
                    </div>
                  )}
                </article>
              ))}
            </div>

            {aiCharts.length === 0 && (
              <div className="empty-charts">
                <BarChart3 size={30} />
                <h3>No visualizations available</h3>
                <p>This dataset does not have enough suitable data for charts.</p>
              </div>
            )}
          </section>

          <section className="ai-insights-section">
            <div className="charts-section-heading">
              <div>
                <h2>Business Insights</h2>
                <p>What these patterns could mean for your analysis.</p>
              </div>
              <span className="insight-count">
                {(ai.insights || []).length} Insights
              </span>
            </div>

            {(ai.insights || []).length > 0 ? (
              <div className="business-insights-grid">
                {ai.insights.map((insight, index) => (
                  <article className="business-insight-card" key={index}>
                    <div className="insight-number">
                      {String(index + 1).padStart(2, "0")}
                    </div>
                    <div>
                      <h3>{insight.title}</h3>
                      <p>{insight.observation}</p>

                      {insight.business_impact && (
                        <div className="insight-detail">
                          <strong>Why it matters</strong>
                          <span>{insight.business_impact}</span>
                        </div>
                      )}

                      {insight.suggestion && (
                        <div className="insight-detail">
                          <strong>Suggested next step</strong>
                          <span>{insight.suggestion}</span>
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-charts">
                <Lightbulb size={25} />
                <h3>No additional insights available</h3>
                <p>Use the charts above to explore the dataset.</p>
              </div>
            )}
          </section>
        </>
      ) : (
        <section className="chart-builder-section">
          <div className="charts-section-heading">
            <div>
              <h2>Customize Your Dashboard</h2>
              <p>
                Choose a generated chart to inspect it in more detail.
              </p>
            </div>
          </div>

          <div className="chart-builder-card">
            <div className="chart-builder-controls">
              <div className="chart-control">
                <label htmlFor="custom-chart-select">Select visualization</label>
                <select
                  id="custom-chart-select"
                  value={selectedChartId}
                  onChange={(event) => setSelectedChartId(event.target.value)}
                >
                  <option value="">Choose a chart</option>
                  {charts.map((chart) => (
                    <option key={chart.id} value={chart.id}>
                      {chart.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="chart-control">
                <label>Dataset version</label>
                <select
                  value={version}
                  onChange={(event) => setVersion(event.target.value)}
                >
                  <option value="original">Original</option>
                  <option value="cleaned">Cleaned</option>
                </select>
              </div>
            </div>

            {selectedChart ? (
              <>
                <div className="selected-chart-heading">
                  <div>
                    <h3>{selectedChart.title}</h3>
                    <p>{selectedChart.subtitle}</p>
                  </div>
                  <span>{selectedChart.chart_type}</span>
                </div>

                <RenderChart chart={selectedChart} height={360} />

                {selectedChart.insight_hint && (
                  <div className="chart-insight-hint custom-chart-hint">
                    <Lightbulb size={16} />
                    <span>{selectedChart.insight_hint}</span>
                  </div>
                )}
              </>
            ) : (
              <div className="chart-builder-empty">
                <SlidersHorizontal size={35} />
                <h3>Choose a visualization</h3>
                <p>Select one of the generated charts to preview it here.</p>
              </div>
            )}
          </div>

          <div className="customize-note">
            <Info size={17} />
            <p>
              Column selection, aggregation, chart type changes and filters
              will be enabled after the custom chart calculation API is added.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}

export default ChartsPage;

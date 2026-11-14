
import { useCallback, useEffect, useMemo, useState } from "react";
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
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  ZAxis,
  Treemap,
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
  Info,
  Activity,
  Plus,
  Trash2,
} from "lucide-react";
import InteractiveChartBuilder from "../components/InteractiveChartBuilder";
import "./ChartsPage.css";

const API_URL = "http://127.0.0.1:8000";

const COLORS = [
  "#6366f1",
  "#06b6d4",
  "#10b981",
  "#f59e0b",
  "#ec4899",
  "#8b5cf6",
  "#f97316",
  "#14b8a6",
  "#3b82f6",
  "#84cc16",
];

const GRID_STYLE = {
  stroke: "#e5e7eb",
  strokeDasharray: "3 3",
};

const AXIS_STYLE = {
  fontSize: 11,
  fill: "#64748b",
};

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }

  return Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  });
};

const formatCompact = (value) => {
  const number = Number(value);

  if (!Number.isFinite(number)) return value;

  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(number);
};

const getChartData = (chart) => {
  if (!chart) return [];

  if (Array.isArray(chart.data)) return chart.data;

  return [];
};

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="chart-tooltip">
      {label !== undefined && (
        <p className="chart-tooltip-label">{String(label)}</p>
      )}

      {payload.map((item, index) => (
        <div className="chart-tooltip-row" key={index}>
          <span
            className="chart-tooltip-dot"
            style={{ background: item.color || item.fill || COLORS[index] }}
          />
          <span>{item.name || "Value"}:</span>
          <strong>{formatNumber(item.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function TreemapContent({ x, y, width, height, name, index }) {
  if (width < 35 || height < 25) return null;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={COLORS[index % COLORS.length]}
        stroke="#fff"
        strokeWidth={2}
        rx={5}
      />

      {width > 65 && height > 40 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#fff"
          fontSize={11}
        >
          {String(name || "").slice(0, 16)}
        </text>
      )}
    </g>
  );
}

function HeatmapChart({ chart }) {
  const data = getChartData(chart);

  if (!data.length) {
    return <EmptyChart />;
  }

  const keys = Object.keys(data[0] || {}).filter(
    (key) => key !== "name" && key !== "label"
  );

  if (!keys.length) {
    return <EmptyChart />;
  }

  const values = data.flatMap((row) =>
    keys.map((key) => Number(row[key])).filter(Number.isFinite)
  );

  const min = Math.min(...values);
  const max = Math.max(...values);

  const getOpacity = (value) => {
    if (max === min) return 0.7;
    return 0.15 + ((Number(value) - min) / (max - min)) * 0.75;
  };

  return (
    <div className="heatmap-wrapper">
      <table className="heatmap-table">
        <thead>
          <tr>
            <th></th>
            {keys.map((key) => (
              <th key={key}>{key}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {data.map((row, index) => (
            <tr key={index}>
              <th>{row.name || row.label || `Row ${index + 1}`}</th>

              {keys.map((key) => (
                <td
                  key={key}
                  title={`${key}: ${formatNumber(row[key])}`}
                  style={{
                    background: `rgba(99, 102, 241, ${getOpacity(
                      row[key]
                    )})`,
                  }}
                >
                  {formatNumber(row[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="chart-empty">
      <BarChart3 size={28} />
      <p>No chart data available</p>
    </div>
  );
}

function RenderChart({ chart }) {
  if (!chart) return <EmptyChart />;

  const data = getChartData(chart);
  const type = String(chart.chart_type || chart.type || "bar").toLowerCase();

  const xKey =
    chart.x_column ||
    chart.x_key ||
    chart.xKey ||
    chart.x_label ||
    chart.xLabel ||
    (data[0] ? Object.keys(data[0])[0] : "name");

  const yKey =
    chart.y_column ||
    chart.y_key ||
    chart.yKey ||
    "value";

  const valueKey = data[0]?.value !== undefined ? "value" : yKey;

  if (!data.length) return <EmptyChart />;

  const commonAxis = (
    <>
      <CartesianGrid {...GRID_STYLE} vertical={false} />
      <XAxis
        dataKey={xKey}
        tick={AXIS_STYLE}
        tickLine={false}
        axisLine={false}
      />
      <YAxis
        tick={AXIS_STYLE}
        tickLine={false}
        axisLine={false}
        tickFormatter={formatCompact}
      />
      <Tooltip content={<ChartTooltip />} />
    </>
  );

  if (type === "heatmap") {
    return <HeatmapChart chart={chart} />;
  }

  if (type === "pie" || type === "donut") {
    return (
      <ResponsiveContainer width="100%" height={290}>
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={xKey}
            cx="50%"
            cy="48%"
            innerRadius={type === "donut" ? 65 : 0}
            outerRadius={105}
            paddingAngle={type === "donut" ? 3 : 1}
            label={({ name, percent }) =>
              `${String(name || "").slice(0, 12)} ${(
                percent * 100
              ).toFixed(0)}%`
            }
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (type === "horizontal_bar") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 15, right: 20 }}
        >
          <CartesianGrid {...GRID_STYLE} horizontal={false} />
          <XAxis
            type="number"
            tick={AXIS_STYLE}
            tickFormatter={formatCompact}
          />
          <YAxis
            type="category"
            dataKey={xKey}
            width={100}
            tick={AXIS_STYLE}
          />
          <Tooltip content={<ChartTooltip />} />
          <Bar
            dataKey={valueKey}
            fill={COLORS[0]}
            radius={[0, 5, 5, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (type === "line" || type === "trend") {
    return (
      <ResponsiveContainer width="100%" height={290}>
        <LineChart data={data}>
          {commonAxis}
          <Line
            type="monotone"
            dataKey={valueKey}
            stroke={COLORS[0]}
            strokeWidth={3}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === "area") {
    return (
      <ResponsiveContainer width="100%" height={290}>
        <AreaChart data={data}>
          {commonAxis}
          <Area
            type="monotone"
            dataKey={valueKey}
            stroke={COLORS[0]}
            fill={COLORS[0]}
            fillOpacity={0.18}
            strokeWidth={2.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (type === "scatter") {
    return (
      <ResponsiveContainer width="100%" height={290}>
        <ScatterChart>
          <CartesianGrid {...GRID_STYLE} />
          <XAxis
            type="number"
            dataKey={xKey}
            name={xKey}
            tick={AXIS_STYLE}
          />
          <YAxis
            type="number"
            dataKey={valueKey}
            name={valueKey}
            tick={AXIS_STYLE}
          />
          <ZAxis range={[50, 50]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} fill={COLORS[0]} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (type === "treemap") {
    return (
      <ResponsiveContainer width="100%" height={290}>
        <Treemap
          data={data.map((item) => ({
            ...item,
            name: item[xKey],
            size: Number(item[valueKey]) || 0,
          }))}
          dataKey="size"
          nameKey="name"
          content={<TreemapContent />}
        />
      </ResponsiveContainer>
    );
  }

  if (type === "histogram") {
    return (
      <ResponsiveContainer width="100%" height={290}>
        <BarChart data={data}>
          {commonAxis}
          <Bar
            dataKey={valueKey}
            fill={COLORS[1]}
            radius={[5, 5, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={290}>
      <BarChart data={data}>
        {commonAxis}
        <Bar
          dataKey={valueKey}
          fill={COLORS[0]}
          radius={[5, 5, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

function SummaryCard({ icon: Icon, label, value, description }) {
  return (
    <div className="chart-summary-card">
      <div className="chart-summary-icon">
        <Icon size={19} />
      </div>

      <div>
        <p>{label}</p>
        <h3>{value ?? "-"}</h3>
        {description && <span>{description}</span>}
      </div>
    </div>
  );
}

function InsightCard({ insight, index }) {
  const text =
    typeof insight === "string"
      ? insight
      : insight?.message ||
        insight?.insight ||
        insight?.description ||
        insight?.title ||
        "Insight";

  return (
    <div className="chart-insight-card" key={index}>
      <div className="chart-insight-icon">
        <Lightbulb size={17} />
      </div>
      <p>{text}</p>
    </div>
  );
}

function ChartCard({ chart, onRemove, custom = false }) {
  const title =
    chart.title ||
    chart.name ||
    chart.chart_title ||
    "Data Visualization";

  const description =
    chart.description ||
    chart.subtitle ||
    chart.aggregation ||
    "";

  return (
    <div className="chart-visual-card">
      <div className="chart-visual-header">
        <div>
          <h3>{title}</h3>
          {description && <p>{description}</p>}
        </div>

        {custom && (
          <button
            type="button"
            className="chart-remove-button"
            onClick={onRemove}
            title="Remove chart"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>

      <RenderChart chart={chart} />
    </div>
  );
}

export default function ChartsPage() {
  const dataset = useOutletContext();

  const datasetId = dataset?.dataset_id || dataset?.id;

  const [version, setVersion] = useState("original");
  const [mode, setMode] = useState("ai");

  const [dashboard, setDashboard] = useState(null);
  const [customCharts, setCustomCharts] = useState([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchDashboard = useCallback(async () => {
    if (!datasetId) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/dashboard?version=${version}`
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || "Unable to load dashboard."
        );
      }

      setDashboard(result);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [datasetId, version]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    setCustomCharts([]);
  }, [datasetId]);

  const handleCustomChartCreated = (chart) => {
    if (!chart) return;

    setCustomCharts((previous) => [
      ...previous,
      {
        ...chart,
        custom_id: `${Date.now()}-${Math.random()}`,
      },
    ]);
  };

  const removeCustomChart = (chartId) => {
    setCustomCharts((previous) =>
      previous.filter((chart) => chart.custom_id !== chartId)
    );
  };

  const summary = useMemo(() => {
    return (
      dashboard?.summary ||
      dashboard?.overview ||
      dashboard?.profile?.overview ||
      {}
    );
  }, [dashboard]);

  const kpis = useMemo(() => {
    return dashboard?.kpis || dashboard?.metrics || [];
  }, [dashboard]);

  const charts = useMemo(() => {
    return (
      dashboard?.charts ||
      dashboard?.visualizations ||
      dashboard?.data?.charts ||
      []
    );
  }, [dashboard]);

  const insights = useMemo(() => {
    const result =
      dashboard?.insights ||
      dashboard?.ai_insights ||
      dashboard?.data?.insights ||
      [];

    return Array.isArray(result) ? result : [];
  }, [dashboard]);

  const chartCount = charts.length + customCharts.length;

  if (!datasetId) {
    return (
      <div className="charts-page">
        <div className="charts-error">
          <AlertCircle size={20} />
          <p>Dataset information is missing. Please upload a dataset again.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="charts-page">
      {/* Page heading */}
      <div className="charts-page-header">
        <div>
          <div className="charts-heading-eyebrow">
            <Sparkles size={15} />
            DATA ANALYTICS
          </div>

          <h1>Data Visualization</h1>

          <p>
            Explore your dataset through AI-generated insights and
            interactive visualizations.
          </p>
        </div>

        <button
          type="button"
          className="charts-refresh-button"
          onClick={fetchDashboard}
          disabled={loading}
        >
          <RefreshCw
            size={16}
            className={loading ? "charts-spin" : ""}
          />
          Refresh
        </button>
      </div>

      {/* Dataset version */}
      <div className="charts-toolbar">
        <div className="charts-version-switch">
          <button
            type="button"
            className={version === "original" ? "active" : ""}
            onClick={() => setVersion("original")}
          >
            Original Data
          </button>

          <button
            type="button"
            className={version === "cleaned" ? "active" : ""}
            onClick={() => setVersion("cleaned")}
          >
            Cleaned Data
          </button>
        </div>

        <div className="charts-dataset-label">
          <Database size={15} />
          {dataset.filename || "Current dataset"}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="charts-error">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button type="button" onClick={fetchDashboard}>
            Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && !dashboard && (
        <div className="charts-loading">
          <div className="charts-loader" />
          <p>Preparing your dashboard...</p>
        </div>
      )}

      {/* Dashboard summary */}
      {dashboard && (
        <>
          <div className="charts-summary-grid">
            <SummaryCard
              icon={Database}
              label="Total Rows"
              value={formatNumber(
                summary.total_rows ??
                  summary.rows ??
                  dataset.profile?.overview?.total_rows
              )}
              description="Records in dataset"
            />

            <SummaryCard
              icon={Layers}
              label="Total Columns"
              value={formatNumber(
                summary.total_columns ??
                  summary.columns ??
                  dataset.profile?.overview?.total_columns
              )}
              description="Dataset features"
            />

            <SummaryCard
              icon={BarChart3}
              label="Visualizations"
              value={formatNumber(chartCount)}
              description="Available charts"
            />

            <SummaryCard
              icon={Activity}
              label="Insights"
              value={formatNumber(insights.length)}
              description="AI observations"
            />
          </div>

          {/* KPI section */}
          {kpis.length > 0 && (
            <section className="charts-kpi-section">
              <div className="charts-section-heading">
                <div>
                  <h2>Key Performance Indicators</h2>
                  <p>Important metrics from your dataset</p>
                </div>
                <Activity size={19} />
              </div>

              <div className="charts-kpi-grid">
                {kpis.map((kpi, index) => {
                  const label =
                    kpi.label ||
                    kpi.name ||
                    kpi.title ||
                    `Metric ${index + 1}`;

                  const value =
                    kpi.value ??
                    kpi.metric ??
                    kpi.count ??
                    "-";

                  return (
                    <div className="charts-kpi-card" key={index}>
                      <span>{label}</span>
                      <strong>
                        {typeof value === "number"
                          ? formatNumber(value)
                          : value}
                      </strong>

                      {kpi.description && (
                        <small>{kpi.description}</small>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Mode switch */}
          <div className="charts-mode-section">
            <div>
              <h2>Your Dashboard</h2>
              <p>
                Switch between automatic analytics and custom charts.
              </p>
            </div>

            <div className="charts-mode-switch">
              <button
                type="button"
                className={mode === "ai" ? "active" : ""}
                onClick={() => setMode("ai")}
              >
                <Sparkles size={16} />
                AI Dashboard
              </button>

              <button
                type="button"
                className={mode === "interactive" ? "active" : ""}
                onClick={() => setMode("interactive")}
              >
                <SlidersHorizontal size={16} />
                Interactive Dashboard
              </button>
            </div>
          </div>

          {/* AI dashboard */}
          {mode === "ai" && (
            <div className="charts-dashboard-content">
              {insights.length > 0 && (
                <section className="charts-insights-section">
                  <div className="charts-section-heading">
                    <div>
                      <h2>
                        <Sparkles size={18} />
                        AI-Generated Insights
                      </h2>
                      <p>
                        Key observations automatically identified
                        from your data.
                      </p>
                    </div>
                  </div>

                  <div className="charts-insights-grid">
                    {insights.map((insight, index) => (
                      <InsightCard
                        insight={insight}
                        index={index}
                        key={index}
                      />
                    ))}
                  </div>
                </section>
              )}

              <section className="charts-visualizations-section">
                <div className="charts-section-heading">
                  <div>
                    <h2>Visual Analytics</h2>
                    <p>
                      Automatically generated charts based on your
                      dataset.
                    </p>
                  </div>

                  <span className="charts-count-label">
                    {charts.length} charts
                  </span>
                </div>

                {charts.length > 0 ? (
                  <div className="charts-visual-grid">
                    {charts.map((chart, index) => (
                      <ChartCard
                        key={chart.id || chart.chart_id || index}
                        chart={chart}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="charts-empty-state">
                    <BarChart3 size={32} />
                    <h3>No automatic charts available</h3>
                    <p>
                      This dataset does not have enough suitable
                      information for automatic visualizations.
                    </p>
                  </div>
                )}
              </section>
            </div>
          )}

          {/* Interactive dashboard */}
          {mode === "interactive" && (
            <div className="charts-interactive-content">
              <div className="charts-interactive-intro">
                <div className="charts-interactive-icon">
                  <SlidersHorizontal size={22} />
                </div>

                <div>
                  <h2>Build Your Own Charts</h2>
                  <p>
                    Choose columns, chart types and aggregations to
                    create visualizations from your dataset.
                  </p>
                </div>
              </div>

              <InteractiveChartBuilder
                datasetId={datasetId}
                version={version}
                onChartCreated={handleCustomChartCreated}
              />

              <section className="charts-custom-section">
                <div className="charts-section-heading">
                  <div>
                    <h2>
                      <BarChart3 size={18} />
                      My Custom Charts
                    </h2>
                    <p>
                      Charts you have created for this dataset version.
                    </p>
                  </div>

                  <span className="charts-count-label">
                    {customCharts.length} charts
                  </span>
                </div>

                {customCharts.length > 0 ? (
                  <div className="charts-visual-grid">
                    {customCharts.map((chart) => (
                      <ChartCard
                        key={chart.custom_id}
                        chart={chart}
                        custom
                        onRemove={() =>
                          removeCustomChart(chart.custom_id)
                        }
                      />
                    ))}
                  </div>
                ) : (
                  <div className="charts-empty-state">
                    <Plus size={32} />
                    <h3>Your custom dashboard is empty</h3>
                    <p>
                      Create your first chart using the builder above.
                      It will appear here.
                    </p>
                  </div>
                )}
              </section>
            </div>
          )}
        </>
      )}

      {/* Dashboard unavailable */}
      {!loading && !dashboard && !error && (
        <div className="charts-empty-state">
          <Info size={30} />
          <h3>Dashboard is not available</h3>
          <p>
            Try refreshing the dashboard or uploading your dataset again.
          </p>
        </div>
      )}
    </div>
  );
}

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
  Layers,
  RefreshCw,
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
const VERSION = "cleaned"; // backend falls back to the uploaded data if not cleaned yet

const COLORS = [
  "#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ec4899",
  "#8b5cf6", "#f97316", "#14b8a6", "#3b82f6", "#84cc16",
];

const GRID_STYLE = { stroke: "#e9e8f2", strokeDasharray: "3 3" };
const AXIS_STYLE = { fontSize: 11, fill: "#6b6880" };

/* ---------------- helpers ---------------- */

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
};

const formatCompact = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);
};

const shorten = (value, max = 14) => {
  const text = String(value ?? "");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
};

const getChartData = (chart) =>
  chart && Array.isArray(chart.data) ? chart.data : [];

const getType = (chart) =>
  String(chart?.chart_type || chart?.type || "bar").toLowerCase();

/* The backend sends rows like {category, value}, {period, value},
   {range, value}, {x, y}, or wide rows {period, A, B, C}.
   Work the keys out from the rows themselves. */
const getAxisKeys = (chart, data) => {
  const first = data[0] || {};
  const keys = Object.keys(first);
  const type = getType(chart);

  if (type === "scatter" && "x" in first && "y" in first) {
    return { xKey: "x", valueKey: "y", seriesKeys: ["y"] };
  }

  const preferred = ["category", "period", "range", "name", "label"];
  let xKey = preferred.find((k) => k in first);
  if (!xKey) xKey = keys.find((k) => typeof first[k] !== "number") || keys[0];

  const numeric = keys.filter(
    (k) => k !== xKey && typeof first[k] === "number"
  );
  const valueKey = "value" in first ? "value" : numeric[0] || "value";
  const seriesKeys =
    !("value" in first) && numeric.length > 1 ? numeric.slice(0, 6) : [valueKey];

  return { xKey, valueKey, seriesKeys };
};

/* Hide charts that plot ID-type columns or have nothing to show */
const isIdLike = (name) => {
  if (!name || typeof name !== "string") return false;
  return (
    /(^|[_\s-])(id|uuid|guid|idx|index)($|[_\s-])/i.test(name) ||
    /[a-z]Id$/.test(name) ||
    /^unnamed/i.test(name)
  );
};

const isUsefulChart = (chart) => {
  const type = getType(chart);
  const data = getChartData(chart);
  if (type === "table") return false;
  if (data.length < 2) return false;
  return ![chart.x_label, chart.y_label, chart.x_column, chart.y_column].some(
    isIdLike
  );
};

const getSize = (chart) => {
  const forced = String(chart.size || "").toLowerCase();
  if (["sm", "small"].includes(forced)) return "sm";
  if (["md", "medium"].includes(forced)) return "md";
  if (["lg", "large"].includes(forced)) return "lg";
  if (["xl", "full"].includes(forced)) return "xl";

  const type = getType(chart);
  if (type === "pie" || type === "donut") return "sm";
  if (type === "line" || type === "area" || type === "trend") return "lg";
  if (type === "treemap") return "lg";
  return "md";
};

const HEIGHT = { sm: 270, md: 290, lg: 310, xl: 320 };

/* Turn long rows {x, y, value} into wide rows {name, colA, colB} */
const toWideHeatmap = (data) => {
  const first = data[0] || {};
  if (!("x" in first && "y" in first && "value" in first)) return data;

  const rows = new Map();
  data.forEach((item) => {
    const row = rows.get(item.y) || { name: item.y };
    row[item.x] = item.value;
    rows.set(item.y, row);
  });
  return [...rows.values()];
};

/* ---------------- chart pieces ---------------- */

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
            style={{
              background: item.color || item.fill || COLORS[index % COLORS.length],
            }}
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
        fill={COLORS[(index || 0) % COLORS.length]}
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
          fontWeight={600}
        >
          {shorten(name, 16)}
        </text>
      )}
    </g>
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

function HeatmapChart({ chart }) {
  const data = toWideHeatmap(getChartData(chart));
  if (!data.length) return <EmptyChart />;

  const keys = Object.keys(data[0]).filter((k) => k !== "name" && k !== "label");
  if (!keys.length) return <EmptyChart />;

  const values = data.flatMap((row) =>
    keys.map((k) => Number(row[k])).filter(Number.isFinite)
  );
  const max = Math.max(...values.map(Math.abs), 0.0001);
  const hasNegative = values.some((v) => v < 0);

  const cellColor = (value) => {
    const n = Number(value);
    if (value === null || !Number.isFinite(n)) return "#f3f2f8";
    const strength = 0.12 + (Math.abs(n) / max) * 0.8;
    return hasNegative && n < 0
      ? `rgba(236, 72, 153, ${strength})`
      : `rgba(99, 102, 241, ${strength})`;
  };

  return (
    <div className="heatmap-wrapper">
      <table className="heatmap-table">
        <thead>
          <tr>
            <th />
            {keys.map((k) => (
              <th key={k}>{shorten(k, 12)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              <th>{shorten(row.name ?? row.label ?? `Row ${i + 1}`, 14)}</th>
              {keys.map((k) => (
                <td
                  key={k}
                  title={`${k}: ${formatNumber(row[k])}`}
                  style={{ background: cellColor(row[k]) }}
                >
                  {formatNumber(row[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableChart({ chart }) {
  const data = getChartData(chart);
  if (!data.length) return <EmptyChart />;
  const cols = chart.columns || Object.keys(data[0]);

  return (
    <div className="chart-table-wrapper">
      <table className="chart-table">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.slice(0, 50).map((row, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{row[c] === null ? "-" : String(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RenderChart({ chart, height = 290 }) {
  if (!chart) return <EmptyChart />;

  const data = getChartData(chart);
  if (!data.length) return <EmptyChart />;

  const type = getType(chart);
  if (type === "heatmap") return <HeatmapChart chart={chart} />;
  if (type === "table") return <TableChart chart={chart} />;

  const { xKey, valueKey, seriesKeys } = getAxisKeys(chart, data);
  const multi = seriesKeys.length > 1;

  const commonAxis = (
    <>
      <CartesianGrid {...GRID_STYLE} vertical={false} />
      <XAxis
        dataKey={xKey}
        tick={AXIS_STYLE}
        tickLine={false}
        axisLine={false}
        tickFormatter={(v) => shorten(v, 10)}
        interval="preserveStartEnd"
        minTickGap={14}
      />
      <YAxis
        tick={AXIS_STYLE}
        tickLine={false}
        axisLine={false}
        tickFormatter={formatCompact}
        width={46}
      />
      <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(99,102,241,0.06)" }} />
      {multi && <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />}
    </>
  );

  if (type === "pie" || type === "donut") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={xKey}
            cx="50%"
            cy="46%"
            innerRadius={type === "donut" ? "52%" : 0}
            outerRadius="75%"
            paddingAngle={type === "donut" ? 3 : 1}
            label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
          <Legend
            iconType="circle"
            wrapperStyle={{ fontSize: 11 }}
            formatter={(v) => shorten(v, 14)}
          />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (type === "horizontal_bar") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ left: 6, right: 20 }}>
          <CartesianGrid {...GRID_STYLE} horizontal={false} />
          <XAxis
            type="number"
            tick={AXIS_STYLE}
            tickFormatter={formatCompact}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey={xKey}
            width={96}
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => shorten(v, 14)}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(99,102,241,0.06)" }} />
          <Bar dataKey={valueKey} radius={[0, 6, 6, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (type === "line" || type === "trend") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ right: 12 }}>
          {commonAxis}
          {seriesKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={3}
              dot={data.length > 40 ? false : { r: 3 }}
              activeDot={{ r: 6 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === "area") {
    const uid = String(chart.id || chart.custom_id || "a").replace(/[^a-z0-9]/gi, "");
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ right: 12 }}>
          <defs>
            {seriesKeys.map((key, i) => (
              <linearGradient id={`g-${uid}-${i}`} key={key} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.5} />
                <stop offset="100%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.03} />
              </linearGradient>
            ))}
          </defs>
          {commonAxis}
          {seriesKeys.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              fill={`url(#g-${uid}-${i})`}
              strokeWidth={2.5}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (type === "scatter") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ right: 14, bottom: 4 }}>
          <CartesianGrid {...GRID_STYLE} />
          <XAxis
            type="number"
            dataKey="x"
            name={chart.x_label || "x"}
            tick={AXIS_STYLE}
            tickFormatter={formatCompact}
            tickLine={false}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={chart.y_label || "y"}
            tick={AXIS_STYLE}
            tickFormatter={formatCompact}
            tickLine={false}
            width={46}
          />
          <ZAxis range={[55, 55]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} fill={COLORS[4]} fillOpacity={0.7} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (type === "treemap") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <Treemap
          data={data.map((item) => ({
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

  /* bar + histogram (default) */
  const isHistogram = type === "histogram";
  const colorEachBar = !multi && !isHistogram && data.length <= 12;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barCategoryGap={isHistogram ? 2 : "22%"}>
        {commonAxis}
        {seriesKeys.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            fill={COLORS[(isHistogram ? 1 : i) % COLORS.length]}
            radius={[6, 6, 0, 0]}
          >
            {colorEachBar &&
              data.map((_, idx) => (
                <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
              ))}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ---------------- cards ---------------- */

function SummaryCard({ icon: Icon, label, value, description, color }) {
  return (
    <div className="chart-summary-card" style={{ "--accent": color }}>
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

function KpiCard({ kpi, index }) {
  const label = kpi.label || kpi.name || kpi.title || `Metric ${index + 1}`;
  const value = kpi.value ?? kpi.metric ?? kpi.count ?? "-";

  return (
    <div
      className="charts-kpi-card"
      style={{ "--accent": COLORS[index % COLORS.length] }}
    >
      <span className="charts-kpi-label">{label}</span>
      <strong>{typeof value === "number" ? formatNumber(value) : value}</strong>
      {kpi.description && <small>{kpi.description}</small>}
    </div>
  );
}

const INSIGHT_TAGS = {
  risk: { label: "Watch out", color: "#f97316" },
  opportunity: { label: "Opportunity", color: "#10b981" },
  info: { label: "Good to know", color: "#6366f1" },
};

function InsightCard({ insight, index }) {
  const isText = typeof insight === "string";
  const title = isText ? null : insight?.title || insight?.headline || null;
  const text = isText
    ? insight
    : insight?.message ||
      insight?.insight ||
      insight?.description ||
      insight?.text ||
      insight?.title ||
      "Insight";
  const action = isText ? null : insight?.recommendation || insight?.action;
  const tag = isText ? null : INSIGHT_TAGS[insight?.type];

  return (
    <div
      className="chart-insight-card"
      style={{ "--accent": tag?.color || COLORS[index % COLORS.length] }}
    >
      <div className="chart-insight-icon">
        <Lightbulb size={17} />
      </div>
      <div>
        {tag && <span className="chart-insight-tag">{tag.label}</span>}
        {title && title !== text && <h4>{title}</h4>}
        <p>{text}</p>
        {action && <span className="chart-insight-action">{action}</span>}
      </div>
    </div>
  );
}

function ChartCard({ chart, index = 0, insight, onRemove, custom = false }) {
  const title = chart.title || chart.name || chart.chart_title || "Data Visualization";
  const description = chart.subtitle || "";
  const size = custom && getType(chart) === "table" ? "xl" : getSize(chart);
  const type = getType(chart).replace("_", " ");
  const note = insight || chart.insight || "";

  return (
    <div
      className={`chart-visual-card chart-size-${size}`}
      style={{ "--accent": COLORS[index % COLORS.length] }}
    >
      <div className="chart-visual-header">
        <div>
          <span className="chart-type-pill">{type}</span>
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

      <RenderChart chart={chart} height={HEIGHT[size]} />

      {note && (
        <div className="chart-card-insight">
          <Lightbulb size={14} />
          <span>{note}</span>
        </div>
      )}
    </div>
  );
}

/* ---------------- AI payload helpers ---------------- */

const asList = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return [];
};

const collectInsights = (dashboard) => {
  const ai = dashboard?.dashboard_ai;
  const list = [...asList(dashboard?.insights)];

  if (ai && typeof ai === "object" && !Array.isArray(ai)) {
    ["insights", "key_insights", "findings", "recommendations"].forEach((k) =>
      list.push(...asList(ai[k]))
    );
  } else {
    list.push(...asList(ai));
  }

  const seen = new Set();
  return list
    .filter((item) => {
      const key =
        typeof item === "string" ? item : item?.message || item?.title || "";
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 9);
};

const getSummaryText = (dashboard) => {
  const ai = dashboard?.dashboard_ai;
  if (typeof ai === "string") return ai;
  if (ai && typeof ai === "object") {
    const text = ai.summary || ai.executive_summary || ai.overview;
    return typeof text === "string" ? text : "";
  }
  return "";
};

const getChartInsightMap = (dashboard) => {
  const source = dashboard?.dashboard_ai?.chart_insights;
  const map = {};
  if (Array.isArray(source)) {
    source.forEach((item) => {
      const id = item?.chart_id || item?.id;
      const text = item?.insight || item?.text || item?.message;
      if (id && text) map[id] = text;
    });
  } else if (source && typeof source === "object") {
    Object.entries(source).forEach(([id, value]) => {
      if (typeof value === "string") map[id] = value;
    });
  }
  return map;
};

/* ---------------- page ---------------- */

export default function ChartsPage() {
  const dataset = useOutletContext();
  const datasetId = dataset?.dataset_id || dataset?.id;

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
        `${API_URL}/api/v1/datasets/${datasetId}/dashboard?version=${VERSION}`
      );
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Unable to load dashboard.");
      }
      setDashboard(result);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    setCustomCharts([]);
  }, [datasetId]);

  const handleCustomChartCreated = (chart) => {
    if (!chart) return;
    setCustomCharts((prev) => [
      ...prev,
      { ...chart, custom_id: `${Date.now()}-${Math.random()}` },
    ]);
  };

  const removeCustomChart = (id) =>
    setCustomCharts((prev) => prev.filter((c) => c.custom_id !== id));

  const summary = useMemo(() => dashboard?.summary || {}, [dashboard]);

  const kpis = useMemo(() => {
    const list = dashboard?.kpis || [];
    return Array.isArray(list) ? list : [];
  }, [dashboard]);

  const allCharts = useMemo(() => {
    const list = dashboard?.charts || [];
    return Array.isArray(list) ? list : [];
  }, [dashboard]);

  const charts = useMemo(() => allCharts.filter(isUsefulChart), [allCharts]);
  const insights = useMemo(() => collectInsights(dashboard), [dashboard]);
  const summaryText = useMemo(() => getSummaryText(dashboard), [dashboard]);
  const chartInsights = useMemo(() => getChartInsightMap(dashboard), [dashboard]);

  const usingCleaned = dashboard?.using_cleaned !== false;

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
      <div className="charts-page-header">
        <div>
          <div className="charts-heading-eyebrow">
            <Sparkles size={15} />
            Data analytics
          </div>
          <h1>Business Dashboard</h1>
          <p>Charts and insights generated from your dataset.</p>
        </div>

        <button
          type="button"
          className="charts-refresh-button"
          onClick={fetchDashboard}
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? "charts-spin" : ""} />
          Refresh
        </button>
      </div>

      <div className="charts-toolbar">
        <div className="charts-dataset-label">
          <Database size={15} />
          {dataset?.filename || "Current dataset"}
        </div>
        {dashboard && (
          <span className="charts-data-note">
            {usingCleaned
              ? "Using cleaned data"
              : "Using uploaded data. Apply cleaning for more accurate charts."}
          </span>
        )}
      </div>

      {error && (
        <div className="charts-error">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button type="button" onClick={fetchDashboard}>
            Retry
          </button>
        </div>
      )}

      {loading && !dashboard && (
        <div className="charts-loading">
          <div className="charts-loader" />
          <p>Preparing your dashboard...</p>
        </div>
      )}

      {dashboard && (
        <>
          <div className="charts-summary-grid">
            <SummaryCard
              icon={Database}
              color={COLORS[0]}
              label="Total rows"
              value={formatNumber(summary.total_rows)}
              description="Records in dataset"
            />
            <SummaryCard
              icon={Layers}
              color={COLORS[1]}
              label="Total columns"
              value={formatNumber(summary.total_columns)}
              description="Dataset features"
            />
            <SummaryCard
              icon={BarChart3}
              color={COLORS[2]}
              label="Charts"
              value={formatNumber(charts.length + customCharts.length)}
              description="Useful visualizations"
            />
            <SummaryCard
              icon={Activity}
              color={COLORS[3]}
              label="Insights"
              value={formatNumber(insights.length)}
              description="Business observations"
            />
          </div>

          {kpis.length > 0 && (
            <section className="charts-kpi-section">
              <div className="charts-section-heading">
                <div>
                  <h2>Key metrics</h2>
                  <p>The numbers that matter most in this dataset</p>
                </div>
              </div>
              <div className="charts-kpi-grid">
                {kpis.map((kpi, index) => (
                  <KpiCard kpi={kpi} index={index} key={index} />
                ))}
              </div>
            </section>
          )}

          <div className="charts-mode-section">
            <div>
              <h2>Dashboard view</h2>
              <p>Automatic business analysis, or compare columns yourself.</p>
            </div>

            <div className="charts-mode-switch">
              <button
                type="button"
                className={mode === "ai" ? "active" : ""}
                onClick={() => setMode("ai")}
              >
                <Sparkles size={16} />
                AI dashboard
              </button>
              <button
                type="button"
                className={mode === "interactive" ? "active" : ""}
                onClick={() => setMode("interactive")}
              >
                <SlidersHorizontal size={16} />
                Column explorer
              </button>
            </div>
          </div>

          {mode === "ai" && (
            <div className="charts-dashboard-content">
              {summaryText && <div className="charts-ai-summary">{summaryText}</div>}

              {insights.length > 0 && (
                <section className="charts-insights-section">
                  <div className="charts-section-heading">
                    <div>
                      <h2>Business insights</h2>
                      <p>What stands out in your data.</p>
                    </div>
                  </div>
                  <div className="charts-insights-grid">
                    {insights.map((insight, index) => (
                      <InsightCard insight={insight} index={index} key={index} />
                    ))}
                  </div>
                </section>
              )}

              <section className="charts-visualizations-section">
                <div className="charts-section-heading">
                  <div>
                    <h2>Visual analytics</h2>
                    <p>Charts picked from the columns in your data. ID columns are skipped.</p>
                  </div>
                  <span className="charts-count-label">{charts.length} charts</span>
                </div>

                {charts.length > 0 ? (
                  <div className="charts-visual-grid">
                    {charts.map((chart, index) => (
                      <ChartCard
                        key={chart.id || index}
                        chart={chart}
                        index={index}
                        insight={chartInsights[chart.id]}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="charts-empty-state">
                    <BarChart3 size={32} />
                    <h3>No automatic charts available</h3>
                    <p>
                      This dataset does not have enough useful columns for
                      automatic charts. Try the column explorer.
                    </p>
                  </div>
                )}
              </section>
            </div>
          )}

          {mode === "interactive" && (
            <div className="charts-interactive-content">
              <div className="charts-interactive-intro">
                <div className="charts-interactive-icon">
                  <SlidersHorizontal size={22} />
                </div>
                <div>
                  <h2>Explore how columns behave</h2>
                  <p>
                    Pick columns and a chart type to see how one column
                    affects another.
                  </p>
                </div>
              </div>

              <InteractiveChartBuilder
                datasetId={datasetId}
                version={VERSION}
                onChartCreated={handleCustomChartCreated}
              />

              <section className="charts-custom-section">
                <div className="charts-section-heading">
                  <div>
                    <h2>My charts</h2>
                    <p>Charts you created for this dataset.</p>
                  </div>
                  <span className="charts-count-label">{customCharts.length} charts</span>
                </div>

                {customCharts.length > 0 ? (
                  <div className="charts-visual-grid">
                    {customCharts.map((chart, index) => (
                      <ChartCard
                        key={chart.custom_id}
                        chart={chart}
                        index={index + 3}
                        custom
                        onRemove={() => removeCustomChart(chart.custom_id)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="charts-empty-state">
                    <Plus size={32} />
                    <h3>No charts yet</h3>
                    <p>Create a chart with the builder above and it will appear here.</p>
                  </div>
                )}
              </section>
            </div>
          )}
        </>
      )}

      {!loading && !dashboard && !error && (
        <div className="charts-empty-state">
          <Info size={30} />
          <h3>Dashboard is not available</h3>
          <p>Refresh the dashboard or upload your dataset again.</p>
        </div>
      )}
    </div>
  );
}
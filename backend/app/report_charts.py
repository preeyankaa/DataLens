"""
app/report_charts.py

Draws the dashboard charts as PNG images for the PDF report.

Handles every chart shape the dashboard produces:
  bar, horizontal_bar, line, area (also multi-series), donut / pie, scatter,
  histogram, treemap and heatmap (wide or x/y/value rows).

Uses matplotlib's object API (Figure, not pyplot) so it is safe to call from
several FastAPI worker threads at once.
"""

import io
import math

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

COLORS = [
    "#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ec4899",
    "#8b5cf6", "#f97316", "#14b8a6", "#3b82f6", "#84cc16",
]
INK = "#3d3b52"
MUTED = "#8d8aa0"
GRID = "#e9e8f2"

NAN = float("nan")


# --------------------------------------------------
# helpers
# --------------------------------------------------

def compact(value):
    """1234 -> 1.2K, 2500000 -> 2.5M"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(v):
        return ""
    a = abs(v)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= limit:
            text = f"{v / limit:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return f"{v:,.0f}" if a >= 100 or v == int(v) else f"{v:,.2f}"


def shorten(value, size=14):
    text = str(value if value is not None else "")
    return text if len(text) <= size else text[: size - 1] + "…"


def number(value):
    if isinstance(value, bool):
        return NAN
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else NAN
    return NAN


def axis_keys(chart, data):
    """Work out which row keys hold the labels and the numbers."""
    first = data[0] if data else {}
    keys = list(first.keys())

    if str(chart.get("chart_type")) == "scatter" and "x" in first and "y" in first:
        return {"x": "x", "value": "y", "series": ["y"]}

    x_key = next(
        (k for k in ("category", "period", "range", "name", "label") if k in first),
        None,
    )
    if x_key is None:
        x_key = next((k for k in keys if not isinstance(first[k], (int, float))), keys[0] if keys else "x")

    numeric = [
        k for k in keys
        if k != x_key and isinstance(first[k], (int, float)) and not isinstance(first[k], bool)
    ]
    value_key = "value" if "value" in first else (numeric[0] if numeric else "value")
    series = numeric[:5] if ("value" not in first and len(numeric) > 1) else [value_key]

    return {"x": x_key, "value": value_key, "series": series}


def _new_figure(width_in, height_in, dpi):
    figure = Figure(figsize=(width_in, height_in), dpi=dpi, facecolor="white")
    FigureCanvasAgg(figure)
    return figure


def _style(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=6.5, length=0)
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.set_facecolor("white")


def _money_axis(axis):
    axis.set_major_formatter(FuncFormatter(lambda v, _: compact(v)))


def _label_positions(count, limit=8):
    """Which category positions get a tick label (keeps long axes readable)."""
    if count <= limit:
        return list(range(count))
    step = math.ceil(count / limit)
    return list(range(0, count, step))


def _to_png(figure):
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0.06, facecolor="white")
    return buffer.getvalue()


# --------------------------------------------------
# chart types
# --------------------------------------------------

def _bar(fig, data, keys):
    ax = fig.add_subplot(111)
    labels = [shorten(r.get(keys["x"]), 12) for r in data]
    series = keys["series"]
    n = len(data)
    positions = list(range(n))

    if len(series) == 1:
        values = [number(r.get(series[0])) for r in data]
        colors = [COLORS[i % len(COLORS)] for i in range(n)] if n <= 12 else COLORS[0]
        bars = ax.bar(positions, values, color=colors, width=0.7)
        if n <= 8:
            for rect, value in zip(bars, values):
                if value == value:
                    ax.annotate(
                        compact(value), (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                        ha="center", va="bottom", fontsize=6, color=INK,
                        xytext=(0, 2), textcoords="offset points",
                    )
    else:
        width = 0.8 / len(series)
        for s, key in enumerate(series):
            ax.bar(
                [p - 0.4 + width * (s + 0.5) for p in positions],
                [number(r.get(key)) for r in data],
                width=width, color=COLORS[s % len(COLORS)], label=shorten(key, 16),
            )
        ax.legend(fontsize=6, frameon=False, ncol=min(len(series), 3))

    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=30 if n > 5 else 0, ha="right" if n > 5 else "center")
    _style(ax, "y")
    _money_axis(ax.yaxis)
    ax.margins(y=0.12)


def _horizontal_bar(fig, data, keys):
    ax = fig.add_subplot(111)
    labels = [shorten(r.get(keys["x"]), 22) for r in data]
    values = [number(r.get(keys["value"])) for r in data]
    positions = list(range(len(data)))

    bars = ax.barh(positions, values, color=[COLORS[i % len(COLORS)] for i in positions], height=0.68)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    _style(ax, "x")
    _money_axis(ax.xaxis)
    ax.tick_params(axis="y", labelsize=6.5)

    for rect, value in zip(bars, values):
        if value == value:
            ax.annotate(
                compact(value), (rect.get_width(), rect.get_y() + rect.get_height() / 2),
                va="center", fontsize=6, color=INK, xytext=(3, 0), textcoords="offset points",
            )
    ax.margins(x=0.14)


def _line_or_area(fig, data, keys, area):
    ax = fig.add_subplot(111)
    n = len(data)
    positions = list(range(n))
    series = keys["series"]

    for s, key in enumerate(series):
        values = [number(r.get(key)) for r in data]
        color = COLORS[s % len(COLORS)]
        ax.plot(
            positions, values, color=color, linewidth=1.8,
            marker="o" if n <= 30 else None, markersize=2.6, label=shorten(key, 16),
        )
        if area:
            ax.fill_between(positions, values, color=color, alpha=0.18, linewidth=0)

    ticks = _label_positions(n, 8)
    ax.set_xticks(ticks)
    ax.set_xticklabels([shorten(data[i].get(keys["x"]), 10) for i in ticks], rotation=0)
    ax.set_xlim(-0.3, n - 0.7 if n > 1 else 0.5)
    _style(ax, "y")
    _money_axis(ax.yaxis)
    if len(series) > 1:
        ax.legend(fontsize=6, frameon=False, ncol=min(len(series), 4), loc="upper left")


def _donut(fig, data, keys, donut):
    ax = fig.add_subplot(111)
    rows = [(shorten(r.get(keys["x"]), 16), number(r.get(keys["value"]))) for r in data]
    rows = [(name, v) for name, v in rows if v == v and v > 0]
    if not rows:
        raise ValueError("no positive values")

    names = [r[0] for r in rows]
    values = [r[1] for r in rows]
    total = sum(values)
    colors = [COLORS[i % len(COLORS)] for i in range(len(rows))]

    ax.pie(
        values, colors=colors, startangle=90, counterclock=False,
        wedgeprops={"width": 0.42 if donut else 1, "edgecolor": "white", "linewidth": 1.2},
        autopct=lambda p: f"{p:.0f}%" if p >= 6 else "",
        pctdistance=0.78 if donut else 0.65,
        textprops={"fontsize": 6.5, "color": "white", "fontweight": "bold"},
    )
    ax.legend(
        [f"{n}  ({v / total * 100:.0f}%)" for n, v in rows],
        loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=6.5, frameon=False,
    )
    ax.set_aspect("equal")


def _scatter(fig, data, keys):
    ax = fig.add_subplot(111)
    points = [(number(r.get("x")), number(r.get("y"))) for r in data]
    points = [(x, y) for x, y in points if x == x and y == y]
    if not points:
        raise ValueError("no points")

    ax.scatter(
        [p[0] for p in points], [p[1] for p in points],
        s=12, color=COLORS[4], alpha=0.6, linewidths=0,
    )
    _style(ax, "both")
    _money_axis(ax.xaxis)
    _money_axis(ax.yaxis)


def _histogram(fig, data, keys):
    ax = fig.add_subplot(111)
    values = [number(r.get(keys["value"])) for r in data]
    positions = list(range(len(data)))

    ax.bar(positions, values, color=COLORS[1], width=0.92)
    ticks = _label_positions(len(data), 6)
    ax.set_xticks(ticks)
    ax.set_xticklabels([shorten(data[i].get(keys["x"]), 14) for i in ticks], rotation=25, ha="right")
    _style(ax, "y")
    _money_axis(ax.yaxis)


def _worst_ratio(row, side):
    total = sum(row)
    return max(
        side * side * max(row) / (total * total),
        total * total / (side * side * min(row)),
    )


def _squarify(areas, x, y, w, h):
    rects, remaining = [], list(areas)
    while remaining:
        side = min(w, h)
        row, i = [remaining[0]], 1
        while i < len(remaining):
            candidate = row + [remaining[i]]
            if _worst_ratio(candidate, side) <= _worst_ratio(row, side):
                row, i = candidate, i + 1
            else:
                break
        remaining = remaining[len(row):]
        total = sum(row)
        if w >= h:
            row_w, cursor = total / h, y
            for area in row:
                row_h = area / row_w
                rects.append((x, cursor, row_w, row_h))
                cursor += row_h
            x, w = x + row_w, w - row_w
        else:
            row_h, cursor = total / w, x
            for area in row:
                row_w = area / row_h
                rects.append((cursor, y, row_w, row_h))
                cursor += row_w
            y, h = y + row_h, h - row_h
    return rects


def _treemap(fig, data, keys):
    ax = fig.add_subplot(111)
    rows = [(str(r.get(keys["x"])), number(r.get(keys["value"]))) for r in data]
    rows = sorted([(n, v) for n, v in rows if v == v and v > 0], key=lambda r: -r[1])
    if not rows:
        raise ValueError("no positive values")

    width, height = 100.0, 60.0
    total = sum(v for _, v in rows)
    areas = [v / total * width * height for _, v in rows]

    for index, ((name, value), (x, y, w, h)) in enumerate(zip(rows, _squarify(areas, 0, 0, width, height))):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=COLORS[index % len(COLORS)], edgecolor="white", linewidth=1.5))
        if w > 13 and h > 9:
            ax.text(x + w / 2, y + h / 2, f"{shorten(name, 16)}\n{compact(value)}",
                    ha="center", va="center", color="white", fontsize=6.5, fontweight="bold")

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")


def _heatmap(fig, data, keys):
    first = data[0]

    if "x" in first and "y" in first and "value" in first:     # long format
        columns = list(dict.fromkeys(str(r["x"]) for r in data))
        rows = list(dict.fromkeys(str(r["y"]) for r in data))
        lookup = {(str(r["y"]), str(r["x"])): number(r.get("value")) for r in data}
        matrix = [[lookup.get((row, col), NAN) for col in columns] for row in rows]
    else:                                                       # wide format
        columns = [k for k in first.keys() if k not in ("name", "label")]
        rows = [str(r.get("name", r.get("label", i + 1))) for i, r in enumerate(data)]
        matrix = [[number(r.get(c)) for c in columns] for r in data]

    flat = [v for row in matrix for v in row if v == v]
    if not flat:
        raise ValueError("no numbers")

    top = max(abs(v) for v in flat) or 1.0
    has_negative = any(v < 0 for v in flat)

    if has_negative:
        cmap = LinearSegmentedColormap.from_list("div", ["#ec4899", "#ffffff", "#6366f1"])
        low, high = -top, top
    else:
        cmap = LinearSegmentedColormap.from_list("seq", ["#f4f4ff", "#6366f1"])
        low, high = 0, top

    ax = fig.add_subplot(111)
    ax.imshow(matrix, cmap=cmap, vmin=low, vmax=high, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels([shorten(c, 11) for c in columns], rotation=30, ha="right")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([shorten(r, 14) for r in rows])
    ax.tick_params(colors=MUTED, labelsize=6.5, length=0)
    for side in ax.spines.values():
        side.set_visible(False)

    decimals = has_negative and top <= 1.0
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value == value:
                dark = abs(value) > top * 0.55
                ax.text(j, i, f"{value:.2f}" if decimals else compact(value),
                        ha="center", va="center", fontsize=6,
                        color="white" if dark else INK)


# --------------------------------------------------
# public
# --------------------------------------------------

def render_chart_png(chart, width_in, height_in, dpi=200):
    """Return PNG bytes for one dashboard chart. Raises ValueError if it cannot be drawn."""
    data = chart.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("chart has no data")

    kind = str(chart.get("chart_type") or chart.get("type") or "bar").lower()
    keys = axis_keys(chart, data)
    figure = _new_figure(width_in, height_in, dpi)

    if kind == "heatmap":
        _heatmap(figure, data, keys)
    elif kind in ("donut", "pie"):
        _donut(figure, data, keys, donut=(kind == "donut"))
    elif kind == "horizontal_bar":
        _horizontal_bar(figure, data, keys)
    elif kind in ("line", "trend"):
        _line_or_area(figure, data, keys, area=False)
    elif kind == "area":
        _line_or_area(figure, data, keys, area=True)
    elif kind == "scatter":
        _scatter(figure, data, keys)
    elif kind == "treemap":
        _treemap(figure, data, keys)
    elif kind == "histogram":
        _histogram(figure, data, keys)
    else:
        _bar(figure, data, keys)

    return _to_png(figure)
"""
app/dashboard_builder.py

Adaptive dashboard generator. It sits on top of app/visualization.py and
reuses its column-type detection, so it works with any dataset:

  * ID columns are never charted
  * a "main measure" (revenue / profit / first numeric) is picked automatically
  * charts are chosen by what columns exist: trend, share (donut), ranking
    (horizontal bar), treemap, heatmap, multi-series trend, weekday pattern,
    "how column A affects column B", scatter, histogram, correlation
  * every chart gets a fact-based `insight`, plus a top-level `insights` list

Use:  from app.dashboard_builder import build_dashboard_data
"""

import numpy as np
import pandas as pd

from app.visualization import (
    build_visualization_data,
    _detect_types,
    _role_columns,
    _clean_numeric,
    _name,
    _normalize_category,
    _safe_number,
    _make_chart,
    _is_identifier,
    _to_binary_flag,
    _return_rate_chart,
    _customer_orders_chart,
    _scatter_chart,
    _histogram_chart,
    MIN_GROUP_RECORDS,
)

MAX_DIM = 15          # max categories for donut / heatmap / treemap dimensions
MAX_CHARTS = 14
WEEKDAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


# --------------------------------------------------------------------------
# chart builders
# --------------------------------------------------------------------------

def _agg_word(agg):
    return {"sum": "Total", "mean": "Average"}.get(agg, "")


def _dim_chart(df, category, metric, agg, chart_type, size, title, top_n=10):
    """Group `metric` by `category`. metric=None counts rows."""
    cat = _normalize_category(df[category])

    if metric is None:
        grouped = cat.value_counts()
        agg, y_label = "count", "Records"
    else:
        frame = pd.DataFrame({"c": cat, "v": _clean_numeric(df[metric])})
        frame = frame.dropna(subset=["v"])
        if frame.empty:
            return None
        grouped = frame.groupby("c")["v"].agg(agg)
        y_label = f"{_agg_word(agg)} {metric}".strip()

    grouped = grouped.sort_values(ascending=False).head(top_n)
    if len(grouped) < 2:
        return None

    data = [
        {"category": str(k), "value": _safe_number(v)}
        for k, v in grouped.items()
    ]

    return _make_chart(
        f"{chart_type}_{_name(metric or 'count')}_by_{_name(category)}",
        chart_type, title, "", str(category), y_label, data, "",
        size, aggregation=agg,
    )


def _trend(df, date_col, parsed, metric, agg, chart_type, size):
    frame = pd.DataFrame({
        "d": parsed, "v": _clean_numeric(df[metric]),
    }).dropna()
    if frame.empty:
        return None

    span = (frame["d"].max() - frame["d"].min()).days
    freq = "M" if span >= 60 else "D"
    frame["p"] = frame["d"].dt.to_period(freq).astype(str)

    grouped = frame.groupby("p")["v"].agg(agg).sort_index()
    if len(grouped) < 2:
        return None

    data = [
        {"period": str(p), "value": _safe_number(v)}
        for p, v in grouped.items()
    ]
    label = "monthly" if freq == "M" else "daily"

    return _make_chart(
        f"{chart_type}_{_name(metric)}_over_{_name(date_col)}",
        chart_type,
        f"{_agg_word(agg)} {metric} over time ({label})".strip(),
        "", str(date_col), metric, data, "", size, aggregation=agg,
    )


def _multi_trend(df, date_col, parsed, metric, category, agg, top=4):
    cat = _normalize_category(df[category])
    top_cats = cat.value_counts().head(top).index

    frame = pd.DataFrame({
        "d": parsed, "c": cat, "v": _clean_numeric(df[metric]),
    }).dropna(subset=["d", "v"])
    frame = frame[frame["c"].isin(top_cats)]
    if frame.empty:
        return None

    span = (frame["d"].max() - frame["d"].min()).days
    freq = "M" if span >= 60 else "D"
    frame["p"] = frame["d"].dt.to_period(freq).astype(str)

    pivot = frame.pivot_table(
        index="p", columns="c", values="v", aggfunc=agg, fill_value=0,
    ).sort_index()

    if len(pivot) < 3 or pivot.shape[1] < 2:
        return None

    data = []
    for period, row in pivot.iterrows():
        item = {"period": str(period)}
        for col, val in row.items():
            item[str(col)] = _safe_number(val)
        data.append(item)

    return _make_chart(
        f"multi_trend_{_name(metric)}_by_{_name(category)}",
        "area",
        f"{metric} trend by {category}",
        "", str(date_col), metric, data, "", "large", aggregation=agg,
    )


def _weekday(df, date_col, parsed, metric, agg):
    frame = pd.DataFrame({
        "d": parsed, "v": _clean_numeric(df[metric]),
    }).dropna()
    if frame.empty or (frame["d"].max() - frame["d"].min()).days < 14:
        return None

    frame["day"] = frame["d"].dt.day_name()
    grouped = frame.groupby("day")["v"].agg(agg).reindex(WEEKDAYS).dropna()
    if len(grouped) < 3:
        return None

    data = [
        {"category": d, "value": _safe_number(v)}
        for d, v in grouped.items()
    ]
    return _make_chart(
        f"weekday_{_name(metric)}", "bar",
        f"{_agg_word(agg)} {metric} by weekday".strip(),
        "", "Weekday", metric, data, "", "medium", aggregation=agg,
    )


def _heat_pivot(df, row_col, col_col, metric, agg):
    r = _normalize_category(df[row_col])
    c = _normalize_category(df[col_col])

    if metric is None:
        v, func = pd.Series(1.0, index=df.index), "sum"
    else:
        v, func = _clean_numeric(df[metric]), ("sum" if agg == "sum" else "mean")

    frame = pd.DataFrame({"r": r, "c": c, "v": v}).dropna(subset=["v"])
    if frame.empty:
        return None

    pivot = frame.pivot_table(
        index="r", columns="c", values="v", aggfunc=func, fill_value=0,
    )
    rows = pivot.sum(axis=1).sort_values(ascending=False).head(8).index
    cols = pivot.sum(axis=0).sort_values(ascending=False).head(6).index
    pivot = pivot.loc[rows, cols]

    if pivot.shape[0] < 2 or pivot.shape[1] < 2:
        return None

    data = []
    for name, row in pivot.iterrows():
        item = {"name": str(name)}
        for col, val in row.items():
            item[str(col)] = _safe_number(val)
        data.append(item)

    what = metric or "Records"
    return _make_chart(
        f"heatmap_{_name(what)}_{_name(row_col)}_{_name(col_col)}",
        "heatmap", f"{what}: {row_col} × {col_col}", "",
        str(col_col), str(row_col), data, "", "medium", aggregation=func,
    )


def _corr_heatmap(df, metrics):
    usable = [
        c for c in metrics
        if _clean_numeric(df[c]).notna().sum() >= 5
        and _clean_numeric(df[c]).nunique() > 5
    ][:8]
    if len(usable) < 2:
        return None

    corr = df[usable].apply(_clean_numeric).corr().round(2)
    data = []
    for name, row in corr.iterrows():
        item = {"name": str(name)}
        for col, val in row.items():
            item[str(col)] = None if pd.isna(val) else float(val)
        data.append(item)

    return _make_chart(
        "numeric_correlation", "heatmap", "How numeric columns relate",
        "", "Metric", "Metric", data, "", "medium",
        aggregation="correlation",
    )


def _bucket_chart(df, driver, target, agg, percent=False, title=None):
    """How does `driver` (numeric) affect `target`?  Groups driver into ranges."""
    x = _clean_numeric(df[driver])
    y = _to_binary_flag(df[target]) if percent else _clean_numeric(df[target])
    frame = pd.DataFrame({"x": x, "y": y}).dropna()

    if len(frame) < 20 or frame["x"].nunique() < 2:
        return None

    if frame["x"].nunique() <= 6:
        key = frame["x"]
    else:
        key = pd.qcut(frame["x"], q=5, duplicates="drop")

    grouped = frame.groupby(key, observed=True)["y"].agg(agg)
    if percent:
        grouped = grouped * 100
    if len(grouped) < 2:
        return None

    def label(k):
        if isinstance(k, pd.Interval):
            return f"{k.left:.4g}–{k.right:.4g}"
        return f"{float(k):g}"

    data = [{"category": label(k), "value": _safe_number(v)}
            for k, v in grouped.items()]

    word = "Return rate (%)" if percent else f"{_agg_word(agg)} {target}".strip()
    return _make_chart(
        f"effect_{_name(driver)}_on_{_name(target)}", "bar",
        title or f"{word} by {driver}", "",
        str(driver), word, data, "", "medium", aggregation=agg,
    )


def _order_hist(df, order_id, revenue):
    t = pd.DataFrame({
        "o": df[order_id], "v": _clean_numeric(df[revenue]),
    }).dropna()
    totals = t.groupby("o")["v"].sum()
    if len(totals) < 5 or totals.nunique() < 2:
        return None

    counts, edges = np.histogram(totals, bins=8)
    data = [
        {"range": f"{edges[i]:.0f}–{edges[i + 1]:.0f}", "value": int(counts[i])}
        for i in range(len(counts))
    ]
    return _make_chart(
        "order_value_distribution", "histogram", "Order value distribution",
        "", "Order value", "Orders", data,
        f"Average order value: {_safe_number(totals.mean())}.",
        "medium", aggregation="sum_by_order",
    )


# --------------------------------------------------------------------------
# insights (rule based, from the chart data itself)
# --------------------------------------------------------------------------

def _describe_chart(chart):
    data = chart.get("data") or []
    kind = chart.get("chart_type")
    if not data:
        return None

    if kind in {"bar", "horizontal_bar", "donut", "pie", "treemap"}:
        vals = [
            (str(r.get("category")), r.get("value")) for r in data
            if isinstance(r.get("value"), (int, float))
        ]
        if len(vals) < 2:
            return None
        top, top_v = max(vals, key=lambda kv: kv[1])
        low, low_v = min(vals, key=lambda kv: kv[1])
        total = sum(v for _, v in vals)
        additive = chart.get("aggregation") in {
            "sum", "count", "sum_quantity_by_product",
            "unique_orders_per_customer", "unique_orders_per_product",
        }
        if additive and total > 0:
            return (f"{top} leads with {top_v / total * 100:.0f}% of the "
                    f"total shown; {low} is lowest.")
        return f"{top} is highest ({top_v:g}); {low} is lowest ({low_v:g})."

    if kind in {"line", "area"}:
        keys = [k for k in data[0] if k != "period"]
        if "value" in data[0]:
            vals = [r["value"] for r in data if r.get("value") is not None]
            if len(vals) < 2 or vals[0] in (0, None):
                return None
            peak = max(data, key=lambda r: r.get("value") or 0)
            change = (vals[-1] - vals[0]) / abs(vals[0]) * 100
            return (f"Peak was {peak['period']}. Latest period is "
                    f"{change:+.0f}% versus the first.")
        totals = {k: sum((r.get(k) or 0) for r in data) for k in keys}
        grand = sum(totals.values())
        if grand > 0:
            top = max(totals, key=totals.get)
            return f"{top} contributes the most ({totals[top] / grand * 100:.0f}% of shown total)."
        return None

    if kind == "histogram":
        top = max(data, key=lambda r: r.get("value") or 0)
        total = sum(r.get("value") or 0 for r in data)
        if total:
            return f"Most records fall in {top['range']} ({top['value'] / total * 100:.0f}%)."
        return None

    if kind == "heatmap":
        keys = [k for k in data[0] if k != "name"]
        best = None
        for row in data:
            for k in keys:
                v = row.get(k)
                if not isinstance(v, (int, float)):
                    continue
                if chart.get("aggregation") == "correlation":
                    if row["name"] == k:
                        continue
                    score = abs(v)
                else:
                    score = v
                if best is None or score > best[0]:
                    best = (score, row["name"], k, v)
        if not best:
            return None
        if chart.get("aggregation") == "correlation":
            strength = "strong" if best[0] >= 0.6 else "moderate" if best[0] >= 0.3 else "weak"
            return f"Strongest link: {best[1]} and {best[2]} ({best[3]:+.2f}, {strength})."
        return f"Highest combination: {best[1]} × {best[2]} ({best[3]:g})."

    if kind == "scatter":
        return chart.get("insight_hint") or None

    return None


def _build_insights(charts, limit=6):
    out = []
    for chart in charts:
        text = chart.get("insight")
        if text and chart["chart_type"] != "scatter":
            out.append({"title": chart["title"], "message": text})
        if len(out) >= limit:
            break
    return out


def _select_diverse(charts, limit):
    if len(charts) <= limit:
        return charts
    chosen, counts = [], {}
    for i, c in enumerate(charts):
        t = c["chart_type"]
        if counts.get(t, 0) < 2:
            chosen.append(i)
            counts[t] = counts.get(t, 0) + 1
    chosen = chosen[:limit]
    for i in range(len(charts)):
        if len(chosen) >= limit:
            break
        if i not in chosen:
            chosen.append(i)
    return [charts[i] for i in sorted(chosen)]


# --------------------------------------------------------------------------
# business insights  (work for any size of business / any dataset)
#
# Rules used everywhere:
#   * talk in percentages and ratios, never assume a currency or a scale
#   * every insight says what it means and what to try next
#   * small samples and weak evidence get a caution instead of a strong claim
# --------------------------------------------------------------------------

def _fmt(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:.2f}M"
    if a >= 1e4:
        return f"{v / 1e3:.1f}K"
    if a >= 100:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def _ins(kind, title, message, rec=None):
    item = {"type": kind, "title": title, "message": message}
    if rec:
        item["recommendation"] = rec
    return item


def _grouped(df, cat, metric, agg):
    frame = pd.DataFrame({
        "c": _normalize_category(df[cat]),
        "v": _clean_numeric(df[metric]),
    }).dropna(subset=["v"])
    if frame.empty:
        return pd.Series(dtype=float)
    g = frame.groupby("c")["v"].agg(agg).sort_values(ascending=False)
    return g[g.index != "(Missing)"]


def _ins_trend(df, ctx, out):
    m, agg = ctx["measure"], ctx["agg"]
    if not m or not ctx["dates"]:
        return
    _, parsed = next(iter(ctx["dates"].items()))
    f = pd.DataFrame({"d": parsed, "v": _clean_numeric(df[m])}).dropna()
    if len(f) < 10:
        return
    span = (f["d"].max() - f["d"].min()).days
    if span < 14:
        return

    mid = f["d"].min() + pd.Timedelta(days=span / 2)
    a, b = f[f["d"] < mid], f[f["d"] >= mid]
    if a.empty or b.empty:
        return
    half = max(span / 2, 1)
    if agg == "sum":
        va, vb = a["v"].sum() / half, b["v"].sum() / half
    else:
        va, vb = a["v"].mean(), b["v"].mean()
    if not va or va <= 0:
        return

    g = (vb - va) / va * 100
    word = "total" if agg == "sum" else "average"
    caution = " The date range is short, so treat this as an early signal." if span < 30 else ""

    if g >= 10:
        out.append(_ins(
            "opportunity", f"{m} is growing",
            f"{word.capitalize()} {m} per day in the later half of your data is {g:.0f}% higher than in the earlier half.{caution}",
            "Find out what changed (new product, offer, season) and keep doing it.",
        ))
    elif g <= -10:
        out.append(_ins(
            "risk", f"{m} is slowing down",
            f"{word.capitalize()} {m} per day in the later half of your data is {abs(g):.0f}% lower than in the earlier half.{caution}",
            "Check what changed in that period: stock, prices, campaigns, or a drop in repeat customers.",
        ))
    else:
        out.append(_ins(
            "info", f"{m} is steady",
            f"{word.capitalize()} {m} per day is about the same in both halves of your data ({g:+.0f}%).{caution}",
            "Steady is fine, but try one new offer or channel to see if you can lift it.",
        ))


def _ins_concentration(df, ctx, out):
    m, agg = ctx["measure"], ctx["agg"]
    if not m:
        return
    for dim in ctx["dims"][:2]:
        g = _grouped(df, dim, m, agg)
        if len(g) < 2 or g.sum() <= 0:
            continue
        top, low = g.index[0], g.index[-1]
        if agg == "sum":
            total = g.sum()
            share, s2 = g.iloc[0] / total * 100, g.iloc[1] / total * 100
            low_share = g.iloc[-1] / total * 100
            if share >= 50:
                out.append(_ins(
                    "risk", f"{m} depends on one {dim}",
                    f"{top} brings {share:.0f}% of total {m}. The next one, {g.index[1]}, brings {s2:.0f}%.",
                    f"If {top} has a bad month, your numbers drop sharply. Try to grow the other {dim} groups.",
                ))
            elif g.iloc[0] < 1.25 * g.iloc[-1]:
                out.append(_ins(
                    "info", f"{m} is evenly spread across {dim}",
                    f"No {dim} group stands out: the best ({top}) and the weakest ({low}) are close ({share:.0f}% vs {low_share:.0f}%).",
                    f"Growth is more likely to come from other levers (price, new products, channels) than from this {dim}.",
                ))
            else:
                out.append(_ins(
                    "opportunity", f"Best and weakest {dim}",
                    f"{top} is the strongest {dim} ({share:.0f}% of {m}). {low} is the weakest ({low_share:.0f}%).",
                    f"Look at why {top} works and try the same for {low}, or decide if {low} deserves less effort.",
                ))
        else:
            out.append(_ins(
                "info", f"{m} differs by {dim}",
                f"Average {m} is highest for {top} ({_fmt(g.iloc[0])}) and lowest for {low} ({_fmt(g.iloc[-1])}).",
                f"Check what is different about {top} (pricing, customers, product mix).",
            ))


def _ins_pareto(df, ctx, out):
    m = ctx["measure"]
    if not m or ctx["agg"] != "sum":
        return
    for ent in ctx["entities"][:2]:
        g = _grouped(df, ent, m, "sum")
        n = len(g)
        if n < 10 or g.sum() <= 0:
            continue
        k = max(1, int(round(n * 0.2)))
        share = g.iloc[:k].sum() / g.sum() * 100
        if share >= 60:
            out.append(_ins(
                "risk" if share >= 80 else "info",
                f"A few {ent} values carry most of {m}",
                f"The top {k} of {n} {ent} values (20%) bring {share:.0f}% of total {m}.",
                f"Keep these top {ent} values in stock, well served and well priced. Losing one would be felt.",
            ))


def _ins_returns(df, ctx, out):
    ret = ctx["roles"]["returned"]
    if not ret:
        return
    flag = _to_binary_flag(df[ret])
    valid = flag.dropna()
    if len(valid) < 20:
        return
    rate = valid.mean() * 100
    if rate == 0:
        return

    worst = None
    for dim in ctx["dims"][:3]:
        frame = pd.DataFrame({"c": _normalize_category(df[dim]), "v": flag}).dropna(subset=["v"])
        g = frame.groupby("c")["v"].agg(["mean", "count"])
        g = g[g["count"] >= MIN_GROUP_RECORDS]
        if g.empty:
            continue
        top = g["mean"].idxmax()
        val = g.loc[top, "mean"] * 100
        if worst is None or val > worst[2]:
            worst = (dim, top, val)

    msg = f"{rate:.1f}% of records are returned."
    kind = "risk" if rate >= 10 else "info"
    rec = "Read the return reasons and fix the biggest cause (quality, size, description)."
    if worst and worst[2] >= max(5, rate * 1.5):
        msg += f" {worst[1]} ({worst[0]}) is the highest at {worst[2]:.1f}%."
        rec = f"Start with {worst[1]}: check product quality, listing accuracy and delivery for it."
        kind = "risk"
    out.append(_ins(kind, "Returns", msg, rec))


def _ins_orders(df, ctx, out):
    oid, rev = ctx["roles"]["order_id"], ctx["roles"]["revenue"]
    if not oid or not rev:
        return
    frame = pd.DataFrame({"o": df[oid], "v": _clean_numeric(df[rev])}).dropna()
    totals = frame.groupby("o")["v"].sum()
    if len(totals) < 5:
        return
    aov, med = totals.mean(), totals.median()
    msg = f"Average order value is {_fmt(aov)} across {len(totals)} orders."
    if med > 0 and aov > 1.5 * med:
        msg += f" A few large orders pull the average up (typical order: {_fmt(med)})."

    sizes = frame.groupby("o").size()
    multi = (sizes > 1).mean() * 100
    if multi < 40:
        rec = "Most orders have one item. Bundles or an 'add one more' offer can raise order value."
    else:
        rec = "Many orders have several items. Bundles and a free-delivery threshold can push this higher."
    out.append(_ins("opportunity", "Order value", msg, rec))


def _ins_repeat(df, ctx, out):
    oid = ctx["roles"]["order_id"]
    cust = ctx["roles"]["customer_id"] or ctx["customer_name"]
    if not cust or not oid:
        return
    g = df.dropna(subset=[cust, oid]).groupby(cust)[oid].nunique()
    if len(g) < 10:
        return
    repeat = (g >= 2).mean() * 100
    if repeat < 30:
        out.append(_ins(
            "risk" if repeat < 20 else "info", "Most customers buy only once",
            f"{repeat:.0f}% of {len(g)} customers ordered more than once.",
            "A follow-up message or small offer after the first order can bring them back. Repeat buyers cost less to win.",
        ))
    else:
        out.append(_ins(
            "opportunity", "You have a repeat customer base",
            f"{repeat:.0f}% of {len(g)} customers ordered more than once.",
            "Reward them and ask for referrals. This is your cheapest source of growth.",
        ))


def _ins_weekday(df, ctx, out):
    m, agg = ctx["measure"], ctx["agg"]
    if not m or not ctx["dates"]:
        return
    _, parsed = next(iter(ctx["dates"].items()))
    f = pd.DataFrame({"d": parsed, "v": _clean_numeric(df[m])}).dropna()
    if len(f) < 20 or (f["d"].max() - f["d"].min()).days < 28:
        return
    daily = f.groupby(f["d"].dt.normalize())["v"].agg("sum" if agg == "sum" else "mean")
    by_day = daily.groupby(daily.index.day_name()).mean()
    if len(by_day) < 4 or by_day.mean() <= 0:
        return
    best, worst = by_day.idxmax(), by_day.idxmin()
    lift = (by_day.max() / by_day.mean() - 1) * 100
    if lift >= 15:
        out.append(_ins(
            "opportunity", "Your busiest day",
            f"{best} is {lift:.0f}% above an average day for {m}. {worst} is the slowest.",
            f"Plan stock, staff and promotions around {best}. Try a small offer on {worst}.",
        ))


def _ins_discount(df, ctx, out):
    disc = ctx["roles"]["discount"]
    if not disc:
        return
    d = _clean_numeric(df[disc])
    if d.notna().sum() < 20:
        return
    scale = 100 if d.max() <= 1 else 1
    d = d * scale
    given = (d > 0)
    share = given[d.notna()].mean() * 100
    if share == 0:
        return
    avg = d[d > 0].mean()
    msg = f"{share:.0f}% of records carry a discount (average {avg:.0f}%)."

    ret = ctx["roles"]["returned"]
    if ret:
        flag = _to_binary_flag(df[ret])
        a, b = flag[given & d.notna()].dropna(), flag[~given & d.notna()].dropna()
        if len(a) >= MIN_GROUP_RECORDS and len(b) >= MIN_GROUP_RECORDS:
            msg += f" Return rate: {a.mean() * 100:.1f}% with a discount vs {b.mean() * 100:.1f}% without."
    out.append(_ins(
        "info", "How discounts are used", msg,
        "Compare a discount period with a normal one. Make sure discounts bring extra sales and not just a lower price on sales you would have made anyway.",
    ))


def _ins_relationship(df, ctx, out):
    cols = [
        c for c in ctx["metrics"]
        if _clean_numeric(df[c]).nunique() > 5
    ][:8]
    if len(cols) < 2:
        return
    corr = df[cols].apply(_clean_numeric).corr()
    best = None
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            v = corr.loc[a, b]
            if pd.notna(v) and (best is None or abs(v) > abs(best[2])):
                best = (a, b, v)
    if not best or abs(best[2]) < 0.5:
        return
    a, b, v = best
    direction = "rise together" if v > 0 else "move in opposite directions"
    note = " This may simply be because one is calculated from the other." if abs(v) > 0.9 else ""
    out.append(_ins(
        "info", "Two columns move together",
        f"{a} and {b} {direction} (correlation {v:+.2f}).{note}",
        "A link does not prove one causes the other. Use it as a lead to test.",
    ))


def _ins_generic(df, ctx, out):
    """For datasets with no sales-like measure (surveys, HR, logs, ...)."""
    for dim in ctx["dims"][:2]:
        vc = _normalize_category(df[dim]).value_counts(normalize=True)
        vc = vc[vc.index != "(Missing)"]
        if len(vc) >= 2 and vc.iloc[0] >= 0.4:
            out.append(_ins(
                "info", f"One {dim} dominates",
                f"{vc.index[0]} makes up {vc.iloc[0] * 100:.0f}% of records in {dim}.",
                "Make sure this matches what you expect, and that smaller groups are not being overlooked.",
            ))
    for col in ctx["metrics"][:2]:
        v = _clean_numeric(df[col]).dropna()
        if len(v) < 20:
            continue
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        limit = q3 + 1.5 * (q3 - q1)
        n = int((v > limit).sum())
        if n and q3 > q1 and n / len(v) >= 0.01:
            out.append(_ins(
                "info", f"Unusually high {col}",
                f"{n} record{'s' if n != 1 else ''} {'have' if n != 1 else 'has'} a {col} far above normal (over {_fmt(limit)}).",
                "Check whether these are data errors or genuine big cases worth a closer look.",
            ))


def _ins_data_notes(df, ctx, out):
    m = ctx["measure"]
    if m:
        miss = df[m].isna().mean() * 100
        if miss >= 5:
            out.append(_ins(
                "info", "Missing values may affect results",
                f"{miss:.0f}% of {m} values are empty, so totals may be lower than reality.",
                "Fill or fix these in the Data Cleaning step for more accurate charts.",
            ))
    if len(df) < 50:
        out.append(_ins(
            "info", "Small dataset",
            f"This file has only {len(df)} rows, so patterns can change quickly with new data.",
            "Use these insights as early hints and re-check once you have more records.",
        ))


def _business_insights(df, ctx, limit=8):
    out = []
    steps = [
        _ins_trend, _ins_concentration, _ins_pareto, _ins_returns,
        _ins_orders, _ins_repeat, _ins_weekday, _ins_discount,
        _ins_relationship,
    ]
    if not ctx["measure"]:
        steps = [_ins_generic, _ins_relationship]
    for step in steps:
        try:
            step(df, ctx, out)
        except Exception:
            continue                      # one failing rule never breaks the dashboard
    if len(out) < 4 and ctx["measure"]:
        try:
            _ins_generic(df, ctx, out)
        except Exception:
            pass
    try:
        _ins_data_notes(df, ctx, out)
    except Exception:
        pass

    order = {"risk": 0, "opportunity": 1, "info": 2}
    notes = [i for i in out if i["title"] in {"Small dataset", "Missing values may affect results"}]
    main = [i for i in out if i not in notes]
    main.sort(key=lambda i: order.get(i["type"], 3))
    return (main + notes)[:limit]


# --------------------------------------------------------------------------
# main entry
# --------------------------------------------------------------------------

def build_dashboard_data(df):
    base = build_visualization_data(df)           # summary, kpis, columns
    if df.empty or len(df.columns) == 0:
        base["insights"] = []
        return base

    detected = _detect_types(df)
    roles = _role_columns(df)
    columns = list(df.columns)

    dates = detected["dates"]
    identifiers = set(detected["identifiers"])
    categorical = detected["categorical"]

    def uniq(c):
        return df[c].nunique(dropna=True)

    # ---- column roles -----------------------------------------------------
    metrics = [
        c for c in detected["numeric"]
        if c not in detected["year_columns"]
        and not _is_identifier(c, df[c])
    ]
    skip_as_measure = {roles["discount"], roles["returned"], roles["quantity"]}

    measure = (
        roles["revenue"]
        or roles["profit"]
        or next((c for c in metrics if c not in skip_as_measure), None)
    )
    agg = "sum" if measure and (
        measure in (roles["revenue"], roles["profit"])
    ) else "mean"

    secondary = roles["quantity"] if roles["quantity"] != measure else None
    if secondary is None:
        secondary = next(
            (c for c in metrics
             if c not in skip_as_measure and c != measure), None
        )
    sec_agg = "sum" if secondary == roles["quantity"] else "mean"

    customer_name = next(
        (c for c in columns
         if _name(c) in {"customer", "customer_name", "client", "client_name"}),
        None,
    )

    cat_cols = [
        c for c in categorical
        if c not in identifiers and c != customer_name
    ]
    dims = [c for c in cat_cols if 2 <= uniq(c) <= MAX_DIM]
    preferred = [
        roles[k] for k in ("category", "channel", "segment")
        if roles[k] in dims
    ]
    dims = preferred + sorted(
        [c for c in dims if c not in preferred], key=uniq
    )

    entities = []
    for c in [roles["product"], customer_name] + cat_cols:
        if c and c in df.columns and c not in entities and c not in identifiers:
            filled = max(int(df[c].notna().sum()), 1)
            if uniq(c) > MAX_DIM and uniq(c) / filled < 0.9:
                entities.append(c)

    # ---- chart plan -------------------------------------------------------
    charts, seen = [], set()

    def add(chart, size=None, ctype=None):
        if not chart or chart["id"] in seen:
            return
        if size:
            chart["size"] = size
        if ctype:
            chart["chart_type"] = ctype
        seen.add(chart["id"])
        charts.append(chart)

    measure_label = f"{_agg_word(agg)} {measure}".strip() if measure else "Records"

    # 1. time
    for date_col, parsed in list(dates.items())[:1]:
        if measure:
            add(_trend(df, date_col, parsed, measure, agg, "line", "large"))
            if dims:
                add(_multi_trend(df, date_col, parsed, measure, dims[0], agg))
            add(_weekday(df, date_col, parsed, measure, agg))
        if secondary:
            add(_trend(df, date_col, parsed, secondary, sec_agg, "area", "medium"))

    # 2. composition by the best category columns
    kinds = [("donut", "small"), ("bar", "medium"),
             ("treemap", "large"), ("donut", "small")]
    for i, dim in enumerate(dims[:4]):
        ctype, size = kinds[i]
        if ctype == "treemap" and uniq(dim) < 4:
            ctype, size = "donut", "small"
        title = f"{measure_label} by {dim}" if measure else f"Records by {dim}"
        add(_dim_chart(df, dim, measure, agg, ctype, size, title,
                       top_n=7 if ctype == "donut" else 10))

    # 3. rankings of entities (products, customers, ...)
    for ent in entities[:3]:
        if measure:
            add(_dim_chart(df, ent, measure, agg, "horizontal_bar", "medium",
                           f"Top {ent} by {measure_label.lower()}", top_n=8))
        if secondary and ent == roles["product"]:
            add(_dim_chart(df, ent, secondary, sec_agg, "horizontal_bar",
                           "medium", f"Top {ent} by {secondary}", top_n=8))
    if customer_name and roles["order_id"]:
        add(_customer_orders_chart(df, customer_name, roles["order_id"]),
            "medium", "horizontal_bar")

    # 4. two categories together
    if len(dims) >= 2:
        add(_heat_pivot(df, dims[0], dims[1], measure, agg))

    # 5. how one column affects another
    if roles["returned"]:
        for dim in dims[:2]:
            add(_return_rate_chart(df, dim, roles["returned"]), "medium")

    drivers = [
        c for c in metrics
        if c not in {measure, roles["returned"]} and uniq(c) > 2
    ]
    for driver in drivers[:2]:
        if measure:
            add(_bucket_chart(
                df, driver, measure, "mean",
                title=f"Average {measure} by {driver} range",
            ))
        if roles["returned"]:
            add(_bucket_chart(
                df, driver, roles["returned"], "mean", percent=True,
                title=f"Return rate by {driver} range",
            ))

    # 6. distributions and numeric relationships
    if roles["order_id"] and roles["revenue"]:
        add(_order_hist(df, roles["order_id"], roles["revenue"]))

    scatter_cols = [c for c in metrics if uniq(c) > 5 and c != roles["returned"]]
    if measure in scatter_cols:
        scatter_cols.remove(measure)
        scatter_cols.insert(0, measure)
    pairs = [(a, b) for i, a in enumerate(scatter_cols)
             for b in scatter_cols[i + 1:]][:2]
    for a, b in pairs:
        add(_scatter_chart(df, a, b), "medium")

    add(_corr_heatmap(df, metrics))

    if not measure:
        for dim in dims[:3]:
            add(_dim_chart(df, dim, None, "count", "donut", "small",
                           f"Records by {dim}", top_n=7))
    for col in metrics[:2]:
        add(_histogram_chart(df, col), "small")

    charts = _select_diverse(charts, MAX_CHARTS)

    for chart in charts:
        chart["insight"] = _describe_chart(chart)

    base["charts"] = charts
    ctx = {
        "measure": measure, "agg": agg, "dims": dims, "entities": entities,
        "dates": dates, "roles": roles, "customer_name": customer_name,
        "metrics": metrics,
    }
    base["insights"] = _business_insights(df, ctx) or _build_insights(charts)
    return base
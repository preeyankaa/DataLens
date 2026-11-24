"""
app/data_analysis.py

Everything the AI analyst needs, built to stay fast on small and large CSVs:

  * build_dataset_card(df)   one compact, vectorised summary of the dataset.
                             main.py caches it, so it is computed only once.
  * run_query(df, spec)      safe group / filter / aggregate tool.
  * explain_change(df, spec) compares two periods and shows which groups
                             drove the change.

The AI never calculates numbers itself. It asks these tools, pandas does the
maths, and the AI only explains the result. Nothing here runs AI-written code.
"""

import json
import re
import warnings

import numpy as np
import pandas as pd

MAX_DETAIL_COLUMNS = 60
MAX_RESULT_ROWS = 30

_AGGS = {"sum", "mean", "median", "min", "max", "count", "nunique"}
_NUMERIC_AGGS = {"sum", "mean", "median", "min", "max"}
_TIME_GRAINS = {"day", "week", "month", "quarter", "year"}
_ALL_GRAINS = _TIME_GRAINS | {"weekday"}
_OPS = {
    "==", "!=", ">", ">=", "<", "<=",
    "contains", "in", "is_null", "not_null",
}
_ID_TOKENS = {"id", "uuid", "guid", "key", "index", "idx"}
_DATE_RE = re.compile(r"^\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")


class QueryError(ValueError):
    """Raised for a bad query. The message is shown to the AI so it can retry."""


# --------------------------------------------------
# small helpers
# --------------------------------------------------

def _clean(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return round(float(value), 2)
    return str(value)


def _round(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(number) else round(number, 2)


def _name_tokens(name):
    text = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    return set(text.split("_"))


def _as_datetime(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(series, errors="coerce", format="mixed")


def _looks_like_id(name, series):
    if _name_tokens(name) & _ID_TOKENS:
        return True

    valid = series.dropna()
    if len(valid) < 20:
        return False
    if valid.nunique() / len(valid) < 0.95:
        return False

    if pd.api.types.is_numeric_dtype(series):
        return bool((valid % 1 == 0).all())

    return True


def _sample_is_date(series):
    values = series.dropna().astype(str).head(50)
    if values.empty:
        return False
    hits = values.map(lambda v: bool(_DATE_RE.match(v))).mean()
    return hits >= 0.8


def _column_kind(name, series):
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        return "id" if _looks_like_id(name, series) else "numeric"

    lowered = str(name).lower()
    if any(w in lowered for w in ("date", "time", "timestamp")) \
            or _sample_is_date(series):
        return "date"
    if _looks_like_id(name, series):
        return "id"

    valid = series.dropna()
    if len(valid) >= 20 and valid.nunique() / len(valid) > 0.9:
        return "text"
    return "categorical"


def column_kind(name, series):
    """Public helper: numeric, categorical, date, id, text or boolean."""
    return _column_kind(name, series)


# --------------------------------------------------
# dataset card (cached by main.py)
# --------------------------------------------------

def _add_detail(info, series, kind):
    if kind == "numeric":
        values = pd.to_numeric(series, errors="coerce").dropna()
        if len(values):
            info.update(
                min=_round(values.min()),
                max=_round(values.max()),
                mean=_round(values.mean()),
                median=_round(values.median()),
                sum=_round(values.sum()),
            )
    elif kind in {"categorical", "boolean"}:
        counts = series.value_counts(dropna=True).head(5)
        info["top_values"] = {str(k): int(v) for k, v in counts.items()}
    elif kind == "date":
        parsed = _as_datetime(series).dropna()
        if len(parsed):
            info["from"] = str(parsed.min().date())
            info["to"] = str(parsed.max().date())
            info["days"] = int((parsed.max() - parsed.min()).days) + 1
    else:
        info["examples"] = (
            series.dropna().astype(str).head(2).str.slice(0, 30).tolist()
        )


def build_dataset_card(df, max_columns=MAX_DETAIL_COLUMNS):
    rows = int(len(df))
    duplicate_mask = df.duplicated().to_numpy()

    columns = {}
    kinds = {}

    for position, column in enumerate(df.columns):
        series = df[column]
        kind = _column_kind(column, series)
        kinds[str(column)] = kind
        missing = series.isna()

        info = {
            "kind": kind,
            "dtype": str(series.dtype),
            "missing": int(missing.sum()),
            "missing_pct": round(float(missing.mean() * 100), 2) if rows else 0.0,
            "unique": int(series.nunique(dropna=True)),
        }

        if info["missing"]:
            info["first_missing_rows"] = (
                np.flatnonzero(missing.to_numpy())[:10] + 1
            ).tolist()

        if position < max_columns:
            _add_detail(info, series, kind)

        columns[str(column)] = info

    numeric_cols = [c for c, k in kinds.items() if k == "numeric"][:8]
    correlations = []

    if len(numeric_cols) >= 2:
        frame = df[numeric_cols]
        if rows > 200_000:
            frame = frame.sample(200_000, random_state=1)
        corr = frame.apply(pd.to_numeric, errors="coerce").corr()

        for i, a in enumerate(numeric_cols):
            for b in numeric_cols[i + 1:]:
                value = corr.loc[a, b]
                if pd.notna(value) and abs(value) >= 0.3:
                    correlations.append(
                        {"a": a, "b": b, "r": round(float(value), 2)}
                    )

        correlations.sort(key=lambda item: -abs(item["r"]))

    sample = (
        df.head(3).astype(str)
        .apply(lambda col: col.str.slice(0, 40))
        .to_dict("records")
    )

    return {
        "overview": {
            "rows": rows,
            "columns": int(len(df.columns)),
            "missing_cells": int(df.isna().sum().sum()),
            "duplicate_rows": int(duplicate_mask.sum()),
            "first_duplicate_rows": (
                np.flatnonzero(duplicate_mask)[:10] + 1
            ).tolist(),
        },
        "notes": [
            "Row numbers count data rows from 1 (the header is not counted).",
            "kind: numeric, categorical, date, id (never aggregate), text.",
            "Exact totals, averages and rankings must come from the tools.",
        ],
        "column_kinds": {
            kind: [c for c, k in kinds.items() if k == kind]
            for kind in ("numeric", "categorical", "date", "id", "text", "boolean")
            if any(k == kind for k in kinds.values())
        },
        "columns": columns,
        "strongest_correlations": correlations[:6],
        "sample_rows": sample,
    }


def build_dataset_context(df):
    """JSON string used as the AI context."""
    return json.dumps(
        build_dataset_card(df), default=str, separators=(",", ":")
    )


# --------------------------------------------------
# query tools
# --------------------------------------------------

def _col(df, name):
    if name in df.columns:
        return name

    lowered = {str(c).lower(): c for c in df.columns}
    if str(name).lower() in lowered:
        return lowered[str(name).lower()]

    available = ", ".join(str(c) for c in list(df.columns)[:40])
    raise QueryError(
        f"Column '{name}' does not exist. Available columns: {available}"
    )


def _period_labels(dt, grain):
    if grain == "day":
        return dt.dt.strftime("%Y-%m-%d")
    if grain == "week":
        return dt.dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d")
    if grain == "month":
        return dt.dt.to_period("M").astype("string")
    if grain == "quarter":
        return dt.dt.to_period("Q").astype("string")
    if grain == "year":
        return dt.dt.year.astype("Int64").astype("string")
    return dt.dt.day_name()


def _apply_filters(df, filters):
    if not filters:
        return df
    if not isinstance(filters, list):
        raise QueryError("filters must be a list.")

    mask = pd.Series(True, index=df.index)

    for item in filters[:8]:
        if not isinstance(item, dict):
            raise QueryError("Each filter must be an object.")

        column = _col(df, item.get("column"))
        op = str(item.get("op") or "==")
        value = item.get("value")
        series = df[column]

        if op not in _OPS:
            raise QueryError(f"Unsupported filter operator '{op}'.")

        is_date = _column_kind(column, series) == "date"

        if op == "is_null":
            match = series.isna()
        elif op == "not_null":
            match = series.notna()
        elif op == "contains":
            match = series.astype("string").str.contains(
                str(value), case=False, na=False, regex=False
            )
        elif op == "in":
            values = value if isinstance(value, list) else [value]
            wanted = {str(v).lower() for v in values}
            match = series.astype("string").str.lower().isin(wanted)
        elif op in {"==", "!="}:
            if is_date:
                target = pd.to_datetime(value, errors="coerce")
                if pd.isna(target):
                    raise QueryError(f"'{value}' is not a valid date.")
                match = _as_datetime(series).dt.normalize() == target.normalize()
            elif pd.api.types.is_numeric_dtype(series):
                try:
                    match = pd.to_numeric(series, errors="coerce") == float(value)
                except (TypeError, ValueError):
                    raise QueryError(f"'{value}' is not a number.")
            else:
                match = (
                    series.astype("string").str.strip().str.lower()
                    == str(value).strip().lower()
                )
            if op == "!=":
                match = ~match
        else:
            if is_date:
                left = _as_datetime(series)
                right = pd.to_datetime(value, errors="coerce")
                if pd.isna(right):
                    raise QueryError(f"'{value}' is not a valid date.")
            else:
                left = pd.to_numeric(series, errors="coerce")
                try:
                    right = float(value)
                except (TypeError, ValueError):
                    raise QueryError(f"'{value}' is not a number.")

            match = {
                ">": left > right,
                ">=": left >= right,
                "<": left < right,
                "<=": left <= right,
            }[op]

        mask &= match.fillna(False)

    return df[mask]


def _group_key(work, item):
    if isinstance(item, str):
        item = {"column": item}
    if not isinstance(item, dict):
        raise QueryError("group_by items must be a column name or {column, grain}.")

    column = _col(work, item.get("column"))
    grain = item.get("grain")

    if grain:
        grain = str(grain).lower()
        if grain not in _ALL_GRAINS:
            raise QueryError(f"grain must be one of {sorted(_ALL_GRAINS)}.")
        return (
            f"{column} ({grain})",
            _period_labels(_as_datetime(work[column]), grain),
            grain,
        )

    series = work[column]
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        key = series
    else:
        key = series.astype("string").str.strip().fillna("(Missing)")

    return str(column), key, None


def run_query(df, spec):
    """Filter, group and aggregate. Returns at most MAX_RESULT_ROWS rows."""
    if not isinstance(spec, dict):
        raise QueryError("The query must be an object.")

    work = _apply_filters(df, spec.get("filters"))
    matched = int(len(work))

    metric = spec.get("metric")
    metric = _col(df, metric) if metric else None

    agg = str(spec.get("agg") or ("sum" if metric else "count")).lower()
    if agg not in _AGGS:
        raise QueryError(f"agg must be one of {sorted(_AGGS)}.")

    if matched == 0:
        return {
            "rows": [], "matched_rows": 0, "total_rows": int(len(df)),
            "note": "No rows match the filters.",
        }

    numeric_needed = agg in _NUMERIC_AGGS
    if numeric_needed and not metric:
        raise QueryError(f"'{agg}' needs a metric column.")

    values = None
    if metric:
        values = (
            pd.to_numeric(work[metric], errors="coerce")
            if numeric_needed else work[metric]
        )
        if numeric_needed and values.notna().sum() == 0:
            raise QueryError(
                f"Column '{metric}' is not numeric, so '{agg}' cannot be "
                "calculated. Use count or nunique instead."
            )

    group_items = spec.get("group_by") or []
    if isinstance(group_items, (str, dict)):
        group_items = [group_items]
    group_items = list(group_items)[:2]

    try:
        top_n = max(1, min(int(spec.get("top_n") or 10), MAX_RESULT_ROWS))
    except (TypeError, ValueError):
        top_n = 10

    base = {
        "matched_rows": matched,
        "total_rows": int(len(df)),
        "metric": metric,
        "agg": agg,
    }

    if not group_items:
        if metric is None:
            value = matched
        elif agg == "count":
            value = int(values.notna().sum())
        elif agg == "nunique":
            value = int(values.nunique(dropna=True))
        else:
            value = float(getattr(values, agg)())
        return {"rows": [{"value": _clean(value)}], **base}

    labels, frame, time_grain = [], pd.DataFrame(index=work.index), False

    for i, item in enumerate(group_items):
        label, key, grain = _group_key(work, item)
        if label in {"value", "share_pct"}:
            label = f"{label} (group)"
        frame[f"g{i}"] = key
        labels.append(label)
        if grain and grain != "weekday":
            time_grain = True

    group_cols = [f"g{i}" for i in range(len(labels))]
    if values is not None:
        frame["__v"] = values

    grouped = frame.groupby(group_cols, dropna=True)

    if metric is None:
        result = grouped.size()
    elif agg == "count":
        result = grouped["__v"].count()
    elif agg == "nunique":
        result = grouped["__v"].nunique()
    else:
        result = grouped["__v"].agg(agg)

    result = result.rename("value").reset_index()

    if result.empty:
        return {"rows": [], "note": "No groups to show.", **base}

    additive = metric is None or agg in {"sum", "count"}
    total = float(result["value"].sum()) if additive else None
    group_count = int(len(result))

    if time_grain:
        result = result.sort_values(group_cols).tail(top_n)
    else:
        ascending = str(spec.get("sort") or "desc").lower() == "asc"
        result = result.sort_values("value", ascending=ascending).head(top_n)

    rows = []
    for _, record in result.iterrows():
        row = {labels[i]: _clean(record[g]) for i, g in enumerate(group_cols)}
        row["value"] = _clean(record["value"])
        if additive and total and len(group_cols) == 1:
            row["share_pct"] = round(float(record["value"]) / total * 100, 1)
        rows.append(row)

    output = {"rows": rows, "groups_total": group_count, **base}
    if group_count > len(rows):
        output["note"] = (
            f"Showing {len(rows)} of {group_count} groups."
        )
    return output


def explain_change(df, spec):
    """Compare two periods and show which groups drove the change."""
    if not isinstance(spec, dict):
        raise QueryError("The request must be an object.")

    metric = _col(df, spec.get("metric"))
    date_col = _col(df, spec.get("date_column"))

    agg = str(spec.get("agg") or "sum").lower()
    if agg not in {"sum", "mean"}:
        raise QueryError("agg must be 'sum' or 'mean'.")

    grain = str(spec.get("grain") or "month").lower()
    if grain not in _TIME_GRAINS:
        raise QueryError(f"grain must be one of {sorted(_TIME_GRAINS)}.")

    work = _apply_filters(df, spec.get("filters"))
    values = pd.to_numeric(work[metric], errors="coerce")
    if values.notna().sum() == 0:
        raise QueryError(f"Column '{metric}' is not numeric.")

    dt = _as_datetime(work[date_col])
    frame = pd.DataFrame({
        "dt": dt, "v": values, "p": _period_labels(dt, grain),
    }).dropna(subset=["dt", "v"])

    periods = sorted(frame["p"].dropna().unique().tolist())
    if len(periods) < 2:
        raise QueryError(
            f"Need at least two {grain} periods, found {len(periods)}."
        )

    current = str(spec.get("current_period") or periods[-1])
    if current not in periods:
        raise QueryError(
            f"Period '{current}' not found. Available: {periods[-12:]}"
        )

    if spec.get("previous_period"):
        previous = str(spec["previous_period"])
    else:
        position = periods.index(current)
        if position == 0:
            raise QueryError(f"There is no period before {current}.")
        previous = periods[position - 1]

    if previous not in periods:
        raise QueryError(
            f"Period '{previous}' not found. Available: {periods[-12:]}"
        )
    if previous == current:
        raise QueryError("The two periods must be different.")

    f_cur = frame[frame["p"] == current]
    f_prev = frame[frame["p"] == previous]

    def total(part):
        return float(part["v"].sum() if agg == "sum" else part["v"].mean())

    t_cur, t_prev = total(f_cur), total(f_prev)
    change = t_cur - t_prev
    pct = (change / t_prev * 100) if t_prev else None

    days_cur = int(f_cur["dt"].dt.normalize().nunique())
    days_prev = int(f_prev["dt"].dt.normalize().nunique())

    notes = [
        "The breakdown shows where the change happened, not why it happened."
    ]
    if agg == "sum" and days_cur < days_prev * 0.8:
        notes.append(
            f"{current} has data for {days_cur} days vs {days_prev} days in "
            f"{previous}, so part of a drop may only be missing days."
        )

    result = {
        "metric": metric,
        "agg": agg,
        "grain": grain,
        "previous_period": previous,
        "current_period": current,
        "previous_value": _round(t_prev),
        "current_value": _round(t_cur),
        "change": _round(change),
        "change_pct": _round(pct),
        "days_in_previous": days_prev,
        "days_in_current": days_cur,
        "breakdown": {},
        "notes": notes,
    }

    dimensions = spec.get("dimensions") or []
    if isinstance(dimensions, str):
        dimensions = [dimensions]

    for dimension in list(dimensions)[:3]:
        column = _col(df, dimension)
        key = (
            work.loc[frame.index, column]
            .astype("string").str.strip().fillna("(Missing)")
        )
        part = pd.DataFrame({"p": frame["p"], "k": key, "v": frame["v"]})
        part = part[part["p"].isin([current, previous])]

        pivot = part.pivot_table(
            index="k", columns="p", values="v",
            aggfunc="sum" if agg == "sum" else "mean",
        ).reindex(columns=[previous, current]).fillna(0)

        pivot["delta"] = pivot[current] - pivot[previous]
        order = pivot["delta"].abs().sort_values(ascending=False).index
        top = pivot.loc[order].head(5)

        rows = []
        for name, record in top.iterrows():
            row = {
                "group": str(name),
                "previous": _clean(record[previous]),
                "current": _clean(record[current]),
                "change": _clean(record["delta"]),
            }
            if agg == "sum" and change:
                row["share_of_total_change_pct"] = round(
                    float(record["delta"]) / change * 100, 1
                )
            rows.append(row)

        result["breakdown"][str(column)] = rows

    return result
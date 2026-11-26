"""
Builds a dashboard payload shaped exactly like the one /dashboard returns,
from the sample file, with every chart type. Used by the PDF/Excel tests.
"""
import numpy as np
import pandas as pd

from app.cleaning import clean_dataframe


def _chart(chart_id, kind, title, data, size="medium", insight=None, agg="sum"):
    return {"id": chart_id, "chart_type": kind, "title": title, "subtitle": "", "x_label": "x", "y_label": "y",
            "data": data, "insight_hint": "", "size": size, "aggregation": agg, "insight": insight}


def cleaned_sample(sample_df):
    ops = {"remove_duplicates": True, "merge_case_columns": ["channel", "segment", "category"],
           "standardize_columns": ["customer"], "date_columns": ["order_date"],
           "missing_values": {"discount_pct": {"strategy": "constant", "value": 0}},
           "drop_rows": [{"column": "quantity", "op": "<", "value": 0}]}
    cleaned, changes = clean_dataframe(sample_df, ops)
    return cleaned, changes, ops


def dashboard_payload(sample_df):
    df = cleaned_sample(sample_df)[0].copy()
    df["d"] = pd.to_datetime(df["order_date"], errors="coerce")
    rows = lambda s: [{"category": str(k), "value": round(float(v), 2)} for k, v in s.items()]

    by_channel = df.groupby("channel")["line_total"].sum().sort_values(ascending=False)
    by_category = df.groupby("category")["line_total"].sum().sort_values(ascending=False)
    by_product = df.groupby("product")["line_total"].sum().sort_values(ascending=False).head(8)
    monthly = df.dropna(subset=["d"]).groupby(df["d"].dt.to_period("M").astype(str))["line_total"].sum()
    seg_month = (df.dropna(subset=["d"]).pivot_table(index=df["d"].dt.to_period("M").astype(str), columns="segment",
                 values="line_total", aggfunc="sum", fill_value=0).round(2))
    heat = df.pivot_table(index="channel", columns="category", values="line_total", aggfunc="sum", fill_value=0).round(2)
    corr = df[["quantity", "unit_price", "discount_pct", "line_total"]].corr().round(2)
    hist_counts, edges = np.histogram(df["line_total"].dropna(), bins=8)

    charts = [
        _chart("trend", "line", "Total line_total over time (monthly)", [{"period": k, "value": round(float(v), 2)} for k, v in monthly.items()],
               "large", "Peak was 2025-10. Latest period is +12% versus the first."),
        _chart("multi", "area", "line_total trend by segment",
               [dict(period=k, **{c: float(v) for c, v in r.items()}) for k, r in seg_month.iterrows()], "large",
               "Loyal contributes the most (38% of shown total)."),
        _chart("donut", "donut", "Total line_total by channel", rows(by_channel), "small", "Referral leads with 41% of the total shown; Direct is lowest."),
        _chart("bar", "bar", "Total line_total by category", rows(by_category), "medium", "Home is highest (1,234); Toys is lowest (456)."),
        _chart("tree", "treemap", "Total line_total by category (share)", rows(by_category), "large"),
        _chart("hbar", "horizontal_bar", "Top product by total line_total", rows(by_product), "medium"),
        _chart("heat", "heatmap", "line_total: channel × category",
               [dict(name=i, **{c: float(v) for c, v in r.items()}) for i, r in heat.iterrows()], "medium", "Highest combination: Referral × Home (410)."),
        _chart("corr", "heatmap", "How numeric columns relate",
               [dict(name=i, **{c: float(v) for c, v in r.items()}) for i, r in corr.iterrows()], "medium",
               "Strongest link: quantity and line_total (+0.82, strong).", "correlation"),
        _chart("hist", "histogram", "Order value distribution",
               [{"range": f"{edges[i]:.0f}–{edges[i + 1]:.0f}", "value": int(hist_counts[i])} for i in range(8)], "medium"),
        _chart("scatter", "scatter", "unit_price vs line_total",
               [{"x": float(a), "y": float(b)} for a, b in df[["unit_price", "line_total"]].dropna().head(120).values], "medium",
               "Correlation: 0.52. Association does not prove causation."),
        _chart("id", "bar", "Orders by customer_id", [{"category": "1", "value": 3}, {"category": "2", "value": 2}], "medium"),
    ]
    charts[-1]["x_label"] = "customer_id"   # must be left out of the report

    insights = [
        {"type": "risk", "title": "line_total depends on one channel",
         "message": "Referral brings 57% of total line_total. The next one, Email, brings 17%.",
         "recommendation": "If Referral has a bad month, your numbers drop sharply. Try to grow the other channel groups.",
         "evidence": {"columns": ["channel", "line_total"], "method": "Added up line_total for each channel. Share = that group's total divided by the total of all groups.",
                      "rows": 340, "confidence": "high",
                      "table": [{"label": "Referral", "value": "12.4K (57%)"}, {"label": "Email", "value": "3.7K (17%)"}]}},
        {"type": "opportunity", "title": "Order value", "message": "Average order value is 52.10 across 189 orders.",
         "recommendation": "Most orders have one item. Bundles can raise order value.",
         "evidence": {"columns": ["order_id", "line_total"], "method": "Added up line_total for each order_id, then averaged.", "rows": 340, "confidence": "high"}},
        {"type": "info", "title": "Small sample", "message": "Only 12 rows matched.", "recommendation": "Treat as an early hint.",
         "evidence": {"columns": [], "method": "Row count.", "rows": 12, "confidence": "low", "note": "Correlation shows two columns move together, not that one causes the other."}},
    ]

    return {
        "dataset_id": "x", "version": "cleaned", "using_cleaned": True,
        "summary": {"total_rows": int(len(df)), "total_columns": int(len(df.columns))},
        "kpis": [{"label": "Total records", "value": int(len(df))}, {"label": "Total revenue", "value": float(df["line_total"].sum())},
                 {"label": "Unique orders", "value": int(df["order_id"].nunique())}, {"label": "Unique customers", "value": int(df["customer_id"].nunique())},
                 {"label": "Missing values", "value": int(df.isna().sum().sum())}],
        "charts": charts, "insights": insights,
        "detected_roles": {"revenue": "line_total", "quantity": "quantity", "order_id": "order_id", "customer": "customer",
                           "product": "product", "returned": "returned", "discount": "discount_pct", "date": "order_date"},
        "ignored_id_columns": ["customer_id", "product_id"],
        "dashboard_ai": {"ai_generated": True, "summary": "Sales are concentrated in one channel. Order value is steady.",
                         "insights": []},
    }
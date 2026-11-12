
import re

import numpy as np
import pandas as pd


MAX_CATEGORIES = 12
MAX_SCATTER_POINTS = 120
MAX_AUTO_CHARTS = 12
MIN_GROUP_RECORDS = 10

ID_WORDS = {"id", "ids", "uuid", "key", "code", "index"}
DATE_WORDS = {"date", "time", "timestamp", "datetime"}

REVENUE_ALIASES = {
    "revenue", "sales", "total_sales", "net_sales",
    "line_total", "order_total", "total_amount",
    "amount", "turnover", "sales_amount",
}

QUANTITY_ALIASES = {
    "quantity", "qty", "units", "volume",
    "units_sold", "quantity_sold",
}

RETURN_ALIASES = {
    "return", "returned", "return_status",
    "is_returned", "refund", "refunded", "is_refunded",
}

DISCOUNT_ALIASES = {
    "discount", "discount_pct", "discount_percent",
}

PROFIT_ALIASES = {"profit", "margin", "earnings"}


def _name(column):
    return re.sub(
        r"[^a-z0-9]+", "_", str(column).lower()
    ).strip("_")


def _safe_number(value, digits=2):
    try:
        if pd.isna(value) or not np.isfinite(float(value)):
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _clean_numeric(series):
    return pd.to_numeric(
        series, errors="coerce"
    ).replace([np.inf, -np.inf], np.nan)


def _matches_alias(column, aliases):
    name = _name(column)

    return (
        name in aliases
        or any(name.startswith(alias + "_") for alias in aliases)
        or any(name.endswith("_" + alias) for alias in aliases)
    )


def _is_identifier(column, series):
    name = _name(column)
    tokens = set(name.split("_"))

    if tokens & ID_WORDS:
        return True

    if any(
        word in name
        for word in ("identifier", "reference", "uuid")
    ):
        return True

    values = series.dropna()

    if len(values) >= 20:
        if values.nunique() / len(values) >= 0.95:
            return True

    return False


def _infer_dayfirst(series):
    day_votes = 0
    month_votes = 0

    for value in series.dropna().astype(str).head(500):
        match = re.match(
            r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
            value,
        )

        if not match:
            continue

        first = int(match.group(1))
        second = int(match.group(2))

        if first > 12 and second <= 12:
            day_votes += 1
        elif second > 12 and first <= 12:
            month_votes += 1

    return day_votes > month_votes


def _parse_dates(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    text = series.astype("string").str.strip()
    dayfirst = _infer_dayfirst(text)

    parsed = pd.to_datetime(
        text,
        format="mixed",
        dayfirst=dayfirst,
        errors="coerce",
    )

    failed = text.notna() & parsed.isna()

    if failed.any():
        retry = pd.to_datetime(
            text[failed],
            format="mixed",
            dayfirst=not dayfirst,
            errors="coerce",
        )
        parsed.loc[failed] = retry

    return parsed


def _normalize_category(series):
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .fillna("(Missing)")
        .replace("", "(Missing)")
    )


def _to_binary_flag(series):
    numeric = _clean_numeric(series)

    if numeric.notna().sum() == series.notna().sum():
        return numeric.where(numeric.isin([0, 1]))

    text = series.astype("string").str.strip().str.lower()

    positive = {
        "yes", "y", "true", "1", "returned",
        "refunded", "return", "refund",
    }

    negative = {
        "no", "n", "false", "0", "not returned",
        "not_refunded", "not returned/refunded",
    }

    result = pd.Series(np.nan, index=series.index, dtype=float)

    result.loc[text.isin(positive)] = 1
    result.loc[text.isin(negative)] = 0

    return result


def _detect_types(df):
    numeric = []
    categorical = []
    dates = {}
    identifiers = []

    for column in df.columns:
        series = df[column]
        name = _name(column)

        if (
            any(word in name for word in DATE_WORDS)
            or name in {"month", "year", "yr"}
        ) and not pd.api.types.is_numeric_dtype(series):

            parsed = _parse_dates(series)

            if parsed.notna().sum() >= max(
                3, int(series.notna().sum() * 0.5)
            ):
                dates[column] = parsed
                continue

        if pd.api.types.is_datetime64_any_dtype(series):
            dates[column] = pd.to_datetime(
                series, errors="coerce"
            )

        elif pd.api.types.is_bool_dtype(series):
            categorical.append(column)

        elif pd.api.types.is_numeric_dtype(series):
            if _is_identifier(column, series):
                identifiers.append(column)
            else:
                numeric.append(column)

        else:
            parsed = _parse_dates(series)
            valid = parsed.notna().sum()
            non_null = series.notna().sum()

            if non_null and valid / non_null >= 0.8 and valid >= 3:
                dates[column] = parsed
            else:
                categorical.append(column)

                if _is_identifier(column, series):
                    identifiers.append(column)

    year_columns = []

    for column in numeric:
        name = _name(column)

        if name in {
            "year", "yr", "fiscal_year"
        } or name.endswith("_year"):
            year_columns.append(column)

    return {
        "numeric": numeric,
        "categorical": categorical,
        "dates": dates,
        "year_columns": year_columns,
        "identifiers": identifiers,
    }


def _make_chart(
    chart_id,
    chart_type,
    title,
    subtitle,
    x_label,
    y_label,
    data,
    insight_hint,
    size="medium",
    aggregation=None,
):
    return {
        "id": chart_id,
        "chart_type": chart_type,
        "title": title,
        "subtitle": subtitle,
        "x_label": x_label,
        "y_label": y_label,
        "data": data,
        "insight_hint": insight_hint,
        "size": size,
        "aggregation": aggregation,
    }


def _role_columns(df):
    columns = list(df.columns)

    def first_alias(aliases):
        return next(
            (
                col for col in columns
                if _matches_alias(col, aliases)
            ),
            None,
        )

    product_name = next(
        (
            col for col in columns
            if _name(col) in {
                "product", "product_name",
                "item", "item_name", "sku_name",
            }
        ),
        None,
    )

    product_id = first_alias({
        "product_id", "item_id", "sku_id",
    })

    product = product_name or product_id

    return {
        "revenue": first_alias(REVENUE_ALIASES),
        "quantity": first_alias(QUANTITY_ALIASES),
        "order_id": first_alias({
            "order_id", "order_number", "order_no",
        }),
        "customer_id": first_alias({
            "customer_id", "client_id", "user_id",
        }),
        "product": product,
        "product_id": product_id,
        "category": first_alias({
            "category", "department", "product_type",
        }),
        "channel": first_alias({
            "channel", "sales_channel", "platform",
        }),
        "segment": first_alias({
            "segment", "customer_segment",
        }),
        "returned": first_alias(RETURN_ALIASES),
        "discount": first_alias(DISCOUNT_ALIASES),
        "profit": first_alias(PROFIT_ALIASES),
    }


def _group_chart(
    df,
    category,
    metric,
    aggregation="sum",
    title=None,
    label=None,
    chart_id=None,
    top_n=MAX_CATEGORIES,
):
    values = df[[category, metric]].copy()

    values[metric] = _clean_numeric(values[metric])
    values[category] = _normalize_category(values[category])
    values = values.dropna(subset=[metric])

    if values.empty:
        return None

    grouped = (
        values.groupby(category)[metric]
        .agg(aggregation)
        .sort_values(ascending=False)
        .head(top_n)
    )

    data = [
        {
            "category": str(key),
            "value": _safe_number(value),
        }
        for key, value in grouped.items()
    ]

    if not data:
        return None

    aggregation_label = label or aggregation.capitalize()

    return _make_chart(
        chart_id or (
            f"{aggregation}_{_name(metric)}_by_{_name(category)}"
        ),
        "bar",
        title or f"{aggregation_label} {metric} by {category}",
        f"{aggregation_label} {metric} across leading {category} groups.",
        str(category),
        f"{aggregation_label} {metric}",
        data,
        f"Compare {aggregation_label.lower()} {metric} across {category} groups.",
        "large",
        aggregation=aggregation,
    )


def _distribution_chart(df, column):
    values = _normalize_category(df[column])
    counts = values.value_counts().head(MAX_CATEGORIES)

    if counts.empty:
        return None

    data = [
        {"category": str(key), "value": int(value)}
        for key, value in counts.items()
    ]

    return _make_chart(
        f"distribution_{_name(column)}",
        "donut",
        f"Records by {column}",
        f"Distribution of records across {column} groups.",
        str(column),
        "Records",
        data,
        f"Shows which {column} groups account for the most records.",
        "small",
        aggregation="count",
    )


def _trend_chart(df, date_column, parsed_dates, metric, aggregation="sum"):
    values = pd.DataFrame({
        "period": parsed_dates,
        "metric": _clean_numeric(df[metric]),
    }).dropna()

    if values.empty:
        return None

    values["period"] = (
        values["period"].dt.to_period("M").astype(str)
    )

    grouped = (
        values.groupby("period")["metric"]
        .agg(aggregation)
        .sort_index()
    )

    if len(grouped) < 2:
        return None

    data = [
        {"period": str(period), "value": _safe_number(value)}
        for period, value in grouped.items()
    ]

    return _make_chart(
        f"trend_{_name(metric)}_by_{_name(date_column)}",
        "line",
        f"Monthly {metric}",
        f"{aggregation.capitalize()} {metric} by month.",
        str(date_column),
        f"{aggregation.capitalize()} {metric}",
        data,
        f"Shows how {aggregation} {metric} changes over time.",
        "large",
        aggregation=aggregation,
    )


def _return_rate_chart(df, category, returned_column):
    values = df[[category, returned_column]].copy()

    values[returned_column] = _to_binary_flag(
        values[returned_column]
    )
    values[category] = _normalize_category(values[category])
    values = values.dropna(subset=[returned_column])

    if values.empty:
        return None

    grouped = values.groupby(category)[returned_column].agg(
        ["mean", "count"]
    )

    grouped = grouped[
        grouped["count"] >= MIN_GROUP_RECORDS
    ]

    if grouped.empty:
        return None

    grouped = (
        grouped.sort_values("mean", ascending=False)
        .head(MAX_CATEGORIES)
    )

    data = [
        {
            "category": str(key),
            "value": _safe_number(row["mean"] * 100),
            "records": int(row["count"]),
        }
        for key, row in grouped.iterrows()
    ]

    return _make_chart(
        f"return_rate_by_{_name(category)}",
        "bar",
        f"Return rate by {category}",
        f"Return percentage for groups with at least {MIN_GROUP_RECORDS} records.",
        str(category),
        "Return rate (%)",
        data,
        "A higher percentage indicates a group with more returned records.",
        "large",
        aggregation="mean_percent",
    )


def _customer_orders_chart(df, customer_id, order_id):
    values = df[[customer_id, order_id]].dropna()

    if values.empty:
        return None

    grouped = (
        values.groupby(customer_id)[order_id]
        .nunique()
        .sort_values(ascending=False)
        .head(MAX_CATEGORIES)
    )

    data = [
        {
            "category": str(customer),
            "value": int(count),
        }
        for customer, count in grouped.items()
    ]

    return _make_chart(
        "top_customers_by_orders",
        "bar",
        "Top customers by orders",
        "Customers with the highest number of unique orders.",
        str(customer_id),
        "Number of orders",
        data,
        "Each order is counted once per customer, even when an order has multiple product rows.",
        "large",
        aggregation="unique_orders_per_customer",
    )


def _top_products_chart(df, product_column, quantity_column):
    values = df[[product_column, quantity_column]].copy()

    values[quantity_column] = _clean_numeric(
        values[quantity_column]
    )
    values[product_column] = _normalize_category(
        values[product_column]
    )
    values = values.dropna(subset=[quantity_column])

    if values.empty:
        return None

    grouped = (
        values.groupby(product_column)[quantity_column]
        .sum()
        .sort_values(ascending=False)
        .head(MAX_CATEGORIES)
    )

    data = [
        {
            "category": str(product),
            "value": _safe_number(quantity),
        }
        for product, quantity in grouped.items()
    ]

    return _make_chart(
        "top_selling_products",
        "bar",
        "Top-selling products",
        "Products ranked by total quantity sold.",
        str(product_column),
        "Quantity sold",
        data,
        "Shows which products have the highest sales volume.",
        "large",
        aggregation="sum_quantity_by_product",
    )


def _top_products_by_orders_chart(
    df,
    product_column,
    order_id,
):
    values = df[[product_column, order_id]].dropna().copy()

    if values.empty:
        return None

    values[product_column] = _normalize_category(
        values[product_column]
    )

    grouped = (
        values.groupby(product_column)[order_id]
        .nunique()
        .sort_values(ascending=False)
        .head(MAX_CATEGORIES)
    )

    if grouped.empty:
        return None

    data = [
        {
            "category": str(product),
            "value": int(order_count),
        }
        for product, order_count in grouped.items()
    ]

    return _make_chart(
        "top_products_by_orders",
        "bar",
        "Products by number of orders",
        "Products ranked by the number of unique orders containing them.",
        str(product_column),
        "Number of orders",
        data,
        "This measures how frequently a product appears in orders, not the number of units sold.",
        "large",
        aggregation="unique_orders_per_product",
    )


def _scatter_chart(df, x_column, y_column):
    values = pd.DataFrame({
        "x": _clean_numeric(df[x_column]),
        "y": _clean_numeric(df[y_column]),
    }).dropna()

    if (
        len(values) < 5
        or values["x"].nunique() < 2
        or values["y"].nunique() < 2
    ):
        return None

    correlation = values["x"].corr(values["y"])

    sample = values.sample(
        min(len(values), MAX_SCATTER_POINTS),
        random_state=42,
    )

    data = [
        {
            "x": _safe_number(row.x),
            "y": _safe_number(row.y),
        }
        for row in sample.itertuples(index=False)
    ]

    return _make_chart(
        f"relationship_{_name(x_column)}_{_name(y_column)}",
        "scatter",
        f"{x_column} vs {y_column}",
        "Explore the relationship between these two measures.",
        str(x_column),
        str(y_column),
        data,
        f"Correlation: {_safe_number(correlation, 3)}. Association does not prove causation.",
        "medium",
        aggregation="correlation",
    )


def _histogram_chart(df, column):
    values = _clean_numeric(df[column]).dropna()

    if len(values) < 2 or values.nunique() < 2:
        return None

    counts, edges = np.histogram(values, bins=10)

    data = [
        {
            "range": f"{edges[i]:.2f} – {edges[i + 1]:.2f}",
            "value": int(counts[i]),
        }
        for i in range(len(counts))
    ]

    return _make_chart(
        f"distribution_numeric_{_name(column)}",
        "histogram",
        f"Distribution of {column}",
        "Shows how values are spread across the dataset.",
        str(column),
        "Records",
        data,
        f"Mean: {_safe_number(values.mean())}; median: {_safe_number(values.median())}.",
        "small",
        aggregation="count",
    )


def _correlation_chart(df, metrics):
    usable = [
        col for col in metrics
        if (
            _clean_numeric(df[col]).notna().sum() >= 5
            and _clean_numeric(df[col]).nunique() > 1
        )
    ]

    if len(usable) < 2:
        return None

    correlation = df[usable].apply(_clean_numeric).corr()

    data = [
        {
            "x": str(col),
            "y": str(row),
            "value": _safe_number(correlation.loc[row, col], 3),
        }
        for row in correlation.index
        for col in correlation.columns
        if pd.notna(correlation.loc[row, col])
    ]

    return _make_chart(
        "numeric_correlation",
        "heatmap",
        "Metric correlation",
        "Explore relationships between numeric measures.",
        "Metric",
        "Metric",
        data,
        "Values near 1 or -1 indicate stronger linear association; values near 0 indicate weaker association.",
        "large",
        aggregation="correlation",
    )


def _build_kpis(df, detected, roles):
    kpis = [
        {
            "label": "Total records",
            "value": int(len(df)),
            "format": "number",
        },
        {
            "label": "Columns",
            "value": int(len(df.columns)),
            "format": "number",
        },
        {
            "label": "Missing values",
            "value": int(df.isna().sum().sum()),
            "format": "number",
        },
        {
            "label": "Duplicate rows",
            "value": int(df.duplicated().sum()),
            "format": "number",
        },
    ]

    revenue = roles["revenue"]

    if revenue:
        revenue_values = _clean_numeric(df[revenue]).dropna()

        if not revenue_values.empty:
            kpis.append({
                "label": "Total revenue",
                "value": _safe_number(revenue_values.sum()),
                "format": "currency",
            })

    order_id = roles["order_id"]

    if order_id:
        kpis.append({
            "label": "Unique orders",
            "value": int(df[order_id].nunique(dropna=True)),
            "format": "number",
        })

    customer_id = roles["customer_id"]

    if customer_id:
        kpis.append({
            "label": "Unique customers",
            "value": int(df[customer_id].nunique(dropna=True)),
            "format": "number",
        })

    if len(kpis) == 4 and detected["numeric"]:
        metric = detected["numeric"][0]
        values = _clean_numeric(df[metric]).dropna()

        if not values.empty:
            kpis.append({
                "label": f"Average {metric}",
                "value": _safe_number(values.mean()),
                "format": "decimal",
            })

    return kpis[:7]


def build_visualization_data(df):
    if df.empty or len(df.columns) == 0:
        return {
            "status": "success",
            "summary": {
                "total_rows": int(len(df)),
                "total_columns": int(len(df.columns)),
                "numeric_columns": 0,
                "categorical_columns": 0,
                "date_columns": 0,
                "missing_values": int(df.isna().sum().sum()),
            },
            "columns": [],
            "kpis": [],
            "charts": [],
        }

    detected = _detect_types(df)
    roles = _role_columns(df)

    numeric = detected["numeric"]
    categorical = detected["categorical"]
    dates = detected["dates"]

    metrics = [
        col for col in numeric
        if (
            col not in detected["year_columns"]
            and not _is_identifier(col, df[col])
        )
    ]

    charts = []
    used_ids = set()

    def add(chart):
        if chart and chart["id"] not in used_ids:
            charts.append(chart)
            used_ids.add(chart["id"])

    revenue = roles["revenue"]
    quantity = roles["quantity"]
    returned = roles["returned"]
    order_id = roles["order_id"]
    customer_id = roles["customer_id"]
    product_column = roles["product"]

    # 1. Business trends.
    for date_column, parsed_dates in dates.items():
        for metric in [
            revenue, quantity, roles["profit"]
        ]:
            if metric and metric in df.columns:
                add(_trend_chart(
                    df, date_column, parsed_dates, metric, "sum"
                ))

    # 2. Revenue comparisons.
    business_groups = [
        roles["category"],
        roles["channel"],
        roles["segment"],
        product_column,
    ]

    if revenue:
        for category in business_groups:
            if category and category in df.columns:
                add(_group_chart(
                    df,
                    category,
                    revenue,
                    aggregation="sum",
                    title=f"Revenue by {category}",
                    label="Total",
                    chart_id=f"revenue_by_{_name(category)}",
                ))

    # 3. Customer analytics.
    if customer_id and order_id:
        add(_customer_orders_chart(
            df, customer_id, order_id
        ))

    # 4. Product analytics.
    if product_column and quantity:
        add(_top_products_chart(
            df, product_column, quantity
        ))

    # Number of unique orders containing each product.
    if product_column and order_id:
        add(_top_products_by_orders_chart(
            df, product_column, order_id
        ))

    # 5. Customer revenue contribution.
    if customer_id and revenue:
        add(_group_chart(
            df,
            customer_id,
            revenue,
            aggregation="sum",
            title="Revenue by customer",
            label="Total",
            chart_id="revenue_by_customer",
        ))

    # 6. Return-rate comparisons.
    if returned:
        for category in [
            roles["category"],
            product_column,
            roles["channel"],
        ]:
            if category and category in df.columns:
                add(_return_rate_chart(
                    df, category, returned
                ))

    # 7. Order value distribution.
    if order_id and revenue:
        order_totals = df[[order_id, revenue]].copy()

        order_totals[revenue] = _clean_numeric(
            order_totals[revenue]
        )

        order_totals = order_totals.dropna(
            subset=[order_id, revenue]
        )

        order_totals = (
            order_totals.groupby(order_id)[revenue].sum()
        )

        if len(order_totals) >= 2 and order_totals.nunique() > 1:
            counts, edges = np.histogram(
                order_totals, bins=10
            )

            data = [
                {
                    "range": f"{edges[i]:.2f} – {edges[i + 1]:.2f}",
                    "value": int(counts[i]),
                }
                for i in range(len(counts))
            ]

            add(_make_chart(
                "order_value_distribution",
                "histogram",
                "Order value distribution",
                "Distribution of total value after combining line items per order.",
                "Order value",
                "Number of orders",
                data,
                f"Average order value: {_safe_number(order_totals.mean())}.",
                "medium",
                aggregation="sum_by_order_then_distribution",
            ))

    # 8. Generic fallback.
    useful_categories = [
        col for col in categorical
        if 1 < df[col].nunique(dropna=True) <= 30
    ]

    generic_metrics = [
        col for col in metrics
        if col not in {
            revenue,
            quantity,
            returned,
            roles["discount"],
            roles["profit"],
        }
    ]

    if not charts:
        for category in useful_categories:
            for metric in generic_metrics[:3]:
                add(_group_chart(
                    df, category, metric, aggregation="mean"
                ))

    if not charts:
        for date_column, parsed_dates in dates.items():
            for metric in generic_metrics[:3]:
                add(_trend_chart(
                    df, date_column, parsed_dates, metric, "mean"
                ))

    # 9. Numeric relationships.
    relationship_metrics = [
        col for col in metrics
        if df[col].nunique(dropna=True) > 5
    ]

    relationship_count = 0

    for i, first in enumerate(relationship_metrics):
        for second in relationship_metrics[i + 1:]:
            add(_scatter_chart(df, first, second))
            relationship_count += 1

            if relationship_count >= 3:
                break

        if relationship_count >= 3:
            break

    # 10. Supporting charts.
    add(_correlation_chart(df, relationship_metrics))

    for column in useful_categories[:3]:
        add(_distribution_chart(df, column))

    for column in metrics[:3]:
        add(_histogram_chart(df, column))

    charts = charts[:MAX_AUTO_CHARTS]

    columns = []

    for column in df.columns:
        if column in dates:
            column_type = "date"
            chart_types = ["line", "bar"]

        elif column in numeric:
            column_type = (
                "identifier"
                if column in detected["identifiers"]
                else "numeric"
            )

            chart_types = (
                ["bar", "donut"]
                if column_type == "identifier"
                else ["bar", "line", "scatter", "histogram"]
            )

        else:
            column_type = (
                "identifier"
                if column in detected["identifiers"]
                else "categorical"
            )
            chart_types = ["bar", "donut"]

        columns.append({
            "name": str(column),
            "type": column_type,
            "chart_types": chart_types,
            "unique_values": int(
                df[column].nunique(dropna=True)
            ),
            "missing_values": int(df[column].isna().sum()),
        })

    return {
        "status": "success",
        "summary": {
            "total_rows": int(len(df)),
            "total_columns": int(len(df.columns)),
            "numeric_columns": len(numeric),
            "categorical_columns": len(categorical),
            "date_columns": len(dates),
            "missing_values": int(df.isna().sum().sum()),
        },
        "kpis": _build_kpis(df, detected, roles),
        "columns": columns,
        "charts": charts,
    }

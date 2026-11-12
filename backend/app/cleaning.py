
import re
import numpy as np
import pandas as pd


ID_TOKENS = {
    "id",
    "uuid",
    "identifier",
    "reference",
    "ref",
    "key",
}

COUNTRY_ALIASES = {
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "usa": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
}


# --------------------------------------------------
# COLUMN HELPERS
# --------------------------------------------------

def _normalise_name(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def _is_identifier(column, series):
    name = _normalise_name(column)
    tokens = set(name.split("_"))

    if (
        tokens & ID_TOKENS
        or name.endswith("_id")
        or name.endswith("_key")
        or name.endswith("_uuid")
        or "identifier" in name
        or "reference" in name
    ):
        return True

    # High-cardinality text columns may represent names or identifiers.
    if (
        series.dtype == "object"
        or pd.api.types.is_string_dtype(series)
    ):
        valid = series.dropna()

        if len(valid) >= 20:
            unique_ratio = valid.nunique() / len(valid)

            if unique_ratio >= 0.95:
                return True

    return False


def _is_date_column(column, series):
    name = _normalise_name(column)

    if any(word in name for word in ("date", "time", "timestamp")):
        return True

    return pd.api.types.is_datetime64_any_dtype(series)


def _infer_date_order(series):
    """
    Infer day-first preference using unambiguous slash dates.
    Ambiguous dates such as 04/05/2025 cannot be identified
    with certainty without knowing the source format.
    """
    samples = series.dropna().astype(str).head(200)

    day_first = 0
    month_first = 0

    for value in samples:
        match = re.match(
            r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})",
            value
        )

        if not match:
            continue

        first = int(match.group(1))
        second = int(match.group(2))

        if first > 12 and second <= 12:
            day_first += 1
        elif second > 12 and first <= 12:
            month_first += 1

    return day_first > month_first


def _parse_dates(series):
    day_first = _infer_date_order(series)

    return pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=day_first,
        format="mixed"
    )


# --------------------------------------------------
# MISSING VALUE STRATEGIES
# --------------------------------------------------

def _recommended_numeric_strategy(series):
    valid = series.dropna()

    if valid.empty:
        return "skip"

    if len(valid) < 3:
        return "median"

    skewness = valid.skew()

    q1 = valid.quantile(0.25)
    q3 = valid.quantile(0.75)
    iqr = q3 - q1

    has_outliers = False

    if iqr > 0:
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        has_outliers = ((valid < lower) | (valid > upper)).any()

    if abs(skewness) > 1 or has_outliers:
        return "median"

    return "mean"


def _recommended_categorical_fill(column):
    """
    Preserve missing business information instead of
    assigning another customer's/product's/category's value.
    """
    return "(Unknown)"


def _standardize_text(value):
    if pd.isna(value):
        return value

    value = re.sub(r"\s+", " ", str(value)).strip()

    if not value:
        return value

    alias_key = value.lower()

    return COUNTRY_ALIASES.get(alias_key, value)


def _get_strategy(config):
    if isinstance(config, dict):
        return config.get("strategy", "auto"), config.get("value")

    if isinstance(config, str):
        return config, None

    return "auto", None


def _fill_missing_values(df, column, config):
    series = df[column]
    missing_count = int(series.isna().sum())

    if missing_count == 0:
        return None

    if _is_identifier(column, series):
        return {
            "strategy": "skipped",
            "unfilled": missing_count,
            "reason": "Identifier columns are not imputed."
        }

    strategy, custom_value = _get_strategy(config)

    if strategy == "auto":
        if pd.api.types.is_numeric_dtype(series):
            strategy = _recommended_numeric_strategy(series)
        elif pd.api.types.is_datetime64_any_dtype(series):
            strategy = "skip"
        else:
            strategy = "unknown"

    # Never assume an unknown return status means "not returned".
    if _normalise_name(column) in {
        "returned",
        "is_returned",
        "return_status",
    } and strategy in {"auto", "unknown"}:
        strategy = "skip"

    if strategy == "skip":
        return {
            "strategy": "skipped",
            "unfilled": missing_count,
            "reason": "Missing values were preserved."
        }

    if strategy == "drop_rows":
        df.dropna(subset=[column], inplace=True)

        return {
            "strategy": "drop_rows",
            "rows_removed": missing_count
        }

    if strategy == "mean":
        if not pd.api.types.is_numeric_dtype(series):
            return {
                "strategy": "skipped",
                "unfilled": missing_count,
                "reason": "Mean requires a numeric column."
            }

        fill_value = series.mean()

    elif strategy == "median":
        if not pd.api.types.is_numeric_dtype(series):
            return {
                "strategy": "skipped",
                "unfilled": missing_count,
                "reason": "Median requires a numeric column."
            }

        fill_value = series.median()

    elif strategy == "mode":
        modes = series.mode(dropna=True)

        if modes.empty:
            return {
                "strategy": "skipped",
                "unfilled": missing_count,
                "reason": "No valid value available for mode."
            }

        fill_value = modes.iloc[0]

    elif strategy == "constant":
        fill_value = custom_value

        if fill_value is None:
            fill_value = "(Unknown)"

    elif strategy == "unknown":
        fill_value = _recommended_categorical_fill(column)

    else:
        return {
            "strategy": "skipped",
            "unfilled": missing_count,
            "reason": f"Unsupported strategy: {strategy}"
        }

    df[column] = series.fillna(fill_value)

    return {
        "strategy": strategy,
        "filled": missing_count,
        "fill_value": fill_value
    }


# --------------------------------------------------
# MAIN CLEANING FUNCTION
# --------------------------------------------------

def clean_dataframe(df, operations):
    cleaned_df = df.copy()
    changes = {}

    operations = operations or {}

    # 1. REMOVE DUPLICATES
    if operations.get("remove_duplicates", False):
        before = len(cleaned_df)

        cleaned_df.drop_duplicates(inplace=True)

        changes["duplicates_removed"] = before - len(cleaned_df)

    # 2. MISSING VALUES
    missing_config = operations.get("missing_values", {})

    if isinstance(missing_config, dict):
        for column, config in missing_config.items():
            if column not in cleaned_df.columns:
                continue

            result = _fill_missing_values(
                cleaned_df,
                column,
                config
            )

            if result is not None:
                changes[f"missing_{column}"] = result

    # 3. DATE STANDARDIZATION
    date_columns = operations.get("date_columns", [])

    for column in date_columns:
        if column not in cleaned_df.columns:
            continue

        parsed = _parse_dates(cleaned_df[column])

        cleaned_df[column] = parsed.dt.strftime("%Y-%m-%d")

        changes[f"date_{column}"] = {
            "converted": int(parsed.notna().sum()),
            "invalid_or_missing": int(parsed.isna().sum()),
            "format": "YYYY-MM-DD"
        }

    # 4. TEXT STANDARDIZATION
    standardize_columns = operations.get("standardize_columns", [])

    for column in standardize_columns:
        if column not in cleaned_df.columns:
            continue

        before = cleaned_df[column].copy()

        cleaned_df[column] = cleaned_df[column].apply(
            _standardize_text
        )

        normalized_count = int(
            (before.fillna("").astype(str) !=
             cleaned_df[column].fillna("").astype(str)).sum()
        )

        changes[f"standardize_{column}"] = {
            "values_normalized": normalized_count
        }

    # 5. CUSTOM VALUE STANDARDIZATION
    standardize_values = operations.get("standardize_values", {})

    for column, mappings in standardize_values.items():
        if column not in cleaned_df.columns:
            continue

        if not isinstance(mappings, dict):
            continue

        cleaned_df[column] = cleaned_df[column].replace(mappings)

        changes[f"standardize_values_{column}"] = {
            "mappings_applied": len(mappings)
        }

    # 6. TYPE CONVERSIONS
    type_conversions = operations.get("type_conversions", {})

    for column, target_type in type_conversions.items():
        if column not in cleaned_df.columns:
            continue

        try:
            if target_type == "integer":
                cleaned_df[column] = pd.to_numeric(
                    cleaned_df[column],
                    errors="coerce"
                ).round().astype("Int64")

            elif target_type == "float":
                cleaned_df[column] = pd.to_numeric(
                    cleaned_df[column],
                    errors="coerce"
                )

            elif target_type == "string":
                cleaned_df[column] = cleaned_df[column].astype("string")

            elif target_type == "datetime":
                cleaned_df[column] = _parse_dates(cleaned_df[column])

            changes[f"type_{column}"] = {
                "converted_to": target_type
            }

        except (ValueError, TypeError, OverflowError) as error:
            changes[f"type_{column}"] = {
                "status": "skipped",
                "reason": str(error)
            }

    # 7. OUTLIER CLIPPING
    # Only runs for columns explicitly selected by the user.
    outlier_columns = operations.get("outlier_columns", [])

    for column in outlier_columns:
        if column not in cleaned_df.columns:
            continue

        if not pd.api.types.is_numeric_dtype(cleaned_df[column]):
            continue

        if _is_identifier(column, cleaned_df[column]):
            changes[f"outliers_{column}"] = {
                "status": "skipped",
                "reason": "Identifier columns are not clipped."
            }
            continue

        valid = cleaned_df[column].dropna()

        if len(valid) < 4:
            changes[f"outliers_{column}"] = {
                "status": "skipped",
                "reason": "Not enough valid values."
            }
            continue

        q1 = valid.quantile(0.25)
        q3 = valid.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            changes[f"outliers_{column}"] = {
                "status": "skipped",
                "reason": "IQR is zero."
            }
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outlier_mask = (
            (cleaned_df[column] < lower_bound)
            | (cleaned_df[column] > upper_bound)
        )

        clipped_count = int(outlier_mask.sum())

        cleaned_df[column] = cleaned_df[column].clip(
            lower=lower_bound,
            upper=upper_bound
        )

        changes[f"outliers_{column}"] = {
            "clipped": clipped_count,
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound)
        }

    return cleaned_df, changes

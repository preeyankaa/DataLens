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


def _merge_case_variants(series):
    """
    Make the same value look the same ("paid search", "Paid Search ",
    "PAID SEARCH" -> the most common spelling). Returns (new_series, info).
    """
    text = series.astype("string")
    tidy = text.str.replace(r"\s+", " ", regex=True).str.strip()
    key = tidy.str.lower()

    frame = pd.DataFrame({"k": key, "v": tidy}).dropna()

    if frame.empty:
        return series, {"values_merged": 0, "groups_merged": 0}

    counts = (
        frame.groupby(["k", "v"]).size().reset_index(name="n")
        .sort_values(["k", "n", "v"], ascending=[True, False, True])
    )

    canonical = counts.drop_duplicates("k").set_index("k")["v"]
    variants = counts.groupby("k")["v"].nunique()

    merged = key.map(canonical).astype(object)
    merged = merged.where(text.notna(), np.nan)

    changed = int(
        (text.fillna("").astype(str) != merged.fillna("").astype(str)).sum()
    )

    return merged, {
        "values_merged": changed,
        "groups_merged": int((variants > 1).sum()),
    }


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
# STEP HELPERS
# (shared with the exported Python script, see app/codegen.py)
# --------------------------------------------------

def _find_replace_series(series, rule):
    """
    Replace text in a column.
    rule: {find, replace, match: "exact"|"contains", case_sensitive}
    Exact match with an empty replacement turns the cell into a blank
    (missing) value, which is handy for placeholders such as "N/A" or "-".
    Returns (new_series, replaced_count).
    """
    find = str(rule.get("find", ""))
    replace = str(rule.get("replace", ""))
    match = rule.get("match", "exact")
    case_sensitive = bool(rule.get("case_sensitive", False))

    text = series.astype("string")

    if match == "contains":
        new = text.str.replace(find, replace, case=case_sensitive, regex=False)
    else:
        stripped = text.str.strip()
        if case_sensitive:
            hit = stripped == find.strip()
        else:
            hit = stripped.str.lower() == find.strip().lower()
        hit = hit.fillna(False)
        new = text.mask(hit, pd.NA) if replace == "" else text.where(~hit, replace)

    count = int((text.fillna("<NA>") != new.fillna("<NA>")).sum())
    new = new.astype(object).where(new.notna(), np.nan)

    return new, count


def _apply_text_case(series, mode):
    text = series.astype("string")

    if mode == "lower":
        new = text.str.lower()
    elif mode == "upper":
        new = text.str.upper()
    elif mode == "title":
        new = text.str.title()
    else:
        raise ValueError(f"Unknown text case '{mode}'.")

    return new.astype(object).where(new.notna(), np.nan)


def _rule_mask(series, op, value):
    """True for the rows a rule like  quantity < 0  matches."""
    if op == "is_null":
        return series.isna()

    if op == "not_null":
        return series.notna()

    text = series.astype("string")

    if op == "contains":
        return text.str.contains(
            str(value), case=False, na=False, regex=False
        ).fillna(False)

    if op == "in":
        values = value if isinstance(value, list) else [value]
        wanted = {str(v).strip().lower() for v in values}
        return text.str.strip().str.lower().isin(wanted).fillna(False)

    if op in ("==", "!="):
        if pd.api.types.is_numeric_dtype(series):
            try:
                mask = pd.to_numeric(series, errors="coerce") == float(value)
            except (TypeError, ValueError):
                raise ValueError(f"'{value}' is not a number.")
        else:
            mask = (
                text.str.strip().str.lower() == str(value).strip().lower()
            )
        mask = mask.fillna(False)
        return mask if op == "==" else ~mask

    if op in (">", ">=", "<", "<="):
        left = pd.to_numeric(series, errors="coerce")
        right = None

        if left.notna().sum() == 0:
            # not numbers: try dates
            right = pd.to_datetime(value, errors="coerce")
            if pd.isna(right):
                raise ValueError(f"'{value}' is not a valid number or date.")
            left = pd.to_datetime(series, errors="coerce", format="mixed")
        else:
            try:
                right = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"'{value}' is not a number.")

        compare = {
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
        }[op]

        return compare.fillna(False)

    raise ValueError(f"Unsupported row rule '{op}'.")


def _clip_outliers(df, column):
    """Cap extreme values of one numeric column (IQR rule). Edits df."""
    if not pd.api.types.is_numeric_dtype(df[column]):
        return None

    if _is_identifier(column, df[column]):
        return {
            "status": "skipped",
            "reason": "Identifier columns are not clipped."
        }

    valid = df[column].dropna()

    if len(valid) < 4:
        return {"status": "skipped", "reason": "Not enough valid values."}

    q1 = valid.quantile(0.25)
    q3 = valid.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        return {"status": "skipped", "reason": "IQR is zero."}

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    clipped_count = int(
        ((df[column] < lower_bound) | (df[column] > upper_bound)).sum()
    )

    df[column] = df[column].clip(lower=lower_bound, upper=upper_bound)

    return {
        "clipped": clipped_count,
        "lower_bound": float(lower_bound),
        "upper_bound": float(upper_bound)
    }


def _convert_type(df, column, target_type):
    """Change a column's type. Numbers typed as text ("$1,200") are handled."""
    try:
        series = df[column]
        non_empty_before = int(series.notna().sum())

        if target_type in ("integer", "float"):
            if pd.api.types.is_numeric_dtype(series):
                numbers = series
            else:
                tidy = (
                    series.astype("string")
                    .str.replace(r"[,\s$€£₹%]", "", regex=True)
                )
                numbers = pd.to_numeric(tidy, errors="coerce")

            if target_type == "integer":
                numbers = numbers.round().astype("Int64")

            df[column] = numbers
            lost = non_empty_before - int(df[column].notna().sum())

            return {"converted_to": target_type, "became_empty": lost}

        if target_type == "string":
            df[column] = series.astype("string")
            return {"converted_to": target_type}

        if target_type == "datetime":
            df[column] = _parse_dates(series)
            lost = non_empty_before - int(df[column].notna().sum())
            return {"converted_to": target_type, "became_empty": lost}

        return {
            "status": "skipped",
            "reason": f"Unknown type '{target_type}'."
        }

    except (ValueError, TypeError, OverflowError) as error:
        return {"status": "skipped", "reason": str(error)}


def _validate_operations(operations):
    """Clear messages for malformed recipes."""
    expected = {
        "remove_duplicates": (bool, int),
        "merge_case_columns": (list,),
        "standardize_columns": (list,),
        "standardize_values": (dict,),
        "date_columns": (list,),
        "type_conversions": (dict,),
        "missing_values": (dict,),
        "outlier_columns": (list,),
        "find_replace": (list,),
        "text_case": (dict,),
        "drop_rows": (list,),
        "drop_columns": (list,),
        "rename_columns": (dict,),
    }

    for key, types in expected.items():
        value = operations.get(key)
        if value is not None and not isinstance(value, types):
            raise ValueError(f"Cleaning option '{key}' has the wrong format.")


# --------------------------------------------------
# MAIN CLEANING FUNCTION
# --------------------------------------------------
# Every option refers to the ORIGINAL column names. Renaming happens last.
#
# Order matters. Text and dates are made consistent FIRST, so rows that
# only differed by spelling or date style are recognised as duplicates.
#
#   1 find & replace      2 text case        3 tidy text      4 merge spellings
#   5 value mappings      6 dates            7 column types   8 remove rows
#   9 duplicates         10 missing values  11 duplicates     12 outliers
#  13 drop columns       14 rename columns

def clean_dataframe(df, operations):
    cleaned_df = df.copy()
    changes = {}

    operations = operations or {}
    _validate_operations(operations)

    # 1. FIND & REPLACE
    for rule in operations.get("find_replace") or []:
        column = rule.get("column")

        if column not in cleaned_df.columns or str(rule.get("find", "")) == "":
            continue

        key = f"find_replace_{column}"

        if pd.api.types.is_numeric_dtype(cleaned_df[column]):
            changes[key] = {
                "status": "skipped",
                "reason": "This column holds numbers, not text."
            }
            continue

        cleaned_df[column], count = _find_replace_series(cleaned_df[column], rule)

        previous = changes.get(key, {"replacements": 0, "rules": 0})
        changes[key] = {
            "replacements": previous.get("replacements", 0) + count,
            "rules": previous.get("rules", 0) + 1,
        }

    # 2. TEXT CASE
    for column, mode in (operations.get("text_case") or {}).items():
        if column not in cleaned_df.columns:
            continue

        if pd.api.types.is_numeric_dtype(cleaned_df[column]):
            continue

        before = cleaned_df[column].copy()
        cleaned_df[column] = _apply_text_case(cleaned_df[column], mode)

        changes[f"text_case_{column}"] = {
            "case": mode,
            "values_changed": int(
                (before.fillna("").astype(str) !=
                 cleaned_df[column].fillna("").astype(str)).sum()
            ),
        }

    # 3. TEXT TIDY-UP (spaces, aliases)
    for column in operations.get("standardize_columns", []) or []:
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

    # 4. SAME VALUE, DIFFERENT SPELLING (case and spaces)
    for column in operations.get("merge_case_columns", []) or []:
        if column not in cleaned_df.columns:
            continue

        if pd.api.types.is_numeric_dtype(cleaned_df[column]):
            continue

        merged, info = _merge_case_variants(cleaned_df[column])
        cleaned_df[column] = merged

        changes[f"merge_case_{column}"] = info

    # 5. CUSTOM VALUE STANDARDIZATION
    standardize_values = operations.get("standardize_values", {}) or {}

    for column, mappings in standardize_values.items():
        if column not in cleaned_df.columns:
            continue

        if not isinstance(mappings, dict):
            continue

        cleaned_df[column] = cleaned_df[column].replace(mappings)

        changes[f"standardize_values_{column}"] = {
            "mappings_applied": len(mappings)
        }

    # 6. DATE STANDARDIZATION
    for column in operations.get("date_columns", []) or []:
        if column not in cleaned_df.columns:
            continue

        parsed = _parse_dates(cleaned_df[column])

        cleaned_df[column] = parsed.dt.strftime("%Y-%m-%d")

        changes[f"date_{column}"] = {
            "converted": int(parsed.notna().sum()),
            "invalid_or_missing": int(parsed.isna().sum()),
            "format": "YYYY-MM-DD"
        }

    # 7. TYPE CONVERSIONS
    for column, target_type in (operations.get("type_conversions") or {}).items():
        if column not in cleaned_df.columns:
            continue

        changes[f"type_{column}"] = _convert_type(
            cleaned_df, column, target_type
        )

    # 8. REMOVE ROWS THAT MATCH A RULE  (e.g. quantity < 0)
    for number, rule in enumerate(operations.get("drop_rows") or [], start=1):
        column = rule.get("column")

        if column not in cleaned_df.columns:
            continue

        op = rule.get("op", "==")
        value = rule.get("value")

        mask = _rule_mask(cleaned_df[column], op, value)
        removed = cleaned_df.index[mask.to_numpy()]

        examples = [
            {"row": int(index) + 2, "value": str(cleaned_df.at[index, column])}
            for index in removed[:3]
        ]

        cleaned_df = cleaned_df.drop(index=removed)

        shown = "" if op in ("is_null", "not_null") else f" {value}"
        changes[f"drop_rows_{number}"] = {
            "column": column,
            "rule": f"{column} {op}{shown}",
            "rows_removed": int(len(removed)),
            "examples": examples,
        }

    # 9. REMOVE DUPLICATES
    remove_duplicates = operations.get("remove_duplicates", False)

    if remove_duplicates:
        before = len(cleaned_df)

        cleaned_df.drop_duplicates(inplace=True)

        changes["duplicates_removed"] = before - len(cleaned_df)

    # 10. MISSING VALUES
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

    # 11. Filling empty cells can make two rows identical (for example an
    #     empty discount filled with 0). Remove those copies too.
    if remove_duplicates:
        before = len(cleaned_df)

        cleaned_df.drop_duplicates(inplace=True)

        changes["duplicates_removed"] = (
            changes.get("duplicates_removed", 0) + before - len(cleaned_df)
        )

    # 12. OUTLIER CLIPPING
    # Only runs for columns explicitly selected by the user.
    for column in operations.get("outlier_columns", []) or []:
        if column not in cleaned_df.columns:
            continue

        result = _clip_outliers(cleaned_df, column)

        if result is not None:
            changes[f"outliers_{column}"] = result

    # 13. DROP COLUMNS
    to_drop = [
        c for c in (operations.get("drop_columns") or [])
        if c in cleaned_df.columns
    ]

    if to_drop:
        cleaned_df = cleaned_df.drop(columns=to_drop)
        changes["drop_columns"] = {"dropped": to_drop}

    # 14. RENAME COLUMNS
    renames = {
        str(old): str(new).strip()
        for old, new in (operations.get("rename_columns") or {}).items()
        if old in cleaned_df.columns
    }

    if renames:
        for old, new in renames.items():
            if not new:
                raise ValueError(f"The new name for '{old}' cannot be empty.")

        final_names = [renames.get(c, c) for c in cleaned_df.columns]
        repeated = sorted({n for n in final_names if final_names.count(n) > 1})

        if repeated:
            raise ValueError(
                "These column names would appear more than once after "
                f"renaming: {', '.join(map(str, repeated))}."
            )

        cleaned_df = cleaned_df.rename(columns=renames)
        changes["rename_columns"] = {"renamed": renames}

    return cleaned_df, changes
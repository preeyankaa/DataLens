import math
import re

import pandas as pd


DATE_KEYWORDS = ("date", "time", "timestamp", "dob", "birth")

MAX_TEXT_UNIQUE = 300          # skip free-text style columns
MAX_VARIANT_EXAMPLES = 3


def _safe_number(value):
    """Convert a number to JSON-safe output."""
    number = float(value)
    return number if math.isfinite(number) else None


def _inconsistent_text(series):
    """
    Find values that are the same thing written differently
    ("Paid Search", "paid search", "PAID SEARCH ").
    Returns (affected_cells, groups, row_mask). row_mask is True where the
    cell is not written in the most common spelling.
    """
    empty = pd.Series(False, index=series.index)
    values = series.dropna().astype(str)
    if values.empty:
        return 0, [], empty

    counts = values.value_counts()
    if len(counts) > MAX_TEXT_UNIQUE or len(counts) / len(values) > 0.5:
        return 0, [], empty

    key = (
        counts.index.to_series()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.lower()
    )

    groups = []
    canonical = {}

    for _, spellings in counts.groupby(key.to_numpy()):
        if len(spellings) < 2:
            continue
        ordered = spellings.sort_values(ascending=False)
        for spelling in ordered.index:
            canonical[spelling] = ordered.index[0]
        groups.append(
            [repr(v) if v != v.strip() else v for v in ordered.index[:4]]
        )

    if not canonical:
        return 0, [], empty

    as_text = series.astype("string")
    mask = as_text.map(canonical).notna() & (
        as_text.map(canonical) != as_text
    )
    mask = mask.fillna(False).astype(bool)

    groups.sort(key=len, reverse=True)
    return int(mask.sum()), groups[:MAX_VARIANT_EXAMPLES], mask


def _date_style_votes(series):
    """Count unambiguous day-first and month-first slash dates."""
    day_first = month_first = 0

    for value in series.dropna().astype(str).head(5000):
        match = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", value)
        if not match:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12 and second <= 12:
            day_first += 1
        elif second > 12 and first <= 12:
            month_first += 1

    return day_first, month_first


def check_data_quality(
    df: pd.DataFrame,
    non_negative_columns: list[str] | None = None,
) -> dict:
    """
    Identify potential data quality issues.

    non_negative_columns contains columns where negative values
    are known to be invalid for the user's use case.
    """

    non_negative_columns = non_negative_columns or []

    row_count = len(df)
    column_count = len(df.columns)
    total_cells = row_count * column_count

    issues = []
    column_quality = {}

    # 1. Missing values
    missing_by_column = df.isna().sum()

    for column in df.columns:
        missing_count = int(missing_by_column[column])

        if missing_count > 0:
            percentage = (
                round(missing_count / row_count * 100, 2)
                if row_count else 0.0
            )

            issues.append({
                "type": "missing_values",
                "column": str(column),
                "severity": "high" if percentage >= 30 else "medium",
                "count": missing_count,
                "percentage": percentage,
                "message": (
                    f"{missing_count} missing values found in '{column}'."
                ),
                "recommendation": (
                    "Review the missing values and choose an appropriate "
                    "handling strategy."
                ),
            })

    # 2. Duplicate rows
    duplicate_mask = df.duplicated()
    duplicate_count = int(duplicate_mask.sum())

    if duplicate_count > 0:
        duplicate_percentage = (
            round(duplicate_count / row_count * 100, 2)
            if row_count else 0.0
        )

        issues.append({
            "type": "duplicate_rows",
            "column": None,
            "severity": (
                "high" if duplicate_percentage >= 20 else "medium"
            ),
            "count": duplicate_count,
            "percentage": duplicate_percentage,
            "row_indices": [
                int(index)
                for index in df.index[duplicate_mask][:100]
                if isinstance(index, (int, pd.api.types.pandas_dtype("int64").type))
            ],
            "message": f"{duplicate_count} duplicate rows detected.",
            "recommendation": (
                "Review repeated records before deciding whether to remove them."
            ),
        })

    # 3. Column-level checks
    for column in df.columns:
        series = df[column]
        non_missing = series.dropna()
        unique_count = int(series.nunique(dropna=True))

        column_quality[str(column)] = {
            "unique_values": unique_count,
            "is_constant": (
                len(non_missing) > 0 and unique_count == 1
            ),
        }

        if len(non_missing) > 0 and unique_count == 1:
            issues.append({
                "type": "constant_column",
                "column": str(column),
                "severity": "low",
                "count": len(non_missing),
                "percentage": 100.0,
                "message": (
                    f"Column '{column}' contains only one distinct value."
                ),
                "recommendation": (
                    "Check whether this column is useful for analysis."
                ),
            })

    # 4. Same value written in different ways (case / extra spaces)
    inconsistent_cell_count = 0
    inconsistent_rows = pd.Series(False, index=df.index)

    for column in df.columns:
        series = df[column]

        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            continue

        affected, groups, text_mask = _inconsistent_text(series)

        if affected == 0:
            continue

        inconsistent_cell_count += affected
        inconsistent_rows |= text_mask
        column_quality[str(column)]["inconsistent_values"] = affected

        issues.append({
            "type": "inconsistent_text",
            "column": str(column),
            "severity": "medium",
            "count": affected,
            "percentage": round(affected / row_count * 100, 2) if row_count else 0.0,
            "examples": groups,
            "message": (
                f"'{column}' has the same value written in different ways "
                f"({affected} cells differ in capital letters or spaces)."
            ),
            "recommendation": (
                "Merge the spellings so each value appears one way. Otherwise "
                "charts and totals will split one group into several."
            ),
        })

    # 5. IQR-based outlier detection
    numeric_df = df.select_dtypes(include="number")

    outlier_cell_count = 0
    outlier_rows = pd.Series(False, index=df.index)

    for column in numeric_df.columns:
        series = numeric_df[column].dropna()

        if len(series) < 4:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if not math.isfinite(float(iqr)) or iqr == 0:
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outlier_mask = (
            (numeric_df[column] < lower_bound)
            | (numeric_df[column] > upper_bound)
        ).fillna(False)

        count = int(outlier_mask.sum())
        outlier_cell_count += count
        outlier_rows |= outlier_mask

        if count > 0:
            issues.append({
                "type": "outliers",
                "column": str(column),
                "severity": "medium",
                "count": count,
                "percentage": round(count / row_count * 100, 2)
                if row_count else 0.0,
                "lower_bound": _safe_number(lower_bound),
                "upper_bound": _safe_number(upper_bound),
                "message": (
                    f"{count} potential outliers detected in '{column}'."
                ),
                "recommendation": (
                    "Review flagged values in context. Statistical outliers "
                    "are not necessarily errors."
                ),
            })

    # 6. Negative values in user-designated non-negative columns
    for column in non_negative_columns:
        if column not in df.columns:
            continue

        if not pd.api.types.is_numeric_dtype(df[column]):
            continue

        negative_mask = df[column] < 0
        count = int(negative_mask.sum())

        if count > 0:
            issues.append({
                "type": "negative_values",
                "column": str(column),
                "severity": "high",
                "count": count,
                "percentage": round(count / row_count * 100, 2)
                if row_count else 0.0,
                "message": (
                    f"{count} negative values found in '{column}', "
                    "which was configured as non-negative."
                ),
                "recommendation": (
                    "Verify the business rule and investigate the affected values."
                ),
            })

    # 7. Dates: values that cannot be read, and mixed date styles
    for column in df.columns:
        name = str(column).lower()

        if not any(keyword in name for keyword in DATE_KEYWORDS):
            continue

        if pd.api.types.is_numeric_dtype(df[column]):
            continue

        non_missing = df[column].dropna()

        if non_missing.empty:
            continue

        day_first, month_first = _date_style_votes(non_missing)

        if day_first and month_first:
            issues.append({
                "type": "mixed_date_formats",
                "column": str(column),
                "severity": "medium",
                "count": day_first + month_first,
                "percentage": round(
                    min(day_first, month_first) / len(non_missing) * 100, 2
                ),
                "message": (
                    f"'{column}' mixes two date styles: {month_first} dates are "
                    f"clearly MM/DD/YYYY and {day_first} are clearly DD/MM/YYYY."
                ),
                "recommendation": (
                    "Convert all dates to one format (YYYY-MM-DD) and check any "
                    "ambiguous dates such as 04/05/2025."
                ),
            })

        parsed = pd.to_datetime(
            non_missing,
            errors="coerce",
            format="mixed",
        )

        invalid_count = int(parsed.isna().sum())

        if invalid_count > 0:
            percentage = round(
                invalid_count / len(non_missing) * 100, 2
            )

            issues.append({
                "type": "invalid_dates",
                "column": str(column),
                "severity": "medium",
                "count": invalid_count,
                "percentage": percentage,
                "message": (
                    f"{invalid_count} non-missing values in '{column}' "
                    "could not be parsed as dates."
                ),
                "recommendation": (
                    "Review the expected date format and the flagged values."
                ),
            })

    # 8. Explainable quality score
    # Based on the share of ROWS affected, so it reacts clearly to real problems.
    missing_cells = int(df.isna().sum().sum())

    def share(count):
        return count / row_count if row_count else 0.0

    penalties = {
        "missing": 35 * share(int(df.isna().any(axis=1).sum())),
        "duplicates": 20 * share(duplicate_count),
        "outliers": 15 * share(int(outlier_rows.sum())),
        "inconsistent_text": 30 * share(int(inconsistent_rows.sum())),
    }

    quality_score = round(
        max(0.0, min(100.0, 100 - sum(penalties.values()))),
        2,
    )

    return {
        "quality_score": quality_score,
        "score_explanation": {
            "method": (
                "100 minus points for the share of rows that have a missing "
                "value, are duplicates, hold an outlier, or use inconsistent spelling"
            ),
            "penalties": {
                key: round(value, 2)
                for key, value in penalties.items()
            },
            "weights": {
                "missing": 35,
                "duplicates": 20,
                "outliers": 15,
                "inconsistent_text": 30,
            },
            "note": (
                "This preliminary heuristic does not include all issue types "
                "and should be calibrated for the dataset's use case."
            ),
        },
        "summary": {
            "total_rows": row_count,
            "total_columns": column_count,
            "total_issues": len(issues),
            "missing_cells": missing_cells,
            "duplicate_rows": duplicate_count,
            "outlier_cells": outlier_cell_count,
            "inconsistent_cells": inconsistent_cell_count,
        },
        "column_quality": column_quality,
        "issues": issues,
    }
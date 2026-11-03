
import math

import pandas as pd


DATE_KEYWORDS = ("date", "time", "timestamp", "dob", "birth")


def _safe_number(value):
    """Convert a number to JSON-safe output."""
    number = float(value)
    return number if math.isfinite(number) else None


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
                if isinstance(index, int)
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

    # 4. IQR-based outlier detection
    numeric_df = df.select_dtypes(include="number")

    outlier_cell_count = 0

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

    # 5. Negative values in user-designated non-negative columns
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

    # 6. Potentially invalid dates in date-like column names
    for column in df.columns:
        name = str(column).lower()

        if not any(keyword in name for keyword in DATE_KEYWORDS):
            continue

        if pd.api.types.is_numeric_dtype(df[column]):
            continue

        non_missing = df[column].dropna()

        if non_missing.empty:
            continue

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

    # 7. Explainable quality score
    missing_cells = int(df.isna().sum().sum())

    missing_rate = (
        missing_cells / total_cells if total_cells else 0.0
    )
    duplicate_rate = (
        duplicate_count / row_count if row_count else 0.0
    )
    outlier_rate = (
        outlier_cell_count / total_cells if total_cells else 0.0
    )

    # This is a heuristic score, not a universal quality standard.
    penalties = {
        "missing": 40 * missing_rate,
        "duplicates": 20 * duplicate_rate,
        "outliers": 20 * outlier_rate,
    }

    quality_score = round(
        max(0.0, min(100.0, 100 - sum(penalties.values()))),
        2,
    )

    return {
        "quality_score": quality_score,
        "score_explanation": {
            "method": "100 minus weighted missing, duplicate and outlier rates",
            "penalties": {
                key: round(value, 2)
                for key, value in penalties.items()
            },
            "weights": {
                "missing": 40,
                "duplicates": 20,
                "outliers": 20,
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
        },
        "column_quality": column_quality,
        "issues": issues,
    }


import json

import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    """
    Analyze a DataFrame and return a JSON-friendly profiling report.
    """

    row_count = len(df)
    column_count = len(df.columns)

    # 1. Dataset-level information
    total_cells = row_count * column_count
    missing_cells = int(df.isna().sum().sum())

    missing_percentage = (
        round((missing_cells / total_cells) * 100, 2)
        if total_cells > 0
        else 0.0
    )

    duplicate_rows = int(df.duplicated().sum())

    # 2. Column-level information
    column_profiles = {}

    for column in df.columns:
        series = df[column]

        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))

        column_profiles[str(column)] = {
            "data_type": str(series.dtype),
            "missing_count": missing_count,
            "missing_percentage": (
                round((missing_count / row_count) * 100, 2)
                if row_count > 0
                else 0.0
            ),
            "unique_values": unique_count,
            "duplicate_values": int(row_count - missing_count - unique_count),
        }

    # 3. Numerical statistics
    numerical_statistics = {}

    numeric_df = df.select_dtypes(include="number")

    for column in numeric_df.columns:
        series = numeric_df[column].dropna()

        if series.empty:
            numerical_statistics[str(column)] = {
                "count": 0,
                "mean": None,
                "median": None,
                "std": None,
                "min": None,
                "max": None,
            }
            continue

        numerical_statistics[str(column)] = {
            "count": int(series.count()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "std": (
                float(series.std())
                if series.count() > 1
                else None
            ),
            "min": float(series.min()),
            "max": float(series.max()),
        }

    # 4. Preview: first five rows
    preview_json = df.head(5).to_json(
        orient="records",
        date_format="iso",
    )
    preview = json.loads(preview_json)

    # 5. Overall report
    return {
        "overview": {
            "total_rows": row_count,
            "total_columns": column_count,
            "total_cells": total_cells,
            "missing_cells": missing_cells,
            "missing_percentage": missing_percentage,
            "duplicate_rows": duplicate_rows,
            "memory_usage_bytes": int(
                df.memory_usage(index=True, deep=True).sum()
            ),
        },
        "columns": column_profiles,
        "numerical_statistics": numerical_statistics,
        "preview": preview,
    }

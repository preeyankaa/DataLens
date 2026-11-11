
import json
import pandas as pd


def build_dataset_context(df: pd.DataFrame) -> str:
    """Create a compact summary of a dataset for AI question answering."""

    total_rows = len(df)
    total_columns = len(df.columns)

    # Overall dataset information
    context = {
        "dataset_overview": {
            "total_rows": total_rows,
            "total_columns": total_columns,
            "total_missing_values": int(df.isna().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()),
        },
        "columns": {},
    }

    # Information about each column
    for column in df.columns:
        series = df[column]

        column_info = {
            "data_type": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_percentage": round(
                float(series.isna().mean() * 100), 2
            ),
            "unique_values": int(series.nunique()),
        }

        # Exact row positions containing missing values (1-based)
        missing_rows = [
            position
            for position, is_missing in enumerate(series.isna(), start=1)
            if is_missing
        ]

        column_info["missing_row_numbers"] = missing_rows[:50]

        # Numerical column statistics
        if pd.api.types.is_numeric_dtype(series):
            numeric_series = series.dropna()

            if not numeric_series.empty:
                column_info["statistics"] = {
                    "minimum": round(float(numeric_series.min()), 2),
                    "maximum": round(float(numeric_series.max()), 2),
                    "average": round(float(numeric_series.mean()), 2),
                    "median": round(float(numeric_series.median()), 2),
                }

        # Most frequent values for non-numerical columns
        else:
            top_values = series.dropna().value_counts().head(5)
            column_info["top_values"] = {
                str(value): int(count)
                for value, count in top_values.items()
            }

        context["columns"][str(column)] = column_info

    # Duplicate row positions (1-based)
    duplicate_positions = [
        position
        for position, is_duplicate in enumerate(
            df.duplicated(keep="first"), start=1
        )
        if is_duplicate
    ]

    context["duplicate_row_numbers"] = duplicate_positions[:50]

    return json.dumps(context, default=str, indent=2)


import pandas as pd


def clean_dataframe(
    df: pd.DataFrame,
    operations: dict,
) -> tuple[pd.DataFrame, dict]:
    """
    Apply user-selected cleaning operations to a copy
    of the original DataFrame.

    Returns:
        cleaned_df: Modified copy of the dataset.
        changes: Summary of cleaning operations.
    """

    cleaned_df = df.copy(deep=True)

    changes = {}

    def validate_column(column):
        if column not in cleaned_df.columns:
            raise ValueError(f"Column '{column}' does not exist.")

    # 1. Remove duplicate rows
    if operations.get("remove_duplicates", False):

        before = len(cleaned_df)

        cleaned_df = cleaned_df.drop_duplicates()

        removed = before - len(cleaned_df)

        changes["duplicates_removed"] = removed

    # 2. Handle missing values
    missing_operations = operations.get("missing_values", {})

    for column, config in missing_operations.items():

        validate_column(column)

        if not isinstance(config, dict):
            raise ValueError(
                f"Invalid missing-value configuration for '{column}'."
            )

        strategy = config.get("strategy")
        series = cleaned_df[column]

        before = int(series.isna().sum())

        if before == 0:
            changes[f"missing_{column}"] = 0
            continue

        if strategy == "mean":

            if not pd.api.types.is_numeric_dtype(series):
                raise ValueError(
                    f"Mean strategy requires numeric column '{column}'."
                )

            fill_value = series.mean()

        elif strategy == "median":

            if not pd.api.types.is_numeric_dtype(series):
                raise ValueError(
                    f"Median strategy requires numeric column '{column}'."
                )

            fill_value = series.median()

        elif strategy == "mode":

            modes = series.mode(dropna=True)

            if modes.empty:
                raise ValueError(
                    f"Cannot calculate mode for '{column}'."
                )

            fill_value = modes.iloc[0]

        elif strategy == "constant":

            if "value" not in config:
                raise ValueError(
                    f"Constant value is required for '{column}'."
                )

            fill_value = config["value"]

        elif strategy == "drop_rows":

            cleaned_df = cleaned_df.dropna(subset=[column])

            changes[f"missing_{column}"] = {
                "rows_removed": before
            }

            continue

        else:
            raise ValueError(
                f"Unsupported missing-value strategy: {strategy}"
            )

        if pd.isna(fill_value):
            raise ValueError(
                f"Cannot fill missing values in '{column}'."
            )

        cleaned_df[column] = series.fillna(fill_value)

        changes[f"missing_{column}"] = {
            "strategy": strategy,
            "filled": before,
        }

    # 3. Standardize dates
    date_columns = operations.get("date_columns", [])

    for column in date_columns:

        validate_column(column)

        before = cleaned_df[column]

        non_missing = before.notna()

        parsed = pd.to_datetime(
            before,
            errors="coerce",
            format="mixed",
        )

        invalid_count = int(
            (non_missing & parsed.isna()).sum()
        )

        if invalid_count > 0:
            raise ValueError(
                f"Cannot standardize '{column}': "
                f"{invalid_count} invalid date values found."
            )

        cleaned_df[column] = parsed.dt.strftime("%Y-%m-%d")

        changes[f"date_{column}"] = {
            "converted": int(non_missing.sum()),
        }

    # 4. Convert data types
    type_conversions = operations.get("type_conversions", {})

    for column, target_type in type_conversions.items():

        validate_column(column)

        try:

            if target_type == "integer":

                numeric = pd.to_numeric(
                    cleaned_df[column],
                    errors="raise",
                )

                if not numeric.dropna().mod(1).eq(0).all():
                    raise ValueError(
                        "Values contain decimal numbers."
                    )

                cleaned_df[column] = numeric.astype("Int64")

            elif target_type == "float":

                cleaned_df[column] = pd.to_numeric(
                    cleaned_df[column],
                    errors="raise",
                )

            elif target_type == "string":

                cleaned_df[column] = cleaned_df[column].astype(
                    "string"
                )

            elif target_type == "datetime":

                cleaned_df[column] = pd.to_datetime(
                    cleaned_df[column],
                    errors="raise",
                    format="mixed",
                )

            else:
                raise ValueError(
                    f"Unsupported target type: {target_type}"
                )

        except (ValueError, TypeError, OverflowError) as error:

            raise ValueError(
                f"Cannot convert '{column}' to {target_type}: {error}"
            ) from error

        changes[f"type_{column}"] = {
            "converted_to": target_type,
        }

    # 5. Handle outliers using IQR clipping
    outlier_columns = operations.get("outlier_columns", [])

    for column in outlier_columns:

        validate_column(column)

        if not pd.api.types.is_numeric_dtype(cleaned_df[column]):
            raise ValueError(
                f"Outlier clipping requires numeric column '{column}'."
            )

        series = cleaned_df[column]

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)

        if pd.isna(q1) or pd.isna(q3):
            changes[f"outliers_{column}"] = 0
            continue

        iqr = q3 - q1

        if iqr == 0:
            changes[f"outliers_{column}"] = 0
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outlier_mask = (
            (series < lower) | (series > upper)
        ).fillna(False)

        count = int(outlier_mask.sum())

        cleaned_df[column] = series.clip(
            lower=lower,
            upper=upper,
        )

        changes[f"outliers_{column}"] = {
            "clipped": count,
            "lower_bound": float(lower),
            "upper_bound": float(upper),
        }

    return cleaned_df, changes

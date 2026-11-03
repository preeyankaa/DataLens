
import pandas as pd
import pytest

from app.cleaning import clean_dataframe


def test_remove_duplicates():
    df = pd.DataFrame({
        "id": [101, 102, 101],
        "city": ["Mumbai", "Pune", "Mumbai"],
    })

    cleaned, changes = clean_dataframe(
        df,
        {"remove_duplicates": True},
    )

    assert len(cleaned) == 2
    assert changes["duplicates_removed"] == 1


def test_fill_missing_with_median():
    df = pd.DataFrame({
        "age": [20, 30, None, 40],
    })

    cleaned, changes = clean_dataframe(
        df,
        {
            "missing_values": {
                "age": {"strategy": "median"}
            }
        },
    )

    assert cleaned["age"].isna().sum() == 0
    assert cleaned.loc[2, "age"] == 30
    assert changes["missing_age"]["filled"] == 1


def test_standardize_dates():
    df = pd.DataFrame({
        "order_date": [
            "10/01/2026",
            "2026-01-11",
            "12-Jan-2026",
        ],
    })

    cleaned, changes = clean_dataframe(
        df,
        {"date_columns": ["order_date"]},
    )

    assert cleaned["order_date"].tolist() == [
        "2026-10-01",
        "2026-01-11",
        "2026-01-12",
    ]


def test_invalid_date_is_rejected():
    df = pd.DataFrame({
        "order_date": ["2026-01-10", "not-a-date"],
    })

    with pytest.raises(ValueError):
        clean_dataframe(
            df,
            {"date_columns": ["order_date"]},
        )


def test_convert_to_integer():
    df = pd.DataFrame({
        "age": ["20", "30", "40"],
    })

    cleaned, _ = clean_dataframe(
        df,
        {"type_conversions": {"age": "integer"}},
    )

    assert str(cleaned["age"].dtype) == "Int64"
    assert cleaned["age"].tolist() == [20, 30, 40]


def test_clip_outliers():
    df = pd.DataFrame({
        "sales": [10, 12, 14, 16, 18, 1000],
    })

    cleaned, changes = clean_dataframe(
        df,
        {"outlier_columns": ["sales"]},
    )

    assert cleaned["sales"].max() < 1000
    assert changes["outliers_sales"]["clipped"] == 1


def test_original_dataframe_is_unchanged():
    df = pd.DataFrame({
        "age": [20, None, 40],
    })

    original = df.copy(deep=True)

    clean_dataframe(
        df,
        {
            "missing_values": {
                "age": {"strategy": "median"}
            }
        },
    )

    pd.testing.assert_frame_equal(df, original)


def test_invalid_column_is_rejected():
    df = pd.DataFrame({"age": [20, 30]})

    with pytest.raises(ValueError):
        clean_dataframe(
            df,
            {
                "missing_values": {
                    "salary": {"strategy": "mean"}
                }
            },
        )

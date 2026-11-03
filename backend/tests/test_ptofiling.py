
import pandas as pd

from app.profiling import profile_dataframe


def test_dataset_overview():
    df = pd.DataFrame({
        "age": [24, 32, None],
        "city": ["Mumbai", "Pune", "Mumbai"],
    })

    report = profile_dataframe(df)
    overview = report["overview"]

    assert overview["total_rows"] == 3
    assert overview["total_columns"] == 2
    assert overview["total_cells"] == 6
    assert overview["missing_cells"] == 1
    assert overview["missing_percentage"] == 16.67


def test_duplicate_rows():
    df = pd.DataFrame({
        "id": [101, 102, 101],
        "city": ["Mumbai", "Pune", "Mumbai"],
    })

    report = profile_dataframe(df)

    assert report["overview"]["duplicate_rows"] == 1


def test_numerical_statistics():
    df = pd.DataFrame({
        "sales": [100, 200, 300],
    })

    report = profile_dataframe(df)
    stats = report["numerical_statistics"]["sales"]

    assert stats["count"] == 3
    assert stats["mean"] == 200.0
    assert stats["median"] == 200.0
    assert stats["min"] == 100.0
    assert stats["max"] == 300.0


def test_column_profile():
    df = pd.DataFrame({
        "city": ["Mumbai", "Pune", "Mumbai", None],
    })

    report = profile_dataframe(df)
    city = report["columns"]["city"]

    assert city["missing_count"] == 1
    assert city["missing_percentage"] == 25.0
    assert city["unique_values"] == 2

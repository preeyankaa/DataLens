
import pandas as pd

from app.quality import check_data_quality


def test_missing_values_are_flagged():
    df = pd.DataFrame({
        "age": [24, None, 32, 40],
    })

    report = check_data_quality(df)

    assert report["summary"]["missing_cells"] == 1

    missing_issues = [
        issue for issue in report["issues"]
        if issue["type"] == "missing_values"
    ]

    assert len(missing_issues) == 1
    assert missing_issues[0]["column"] == "age"
    assert missing_issues[0]["count"] == 1


def test_duplicate_rows_are_detected():
    df = pd.DataFrame({
        "id": [101, 102, 101],
        "city": ["Mumbai", "Pune", "Mumbai"],
    })

    report = check_data_quality(df)

    assert report["summary"]["duplicate_rows"] == 1

    duplicate_issues = [
        issue for issue in report["issues"]
        if issue["type"] == "duplicate_rows"
    ]

    assert len(duplicate_issues) == 1


def test_negative_values_follow_configured_rules():
    df = pd.DataFrame({
        "age": [24, -2, 30],
        "balance": [-100, 200, 300],
    })

    report = check_data_quality(
        df,
        non_negative_columns=["age"],
    )

    negative_issues = [
        issue for issue in report["issues"]
        if issue["type"] == "negative_values"
    ]

    assert len(negative_issues) == 1
    assert negative_issues[0]["column"] == "age"
    assert negative_issues[0]["count"] == 1


def test_invalid_dates_are_detected():
    df = pd.DataFrame({
        "order_date": [
            "2026-01-10",
            "not-a-date",
            "2026-01-12",
        ],
    })

    report = check_data_quality(df)

    date_issues = [
        issue for issue in report["issues"]
        if issue["type"] == "invalid_dates"
    ]

    assert len(date_issues) == 1
    assert date_issues[0]["count"] == 1


def test_quality_score_stays_in_range():
    df = pd.DataFrame({
        "value": [10, 20, None, 20],
    })

    report = check_data_quality(df)

    assert 0 <= report["quality_score"] <= 100


def test_constant_column_is_detected():
    df = pd.DataFrame({
        "country": ["India", "India", "India"],
    })

    report = check_data_quality(df)

    constant_issues = [
        issue for issue in report["issues"]
        if issue["type"] == "constant_column"
    ]

    assert len(constant_issues) == 1
    assert constant_issues[0]["column"] == "country"

"""New cleaning steps: find & replace, text case, row rules, drop and rename."""
import pandas as pd
import pytest

from app.cleaning import clean_dataframe


def test_find_replace_exact_with_blank_makes_cells_missing():
    df = pd.DataFrame({"price": ["5", "N/A", "n/a ", "7", None]})
    cleaned, changes = clean_dataframe(df, {"find_replace": [{"column": "price", "find": "N/A", "replace": ""}]})
    assert cleaned["price"].isna().sum() == 3
    assert changes["find_replace_price"]["replacements"] == 2


def test_find_replace_contains_and_case_sensitive():
    df = pd.DataFrame({"city": ["New York", "new york", "Boston"]})
    cleaned, _ = clean_dataframe(df, {"find_replace": [{"column": "city", "find": "New", "replace": "Old", "match": "contains", "case_sensitive": True}]})
    assert cleaned["city"].tolist() == ["Old York", "new york", "Boston"]


def test_find_replace_skips_numeric_columns():
    df = pd.DataFrame({"n": [1, 2]})
    _, changes = clean_dataframe(df, {"find_replace": [{"column": "n", "find": "1", "replace": "9"}]})
    assert changes["find_replace_n"]["status"] == "skipped"


@pytest.mark.parametrize("mode,expected", [("lower", "anna lee"), ("upper", "ANNA LEE"), ("title", "Anna Lee")])
def test_text_case(mode, expected):
    cleaned, _ = clean_dataframe(pd.DataFrame({"name": ["aNNa lEE"]}), {"text_case": {"name": mode}})
    assert cleaned.loc[0, "name"] == expected


def test_remove_rows_by_rule_numeric_and_text():
    df = pd.DataFrame({"qty": [1, -1, 3, -5], "ch": ["a", "b", "TEST", "c"]})
    cleaned, changes = clean_dataframe(df, {"drop_rows": [
        {"column": "qty", "op": "<", "value": 0},
        {"column": "ch", "op": "==", "value": "test"},
    ]})
    assert cleaned["qty"].tolist() == [1]
    assert changes["drop_rows_1"]["rows_removed"] == 2
    assert changes["drop_rows_1"]["examples"][0] == {"row": 3, "value": "-1"}


def test_remove_rows_with_empty_value_and_date_rule():
    df = pd.DataFrame({"d": ["2025-01-01", None, "2025-06-01"], "x": [1, 2, 3]})
    cleaned, _ = clean_dataframe(df, {"drop_rows": [{"column": "d", "op": "is_null"}, {"column": "d", "op": "<", "value": "2025-02-01"}]})
    assert cleaned["x"].tolist() == [3]


def test_bad_row_rule_value_is_a_clear_error():
    with pytest.raises(ValueError, match="not a number"):
        clean_dataframe(pd.DataFrame({"q": [1, 2]}), {"drop_rows": [{"column": "q", "op": "<", "value": "abc"}]})


def test_drop_and_rename_columns_use_original_names():
    df = pd.DataFrame({"a": [1, 1], "b": [2, 2], "c": [3, 3]})
    cleaned, changes = clean_dataframe(df, {
        "outlier_columns": ["b"], "drop_columns": ["b"], "rename_columns": {"a": "Alpha", "c": "Gamma"},
    })
    assert list(cleaned.columns) == ["Alpha", "Gamma"]
    assert changes["rename_columns"]["renamed"] == {"a": "Alpha", "c": "Gamma"}


def test_rename_to_an_existing_name_is_rejected():
    with pytest.raises(ValueError, match="more than once"):
        clean_dataframe(pd.DataFrame({"a": [1], "b": [2]}), {"rename_columns": {"a": "b"}})


def test_empty_new_name_is_rejected():
    with pytest.raises(ValueError, match="cannot be empty"):
        clean_dataframe(pd.DataFrame({"a": [1]}), {"rename_columns": {"a": "  "}})


def test_text_numbers_with_currency_symbols_convert():
    df = pd.DataFrame({"price": ["$1,200", "₹ 35.5", "abc", None]})
    cleaned, changes = clean_dataframe(df, {"type_conversions": {"price": "float"}})
    assert cleaned["price"].tolist()[:2] == [1200.0, 35.5]
    assert changes["type_price"]["became_empty"] == 1


def test_malformed_recipe_gets_a_clear_error():
    with pytest.raises(ValueError, match="wrong format"):
        clean_dataframe(pd.DataFrame({"a": [1]}), {"drop_columns": "a"})


def test_placeholder_then_convert_then_fill_pipeline():
    df = pd.DataFrame({"price": ["10", "-", "30", "N/A", "50"]})
    cleaned, _ = clean_dataframe(df, {
        "find_replace": [{"column": "price", "find": "-", "replace": ""}, {"column": "price", "find": "N/A", "replace": ""}],
        "type_conversions": {"price": "float"},
        "missing_values": {"price": {"strategy": "median"}},
    })
    assert cleaned["price"].tolist() == [10.0, 30.0, 30.0, 30.0, 50.0]
"""The exported script must give exactly the same result as the website."""
import pandas as pd
import pytest

from app.cleaning import clean_dataframe
from app.codegen import generate_cleaning_code

OPS_CASES = {
    "duplicates_only": {"remove_duplicates": True},
    "spelling_dates": {"remove_duplicates": True, "merge_case_columns": ["channel", "segment", "category"],
                       "standardize_columns": ["customer"], "date_columns": ["order_date"]},
    "missing_strategies": {"missing_values": {
        "discount_pct": {"strategy": "constant", "value": 0}, "unit_price": {"strategy": "median"},
        "quantity": {"strategy": "mode"}, "product": {"strategy": "unknown"}, "channel": {"strategy": "unknown"},
        "returned": {"strategy": "unknown"}, "customer_id": {"strategy": "median"}, "line_total": {"strategy": "skip"},
        "segment": {"strategy": "drop_rows"}}},
    "outliers": {"outlier_columns": ["quantity", "unit_price", "customer_id"]},
    "custom_steps": {
        "find_replace": [{"column": "channel", "find": "social", "replace": "Social Media", "match": "exact"}],
        "text_case": {"category": "upper"},
        "drop_rows": [{"column": "quantity", "op": "<", "value": 0}, {"column": "order_date", "op": "is_null"}],
        "type_conversions": {"returned": "string"},
        "drop_columns": ["product_id"],
        "rename_columns": {"line_total": "Revenue", "channel": "Sales channel"},
    },
    "everything": {
        "remove_duplicates": True, "merge_case_columns": ["channel", "segment"], "standardize_columns": ["customer"],
        "date_columns": ["order_date"], "find_replace": [{"column": "category", "find": "home", "replace": "Home", "match": "exact"}],
        "drop_rows": [{"column": "quantity", "op": "<", "value": 0}],
        "missing_values": {"discount_pct": {"strategy": "constant", "value": 0}, "unit_price": {"strategy": "mean"}},
        "outlier_columns": ["quantity"], "drop_columns": ["customer_id"], "rename_columns": {"order_id": "Order"},
    },
}


def _run(code, df):
    scope = {"df": df.copy()}
    exec(compile(code, "<generated>", "exec"), scope)
    return scope["df"]


@pytest.mark.parametrize("name", OPS_CASES)
def test_generated_script_matches_the_website(sample_df, name):
    ops = OPS_CASES[name]
    expected, _ = clean_dataframe(sample_df, ops)
    got = _run(generate_cleaning_code(sample_df, ops, include_load=False), sample_df)
    pd.testing.assert_frame_equal(got, expected, check_dtype=False)


def test_script_is_standalone_and_readable(sample_df):
    code = generate_cleaning_code(sample_df, OPS_CASES["everything"], "sales.xlsx")
    assert "pd.read_excel('sales.xlsx')" in code
    assert "# Remove rows where quantity < 0" in code
    assert code.count("import pandas as pd") == 1
    compile(code, "<generated>", "exec")


def test_no_steps_gives_a_valid_script(sample_df):
    code = generate_cleaning_code(sample_df, {})
    assert "no cleaning steps selected" in code
    compile(code, "<generated>", "exec")


def test_unknown_columns_are_left_out(sample_df):
    code = generate_cleaning_code(sample_df, {"drop_columns": ["nope"], "text_case": {"nope": "lower"}}, include_load=False)
    assert "nope" not in code
"""
app/codegen.py

Turns a set of cleaning options into a standalone Python (pandas) script.

The script calls the very same helper functions DataLens uses (their source
is copied in), so running it gives the same result as the website. tests/
checks this by running the generated code and comparing it with
clean_dataframe().
"""

import inspect
import re

from app import cleaning as C


def _helper_source(*functions):
    return "\n\n".join(inspect.getsource(f).rstrip() for f in functions)


def _py(value):
    return repr(value)


def _name(column):
    return _py(str(column))


def generate_cleaning_code(
    df,
    operations,
    source_name="your_file.csv",
    include_load=True,
):
    ops = operations or {}
    C._validate_operations(ops)

    columns = set(df.columns)

    def known(items):
        return [c for c in (items or []) if c in columns]

    steps = []        # readable lines of the script
    helpers = []      # helper functions that the steps need
    constants = []

    def add_helper(*functions):
        for function in functions:
            if function not in helpers:
                helpers.append(function)

    # ---- 1. find & replace ------------------------------------------------
    for rule in ops.get("find_replace") or []:
        column = rule.get("column")
        if column not in columns or str(rule.get("find", "")) == "":
            continue
        add_helper(C._find_replace_series)
        clean_rule = {
            "find": str(rule.get("find", "")),
            "replace": str(rule.get("replace", "")),
            "match": rule.get("match", "exact"),
            "case_sensitive": bool(rule.get("case_sensitive", False)),
        }
        what = "blank" if clean_rule["replace"] == "" else repr(clean_rule["replace"])
        steps.append(
            f"# Replace {clean_rule['find']!r} with {what} in {column}\n"
            f"df[{_name(column)}], _ = _find_replace_series(df[{_name(column)}], {_py(clean_rule)})"
        )

    # ---- 2. text case ---------------------------------------------------
    for column, mode in (ops.get("text_case") or {}).items():
        if column not in columns:
            continue
        add_helper(C._apply_text_case)
        steps.append(
            f"# Change {column} to {mode} case\n"
            f"if not pd.api.types.is_numeric_dtype(df[{_name(column)}]):\n"
            f"    df[{_name(column)}] = _apply_text_case(df[{_name(column)}], {_py(mode)})"
        )

    # ---- 3. tidy text --------------------------------------------------------
    for column in known(ops.get("standardize_columns")):
        add_helper(C._standardize_text)
        constants.append(f"COUNTRY_ALIASES = {_py(C.COUNTRY_ALIASES)}")
        steps.append(
            f"# Remove extra spaces and expand short country names in {column}\n"
            f"df[{_name(column)}] = df[{_name(column)}].apply(_standardize_text)"
        )

    # ---- 4. merge spellings -------------------------------------------------
    for column in known(ops.get("merge_case_columns")):
        add_helper(C._merge_case_variants)
        steps.append(
            f"# Make every spelling of the same value in {column} identical\n"
            f"if not pd.api.types.is_numeric_dtype(df[{_name(column)}]):\n"
            f"    df[{_name(column)}], _ = _merge_case_variants(df[{_name(column)}])"
        )

    # ---- 5. value mappings ----------------------------------------------------
    for column, mapping in (ops.get("standardize_values") or {}).items():
        if column in columns and isinstance(mapping, dict):
            steps.append(
                f"# Replace listed values in {column}\n"
                f"df[{_name(column)}] = df[{_name(column)}].replace({_py(mapping)})"
            )

    # ---- 6. dates ------------------------------------------------------------
    for column in known(ops.get("date_columns")):
        add_helper(C._infer_date_order, C._parse_dates)
        steps.append(
            f"# Write all dates in {column} as YYYY-MM-DD\n"
            f"df[{_name(column)}] = _parse_dates(df[{_name(column)}]).dt.strftime('%Y-%m-%d')"
        )

    # ---- 7. column types -----------------------------------------------------
    for column, target in (ops.get("type_conversions") or {}).items():
        if column not in columns:
            continue
        add_helper(C._infer_date_order, C._parse_dates, C._convert_type)
        steps.append(
            f"# Convert {column} to {target}\n"
            f"_convert_type(df, {_name(column)}, {_py(target)})"
        )

    # ---- 8. remove rows by rule -------------------------------------------------
    for rule in ops.get("drop_rows") or []:
        column = rule.get("column")
        if column not in columns:
            continue
        add_helper(C._rule_mask)
        op, value = rule.get("op", "=="), rule.get("value")
        steps.append(
            f"# Remove rows where {column} {op}"
            f"{'' if op in ('is_null', 'not_null') else ' ' + str(value)}\n"
            f"df = df.drop(index=df.index[_rule_mask(df[{_name(column)}], {_py(op)}, {_py(value)}).to_numpy()])"
        )

    # ---- 9. duplicates -------------------------------------------------------
    remove_duplicates = bool(ops.get("remove_duplicates"))
    if remove_duplicates:
        steps.append("# Remove rows that are exact copies of an earlier row\ndf = df.drop_duplicates()")

    # ---- 10. missing values --------------------------------------------------
    missing = ops.get("missing_values") or {}
    for column, config in missing.items():
        if column not in columns:
            continue
        add_helper(
            C._normalise_name, C._is_identifier,
            C._recommended_numeric_strategy, C._recommended_categorical_fill,
            C._get_strategy, C._fill_missing_values,
        )
        constants.append(f"ID_TOKENS = {_py(C.ID_TOKENS)}")
        strategy, value = C._get_strategy(config)
        note = {
            "mean": "the average", "median": "the median", "mode": "the most common value",
            "unknown": "'(Unknown)'", "constant": f"{value!r}", "drop_rows": "remove those rows",
            "skip": "keep them empty",
        }.get(strategy, strategy)
        steps.append(
            f"# Empty cells in {column}: {note}\n"
            f"_fill_missing_values(df, {_name(column)}, {_py(config)})"
        )

    if remove_duplicates and missing:
        steps.append(
            "# Filling cells can make two rows identical, so check for copies again\n"
            "df = df.drop_duplicates()"
        )

    # ---- 12. outliers --------------------------------------------------------
    for column in known(ops.get("outlier_columns")):
        add_helper(C._normalise_name, C._is_identifier, C._clip_outliers)
        constants.append(f"ID_TOKENS = {_py(C.ID_TOKENS)}")
        steps.append(
            f"# Cap extreme values in {column} (IQR rule)\n"
            f"_clip_outliers(df, {_name(column)})"
        )

    # ---- 13. drop columns ---------------------------------------------------
    to_drop = known(ops.get("drop_columns"))
    if to_drop:
        steps.append(f"# Remove columns you do not need\ndf = df.drop(columns={_py(to_drop)})")

    # ---- 14. rename columns -----------------------------------------------------
    renames = {
        str(old): str(new).strip()
        for old, new in (ops.get("rename_columns") or {}).items()
        if old in columns
    }
    if renames:
        steps.append(f"# Rename columns\ndf = df.rename(columns={_py(renames)})")

    # ---- put the script together -------------------------------------------------
    unique_constants = list(dict.fromkeys(constants))

    # helpers must come in dependency order, so sort by where they appear
    order = [
        C._normalise_name, C._is_identifier, C._standardize_text,
        C._infer_date_order, C._parse_dates, C._merge_case_variants,
        C._find_replace_series, C._apply_text_case, C._rule_mask,
        C._recommended_numeric_strategy, C._recommended_categorical_fill,
        C._get_strategy, C._fill_missing_values, C._clip_outliers,
        C._convert_type,
    ]
    helpers = [f for f in order if f in helpers]

    lines = [
        '"""',
        "Cleaning steps exported from DataLens.",
        "",
        "The helper functions below are the same ones DataLens uses, so this",
        "script gives the same result as the website. The steps you chose come",
        "after them.",
        '"""',
        "",
        "import re",
        "",
        "import numpy as np",
        "import pandas as pd",
        "",
    ]

    if unique_constants:
        lines += unique_constants + [""]

    if helpers:
        lines += [
            "# ----------------------------------------------------------------",
            "# Helper functions",
            "# ----------------------------------------------------------------",
            "",
            _helper_source(*helpers),
            "",
        ]

    lines += [
        "# ----------------------------------------------------------------",
        "# Your cleaning steps",
        "# ----------------------------------------------------------------",
        "",
    ]

    if include_load:
        is_excel = str(source_name).lower().endswith((".xlsx", ".xlsm"))
        reader = "read_excel" if is_excel else "read_csv"
        lines += [f"df = pd.{reader}({_py(str(source_name))})", ""]

    if steps:
        lines += ["\n\n".join(steps), ""]
    else:
        lines += ["# (no cleaning steps selected)", ""]

    if include_load:
        lines += ['df.to_csv("datalens_cleaned.csv", index=False)', 'print(f"Done: {len(df)} rows, {len(df.columns)} columns")', ""]

    return re.sub(r"\n{4,}", "\n\n\n", "\n".join(lines))
"""
app/trust.py

Builds a "cleaning report" that lets a user verify what cleaning did:

  * rows, missing values and duplicates before / after
  * totals of numeric columns before / after (so no money disappears silently)
  * a change log with real before -> after examples and CSV row numbers
  * warnings for assumptions made (for example mixed date formats)
"""

import re
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.cleaning import _infer_date_order, _is_identifier

MAX_EXAMPLES = 3
MAX_CHECK_COLUMNS = 10
FLAG_CHANGE_PCT = 1.0

_PREFIXES = [
    ("standardize_values_", "Replaced values"),
    ("find_replace_", "Find & replace"),
    ("text_case_", "Text case changed"),
    ("merge_case_", "Merged spellings"),
    ("standardize_", "Tidied text"),
    ("missing_", "Missing values"),
    ("date_", "Dates converted"),
    ("type_", "Type changed"),
    ("outliers_", "Outliers capped"),
]


def _display(value):
    if value is None:
        return "(empty)"
    try:
        if pd.isna(value):
            return "(empty)"
    except (TypeError, ValueError):
        pass
    text = str(value)
    return "(empty)" if text == "" else text[:40]


def _examples(original, cleaned, column):
    """Real before -> after cells, matched by row index."""
    if column not in original.columns or column not in cleaned.columns:
        return 0, []

    index = cleaned.index.intersection(original.index)
    if len(index) == 0:
        return 0, []

    before = original.loc[index, column]
    after = cleaned.loc[index, column]

    before_text = before.astype("string").fillna("")
    after_text = after.astype("string").fillna("")
    changed = (before_text != after_text).to_numpy()

    count = int(changed.sum())
    examples = []

    for position in np.flatnonzero(changed)[:MAX_EXAMPLES]:
        row_label = index[position]
        examples.append({
            "row": int(row_label) + 2,          # CSV row number (header is row 1)
            "before": _display(before.iloc[position]),
            "after": _display(after.iloc[position]),
        })

    return count, examples


def _describe(change_key, detail):
    """Plain-English line for one entry of `changes` from clean_dataframe."""
    if not isinstance(detail, dict):
        return str(detail)

    if "strategy" in detail:
        strategy = detail["strategy"]
        if strategy == "skipped":
            return f"Not changed. {detail.get('reason', '')} ({detail.get('unfilled', 0)} empty cells kept)."
        if strategy == "drop_rows":
            return f"Removed {detail.get('rows_removed', 0)} rows that had no value."
        value = detail.get("fill_value")
        try:
            value = round(float(value), 4)
        except (TypeError, ValueError):
            pass
        return f"Filled {detail.get('filled', 0)} empty cells using {strategy} ({value})."

    if "converted" in detail and "format" in detail:
        return (
            f"{detail['converted']} dates converted to {detail['format']}; "
            f"{detail.get('invalid_or_missing', 0)} could not be read and were left empty."
        )

    if "values_merged" in detail:
        return (
            f"{detail['values_merged']} values were rewritten so the same thing is spelled one way "
            f"({detail.get('groups_merged', 0)} groups of spellings merged, using the most common spelling)."
        )

    if "values_normalized" in detail:
        return f"{detail['values_normalized']} values tidied (spaces, spelling aliases)."

    if "mappings_applied" in detail:
        return f"{detail['mappings_applied']} value replacements applied."

    if "replacements" in detail:
        return (
            f"{detail['replacements']} cells changed by "
            f"{detail.get('rules', 1)} find-and-replace rule(s)."
        )

    if "case" in detail:
        return f"Text changed to {detail['case']} case ({detail.get('values_changed', 0)} values)."

    if "converted_to" in detail:
        text = f"Converted to {detail['converted_to']}."
        if detail.get("became_empty"):
            text += (
                f" {detail['became_empty']} values could not be read as "
                f"{detail['converted_to']} and became empty."
            )
        return text

    if "clipped" in detail:
        return (
            f"{detail['clipped']} values capped to the range "
            f"{detail['lower_bound']:.2f} to {detail['upper_bound']:.2f}."
        )

    if "reason" in detail:
        return f"Skipped. {detail['reason']}"

    return ", ".join(f"{k}: {v}" for k, v in detail.items())


def _change_log(original, cleaned, changes):
    log = []

    removed = changes.get("duplicates_removed")
    if removed is not None:
        removed_rows = original.index.difference(cleaned.index)
        log.append({
            "column": "(whole rows)",
            "action": "Duplicate rows removed",
            "detail": (
                f"{removed} rows that were exact copies of an earlier row were removed."
                if removed else "No duplicate rows found."
            ),
            "cells_changed": 0,
            "examples": [
                {"row": int(i) + 2, "before": "exact copy of an earlier row", "after": "removed"}
                for i in removed_rows[:MAX_EXAMPLES]
            ],
        })

    for key, detail in changes.items():
        if key == "duplicates_removed":
            continue

        if key == "drop_columns":
            names = detail.get("dropped", [])
            log.append({
                "column": ", ".join(map(str, names)),
                "action": "Columns removed",
                "detail": f"Removed {len(names)} column(s) you did not need.",
                "cells_changed": 0,
                "examples": [],
            })
            continue

        if key == "rename_columns":
            renamed = detail.get("renamed", {})
            log.append({
                "column": ", ".join(map(str, renamed)),
                "action": "Columns renamed",
                "detail": "; ".join(f"{old} became {new}" for old, new in renamed.items()),
                "cells_changed": 0,
                "examples": [],
            })
            continue

        if key.startswith("drop_rows_") and isinstance(detail, dict):
            column = detail.get("column", "")
            log.append({
                "column": column,
                "action": "Rows removed",
                "detail": f"Removed {detail.get('rows_removed', 0)} rows where {detail.get('rule', '')}.",
                "cells_changed": 0,
                "examples": [
                    {"row": e["row"], "before": f"{column} = {e['value']}", "after": "row removed"}
                    for e in detail.get("examples", [])
                ],
            })
            continue

        for prefix, action in _PREFIXES:
            if key.startswith(prefix):
                column = key[len(prefix):]
                break
        else:
            column, action = key, "Change"

        cells, examples = _examples(original, cleaned, column)

        log.append({
            "column": column,
            "action": action,
            "detail": _describe(key, detail),
            "cells_changed": cells,
            "examples": examples,
        })

    return log


def _total_checks(original, cleaned, renames=None):
    checks = []
    renames = renames or {}

    for column in original.columns:
        after_name = renames.get(column, column)
        if after_name not in cleaned.columns:
            continue
        if not pd.api.types.is_numeric_dtype(original[column]):
            continue
        if pd.api.types.is_bool_dtype(original[column]):
            continue
        if _is_identifier(column, original[column]):
            continue

        before = pd.to_numeric(original[column], errors="coerce")
        after = pd.to_numeric(cleaned[after_name], errors="coerce")

        if before.notna().sum() == 0:
            continue

        before_sum, after_sum = float(before.sum()), float(after.sum())
        change_pct = (
            (after_sum - before_sum) / abs(before_sum) * 100
            if before_sum else (0.0 if after_sum == 0 else 100.0)
        )

        flagged = abs(change_pct) >= FLAG_CHANGE_PCT

        checks.append({
            "column": str(column) if after_name == column else f"{column} (now {after_name})",
            "before_total": round(before_sum, 2),
            "after_total": round(after_sum, 2),
            "change_pct": round(change_pct, 2),
            "before_average": round(float(before.mean()), 2),
            "after_average": round(float(after.mean()), 2),
            "flag": flagged,
            "note": (
                "Total changed by more than 1%. Expected when rows are removed "
                "or empty cells are filled. Check it matches what you chose."
                if flagged else "Total is unchanged or almost unchanged."
            ),
        })

        if len(checks) >= MAX_CHECK_COLUMNS:
            break

    return checks


def _date_assumptions(original, operations):
    """Warn about mixed or ambiguous slash dates."""
    notes = []
    requested = set((operations or {}).get("date_columns", []) or [])

    for column in original.columns:
        name = str(column).lower()
        is_candidate = (
            column in requested
            or any(w in name for w in ("date", "time", "timestamp"))
        )
        if not is_candidate or pd.api.types.is_numeric_dtype(original[column]):
            continue

        values = original[column].dropna().astype(str)
        if values.empty:
            continue

        day_first = month_first = ambiguous = 0
        for value in values.head(5000):
            match = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", value)
            if not match:
                continue
            first, second = int(match.group(1)), int(match.group(2))
            if first > 12 and second <= 12:
                day_first += 1
            elif second > 12 and first <= 12:
                month_first += 1
            elif first <= 12 and second <= 12 and first != second:
                ambiguous += 1

        if day_first and month_first:
            read_as = "DD/MM" if _infer_date_order(original[column]) else "MM/DD"
            notes.append({
                "level": "warning",
                "column": str(column),
                "message": (
                    f"Two date styles were mixed in this column "
                    f"({month_first} rows are clearly MM/DD, {day_first} rows are clearly DD/MM). "
                    f"{ambiguous} other dates are ambiguous (for example 04/05/2025) and were read as {read_as}. "
                    "Please check these if exact dates matter."
                ),
            })
        elif ambiguous and (day_first or month_first):
            style = "DD/MM" if day_first else "MM/DD"
            notes.append({
                "level": "info",
                "column": str(column),
                "message": (
                    f"Some dates in this column are unambiguous {style}, so "
                    f"{ambiguous} ambiguous dates were read as {style} too."
                ),
            })
        elif ambiguous and not (day_first or month_first):
            notes.append({
                "level": "warning",
                "column": str(column),
                "message": (
                    f"{ambiguous} dates could be read as either DD/MM or MM/DD "
                    "and nothing in the column settles it. Confirm the format "
                    "before relying on monthly or daily trends."
                ),
            })

    return notes


def build_cleaning_report(original, cleaned, changes, operations=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        assumptions = _date_assumptions(original, operations)

        for key, detail in changes.items():
            if (
                key.startswith("missing_")
                and isinstance(detail, dict)
                and detail.get("strategy") == "unknown"
            ):
                assumptions.append({
                    "level": "info",
                    "column": key[len("missing_"):],
                    "message": "Empty cells were labelled '(Unknown)' rather than guessed.",
                })

        report = {
            "rows": {
                "before": int(len(original)),
                "after": int(len(cleaned)),
                "removed": int(len(original) - len(cleaned)),
            },
            "missing_cells": {
                "before": int(original.isna().sum().sum()),
                "after": int(cleaned.isna().sum().sum()),
            },
            "duplicate_rows": {
                "before": int(original.duplicated().sum()),
                "after": int(cleaned.duplicated().sum()),
            },
            "column_checks": _total_checks(
                original, cleaned, (operations or {}).get("rename_columns")
            ),
            "change_log": _change_log(original, cleaned, changes),
            "assumptions": assumptions,
            "applied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    return report
"""
app/exporter.py

Exports the cleaned data:

  * Excel (.xlsx) with four sheets: the data, a cleaning log, a totals check
    and an "About" sheet that says where the file came from
  * CSV (UTF-8 with BOM so Excel opens accents correctly)

Text that starts with = + - or @ could run as a formula when the file is
opened in Excel or Google Sheets. In the workbook those cells are stored as
plain text, and in the CSV they get a leading apostrophe.
"""

import io
import re
from datetime import datetime

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="EEEEFF")
HEADER_FONT = Font(bold=True, color="3D3B52")
MAX_WIDTH = 42
_NUMBER_LIKE = re.compile(r"^[+-]?[\d.,]+(e[+-]?\d+)?%?$", re.I)


# --------------------------------------------------
# helpers
# --------------------------------------------------

def _safe_text(value):
    """CSV: neutralise values that a spreadsheet would run as a formula."""
    if not isinstance(value, str) or not value:
        return value
    first = value[0]
    if first in ("=", "@"):
        return "'" + value
    if first in ("+", "-") and not _NUMBER_LIKE.match(value.strip()):
        return "'" + value
    return value


def _style_sheet(ws, widths=True, freeze=True):
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")

    if freeze:
        ws.freeze_panes = "A2"

    if widths:
        for column in ws.columns:
            letter = get_column_letter(column[0].column)
            longest = max(
                (len(str(cell.value)) for cell in column[:200] if cell.value is not None),
                default=8,
            )
            ws.column_dimensions[letter].width = min(max(longest + 2, 10), MAX_WIDTH)

    # strings that start with "=" must stay text
    for row in ws.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                cell.data_type = "s"


def _examples_text(examples):
    return "; ".join(
        f"row {e.get('row')}: {e.get('before')} -> {e.get('after')}"
        for e in (examples or [])
    )


# --------------------------------------------------
# public
# --------------------------------------------------

def build_csv_bytes(df):
    safe = df.copy()
    for column in safe.columns:
        if safe[column].dtype == object or pd.api.types.is_string_dtype(safe[column]):
            safe[column] = safe[column].map(_safe_text)
    return safe.to_csv(index=False).encode("utf-8-sig")


def build_excel_bytes(df, source_name, using_cleaned, report=None, quality_before=None, quality_after=None):
    """Workbook bytes. `report` is the cleaning report (or None)."""
    data_sheet = "Cleaned data" if using_cleaned else "Data"

    about = [
        ("Source file", source_name),
        ("Data in this workbook", "Cleaned data" if using_cleaned else "Uploaded data (cleaning not applied)"),
        ("Rows", len(df)),
        ("Columns", len(df.columns)),
        ("Exported", datetime.now().strftime("%d %b %Y, %H:%M")),
    ]

    if report:
        about += [
            ("Rows before cleaning", report["rows"]["before"]),
            ("Rows removed", report["rows"]["removed"]),
            ("Empty cells before / after", f"{report['missing_cells']['before']} / {report['missing_cells']['after']}"),
            ("Duplicate rows before / after", f"{report['duplicate_rows']['before']} / {report['duplicate_rows']['after']}"),
        ]
        if quality_before is not None and quality_after is not None:
            about.append(("Quality score before / after", f"{quality_before:.1f} / {quality_after:.1f}"))
        about.append(("Cleaned at", report.get("applied_at")))

    about.append(("Note", "Your original upload is never changed. See the other sheets for what was done."))

    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=data_sheet, index=False)

        if report:
            log_rows = [
                {
                    "Step": number,
                    "Column": entry.get("column"),
                    "What was done": entry.get("action"),
                    "Details": entry.get("detail"),
                    "Cells changed": entry.get("cells_changed"),
                    "Examples (CSV row: before -> after)": _examples_text(entry.get("examples")),
                }
                for number, entry in enumerate(report.get("change_log") or [], start=1)
            ]
            pd.DataFrame(log_rows or [{"Step": "", "Column": "", "What was done": "No changes were made",
                                        "Details": "", "Cells changed": "", "Examples (CSV row: before -> after)": ""}]
                         ).to_excel(writer, sheet_name="Cleaning log", index=False)

            checks = [
                {
                    "Column": c.get("column"),
                    "Total before": c.get("before_total"),
                    "Total after": c.get("after_total"),
                    "Change %": c.get("change_pct"),
                    "Average before": c.get("before_average"),
                    "Average after": c.get("after_average"),
                    "Needs a look": "Yes" if c.get("flag") else "No",
                }
                for c in report.get("column_checks") or []
            ]
            if checks:
                pd.DataFrame(checks).to_excel(writer, sheet_name="Totals check", index=False)

            warnings = report.get("assumptions") or []
            if warnings:
                pd.DataFrame(
                    [{"Level": a.get("level"), "Column": a.get("column"), "Please check": a.get("message")} for a in warnings]
                ).to_excel(writer, sheet_name="Assumptions", index=False)

        pd.DataFrame(about, columns=["Item", "Value"]).to_excel(writer, sheet_name="About", index=False)

        for ws in writer.book.worksheets:
            _style_sheet(ws, freeze=True)

        for name in ("Cleaning log", "Assumptions"):
            if name in writer.book.sheetnames:
                for row in writer.book[name].iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                for letter in ("D", "F") if name == "Cleaning log" else ("C",):
                    writer.book[name].column_dimensions[letter].width = 60

    return buffer.getvalue()
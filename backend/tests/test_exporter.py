import io

import pandas as pd
from openpyxl import load_workbook

from app.exporter import build_csv_bytes, build_excel_bytes
from app.trust import build_cleaning_report
from report_fixtures import cleaned_sample


def test_excel_with_cleaning_report_has_four_useful_sheets(sample_df):
    cleaned, changes, ops = cleaned_sample(sample_df)
    report = build_cleaning_report(sample_df, cleaned, changes, ops)
    book = load_workbook(io.BytesIO(build_excel_bytes(cleaned, "sales.csv", True, report, 78.9, 92.7)))

    assert book.sheetnames[0] == "Cleaned data"
    assert {"Cleaning log", "Totals check", "About"} <= set(book.sheetnames)

    data = book["Cleaned data"]
    assert data.max_row == len(cleaned) + 1 and data.max_column == len(cleaned.columns)
    assert data.freeze_panes == "A2"

    about = {row[0].value: row[1].value for row in book["About"].iter_rows(min_row=2)}
    assert about["Source file"] == "sales.csv"
    assert about["Rows before cleaning"] == len(sample_df)
    assert about["Quality score before / after"] == "78.9 / 92.7"

    log = book["Cleaning log"]
    assert log.max_row - 1 == len(report["change_log"])


def test_excel_without_cleaning_is_labelled_as_uploaded_data(sample_df):
    book = load_workbook(io.BytesIO(build_excel_bytes(sample_df, "sales.csv", False)))
    assert book.sheetnames == ["Data", "About"]
    about = {row[0].value: row[1].value for row in book["About"].iter_rows(min_row=2)}
    assert "not applied" in about["Data in this workbook"]


def test_text_starting_with_equals_stays_text_in_excel():
    df = pd.DataFrame({"note": ["=1+1", "=HYPERLINK(\"http://x\")", "fine"]})
    book = load_workbook(io.BytesIO(build_excel_bytes(df, "x.csv", False)))
    cells = [book["Data"].cell(row=r, column=1) for r in (2, 3, 4)]
    assert all(c.data_type == "s" for c in cells) and cells[0].value == "=1+1"


def test_numbers_and_blanks_survive_excel(sample_df):
    book = load_workbook(io.BytesIO(build_excel_bytes(sample_df, "x.csv", False)))
    sheet = book["Data"]
    headers = [c.value for c in sheet[1]]
    price_col = headers.index("unit_price") + 1
    values = [sheet.cell(row=r, column=price_col).value for r in range(2, 40)]
    assert any(isinstance(v, (int, float)) for v in values)
    assert any(v is None for v in values) or sample_df["unit_price"].head(38).notna().all()


def test_csv_has_bom_accents_and_formula_protection():
    df = pd.DataFrame({"name": ["José", "=cmd|' /C calc'!A0", "@SUM(1)", "-abc", "-5", "+12.5", "plain"], "n": range(7)})
    raw = build_csv_bytes(df)
    assert raw.startswith(b"\xef\xbb\xbf")
    back = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    names = back["name"].tolist()
    assert names[0] == "José"
    assert names[1].startswith("'=") and names[2].startswith("'@") and names[3] == "'-abc"
    assert names[4] == "-5" or names[4] == -5 or str(names[4]) == "-5"
    assert names[6] == "plain"
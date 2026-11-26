"""API level checks: upload, sample data, cleaning and the cleaning report."""
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

OPS = {
    "remove_duplicates": True,
    "merge_case_columns": ["channel", "segment", "category"],
    "standardize_columns": ["customer"],
    "date_columns": ["order_date"],
    "missing_values": {"discount_pct": {"strategy": "constant", "value": 0}},
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def sample(client):
    response = client.post("/api/v1/datasets/sample")
    assert response.status_code == 200
    return response.json()


def test_sample_dataset_loads_with_a_realistic_report(sample):
    assert sample["profile"]["overview"]["total_rows"] >= 200
    assert sample["quality_report"]["quality_score"] < 90      # it is messy on purpose
    assert sample["load_info"]["notes"]


def test_cleaning_preview_does_not_change_anything(client, sample):
    did = sample["dataset_id"]
    preview = client.post(f"/api/v1/datasets/{did}/clean/preview", json=OPS).json()
    assert preview["after"]["rows"] < preview["before"]["rows"]
    assert client.get(f"/api/v1/datasets/{did}/clean/report").json() == {"available": False}


def test_apply_cleaning_then_read_the_report(client, sample):
    did = sample["dataset_id"]
    assert client.post(f"/api/v1/datasets/{did}/clean/apply", json=OPS).status_code == 200

    report = client.get(f"/api/v1/datasets/{did}/clean/report").json()
    assert report["available"] is True
    assert report["rows"]["after"] == report["rows"]["before"] - report["rows"]["removed"]
    assert report["duplicate_rows"]["after"] == 0
    assert report["change_log"] and report["assumptions"]


def test_semicolon_csv_upload(client):
    raw = "name;price\nAnna;5,5\nBen;7,1\n".encode()
    response = client.post("/api/v1/datasets/upload", files={"file": ("a.csv", raw, "text/csv")})
    assert response.status_code == 200
    assert response.json()["profile"]["overview"]["total_columns"] == 2


def test_excel_upload(client):
    buffer = io.BytesIO()
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_excel(buffer, index=False, engine="openpyxl")
    response = client.post("/api/v1/datasets/upload", files={"file": ("a.xlsx", buffer.getvalue(), "application/octet-stream")})
    assert response.status_code == 200 and response.json()["load_info"]["format"] == "excel"


@pytest.mark.parametrize("name,content,status", [
    ("a.pdf", b"x", 415),
    ("a.csv", b"", 400),
    ("a.csv", b"a,b\n", 400),
])
def test_bad_uploads_get_clear_errors(client, name, content, status):
    response = client.post("/api/v1/datasets/upload", files={"file": (name, content, "text/csv")})
    assert response.status_code == status and response.json()["detail"]


def test_unknown_dataset_is_404(client):
    assert client.get("/api/v1/datasets/nope/clean/report").status_code == 404


def test_export_python_code_endpoint(client, sample):
    did = sample["dataset_id"]
    response = client.post(f"/api/v1/datasets/{did}/clean/code", json={"remove_duplicates": True, "drop_columns": ["product_id"]})
    assert response.status_code == 200
    code = response.json()["code"]
    assert "pd.read_csv('datalens_sample_sales.csv')" in code and "drop_duplicates" in code
    compile(code, "<exported>", "exec")


def test_new_steps_flow_through_preview_and_report(client, sample):
    did = sample["dataset_id"]
    ops = {"drop_rows": [{"column": "quantity", "op": "<", "value": 0}],
           "rename_columns": {"line_total": "Revenue"}, "drop_columns": ["product_id"]}
    preview = client.post(f"/api/v1/datasets/{did}/clean/preview", json=ops).json()
    assert preview["after"]["rows"] < preview["before"]["rows"]
    assert preview["changes"]["rename_columns"]["renamed"] == {"line_total": "Revenue"}

    assert client.post(f"/api/v1/datasets/{did}/clean/apply", json=ops).status_code == 200
    report = client.get(f"/api/v1/datasets/{did}/clean/report").json()
    actions = {entry["action"] for entry in report["change_log"]}
    assert {"Rows removed", "Columns removed", "Columns renamed"} <= actions
    assert any("line_total (now Revenue)" in c["column"] for c in report["column_checks"])


def test_bad_recipe_is_a_422(client, sample):
    did = sample["dataset_id"]
    bad = client.post(f"/api/v1/datasets/{did}/clean/preview", json={"rename_columns": {"order_id": "channel"}})
    assert bad.status_code == 422 and "more than once" in bad.json()["detail"]


def test_start_over_removes_cleaning(client, sample):
    did = sample["dataset_id"]
    client.post(f"/api/v1/datasets/{did}/clean/apply", json={"remove_duplicates": True})
    assert client.get(f"/api/v1/datasets/{did}/clean/report").json()["available"] is True
    assert client.delete(f"/api/v1/datasets/{did}/clean").status_code == 200
    assert client.get(f"/api/v1/datasets/{did}/clean/report").json() == {"available": False}
    assert client.get(f"/api/v1/datasets/{did}/dashboard").json()["using_cleaned"] is False


def test_export_excel_and_csv(client, sample):
    did = sample["dataset_id"]
    client.post(f"/api/v1/datasets/{did}/clean/apply", json=OPS)

    excel = client.get(f"/api/v1/datasets/{did}/export?format=xlsx")
    assert excel.status_code == 200 and "spreadsheetml" in excel.headers["content-type"]
    assert "-cleaned.xlsx" in excel.headers["content-disposition"]
    from openpyxl import load_workbook
    book = load_workbook(io.BytesIO(excel.content))
    assert "Cleaning log" in book.sheetnames

    csv = client.get(f"/api/v1/datasets/{did}/export?format=csv")
    assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbf")
    assert len(pd.read_csv(io.BytesIO(csv.content), encoding="utf-8-sig")) == book["Cleaned data"].max_row - 1


def test_export_rejects_unknown_format_and_dataset(client, sample):
    assert client.get(f"/api/v1/datasets/{sample['dataset_id']}/export?format=pdf").status_code == 400
    assert client.get("/api/v1/datasets/nope/export").status_code == 404


def test_pdf_report_endpoint(client, sample):
    did = sample["dataset_id"]
    client.post(f"/api/v1/datasets/{did}/clean/apply", json=OPS)
    response = client.get(f"/api/v1/datasets/{did}/report/pdf")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "datalens-report.pdf" in response.headers["content-disposition"]

    from pypdf import PdfReader
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    assert "Data cleaning report" in text and "Did any totals change?" in text


def test_pdf_report_without_cleaning(client):
    fresh = client.post("/api/v1/datasets/sample").json()["dataset_id"]
    response = client.get(f"/api/v1/datasets/{fresh}/report/pdf")
    assert response.status_code == 200
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    assert "No cleaning was applied" in text
import io
import threading

import pytest
from pypdf import PdfReader

from app.report_charts import render_chart_png
from app.report_pdf import build_pdf_report, format_number, usable_charts
from app.quality import check_data_quality
from app.trust import build_cleaning_report
from report_fixtures import cleaned_sample, dashboard_payload


@pytest.fixture(scope="module")
def context(sample_df):
    cleaned, changes, ops = cleaned_sample(sample_df)
    return {
        "filename": "sales.csv", "using_cleaned": True, "dashboard": dashboard_payload(sample_df),
        "cleaning_report": build_cleaning_report(sample_df, cleaned, changes, ops),
        "quality_before": check_data_quality(sample_df, non_negative_columns=["quantity"]),
        "quality_after": check_data_quality(cleaned, non_negative_columns=["quantity"]),
    }


def _text(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages), "\n".join(page.extract_text() for page in reader.pages)


def test_report_has_every_section_and_chart(context):
    pdf = build_pdf_report(context)
    pages, text = _text(pdf)
    assert pdf.startswith(b"%PDF") and pages >= 3
    for heading in ("At a glance", "Data cleaning report", "Did any totals change?", "What was changed",
                    "Key insights", "Charts", "How your columns were read"):
        assert heading in text
    for chart in usable_charts(context["dashboard"]["charts"]):
        assert chart["title"] in text, chart["title"]


def test_every_ai_generated_chart_is_included_but_id_charts_are_not(context):
    _, text = _text(build_pdf_report(context))
    assert "10 charts built from your data" in text
    assert "Orders by customer_id" not in text


def test_before_after_numbers_and_quality_score_are_shown(context):
    _, text = _text(build_pdf_report(context))
    report = context["cleaning_report"]
    assert str(report["rows"]["before"]) in text and str(report["rows"]["after"]) in text
    assert "Quality score" in text


def test_insight_shows_confidence_and_how_it_was_calculated(context):
    _, text = _text(build_pdf_report(context))
    assert "High confidence" in text and "Low confidence" in text
    assert "How this was calculated" in text


def test_ai_text_is_labelled(context):
    _, text = _text(build_pdf_report(context))
    assert "AI summary" in text and "Written by AI" in text


def test_ai_text_is_left_out_when_ai_did_not_write_it(context):
    dashboard = {**context["dashboard"], "dashboard_ai": {"ai_generated": False, "summary": "generic text", "insights": []}}
    _, text = _text(build_pdf_report({**context, "dashboard": dashboard}))
    assert "generic text" not in text and "AI summary" not in text


def test_report_without_cleaning_lists_the_problems_found(sample_df, context):
    ctx = {**context, "using_cleaned": False, "cleaning_report": None, "quality_after": None}
    _, text = _text(build_pdf_report(ctx))
    assert "No cleaning was applied" in text and "Duplicate rows" in text


def test_report_with_no_charts_still_builds(context):
    ctx = {**context, "dashboard": {**context["dashboard"], "charts": [], "insights": []}}
    _, text = _text(build_pdf_report(ctx))
    assert "did not have enough useful columns" in text


def test_one_broken_chart_does_not_break_the_report(context):
    broken = {"id": "bad", "chart_type": "scatter", "title": "Broken chart", "size": "medium",
              "data": [{"x": "a", "y": "b"}, {"x": "c", "y": "d"}]}
    dashboard = {**context["dashboard"], "charts": context["dashboard"]["charts"][:2] + [broken]}
    _, text = _text(build_pdf_report({**context, "dashboard": dashboard}))
    assert "Broken chart" in text and "could not be drawn" in text


def test_special_characters_are_safe(context):
    nasty = {"id": "n", "chart_type": "bar", "title": "Sales <b>& tax</b> in ₹ for “café”", "size": "medium",
             "data": [{"category": "<x>&", "value": 3}, {"category": "é→ü", "value": 5}], "insight": "5 > 3 & done"}
    dashboard = {**context["dashboard"], "charts": [nasty], "insights": [{"type": "info", "title": "A&B <i>", "message": "x < y & z", "recommendation": "do <this>"}]}
    pdf = build_pdf_report({**context, "filename": "my <file> & co.csv", "dashboard": dashboard})
    _, text = _text(pdf)
    assert "₹" in text and "café" in text and "x < y & z" in text


@pytest.mark.parametrize("value,expected", [
    (999, "999"), (1234.5, "1,234.5"), (123456, "1,23,456"), (1234567.5, "12,34,567.5"),
    (-1500.256, "-1,500.26"), (0, "0"), (None, "-"),
])
def test_indian_number_grouping(value, expected):
    assert format_number(value) == expected


@pytest.mark.parametrize("index", range(10))
def test_every_chart_type_renders_a_png(context, index):
    chart = context["dashboard"]["charts"][index]
    png = render_chart_png(chart, 3.4, 2.5, dpi=80)
    assert png.startswith(b"\x89PNG")


def test_charts_can_be_drawn_from_several_threads_at_once(context):
    errors = []

    def work():
        try:
            for chart in context["dashboard"]["charts"][:5]:
                render_chart_png(chart, 3.4, 2.5, dpi=60)
        except Exception as error:   # pragma: no cover
            errors.append(error)

    threads = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []


def test_long_label_and_many_points_do_not_break_charts():
    many = {"id": "m", "chart_type": "line", "title": "t", "data": [{"period": f"2025-{i:03d}", "value": i * 1.5} for i in range(400)]}
    long_labels = {"id": "l", "chart_type": "bar", "title": "t", "data": [{"category": "x" * 90 + str(i), "value": i} for i in range(25)]}
    assert render_chart_png(many, 7, 2.7, dpi=60).startswith(b"\x89PNG")
    assert render_chart_png(long_labels, 3.4, 2.5, dpi=60).startswith(b"\x89PNG")
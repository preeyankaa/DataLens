"""
app/report_pdf.py

Builds the downloadable PDF analytics report:

  1. At a glance        key numbers and KPIs
  2. Data cleaning      before / after, assumptions, totals check, change log
  3. Key insights       with confidence and how each was calculated
  4. Charts             every dashboard chart, with its finding
  5. How columns were read

Every number comes from code. Text written by AI is labelled as such.
"""

import io
import os
import re
from datetime import datetime
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.report_charts import render_chart_png

INDIGO = colors.HexColor("#6366f1")
INK = colors.HexColor("#25243a")
BODY = colors.HexColor("#3d3b52")
MUTED = colors.HexColor("#8d8aa0")
LINE = colors.HexColor("#e6e4ef")
SOFT = colors.HexColor("#f6f6fd")

TAGS = {
    "risk": ("Watch out", colors.HexColor("#f97316")),
    "opportunity": ("Opportunity", colors.HexColor("#10b981")),
    "info": ("Good to know", colors.HexColor("#6366f1")),
    "ai": ("AI comment", colors.HexColor("#8b5cf6")),
}
CONFIDENCE = {
    "high": ("High confidence", colors.HexColor("#0f8a55")),
    "medium": ("Medium confidence", colors.HexColor("#a86b00")),
    "low": ("Low confidence", colors.HexColor("#cc2b55")),
}

PAGE_W, PAGE_H = A4
MARGIN = 1.6 * cm
CONTENT_W = PAGE_W - 2 * MARGIN
GAP = 0.4 * cm
HALF_W = (CONTENT_W - GAP) / 2

_FONTS_READY = False


# --------------------------------------------------
# fonts and styles
# --------------------------------------------------

def _register_fonts():
    """DejaVu ships with matplotlib, so no font files are needed."""
    global _FONTS_READY
    if _FONTS_READY:
        return

    folder = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    for name, file in (
        ("DV", "DejaVuSans.ttf"),
        ("DV-B", "DejaVuSans-Bold.ttf"),
        ("DV-I", "DejaVuSans-Oblique.ttf"),
        ("DV-BI", "DejaVuSans-BoldOblique.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, os.path.join(folder, file)))

    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
    _FONTS_READY = True


def _styles():
    def style(name, **kw):
        base = dict(fontName="DV", fontSize=8.5, leading=12, textColor=BODY, alignment=TA_LEFT)
        base.update(kw)
        return ParagraphStyle(name, **base)

    return {
        "title": style("title", fontName="DV-B", fontSize=21, leading=26, textColor=INK),
        "meta": style("meta", fontSize=8.5, textColor=MUTED, leading=12),
        "h1": style("h1", fontName="DV-B", fontSize=13.5, leading=18, textColor=INK, spaceBefore=14, spaceAfter=6, keepWithNext=1),
        "h2": style("h2", fontName="DV-B", fontSize=10, leading=14, textColor=INK, spaceBefore=8, spaceAfter=3, keepWithNext=1),
        "sub": style("sub", fontSize=7.5, leading=10.5, textColor=MUTED, spaceAfter=5, keepWithNext=1),
        "body": style("body"),
        "small": style("small", fontSize=7.5, leading=10.5, textColor=MUTED),
        "note": style("note", fontName="DV-I", fontSize=7.5, leading=10.5, textColor=MUTED),
        "cell": style("cell", fontSize=8, leading=11),
        "cellb": style("cellb", fontName="DV-B", fontSize=8, leading=11, textColor=INK),
        "head": style("head", fontName="DV-B", fontSize=7.5, leading=10, textColor=MUTED),
        "stat": style("stat", fontName="DV-B", fontSize=15, leading=19, textColor=INK),
        "statlabel": style("statlabel", fontSize=7.5, leading=10, textColor=MUTED),
        "chart_title": style("chart_title", fontName="DV-B", fontSize=8.8, leading=12, textColor=INK),
        "chart_note": style("chart_note", fontName="DV-I", fontSize=7.6, leading=10.5, textColor=BODY),
    }


def esc(value):
    return escape(str(value if value is not None else ""))


# --------------------------------------------------
# number formatting
# --------------------------------------------------

def format_number(value, digits=2):
    """12345678.5 -> 1,23,45,678.5 (same grouping as the website)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return esc(value) if value is not None else "-"

    if number != number or number in (float("inf"), float("-inf")):
        return "-"

    text = f"{abs(number):.{digits}f}".rstrip("0").rstrip(".") if digits else f"{abs(number):.0f}"
    whole, _, fraction = text.partition(".")

    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])

    sign = "-" if number < 0 else ""
    return f"{sign}{whole}{'.' + fraction if fraction else ''}"


# --------------------------------------------------
# page furniture
# --------------------------------------------------

def _page_furniture(title):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, PAGE_H - 1.15 * cm, PAGE_W - MARGIN, PAGE_H - 1.15 * cm)
        canvas.setFont("DV-B", 8)
        canvas.setFillColor(INDIGO)
        canvas.drawString(MARGIN, PAGE_H - 0.9 * cm, "DataLens")
        canvas.setFont("DV", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.9 * cm, title[:70])
        canvas.drawString(MARGIN, 0.85 * cm, "Numbers are calculated from your data. AI text is labelled.")
        canvas.drawRightString(PAGE_W - MARGIN, 0.85 * cm, f"Page {doc.page}")
        canvas.restoreState()

    return draw


# --------------------------------------------------
# building blocks
# --------------------------------------------------

def _table(rows, widths, header=True, zebra=True, extra=None):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), SOFT), ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE)]
    if extra:
        commands += extra
    table.setStyle(TableStyle(commands))
    return table


def _stat_cards(items, styles, per_row=4):
    """items: list of (label, value, hint). Returns a table of cards."""
    cells = []
    for label, value, hint in items:
        parts = [Paragraph(esc(value), styles["stat"]), Paragraph(esc(label), styles["statlabel"])]
        if hint:
            parts.append(Paragraph(esc(hint), styles["small"]))
        cells.append(parts)

    rows = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
    for row in rows:
        row.extend([""] * (per_row - len(row)))

    width = CONTENT_W / per_row
    table = Table(rows, colWidths=[width] * per_row, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell != "":
                commands += [
                    ("BACKGROUND", (c, r), (c, r), SOFT),
                    ("LINEBEFORE", (c, r), (c, r), 2.2, INDIGO),
                    ("BOX", (c, r), (c, r), 0.4, colors.white),
                ]
    table.setStyle(TableStyle(commands))
    return table


def _pill(text, color, styles):
    return Paragraph(f'<font color="{color.hexval().replace("0x", "#")}"><b>{esc(text)}</b></font>', styles["small"])


# --------------------------------------------------
# sections
# --------------------------------------------------

def _section_glance(context, styles):
    dashboard = context["dashboard"]
    summary = dashboard.get("summary") or {}
    charts = context["charts"]
    insights = context["insights"]
    story = [Paragraph("At a glance", styles["h1"])]

    quality_before = (context.get("quality_before") or {}).get("quality_score")
    quality_after = (context.get("quality_after") or {}).get("quality_score")

    if quality_after is not None:
        quality = (f"{quality_before:.0f} to {quality_after:.0f}", "Data quality score (0-100)")
    elif quality_before is not None:
        quality = (f"{quality_before:.0f}", "Data quality score (0-100)")
    else:
        quality = ("-", "Data quality score")

    story.append(_stat_cards([
        ("Rows", format_number(summary.get("total_rows"), 0), None),
        ("Columns", format_number(summary.get("total_columns"), 0), None),
        (quality[1], quality[0], "before to after cleaning" if quality_after is not None else None),
        ("Charts in this report", str(len(charts)), None),
    ], styles))

    kpis = [k for k in (dashboard.get("kpis") or []) if isinstance(k, dict)]
    if kpis:
        story += [Spacer(1, 6), Paragraph("Key metrics", styles["h2"])]
        items = []
        for kpi in kpis[:8]:
            value = kpi.get("value", kpi.get("metric", "-"))
            shown = format_number(value) if isinstance(value, (int, float)) else str(value)
            items.append((kpi.get("label") or kpi.get("name") or "Metric", shown, kpi.get("description")))
        story.append(_stat_cards(items, styles))

    ai = dashboard.get("dashboard_ai")
    if isinstance(ai, dict) and ai.get("ai_generated") and ai.get("summary"):
        box = Table(
            [[[Paragraph("<b>AI summary</b>", ParagraphStyle("t", parent=styles["small"], textColor=colors.HexColor("#8b5cf6"))),
               Paragraph(esc(ai["summary"]), styles["body"]),
               Paragraph("Written by AI from the verified numbers in this report.", styles["note"])]]],
            colWidths=[CONTENT_W],
        )
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f1ff")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [Spacer(1, 8), box]

    return story


def _before_after_table(report, quality_before, quality_after, styles):
    def delta(before, after, lower_is_better=True):
        diff = after - before
        if diff == 0:
            return "No change"
        color = "#0f8a55" if (diff < 0) == lower_is_better else "#cc2b55"
        return f'<font color="{color}"><b>{"+" if diff > 0 else ""}{format_number(diff)}</b></font>'

    head = [Paragraph(t, styles["head"]) for t in ("", "Before", "After", "Change")]
    rows = [head]

    rows.append([
        Paragraph("Rows", styles["cellb"]),
        Paragraph(format_number(report["rows"]["before"], 0), styles["cell"]),
        Paragraph(format_number(report["rows"]["after"], 0), styles["cell"]),
        Paragraph(delta(report["rows"]["before"], report["rows"]["after"], lower_is_better=False), styles["cell"]),
    ])
    for label, key in (("Empty cells", "missing_cells"), ("Duplicate rows", "duplicate_rows")):
        rows.append([
            Paragraph(label, styles["cellb"]),
            Paragraph(format_number(report[key]["before"], 0), styles["cell"]),
            Paragraph(format_number(report[key]["after"], 0), styles["cell"]),
            Paragraph(delta(report[key]["before"], report[key]["after"]), styles["cell"]),
        ])

    if quality_before is not None and quality_after is not None:
        diff = quality_after - quality_before
        color = "#0f8a55" if diff >= 0 else "#cc2b55"
        rows.append([
            Paragraph("Quality score", styles["cellb"]),
            Paragraph(f"{quality_before:.1f}", styles["cell"]),
            Paragraph(f"{quality_after:.1f}", styles["cell"]),
            Paragraph(f'<font color="{color}"><b>{diff:+.1f}</b></font>' if diff else "No change", styles["cell"]),
        ])

    return _table(rows, [4.2 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm])


def _section_cleaning(context, styles):
    story = [Paragraph("Data cleaning report", styles["h1"])]
    report = context.get("cleaning_report")
    q_before = context.get("quality_before") or {}
    q_after = context.get("quality_after") or {}

    if not report:
        story.append(Paragraph(
            "No cleaning was applied, so this report uses your uploaded data as it is. "
            "The problems DataLens found in the file are listed below. "
            "Cleaning them first gives more accurate charts and insights.", styles["body"]))
        issues = q_before.get("issues") or []
        if issues:
            rows = [[Paragraph(t, styles["head"]) for t in ("Problem", "Column", "What was found")]]
            for issue in issues[:12]:
                rows.append([
                    Paragraph(esc(str(issue.get("type", "")).replace("_", " ").capitalize()), styles["cellb"]),
                    Paragraph(esc(issue.get("column") or "(whole rows)"), styles["cell"]),
                    Paragraph(esc(issue.get("message", "")), styles["cell"]),
                ])
            story += [Spacer(1, 6), _table(rows, [3.6 * cm, 3.4 * cm, CONTENT_W - 7.0 * cm])]
        return story

    applied = report.get("applied_at", "")
    try:
        applied = datetime.fromisoformat(applied).strftime("%d %b %Y, %H:%M UTC")
    except (TypeError, ValueError):
        pass

    story.append(Paragraph(
        f"Cleaning was applied on {esc(applied)}. "
        "Your uploaded file was not modified.", styles["body"]))
    story += [Spacer(1, 6), _before_after_table(report, q_before.get("quality_score"), q_after.get("quality_score"), styles)]

    assumptions = report.get("assumptions") or []
    if assumptions:
        story.append(Paragraph("Please check these assumptions", styles["h2"]))
        for item in assumptions:
            mark = "Check: " if item.get("level") == "warning" else "Note: "
            story.append(Paragraph(
                f'<b>{esc(mark)}{esc(item.get("column"))}</b>  {esc(item.get("message"))}', styles["body"]))
            story.append(Spacer(1, 2))

    checks = report.get("column_checks") or []
    if checks:
        story += [Paragraph("Did any totals change?", styles["h2"]),
                  Paragraph("Totals of number columns before and after cleaning. Money should not disappear unless "
                            "rows were removed or empty cells were filled.", styles["sub"])]
        rows = [[Paragraph(t, styles["head"]) for t in ("Column", "Total before", "Total after", "Change")]]
        flags = []
        for index, check in enumerate(checks, start=1):
            change = check.get("change_pct", 0)
            rows.append([
                Paragraph(esc(check.get("column")), styles["cell"]),
                Paragraph(format_number(check.get("before_total")), styles["cell"]),
                Paragraph(format_number(check.get("after_total")), styles["cell"]),
                Paragraph(f'{"+" if change > 0 else ""}{format_number(change)}%' + (" (check)" if check.get("flag") else ""), styles["cell"]),
            ])
            if check.get("flag"):
                flags.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#fff8eb")))
        story.append(_table(rows, [5.4 * cm, 4.0 * cm, 4.0 * cm, CONTENT_W - 13.4 * cm], extra=flags))

    log = report.get("change_log") or []
    heading = [Paragraph("What was changed", styles["h2"])]
    if not log:
        story += heading + [Paragraph("No changes were made.", styles["body"])]

    for entry in log:
        block = [Paragraph(
            f'<b>{esc(entry.get("column"))}</b>  <font color="#6366f1">{esc(entry.get("action"))}</font>', styles["body"]),
            Paragraph(esc(entry.get("detail")), styles["small"])]

        examples = (entry.get("examples") or [])[:2]
        if examples:
            rows = [[Paragraph(t, styles["head"]) for t in ("CSV row", "Before", "After")]]
            for example in examples:
                rows.append([Paragraph(esc(example.get("row")), styles["cell"]),
                             Paragraph(esc(example.get("before")), styles["cell"]),
                             Paragraph(esc(example.get("after")), styles["cell"])])
            block += [Spacer(1, 2), _table(rows, [2.0 * cm, 7.4 * cm, 7.4 * cm], zebra=False)]

        story += [KeepTogether(heading + block), Spacer(1, 6)]
        heading = []

    return story


def _insight_block(insight, styles):
    tag_label, tag_color = TAGS.get(insight.get("type"), TAGS["info"])
    title = insight.get("title") or ""
    message = insight.get("message") or insight.get("observation") or ""
    action = insight.get("recommendation") or insight.get("suggestion") or ""
    evidence = insight.get("evidence") if isinstance(insight.get("evidence"), dict) else None

    heading = f'<font color="{tag_color.hexval().replace("0x", "#")}"><b>{esc(tag_label.upper())}</b></font>'
    if evidence and evidence.get("confidence") in CONFIDENCE:
        label, color = CONFIDENCE[evidence["confidence"]]
        heading += f'   <font color="{color.hexval().replace("0x", "#")}">{esc(label)}</font>'

    parts = [Paragraph(heading, styles["small"])]
    if title and title != message:
        parts.append(Paragraph(f"<b>{esc(title)}</b>", styles["cellb"]))
    parts.append(Paragraph(esc(message), styles["body"]))
    if action:
        parts.append(Paragraph(f'<font color="{tag_color.hexval().replace("0x", "#")}"><b>{esc(action)}</b></font>', styles["small"]))

    if evidence:
        basis = []
        if evidence.get("columns"):
            basis.append("Columns: " + ", ".join(map(str, evidence["columns"])))
        if evidence.get("rows") is not None:
            basis.append(f"Rows used: {format_number(evidence['rows'], 0)}")
        if evidence.get("method"):
            basis.append(str(evidence["method"]))
        table = evidence.get("table") or []
        if table:
            basis.append("; ".join(f"{t.get('label')}: {t.get('value')}" for t in table[:5]))
        if evidence.get("note"):
            basis.append(str(evidence["note"]))
        parts.append(Spacer(1, 2))
        parts.append(Paragraph("How this was calculated: " + esc("  |  ".join(basis)), styles["note"]))

    box = Table([[parts]], colWidths=[CONTENT_W])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("LINEBEFORE", (0, 0), (0, 0), 2.4, tag_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([box, Spacer(1, 6)])


def _section_insights(context, styles):
    insights = context["insights"]
    if not insights:
        return []
    story = [Paragraph("Key insights", styles["h1"]),
             Paragraph("Each insight shows how it was calculated, so you can check it yourself.", styles["sub"])]
    story += [_insight_block(item, styles) for item in insights]
    return story


def _chart_cell(item, styles, width):
    chart = item["chart"]
    ratio = 0.60 if width > HALF_W + 1 else 0.74
    width_in, height_in = width / 72.0, width * ratio / 72.0

    cell = [Paragraph(esc(chart.get("title") or "Chart"), styles["chart_title"])]
    kind = str(chart.get("chart_type", "")).replace("_", " ")
    if kind:
        cell.append(Paragraph(esc(kind), styles["small"]))

    try:
        png = render_chart_png(chart, width_in, height_in)
        image = Image(io.BytesIO(png))
        ratio_img = image.imageHeight / float(image.imageWidth)
        image.drawWidth = width
        image.drawHeight = width * ratio_img
        cell.append(image)
    except Exception:
        cell.append(Paragraph("This chart could not be drawn.", styles["note"]))

    if chart.get("insight"):
        cell.append(Spacer(1, 2))
        cell.append(Paragraph(esc(chart["insight"]), styles["chart_note"]))

    return cell


def _is_id_like(name):
    if not isinstance(name, str):
        return False
    return bool(
        re.search(r"(^|[_\s-])(id|uuid|guid|idx|index)($|[_\s-])", name, re.I)
        or re.search(r"[a-z]Id$", name)
        or re.match(r"^unnamed", name, re.I)
    )


def usable_charts(charts):
    """Same rule as the dashboard: skip ID charts and charts with no data."""
    result = []
    for chart in charts or []:
        data = chart.get("data")
        if not isinstance(data, list) or len(data) < 2:
            continue
        if str(chart.get("chart_type")) == "table":
            continue
        if any(_is_id_like(chart.get(k)) for k in ("x_label", "y_label", "x_column", "y_column")):
            continue
        result.append(chart)
    return result


def _is_wide(chart):
    size = str(chart.get("size", "")).lower()
    if size in ("lg", "large", "xl", "full"):
        return True
    return str(chart.get("chart_type")) in ("line", "area", "trend", "treemap")


def _section_charts(context, styles):
    charts = context["charts"]
    if not charts:
        return [Paragraph("Charts", styles["h1"]),
                Paragraph("This dataset did not have enough useful columns for automatic charts.", styles["body"])]

    intro = [Paragraph("Charts", styles["h1"]),
             Paragraph(f"{len(charts)} charts built from your data. ID columns are left out because they carry no business meaning.",
                       styles["sub"])]
    story = []

    def emit(block):
        """The Charts heading is kept together with the first chart."""
        nonlocal intro
        if intro:
            story.append(KeepTogether(intro + block))
            intro = []
        else:
            story.append(KeepTogether(block))
        story.append(Spacer(1, 10))

    items = [{"chart": c, "wide": _is_wide(c)} for c in charts]
    used = [False] * len(items)

    for i, item in enumerate(items):
        if used[i]:
            continue
        used[i] = True

        if item["wide"]:
            emit(_chart_cell(item, styles, CONTENT_W))
            continue

        partner = next((j for j in range(i + 1, len(items)) if not used[j] and not items[j]["wide"]), None)
        left = _chart_cell(item, styles, HALF_W)

        if partner is None:
            emit(left)
            continue

        used[partner] = True
        right = _chart_cell(items[partner], styles, HALF_W)
        row = Table([[left, right]], colWidths=[HALF_W + GAP / 2, HALF_W + GAP / 2], hAlign="LEFT")
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), GAP / 2),
            ("LEFTPADDING", (1, 0), (1, 0), GAP / 2), ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        emit([row])

    return story


ROLE_LABELS = [
    ("revenue", "Sales / revenue amount"), ("quantity", "Quantity"), ("date", "Date"),
    ("order_id", "Order ID"), ("customer", "Customer"), ("product", "Product"),
    ("returned", "Returned (0/1)"), ("discount", "Discount"),
]


def _section_columns(context, styles):
    dashboard = context["dashboard"]
    roles = dashboard.get("detected_roles") or {}
    ignored = dashboard.get("ignored_id_columns") or []

    found = [(label, roles.get(key)) for key, label in ROLE_LABELS if roles.get(key)]
    if not found and not ignored:
        return []

    story = [Paragraph("How your columns were read", styles["h1"]),
             Paragraph("If any of these is wrong, change it on the Charts page and download the report again.", styles["sub"])]

    if found:
        rows = [[Paragraph(t, styles["head"]) for t in ("Meaning", "Column used")]]
        rows += [[Paragraph(esc(label), styles["cellb"]), Paragraph(esc(col), styles["cell"])] for label, col in found]
        story.append(_table(rows, [6.0 * cm, 8.0 * cm]))

    if ignored:
        story += [Spacer(1, 5), Paragraph("ID columns left out of charts: " + esc(", ".join(map(str, ignored))), styles["small"])]

    return story


# --------------------------------------------------
# public
# --------------------------------------------------

def collect_insights(dashboard):
    """Verified insights first, then AI comments (only when really written by AI)."""
    items = [i for i in (dashboard.get("insights") or []) if isinstance(i, dict)]
    ai = dashboard.get("dashboard_ai")

    if isinstance(ai, dict) and ai.get("ai_generated"):
        for item in ai.get("insights") or []:
            if isinstance(item, dict):
                items.append({**item, "type": "ai"})

    seen, result = set(), []
    for item in items:
        key = item.get("message") or item.get("observation") or item.get("title")
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result[:11]


def build_pdf_report(context):
    """
    context: {
      filename, using_cleaned, dashboard (the /dashboard payload),
      cleaning_report (or None), quality_before, quality_after
    }
    Returns PDF bytes.
    """
    _register_fonts()
    styles = _styles()

    dashboard = context.get("dashboard") or {}
    prepared = {
        **context,
        "dashboard": dashboard,
        "charts": usable_charts(dashboard.get("charts")),
        "insights": collect_insights(dashboard),
    }

    filename = context.get("filename") or "dataset"
    version = "cleaned data" if context.get("using_cleaned") else "uploaded data (not cleaned)"

    buffer = io.BytesIO()
    document = BaseDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.7 * cm, bottomMargin=1.5 * cm,
        title=f"DataLens report - {filename}", author="DataLens",
    )
    frame = Frame(MARGIN, 1.5 * cm, CONTENT_W, PAGE_H - 3.2 * cm, id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    document.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=_page_furniture(filename))])

    story = [
        Paragraph("Data analytics report", styles["title"]),
        Spacer(1, 3),
        Paragraph(
            f"<b>{esc(filename)}</b>  |  Data used: {esc(version)}  |  Created {datetime.now().strftime('%d %b %Y, %H:%M')}",
            styles["meta"]),
        Spacer(1, 4),
    ]

    story += _section_glance(prepared, styles)
    story += _section_cleaning(prepared, styles)
    story += _section_insights(prepared, styles)
    story += _section_charts(prepared, styles)
    story += _section_columns(prepared, styles)

    document.build(story)
    return buffer.getvalue()
# core/export_pdf.py
from __future__ import annotations

import os
from ui.common import LABELS, EMO_COLORS, fmt_mmss, fmt_hhmm
from core.storage import load_moments_aggregate


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _register_dejavu_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts_dir = os.path.join(_project_root(), "ui", "assets", "fonts")
    regular_path = os.path.join(fonts_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(fonts_dir, "DejaVuSans-Bold.ttf")

    regular_name = "DejaVuSans"
    bold_name = "DejaVuSans-Bold"

    try:
        pdfmetrics.getFont(regular_name)
        pdfmetrics.getFont(bold_name)
        return regular_name, bold_name
    except Exception:
        pass

    if not (os.path.exists(regular_path) and os.path.exists(bold_path)):
        return "Helvetica", "Helvetica-Bold"

    pdfmetrics.registerFont(TTFont(regular_name, regular_path))
    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
    return regular_name, bold_name

def _period_to_key(period: str) -> str:
    p = (period or "").strip()
    # EN keys
    if p in ("Today", "Last 7 days", "All time"):
        return p
    # UA shown values
    ua = {
        "Сьогодні": "Today",
        "Останні 7 днів": "Last 7 days",
        "За весь час": "All time",
    }
    return ua.get(p, "All time")


def _draw_donut_on_canvas(
    c,
    cx: float,
    cy: float,
    r: float,
    items: list[tuple[str, int]],
    total: int,
    colors_mod,
    panel_hex: str,
):
    """
    items: [(emo, count)] тільки ті, що >0 (або topN+Other)
    """
    if total <= 0:
        return

    start = 90.0
    for emo, cnt in items:
        if cnt <= 0:
            continue
        extent = 360.0 * (cnt / total)

        c.setFillColor(colors_mod.HexColor(EMO_COLORS.get(emo, "#94a3b8")))
        c.setStrokeColor(colors_mod.HexColor(panel_hex))
        c.setLineWidth(0.6)
        c.wedge(cx - r, cy - r, cx + r, cy + r, startAng=start, extent=-extent, stroke=1, fill=1)
        start -= extent

    # donut hole
    inner = r * 0.58
    c.setFillColor(colors_mod.HexColor(panel_hex))
    c.setStrokeColor(colors_mod.HexColor(panel_hex))
    c.circle(cx, cy, inner, stroke=1, fill=1)

def export_stats_pdf(
    save_path: str,
    period: str,
    totals: dict[str, float],
    sessions_count: int,
    total_sec: float,
    lang: str = "EN",
) -> str:
    # import reportlab ONLY here
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics import renderPDF

    lang = (lang or "EN").upper()

    FONT_REG, FONT_BOLD = _register_dejavu_fonts()

    c = pdf_canvas.Canvas(save_path, pagesize=A4)
    page_w, page_h = A4
    margin = 2 * cm

    APP_NAME = "MoodTracker"  # або як хочеш
    title = f"{APP_NAME} — Session statistics" if lang == "EN" else f"{APP_NAME} — Статистика сесій"
    c.setFont(FONT_BOLD, 18)
    y = page_h - margin
    c.setFillColor(colors.black)
    c.drawString(margin, y, title)

    c.setFont(FONT_REG, 12)
    y -= 0.9 * cm
    if lang == "EN":
        c.drawString(margin, y, f"Period: {period}")
        y -= 0.65 * cm
        c.drawString(margin, y, f"Sessions: {sessions_count}")
        y -= 0.65 * cm
        c.drawString(margin, y, f"Total time: {fmt_hhmm(total_sec)}")
    else:
        c.drawString(margin, y, f"Період: {period}")
        y -= 0.65 * cm
        c.drawString(margin, y, f"Сесій: {sessions_count}")
        y -= 0.65 * cm
        c.drawString(margin, y, f"Загальний час: {fmt_hhmm(total_sec)}")

    y -= 0.6 * cm

    vals_min = [(float(totals.get(emo, 0.0) or 0.0) / 60.0) for emo in LABELS]
    max_val = max(vals_min) if vals_min else 1.0
    if max_val <= 0:
        max_val = 1.0

    bar_w = page_w - 2 * margin
    bar_h = 7.5 * cm
    bar_d = Drawing(bar_w, bar_h)

    bc = VerticalBarChart()
    bc.x = 0.8 * cm
    bc.y = 1.2 * cm
    bc.width = bar_w - 1.6 * cm
    bc.height = bar_h - 2.2 * cm
    bc.data = [vals_min]
    bc.categoryAxis.categoryNames = [e.capitalize() for e in LABELS]
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = max_val * 1.10
    bc.valueAxis.valueStep = max(1, int((max_val * 1.10) / 5))

    bc.valueAxis.labels.fontName = FONT_REG
    bc.valueAxis.labels.fontSize = 8
    bc.categoryAxis.labels.fontName = FONT_REG
    bc.categoryAxis.labels.fontSize = 9

    bc.strokeColor = colors.HexColor("#1f2937")
    bc.bars.strokeColor = None

    for i, emo in enumerate(LABELS):
        bc.bars[(0, i)].fillColor = colors.HexColor(EMO_COLORS.get(emo, "#94a3b8"))

    bar_d.add(bc)
    bar_y = y - bar_h
    renderPDF.draw(bar_d, c, margin, bar_y)

    pie_w = 9.2 * cm
    pie_h = 9.2 * cm
    pie_d = Drawing(pie_w, pie_h)

    pie = Pie()
    pie.x = 0.6 * cm
    pie.y = 0.6 * cm
    pie.width = pie_w - 1.2 * cm
    pie.height = pie_h - 1.2 * cm
    pie.data = vals_min
    pie.labels = [""] * len(LABELS)
    pie.sideLabels = False

    for i, emo in enumerate(LABELS):
        pie.slices[i].fillColor = colors.HexColor(EMO_COLORS.get(emo, "#94a3b8"))
        pie.slices[i].strokeColor = colors.white
        pie.slices[i].strokeWidth = 0.3

    pie_d.add(pie)

    bottom_y = bar_y - 0.8 * cm - pie_h
    renderPDF.draw(pie_d, c, margin, bottom_y)

    table_x = margin + pie_w + 1.0 * cm
    table_y = bottom_y + pie_h - 0.3 * cm

    c.setFont(FONT_BOLD, 12)
    c.setFillColor(colors.black)
    c.drawString(table_x, table_y, "Emotion" if lang == "EN" else "Емоція")
    c.drawString(table_x + 6.0 * cm, table_y, "Time" if lang == "EN" else "Час")
    c.drawString(table_x + 9.0 * cm, table_y, "Share" if lang == "EN" else "Частка")

    c.setFont(FONT_REG, 12)
    table_y -= 0.7 * cm

    total = total_sec if total_sec > 0 else 1.0
    for emo in LABELS:
        sec = float(totals.get(emo, 0.0) or 0.0)
        pct = int(round((sec / total) * 100)) if total_sec > 0 else 0

        c.setFillColor(colors.HexColor(EMO_COLORS.get(emo, "#94a3b8")))
        c.rect(table_x, table_y - 0.18 * cm, 0.25 * cm, 0.25 * cm, stroke=0, fill=1)

        c.setFillColor(colors.black)
        c.drawString(table_x + 0.4 * cm, table_y, emo.capitalize())
        c.drawString(table_x + 6.0 * cm, table_y, fmt_mmss(sec))
        c.drawString(table_x + 9.0 * cm, table_y, f"{pct}%")
        table_y -= 0.6 * cm

    # ============================
    # PAGE 2: Moments breakdown
    # ============================
    c.showPage()

    period_key = _period_to_key(period)
    moments_total, moments_by_emo = load_moments_aggregate(period_key)

    y2 = page_h - margin
    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, 18)
    c.drawString(margin, y2, "Moments breakdown" if lang == "EN" else "Розподіл моментів")

    y2 -= 0.9 * cm
    c.setFont(FONT_REG, 12)
    if lang == "EN":
        c.drawString(margin, y2, f"Period: {period}")
        y2 -= 0.65 * cm
        c.drawString(margin, y2, f"Total moments: {moments_total}")
    else:
        c.drawString(margin, y2, f"Період: {period}")
        y2 -= 0.65 * cm
        c.drawString(margin, y2, f"Моментів всього: {moments_total}")

    # --- Donut + legend layout ---
    block_top = y2 - 1.0 * cm
    donut_r = 3.6 * cm
    donut_cx = margin + donut_r + 0.4 * cm
    donut_cy = block_top - donut_r

    # підготуємо items: top-6 + Other (щоб легенда не розлазилась)
    vals = [(emo, int(moments_by_emo.get(emo, 0) or 0)) for emo in LABELS]
    vals = [(e, v) for e, v in vals if v > 0]
    vals.sort(key=lambda x: x[1], reverse=True)

    top = vals[:6]
    other_sum = sum(v for _, v in vals[6:])
    items = top[:]
    if other_sum > 0:
        items.append(("other", other_sum))
        # колір для other
        EMO_COLORS.setdefault("other", "#94a3b8")

    # donut
    panel_hex = "#ffffff"  # фон сторінки (білий). якщо хочеш під "panel" — постав свій hex.
    _draw_donut_on_canvas(c, donut_cx, donut_cy, donut_r, items, int(moments_total), colors, panel_hex)

    # center text
    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, 18)
    c.drawCentredString(donut_cx, donut_cy + 4, str(int(moments_total)))

    c.setFillColor(colors.HexColor("#6b7280"))
    c.setFont(FONT_REG, 10)
    c.drawCentredString(
        donut_cx,
        donut_cy - 12,
        "moments" if lang == "EN" else "моментів",
    )

    # legend справа
    legend_x = margin + 9.0 * cm
    legend_y = block_top - 0.2 * cm
    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, 12)
    c.drawString(legend_x, legend_y, "Counts" if lang == "EN" else "К-сть")

    legend_y -= 0.8 * cm
    c.setFont(FONT_REG, 12)

    for emo, cnt in items:
        c.setFillColor(colors.HexColor(EMO_COLORS.get(emo, "#94a3b8")))
        c.rect(legend_x, legend_y - 0.18 * cm, 0.25 * cm, 0.25 * cm, stroke=0, fill=1)

        c.setFillColor(colors.black)
        label = emo.capitalize() if emo != "other" else ("Other" if lang == "EN" else "Інше")
        c.drawString(legend_x + 0.4 * cm, legend_y, f"{label}")
        c.drawRightString(legend_x + 6.5 * cm, legend_y, str(cnt))

        legend_y -= 0.6 * cm

    c.showPage()
    c.save()
    return save_path

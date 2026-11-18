"""Render the accompanying, deliberately simple methods-paper Markdown.

Optional document-build dependency: ReportLab. This is not needed to run the
auditor. Fonts are resolved locally; no fonts or resources are downloaded.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted,
)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "EditAuditor_Methods_v1.md"
OUTPUT = ROOT / "EditAuditor_Methods_v1.pdf"
INK, SECONDARY = colors.HexColor("#2C2C2B"), colors.HexColor("#525860")
BLUE, SURFACE, BORDER = colors.HexColor("#155F9B"), colors.HexColor("#F1F6FA"), colors.HexColor("#D9DFE5")
WIDTH = 480


def fonts():
    options = [
        (Path("/usr/share/fonts/msttcore/arial.ttf"), Path("/usr/share/fonts/msttcore/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"), Path("/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf")),
        (Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"), Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for regular, bold in options:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("PaperSans", str(regular)))
            pdfmetrics.registerFont(TTFont("PaperSansBold", str(bold)))
            pdfmetrics.registerFontFamily("PaperSans", normal="PaperSans", bold="PaperSansBold",
                                         italic="PaperSans", boldItalic="PaperSansBold")
            return "PaperSans"
    raise SystemExit("A local Arial or DejaVu Sans font pair is required; no font is downloaded.")


FONT = fonts()
styles = getSampleStyleSheet()
styles.add(ParagraphStyle("PaperTitle", fontName="PaperSansBold", fontSize=25, leading=29,
                         textColor=INK, spaceAfter=18))
styles.add(ParagraphStyle("PaperH2", fontName="PaperSansBold", fontSize=18, leading=23,
                         textColor=INK, spaceBefore=6, spaceAfter=12, keepWithNext=True))
styles.add(ParagraphStyle("PaperH3", fontName="PaperSansBold", fontSize=12.5, leading=17,
                         textColor=BLUE, spaceBefore=10, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle("PaperBody", fontName=FONT, fontSize=11, leading=15.1,
                         textColor=INK, spaceAfter=8, alignment=TA_LEFT))
styles.add(ParagraphStyle("PaperBullet", parent=styles["PaperBody"], leftIndent=13,
                         firstLineIndent=0, bulletIndent=0, spaceAfter=7))
styles.add(ParagraphStyle("PaperCell", fontName=FONT, fontSize=10, leading=13.5, textColor=INK))
styles.add(ParagraphStyle("PaperCellHead", parent=styles["PaperCell"], fontName="PaperSansBold"))
styles.add(ParagraphStyle("PaperCallout", parent=styles["PaperBody"], fontSize=11, leading=15.5, spaceAfter=0))
styles.add(ParagraphStyle("PaperCode", fontName="Courier", fontSize=10, leading=14,
                         textColor=INK, backColor=colors.HexColor("#F7F8F9"),
                         borderPadding=10, spaceBefore=5, spaceAfter=13))


def inline(text):
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#155F9B">\1</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="10">\1</font>', text)
    return text


def page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(SECONDARY)
    canvas.setFont(FONT, 9)
    canvas.drawString(66, 759, "EDIT AUDITOR")
    canvas.drawRightString(546, 759, "WORKING METHODS PAPER  /  v0.1.0")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.6)
    canvas.line(66, 748, 546, 748)
    canvas.drawString(66, 29, "Aaron Michael Weis (ΩNeiron™)  ·  Research draft")
    canvas.drawRightString(546, 29, str(doc.page))
    canvas.restoreState()


def main():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line == "<!-- PAGE -->":
            story.append(PageBreak())
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            story.append(Preformatted("\n".join(code), styles["PaperCode"]))
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            widths = [126, 354] if len(rows[0]) == 2 else [WIDTH / len(rows[0])] * len(rows[0])
            cells = [[Paragraph(inline(cell), styles["PaperCellHead" if row_number == 0 else "PaperCell"])
                      for cell in row] for row_number, row in enumerate(rows)]
            table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, BORDER),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([table, Spacer(1, 12)])
            continue
        if line.startswith("> "):
            callout = Table([[Paragraph(inline(line[2:]), styles["PaperCallout"])]], colWidths=[WIDTH])
            callout.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]))
            story.extend([callout, Spacer(1, 14)])
            index += 1
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["PaperTitle"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["PaperH2"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), styles["PaperH3"]))
        elif line.startswith("- "):
            story.append(Paragraph(inline(line[2:]), styles["PaperBullet"], bulletText="•"))
        else:
            parts = [line]
            while index + 1 < len(lines) and lines[index + 1].strip() and not lines[index + 1].startswith(("#", "|", ">", "```", "- ", "<!--")):
                index += 1
                parts.append(lines[index])
            story.append(Paragraph(inline(" ".join(parts)), styles["PaperBody"]))
        index += 1
    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter, leftMargin=66, rightMargin=66,
        topMargin=66, bottomMargin=55,
        title="Preservation-First Editing: A Local, Review-Bound Auditor for Markdown",
        author="Aaron Michael Weis (ΩNeiron™)",
        subject="Working methods paper accompanying Edit Auditor v0.1.0",
    )
    document.build(story, onFirstPage=page, onLaterPages=page)
    print(OUTPUT.name)


if __name__ == "__main__":
    main()
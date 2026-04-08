"""
output/pdf_exporter.py
Converts a .docx file to a PDF.

Strategy:
  1. Try docx2pdf (uses Word/LibreOffice — best fidelity, platform-dependent)
  2. Fall back to a reportlab-rendered version if docx2pdf unavailable

The reportlab fallback reads the .docx via python-docx and renders a clean
multi-page PDF — it won't perfectly mirror the Word styling, but it produces
a professional, readable document suitable for delivery.
"""

from __future__ import annotations

import re
from pathlib import Path


# ── Public API ──────────────────────────────────────────────────────────────


def export_pdf(docx_path: str | Path, pdf_path: str | Path | None = None) -> Path:
    """
    Convert a .docx file to PDF.

    Args:
        docx_path: Path to the source .docx file.
        pdf_path: Where to write the PDF. Defaults to same location as .docx
                  with .pdf extension.

    Returns:
        Path to the created PDF file.
    """
    docx_path = Path(docx_path)
    if pdf_path is None:
        pdf_path = docx_path.with_suffix(".pdf")
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Try docx2pdf first (best quality, requires MS Word or LibreOffice)
    if _try_docx2pdf(docx_path, pdf_path):
        return pdf_path

    # Fall back to reportlab renderer
    _render_with_reportlab(docx_path, pdf_path)
    return pdf_path


# ── docx2pdf strategy ───────────────────────────────────────────────────────


def _try_docx2pdf(docx_path: Path, pdf_path: Path) -> bool:
    """
    Attempt conversion via docx2pdf. Returns True on success.
    """
    try:
        from docx2pdf import convert  # type: ignore

        convert(str(docx_path), str(pdf_path))
        return pdf_path.exists()
    except Exception:
        return False


# ── ReportLab fallback ──────────────────────────────────────────────────────

_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _render_with_reportlab(docx_path: Path, pdf_path: Path) -> None:
    """
    Read the .docx and render a PDF via ReportLab.
    Extracts text from docx paragraphs and tables, then lays it out.
    """
    from docx import Document
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    doc = Document(docx_path)

    # Build styles
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "BPTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#1F497D"),
        alignment=1,  # center
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "BPSubtitle",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#2E74B5"),
        alignment=1,
        spaceAfter=2,
    )
    style_h1 = ParagraphStyle(
        "BPH1",
        parent=styles["Heading1"],
        fontSize=15,
        leading=20,
        textColor=colors.HexColor("#1F497D"),
        spaceBefore=14,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    style_h2 = ParagraphStyle(
        "BPH2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2E74B5"),
        spaceBefore=10,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    style_body = ParagraphStyle(
        "BPBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=5,
    )
    style_note = ParagraphStyle(
        "BPNote",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#C05000"),
        spaceAfter=5,
        fontName="Helvetica-Oblique",
    )

    story: list = []

    # Walk docx paragraphs/tables in order
    for block in _iter_blocks(doc):
        if block["type"] == "paragraph":
            text = block["text"].strip()
            if not text:
                story.append(Spacer(1, 4))
                continue

            # Detect heading styles by paragraph style name
            style_name = block.get("style", "")
            if "Title" in style_name or "BUSINESS PLAN" in text:
                story.append(Paragraph(text, style_title))
            elif style_name.startswith("Heading 1") or text.startswith("## "):
                clean = text.lstrip("#").strip()
                story.append(Paragraph(clean, style_h1))
            elif style_name.startswith("Heading 2") or text.startswith("### "):
                clean = text.lstrip("#").strip()
                story.append(Paragraph(clean, style_h2))
            elif "Note for review" in text or "WRITER_NOTE" in text.upper():
                safe = _escape_xml(text)
                story.append(Paragraph(safe, style_note))
            else:
                safe = _markdown_bold_to_reportlab(text)
                story.append(Paragraph(safe, style_body))

        elif block["type"] == "table":
            tbl_data = block["data"]
            if not tbl_data:
                continue

            col_count = max(len(r) for r in tbl_data)
            # Pad rows to same width
            padded = [r + [""] * (col_count - len(r)) for r in tbl_data]

            rl_table = Table(padded, repeatRows=1)
            rl_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F497D")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(rl_table)
            story.append(Spacer(1, 8))

    pdf_doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=1.25 * inch,
        rightMargin=1.25 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
    )
    pdf_doc.build(story)


def _iter_blocks(doc):
    """Yield paragraph and table blocks in document order."""
    body = doc.element.body
    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            from docx.text.paragraph import Paragraph as DocxParagraph
            para = DocxParagraph(child, doc)
            yield {
                "type": "paragraph",
                "text": para.text,
                "style": para.style.name if para.style else "",
            }
        elif tag == "tbl":
            from docx.table import Table as DocxTable
            tbl = DocxTable(child, doc)
            data = []
            for row in tbl.rows:
                data.append([cell.text.strip() for cell in row.cells])
            yield {"type": "table", "data": data}


def _escape_xml(text: str) -> str:
    """Escape characters that would break ReportLab XML parsing."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _markdown_bold_to_reportlab(text: str) -> str:
    """Convert **bold** markers to ReportLab <b> tags."""
    escaped = _escape_xml(text)
    return _RE_BOLD.sub(r"<b>\1</b>", escaped)

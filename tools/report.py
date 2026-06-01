"""
export_pdf: turn an agent answer into a clean PDF report.

The agent calls this tool with a title and the report body (plain text or light
markdown). We save it to reports folder and return the path.


fpdf2's built-in fonts are Latin-1 only, so we normalise the most common
Unicode punctuation (em dashes, smart quotes, bullets, arrows) to ASCII and
drop anything else, rather than ship a TTF font file.
"""

import os
import re
import datetime
from fpdf import FPDF

REPORTS_DIR = "reports"

#common Unicode -> ASCII
_UNICODE_FIXES = {
    "—": "-", "–": "-",
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "•": "-", "·": "-",
    "…": "...",
    " ": " ",
    "→": "->", "←": "<-",
    "≥": ">=", "≤": "<=",
}


def _safe(text: str) -> str:
    """Make text printable with the Latin-1 core font."""
    for bad, good in _UNICODE_FIXES.items():
        text = text.replace(bad, good)
    #drop anything still outside Latin-1 (e.g. emoji) instead of crashing
    return text.encode("latin-1", "ignore").decode("latin-1")


def export_pdf(title: str, content: str) -> dict:
    """
    Render a report to a PDF file.

    title:   short report title (also used for the filename).
    content: the report body. Plain text, or light markdown: lines starting
             with '# '/'## ' become headings, '- '/'* ' become bullets, and
             **bold** is honoured inline.

    Returns {"path": "<file path>"} on success, or {"error": "<message>"}.
    """
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)

        now = datetime.datetime.now()
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] or "report"
        path = os.path.join(REPORTS_DIR, f"{slug}-{now:%Y%m%d-%H%M%S}.pdf")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        #title
        pdf.set_font("Helvetica", "B", 18)
        pdf.multi_cell(0, 10, _safe(title), new_x="LMARGIN", new_y="NEXT")

        #generated-on line
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(0, 6, f"Generated {now:%Y-%m-%d %H:%M}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        _render_body(pdf, content)

        pdf.output(path)
        return {"path": path}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _render_body(pdf: FPDF, content: str) -> None:
    """Render the body line-by-line with light markdown awareness."""
    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        if not line.strip():
            pdf.ln(3)  #blank line -> a little vertical space
            continue

        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 8, _safe(line[3:]), new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("# "):
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(0, 9, _safe(line[2:]), new_x="LMARGIN", new_y="NEXT")
        elif line.lstrip().startswith(("- ", "* ")):
            pdf.set_font("Helvetica", "", 11)
            stripped = line.lstrip()
            pdf.multi_cell(0, 6, _safe("  - " + stripped[2:]), markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _safe(line), markdown=True,
                           new_x="LMARGIN", new_y="NEXT")

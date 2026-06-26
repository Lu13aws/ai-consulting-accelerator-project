"""Render an engagement's Markdown report to Word (.docx) or PDF.

Both renderers are pure-Python (python-docx, fpdf2) — no system dependencies, so they
run on AWS Lambda. They take the Markdown produced by `build_report()` and apply light
formatting (headings, bullets, **bold**). Not a full Markdown engine — just enough for
the structured artifacts these skills emit.
"""

from io import BytesIO

from docx import Document
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _heading_level(line: str) -> int:
    """Return the Markdown heading level (1–6), or 0 if the line is not a heading."""
    s = line.lstrip()
    n = 0
    while n < len(s) and s[n] == "#":
        n += 1
    return n if 1 <= n <= 6 and n < len(s) and s[n] == " " else 0


def _bullet_text(line: str) -> str | None:
    s = line.lstrip()
    return s[2:] if s[:2] in ("- ", "* ") else None


def _is_table_separator(line: str) -> bool:
    """A Markdown table divider row, e.g. `|----|:---:|` — rendered as nothing."""
    s = line.strip()
    return bool(s) and set(s) <= set("|-: ") and "-" in s


def _clean_table_row(line: str) -> str:
    """Flatten a `| a | b |` table row into spaced columns (drops the pipe borders)."""
    s = line.strip()
    if s.startswith("|"):
        return "   ".join(c.strip() for c in s.strip("|").split("|"))
    return line


# ── Word (.docx) ──────────────────────────────────────────────────────────────

def _add_runs(paragraph, text: str) -> None:
    """Add text to a paragraph, turning **…** into bold runs."""
    for i, part in enumerate(text.split("**")):
        if not part:
            continue
        run = paragraph.add_run(part)
        if i % 2 == 1:
            run.bold = True


def render_docx(markdown: str) -> bytes:
    doc = Document()
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip() or _is_table_separator(line):
            continue
        level = _heading_level(line)
        if level:
            # md '#' is the document title → Word heading level 0; deeper levels shift down.
            doc.add_heading(line.lstrip("#").strip(), level=min(level - 1, 4))
            continue
        bullet = _bullet_text(line)
        if bullet is not None:
            _add_runs(doc.add_paragraph(style="List Bullet"), bullet)
        else:
            _add_runs(doc.add_paragraph(), _clean_table_row(line))
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── PDF ─────────────────────────────────────────────────────────────────────

_UNICODE_REPLACEMENTS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "•": "-", "…": "...",
    "→": "->", " ": " ",
}


def _latin1(text: str) -> str:
    """fpdf2 core fonts are Latin-1 only — map common punctuation, drop the rest safely."""
    for src, dst in _UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def _wrap_tokens(text: str, limit: int = 70) -> str:
    """Insert break points into over-long tokens so fpdf2's WORD wrapping can fit them
    (avoids both the 'no horizontal space' crash and the wrapmode=CHAR loop in fpdf2)."""
    out: list[str] = []
    for token in text.split(" "):
        while len(token) > limit:
            out.append(token[:limit])
            token = token[limit:]
        out.append(token)
    return " ".join(out)


def render_pdf(markdown: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    def cell(text: str, height: float) -> None:
        # new_x=LMARGIN resets the cursor to the left margin; without it a full-width
        # (w=0) cell leaves x at the right edge, so the next w=0 cell gets zero width.
        pdf.multi_cell(0, height, _wrap_tokens(text.replace("**", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for raw in markdown.splitlines():
        line = _latin1(raw.rstrip())
        if not line.strip():
            pdf.ln(3)
            continue
        if _is_table_separator(line):
            continue
        level = _heading_level(line)
        if level:
            size = {1: 18, 2: 15, 3: 13}.get(level, 12)
            pdf.set_font("Helvetica", "B", size)
            cell(line.lstrip("#").strip(), size * 0.5 + 2)
            pdf.set_font("Helvetica", size=11)
            pdf.ln(1)
            continue
        # Inline bold (**…**) is not rendered in the PDF body — strip the markers; the
        # heading hierarchy carries the structure.
        bullet = _bullet_text(line)
        cell(f"  -  {bullet}" if bullet is not None else _clean_table_row(line), 6)
    return bytes(pdf.output())

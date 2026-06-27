"""Curated project-pattern catalog (Pattern Library pilot).

A small, hand-curated set of project archetypes (Corporate Knowledge Hub, Enterprise
Search, …) stored as Markdown under ``data/patterns/``. The catalog is read into the
prompt of the ``consulting.match-patterns`` skill — NO embeddings, NO RAG: at this size
(a handful of short files) the LLM matches the engagement context against the catalog
directly.

Deliberately discovery-scoped: each pattern lists typical goals / stakeholders / risks /
assumptions / pitfalls / success factors — and NO architecture or technology, to keep the
feature on the "assists, does not prescribe a solution" side of the line.
"""

from pathlib import Path

# data/patterns/ relative to the repo root (this file is apps/consulting_api/services/).
PATTERN_DIR = Path(__file__).resolve().parents[3] / "data" / "patterns"

# Safety cap so the catalog can never blow up the prompt if many patterns are added.
_MAX_CATALOG_CHARS = 20_000


def load_pattern_catalog(directory: Path | None = None) -> str:
    """Concatenate all pattern Markdown files into one catalog string (empty if none)."""
    directory = directory or PATTERN_DIR
    if not directory.is_dir():
        return ""
    blocks: list[str] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            blocks.append(text)
    catalog = "\n\n---\n\n".join(blocks)
    return catalog[:_MAX_CATALOG_CHARS]

"""Unit tests for the pure ingestion helpers (no DB / no network)."""

from pathlib import Path

from scripts.ingest_frameworks import (
    INGEST_EXTENSIONS,
    collect_files,
    derive_category,
    derive_language,
    derive_source_uri,
)


def test_derive_language_detects_tokens():
    assert derive_language("cpre_foundationlevel_handbook_de_v1.3.2.pdf") == "de"
    assert derive_language("advanced_level_elicitation_handbook_en_v2.2.0.pdf") == "en"
    assert derive_language("ireb-cpre-handbook-for-requirements-management-de-v2.1.pdf") == "de"
    # No language token -> unknown (not a wrong guess)
    assert derive_language("iiba_babok_v3.pdf") == "unknown"
    assert derive_language("scrum_framework.pdf") == "unknown"


def test_derive_category_uses_top_level_folder():
    data_root = Path("/data")
    assert derive_category(Path("/data/requirements_engineering/x.pdf"), data_root) == "requirements_engineering"
    assert derive_category(Path("/data/frameworks/sub/y.pdf"), data_root) == "frameworks"
    # File directly under data/ has no category folder
    assert derive_category(Path("/data/top.pdf"), data_root) == "general"


def test_derive_source_uri_is_canonical_framework_scheme():
    uri = derive_source_uri("requirements_engineering", Path("/data/requirements_engineering/ireb_elicitation_summary.pdf"))
    assert uri == "framework://requirements_engineering/ireb_elicitation_summary"


def test_collect_files_only_picks_ingestible_extensions(tmp_path: Path):
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "page.html").write_text("x")
    (tmp_path / "note.htm").write_text("x")
    (tmp_path / "img.png").write_text("x")
    (tmp_path / "deck.pptx").write_text("x")
    (tmp_path / "doc.docx").write_text("x")
    sub = tmp_path / "saved_page_files"
    sub.mkdir()
    (sub / "script.js").write_text("x")
    (sub / "style.css").write_text("x")

    found = {p.name for p in collect_files(tmp_path)}
    assert found == {"a.pdf", "page.html", "note.htm"}


def test_ingest_extensions_are_pdf_and_html_only():
    assert frozenset({".pdf", ".html", ".htm"}) == INGEST_EXTENSIONS

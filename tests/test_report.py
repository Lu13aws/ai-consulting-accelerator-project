"""Unit test for the engagement report composer (pure, no DB)."""

from types import SimpleNamespace

from apps.consulting_api.services.engagement_service import build_report
from apps.consulting_api.services.report_render import render_docx, render_pdf


def _engagement(**overrides):
    base = {
        "title": "Onboarding too slow",
        "status": "concluded",
        "initial_input": "New hires take months to ramp up.",
        "initial_analysis": "## Problem Statement\nSlow onboarding.",
        "hypotheses": "### H1\nNo structured process.",
        "open_questions": "How many hires?",
        "answers": None,
        "refined_analysis": None,
        "requirements": "## Classification\n- Goal: faster onboarding",
        "assessment": "## Assessment\nBottleneck is process.",
        "extras": {"roadmap": "## Roadmap\nNow / Next / Later"},
        "turns": [
            {"answers": "50/year", "findings": "Refined: process gap", "open_questions": "Budget?"},
        ],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_report_includes_all_sections():
    md = build_report(_engagement())
    assert md.startswith("# Onboarding too slow")
    assert "human review" in md  # draft disclaimer
    for heading in (
        "## Situation",
        "## Initial Analysis",
        "## Hypotheses",
        "## Round 1 — Answers",
        "## Round 1 — Updated Findings",
        "## Requirements",
        "## Consultant's Assessment",
        "## Roadmap",
    ):
        assert heading in md


def test_report_skips_empty_sections_and_legacy_fallback():
    # No turns + legacy refined_analysis present → legacy sections appear, no Round headings.
    md = build_report(
        _engagement(turns=[], answers="legacy answer", refined_analysis="legacy refined", extras={})
    )
    assert "## Round 1" not in md
    assert "## Refined Analysis" in md
    assert "## Roadmap" not in md  # extras empty → skipped


def test_render_docx_produces_a_word_file():
    data = render_docx(build_report(_engagement()))
    assert data[:2] == b"PK"  # .docx is a zip archive
    assert len(data) > 1000


def test_render_pdf_produces_a_pdf_file():
    # Includes German umlauts + an em-dash to exercise Latin-1 sanitisation.
    data = render_pdf("# Über — Onboarding\n\n## Ziele\n\n- **Schnell** ramping\n")
    assert data[:4] == b"%PDF"
    assert len(data) > 500


def test_render_pdf_handles_unbreakable_long_token():
    # A token wider than the page must not crash (wrapmode CHAR breaks it).
    data = render_pdf("## Link\n\n" + "x" * 400 + "\n")
    assert data[:4] == b"%PDF"

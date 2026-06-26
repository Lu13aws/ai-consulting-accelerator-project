"""Unit test for the engagement report composer (pure, no DB)."""

from types import SimpleNamespace

from apps.consulting_api.services.engagement_service import build_report


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

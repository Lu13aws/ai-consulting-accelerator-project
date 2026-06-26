"""Deterministic unit tests for the eval check functions (no LLM, no DB)."""

from apps.consulting_api.services.eval_checks import (
    check_citations,
    check_disclaimer,
    check_language,
    check_nonempty,
    check_sections,
    run_checks,
)
from apps.consulting_api.services.skills import DRAFT_DISCLAIMER

_EN = "## Problem Statement\nThe team is slow and the process is not defined. " + "word " * 50
_DE = "## Problemstellung\nDas Team ist langsam und der Prozess ist nicht definiert für uns. " + "wort " * 50


def test_nonempty():
    assert check_nonempty(_EN).passed
    assert not check_nonempty("too short").passed


def test_language_lock():
    assert check_language(_EN, "en").passed
    assert check_language(_DE, "de").passed
    assert not check_language(_EN, "de").passed  # English text, expected German → fail


def test_disclaimer():
    assert check_disclaimer(f"body\n\n{DRAFT_DISCLAIMER}").passed
    assert not check_disclaimer("body without the marker").passed


def test_sections():
    assert check_sections(_EN, ["## Problem Statement"]).passed
    assert not check_sections(_EN, ["## Missing Section"]).passed
    assert check_sections(_EN, None).passed  # skipped when none expected


def test_citations():
    assert check_citations("no markers here", 0).passed  # not citing is fine
    assert check_citations("grounded in [1] and [2].", 3).passed  # within range
    assert not check_citations("see [4]", 2).passed  # fabricated — only 2 sources
    assert not check_citations("see [1]", 0).passed  # cites with zero grounding


def test_run_checks_aggregates_all():
    results = run_checks(artifact=f"{_EN}\n\n{DRAFT_DISCLAIMER}", expected_lang="en", n_sources=0)
    assert {r.name for r in results} == {
        "nonempty", "language_lock", "disclaimer", "sections", "citations",
    }
    assert all(r.passed for r in results)

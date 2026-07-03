"""Deterministic unit tests for the eval check functions (no LLM, no DB)."""

from apps.consulting_api.services.eval_checks import (
    check_caveats,
    check_citations,
    check_confidence,
    check_disclaimer,
    check_language,
    check_nonempty,
    check_sections,
    check_structure,
    judge_min_score,
    parse_judge_scores,
    run_checks,
)
from apps.consulting_api.services.skills import DRAFT_DISCLAIMER

_EN = "## Problem Statement\nThe team is slow and the process is not defined.\n## Goals\n" + "word " * 50
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
    # skill-specific "AI-generated …" review/validation notices also count
    assert check_disclaimer(
        'body\n\n"AI-generated readiness assessment — findings require validation with leadership."'
    ).passed
    assert check_disclaimer('x\n\n"AI-generated value narrative — draft only."').passed
    assert not check_disclaimer("body without the marker").passed
    # "AI-generated" alone (no review/validation/draft clause) is not a disclaimer
    assert not check_disclaimer("AI-generated summary of the current situation.").passed


def test_sections():
    assert check_sections(_EN, ["## Problem Statement"]).passed
    assert not check_sections(_EN, ["## Missing Section"]).passed
    assert check_sections(_EN, None).passed  # skipped when none expected


def test_citations():
    assert check_citations("no markers here", 0).passed  # not citing is fine
    assert check_citations("grounded in [1] and [2].", 3).passed  # within range
    assert not check_citations("see [4]", 2).passed  # fabricated — only 2 sources
    assert not check_citations("see [1]", 0).passed  # cites with zero grounding


def test_structure():
    assert check_structure("## A\nbody\n## B\nmore").passed  # 2 headings
    assert check_structure("## Risks\n| a | b |\n| c | d |").passed  # 1 heading + table
    assert check_structure("- one\n- two\n- three").passed  # a list
    assert check_structure("**Top 3 Blockers**\ntext\n**Next Steps**\nmore").passed  # bold headers
    assert check_structure("1. Data — low\n2. Tech — medium\n3. Talent — low").passed  # numbered list
    assert not check_structure("just a wall of prose with no headings at all").passed


def test_caveats():
    assert check_caveats("This is a preliminary hypothesis to validate.", ["to validate", "vorläufig"]).passed
    assert check_caveats("Dies ist vorläufig.", ["to validate", "vorläufig"]).passed  # bilingual
    assert not check_caveats("Here is the definitive root cause.", ["to validate"]).passed
    assert check_caveats("anything", None).passed  # skipped when no phrases


def test_confidence():
    assert check_confidence("### H1\n**Confidence:** High\nevidence", required=True).passed
    assert not check_confidence("### H1\nno confidence label here", required=True).passed
    assert check_confidence("no label", required=False).passed  # skipped


def test_parse_judge_scores():
    raw = '```json\n{"groundedness": 4, "relevance": 5, "citation_faithfulness": 3, "rationale": "ok"}\n```'
    scores = parse_judge_scores(raw)
    assert scores == {"groundedness": 4, "relevance": 5, "citation_faithfulness": 3, "rationale": "ok"}
    assert parse_judge_scores("not json at all") == {}
    # clamps out-of-range and ignores junk values
    clamped = parse_judge_scores('{"groundedness": 9, "relevance": "x", "citation_faithfulness": 0}')
    assert clamped["groundedness"] == 5 and clamped["citation_faithfulness"] == 1
    assert "relevance" not in clamped


def test_judge_min_score():
    assert judge_min_score({"groundedness": 4, "relevance": 5, "citation_faithfulness": 3}) == 3
    assert judge_min_score({}) is None


def test_run_checks_aggregates_all():
    results = run_checks(artifact=f"{_EN}\n\n{DRAFT_DISCLAIMER}", expected_lang="en", n_sources=0)
    assert {r.name for r in results} == {
        "nonempty", "language_lock", "disclaimer", "structure", "sections", "caveats", "confidence",
    }
    assert all(r.passed for r in results)

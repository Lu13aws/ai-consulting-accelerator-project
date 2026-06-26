"""Rule-based quality checks for skill outputs (the eval harness).

Pure, deterministic functions — no LLM, no DB — so they are cheap and unit-testable.
The runner in `scripts/eval.py` produces the artifacts (the expensive part) and feeds
them here. Each check returns a CheckResult; a skill output "passes" when every check does.

These encode the non-negotiables from CLAUDE.md: output language is locked to the input
language, every artifact is marked as a draft, structured skills emit their defined
sections, and citations are never fabricated.
"""

import re
from dataclasses import dataclass

from apps.consulting_api.services.consulting_service import _detect_language
from apps.consulting_api.services.skills import DRAFT_DISCLAIMER


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def check_nonempty(artifact: str, min_len: int = 200) -> CheckResult:
    n = len(artifact.strip())
    return CheckResult("nonempty", n >= min_len, f"{n} chars (min {min_len})")


def check_language(artifact: str, expected_lang: str) -> CheckResult:
    """The output language must match the (expected) input language — the language lock."""
    got = _detect_language(artifact)
    return CheckResult("language_lock", got == expected_lang, f"expected {expected_lang}, got {got}")


def check_disclaimer(artifact: str) -> CheckResult:
    ok = DRAFT_DISCLAIMER in artifact
    return CheckResult("disclaimer", ok, "present" if ok else "draft disclaimer missing")


def check_sections(artifact: str, required: list[str] | None) -> CheckResult:
    """All expected Markdown headings are present (case-insensitive substring match)."""
    if not required:
        return CheckResult("sections", True, "skipped (no expected sections)")
    lowered = artifact.lower()
    missing = [s for s in required if s.lower() not in lowered]
    return CheckResult(
        "sections",
        not missing,
        f"missing {missing}" if missing else f"all {len(required)} present",
    )


def check_citations(artifact: str, n_sources: int) -> CheckResult:
    """No fabricated citations: every [n] marker must reference a retrieved source."""
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", artifact)}
    if not markers:
        return CheckResult("citations", True, "no citation markers")
    out_of_range = sorted(m for m in markers if m < 1 or m > n_sources)
    ok = not out_of_range
    return CheckResult(
        "citations",
        ok,
        f"cites {out_of_range} but only {n_sources} sources" if not ok else f"{len(markers)} marker(s), {n_sources} sources",
    )


def run_checks(
    *,
    artifact: str,
    expected_lang: str,
    n_sources: int,
    sections: list[str] | None = None,
) -> list[CheckResult]:
    return [
        check_nonempty(artifact),
        check_language(artifact, expected_lang),
        check_disclaimer(artifact),
        check_sections(artifact, sections),
        check_citations(artifact, n_sources),
    ]

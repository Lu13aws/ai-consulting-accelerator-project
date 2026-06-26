"""Quality eval harness for the consulting skills.

Runs a fixed set of golden cases (DE + EN) through the REAL skills (LLM + vector
store) and applies rule-based checks (see eval_checks.py): non-empty, language lock,
draft disclaimer, required sections, citation integrity. Prints a scorecard.

This calls the real LLM and costs ~cents per case — run it on demand (e.g. after a
prompt/version change), not in CI. Use --dry-run to list the cases without calling.

Usage:
    uv run python scripts/eval.py            # run all cases
    uv run python scripts/eval.py --dry-run  # list cases, no LLM calls
    uv run python scripts/eval.py --only problem-en,roadmap-en
"""

import argparse
import asyncio
import sys

from aiplatform.storage.database import get_async_session
from apps.consulting_api.api.schemas import StructureRequest
from apps.consulting_api.services.consulting_service import ConsultingService
from apps.consulting_api.services.eval_checks import run_checks

# Golden cases. `sections` (exact headings) only on EN cases — for DE the model
# translates the headings, so exact matching would be brittle.
CASES: list[dict] = [
    {
        "id": "problem-en",
        "skill": "consulting.structure-business-problem",
        "lang": "en",
        "inputs": {
            "problem_description": (
                "New hires take months to become productive; onboarding is ad-hoc "
                "and tribal knowledge is undocumented."
            )
        },
        "sections": ["## Problem Statement", "## Pain Points", "## Goals & Success Metrics", "## Scope Boundary"],
    },
    {
        "id": "problem-de",
        "skill": "consulting.structure-business-problem",
        "lang": "de",
        "inputs": {
            "problem_description": (
                "Neue Mitarbeitende brauchen Monate bis zur Produktivität; das Onboarding "
                "ist unstrukturiert und Wissen ist nicht dokumentiert."
            )
        },
    },
    {
        "id": "requirements-en",
        "skill": "consulting.structure-requirements",
        "lang": "en",
        "inputs": {
            "requirements": (
                "As a manager I want a dashboard. The system must be fast. Onboarding "
                "should take 4 weeks. Users need to track their progress."
            )
        },
    },
    {
        "id": "stakeholders-en",
        "skill": "consulting.analyze-stakeholders",
        "lang": "en",
        "inputs": {
            "project_description": "Rolling out a structured onboarding program across a 500-person company.",
            "known_stakeholders": "HR, team leads, new hires",
        },
        "sections": ["## Stakeholder Categories", "## RACI Matrix"],
    },
    {
        "id": "hypotheses-de",
        "skill": "consulting.generate-hypotheses",
        "lang": "de",
        "inputs": {
            "context": (
                "Neue Mitarbeitende brauchen Monate bis zur Produktivität; 70% des Wissens "
                "ist undokumentiert; es gibt keinen einheitlichen Prozess."
            )
        },
    },
    {
        "id": "open-questions-de",
        "skill": "consulting.open-questions",
        "lang": "de",
        "inputs": {
            "context": (
                "Ein Mittelständler möchte sein Onboarding beschleunigen, hat aber kein "
                "LMS und kein strukturiertes Mentoring."
            )
        },
    },
    {
        "id": "roadmap-en",
        "skill": "consulting.structure-roadmap",
        "lang": "en",
        "inputs": {
            "vision": "Every new hire is productive within 4 weeks.",
            "goals": "Reduce ramp time; standardize onboarding; capture tribal knowledge.",
        },
    },
    # ── language balance (DE variants of the EN-only structured skills) ──
    {
        "id": "requirements-de",
        "skill": "consulting.structure-requirements",
        "lang": "de",
        "inputs": {
            "requirements": (
                "Als Manager möchte ich ein Dashboard. Das System muss schnell sein. Das "
                "Onboarding soll vier Wochen dauern. Nutzer müssen ihren Fortschritt verfolgen."
            )
        },
    },
    {
        "id": "stakeholders-de",
        "skill": "consulting.analyze-stakeholders",
        "lang": "de",
        "inputs": {
            "project_description": "Einführung eines strukturierten Onboarding-Programms in einem Unternehmen mit 500 Mitarbeitenden.",
            "known_stakeholders": "Personalabteilung, Teamleitungen, neue Mitarbeitende",
        },
    },
    {
        "id": "roadmap-de",
        "skill": "consulting.structure-roadmap",
        "lang": "de",
        "inputs": {
            "vision": "Jede neu eingestellte Person ist innerhalb von vier Wochen produktiv.",
            "goals": "Einarbeitungszeit verkürzen; Onboarding standardisieren; implizites Wissen dokumentieren.",
        },
    },
    # ── confidence ranking (EN — 'Confidence:' label is reliable in English) ──
    {
        "id": "hypotheses-en",
        "skill": "consulting.generate-hypotheses",
        "lang": "en",
        "confidence": True,
        "inputs": {
            "context": (
                "New hires take months to become productive; 70% of knowledge is "
                "undocumented; there is no consistent process."
            )
        },
    },
    # ── consultant-assessment (most at risk of drifting into prescriptive advice) ──
    {
        "id": "assessment-en",
        "skill": "consulting.consultant-assessment",
        "lang": "en",
        "inputs": {
            "context": (
                "New hires take months to ramp up. ~50 hires/year. 70% of knowledge "
                "undocumented. No LMS, informal mentoring. Managers want a dashboard."
            )
        },
        "sections": ["## Prioritisation", "## Validate Before Solutioning"],
    },
    {
        "id": "assessment-de",
        "skill": "consulting.consultant-assessment",
        "lang": "de",
        "inputs": {
            "context": (
                "Neue Mitarbeitende brauchen Monate. ~50 Einstellungen/Jahr. 70% des Wissens "
                "undokumentiert. Kein LMS, informelles Mentoring. Führungskräfte wünschen ein Dashboard."
            )
        },
    },
    # ── remaining discovery skills (coverage) ──
    {
        "id": "risks-en",
        "skill": "consulting.identify-risks",
        "lang": "en",
        "inputs": {
            "context": (
                "A 500-person company is rolling out a new structured onboarding program "
                "over 6 months with a small HR team and no LMS."
            )
        },
    },
    {
        "id": "assumptions-en",
        "skill": "consulting.detect-assumptions",
        "lang": "en",
        "inputs": {
            "context": (
                "We will cut onboarding time to 4 weeks by introducing a mentoring program "
                "and a knowledge base."
            )
        },
    },
    {
        "id": "interview-guide-en",
        "skill": "consulting.interview-guide",
        "lang": "en",
        "inputs": {
            "context": "Discovery interviews with team leads about why new hires take so long to become productive."
        },
    },
]

# Preliminary-framing markers per skill (bilingual). A passing output hedges with at
# least one — guards the "AI assists, does not decide" discipline (see check_caveats).
SKILL_CAVEATS: dict[str, list[str]] = {
    "consulting.structure-business-problem": [
        "to validate", "to be validated", "hypothesis", "preliminary",
        "zu validieren", "zu bestätigen", "hypothese", "vorläufig", "annahme",
    ],
    "consulting.consultant-assessment": [
        "preliminary", "to validate", "validate", "not a decision",
        "vorläufig", "validieren", "zu validieren", "keine entscheidung",
    ],
    "consulting.structure-requirements": [
        "to validate", "suggested", "to be validated",
        "zu validieren", "vorgeschlagen", "vorschlag",
    ],
    "consulting.detect-assumptions": [
        "assumption", "validate", "annahme", "validieren", "überprüfen", "zu prüfen",
    ],
}

_GREEN, _RED, _DIM, _RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


async def _run_case(case: dict) -> tuple[list, int, int]:
    async with get_async_session() as session:
        service = ConsultingService(session)
        resp = await service.structure_artifact(
            StructureRequest(skill=case["skill"], inputs=case["inputs"], top_k=case.get("top_k", 6))
        )
    results = run_checks(
        artifact=resp.artifact,
        expected_lang=case["lang"],
        n_sources=len(resp.sources),
        sections=case.get("sections"),
        caveats=SKILL_CAVEATS.get(case["skill"]),
        needs_confidence=case.get("confidence", False),
    )
    return results, len(resp.sources), resp.input_tokens + resp.output_tokens


async def main(only: set[str] | None) -> int:
    cases = [c for c in CASES if not only or c["id"] in only]
    print(f"Running {len(cases)} eval case(s)...\n")
    total_checks = passed_checks = failed_cases = total_tokens = 0

    for case in cases:
        try:
            results, n_sources, tokens = await _run_case(case)
        except Exception as exc:  # noqa: BLE001 — report, don't abort the whole run
            failed_cases += 1
            print(f"{_RED}FAIL {case['id']}{_RESET}  ERROR: {exc}\n")
            continue
        total_tokens += tokens
        case_failed = False
        print(f"{case['id']}  ({case['skill']}, {case['lang']}, {n_sources} sources, {tokens} tok)")
        for r in results:
            total_checks += 1
            if r.passed:
                passed_checks += 1
                print(f"  {_GREEN}PASS{_RESET} {r.name:<14} {_DIM}{r.detail}{_RESET}")
            else:
                case_failed = True
                print(f"  {_RED}FAIL {r.name:<14} {r.detail}{_RESET}")
        failed_cases += int(case_failed)
        print()

    print("-" * 60)
    print(f"Checks: {passed_checks}/{total_checks} passed | "
          f"Cases: {len(cases) - failed_cases}/{len(cases)} clean | ~{total_tokens} tokens")
    return 1 if failed_cases else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the consulting skill quality eval harness.")
    parser.add_argument("--dry-run", action="store_true", help="List cases without calling the LLM.")
    parser.add_argument("--only", help="Comma-separated case ids to run (default: all).")
    args = parser.parse_args()
    only_ids = {s.strip() for s in args.only.split(",")} if args.only else None

    if args.dry_run:
        for c in CASES:
            if not only_ids or c["id"] in only_ids:
                secs = len(c.get("sections", []))
                print(f"{c['id']:<18} {c['skill']:<40} lang={c['lang']} sections={secs}")
        sys.exit(0)

    sys.exit(asyncio.run(main(only_ids)))

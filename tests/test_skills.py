"""Unit tests for the structuring skills registry (no DB / no LLM)."""

import pytest
from apps.consulting_api.services.skills import (
    DRAFT_DISCLAIMER,
    SKILLS,
    StructuringSkill,
    get_skill,
)

EXPECTED_SKILLS = {
    "consulting.structure-business-problem",
    "consulting.structure-requirements",
    "consulting.analyze-stakeholders",
}


def test_all_expected_skills_registered():
    assert set(SKILLS) == EXPECTED_SKILLS


def test_get_skill_returns_registered_skill():
    skill = get_skill("consulting.structure-business-problem")
    assert isinstance(skill, StructuringSkill)
    assert skill.name == "consulting.structure-business-problem"


def test_get_skill_unknown_raises_valueerror_listing_available():
    with pytest.raises(ValueError) as exc:
        get_skill("consulting.does-not-exist")
    # The error lists the available skills so the API surface is discoverable
    assert "consulting.structure-business-problem" in str(exc.value)


@pytest.mark.parametrize("skill", SKILLS.values(), ids=lambda s: s.name)
def test_skill_contract_is_well_formed(skill: StructuringSkill):
    assert skill.name.startswith("consulting.")
    assert skill.version  # non-empty, e.g. "1.0"
    assert skill.description
    assert skill.required_fields, "every skill must declare at least one required field"
    assert skill.system_prompt.strip()
    assert skill.retrieval_seed.strip()


@pytest.mark.parametrize("skill", SKILLS.values(), ids=lambda s: s.name)
def test_system_prompt_enforces_language_and_disclaimer(skill: StructuringSkill):
    prompt = skill.system_prompt.lower()
    # Language fidelity is a hard requirement (CLAUDE.md principle #6)
    assert "language" in prompt
    # The prompt instructs the model to emit the draft disclaimer
    assert "disclaimer" in prompt


def test_draft_disclaimer_marks_output_as_review_draft():
    assert "draft" in DRAFT_DISCLAIMER.lower()
    assert "human review" in DRAFT_DISCLAIMER.lower()

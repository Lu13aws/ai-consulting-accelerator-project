"""
Structuring skills registry — procedural memory.

Each skill is a NAMED, VERSIONED capability with an explicit input/output
contract. Skills are invoked by name (never retrieved by similarity), per the
Memory Architecture section of CLAUDE.md.

To add a skill: append a StructuringSkill to SKILLS. Bump `version` whenever the
system_prompt or contract changes (v1.0 -> v1.1).
"""

from dataclasses import dataclass, field

DRAFT_DISCLAIMER = "_AI-generated draft — requires human review. This is a starting point, not a final deliverable._"


@dataclass(frozen=True)
class StructuringSkill:
    name: str
    version: str
    description: str
    required_fields: list[str]
    optional_fields: list[str] = field(default_factory=list)
    # Anchor query used to retrieve grounding chunks from the consulting corpus.
    retrieval_seed: str = ""
    system_prompt: str = ""


_BUSINESS_PROBLEM = StructuringSkill(
    name="consulting.structure-business-problem",
    version="1.2",
    description=(
        "Structures a free-text business problem into an IREB/BABOK-aligned problem "
        "statement (Problem Statement, Root Cause, Affected Stakeholders, Business "
        "Impact, Scope Boundary)."
    ),
    required_fields=["problem_description"],
    optional_fields=["additional_context"],
    retrieval_seed=(
        "business problem definition, business need, root cause analysis, affected "
        "stakeholders, business impact, scope boundary in scope out of scope, IREB BABOK"
    ),
    system_prompt="""\
You are a consulting assistant that structures a raw business problem into a clear,
IREB/BABOK-aligned problem definition. You do not invent facts: build only on the
user's input, using the provided framework context to ground terminology and method.

LANGUAGE (most important rule): Write the ENTIRE output — every heading and label — in
the SAME language as the user's problem description. Never switch languages (the
framework context may be in another language than the input; always follow the INPUT
language). The headings listed below are written in English only as a template; if the
user's input is in another language, translate all of them into that language.

Produce GitHub-flavored Markdown with EXACTLY these sections, in this order (with
headings in the user's language):

## Problem Statement
## Root Cause
## Affected Stakeholders
## Business Impact
## Scope Boundary
### In Scope
### Out of Scope

Rules:
- Use only information present in the user's input. Where the input is insufficient
  for a section, write a brief note (in the user's language) such as "_Not enough
  information provided — to be clarified with stakeholders._" instead of guessing.
- Where a statement reflects a framework concept, cite the relevant source using its
  [1], [2], … label from the context.
- End the output with the draft disclaimer provided to you, on its own line.
- Be concise and practitioner-oriented; bullet points over paragraphs.\
""",
)


_REQUIREMENTS = StructuringSkill(
    name="consulting.structure-requirements",
    version="1.1",
    description=(
        "Reformats raw/unstructured requirements into INVEST-compliant user stories "
        "with acceptance criteria, and flags ambiguous, incomplete or conflicting "
        "requirements against IREB quality criteria."
    ),
    required_fields=["requirements"],
    optional_fields=["context"],
    retrieval_seed=(
        "INVEST user stories acceptance criteria requirements quality criteria "
        "unambiguous complete consistent verifiable testable atomic IREB requirement "
        "documentation user story acceptance criteria"
    ),
    system_prompt="""\
You are a consulting assistant that turns raw, unstructured requirements into
INVEST-compliant user stories with acceptance criteria. You do not invent scope:
build only on the user's input, using the provided framework context to ground the
quality criteria and terminology.

LANGUAGE (most important rule): Write the ENTIRE output — every heading and label —
in the SAME language as the user's requirements. Never switch languages (the framework
context may be in another language than the input; always follow the INPUT language).
The headings listed below are written in English only as a template; if the user's
input is in another language, translate all of them into that language.

Produce GitHub-flavored Markdown with these sections, in this order (with headings in
the user's language):

## User Stories
For each story use this shape:
### US-<n>: <short title>
**Story:** As a <role>, I want <goal>, so that <benefit>.
**Acceptance Criteria:**
- <criterion 1>
- <criterion 2>
**INVEST note:** <only if the story violates an INVEST property — name it briefly; otherwise omit this line>

## Flags & Quality Issues
- List each requirement that is ambiguous, incomplete, conflicting, or untestable.
  Name the specific IREB quality criterion it violates (e.g. unambiguous, complete,
  consistent, verifiable, atomic) and cite the relevant source with its [1], [2], …
  label from the context where applicable.

Rules:
- Derive stories ONLY from the user's input. Do not add features that were not stated.
- If a requirement is too vague to turn into a story, do NOT fabricate one — list it
  under Flags & Quality Issues instead.
- End the output with the draft disclaimer provided to you, on its own line.
- Be concise and practitioner-oriented; bullet points over paragraphs.\
""",
)


_STAKEHOLDERS = StructuringSkill(
    name="consulting.analyze-stakeholders",
    version="1.1",
    description=(
        "Analyses a project and its known stakeholders: suggests missing stakeholder "
        "categories, a RACI matrix skeleton, and engagement levels, grounded in the "
        "BABOK stakeholder analysis knowledge area."
    ),
    required_fields=["project_description", "known_stakeholders"],
    optional_fields=["context"],
    retrieval_seed=(
        "BABOK stakeholder analysis knowledge area stakeholder list onion diagram "
        "RACI responsible accountable consulted informed engagement levels stakeholder "
        "categories roles influence interest"
    ),
    system_prompt="""\
You are a consulting assistant that performs an initial stakeholder analysis,
grounded in the BABOK stakeholder analysis knowledge area. You do not invent facts:
build on the user's project description and known stakeholders, using the provided
framework context to ground categories, RACI and engagement concepts.

LANGUAGE (most important rule): Write the ENTIRE output — every heading, label and
table header — in the SAME language as the user's input. Never switch languages. The
headings listed below are written in English only as a template; if the user's input
is in another language, translate all of them (and the RACI column labels) into that
language.

Produce GitHub-flavored Markdown with these sections, in this order (with headings in
the user's language):

## Stakeholder Categories
- List the known stakeholders, grouped sensibly.
- Then, under a clear sub-label, SUGGEST stakeholder categories that appear to be
  missing for a project of this kind (clearly marked as suggestions to verify).

## RACI Matrix (skeleton)
- A Markdown table: rows = stakeholders, columns = 3–5 key activities/decisions you
  derive from the project description.
- Fill cells with R, A, C, or I. Use them as a starting proposal, not fact. Ensure at
  most one A per activity where possible.

## Engagement Levels
- For each stakeholder, propose a current/target engagement level and a brief
  engagement approach.

Rules:
- Base the analysis on the user's input; where you propose additions, mark them
  explicitly as suggestions to validate with the team.
- Where a concept reflects the framework, cite the relevant source with its [1], [2],
  … label from the context.
- End the output with the draft disclaimer provided to you, on its own line.
- Be concise and practitioner-oriented.\
""",
)


SKILLS: dict[str, StructuringSkill] = {
    _BUSINESS_PROBLEM.name: _BUSINESS_PROBLEM,
    _REQUIREMENTS.name: _REQUIREMENTS,
    _STAKEHOLDERS.name: _STAKEHOLDERS,
}


def get_skill(name: str) -> StructuringSkill:
    skill = SKILLS.get(name)
    if skill is None:
        available = ", ".join(sorted(SKILLS)) or "(none registered)"
        raise ValueError(f"Unknown skill '{name}'. Available skills: {available}")
    return skill

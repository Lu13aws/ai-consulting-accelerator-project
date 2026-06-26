"""
Structuring skills registry — procedural memory.

Each skill is a NAMED, VERSIONED capability with an explicit input/output
contract. Skills are invoked by name (never retrieved by similarity), per the
Memory Architecture section of CLAUDE.md.

Skills are grouped into product layers via `layer` (discovery | analysis | delivery)
— a taxonomy for the UI, not separate systems.

To add a skill: append a StructuringSkill to SKILLS. Bump `version` whenever the
system_prompt or contract changes (v1.0 -> v1.1).
"""

from dataclasses import dataclass, field

DRAFT_DISCLAIMER = "_AI-generated draft — requires human review. This is a starting point, not a final deliverable._"

# Shared, hardened language rule. Functional/abstract (no language-specific example
# sentences) so the output language always follows the INPUT, never the (possibly
# differently-languaged) framework context.
_LANG_RULE = """\
LANGUAGE — THIS OVERRIDES EVERYTHING ELSE: Write the COMPLETE output — every heading,
label and sentence — in the language stated in the user message ("Write the entire
response in …"). The section names below are an English layout template; render them in
that exact target language. Never switch to, translate into, or mix in any OTHER
language (the framework context may be in a different language — ignore that)."""


@dataclass(frozen=True)
class StructuringSkill:
    name: str
    version: str
    description: str
    required_fields: list[str]
    optional_fields: list[str] = field(default_factory=list)
    layer: str = "analysis"  # discovery | analysis | delivery
    # Anchor query used to retrieve grounding chunks from the consulting corpus.
    retrieval_seed: str = ""
    system_prompt: str = ""


# ── Discovery layer ───────────────────────────────────────────────────────────

_BUSINESS_PROBLEM = StructuringSkill(
    name="consulting.structure-business-problem",
    version="1.3",
    description=(
        "Structures a free-text business problem into an IREB/BABOK-aligned analysis "
        "(current/target state, pain points, goals, success metrics, root cause, "
        "stakeholders, impact, scope)."
    ),
    required_fields=["problem_description"],
    optional_fields=["additional_context"],
    layer="discovery",
    retrieval_seed=(
        "business problem definition business need current state target state pain points "
        "business goals success metrics root cause affected stakeholders business impact "
        "scope boundary in scope out of scope IREB BABOK"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that structures a raw business problem into a clear,
IREB/BABOK-aligned problem definition. Build ONLY on the user's input; use the framework
context to ground terminology. Where a statement reflects a framework concept, cite it
with its [1], [2], … label. Where the input is insufficient for a section, write a brief
note (in the user's language) such as "_Not enough information provided — to be
clarified._" instead of guessing.

Produce GitHub-flavored Markdown with these sections (headings translated):

## Problem Statement
## Current State
## Target State
## Pain Points
## Business Goals
## Success Metrics
## Root Cause
## Affected Stakeholders
## Business Impact
## Scope Boundary
### In Scope
### Out of Scope

End the output with the draft disclaimer provided to you, on its own line. Be concise;
bullet points over paragraphs.""",
)


_STAKEHOLDERS = StructuringSkill(
    name="consulting.analyze-stakeholders",
    version="1.2",
    description=(
        "Initial stakeholder analysis: role categories, RACI skeleton, influence/interest "
        "classification, engagement levels and a communication plan (BABOK)."
    ),
    required_fields=["project_description", "known_stakeholders"],
    optional_fields=["context"],
    layer="discovery",
    retrieval_seed=(
        "BABOK stakeholder analysis knowledge area stakeholder list onion diagram RACI "
        "responsible accountable consulted informed engagement levels influence interest "
        "grid communication plan business owner product owner sponsor data owner"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant performing an initial stakeholder analysis grounded in the
BABOK stakeholder analysis knowledge area. Build on the user's input; mark proposed
additions as suggestions to validate. Cite [1], [2], … where a concept reflects the framework.

Produce GitHub-flavored Markdown with these sections (headings AND table headers translated):

## Stakeholder Categories
- Group the known stakeholders by role (e.g. Business Owner, Product Owner, Project Sponsor,
  Data Owner, Power User, End User) and SUGGEST missing categories (marked as suggestions).
## RACI Matrix (skeleton)
- A Markdown table: rows = stakeholders, columns = 3–5 key activities/decisions derived from
  the input; cells R, A, C or I; at most one A per activity where possible.
## Influence / Interest
- Classify each stakeholder as high/low influence × high/low interest, with the engagement
  implication (manage closely / keep satisfied / keep informed / monitor).
## Engagement Levels
- For each stakeholder, a current/target engagement level and a brief approach.
## Communication Plan
- A short table: stakeholder (or group), what to communicate, frequency, channel.

End the output with the draft disclaimer provided to you, on its own line. Be concise.""",
)


_RISKS = StructuringSkill(
    name="consulting.identify-risks",
    version="1.0",
    description="Identifies project/solution risks: Risk, Impact, Probability, Recommendation.",
    required_fields=["context"],
    layer="discovery",
    retrieval_seed=(
        "risk register risk impact probability likelihood mitigation recommendation project "
        "risks dependencies assumptions delivery risk"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that identifies risks from a project or problem description.
Build on the user's input; reasonable inferred risks are allowed but phrase them as
"potential" and do not invent specifics.

Produce a GitHub-flavored Markdown table (headings/headers translated) with the columns:
Risk · Impact · Probability · Recommendation. Use High / Medium / Low for Impact and
Probability. Group rows by theme (e.g. technical, organizational, data, delivery) if helpful.

End the output with the draft disclaimer provided to you, on its own line. Be concise.""",
)


_ASSUMPTIONS = StructuringSkill(
    name="consulting.detect-assumptions",
    version="1.0",
    description="Surfaces the implicit assumptions behind a project, each marked as an assumption to validate.",
    required_fields=["context"],
    layer="discovery",
    retrieval_seed=(
        "assumptions implicit premises preconditions dependencies to validate constraints"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that surfaces the IMPLICIT assumptions behind a project or
problem description. List each as a bullet phrased as an explicit assumption (e.g. "We
assume that …"), grouped sensibly (e.g. Business, Technical, Organizational, Data). Every
item is an assumption to validate — never present them as established facts.

Translate all headings into the user's language. End the output with the draft disclaimer
provided to you, on its own line. Be concise.""",
)


_OPEN_QUESTIONS = StructuringSkill(
    name="consulting.open-questions",
    version="1.0",
    description="Generates the clarification questions to ask before designing a solution.",
    required_fields=["context"],
    layer="discovery",
    retrieval_seed=(
        "open questions clarification discovery scope users volume data budget timeline "
        "compliance security integrations success criteria elicitation"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that lists the clarification questions a consultant should
ask before designing a solution, based on the GAPS in the user's description. Group the
questions by theme (e.g. Scope, Users & Volume, Data, Integrations, Compliance & Security,
Budget & Timeline, Success Criteria). Only ask questions whose answers are missing from the
input — do not ask what the input already answers.

Translate all headings into the user's language. End the output with the draft disclaimer
provided to you, on its own line. Be concise.""",
)


_HYPOTHESES = StructuringSkill(
    name="consulting.generate-hypotheses",
    version="1.0",
    description="Generates explicitly-labelled root-cause hypotheses when the cause is not yet known.",
    required_fields=["context"],
    layer="discovery",
    retrieval_seed=(
        "root cause hypotheses possible causes investigation diagnosis five whys analysis "
        "single source of truth data quality process"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that generates plausible ROOT-CAUSE HYPOTHESES for a problem
whose true cause is not yet known. For each hypothesis provide: a one-line statement, why it
is plausible (from the input), and how to test/validate it. Every item is explicitly a
HYPOTHESIS, not a conclusion. Order by likelihood only if the input justifies it.

Translate all headings into the user's language. End the output with the draft disclaimer
provided to you, on its own line. Be concise; bullet points over paragraphs.""",
)


_INTERVIEW_GUIDE = StructuringSkill(
    name="consulting.interview-guide",
    version="1.0",
    description="Produces a stakeholder discovery interview guide, grounded in requirements elicitation.",
    required_fields=["context"],
    layer="discovery",
    retrieval_seed=(
        "interview guide discovery questions requirements elicitation stakeholder interview "
        "IREB elicitation techniques current process pain points goals"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that produces a discovery INTERVIEW GUIDE for the project in
the user's description, grounded in requirements-elicitation practice. Provide a short
opening, then questions grouped by topic (e.g. Current Process, Pain Points, Goals &
Success, Data & Systems, Constraints, Stakeholders). If specific stakeholder roles are
mentioned, add a few role-specific questions. Cite [1], [2], … where a technique reflects
the framework context.

Translate all headings into the user's language. End the output with the draft disclaimer
provided to you, on its own line. Be concise.""",
)


# ── Analysis layer ────────────────────────────────────────────────────────────

_REQUIREMENTS = StructuringSkill(
    name="consulting.structure-requirements",
    version="1.3",
    description=(
        "Classifies raw requirements by type (business/functional/non-functional/constraint/"
        "assumption/risk/open question/…), writes INVEST user stories for functional ones, "
        "and flags quality issues against IREB criteria."
    ),
    required_fields=["requirements"],
    optional_fields=["context"],
    layer="analysis",
    retrieval_seed=(
        "requirement classification business functional non-functional constraint assumption "
        "risk open question out of scope INVEST user stories acceptance criteria IREB quality "
        "unambiguous complete consistent verifiable atomic"
    ),
    system_prompt=f"""\
{_LANG_RULE}

You are a consulting assistant that classifies and structures raw requirements, grounded in
IREB. Build ONLY on the user's input; do not invent scope.

Produce GitHub-flavored Markdown with these sections (headings translated):

Section 1 — a "Requirement Classification" heading: group the user's items by type —
Business Requirement, Functional Requirement, Non-functional Requirement, Constraint,
Assumption, Risk, Open Question, Future Requirement, Out of Scope. Include only the groups
that actually apply; list items as bullets under each.

Section 2 — a "User Stories" heading: for the FUNCTIONAL requirements, write INVEST user
stories. For each: "US-<n>: <short title>", a single role/goal/benefit sentence,
acceptance-criteria bullets, and an INVEST-note line ONLY if a story violates an INVEST
property (keep "INVEST" as-is).

Section 3 — a "Quality Issues" heading: flag ambiguous, incomplete, conflicting or
untestable items; name the specific IREB quality criterion (unambiguous, complete,
consistent, verifiable, atomic) and cite [1], [2], … where applicable.

End the output with the draft disclaimer provided to you, on its own line. Be concise.""",
)


# ── Delivery layer ────────────────────────────────────────────────────────────

_ROADMAP = StructuringSkill(
    name="consulting.structure-roadmap",
    version="1.0",
    description=(
        "Turns a product/project vision into a Now / Next / Later roadmap plus an agile "
        "backlog (Epic -> Feature -> User Story with acceptance criteria and MoSCoW "
        "priority), grounded in roadmapping practice and Scrum/agile frameworks."
    ),
    required_fields=["vision", "goals"],
    optional_fields=["known_scope", "constraints", "target_users"],
    layer="delivery",
    retrieval_seed=(
        "roadmap roadmapping now next later horizons themes initiatives priorisierung "
        "product backlog epic feature user story acceptance criteria MoSCoW must should "
        "could sprint agile scrum"
    ),
    system_prompt="""\
LANGUAGE — THIS OVERRIDES EVERYTHING ELSE: First detect the language of the user's
input below and write the COMPLETE output in that exact language — headings, titles,
descriptions, the role/goal/benefit sentence, and the acceptance criteria. The layout
below is a structure template, NOT a language instruction. Keep only established
terms as-is (Epic, Feature, User Story, Backlog, MoSCoW, and the horizon labels
Now / Next / Later); write everything else in the user's language. Do not otherwise
mix languages. The framework context may be in another language than the input —
always follow the INPUT language.

You are a consulting assistant that turns a product/project vision into (1) a roadmap
on the Now / Next / Later horizons and (2) an agile backlog. Build ONLY on the user's
input, using the provided framework context (roadmapping practice + Scrum/agile) to
ground method and terminology. Cite a source with its [1], [2], … label where a
statement reflects the context.

Produce GitHub-flavored Markdown:

Section 1 — a top-level heading for the roadmap. Under it, three sub-sections labelled
"Now", "Next", "Later". In each, list the initiatives/themes that belong there
(derived from the goals and scope) as short bullets. Do NOT invent calendar dates; use
only the relative horizons unless the user gave concrete timing.

Section 2 — a top-level heading for the backlog, as a nested hierarchy:
  - Epics at the top level; for each Epic note which roadmap horizon it maps to.
    - Features under each Epic.
      - User Stories under each Feature: one sentence in the role/goal/benefit form,
        then a short acceptance-criteria list, then a MoSCoW priority
        (Must / Should / Could / Won't).

Rules:
- Derive everything ONLY from the user's input; mark anything you infer as an
  assumption to validate. Do not fabricate scope, dates, or estimates.
- Keep it a focused draft: roughly 3–5 epics with a few features each and only the
  most important user stories — not exhaustive.
- End the output with the draft disclaimer provided to you, on its own line.
- Be concise; bullet points over paragraphs.\
""",
)


SKILLS: dict[str, StructuringSkill] = {
    s.name: s
    for s in (
        _BUSINESS_PROBLEM,
        _STAKEHOLDERS,
        _RISKS,
        _ASSUMPTIONS,
        _OPEN_QUESTIONS,
        _HYPOTHESES,
        _INTERVIEW_GUIDE,
        _REQUIREMENTS,
        _ROADMAP,
    )
}


def get_skill(name: str) -> StructuringSkill:
    skill = SKILLS.get(name)
    if skill is None:
        available = ", ".join(sorted(SKILLS)) or "(none registered)"
        raise ValueError(f"Unknown skill '{name}'. Available skills: {available}")
    return skill

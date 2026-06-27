"""
API smoke + validation tests using FastAPI's TestClient.

These cover the paths that do NOT call the LLM or the DB: health, the skills
listing, and the request-validation failures (unknown skill / missing required
field) which are rejected before any embedding or DB access. The DB session
dependency is overridden so no real database is required.
"""

import pytest
from aiplatform.storage.database import get_session
from apps.consulting_api.main import app
from apps.consulting_api.storage.engagement_db import get_engagement_session
from fastapi.testclient import TestClient


def _no_db_session():
    # The tested paths never touch the session; yield None to satisfy the dependency.
    yield None


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = _no_db_session
    app.dependency_overrides[get_engagement_session] = _no_db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "app": "consulting"}


def test_list_skills_returns_all_skills(client):
    resp = client.get("/api/v1/skills")
    assert resp.status_code == 200
    body = resp.json()
    assert body["skill_count"] == 13
    names = {s["name"] for s in body["skills"]}
    assert {
        "consulting.structure-business-problem",
        "consulting.structure-requirements",
        "consulting.analyze-stakeholders",
        "consulting.structure-roadmap",
        "consulting.identify-risks",
        "consulting.detect-assumptions",
        "consulting.open-questions",
        "consulting.generate-hypotheses",
        "consulting.interview-guide",
        "consulting.refine-analysis",
        "consulting.consultant-assessment",
        "consulting.match-patterns",
        "consulting.relevant-knowledge",
    } == names
    # Input contract + layer are exposed for the UI
    for s in body["skills"]:
        assert s["required_fields"]
        assert s["version"]
        assert s["layer"] in {"discovery", "analysis", "delivery"}


def test_structure_unknown_skill_returns_422(client):
    resp = client.post(
        "/api/v1/structure",
        json={"skill": "consulting.nope", "inputs": {"problem_description": "x"}},
    )
    assert resp.status_code == 422
    assert "Unknown skill" in resp.json()["detail"]


def test_structure_missing_required_field_returns_422(client):
    resp = client.post(
        "/api/v1/structure",
        json={
            "skill": "consulting.structure-business-problem",
            "inputs": {"additional_context": "only optional provided"},
        },
    )
    assert resp.status_code == 422
    assert "problem_description" in resp.json()["detail"]


def test_structure_empty_required_field_returns_422(client):
    resp = client.post(
        "/api/v1/structure",
        json={
            "skill": "consulting.structure-business-problem",
            "inputs": {"problem_description": "   "},
        },
    )
    assert resp.status_code == 422


# ── /api/v1/consulting/* alias routes — request validation (no LLM/DB) ──────────

def test_consulting_query_requires_question(client):
    # Missing body field -> Pydantic 422 before the route logic runs.
    assert client.post("/api/v1/consulting/query", json={}).status_code == 422
    assert client.post("/api/v1/consulting/query", json={"question": ""}).status_code == 422


def test_consulting_structure_problem_requires_description(client):
    assert client.post("/api/v1/consulting/structure/problem", json={}).status_code == 422


def test_consulting_structure_requirements_requires_text(client):
    assert client.post("/api/v1/consulting/structure/requirements", json={}).status_code == 422


def test_consulting_roadmap_requires_vision_and_goals(client):
    # vision alone is not enough — goals is also required.
    resp = client.post("/api/v1/consulting/structure/roadmap", json={"vision": "An app"})
    assert resp.status_code == 422


def test_consulting_stakeholders_requires_input(client):
    assert client.post("/api/v1/consulting/stakeholders", json={}).status_code == 422


def test_consulting_routes_exist(client):
    # A GET on a POST-only route returns 405 (route exists), not 404.
    assert client.get("/api/v1/consulting/query").status_code == 405


# ── Engagement routes (Phase 2) — request validation (no LLM/DB) ──────────────

def test_engagement_create_requires_input(client):
    assert client.post("/api/v1/consulting/engagements", json={}).status_code == 422
    assert client.post("/api/v1/consulting/engagements", json={"input": ""}).status_code == 422


def test_engagement_answer_requires_answers(client):
    eid = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/v1/consulting/engagements/{eid}/answer", json={}).status_code == 422


def test_engagement_answer_rejects_bad_uuid(client):
    # A non-UUID path segment fails path validation (422), proving the route is wired.
    resp = client.post("/api/v1/consulting/engagements/not-a-uuid/answer", json={"answers": "x"})
    assert resp.status_code == 422


def test_engagement_generate_requires_tool(client):
    eid = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/v1/consulting/engagements/{eid}/generate", json={}).status_code == 422


def test_engagement_conclude_route_wired(client):
    # POST-only conclude route exists (bad UUID → 422 path validation, not 404).
    assert client.post("/api/v1/consulting/engagements/not-a-uuid/conclude").status_code == 422


def test_engagement_report_rejects_unknown_format(client):
    eid = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/api/v1/consulting/engagements/{eid}/report?format=xlsx")
    assert resp.status_code == 422
    assert "Unknown format" in resp.json()["detail"]


def test_engagement_update_rejects_bad_uuid(client):
    assert client.patch("/api/v1/consulting/engagements/not-a-uuid", json={"title": "x"}).status_code == 422


def test_engagement_delete_rejects_bad_uuid(client):
    assert client.delete("/api/v1/consulting/engagements/not-a-uuid").status_code == 422

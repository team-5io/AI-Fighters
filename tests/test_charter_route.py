from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.charter import LLMCharterRule

client = TestClient(app)


def _override_get_db(fake_db):
    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db


def teardown_function():
    app.dependency_overrides.clear()


def _fake_rule(**overrides):
    rule = MagicMock()
    rule.id = overrides.get("id", uuid4())
    rule.title = overrides.get("title", "리뷰 SLA")
    rule.description = overrides.get("description", "24시간 이내 리뷰")
    rule.status = overrides.get("status", "draft")
    return rule


@patch("app.api.routes.charter.create_draft_rules")
@patch("app.api.routes.charter.call_charter_llm")
def test_generate_charter_returns_draft_rules(mock_llm, mock_create):
    _override_get_db(MagicMock())
    mock_llm.return_value = [LLMCharterRule(title="리뷰 SLA", description="24시간 이내 리뷰")]
    mock_create.return_value = [_fake_rule()]

    response = client.post("/api/ai/charter/generate", json={"teamId": str(uuid4())})

    assert response.status_code == 200
    body = response.json()
    assert len(body["rules"]) == 1
    assert body["rules"][0]["status"] == "draft"
    assert body["rules"][0]["title"] == "리뷰 SLA"


@patch("app.api.routes.charter.call_charter_llm")
def test_generate_charter_llm_failure_returns_502(mock_llm):
    _override_get_db(MagicMock())
    mock_llm.side_effect = RuntimeError("charter_generation_failed")

    response = client.post("/api/ai/charter/generate", json={"teamId": str(uuid4())})

    assert response.status_code == 502
    assert response.json() == {"error": "charter_generation_failed"}


@patch("app.api.routes.charter.update_rule_service")
@patch("app.api.routes.charter.get_rule")
def test_update_rule_returns_204_when_found(mock_get_rule, mock_update):
    _override_get_db(MagicMock())
    mock_get_rule.return_value = _fake_rule()

    response = client.patch(
        f"/api/ai/charter/rules/{uuid4()}",
        json={"title": "새 제목", "description": "새 설명"},
    )

    assert response.status_code == 204
    mock_update.assert_called_once()


@patch("app.api.routes.charter.get_rule")
def test_update_rule_returns_404_when_not_found(mock_get_rule):
    _override_get_db(MagicMock())
    mock_get_rule.return_value = None

    response = client.patch(
        f"/api/ai/charter/rules/{uuid4()}",
        json={"title": "새 제목", "description": "새 설명"},
    )

    assert response.status_code == 404


@patch("app.api.routes.charter.adopt_rules_service")
def test_adopt_rules_returns_204(mock_adopt):
    _override_get_db(MagicMock())
    team_id = uuid4()
    rule_ids = [uuid4(), uuid4()]
    adopted_by = uuid4()

    response = client.post(
        "/api/ai/charter/adopt",
        json={
            "teamId": str(team_id),
            "ruleIds": [str(r) for r in rule_ids],
            "adoptedBy": str(adopted_by),
        },
    )

    assert response.status_code == 204
    mock_adopt.assert_called_once()
    args = mock_adopt.call_args[0]
    assert args[1] == team_id
    assert args[3] == adopted_by


@patch("app.api.routes.charter.list_rules_service")
def test_list_rules_returns_rules_for_team(mock_list):
    _override_get_db(MagicMock())
    mock_list.return_value = [_fake_rule(status="adopted")]

    response = client.get(f"/api/ai/charter/rules?teamId={uuid4()}&status=adopted")

    assert response.status_code == 200
    body = response.json()
    assert len(body["rules"]) == 1
    assert body["rules"][0]["status"] == "adopted"

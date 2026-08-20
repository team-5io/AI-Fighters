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

    response = client.post("/api/ai/charter/generate", json={"teamId": 1})

    assert response.status_code == 200
    body = response.json()
    assert len(body["rules"]) == 1
    assert body["rules"][0]["status"] == "draft"
    assert body["rules"][0]["title"] == "리뷰 SLA"


@patch("app.api.routes.charter.call_charter_llm")
def test_generate_charter_llm_failure_returns_502(mock_llm):
    _override_get_db(MagicMock())
    mock_llm.side_effect = RuntimeError("charter_generation_failed")

    response = client.post("/api/ai/charter/generate", json={"teamId": 1})

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
    team_id = 1
    rule_ids = [uuid4(), uuid4()]
    adopted_by = uuid4()

    response = client.post(
        "/api/ai/charter/adopt",
        json={
            "teamId": team_id,
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

    response = client.get("/api/ai/charter/rules?teamId=1&status=adopted")

    assert response.status_code == 200
    body = response.json()
    assert len(body["rules"]) == 1
    assert body["rules"][0]["status"] == "adopted"


@patch("app.api.routes.charter.create_draft_rules")
@patch("app.api.routes.charter.call_charter_llm")
def test_generate_passes_locale_to_service(mock_llm, mock_create):
    _override_get_db(MagicMock())
    mock_llm.return_value = [LLMCharterRule(title="리뷰 SLA", description="24시간 이내 리뷰")]
    mock_create.return_value = [_fake_rule()]

    response = client.post("/api/ai/charter/generate", json={"teamId": 1, "locale": "ja"})

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["locale"] == "ja"


@patch("app.api.routes.charter.create_draft_rules")
@patch("app.api.routes.charter.call_charter_llm")
def test_generate_locale_is_optional(mock_llm, mock_create):
    _override_get_db(MagicMock())
    mock_llm.return_value = [LLMCharterRule(title="리뷰 SLA", description="24시간 이내 리뷰")]
    mock_create.return_value = [_fake_rule()]

    response = client.post("/api/ai/charter/generate", json={"teamId": 1})

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["locale"] is None


@patch("app.api.routes.charter.create_draft_rules")
@patch("app.api.routes.charter.call_charter_llm")
def test_generate_passes_locale_to_persistence(mock_llm, mock_create):
    """생성 시점 locale은 프롬프트에만 쓰이면 안 된다 — source_locale로 저장돼야 한다."""
    _override_get_db(MagicMock())
    mock_llm.return_value = [LLMCharterRule(title="리뷰 SLA", description="24시간 이내 리뷰")]
    mock_create.return_value = [_fake_rule()]

    client.post("/api/ai/charter/generate", json={"teamId": 1, "locale": "ja"})

    assert mock_create.call_args.kwargs["locale"] == "ja"


@patch("app.api.routes.charter.update_rule_service")
@patch("app.api.routes.charter.get_rule")
def test_update_rule_passes_locale(mock_get, mock_update):
    _override_get_db(MagicMock())
    mock_get.return_value = _fake_rule()

    response = client.patch(
        f"/api/ai/charter/rules/{uuid4()}",
        json={"title": "새 제목", "description": "새 설명", "locale": "ja"},
    )

    assert response.status_code == 204
    assert mock_update.call_args.kwargs["locale"] == "ja"


@patch("app.api.routes.charter.update_rule_service")
@patch("app.api.routes.charter.get_rule")
def test_update_rule_locale_is_optional(mock_get, mock_update):
    _override_get_db(MagicMock())
    mock_get.return_value = _fake_rule()

    response = client.patch(
        f"/api/ai/charter/rules/{uuid4()}",
        json={"title": "새 제목", "description": "새 설명"},
    )

    assert response.status_code == 204
    assert mock_update.call_args.kwargs["locale"] is None


@patch("app.api.routes.charter.translate_fields")
@patch("app.api.routes.charter.list_rules_service")
def test_list_rules_translates_on_read(mock_list, mock_translate):
    """저장된 규칙은 조회 시점에 요청 locale로 번역해 내려준다."""
    _override_get_db(MagicMock())
    rule = _fake_rule(title="리뷰 SLA", description="24시간 이내 리뷰")
    rule.source_locale = "ko"
    mock_list.return_value = [rule]
    mock_translate.return_value = {
        (rule.id, "title"): "レビューSLA",
        (rule.id, "description"): "24時間以内",
    }

    response = client.get("/api/ai/charter/rules?teamId=1&locale=ja")

    assert response.status_code == 200
    body = response.json()["rules"][0]
    assert body["title"] == "レビューSLA"
    assert body["description"] == "24時間以内"


@patch("app.api.routes.charter.translate_fields")
@patch("app.api.routes.charter.list_rules_service")
def test_list_rules_passes_source_locale_and_fields(mock_list, mock_translate):
    _override_get_db(MagicMock())
    rule = _fake_rule(title="리뷰 SLA", description="24시간 이내 리뷰")
    rule.source_locale = "ko"
    mock_list.return_value = [rule]
    mock_translate.return_value = {}

    client.get("/api/ai/charter/rules?teamId=1&locale=ja")

    fields = mock_translate.call_args.args[1]
    assert {f.field for f in fields} == {"title", "description"}
    assert {f.entity_type for f in fields} == {"charter_rule"}
    assert {f.source_locale for f in fields} == {"ko"}
    assert mock_translate.call_args.args[2] == "ja"


@patch("app.api.routes.charter.translate_fields")
@patch("app.api.routes.charter.list_rules_service")
def test_list_rules_locale_is_optional(mock_list, mock_translate):
    """locale 쿼리 파라미터가 없어도 현행 동작이 유지된다."""
    _override_get_db(MagicMock())
    rule = _fake_rule(title="리뷰 SLA", description="24시간 이내 리뷰")
    rule.source_locale = "ko"
    mock_list.return_value = [rule]
    mock_translate.return_value = {}

    response = client.get("/api/ai/charter/rules?teamId=1")

    assert response.status_code == 200
    body = response.json()["rules"][0]
    assert body["title"] == "리뷰 SLA"
    assert body["description"] == "24시간 이내 리뷰"


@patch("app.api.routes.charter.translate_fields")
@patch("app.api.routes.charter.create_draft_rules")
@patch("app.api.routes.charter.call_charter_llm")
def test_generate_response_is_not_translated(mock_llm, mock_create, mock_translate):
    """생성 응답은 이미 요청자의 언어다 — 번역이 필요한 것은 나중에 다른 언어로 조회할 때뿐이다."""
    _override_get_db(MagicMock())
    mock_llm.return_value = [LLMCharterRule(title="리뷰 SLA", description="24시간 이내 리뷰")]
    mock_create.return_value = [_fake_rule()]

    client.post("/api/ai/charter/generate", json={"teamId": 1, "locale": "ja"})

    mock_translate.assert_not_called()

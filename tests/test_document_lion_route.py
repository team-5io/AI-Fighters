from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.cio_orchestrator import CioReviewVerdict
from app.services.document_lion import LLMReviewIssue, LLMReviewResult

client = TestClient(app)


def _override_get_db(fake_db):
    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db


def teardown_function():
    app.dependency_overrides.clear()


def _fake_review(**overrides):
    review = MagicMock()
    review.id = overrides.get("id", uuid4())
    review.overall_verdict = overrides.get("overall_verdict", "approve")
    return review


def _fake_issue(**overrides):
    issue = MagicMock()
    issue.severity = overrides.get("severity", "critical")
    issue.issue_type = overrides.get("issue_type", "charter_violation")
    issue.description = overrides.get("description", "리뷰 SLA 규칙 위반")
    issue.related_document_ref = overrides.get("related_document_ref", None)
    issue.charter_rule_id = overrides.get("charter_rule_id", None)
    issue.location_ref = overrides.get("location_ref", None)
    return issue


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_create_review_returns_review_with_issues(mock_fetch_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_fetch_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(
        issues=[LLMReviewIssue(severity="critical", issue_type="charter_violation", description="리뷰 SLA 규칙 위반")]
    )
    fake_review = _fake_review(overall_verdict="reject_recommended")
    mock_create.return_value = (fake_review, [_fake_issue()])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post(
        "/api/ai/document-lion/reviews",
        json={
            "documentId": 100,
            "docPrId": 7,
            "teamId": 1,
            "triggerType": "auto",
            "requestedBy": str(uuid4()),
            "content": "문서 본문",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overallVerdict"] == "reject_recommended"
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issueType"] == "charter_violation"
    mock_cio.assert_called_once_with("document_lion", "문서 본문", "리뷰 SLA 규칙 위반")


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_cio_review_failure_does_not_break_response(mock_fetch_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_fetch_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.side_effect = RuntimeError("cio_review_failed")

    response = client.post(
        "/api/ai/document-lion/reviews",
        json={
            "documentId": 100,
            "teamId": 1,
            "triggerType": "manual",
            "requestedBy": str(uuid4()),
            "content": "문서 본문",
        },
    )

    assert response.status_code == 200


@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_create_review_llm_failure_returns_502(mock_fetch_rules):
    _override_get_db(MagicMock())
    mock_fetch_rules.side_effect = RuntimeError("document_lion_review_failed")

    response = client.post(
        "/api/ai/document-lion/reviews",
        json={
            "documentId": 100,
            "teamId": 1,
            "triggerType": "manual",
            "requestedBy": str(uuid4()),
            "content": "문서 본문",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"error": "document_lion_review_failed"}


@patch("app.api.routes.document_lion.get_review")
def test_get_review_returns_stored_review(mock_get_review):
    _override_get_db(MagicMock())
    fake_review = _fake_review(overall_verdict="approve")
    mock_get_review.return_value = (fake_review, [])

    response = client.get(f"/api/ai/document-lion/reviews/{fake_review.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["overallVerdict"] == "approve"
    assert body["issues"] == []


@patch("app.api.routes.document_lion.get_review")
def test_get_review_returns_404_when_not_found(mock_get_review):
    _override_get_db(MagicMock())
    mock_get_review.return_value = None

    response = client.get(f"/api/ai/document-lion/reviews/{uuid4()}")

    assert response.status_code == 404


def _review_body(**overrides):
    body = {
        "documentId": 100,
        "teamId": 1,
        "triggerType": "manual",
        "requestedBy": str(uuid4()),
        "content": "문서 본문",
    }
    body.update(overrides)
    return body


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_passes_locale_to_service(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/document-lion/reviews", json=_review_body(locale="ja"))

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["locale"] == "ja"


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_locale_is_optional(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/document-lion/reviews", json=_review_body())

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["locale"] is None


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_passes_blocks_to_service(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    blocks = [{"blockId": "b-1", "content": "첫 문단"}]
    response = client.post("/api/ai/document-lion/reviews", json=_review_body(blocks=blocks))

    assert response.status_code == 200
    passed = mock_llm.call_args.kwargs["blocks"]
    assert [b.block_id for b in passed] == ["b-1"]


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_blocks_are_optional(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/document-lion/reviews", json=_review_body())

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["blocks"] is None


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_response_exposes_location_ref_as_object(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    stored = '{"blockId": "b-1", "quote": "문제 문장"}'
    mock_create.return_value = (_fake_review(), [_fake_issue(location_ref=stored)])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/document-lion/reviews", json=_review_body())

    assert response.status_code == 200
    assert response.json()["issues"][0]["locationRef"] == {"blockId": "b-1", "quote": "문제 문장"}


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_legacy_plain_text_location_ref_survives(mock_rules, mock_llm, mock_create, mock_cio):
    """포맷 확정 전에 저장된 행도 응답에서 깨지지 않아야 한다."""
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [_fake_issue(location_ref="3번째 문단")])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/document-lion/reviews", json=_review_body())

    assert response.status_code == 200
    assert response.json()["issues"][0]["locationRef"] == {"blockId": None, "quote": "3번째 문단"}


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_hallucinated_block_id_is_dropped_end_to_end(mock_rules, mock_llm, mock_cio):
    """LLM이 없는 blockId를 내놔도 저장·응답에 실리지 않아야 한다."""
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(
        issues=[
            LLMReviewIssue(
                severity="minor",
                issue_type="charter_violation",
                description="위반",
                block_id="b-존재하지-않음",
                quote="문제 문장",
            )
        ]
    )
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    with patch("app.api.routes.document_lion.create_review") as mock_create:
        mock_create.return_value = (_fake_review(), [])
        client.post(
            "/api/ai/document-lion/reviews",
            json=_review_body(blocks=[{"blockId": "b-1", "content": "첫 문단"}]),
        )
        assert mock_create.call_args.kwargs["valid_block_ids"] == {"b-1"}


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_passes_locale_to_persistence(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    client.post("/api/ai/document-lion/reviews", json=_review_body(locale="ja"))

    assert mock_create.call_args.kwargs["locale"] == "ja"


@patch("app.api.routes.document_lion.translate_fields")
@patch("app.api.routes.document_lion.get_review")
def test_get_review_translates_issue_descriptions(mock_get, mock_translate):
    _override_get_db(MagicMock())
    review = _fake_review()
    review.source_locale = "ko"
    issue = _fake_issue(description="리뷰 SLA 규칙 위반")
    issue.id = uuid4()
    mock_get.return_value = (review, [issue])
    mock_translate.return_value = {(issue.id, "description"): "レビューSLA規則違反"}

    response = client.get(f"/api/ai/document-lion/reviews/{review.id}?locale=ja")

    assert response.status_code == 200
    assert response.json()["issues"][0]["description"] == "レビューSLA規則違反"


@patch("app.api.routes.document_lion.translate_fields")
@patch("app.api.routes.document_lion.get_review")
def test_get_review_uses_parent_source_locale(mock_get, mock_translate):
    """이슈의 원본 언어는 부모 리뷰의 source_locale을 따른다 — 칸이 부모에만 있다."""
    _override_get_db(MagicMock())
    review = _fake_review()
    review.source_locale = "en"
    issue = _fake_issue(description="charter violation")
    issue.id = uuid4()
    mock_get.return_value = (review, [issue])
    mock_translate.return_value = {}

    client.get(f"/api/ai/document-lion/reviews/{review.id}?locale=ja")

    fields = mock_translate.call_args.args[1]
    assert [f.source_locale for f in fields] == ["en"]
    assert [f.entity_type for f in fields] == ["document_review_issue"]
    assert [f.field for f in fields] == ["description"]


@patch("app.api.routes.document_lion.translate_fields")
@patch("app.api.routes.document_lion.get_review")
def test_get_review_locale_is_optional(mock_get, mock_translate):
    _override_get_db(MagicMock())
    review = _fake_review()
    review.source_locale = "ko"
    issue = _fake_issue(description="리뷰 SLA 규칙 위반")
    issue.id = uuid4()
    mock_get.return_value = (review, [issue])
    mock_translate.return_value = {}

    response = client.get(f"/api/ai/document-lion/reviews/{review.id}")

    assert response.status_code == 200
    assert response.json()["issues"][0]["description"] == "리뷰 SLA 규칙 위반"


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_passes_related_documents_to_service(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    related = [
        {"documentId": 200, "title": "보안 정책", "content": "90일마다 교체", "relationType": "REFERENCE"}
    ]
    response = client.post(
        "/api/ai/document-lion/reviews", json=_review_body(relatedDocuments=related)
    )

    assert response.status_code == 200
    passed = mock_llm.call_args.kwargs["related_documents"]
    assert [d.id for d in passed] == [200]
    assert mock_create.call_args.kwargs["valid_related_document_ids"] == {200}


@patch("app.api.routes.document_lion.review_ai_output")
@patch("app.api.routes.document_lion.create_review")
@patch("app.api.routes.document_lion.call_document_lion_llm")
@patch("app.api.routes.document_lion.fetch_adopted_charter_rules")
def test_related_documents_are_optional(mock_rules, mock_llm, mock_create, mock_cio):
    _override_get_db(MagicMock())
    mock_rules.return_value = []
    mock_llm.return_value = LLMReviewResult(issues=[])
    mock_create.return_value = (_fake_review(), [])
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/document-lion/reviews", json=_review_body())

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["related_documents"] is None
    assert mock_create.call_args.kwargs["valid_related_document_ids"] is None

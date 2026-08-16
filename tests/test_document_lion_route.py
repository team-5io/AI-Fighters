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
            "documentId": str(uuid4()),
            "docPrId": str(uuid4()),
            "teamId": str(uuid4()),
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
            "documentId": str(uuid4()),
            "teamId": str(uuid4()),
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
            "documentId": str(uuid4()),
            "teamId": str(uuid4()),
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

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.document_lion import (
    CharterRuleContext,
    LLMReviewIssue,
    LLMReviewResult,
    call_document_lion_llm,
)


@patch("app.services.document_lion.get_genai_client")
def test_returns_issues_from_llm(mock_get_client):
    parsed = LLMReviewResult(
        issues=[
            LLMReviewIssue(
                severity="critical",
                issue_type="charter_violation",
                description="리뷰 SLA 규칙 위반",
            )
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_document_lion_llm("본문 내용", [CharterRuleContext(id=uuid4(), title="리뷰 SLA", description="24시간 이내 리뷰")])

    assert result == parsed
    mock_client.models.generate_content.assert_called_once()


@patch("app.services.document_lion.get_genai_client")
def test_returns_empty_issues_when_no_problems(mock_get_client):
    parsed = LLMReviewResult(issues=[])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_document_lion_llm("문제 없는 본문", [])

    assert result.issues == []


@patch("app.services.document_lion.get_genai_client")
def test_raises_on_malformed_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=None)
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        call_document_lion_llm("본문", [])

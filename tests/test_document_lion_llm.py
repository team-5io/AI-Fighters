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


def _mock_empty(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=LLMReviewResult(issues=[]))
    mock_get_client.return_value = mock_client
    return mock_client


@patch("app.services.document_lion.get_genai_client")
def test_prompt_defaults_to_korean_when_locale_missing(mock_get_client):
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("본문 내용", [])

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "Korean" in prompt


@patch("app.services.document_lion.get_genai_client")
def test_prompt_uses_requested_locale(mock_get_client):
    """프롬프트 본문은 한국어로 유지하고 출력 언어 지시만 분리한다.

    프롬프트를 영어 기반으로 재작성하는 것은 검토 품질 자체를 바꿀 수 있는 변경이라
    이 작업의 범위가 아니다 (설계 5.1 / 12절).
    """
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("본문 내용", [], locale="ja")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "Japanese" in prompt
    assert "Korean" not in prompt
    # 한국어 프롬프트 본문은 그대로 남아 있어야 한다
    assert "협업 규칙" in prompt


@patch("app.services.document_lion.get_genai_client")
def test_prompt_falls_back_to_english_for_unsupported_locale(mock_get_client):
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("본문 내용", [], locale="th")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "English" in prompt


@patch("app.services.document_lion.get_genai_client")
def test_uses_document_lion_model_override(mock_get_client, monkeypatch):
    """DocumentLion은 판단 계열이라 모델을 따로 올릴 수 있어야 한다."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "document_lion_model", "gemini-pro-latest")
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("본문 내용", [])

    assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-pro-latest"


@patch("app.services.document_lion.get_genai_client")
def test_falls_back_to_shared_model_when_override_unset(mock_get_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "document_lion_model", "")
    monkeypatch.setattr(settings, "gemini_model", "gemini-flash-lite-latest")
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("본문 내용", [])

    assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-flash-lite-latest"

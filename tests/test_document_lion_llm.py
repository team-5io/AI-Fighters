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


@patch("app.services.document_lion.get_genai_client")
def test_prompt_renders_blocks_with_ids(mock_get_client):
    """블록을 [blockId] 형태로 렌더링해 LLM이 그 id를 되돌려줄 수 있게 한다.

    이 기법은 이 레포에서 이미 검증됐다 — 협업 규칙을 '- (UUID) 제목' 으로 넣고
    LLM이 그 UUID를 charter_rule_id에 되돌려주는 구조가 동작 중이다.
    """
    from app.schemas.document_lion import DocumentBlock

    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm(
        "문서 본문",
        [],
        blocks=[DocumentBlock(block_id="b-1", content="첫 문단"), DocumentBlock(block_id="b-2", content="둘째 문단")],
    )

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "[b-1] 첫 문단" in prompt
    assert "[b-2] 둘째 문단" in prompt
    assert "block_id" in prompt


@patch("app.services.document_lion.get_genai_client")
def test_prompt_falls_back_to_flat_content_without_blocks(mock_get_client):
    """blocks는 optional이다 — BE가 아직 안 보내는 구간에서도 현행 동작이 유지된다."""
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("문서 본문 전체", [])

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "문서 본문 전체" in prompt
    assert "[b-" not in prompt


@patch("app.services.document_lion.get_genai_client")
def test_empty_block_list_is_treated_as_absent(mock_get_client):
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("문서 본문 전체", [], blocks=[])

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "문서 본문 전체" in prompt


@patch("app.services.document_lion.get_genai_client")
def test_prompt_requires_english_output(mock_get_client):
    """프롬프트 본문은 한국어로 유지하고 출력 언어 지시만 분리한다.

    프롬프트를 영어로 재작성하는 것은 검토 품질을 바꿀 수 있어 범위 밖이다(설계 12절).
    """
    mock_client = _mock_empty(mock_get_client)

    call_document_lion_llm("본문 내용", [])

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "in English" in prompt
    assert "협업 규칙" in prompt

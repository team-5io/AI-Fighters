from unittest.mock import MagicMock, patch

import pytest

from app.services.writing_assistant import LLMSuggestion, LLMSuggestionsResult, call_writing_assistant_llm


@patch("app.services.writing_assistant.get_genai_client")
def test_returns_suggestions_from_llm(mock_get_client):
    parsed = LLMSuggestionsResult(
        suggestions=[
            LLMSuggestion(type="structure", text="섹션을 나누세요"),
            LLMSuggestion(type="clarity", text="이 문장을 더 명확하게 쓰세요"),
            LLMSuggestion(type="next-paragraph", text="다음엔 결론을 쓰세요"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_writing_assistant_llm("본문 내용", "커서 주변 문맥")

    assert result == parsed.suggestions
    mock_client.models.generate_content.assert_called_once()


@patch("app.services.writing_assistant.get_genai_client")
def test_structure_suggestion_prompt_asks_for_toc_and_required_sections(mock_get_client):
    """Notion 기능명세서 "문서 구조 가이드 제안": 목차·필수 섹션 구조를 추천해야 한다."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=LLMSuggestionsResult(suggestions=[]))
    mock_get_client.return_value = mock_client

    call_writing_assistant_llm("본문 내용", "커서 주변 문맥")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "목차" in prompt
    assert "필수 섹션" in prompt


@patch("app.services.writing_assistant.get_genai_client")
def test_truncates_to_configured_count(mock_get_client):
    parsed = LLMSuggestionsResult(
        suggestions=[
            LLMSuggestion(type="structure", text="1"),
            LLMSuggestion(type="clarity", text="2"),
            LLMSuggestion(type="next-paragraph", text="3"),
            LLMSuggestion(type="structure", text="4"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_writing_assistant_llm("본문 내용", "커서 주변 문맥", count=2)

    assert len(result) == 2
    assert result == parsed.suggestions[:2]


@patch("app.services.writing_assistant.get_genai_client")
def test_raises_on_malformed_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=None)
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        call_writing_assistant_llm("본문 내용", "커서 주변 문맥")


@patch("app.services.writing_assistant.get_genai_client")
def test_prompt_requires_korean_output(mock_get_client):
    """제안 본문은 한국어로 내려와야 한다 — 프롬프트에 출력 언어 지시가 있어야 한다."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=LLMSuggestionsResult(suggestions=[]))
    mock_get_client.return_value = mock_client

    call_writing_assistant_llm("본문 내용", "커서 주변 문맥")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "in Korean" in prompt

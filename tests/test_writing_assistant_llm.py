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

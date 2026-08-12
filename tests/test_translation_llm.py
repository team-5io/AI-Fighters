from unittest.mock import MagicMock, patch

import pytest

from app.services.translation import LLMTranslationResult, call_translation_llm


@patch("app.services.translation.get_genai_client")
def test_call_translation_llm_returns_parsed_result(mock_get_client):
    expected = LLMTranslationResult(translated_content="Hello", preserved_terms=["Doc PR"])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=expected)
    mock_get_client.return_value = mock_client

    result = call_translation_llm("안녕하세요", "ko", "en")

    assert result == expected
    mock_client.models.generate_content.assert_called_once()


@patch("app.services.translation.get_genai_client")
def test_call_translation_llm_raises_on_empty_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=None)
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        call_translation_llm("안녕하세요", "ko", "en")


@patch("app.services.translation.get_genai_client")
def test_call_translation_llm_raises_on_malformed_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed={"not": "expected shape"})
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        call_translation_llm("안녕하세요", "ko", "en")

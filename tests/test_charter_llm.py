from unittest.mock import MagicMock, patch

import pytest

from app.services.charter import LLMCharterRule, LLMCharterRulesResult, call_charter_llm


@patch("app.services.charter.get_genai_client")
def test_returns_rules_from_llm(mock_get_client):
    parsed = LLMCharterRulesResult(
        rules=[
            LLMCharterRule(title="리뷰 SLA", description="Doc PR은 24시간 이내 리뷰한다"),
            LLMCharterRule(title="소통 채널", description="긴급 사안은 슬랙 #urgent로"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_charter_llm(count=2)

    assert result == parsed.rules
    mock_client.models.generate_content.assert_called_once()


@patch("app.services.charter.get_genai_client")
def test_truncates_to_configured_count(mock_get_client):
    parsed = LLMCharterRulesResult(
        rules=[
            LLMCharterRule(title="1", description="d1"),
            LLMCharterRule(title="2", description="d2"),
            LLMCharterRule(title="3", description="d3"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_charter_llm(count=1)

    assert result == parsed.rules[:1]


@patch("app.services.charter.get_genai_client")
def test_raises_on_malformed_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=None)
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        call_charter_llm()

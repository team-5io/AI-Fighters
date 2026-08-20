from unittest.mock import MagicMock, patch

import pytest

from app.services.cio_orchestrator import CioReviewVerdict, review_ai_output


@patch("app.services.cio_orchestrator.get_genai_client")
def test_returns_verdict_from_llm(mock_get_client):
    parsed = CioReviewVerdict(approved=True, concerns=[])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = review_ai_output("translation", "원문", "번역 결과")

    assert result == parsed
    mock_client.models.generate_content.assert_called_once()


@patch("app.services.cio_orchestrator.get_genai_client")
def test_flags_concerns_when_output_off_context(mock_get_client):
    parsed = CioReviewVerdict(approved=False, concerns=["원문에 없는 내용이 추가됨"])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = review_ai_output("writing_assistant", "원문", "엉뚱한 제안")

    assert result.approved is False
    assert result.concerns == ["원문에 없는 내용이 추가됨"]


@patch("app.services.cio_orchestrator.get_genai_client")
def test_raises_on_malformed_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=None)
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        review_ai_output("document_lion", "원문", "결과")


@patch("app.services.cio_orchestrator.get_genai_client")
def test_uses_cio_model_override(mock_get_client, monkeypatch):
    """CIO는 원문과 생성물을 대조하는 판단 계열이라 모델을 따로 올릴 수 있어야 한다."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "cio_model", "gemini-pro-latest")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        parsed=CioReviewVerdict(approved=True, concerns=[])
    )
    mock_get_client.return_value = mock_client

    review_ai_output("translation", "원문", "번역 결과")

    assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-pro-latest"


@patch("app.services.cio_orchestrator.get_genai_client")
def test_falls_back_to_shared_model_when_override_unset(mock_get_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cio_model", "")
    monkeypatch.setattr(settings, "gemini_model", "gemini-flash-lite-latest")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        parsed=CioReviewVerdict(approved=True, concerns=[])
    )
    mock_get_client.return_value = mock_client

    review_ai_output("translation", "원문", "번역 결과")

    assert mock_client.models.generate_content.call_args.kwargs["model"] == "gemini-flash-lite-latest"

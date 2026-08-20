from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.cio_orchestrator import CioReviewVerdict
from app.services.writing_assistant import LLMSuggestion

client = TestClient(app)


def _request_body():
    return {
        "documentId": 100,
        "content": "본문 내용",
        "cursorContext": "커서 주변 문맥",
    }


@patch("app.api.routes.writing_assistant.review_ai_output")
@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_returns_suggestions(mock_llm, mock_cio):
    mock_llm.return_value = [
        LLMSuggestion(type="structure", text="섹션을 나누세요"),
        LLMSuggestion(type="clarity", text="이 문장을 더 명확하게 쓰세요"),
    ]
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/writing-assistant/suggestions", json=_request_body())

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == [
        {"type": "structure", "text": "섹션을 나누세요"},
        {"type": "clarity", "text": "이 문장을 더 명확하게 쓰세요"},
    ]
    mock_cio.assert_called_once_with("writing_assistant", "본문 내용", "섹션을 나누세요\n이 문장을 더 명확하게 쓰세요")


@patch("app.api.routes.writing_assistant.review_ai_output")
@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_cio_review_failure_does_not_break_response(mock_llm, mock_cio):
    mock_llm.return_value = [LLMSuggestion(type="structure", text="섹션을 나누세요")]
    mock_cio.side_effect = RuntimeError("cio_review_failed")

    response = client.post("/api/ai/writing-assistant/suggestions", json=_request_body())

    assert response.status_code == 200


@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_llm_failure_returns_502(mock_llm):
    mock_llm.side_effect = RuntimeError("writing_assistant_failed")

    response = client.post("/api/ai/writing-assistant/suggestions", json=_request_body())

    assert response.status_code == 502
    assert response.json() == {"error": "writing_assistant_failed"}


@patch("app.api.routes.writing_assistant.review_ai_output")
@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_passes_locale_to_service(mock_llm, mock_cio):
    mock_llm.return_value = [LLMSuggestion(type="structure", text="섹션을 나누세요")]
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post(
        "/api/ai/writing-assistant/suggestions", json={**_request_body(), "locale": "ja"}
    )

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["locale"] == "ja"


@patch("app.api.routes.writing_assistant.review_ai_output")
@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_locale_is_optional(mock_llm, mock_cio):
    """locale이 없어도 422가 아니라 정상 동작해야 한다.

    required로 잡으면 BE가 아직 locale을 안 보내는 구간의 모든 호출이 422가 되고,
    BE가 이를 502로 감싸 내려보내 화면에는 "AI 장애"로 보인다.
    """
    mock_llm.return_value = [LLMSuggestion(type="structure", text="섹션을 나누세요")]
    mock_cio.return_value = CioReviewVerdict(approved=True, concerns=[])

    response = client.post("/api/ai/writing-assistant/suggestions", json=_request_body())

    assert response.status_code == 200
    assert mock_llm.call_args.kwargs["locale"] is None

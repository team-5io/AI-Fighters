from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.writing_assistant import LLMSuggestion

client = TestClient(app)


def _request_body():
    return {
        "documentId": "doc-1",
        "content": "본문 내용",
        "cursorContext": "커서 주변 문맥",
    }


@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_returns_suggestions(mock_llm):
    mock_llm.return_value = [
        LLMSuggestion(type="structure", text="섹션을 나누세요"),
        LLMSuggestion(type="clarity", text="이 문장을 더 명확하게 쓰세요"),
    ]

    response = client.post("/api/ai/writing-assistant/suggestions", json=_request_body())

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == [
        {"type": "structure", "text": "섹션을 나누세요"},
        {"type": "clarity", "text": "이 문장을 더 명확하게 쓰세요"},
    ]


@patch("app.api.routes.writing_assistant.call_writing_assistant_llm")
def test_llm_failure_returns_502(mock_llm):
    mock_llm.side_effect = RuntimeError("writing_assistant_failed")

    response = client.post("/api/ai/writing-assistant/suggestions", json=_request_body())

    assert response.status_code == 502
    assert response.json() == {"error": "writing_assistant_failed"}

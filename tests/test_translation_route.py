from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.translation import LLMTranslationResult

client = TestClient(app)


def _request_body(document_id):
    return {
        "documentId": str(document_id),
        "content": "안녕하세요",
        "sourceLang": "ko",
        "targetLang": "en",
    }


def _override_get_db(fake_db):
    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db


def teardown_function():
    app.dependency_overrides.clear()


@patch("app.api.routes.translation.get_cached_translation")
def test_returns_cached_translation_without_calling_llm(mock_get_cached):
    fake_db = MagicMock()
    _override_get_db(fake_db)
    cached_row = MagicMock(translated_content="Hello", preserved_terms='["Doc PR"]')
    mock_get_cached.return_value = cached_row

    with patch("app.api.routes.translation.call_translation_llm") as mock_llm:
        response = client.post("/api/ai/translations", json=_request_body(uuid4()))

    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is True
    assert body["translatedContent"] == "Hello"
    assert body["preservedTerms"] == ["Doc PR"]
    mock_llm.assert_not_called()


@patch("app.api.routes.translation.save_translation")
@patch("app.api.routes.translation.call_translation_llm")
@patch("app.api.routes.translation.get_cached_translation")
def test_cache_miss_calls_llm_and_saves(mock_get_cached, mock_llm, mock_save):
    fake_db = MagicMock()
    _override_get_db(fake_db)
    mock_get_cached.return_value = None
    mock_llm.return_value = LLMTranslationResult(translated_content="Hello", preserved_terms=["Doc PR"])
    mock_save.return_value = MagicMock(translated_content="Hello")

    response = client.post("/api/ai/translations", json=_request_body(uuid4()))

    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is False
    assert body["translatedContent"] == "Hello"
    assert body["preservedTerms"] == ["Doc PR"]
    mock_save.assert_called_once()


@patch("app.api.routes.translation.call_translation_llm")
@patch("app.api.routes.translation.get_cached_translation")
def test_llm_failure_returns_502_without_retry(mock_get_cached, mock_llm):
    fake_db = MagicMock()
    _override_get_db(fake_db)
    mock_get_cached.return_value = None
    mock_llm.side_effect = RuntimeError("translation_failed")

    response = client.post("/api/ai/translations", json=_request_body(uuid4()))

    assert response.status_code == 502
    assert response.json() == {"error": "translation_failed"}
    mock_llm.assert_called_once()


@patch("app.api.routes.translation.save_translation")
@patch("app.api.routes.translation.call_translation_llm")
@patch("app.api.routes.translation.get_cached_translation")
def test_save_failure_after_llm_success_returns_502(mock_get_cached, mock_llm, mock_save):
    """동시 요청이 같은 (document_id, target_lang)로 캐시 미스 후 동시에 저장을 시도하면
    UniqueConstraint 위반(IntegrityError)이 날 수 있다 — 그 경우도 500이 아니라 계약대로 502."""
    fake_db = MagicMock()
    _override_get_db(fake_db)
    mock_get_cached.return_value = None
    mock_llm.return_value = LLMTranslationResult(translated_content="Hello", preserved_terms=[])
    mock_save.side_effect = Exception("duplicate key value violates unique constraint")

    response = client.post("/api/ai/translations", json=_request_body(uuid4()))

    assert response.status_code == 502
    assert response.json() == {"error": "translation_failed"}

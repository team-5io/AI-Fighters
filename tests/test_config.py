from app.core.config import Settings


class TestPerServiceModelOverride:
    """5번 결정 — 서비스별 모델 설정 분리. 값이 비어 있으면 기존 모델을 그대로 쓴다."""

    def test_defaults_to_shared_model_when_unset(self):
        s = Settings(gemini_model="gemini-flash-lite-latest", document_lion_model="", cio_model="")
        assert s.effective_document_lion_model == "gemini-flash-lite-latest"
        assert s.effective_cio_model == "gemini-flash-lite-latest"

    def test_override_wins_when_set(self):
        s = Settings(gemini_model="gemini-flash-lite-latest", document_lion_model="gemini-pro-latest")
        assert s.effective_document_lion_model == "gemini-pro-latest"
        # 지정하지 않은 쪽은 영향받지 않는다
        assert s.effective_cio_model == "gemini-flash-lite-latest"

    def test_shipped_defaults_change_nothing(self):
        """기본값으로는 현행과 완전히 동일하게 동작해야 한다 — 비용·동작 변화 0."""
        s = Settings()
        assert s.effective_document_lion_model == s.gemini_model
        assert s.effective_cio_model == s.gemini_model
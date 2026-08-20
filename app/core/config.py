from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ai_fighters:ai_fighters@localhost:5432/ai_fighters"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    writing_assistant_suggestion_count: int = 3
    charter_generation_rule_count: int = 5

    # DocumentLion과 CIO는 생성이 아니라 '판단' 계열이다 (문서 이해 → 규칙 대조 → 위반 판정).
    # 판단 계열이 저가 모델에서 먼저 무너질 수 있어 모델을 따로 올릴 수 있게 분리해둔다.
    # 비워두면 gemini_model을 그대로 쓴다 — 기본값으로는 현행과 완전히 동일하게 동작한다.
    document_lion_model: str = ""
    cio_model: str = ""

    # 배치 번역 청크 기준(문자 수). 개수 기준으로는 항목 길이 편차를 잡을 수 없다.
    # 청크는 토큰 대책이기도 하지만 본질은 실패 격리다 — 개수 불일치로 한 청크가 실패해도
    # 나머지 청크의 번역은 살아남는다.
    translation_batch_chunk_chars: int = 4000

    @property
    def effective_document_lion_model(self) -> str:
        return self.document_lion_model or self.gemini_model

    @property
    def effective_cio_model(self) -> str:
        return self.cio_model or self.gemini_model


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ai_fighters:ai_fighters@localhost:5432/ai_fighters"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"


settings = Settings()

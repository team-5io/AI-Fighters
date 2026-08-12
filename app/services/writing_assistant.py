from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.writing_assistant import SuggestionType
from app.services.llm_client import get_genai_client


class LLMSuggestion(BaseModel):
    type: SuggestionType
    text: str


class LLMSuggestionsResult(BaseModel):
    suggestions: list[LLMSuggestion]


def call_writing_assistant_llm(content: str, cursor_context: str, count: int | None = None) -> list[LLMSuggestion]:
    suggestion_count = count if count is not None else settings.writing_assistant_suggestion_count
    prompt = (
        f"Suggest exactly {suggestion_count} writing improvements for the text below, "
        "focused on the cursor position given in cursor_context. Each suggestion must have "
        "a type: 'structure' (문서 구조 개선), 'next-paragraph' (다음 문단 제안), "
        "or 'clarity' (명확성 개선).\n\n"
        f"Text:\n{content}\n\n"
        f"Cursor context:\n{cursor_context}"
    )
    response = get_genai_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMSuggestionsResult,
        ),
    )
    result = response.parsed
    if not isinstance(result, LLMSuggestionsResult):
        raise RuntimeError("writing_assistant_failed: empty or malformed LLM response")
    return result.suggestions[:suggestion_count]

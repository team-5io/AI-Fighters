from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.core.locale import language_instruction
from app.schemas.writing_assistant import SuggestionType
from app.services.llm_client import get_genai_client


# 표시 순서: 문서 구조 -> 다음 문단 -> 문장 다듬기. 큰 단위에서 작은 단위로 내려간다.
# 프롬프트에 순서 지시가 없어 LLM 응답 순서는 매번 달라지므로 서버에서 정돈해 내려준다.
_SUGGESTION_TYPE_ORDER = {"structure": 0, "next-paragraph": 1, "clarity": 2}


class LLMSuggestion(BaseModel):
    type: SuggestionType
    text: str


class LLMSuggestionsResult(BaseModel):
    suggestions: list[LLMSuggestion]


def call_writing_assistant_llm(
    content: str, cursor_context: str, count: int | None = None, locale: str | None = None
) -> list[LLMSuggestion]:
    suggestion_count = count if count is not None else settings.writing_assistant_suggestion_count
    prompt = (
        f"Suggest exactly {suggestion_count} writing improvements for the text below, "
        "focused on the cursor position given in cursor_context. Each suggestion must have "
        "a type: 'structure' (문서에 필요한 목차·필수 섹션 구조를 추천— 예: 빠진 섹션, 순서 재배치), "
        "'next-paragraph' (다음 문단 제안), or 'clarity' (명확성 개선).\n"
        f"{language_instruction(locale)}\n\n"
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
    # 자르기를 먼저 하고 정렬한다. 순서를 뒤집으면 structure 제안만 남도록 편향된다 —
    # LLM이 고른 상위 N개를 존중하고 표시 순서만 정돈하는 것이 목적이다.
    selected = result.suggestions[:suggestion_count]
    return sorted(selected, key=lambda s: _SUGGESTION_TYPE_ORDER.get(s.type, len(_SUGGESTION_TYPE_ORDER)))

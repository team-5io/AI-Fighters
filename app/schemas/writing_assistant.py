from typing import Literal

from app.schemas.base import CamelModel

SuggestionType = Literal["structure", "next-paragraph", "clarity"]


class SuggestionRequest(CamelModel):
    document_id: int
    content: str
    cursor_context: str
    # BE 사용자 프로필의 선호 언어. optional이다 — required로 잡으면 BE가 아직 locale을
    # 실어보내지 않는 구간의 모든 호출이 422가 되고, BE가 이를 502로 감싸 내려보낸다.
    locale: str | None = None


class Suggestion(CamelModel):
    type: SuggestionType
    text: str


class SuggestionResponse(CamelModel):
    suggestions: list[Suggestion]

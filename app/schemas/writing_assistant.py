from typing import Literal

from app.schemas.base import CamelModel

SuggestionType = Literal["structure", "next-paragraph", "clarity"]


class SuggestionRequest(CamelModel):
    document_id: int
    content: str
    cursor_context: str


class Suggestion(CamelModel):
    type: SuggestionType
    text: str


class SuggestionResponse(CamelModel):
    suggestions: list[Suggestion]

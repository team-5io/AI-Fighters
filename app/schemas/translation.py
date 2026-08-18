from app.schemas.base import CamelModel


class TranslationRequest(CamelModel):
    document_id: int
    block_id: str
    content: str
    source_lang: str
    target_lang: str


class TranslationResponse(CamelModel):
    translated_content: str
    preserved_terms: list[str]
    cached: bool

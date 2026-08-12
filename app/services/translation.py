import hashlib
import json
from uuid import UUID

from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.translation_cache import TranslationCache
from app.services.llm_client import get_genai_client


class LLMTranslationResult(BaseModel):
    translated_content: str
    preserved_terms: list[str]


def call_translation_llm(content: str, source_lang: str, target_lang: str) -> LLMTranslationResult:
    prompt = (
        f"Translate the following text from {source_lang} to {target_lang}.\n"
        "Keep proper nouns, product names, and domain-specific terms "
        "(e.g. 'Doc PR', 'RACI') untranslated in the translation, and list "
        "each one you kept untranslated in preserved_terms.\n\n"
        f"Text:\n{content}"
    )
    response = get_genai_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMTranslationResult,
        ),
    )
    result = response.parsed
    if not isinstance(result, LLMTranslationResult):
        raise RuntimeError("translation_failed: empty or malformed LLM response")
    return result


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_cached_translation(db: Session, document_id: UUID, target_lang: str) -> TranslationCache | None:
    return (
        db.query(TranslationCache)
        .filter(
            TranslationCache.document_ref == document_id,
            TranslationCache.target_lang == target_lang,
        )
        .one_or_none()
    )


def save_translation(
    db: Session,
    document_id: UUID,
    source_lang: str,
    target_lang: str,
    content: str,
    translated_content: str,
    preserved_terms: list[str],
) -> TranslationCache:
    row = TranslationCache(
        document_ref=document_id,
        source_lang=source_lang,
        target_lang=target_lang,
        translated_content=translated_content,
        preserved_terms=json.dumps(preserved_terms, ensure_ascii=False),
        source_content_hash=_hash_content(content),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def deserialize_preserved_terms(raw: str | None) -> list[str]:
    return json.loads(raw) if raw else []

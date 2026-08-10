import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.translation_cache import TranslationCache


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

import hashlib
import json
import logging

from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.locale import language_name
from app.models.translation_cache import TranslationCache
from app.services.llm_client import get_genai_client

logger = logging.getLogger(__name__)


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


class LLMBatchTranslationResult(BaseModel):
    translations: list[str]


def chunk_indices(texts: list[str], max_chars: int) -> list[list[int]]:
    """번역 대상을 문자 수 기준으로 묶어 인덱스 청크 목록을 돌려준다.

    개수 기준으로는 항목 길이 편차를 잡을 수 없다 — 규칙 5개가 각 2,000자면 10,000자이고
    규칙 30개가 각 100자면 3,000자다.

    한 항목이 혼자 한도를 넘으면 그 항목만으로 한 청크가 된다. 이 경우를 정해두지 않으면
    빈 청크가 생기거나 루프가 진행되지 않는다.
    """
    chunks: list[list[int]] = []
    current: list[int] = []
    current_len = 0

    for index, text in enumerate(texts):
        length = len(text)
        if current and current_len + length > max_chars:
            chunks.append(current)
            current, current_len = [], 0
        current.append(index)
        current_len += length

    if current:
        chunks.append(current)
    return chunks


def _translate_chunk(texts: list[str], source_lang: str, target_lang: str) -> list[str]:
    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(texts))
    prompt = (
        f"Translate each numbered item below from {language_name(source_lang)} to "
        f"{language_name(target_lang)}.\n"
        f"Return exactly {len(texts)} translations in `translations`, in the same order as the input. "
        "Do not merge, split, reorder, or omit items.\n"
        "Keep proper nouns, product names, and domain-specific terms "
        "(e.g. 'Doc PR', 'RACI') untranslated.\n\n"
        f"{numbered}"
    )
    response = get_genai_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMBatchTranslationResult,
        ),
    )
    result = response.parsed
    if not isinstance(result, LLMBatchTranslationResult):
        raise RuntimeError("batch_translation_failed: empty or malformed LLM response")
    return result.translations


def call_batch_translation_llm(texts: list[str], source_lang: str, target_lang: str) -> list[str]:
    """여러 텍스트를 청크 단위 LLM 호출로 번역한다. 입력과 같은 길이·순서로 반환한다.

    예외를 전파하지 않는다. 실패한 청크는 원문을 그대로 남긴다 — 조회 화면이 통째로
    죽는 것보다 원본 언어라도 보이는 편이 낫다. 기존 Translation의 '실패 즉시 원문 표시'
    정책과 같다.

    응답 개수가 입력과 다르면 실패로 간주한다. 순서가 어긋난 채 매핑되면 엉뚱한 규칙에
    엉뚱한 번역이 붙는다.
    """
    if not texts:
        return []

    results = list(texts)

    for chunk in chunk_indices(texts, settings.translation_batch_chunk_chars):
        chunk_texts = [texts[i] for i in chunk]
        try:
            translated = _translate_chunk(chunk_texts, source_lang, target_lang)
        except Exception:
            logger.warning(
                "batch translation chunk failed (%s -> %s, %d items) — keeping source text",
                source_lang,
                target_lang,
                len(chunk_texts),
                exc_info=True,
            )
            continue

        if len(translated) != len(chunk_texts):
            logger.warning(
                "batch translation returned %d translations for %d inputs (%s -> %s) — keeping source text",
                len(translated),
                len(chunk_texts),
                source_lang,
                target_lang,
            )
            continue

        for index, text in zip(chunk, translated):
            results[index] = text

    return results


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_cached_translation(db: Session, document_id: int, block_id: str, target_lang: str) -> TranslationCache | None:
    return (
        db.query(TranslationCache)
        .filter(
            TranslationCache.document_ref == document_id,
            TranslationCache.block_ref == block_id,
            TranslationCache.target_lang == target_lang,
        )
        .one_or_none()
    )


def save_translation(
    db: Session,
    document_id: int,
    block_id: str,
    source_lang: str,
    target_lang: str,
    content: str,
    translated_content: str,
    preserved_terms: list[str],
) -> TranslationCache:
    row = TranslationCache(
        document_ref=document_id,
        block_ref=block_id,
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

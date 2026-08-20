"""저장된 AI 생성 텍스트를 조회 시점에 사용자 언어로 번역한다.

Writing Assistant 제안은 응답 후 폐기되므로 생성 시점 locale로 끝난다. 반면 Charter
규칙과 DocumentLion 이슈는 DB에 저장되므로, 나중에 다른 언어 사용자가 조회할 때
이미 굳은 텍스트를 번역해야 한다.

번역은 최초 조회 시 lazy로 수행하고 캐시한다 — 아무도 읽지 않는 언어에 쿼터를 쓰지 않는다.
"""

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.locale import normalize_locale
from app.models.ai_text_translation import AiTextTranslation
from app.services.translation import call_batch_translation_llm

logger = logging.getLogger(__name__)

FieldKey = tuple[UUID, str]


@dataclass(frozen=True)
class TranslatableField:
    entity_type: str
    entity_id: UUID
    field: str
    source_locale: str
    text: str

    @property
    def key(self) -> FieldKey:
        return (self.entity_id, self.field)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_key(entity_type: str, entity_id: UUID, field: str) -> tuple[str, UUID, str]:
    return (entity_type, entity_id, field)


def translate_fields(
    db: Session, fields: list[TranslatableField], target_locale: str | None
) -> dict[FieldKey, str]:
    """(entity_id, field) -> 표시할 텍스트 매핑을 돌려준다.

    번역이 불필요하거나 실패하면 원문을 그대로 담는다. 예외를 전파하지 않는다.
    """
    target = normalize_locale(target_locale)
    result: dict[FieldKey, str] = {f.key: f.text for f in fields}
    if not fields:
        return result

    # 원본 언어가 요청 언어와 같거나 내용이 비어 있으면 번역할 것이 없다.
    pending = [f for f in fields if normalize_locale(f.source_locale) != target and f.text.strip()]
    if not pending:
        return result

    cached = _fetch_cache(db, pending, target)

    to_translate: list[TranslatableField] = []
    for field in pending:
        row = cached.get(_cache_key(field.entity_type, field.entity_id, field.field))
        if row is not None and row.source_text_hash == _hash_text(field.text):
            result[field.key] = row.translated_text
        else:
            to_translate.append(field)

    if not to_translate:
        return result

    # 원본 언어별로 묶어 각 묶음당 1회 호출한다 (내부에서 문자 수 기준으로 다시 청크로 쪼갠다).
    by_source: dict[str, list[TranslatableField]] = defaultdict(list)
    for field in to_translate:
        by_source[normalize_locale(field.source_locale)].append(field)

    dirty = False
    for source_locale, group in by_source.items():
        translations = call_batch_translation_llm([f.text for f in group], source_locale, target)
        for field, translated in zip(group, translations):
            # 번역 실패 시 call_batch_translation_llm은 원문을 되돌려준다. 그 원문을 번역으로
            # 저장하면 캐시가 영구히 오염되어 이후 재시도조차 하지 않는다.
            if translated == field.text:
                continue
            result[field.key] = translated
            _upsert(db, cached, field, target, translated)
            dirty = True

    if dirty:
        db.commit()
    return result


def _fetch_cache(
    db: Session, fields: list[TranslatableField], target_locale: str
) -> dict[tuple[str, UUID, str], AiTextTranslation]:
    rows = (
        db.query(AiTextTranslation)
        .filter(
            AiTextTranslation.target_locale == target_locale,
            AiTextTranslation.entity_type.in_({f.entity_type for f in fields}),
            AiTextTranslation.entity_id.in_({f.entity_id for f in fields}),
        )
        .all()
    )
    return {_cache_key(r.entity_type, r.entity_id, r.field): r for r in rows}


def _upsert(
    db: Session,
    cached: dict[tuple[str, UUID, str], AiTextTranslation],
    field: TranslatableField,
    target_locale: str,
    translated: str,
) -> None:
    key = _cache_key(field.entity_type, field.entity_id, field.field)
    row = cached.get(key)
    if row is not None:
        # UNIQUE(entity_type, entity_id, field, target_locale)이 있으므로 새로 넣으면 충돌한다.
        row.translated_text = translated
        row.source_text_hash = _hash_text(field.text)
        return

    row = AiTextTranslation(
        entity_type=field.entity_type,
        entity_id=field.entity_id,
        field=field.field,
        target_locale=target_locale,
        translated_text=translated,
        source_text_hash=_hash_text(field.text),
    )
    db.add(row)
    cached[key] = row

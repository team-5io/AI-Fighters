import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiTextTranslation(Base):
    """AI가 생성해 저장한 텍스트의 번역 보관함.

    기존 translation_cache를 재사용하지 않는다. 그 테이블은
    document_ref(BIGINT) + block_ref + target_lang으로 '문서 블록 전용'으로 설계돼 있고,
    규칙·이슈는 문서도 블록도 아니다. 억지로 끼워 넣으면 유니크 제약이 충돌한다.
    """

    __tablename__ = "ai_text_translation"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "field", "target_locale"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 'charter_rule' | 'document_review_issue'
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # 'title' | 'description'
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    target_locale: Mapped[str] = mapped_column(String(10), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 원문이 수정되면 저장된 번역은 거짓이 된다. 해시가 다르면 캐시를 무시하고 재번역한다.
    source_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

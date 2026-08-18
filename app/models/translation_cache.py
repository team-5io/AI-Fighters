import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TranslationCache(Base):
    __tablename__ = "translation_cache"
    __table_args__ = (UniqueConstraint("document_ref", "block_ref", "target_lang"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # BE Document.id는 Long(BIGINT) — publicId(UUID) 발급 대상이 아님. UUID로 잘못 잡혀있던 것 수정.
    document_ref: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # BE blocks 테이블의 블록 id는 FE가 생성하는 문자열(VARCHAR(64))
    block_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    source_lang: Mapped[str] = mapped_column(String(10), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(10), nullable=False)
    translated_content: Mapped[str] = mapped_column(Text, nullable=False)
    # Postgres 배열 대신 JSON 문자열로 저장 (ERD Cloud import 시 TEXT로 정리하기로 한 결정과 동일)
    preserved_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

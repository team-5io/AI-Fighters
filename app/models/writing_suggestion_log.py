import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WritingSuggestionLog(Base):
    __tablename__ = "writing_suggestion_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_by_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suggestion_type: Mapped[str] = mapped_column(String(20), nullable=False)
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

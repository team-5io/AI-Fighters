import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentReview(Base):
    __tablename__ = "document_review"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # BE DocPr.id/Document.id는 Long — publicId 발급 대상이 아님 (UUID로 잘못 잡혀있던 것 수정)
    doc_pr_ref: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    document_ref: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(10), nullable=False)
    overall_verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_by_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

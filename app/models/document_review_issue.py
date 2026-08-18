import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentReviewIssue(Base):
    __tablename__ = "document_review_issue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_review.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # BE Document.id는 Long — publicId 발급 대상이 아님 (UUID로 잘못 잡혀있던 것 수정)
    related_document_ref: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    charter_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("charter_rule.id", ondelete="SET NULL"), nullable=True
    )
    location_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

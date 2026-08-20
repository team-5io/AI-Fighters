from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    AiTextTranslation,
    CharterRule,
    DocumentReview,
    DocumentReviewIssue,
    TranslationCache,
    WritingSuggestionLog,
)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("created tables:", ", ".join(sorted(Base.metadata.tables.keys())))

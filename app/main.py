import logging

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes import charter, document_lion, translation, writing_assistant
from app.db.session import get_db
from app.models import (
    CharterRule,
    DocumentReview,
    DocumentReviewIssue,
    TranslationCache,
    WritingSuggestionLog,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="AI-Fighters", version="0.1.0")

app.include_router(translation.router, prefix="/api/ai")
app.include_router(writing_assistant.router, prefix="/api/ai")
app.include_router(document_lion.router, prefix="/api/ai")
app.include_router(charter.router, prefix="/api/ai")

# 헬스체크가 실제로 조회하는 테이블. 각 모델의 전체 컬럼 목록이 SELECT에 들어가므로
# 컬럼 누락(마이그레이션 미적용)이 여기서 잡힌다. SELECT 1로는 잡히지 않는다.
_SCHEMA_CHECK_MODELS = (
    CharterRule,
    DocumentReview,
    DocumentReviewIssue,
    TranslationCache,
    WritingSuggestionLog,
)


@app.get("/health", response_model=None)
def health(db: Session = Depends(get_db)) -> dict[str, str] | JSONResponse:
    """DB 접속과 스키마 일치까지 확인한다.

    CD의 deploy job은 이 응답 하나로 배포 성공을 판정한다. 상수를 돌려주면 마이그레이션을
    빠뜨려도 배포가 success로 찍히고 실제 엔드포인트만 500이 된다 — 2026-08-21에 실제로
    겪은 상황이다. 그래서 앱이 읽는 테이블을 실제로 한 건씩 조회한다.
    """
    try:
        for model in _SCHEMA_CHECK_MODELS:
            db.query(model).limit(1).all()
    except Exception:
        logger.exception("health check failed — DB 스키마가 모델과 어긋났을 수 있다")
        return JSONResponse(
            status_code=503, content={"status": "unhealthy", "reason": "db_schema_check_failed"}
        )
    return {"status": "ok"}

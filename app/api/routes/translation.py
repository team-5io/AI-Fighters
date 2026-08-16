import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.translation import TranslationRequest, TranslationResponse
from app.services.cio_orchestrator import review_ai_output
from app.services.translation import (
    call_translation_llm,
    deserialize_preserved_terms,
    get_cached_translation,
    save_translation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translations", tags=["translation"])


@router.post("", response_model=TranslationResponse)
def translate(payload: TranslationRequest, db: Session = Depends(get_db)) -> TranslationResponse | JSONResponse:
    cached = get_cached_translation(db, payload.document_id, payload.target_lang)
    if cached is not None:
        return TranslationResponse(
            translated_content=cached.translated_content,
            preserved_terms=deserialize_preserved_terms(cached.preserved_terms),
            cached=True,
        )

    try:
        result = call_translation_llm(payload.content, payload.source_lang, payload.target_lang)
        row = save_translation(
            db,
            document_id=payload.document_id,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            content=payload.content,
            translated_content=result.translated_content,
            preserved_terms=result.preserved_terms,
        )
    except Exception:
        # 계약(docs/api_contract.md): 실패 시 재시도 없이 즉시 원문 표시 -> FE가 502로 판단.
        # save_translation도 이 블록 안에 둬서, 동시 요청이 같은 (document_id, target_lang)로
        # 캐시 미스 후 동시에 저장을 시도해 UniqueConstraint에 걸리는 경우도 502로 처리한다.
        logger.exception(
            "translation failed for document_id=%s target_lang=%s", payload.document_id, payload.target_lang
        )
        return JSONResponse(status_code=502, content={"error": "translation_failed"})

    try:
        review_ai_output("translation", payload.content, result.translated_content)
    except Exception:
        # CIO 2차 검토는 참고용 — 실패해도 번역 응답 자체는 그대로 내려준다.
        logger.exception("cio review failed for document_id=%s", payload.document_id)

    return TranslationResponse(
        translated_content=row.translated_content,
        preserved_terms=result.preserved_terms,
        cached=False,
    )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.translation import TranslationRequest, TranslationResponse
from app.services.translation import deserialize_preserved_terms, get_cached_translation

router = APIRouter(prefix="/translations", tags=["translation"])


@router.post("", response_model=TranslationResponse)
def translate(payload: TranslationRequest, db: Session = Depends(get_db)) -> TranslationResponse:
    cached = get_cached_translation(db, payload.document_id, payload.target_lang)
    if cached is not None:
        return TranslationResponse(
            translated_content=cached.translated_content,
            preserved_terms=deserialize_preserved_terms(cached.preserved_terms),
            cached=True,
        )

    # TODO: LLM 호출 -> translated_content/preserved_terms 확보 후 save_translation()으로 저장
    raise HTTPException(status_code=501, detail="not implemented yet")

from fastapi import APIRouter, HTTPException

from app.schemas.translation import TranslationRequest, TranslationResponse

router = APIRouter(prefix="/translations", tags=["translation"])


@router.post("", response_model=TranslationResponse)
def translate(payload: TranslationRequest) -> TranslationResponse:
    # TODO: translation_cache 조회(document_id + target_lang) 후 캐시 미스면 LLM 호출
    raise HTTPException(status_code=501, detail="not implemented yet")

from fastapi import APIRouter, HTTPException

from app.schemas.writing_assistant import SuggestionRequest, SuggestionResponse

router = APIRouter(prefix="/writing-assistant", tags=["writing-assistant"])


@router.post("/suggestions", response_model=SuggestionResponse)
def get_suggestions(payload: SuggestionRequest) -> SuggestionResponse:
    # TODO: LLM 호출 — content + cursor_context 기반 구조/다음 문단/명확성 제안 생성
    raise HTTPException(status_code=501, detail="not implemented yet")

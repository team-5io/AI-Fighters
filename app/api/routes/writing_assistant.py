import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.writing_assistant import Suggestion, SuggestionRequest, SuggestionResponse
from app.services.writing_assistant import call_writing_assistant_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/writing-assistant", tags=["writing-assistant"])


@router.post("/suggestions", response_model=SuggestionResponse)
def get_suggestions(payload: SuggestionRequest) -> SuggestionResponse | JSONResponse:
    try:
        suggestions = call_writing_assistant_llm(payload.content, payload.cursor_context)
    except Exception:
        logger.exception("writing assistant suggestion generation failed for document_id=%s", payload.document_id)
        return JSONResponse(status_code=502, content={"error": "writing_assistant_failed"})

    return SuggestionResponse(
        suggestions=[Suggestion(type=s.type, text=s.text) for s in suggestions],
    )

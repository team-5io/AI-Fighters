import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.writing_assistant import Suggestion, SuggestionRequest, SuggestionResponse
from app.services.cio_orchestrator import review_ai_output
from app.services.writing_assistant import call_writing_assistant_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/writing-assistant", tags=["writing-assistant"])


@router.post("/suggestions", response_model=SuggestionResponse)
def get_suggestions(payload: SuggestionRequest) -> SuggestionResponse | JSONResponse:
    try:
        suggestions = call_writing_assistant_llm(
            payload.content, payload.cursor_context, locale=payload.locale
        )
    except Exception:
        logger.exception("writing assistant suggestion generation failed for document_id=%s", payload.document_id)
        return JSONResponse(status_code=502, content={"error": "writing_assistant_failed"})

    try:
        output_text = "\n".join(s.text for s in suggestions)
        review_ai_output("writing_assistant", payload.content, output_text)
    except Exception:
        # CIO 2차 검토는 참고용 — 실패해도 제안 응답 자체는 그대로 내려준다.
        logger.exception("cio review failed for document_id=%s", payload.document_id)

    return SuggestionResponse(
        suggestions=[Suggestion(type=s.type, text=s.text) for s in suggestions],
    )

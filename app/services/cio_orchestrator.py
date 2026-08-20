from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.services.llm_client import get_genai_client


class CioReviewVerdict(BaseModel):
    approved: bool
    concerns: list[str]


def review_ai_output(function_name: str, source_content: str, output_text: str) -> CioReviewVerdict:
    # AI 기능(Translation/Writing Assistant/DocumentLion)이 사용자에게 제안하려는 생성물을
    # 실제 원문 맥락과 비교해 2차 검토한다 (Notion "AI 제안 결과 2차 검토(CIO)"). 이 검토는
    # 참고용이며 절대 요청을 차단하지 않는다 — 실제 승인/반려/Merge 전권은 항상 사용자(R/A)에게 있다.
    prompt = (
        f"'{function_name}' 기능이 아래 원문을 바탕으로 생성한 결과물을 검토해라.\n"
        "생성물이 원문의 맥락과 논점을 벗어나거나, 원문에 없는 내용을 지어내거나, "
        "명백히 부적절한 내용이 있으면 approved를 false로 하고 concerns에 구체적인 이유를 적어라. "
        "문제 없으면 approved를 true, concerns는 빈 배열로 반환해라.\n\n"
        f"원문:\n{source_content}\n\n"
        f"생성물:\n{output_text}"
    )
    response = get_genai_client().models.generate_content(
        model=settings.effective_cio_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CioReviewVerdict,
        ),
    )
    result = response.parsed
    if not isinstance(result, CioReviewVerdict):
        raise RuntimeError("cio_review_failed: empty or malformed LLM response")
    return result

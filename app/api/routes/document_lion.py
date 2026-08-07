from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.document_lion import ReviewRequest, ReviewResponse

router = APIRouter(prefix="/document-lion", tags=["document-lion"])


@router.post("/reviews", response_model=ReviewResponse)
def create_review(payload: ReviewRequest) -> ReviewResponse:
    # TODO: Document Graph 연결 문서 조회 -> 충돌/정합성/Charter 위반 검토 -> document_review(+issue) 저장
    # critical 이슈가 하나라도 있으면 overall_verdict = reject_recommended
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: UUID) -> ReviewResponse:
    # TODO: document_review + document_review_issue 조회
    raise HTTPException(status_code=501, detail="not implemented yet")

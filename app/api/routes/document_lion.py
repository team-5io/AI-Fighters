import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document_review import DocumentReview
from app.models.document_review_issue import DocumentReviewIssue
from app.schemas.document_lion import ReviewIssue, ReviewRequest, ReviewResponse
from app.services.document_lion import (
    CharterRuleContext,
    call_document_lion_llm,
    create_review,
    fetch_adopted_charter_rules,
    get_review,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document-lion", tags=["document-lion"])


def _to_response(review: DocumentReview, issues: list[DocumentReviewIssue]) -> ReviewResponse:
    return ReviewResponse(
        review_id=review.id,
        overall_verdict=review.overall_verdict,
        issues=[
            ReviewIssue(
                severity=issue.severity,
                issue_type=issue.issue_type,
                description=issue.description,
                related_document_id=issue.related_document_ref,
                charter_rule_id=issue.charter_rule_id,
                location_ref=issue.location_ref,
            )
            for issue in issues
        ],
    )


@router.post("/reviews", response_model=ReviewResponse)
def create_review_route(payload: ReviewRequest, db: Session = Depends(get_db)) -> ReviewResponse | JSONResponse:
    try:
        charter_rules = fetch_adopted_charter_rules(db, payload.team_id)
        rule_contexts = [
            CharterRuleContext(id=rule.id, title=rule.title, description=rule.description) for rule in charter_rules
        ]
        llm_result = call_document_lion_llm(payload.content, rule_contexts)
        review, issues = create_review(
            db, payload.document_id, payload.doc_pr_id, payload.trigger_type, payload.requested_by, llm_result.issues
        )
    except Exception:
        logger.exception("document lion review failed for document_id=%s", payload.document_id)
        return JSONResponse(status_code=502, content={"error": "document_lion_review_failed"})

    return _to_response(review, issues)


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
def get_review_route(review_id: UUID, db: Session = Depends(get_db)) -> ReviewResponse:
    result = get_review(db, review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="review_not_found")
    review, issues = result
    return _to_response(review, issues)

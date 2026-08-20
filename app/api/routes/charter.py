import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.charter_rule import CharterRule
from app.schemas.charter import (
    AdoptRulesRequest,
    CharterRuleOut,
    CharterRulesResponse,
    GenerateCharterRequest,
    GenerateCharterResponse,
    RuleStatus,
    UpdateRuleRequest,
)
from app.services.charter import (
    adopt_rules as adopt_rules_service,
    call_charter_llm,
    create_draft_rules,
    get_rule,
    list_rules as list_rules_service,
    update_rule as update_rule_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/charter", tags=["charter"])


def _to_out(rule: CharterRule) -> CharterRuleOut:
    return CharterRuleOut(id=rule.id, status=rule.status, title=rule.title, description=rule.description)


@router.post("/generate", response_model=GenerateCharterResponse)
def generate_charter(
    payload: GenerateCharterRequest, db: Session = Depends(get_db)
) -> GenerateCharterResponse | JSONResponse:
    try:
        llm_rules = call_charter_llm(locale=payload.locale)
        rows = create_draft_rules(db, payload.team_id, llm_rules)
    except Exception:
        logger.exception("charter generation failed for team_id=%s", payload.team_id)
        return JSONResponse(status_code=502, content={"error": "charter_generation_failed"})

    return GenerateCharterResponse(rules=[_to_out(row) for row in rows])


@router.patch("/rules/{rule_id}", status_code=204)
def update_rule(rule_id: UUID, payload: UpdateRuleRequest, db: Session = Depends(get_db)) -> None:
    rule = get_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule_not_found")
    update_rule_service(db, rule, payload.title, payload.description)


@router.post("/adopt", status_code=204)
def adopt_rules(payload: AdoptRulesRequest, db: Session = Depends(get_db)) -> None:
    adopt_rules_service(db, payload.team_id, payload.rule_ids, payload.adopted_by)


@router.get("/rules", response_model=CharterRulesResponse)
def list_rules(
    team_id: int = Query(..., alias="teamId"),
    status: RuleStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> CharterRulesResponse:
    rules = list_rules_service(db, team_id, status)
    return CharterRulesResponse(rules=[_to_out(row) for row in rules])

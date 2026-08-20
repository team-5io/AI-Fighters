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
from app.services.ai_text_translation import TranslatableField, translate_fields
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


_TRANSLATABLE_RULE_FIELDS = ("title", "description")


def _to_out(rule: CharterRule, translated: dict | None = None) -> CharterRuleOut:
    translated = translated or {}
    return CharterRuleOut(
        id=rule.id,
        status=rule.status,
        title=translated.get((rule.id, "title"), rule.title),
        description=translated.get((rule.id, "description"), rule.description),
    )


@router.post("/generate", response_model=GenerateCharterResponse)
def generate_charter(
    payload: GenerateCharterRequest, db: Session = Depends(get_db)
) -> GenerateCharterResponse | JSONResponse:
    try:
        llm_rules = call_charter_llm(locale=payload.locale)
        rows = create_draft_rules(db, payload.team_id, llm_rules, locale=payload.locale)
    except Exception:
        logger.exception("charter generation failed for team_id=%s", payload.team_id)
        return JSONResponse(status_code=502, content={"error": "charter_generation_failed"})

    return GenerateCharterResponse(rules=[_to_out(row) for row in rows])


@router.patch("/rules/{rule_id}", status_code=204)
def update_rule(rule_id: UUID, payload: UpdateRuleRequest, db: Session = Depends(get_db)) -> None:
    rule = get_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule_not_found")
    update_rule_service(db, rule, payload.title, payload.description, locale=payload.locale)


@router.post("/adopt", status_code=204)
def adopt_rules(payload: AdoptRulesRequest, db: Session = Depends(get_db)) -> None:
    adopt_rules_service(db, payload.team_id, payload.rule_ids, payload.adopted_by)


@router.get("/rules", response_model=CharterRulesResponse)
def list_rules(
    team_id: int = Query(..., alias="teamId"),
    status: RuleStatus | None = Query(None),
    locale: str | None = Query(None),
    db: Session = Depends(get_db),
) -> CharterRulesResponse:
    rules = list_rules_service(db, team_id, status)
    # 저장된 규칙은 생성 시점 언어로 굳어 있다. 다국어 팀에서는 나중에 합류한
    # 사용자도 기존 규칙을 읽어야 하므로 조회 시점에 번역한다.
    fields = [
        TranslatableField(
            entity_type="charter_rule",
            entity_id=row.id,
            field=name,
            source_locale=row.source_locale,
            text=getattr(row, name),
        )
        for row in rules
        for name in _TRANSLATABLE_RULE_FIELDS
    ]
    translated = translate_fields(db, fields, locale)
    return CharterRulesResponse(rules=[_to_out(row, translated) for row in rules])

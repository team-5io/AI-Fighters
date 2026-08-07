from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.schemas.charter import (
    AdoptRulesRequest,
    CharterRulesResponse,
    GenerateCharterRequest,
    GenerateCharterResponse,
    UpdateRuleRequest,
)

router = APIRouter(prefix="/charter", tags=["charter"])


@router.post("/generate", response_model=GenerateCharterResponse)
def generate_charter(payload: GenerateCharterRequest) -> GenerateCharterResponse:
    # TODO: 팀원 협업 방식 분석 -> charter_rule 여러 건 생성(status=draft, generated_by=ai)
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: UUID, payload: UpdateRuleRequest) -> None:
    # TODO: charter_rule 단건 title/description 수정
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/adopt")
def adopt_rules(payload: AdoptRulesRequest) -> None:
    # TODO: 지정된 rule_ids 상태를 adopted로 일괄 변경, adopted_by_ref/adopted_at 기록
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.get("/rules", response_model=CharterRulesResponse)
def list_rules(team_id: UUID = Query(...)) -> CharterRulesResponse:
    # TODO: team_ref 기준 charter_rule 목록 조회
    raise HTTPException(status_code=501, detail="not implemented yet")

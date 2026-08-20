from typing import Literal
from uuid import UUID

from app.schemas.base import CamelModel

RuleStatus = Literal["draft", "adopted", "archived"]


class GenerateCharterRequest(CamelModel):
    team_id: int
    # BE 사용자 프로필의 선호 언어. optional이다 — required로 잡으면 BE가 아직 locale을
    # 실어보내지 않는 구간의 모든 호출이 422가 되고, BE가 이를 502로 감싸 내려보낸다.
    locale: str | None = None


class CharterRuleOut(CamelModel):
    id: UUID
    status: RuleStatus
    title: str
    description: str


class GenerateCharterResponse(CamelModel):
    rules: list[CharterRuleOut]


class UpdateRuleRequest(CamelModel):
    title: str
    description: str


class AdoptRulesRequest(CamelModel):
    team_id: int
    rule_ids: list[UUID]
    adopted_by: UUID


class CharterRulesResponse(CamelModel):
    rules: list[CharterRuleOut]

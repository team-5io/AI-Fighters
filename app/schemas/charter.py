from typing import Literal
from uuid import UUID

from app.schemas.base import CamelModel

RuleStatus = Literal["draft", "adopted", "archived"]


class GenerateCharterRequest(CamelModel):
    team_id: int


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

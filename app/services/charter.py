from datetime import datetime, timezone
from uuid import UUID

from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.charter_rule import CharterRule
from app.services.llm_client import get_genai_client


class LLMCharterRule(BaseModel):
    title: str
    description: str


class LLMCharterRulesResult(BaseModel):
    rules: list[LLMCharterRule]


def call_charter_llm(count: int | None = None) -> list[LLMCharterRule]:
    rule_count = count if count is not None else settings.charter_generation_rule_count
    # teamId만으로는 실제 협업 이력(Doc PR 리뷰 시간, 커뮤니케이션 패턴 등)을 분석할 데이터
    # 소스가 아직 없다 (BE 활동 로그 연동 전) — 그래서 실제 팀 행동 분석 대신, 일반적인
    # 협업 모범 사례 기반 초안을 생성한다. status가 항상 "draft"로 시작해 팀이 검토 후
    # 채택하는 구조라 초안 품질이 낮아도 무방하고, 실제 활동 데이터가 붙으면 이 프롬프트에
    # 주입하는 식으로 확장하면 된다.
    prompt = (
        f"Generate exactly {rule_count} starter team collaboration charter rules for a "
        "software team that reviews documentation changes through a Doc PR workflow "
        "(similar to a git pull request, but for docs). Cover distinct topics such as "
        "review turnaround time, communication channels, documentation standards, "
        "conflict resolution, and meeting norms. Each rule needs a short title and a "
        "one-paragraph description, written in Korean."
    )
    response = get_genai_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMCharterRulesResult,
        ),
    )
    result = response.parsed
    if not isinstance(result, LLMCharterRulesResult):
        raise RuntimeError("charter_generation_failed: empty or malformed LLM response")
    return result.rules[:rule_count]


def create_draft_rules(db: Session, team_id: UUID, llm_rules: list[LLMCharterRule]) -> list[CharterRule]:
    rows = [
        CharterRule(
            team_ref=team_id,
            title=rule.title,
            description=rule.description,
            status="draft",
            generated_by="ai",
        )
        for rule in llm_rules
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def get_rule(db: Session, rule_id: UUID) -> CharterRule | None:
    return db.get(CharterRule, rule_id)


def update_rule(db: Session, rule: CharterRule, title: str, description: str) -> CharterRule:
    rule.title = title
    rule.description = description
    db.commit()
    db.refresh(rule)
    return rule


def adopt_rules(db: Session, team_id: UUID, rule_ids: list[UUID], adopted_by: UUID) -> None:
    db.query(CharterRule).filter(
        CharterRule.team_ref == team_id,
        CharterRule.id.in_(rule_ids),
    ).update(
        {
            "status": "adopted",
            "adopted_by_ref": adopted_by,
            "adopted_at": datetime.now(timezone.utc),
        },
        synchronize_session=False,
    )
    db.commit()


def list_rules(db: Session, team_id: UUID, status: str | None = None) -> list[CharterRule]:
    query = db.query(CharterRule).filter(CharterRule.team_ref == team_id)
    if status is not None:
        query = query.filter(CharterRule.status == status)
    return query.order_by(CharterRule.created_at).all()

from datetime import datetime, timezone
from uuid import UUID

from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.locale import language_instruction, normalize_locale
from app.models.charter_rule import CharterRule
from app.services.llm_client import get_genai_client


class LLMCharterRule(BaseModel):
    title: str
    description: str


class LLMCharterRulesResult(BaseModel):
    rules: list[LLMCharterRule]


def call_charter_llm(count: int | None = None, locale: str | None = None) -> list[LLMCharterRule]:
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
        "one-paragraph description. "
        f"{language_instruction(locale)}"
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


def create_draft_rules(
    db: Session, team_id: int, llm_rules: list[LLMCharterRule], locale: str | None = None
) -> list[CharterRule]:
    # 쓰기 시점에 원본 언어를 채운다. 비어 있으면 이후 조회 시 무슨 언어에서
    # 번역해야 하는지 알 수 없어 번역 자체가 불가능하다.
    source_locale = normalize_locale(locale)
    rows = [
        CharterRule(
            team_ref=team_id,
            title=rule.title,
            description=rule.description,
            status="draft",
            generated_by="ai",
            source_locale=source_locale,
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


def update_rule(
    db: Session, rule: CharterRule, title: str, description: str, locale: str | None = None
) -> CharterRule:
    rule.title = title
    rule.description = description
    # 일본 사용자가 한국어 규칙을 일본어로 고쳐 쓸 수 있다. locale 미전달 시에는
    # 기존 원본 언어를 덮어쓰지 않는다 — BE 미배포 구간에서 잘못된 값이 박히면 안 된다.
    if locale is not None:
        rule.source_locale = normalize_locale(locale)
    db.commit()
    db.refresh(rule)
    return rule


def adopt_rules(db: Session, team_id: int, rule_ids: list[UUID], adopted_by: UUID) -> None:
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


def list_rules(db: Session, team_id: int, status: str | None = None) -> list[CharterRule]:
    query = db.query(CharterRule).filter(CharterRule.team_ref == team_id)
    if status is not None:
        query = query.filter(CharterRule.status == status)
    return query.order_by(CharterRule.created_at).all()

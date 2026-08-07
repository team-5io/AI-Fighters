from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """요청/응답 JSON은 camelCase(api_contract.md 기준), 파이썬 내부는 snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

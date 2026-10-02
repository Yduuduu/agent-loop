"""인덱싱된 정책 문서 원문을 구조화된 정책 요약(PolicyItem 리스트)으로 추출한다.

Phase 6의 인제스천 상태 머신(uploaded -> chunking -> embedding -> indexed | failed)과는
완전히 분리된 후처리 단계다 — 실패해도 문서 자체(검색 가능 여부)에는 영향이 없다.
"""

from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, create_model

from app.core.config import get_settings
from app.core.policy_categories import OTHER_POLICY_TYPE, policy_types_for

SUMMARIZE_SYSTEM_PROMPT = """당신은 교육 플랫폼(클래스·콘텐츠 구독·도서 판매)의 환불 정책 문서를
정리하는 보조원이다. 아래 정책 문서 원문을 읽고, 실제로 서비스에 적용되는 규칙만
뽑아 구조화된 항목 리스트로 정리하라.

원칙:
- 이 문서의 대분류는 "{product_category}"이다.
- 각 항목의 policy_type은 다음 소분류 중 하나로만 분류한다: {policy_types}
- title은 한 줄 요약(예: "진도율 1/3 미만 시 2/3 환불"), summary는 1~2문장 설명이다.
- source_excerpt는 반드시 원문에서 그대로 발췌한다 — 새로 지어내지 않는다.
- 원문에 없는 규칙을 추론해서 만들어내지 마라. 애매하면 "{other}"로 분류하고 있는
  그대로만 요약하라."""

SUMMARIZE_USER_TEMPLATE = """정책 문서 원문:
{document_text}"""


class PolicyItem(BaseModel):
    # 소분류(app/core/policy_categories.py). 저장/응답 계약에서는 문자열로 받는다 —
    # 분류 체계가 바뀌어도 이미 저장된 요약이 검증 오류로 깨지지 않게 하기 위함이다.
    policy_type: str
    title: str
    summary: str
    source_excerpt: str


# (문서 원문, 대분류 | None) -> 정책 항목 리스트
SummarizeFn = Callable[[str, str | None], Awaitable[list[PolicyItem]]]


def _structured_output_model(policy_types: list[str]) -> type[BaseModel]:
    """LLM 출력은 해당 대분류의 소분류만 고르도록 Literal로 좁힌 모델을 동적으로 만든다."""
    item_model = create_model(
        "PolicyItemOutput",
        policy_type=(Literal[tuple(policy_types)], ...),
        title=(str, ...),
        summary=(str, ...),
        source_excerpt=(str, ...),
    )
    return create_model("PolicySummary", items=(list[item_model], ...))


async def default_summarize_policy_document(
    document_text: str, product_category: str | None
) -> list[PolicyItem]:
    settings = get_settings()
    policy_types = policy_types_for(product_category)
    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=settings.google_api_key)
    structured_llm = llm.with_structured_output(_structured_output_model(policy_types))
    system_prompt = SUMMARIZE_SYSTEM_PROMPT.format(
        product_category=product_category or "미지정",
        policy_types=", ".join(policy_types),
        other=OTHER_POLICY_TYPE,
    )
    user_prompt = SUMMARIZE_USER_TEMPLATE.format(document_text=document_text)
    result = await structured_llm.ainvoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return [PolicyItem(**item.model_dump()) for item in result.items]  # type: ignore[union-attr]

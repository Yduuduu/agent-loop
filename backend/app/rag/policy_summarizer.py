"""인덱싱된 정책 문서 원문을 구조화된 정책 요약(PolicyItem 리스트)으로 추출한다.

Phase 6의 인제스천 상태 머신(uploaded -> chunking -> embedding -> indexed | failed)과는
완전히 분리된 후처리 단계다 — 실패해도 문서 자체(검색 가능 여부)에는 영향이 없다.
"""

from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.core.config import get_settings

SUMMARIZE_SYSTEM_PROMPT = """당신은 이커머스 환불 정책 문서를 정리하는 보조원이다.
아래 정책 문서 원문을 읽고, 실제로 서비스에 적용되는 규칙만 뽑아 구조화된
항목 리스트로 정리하라.

원칙:
- 각 항목은 category(환불기한/파손기준/증빙요건/고액기준/기타) 중 하나로 분류한다.
- title은 한 줄 요약(예: "파손 상품 7일 이내 무료 반품"), summary는 1~2문장 설명이다.
- source_excerpt는 반드시 원문에서 그대로 발췌한다 — 새로 지어내지 않는다.
- 원문에 없는 규칙을 추론해서 만들어내지 마라. 애매하면 "기타"로 분류하고 있는
  그대로만 요약하라."""

SUMMARIZE_USER_TEMPLATE = """정책 문서 원문:
{document_text}"""


class PolicyItem(BaseModel):
    category: Literal["환불기한", "파손기준", "증빙요건", "고액기준", "기타"]
    title: str
    summary: str
    source_excerpt: str


class PolicySummary(BaseModel):
    items: list[PolicyItem]


SummarizeFn = Callable[[str], Awaitable[list[PolicyItem]]]


async def default_summarize_policy_document(document_text: str) -> list[PolicyItem]:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=settings.google_api_key)
    structured_llm = llm.with_structured_output(PolicySummary)
    result = await structured_llm.ainvoke(
        [
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": SUMMARIZE_USER_TEMPLATE.format(document_text=document_text)},
        ]
    )
    return result.items  # type: ignore[union-attr]

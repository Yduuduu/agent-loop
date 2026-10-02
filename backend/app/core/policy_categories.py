"""정책서 분류 체계(대분류 → 소분류)의 단일 소스.

교육 플랫폼(클래스 단건 판매, 콘텐츠 구독, 도서 판매 등)을 가정한 2단계 분류다.
- 대분류(product_category): 문서 단위. 업로드 시 관리자가 고른다.
- 소분류(policy_type): 정책 항목 단위. 요약 LLM이 해당 대분류의 소분류 중 하나로 분류한다.

프론트는 GET /api/knowledge-base/categories로 이 값을 그대로 받아 쓰므로,
분류를 바꾸려면 여기만 고치면 된다. 라벨 자체가 저장값이라 이미 저장된
문서/요약이 있는 라벨의 이름을 바꾸면 기존 데이터는 "미분류"처럼 보이게 된다.
"""

POLICY_CATEGORIES: dict[str, list[str]] = {
    "클래스": [
        "수강 전 환불",
        "진도율 기준 환불",
        "수강기간 만료",
        "라이브·오프라인 클래스",
        "강의자료 다운로드",
    ],
    "콘텐츠 구독": [
        "월 구독 해지",
        "월 구독 첫 결제 환불",
        "연 구독 중도 해지",
        "자동 갱신",
        "무료체험 유료 전환",
        "플랜 변경",
    ],
    "도서": [
        "단순 변심 반품",
        "파손·오배송",
        "반품 불가 조건",
        "전자책",
    ],
    "패키지·번들": [
        "번들 부분 환불",
        "사은품",
    ],
    "결제·혜택 공통": [
        "쿠폰·할인",
        "포인트·적립금",
        "결제수단별 환불",
        "할부·분할결제",
        "프로모션 상품",
        "B2B·단체 구매",
    ],
    "예외·특수 상황": [
        "서비스 장애",
        "폐강·강사 이탈",
        "중복 결제",
        "미성년자 결제",
        "부정 이용",
        "특별 사유",
    ],
}

# 대분류 미지정 문서(Phase 6 이전 업로드분 등)와, 어느 소분류에도 맞지 않는 항목의 라벨.
UNCATEGORIZED = "미분류"
OTHER_POLICY_TYPE = "기타"


def is_valid_product_category(value: str) -> bool:
    return value in POLICY_CATEGORIES


def policy_types_for(product_category: str | None) -> list[str]:
    """요약 LLM이 고를 수 있는 소분류 후보. 대분류가 없으면 전체 소분류를 허용한다."""
    if product_category in POLICY_CATEGORIES:
        types = list(POLICY_CATEGORIES[product_category])
    else:
        types = [t for group in POLICY_CATEGORIES.values() for t in group]
    return [*types, OTHER_POLICY_TYPE]

"""목업 환불 정책 PDF(backend/data/policy_docs/refund_policy.pdf)를 생성한다.

이 스크립트는 최초 1회 정적 픽스처를 만들기 위한 개발용 도구다
(reportlab, requirements-dev.txt 전용 — 런타임 ingest 경로는 pypdf만 사용).
정책 문서 자체를 수정하려면 이 스크립트의 SECTIONS를 고쳐 재실행한다.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "policy_docs" / "refund_policy.pdf"
FONT_NAME = "HYSMyeongJo-Medium"

SECTIONS = [
    (
        "1. 반품/환불 가능 기간",
        [
            "고객은 상품 수령일로부터 14일 이내에 반품 및 환불을 요청할 수 있다.",
            "반품 기한이 지난 요청은 원칙적으로 자동 거절 처리한다.",
            "단, 상품 파손 등 품질 하자가 명백한 경우",
            "기한 내 요청에 한해 예외 승인 절차를 적용한다.",
        ],
    ),
    (
        "2. 파손/불량 상품 환불",
        [
            "수령 시점에 이미 파손되었거나 정상 작동하지 않는 상품은",
            "환불 기한 내 요청 시 자동 승인 대상이다.",
            "파손 여부 판정은 고객이 제출한 설명과 증빙 사진을 근거로 한다.",
            "파손이 명확하고 증빙이 충분한 경우 상담원 개입 없이 즉시 환불을 진행할 수 있다.",
        ],
    ),
    (
        "3. 고액 환불 승인 정책",
        [
            "환불 예정 금액이 500달러를 초과하는 건은 자동 승인 대상에서 제외하고,",
            "반드시 상담원(사람)의 최종 검토를 거쳐야 한다.",
            "고액 기준은 주문 내 환불 대상 품목 합계 금액을 기준으로 산정한다.",
            "고액 환불 건은 파손 여부와 무관하게 사람 검토 대기 상태로 분류한다.",
        ],
    ),
    (
        "4. 증빙 자료 기준",
        [
            "파손을 근거로 한 환불 요청은 파손 부위가 식별 가능한 사진을 첨부해야 한다.",
            "사진이 흐릿하거나 파손 여부를 육안으로 판단하기 어려운 경우,",
            "또는 증빙 사진이 누락된 경우 자동 판정을 내리지 않고 사람 검토로 전환한다.",
            "증빙이 모호한 건을 자동으로 승인하거나 거절해서는 안 된다.",
        ],
    ),
    (
        "5. 단순 변심 환불",
        [
            "단순 변심(색상/사이즈 불만족, 기대와 다름 등)에 의한 반품은",
            "반품 기한 내 요청이라도 파손이 아니므로 자동 승인 대상이 아니다.",
            "저액(50달러 이하) 단순 변심 건은 정책상 해피패스로 간주해 자동 승인할 수 있으나,",
            "그 외 단순 변심 건은 상담원 검토를 권장한다.",
        ],
    ),
]

TITLE = "AgentOps 환불 정책 (목업 문서)"


def build_pdf() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    c.setFont(FONT_NAME, 16)
    c.drawString(margin, y, TITLE)
    y -= 12 * mm

    for heading, paragraphs in SECTIONS:
        if y < margin + 30 * mm:
            c.showPage()
            y = height - margin

        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, heading)
        y -= 8 * mm

        c.setFont(FONT_NAME, 10.5)
        for paragraph in paragraphs:
            for line in _wrap(paragraph, max_chars=44):
                if y < margin:
                    c.showPage()
                    c.setFont(FONT_NAME, 10.5)
                    y = height - margin
                c.drawString(margin, y, line)
                y -= 6.5 * mm
            y -= 2 * mm

        y -= 6 * mm

    c.save()
    print(f"wrote {OUTPUT_PATH}")


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        current += ch
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


if __name__ == "__main__":
    build_pdf()

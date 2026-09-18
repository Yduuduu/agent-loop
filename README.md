# AgentOps

B2B CS 환불 자동화 에이전트(LangGraph) + 실시간 관제 대시보드(Next.js + FastAPI SSE).

에이전트의 내부 추론 과정(Tool Calling, RAG 검색)을 SSE로 스트리밍해 시각화하고,
필요 시 관리자가 개입(Human-in-the-Loop)할 수 있는 프로덕션급 구조를 목표로 한다.

## 모노레포 구조

```
agent-loop/
├── backend/    # FastAPI + LangGraph 에이전트
├── frontend/   # Next.js 대시보드
└── docs/       # 로드맵 / 스펙 문서
```

상세 설계 및 Phase별 로드맵은 `docs/roadmap.md` 참고.

## 로컬 개발

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

`GET http://localhost:8000/health` → `{"status": "ok"}`

### RefundAgent 단독 실행 (Phase 1)

DB 마이그레이션 → 목업 주문 시딩 → 정책 문서 인덱싱 → CLI 실행 순서로 진행한다.
`.env`에 실제 `OPENAI_API_KEY`가 있어야 damage_assessment/decision 노드가 동작한다.

```bash
cd backend
alembic upgrade head
PYTHONPATH=. python scripts/seed_db.py            # backend/data/mock_orders.json 6건 적재
PYTHONPATH=. python scripts/ingest_policy_docs.py  # backend/data/policy_docs/*.pdf → ChromaDB
PYTHONPATH=. python scripts/run_agent_cli.py \
  --order-id ORD-1001 \
  --message "제품이 파손된 상태로 도착했습니다." \
  --image mock_evidence/ord-1001-damage-1.jpg
```

5개 시나리오 pytest(LLM은 fake로 대체해 결정론적으로 검증):

```bash
PYTHONPATH=. pytest tests/test_refund_agent.py -v
```

### FastAPI SSE 스트리밍 (Phase 2)

RefundAgent 실행을 HTTP API로 감싼다. `POST`로 케이스를 만들면 즉시 백그라운드에서
그래프 실행이 시작되고, `GET .../stream`에 연결하면 진행 상황이 SSE로 온다
(`node_start` → `tool_call`/`node_end` 반복 → `decision`|`error`로 종료).

```bash
cd backend
uvicorn app.main:app --reload

# 다른 터미널에서
curl -X POST http://localhost:8000/api/refund-requests \
  -F "order_id=ORD-1001" -F "message=제품이 파손된 상태로 도착했습니다."
# → {"case_id": "..."}

curl -N http://localhost:8000/api/refund-requests/<case_id>/stream
curl http://localhost:8000/api/refund-requests/<case_id>   # 상태 폴링(재연결용)
```

API 통합 테스트(LLM fake, httpx 스트리밍):

```bash
PYTHONPATH=. pytest tests/test_refund_api.py -v
```

### HITL 일시정지/재개 (Phase 3)

고액 환불 등으로 `flag_for_human`에 도달하면 LangGraph `interrupt()`가 실행을
진짜로 멈추고 `AsyncSqliteSaver` 체크포인터(메인 DB와 같은 SQLite 파일)에
영속화한다 — 백엔드 프로세스를 재시작해도 재개할 수 있다.

```bash
# 케이스가 고액이라 awaiting_human으로 멈췄다고 가정
curl -N http://localhost:8000/api/refund-requests/<case_id>/stream
# → ... event: awaiting_human (스트림은 여기서 끝남, 최종 판정 아직 없음)

curl -X POST http://localhost:8000/api/refund-requests/<case_id>/resume \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "admin_note": "관리자 확인 후 승인"}'
# → {"case_id": "..."} — 재개된 실행이 백그라운드에서 시작됨

# resume 시점엔 원래 SSE 연결이 끊겨 있을 수 있으므로, 프론트는 resume 응답을
# 받은 뒤 같은 스트림 엔드포인트에 새로 연결해 이어지는 이벤트를 본다.
curl -N http://localhost:8000/api/refund-requests/<case_id>/stream
# → event: decision (approve)

curl "http://localhost:8000/api/refund-requests?status=awaiting_human"  # 관리자 대기열
```

resume 페이로드 계약: `{"action": "approve" | "reject" | "takeover", "admin_note": str | None, "admin_message": str | None}`.
`approve`/`reject`는 `admin_note`를 사유로 쓰고, `takeover`(관리자 직접 개입)는
그래프가 재추론하지 않고 `admin_message`가 곧바로 최종 사유가 되며 `decision`은
`"resolved"`로 기록된다.

체크포인터 영속성(프로세스 재시작 후 재개) + resume 3가지 경로(approve/reject/takeover) 테스트:

```bash
PYTHONPATH=. pytest tests/test_refund_agent.py tests/test_refund_api.py -v
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL, 기본값 http://localhost:8000
npm run dev
```

`http://localhost:3000` → `/dashboard`로 리다이렉트.

### SSE 실시간 추론 뷰어 (Phase 4)

백엔드(`uvicorn app.main:app --reload`)를 먼저 띄운 상태에서:

1. `/dashboard` — 전체 케이스 목록(React Query 폴링)
2. `/refund-cases` — 신규 환불 요청 제출 폼(수동 테스트용, mock_orders.json의 order_id 사용)
3. 제출하면 `/refund-cases/[case_id]`로 이동 — 네이티브 `EventSource`(`lib/sse-client.ts`)로
   스트림에 연결해 `node_start`/`tool_call`/`node_end`/`decision`/`awaiting_human`/`error`를
   Zustand 스토어(`store/refund-stream-store.ts`)에 반영, 파이프라인 단계별 진행 상황을
   실시간 렌더링한다(`components/agent-viewer/`). SSE 연결이 끊기면 케이스 상세의
   React Query 폴링(`useRefundCase`)이 상태의 최종 진실 소스 역할을 한다.

모의 EventSource 이벤트 시퀀스로 스토어/컴포넌트 테스트(Vitest):

```bash
cd frontend
npm run test
```

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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:3000`

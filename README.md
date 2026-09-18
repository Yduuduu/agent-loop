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

백엔드 `.venv` 설치와 프론트엔드 `npm install`이 끝난 상태라면, 루트에서 아래 명령 한 줄로
백엔드(uvicorn)와 프론트엔드(next dev)를 동시에 띄울 수 있다(Ctrl+C로 둘 다 종료):

```bash
./dev.sh
```

최초 설정이나 개별 실행이 필요하면 아래 섹션을 따른다.

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
`.env`에 실제 `GOOGLE_API_KEY`(Gemini)가 있어야 damage_assessment/decision 노드가 동작한다.

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

### 지식베이스 동적 업데이트 (Phase 6)

`POST /api/knowledge-base/documents`로 PDF를 업로드하면 즉시 백그라운드에서
`uploaded → chunking → embedding → indexed`(또는 `failed`) 순으로 인제스천이
진행되고, `GET .../documents/{doc_id}/stream`으로 각 단계 진행률(`progress_pct`)을
SSE로 받는다. Phase 1/2와 같은 어댑터 패턴(`app/api/kb_runner.py`)이며 같은
`event_bus`를 공유한다(refund case와 doc_id 네임스페이스만 `kb:` 접두어로 분리).
버전 관리는 MVP 범위에서 추가만 지원한다 — 같은 파일명을 다시 올려도 이전
청크를 덮어쓰지 않는다(벡터 id가 doc_id로 접두되어 매 업로드가 고유함).

```bash
cd backend
uvicorn app.main:app --reload

curl -X POST http://localhost:8000/api/knowledge-base/documents \
  -F "file=@data/policy_docs/refund_policy.pdf;type=application/pdf"
# → {"doc_id": "..."}

curl -N http://localhost:8000/api/knowledge-base/documents/<doc_id>/stream
# → event: chunking (25%) → embedding (60%) → indexed (100%, chunk_count)

curl http://localhost:8000/api/knowledge-base/documents        # 목록(상태/청크수)
```

통합 테스트는 실제 임베딩 API를 호출하지 않도록 `DeterministicFakeEmbedding` +
임시 디렉터리 Chroma를 주입하고, "업로드됨" 표시가 아니라 `search_policy_chunks`
(실제 검색 경로)로 새로 올린 문서의 청크가 조회되는지까지 검증한다:

```bash
PYTHONPATH=. pytest tests/test_knowledge_base_api.py -v
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

### HITL 관리자 제어 (Phase 5)

`/refund-cases/[id]`가 케이스 상태에 따라 분기한다: `in_progress`는 뷰어만,
`awaiting_human`은 뷰어 + `components/hitl/HitlPanel`(플래그 사유·환불액,
승인/거절/직접개입), `completed`/`failed`는 뷰어 + 최종 요약. 이 요약은
SSE(Zustand)가 아니라 React Query 폴링 데이터로 그리므로, 완료된 지 오래된
케이스를 방금 눌러서 들어가도(라이브 스트림을 놓쳤어도) 항상 정확하다.

- 승인은 바로 실행되고, 거절/직접개입은 되돌릴 수 없어 확인 단계를 거친다.
- resume 성공 시 케이스 상세 페이지가 `AgentViewerStream`을 리마운트해 새 SSE
  스트림에 재연결한다(같은 caseId로는 재연결 트리거가 안 되므로 `key`를 바꿔 강제).
- `/dashboard`에 `awaiting_human_since` 오름차순(가장 오래 기다린 순) 대기열
  섹션이 추가된다.
- MVP 단순화: 다중 관리자 동시 처리 충돌 방지는 다루지 않는다(last-write-wins).

```bash
cd frontend
npm run test    # HitlPanel/대기열 정렬 포함
```

### 지식베이스 업로드 UI (Phase 6)

`/knowledge-base`에서 PDF를 드래그앤드롭하거나 클릭해서 선택하면(타입/크기
클라이언트 검증 후) 즉시 업로드되고, `components/kb-upload/UploadProgress`가
SSE(`lib/kb-sse-client.ts`)로 단계별 라벨·퍼센트를 실시간으로 보여준다.
완료/실패 시 문서 목록(React Query)도 함께 갱신된다.

```bash
cd frontend
npm run test    # 검증 로직/SSE 클라이언트/업로드 추적 훅/DropZone 포함
```

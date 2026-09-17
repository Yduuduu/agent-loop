# AgentOps — B2B CS 환불 자동화 에이전트 + 관제 대시보드 로드맵

## Context

`/Users/choiyunju/agent-loop`는 완전히 빈 저장소(커밋 0개, `.git`만 존재)이며, 여기에 "AgentOps"라는 신규 프로젝트를 처음부터 구축한다. 목적은 단순 챗봇 텍스트 응답 수준을 넘어, LangGraph 기반 '목적 달성형 AI 에이전트(CS 환불 처리)'와 이를 관제/개입할 수 있는 프로덕션급 관리자 대시보드를 만드는 것이다. 차별화 포인트는 Next.js + FastAPI의 SSE 스트리밍으로 에이전트의 내부 사고 과정(Tool Calling, RAG 검색)을 실시간 시각화하는 것.

프로젝트 규모가 매우 크기 때문에(에이전트+RAG+SSE+HITL+대시보드), 이번 플랜의 산출물은 **코드가 아니라 Phase별 로드맵 + 태스크 브레이크다운 문서**다. 각 Phase는 이후 별도 세션/스펙으로 독립 실행 가능하도록 설계한다. 사용자가 확정한 3가지 전제:

1. **결과물 범위**: 로드맵 문서만 (Kiro의 spec.md처럼). 코드는 이번에 작성하지 않음.
2. **구현 순서**: 백엔드(에이전트 로직)를 먼저 완성·검증한 뒤 프론트엔드(SSE 대시보드)를 붙인다.
3. **레포/환경**: 단일 모노레포(`backend/`, `frontend/`를 `agent-loop` 아래에), 로컬 개발 우선(Docker/AWS는 후반 Phase).

## 모노레포 레이아웃 (Phase 0에서 확정, 이후 전 Phase가 참조)

```
agent-loop/
├── backend/
│   ├── app/
│   │   ├── agents/refund_agent/   # graph.py, state.py, nodes.py, prompts.py
│   │   ├── tools/                 # order_lookup.py, policy_rag_search.py
│   │   ├── rag/                   # ingest.py, chunking.py, retriever.py
│   │   ├── api/
│   │   │   ├── routes/            # refund.py, hitl.py, knowledge_base.py
│   │   │   ├── schemas/           # Pydantic 요청/응답 + SSE 이벤트 모델
│   │   │   └── deps.py
│   │   ├── db/                    # models.py, session.py, seed.py
│   │   ├── core/                  # config.py, logging.py
│   │   └── main.py
│   ├── scripts/                   # run_agent_cli.py, seed_db.py
│   ├── tests/
│   ├── data/                      # mock_orders.json, policy_docs/
│   ├── alembic/
│   └── .env.example
├── frontend/
│   ├── app/                       # dashboard/, refund-cases/[id]/, knowledge-base/
│   ├── components/                # agent-viewer/, hitl/, kb-upload/
│   ├── lib/                       # sse-client.ts, api-client.ts
│   ├── store/                     # Zustand
│   └── hooks/                     # React Query
├── docs/                          # spec.md, tasks.md, phase-N/
├── docker-compose.yml             # Phase 7에서 추가
└── README.md
```

---

## Phase 0 — 모노레포 스캐폴딩 + 로컬 개발 환경

**Exit criteria**: `backend`에서 `uvicorn app.main:app --reload`로 `/health` 200 OK, `frontend`에서 `npm run dev`로 기본 Next.js 페이지 구동. 비즈니스 로직 없음. 스캐폴딩 커밋 존재.

**Tasks**:
- 루트 `README.md`, `.gitignore`(Python+Node+macOS)
- `backend/` 패키지 골격 생성, 의존성 관리 방식 결정(venv+requirements.txt 권장) 후 핵심 패키지 고정: `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `langchain`, `langgraph`, `langchain-openai`, `chromadb`, `pypdf`, `pydantic-settings`, `langfuse`
- `pydantic-settings` 기반 `core/config.py` + `.env.example`(`OPENAI_API_KEY`, `DATABASE_URL`, `CHROMA_PERSIST_DIR`, `LANGFUSE_*`)
- `/health`만 있는 FastAPI 앱 팩토리
- **DB 전략**: Phase 0~1은 SQLite(무설정, 파일 기반), SQLAlchemy로 Postgres 전환이 `DATABASE_URL` 한 줄 변경이 되도록 SQLite 전용 문법 금지
- `alembic init`으로 마이그레이션 규율을 처음부터 확립
- `create-next-app`(TypeScript, App Router, Tailwind)으로 `frontend/` 초기화, `zustand`, `@tanstack/react-query` 추가
- **목업 사내 RDB 전략 확정**: `backend/data/mock_orders.json` (5~8건) → `seed_db.py`로 적재. 테스트 시나리오 5종 확정:
  1. 반품 기한 내 파손 → 자동 승인
  2. 고액 환불(예: $500 초과) → HITL 강제
  3. 반품 기한 만료 → 자동 거절
  4. 증빙 사진 모호/누락 → HITL 강제
  5. 일반 저액 승인 (해피패스)
- 린트/포맷 베이스라인: 백엔드 `ruff`/`black`, 프론트엔드 `eslint`/`prettier`

---

## Phase 1 — 핵심 LangGraph 에이전트 (API 없이 단독 실행)

**Exit criteria**: `python backend/scripts/run_agent_cli.py --order-id ORD-1001 --message "..." --image ...`로 최종 판정(승인/거절/사람필요) 및 중간 추론 과정이 stdout에 출력됨. 5개 시나리오별 `pytest` 테스트 통과.

**Tasks**:
- SQLAlchemy 모델: `Order`, `OrderItem`, `RefundCase`, `RefundDecision`, `PolicyDocument`(+ Alembic 마이그레이션)
- `seed_db.py`로 Phase 0의 5개 시나리오 적재
- **에이전트 상태 스키마**(`state.py`) 확정: `order_id`, `user_message`, `image_refs`, `order_data`, `damage_assessment`, `policy_findings`, `decision`, `decision_reason`, `requires_human`, `messages`, `trace` — 이 스키마는 Phase 2 SSE 이벤트 및 Phase 4 프론트 상태의 기반이므로 사실상 고정 계약으로 취급
- `order_lookup` 툴: `order_id`로 주문 정보(구매일, 상품, 가격, 반품기한) 조회
- `damage_assessment` 노드: 텍스트+이미지를 GPT-4o(vision)로 파손 여부/심각도 판정 — 추적성을 위해 별도 노드로 분리(추후 UI에서 하나의 단계로 노출)
- RAG 파이프라인: 샘플 환불 정책 PDF 1~2개 → `RecursiveCharacterTextSplitter`(500~1000 토큰, overlap) → OpenAI 임베딩 → ChromaDB 로컬 persist
- `policy_rag_search` 툴: 케이스 기반 쿼리로 관련 정책 청크 top-k 검색
- `decision` 노드: 주문정보+파손판정+정책검색 결과를 종합해 구조화 출력(Pydantic: `decision: Literal["approve","reject","needs_human"]`, `reason`, `confidence`)
- 조건부 라우팅(순수 Python 함수, 아직 `interrupt()` 아님): `needs_human` 또는 고액/저신뢰 시 "사람 검토 대기" 터미널 상태로 분기
- `StateGraph` 조립: `order_lookup → damage_assessment → policy_rag_search → decision → (조건부: finalize | flag_for_human)`
- `run_agent_cli.py`: CLI 인자 파싱, `.stream()`으로 중간 단계 노출, pretty-print
- Langfuse 콜백 핸들러를 그래프 호출에 연결해 첫 실행부터 트레이싱 확보
- 5개 시나리오 pytest

**설계 결정**:
- 노드 단위는 개념적으로 구분되는 추론 단계(조회/판정/검색/결정)마다 분리 — SSE 세분화 수준을 여기서 결정
- 구조화 LLM 출력(Pydantic 파싱) 사용, 자유 텍스트 파싱 금지
- 노드는 처음부터 `async def`로 작성(Phase 2의 `astream_events`를 위해)

---

## Phase 2 — FastAPI 백엔드: 에이전트 SSE 스트리밍 래핑

**Exit criteria**: `uvicorn` 실행 중, `POST /api/refund-requests`로 케이스 생성 후 `GET /api/refund-requests/{case_id}/stream`에서 노드 진행 SSE 이벤트가 실시간으로 오고 최종 `decision` 이벤트로 종료됨. `curl -N` 또는 `httpx` 스트리밍 테스트로 검증, 프론트엔드 불필요.

**Tasks**:
- 엔드포인트 설계:
  - `POST /api/refund-requests` — order_id/message/이미지(multipart) → `RefundCase` 생성(`pending`) → 에이전트 실행 트리거 → `{case_id}` 반환
  - `GET /api/refund-requests/{case_id}/stream` — SSE (`StreamingResponse`, `text/event-stream`)
  - `GET /api/refund-requests/{case_id}` — 폴링/상태 조회(재연결용)
- **SSE 이벤트 스키마** 확정(Pydantic → JSON): `node_start`, `node_end`, `tool_call`, `decision`, `error` — 필드명은 Phase 4 프론트 매핑의 기반이므로 여기서 고정
- 실행 모델: `graph.astream_events(...)`를 SSE 제너레이터 안에서 구동 → 위 단순화 스키마로 매핑하는 어댑터 레이어(`app/api/schemas/sse_events.py`) 분리 — LangChain 내부 이벤트 형태를 프론트에 직접 노출하지 않음
- Phase 2는 **인프로세스 제너레이터**로 단순하게 시작(단일 프로세스/단일 클라이언트 가정), 단 Phase 3의 pause/resume은 스트리밍 연결과 실행을 분리해야 함을 명시적으로 남겨둠
- 이미지 업로드: `backend/data/uploads/` 로컬 저장 또는 base64 직접 전달 중 택1
- `RefundCase` 상태 전이(`pending → in_progress → awaiting_human | completed`)를 DB에 기록해 스트림 미연결 상태에서도 상태 조회 가능
- CORS(`http://localhost:3000`) 설정
- 에이전트 예외 시 `error` SSE 이벤트 + 케이스 `failed` 처리
- `httpx.AsyncClient` 스트리밍 통합 테스트(자동승인/자동거절 시나리오)

---

## Phase 3 — Human-in-the-Loop 일시정지/재개 메커니즘

**Exit criteria**: 고액 환불 등 HITL 시나리오에서 에이전트가 중단되고 `awaiting_human` 상태가 영속화됨(백엔드 프로세스 재시작 후에도 유지·재개 가능해야 함 — 검증 포인트). `POST /api/refund-requests/{case_id}/resume`에 `{"action": "approve"}` 등으로 재개 시 최종 결정 도달. 통합 테스트: 케이스 시작 → `awaiting_human` 확인 → resume → 최종 상태 확인.

**Tasks**:
- **LangGraph checkpointer** 도입(`SqliteSaver`/`AsyncSqliteSaver` 등, 기존 DB와 동일 저장소 활용 권장) — 메모리 아닌 영속 저장
- Phase 1의 "플래그만 세우는" 분기를 실제 `interrupt()` 호출로 교체 — 그래프 실행이 진짜로 중단됨
- **resume 페이로드 계약** 확정: `{"action": "approve" | "reject" | "takeover", "admin_note": str | None, "admin_message": str | None}`
- `POST /api/refund-requests/{case_id}/resume`: `case_id`를 `thread_id`로 체크포인트 상태 로드 → `Command(resume=...)` 주입 → 실행 재개 → `RefundDecision` 영속화
- **thread_id 전략**: `case_id == thread_id` 규약 고정 (정확성에 직결되므로 문서화)
- **스트림 재연결 문제**: resume은 원래 SSE 연결이 이미 끊긴 뒤(몇 분~몇 시간 후) 발생할 수 있으므로, resume 자체가 새 스트림을 반환하거나 프론트가 재연결 시 "중단 지점 이후부터 스트리밍" 되도록 설계 — 방식 하나를 정해 문서화(Phase 5 UI가 이 설계에 의존)
- 관리자 대기열용 필드 추가: `awaiting_human_since`, `flagged_reason`, `refund_amount`
- `GET /api/refund-requests?status=awaiting_human` 목록 엔드포인트
- 테스트: (a) 일시정지-재개 사이 프로세스 재시작 후에도 재개 성공(체크포인터 영속성 증명), (b) reject 경로, (c) takeover 경로(관리자 메시지가 그래프 재추론 없이 바로 최종 결정이 됨 — MVP 단순화 결정)

---

## Phase 4 — Next.js 프론트: SSE 클라이언트 + 실시간 추론 뷰어

**Exit criteria**: 케이스 상세 페이지에서 환불 요청을 트리거/관찰하면 "주문 조회 중...", "정책 검색 중..." 등 에이전트 단계가 SSE로 실시간 렌더링됨. 모의 `EventSource` 이벤트 시퀀스로 컴포넌트 테스트.

**Tasks**:
- `lib/sse-client.ts`: 네이티브 `EventSource`(GET 기반, 자동 재연결) 사용 — Phase 2 스트림 엔드포인트를 GET으로 설계해 이 방식이 가능하도록 함
- Zustand 스토어: 현재 노드, 완료 노드 목록, 툴콜 로그, 최신 결정, 연결 상태
- React Query: 케이스 메타데이터, 목록(`GET /api/refund-requests`) — 스트리밍 상태(Zustand)와 역할 분리
- `components/agent-viewer/`: 노드명→사용자 친화 라벨 매핑("order_lookup" → "주문 내역 조회 중...") + 단계별 시각 상태(대기/진행/완료)
- SSE 예외 처리: 재연결, 중복/순서뒤바뀀 이벤트에 안전한 상태 업데이트, 종료 이벤트(`decision`/`error`) 감지
- 케이스 상세 페이지(`app/refund-cases/[id]/page.tsx`) + 신규 환불 요청 제출 폼(수동 테스트용)
- 대시보드 목록 페이지(`app/dashboard/`) — Phase 5 전 최소 골격

---

## Phase 5 — Next.js 프론트: HITL 관리자 제어

**Exit criteria**: 대시보드에서 `awaiting_human` 케이스 큐를 보고, 케이스를 열어 Phase 4 뷰어(중단 지점까지)+플래그 사유를 확인하고, 승인/거절/직접개입 클릭 시 Phase 3 resume API 호출 → 케이스가 `completed`로 전환되고 재개 후 이벤트가 실시간 반영됨.

**Tasks**:
- `components/hitl/`: 승인/거절 버튼, 직접개입(자유 텍스트) 폼, 확인 단계(거절/개입은 되돌리기 어려우므로)
- React Query mutation으로 resume API 연결, 성공 시 SSE 뷰어 재연결 또는 결과 낙관적 반영
- `awaiting_human` 대기열 뷰: `awaiting_human_since` 정렬, 플래그 사유/환불액 한눈에 표시
- 케이스 상세 페이지 상태 분기: `in_progress`(뷰어만) / `awaiting_human`(뷰어+HITL 패널) / `completed`(뷰어+최종 요약)
- MVP 단순화로 명시: 실제 다중 관리자 인증/충돌 방지는 생략(last-write-wins), 문서에 명시

---

## Phase 6 — RAG 지식베이스 동적 업데이트 UI

**Exit criteria**: PDF 드래그앤드롭 → 업로드→청킹→임베딩/벡터DB 반영→완료 단계별 프로그레스 바 표시. 신규 업로드 문서가 이후 `policy_rag_search`에서 실제로 검색되는지 통합 테스트로 검증(단순 "업로드됨" 표시가 아니라 실제 검색 경로에 반영되는지).

**Tasks (백엔드)**:
- `POST /api/knowledge-base/documents` — PDF 업로드(multipart) → `PolicyDocument`(`uploaded`) 생성 → 비동기 인제스천 트리거
- Phase 1 `rag/ingest.py`를 확장해 단계별 진행 이벤트 발행: `uploaded → chunking → embedding → indexed → failed`, `chunk_count`/`progress_pct` 영속화
- `GET /api/knowledge-base/documents/{doc_id}/stream` (Phase 2와 동일 SSE 패턴 재사용) + 상태 조회 엔드포인트
- `GET /api/knowledge-base/documents` 목록
- **버전 관리 단순화**: MVP는 추가만(additive) — 이전 청크 교체/삭제는 범위 외로 명시

**Tasks (프론트)**:
- `components/kb-upload/`: 드래그앤드롭 존, PDF 검증(타입/크기)
- 인제스천 SSE에 연동된 프로그레스 바(단계별 라벨/퍼센트)
- 문서 목록 페이지(상태/청크수)

---

## Phase 7 (스트레치) — Docker화 + AWS 배포

Phase 0~6이 로컬에서 검증된 뒤 진행. `backend`/`frontend` 개별 컨테이너화, `docker-compose.yml`로 Postgres+ChromaDB(영구 볼륨)+backend+frontend 통합, `DATABASE_URL`/`CHROMA_PERSIST_DIR`를 로컬 경로→컨테이너 서비스로 전환(Phase 0의 env-driven 설정 덕분에 값만 교체). 이후 AWS 배포: EC2/ECS(백엔드/프론트), S3(업로드 파일), RDS(Postgres), 벡터DB 운영 방식 결정. 이 Phase는 도달 시 별도 상세 스펙으로 분리.

## Phase 8 (스트레치) — 향후 고도화

- **LLM-as-a-Judge 환각 평가 대시보드**: Langfuse 트레이스(Phase 1부터 수집됨) 기반으로 판정의 정책/주문데이터 충실도를 평가하는 2차 평가 파이프라인 + 관리자 분석 뷰
- **멀티 에이전트 아키텍처 분리**: 단일 `refund_agent`를 의도분류 에이전트 + 처리 에이전트로 분리. `backend/app/agents/`와 API 라우팅 계층에만 영향, SSE/HITL 인프라(Phase 2~3)는 케이스 단위 이벤트로 설계되어 재사용 가능

---

## 전 Phase 공통 원칙
- 각 Phase의 exit criteria는 CLI 명령/API 호출/특정 UI 동작으로 모호함 없이 검증 가능해야 함 — `tasks.md` 체크리스트로 옮길 때도 이 성질 유지
- **SSE 이벤트 스키마**(Phase 2)와 **resume 액션 계약**(Phase 3)은 전체 로드맵에서 가장 결합도가 높은 "고정 계약" — 이후 변경 시 프론트/백엔드 양쪽 모두 갱신 필요함을 명시
- 목업 RDB의 5개 시나리오(Phase 0/1)는 이후 모든 Phase의 테스트/수동 검증에서 동일하게 재사용(각 Phase가 새 테스트 데이터를 만들지 않음)

## 검증 방법 요약
- Phase 0~1: `pytest`, `run_agent_cli.py` 수동 실행
- Phase 2~3: `httpx` 비동기 스트리밍 테스트, `curl -N`으로 SSE 수동 확인, 프로세스 재시작 후 resume 검증
- Phase 4~6: 브라우저 수동 확인 + 컴포넌트/통합 테스트(모의 SSE)
- Phase 7: `docker-compose up` 후 전체 스택 통합 확인

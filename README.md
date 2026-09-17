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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:3000`

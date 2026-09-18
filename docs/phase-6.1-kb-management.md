# Phase 6.1 — 지식베이스 관리 페이지 고도화

## Context

`docs/roadmap.md` Phase 6에서 지식베이스 업로드/인제스천 파이프라인(`uploaded → chunking → embedding → indexed`)과 문서 목록 조회까지 구축했다. 당시 "버전 관리는 MVP 범위 밖(추가만 지원)"으로 명시하며 **삭제 기능은 의도적으로 제외**했다. 이번 Phase 6.1은 그 이후 확장으로, `frontend/app/knowledge-base/page.tsx`를 다음 방향으로 고도화한다:

1. 문서 목록에서 문서를 클릭하면 원문 파일을 열람
2. 우리 서비스에 현재 적용 중인 정책을 한눈에 확인하는 대시보드
3. 문서 삭제 기능
4. (제안) 부가 기능 3종

**현재 상태 요약** (조사 완료, 코드 기준):

- 백엔드 `PolicyDocument` 모델(`backend/app/db/models.py:85`)은 `doc_id, filename, status, progress_pct, chunk_count, created_at`만 가짐. 정책을 구조화해서 저장하는 개념은 전혀 없음.
- 원본 PDF는 `settings.policy_docs_dir`(기본 `./data/policy_docs`)에 `{doc_id}-{filename}`으로 실제 저장되어 있음 → 열람 기능은 새 파일이 아니라 이미 있는 파일을 서빙하기만 하면 됨.
- 임베딩 청크는 Chroma(`settings.chroma_persist_dir`)에 있고, id는 `f"{doc_id}-{i}"`, 메타데이터에 `doc_id` 필드가 있음 → 삭제 시 이 메타데이터로 필터링해서 지울 수 있음.
- 삭제/파일열람/정책요약 엔드포인트 모두 백엔드에 없음. 프론트 `lib/api-client.ts`, `hooks/use-kb-documents.ts`에도 대응 함수 없음.
- 프론트에는 별도 UI 라이브러리(Radix/shadcn 등)가 없고 순수 Tailwind + 커스텀 컴포넌트로 구성됨 → 모달/확인창도 직접 구현해야 함.

---

## 확정 스코프 3가지

### 1. 문서 원문 열람

**설계 결정 (권장)**: 별도 PDF 뷰어를 새로 만들지 않고, 브라우저 내장 PDF 뷰어를 그대로 활용한다 — `GET /api/knowledge-base/documents/{doc_id}/file`을 새 탭(`target="_blank"`)으로 연다. PDF.js 등 커스텀 뷰어 구현보다 훨씬 적은 공수로 동일한 사용자 경험을 제공하기 때문. 파일 크기가 크지 않고(업로드 제한 20MB) 문서 종류가 PDF로 고정되어 있어 이 방식의 한계(비-PDF 대응 불가)는 현재 스코프에서 문제되지 않는다.

**백엔드**:
- `GET /api/knowledge-base/documents/{doc_id}/file` 추가. `PolicyDocument.file_path`(신규 컬럼, 아래 참고)로 실제 경로를 찾아 `FileResponse(path, media_type="application/pdf", filename=doc.filename)`로 반환. 파일이 없으면 404.
- **DB 마이그레이션**: `PolicyDocument`에 `file_path: str` 컬럼 추가(Alembic). 현재는 업로드 라우트에서 `dest_path`를 즉석으로 조립만 하고 DB에 저장하지 않는다(`backend/app/api/routes/knowledge_base.py:51`) — 파일 열람/삭제 양쪽에서 안정적으로 참조하려면 업로드 시점에 DB에 영속화해야 한다.

**프론트**:
- `lib/api-client.ts`에 `kbDocumentFileUrl(docId): string` 추가.
- 문서 목록 `<li>` 클릭 시 상세 모달(`components/kb/document-detail-modal.tsx`, 신규)을 열고, 그 안에 "원문 보기" 버튼(새 탭으로 파일 URL 오픈) 배치.

### 2. 적용 중인 정책 한눈에 보기

**핵심 설계 질문**: 정책을 "한눈에" 보여주려면 PDF 원문이 아니라 구조화된 요약이 필요하다. 현재 시스템엔 이런 추출 파이프라인이 없으므로 신규로 만들어야 한다.

**설계 결정 (권장)**: 인덱싱 완료(`indexed`) 이후 **별도의 비동기 후처리 단계**로 LLM 기반 정책 요약을 추출한다. 기존 인제스천 상태 머신(`uploaded → chunking → embedding → indexed → failed`)에는 손대지 않고 완전히 분리한다 — 이유는 (a) 프론트 `TERMINAL_STATUSES`(`frontend/hooks/use-kb-documents.ts:6`)가 이미 `indexed`를 종료 상태로 취급 중이라 상태 머신을 건드리면 기존 폴링 로직에 영향이 가고, (b) 정책 요약은 검색(RAG) 기능의 필수 전제조건이 아니므로 실패해도 문서 자체는 정상 사용 가능해야 하기 때문.

**백엔드**:
- `PolicyDocument`에 컬럼 2개 추가(Alembic): `policy_summary: JSON | None`(추출 결과), `policy_summary_status: str`(`pending | summarizing | done | failed`, 기본 `pending`).
- 구조화 출력 스키마 신규 정의(`backend/app/api/schemas/policy_summary.py`): 프로젝트 컨벤션("구조화 LLM 출력 사용, 자유 텍스트 파싱 금지", roadmap.md Phase 1 설계 결정 참고)을 따라 Pydantic으로 고정.
  ```python
  class PolicyItem(BaseModel):
      category: Literal["환불기한", "파손기준", "증빙요건", "고액기준", "기타"]
      title: str
      summary: str        # 1~2문장 요약
      source_excerpt: str  # 근거가 된 원문 발췌
  ```
- `backend/app/rag/policy_summarizer.py` 신규: 인덱싱된 청크(`app/rag/ingest.py`의 `extract_pdf_text` 결과 재사용 가능)를 Gemini(기존 스택, 최근 커밋에서 기본 LLM 프로바이더가 Gemini로 전환됨)에 구조화 출력으로 넘겨 `PolicyItem` 리스트를 받는다.
- `run_ingestion`(`backend/app/api/kb_runner.py`) 완료 콜백에서 `policy_summarizer`를 fire-and-forget으로 트리거(업로드 라우트의 기존 `_background_tasks` 패턴 재사용).
- `GET /api/knowledge-base/policies` 신규: `policy_summary_status == "done"`인 모든 문서의 `policy_summary`를 모아 `category`별로 그룹핑해서 반환. 대시보드가 프론트에서 N개 문서를 순회하며 합치지 않고 서버에서 한 번에 정리된 형태로 받도록 한다.
- `KBDocumentResponse`에 `policy_summary`, `policy_summary_status` 필드 추가.

**프론트**:
- `knowledge-base/page.tsx` 상단에 "적용 중인 정책" 섹션 추가 — `GET /api/knowledge-base/policies` 결과를 카테고리별 카드로 렌더링. 각 항목 클릭 시 출처 문서로 스크롤/포커스(선택) 또는 최소한 출처 파일명 표시.
- 문서 상세 모달에도 해당 문서의 `policy_summary` 리스트를 보여준다.
- 신규 훅 `useKbPolicies()`(`hooks/use-kb-documents.ts`에 추가, `refetchInterval` 불필요 — 요약 완료 시 `kb-documents` invalidate와 함께 같이 invalidate).

### 3. 문서 삭제

**설계 결정 (권장)**: 소프트 삭제가 아닌 **하드 삭제**로 간다 — 기존 "추가만 지원, 버전 관리 없음" MVP 철학과 일관되고, 관리자 화면 하나뿐이라 복구 요구사항이 아직 없다. 삭제 순서는 실패 시 고아 상태를 만들지 않는 방향으로 고정한다: **① Chroma 벡터 삭제 → ② 디스크 파일 삭제 → ③ DB 로우 삭제**. 이렇게 하면 중간에 실패해도 문서가 목록에 남아 있어 사용자가 재시도할 수 있고, "목록엔 없는데 파일/벡터는 남아있는" 상태를 피할 수 있다.

**백엔드**:
- `DELETE /api/knowledge-base/documents/{doc_id}` 신규.
  1. `store.adelete(where={"doc_id": doc_id})` (langchain_chroma) 또는 `store._collection.delete(where={"doc_id": doc_id})`로 해당 문서의 전체 청크 삭제. `chunk_count`로 정확한 id 목록(`f"{doc_id}-{i}"`)을 재구성해 `adelete(ids=...)`를 쓰는 방식도 가능 — 메타데이터 필터가 더 안전(청크 수 불일치 방어).
  2. `Path(doc.file_path).unlink(missing_ok=True)`.
  3. `session.delete(doc)` + commit.
  4. 인덱싱 진행 중(`status`가 terminal이 아님)인 문서는 삭제 거부(409) — 진행 중인 백그라운드 태스크와의 경합 방지.
- `event_bus`에 해당 doc_id의 남은 큐가 있다면 정리.

**프론트**:
- 문서 상세 모달 또는 목록 행에 "삭제" 버튼. 파괴적 작업이므로 확인 모달(`components/kb/confirm-dialog.tsx`, 신규 — 재사용 가능한 범용 컴포넌트로 설계) 경유 필수.
- `useDeleteKbDocument()` 뮤테이션 신규 — 성공 시 `["kb-documents"]`, `["kb-policies"]` invalidate.

---

## 제안하는 부가 기능

우선순위 순으로 정리했고, **1번과 2번을 권장**한다. 나머지는 근거가 약하거나 선행 조건이 없어 이번 Phase 범위 밖으로 미루는 게 낫다고 판단했다.

1. **(권장) 인덱싱 실패 문서 재시도 버튼** — LLM/네트워크 문제로 `failed` 상태가 될 수 있는데 현재는 재업로드(중복 파일로 새 문서 생성)밖에 방법이 없다. `POST /api/knowledge-base/documents/{doc_id}/retry`로 같은 파일을 재인제스천하면 구현 공수 대비 효용이 크다.
2. **(권장) 정책 검색 테스트 도구** — 관리자가 쿼리를 입력하면 `policy_rag_search`가 실제로 어떤 청크를 반환하는지 KB 페이지에서 바로 확인. 환불 에이전트가 참조하는 검색 결과를 관리자가 신뢰할 수 있는지 검증하는 용도로, 이미 있는 `search_policy_chunks`(`backend/app/rag/retriever.py`)를 그대로 노출하면 되므로 백엔드 신규 로직이 거의 없다.
3. 문서 카테고리 필터링 — 2번 "정책 한눈에 보기"의 `category` 그룹핑이 사실상 이 역할을 대신하므로 별도 태깅 UI는 중복. 스킵 권장.
4. 업로드 시 동일 파일명 중복 경고 — 있으면 좋지만 사용자가 요청한 3가지에 비해 우선순위 낮음.
5. 업로드/삭제 감사 로그(누가 언제) — 현재 시스템에 관리자 인증/식별 개념 자체가 없어(어떤 라우트도 사용자 세션을 받지 않음) 이번 Phase에서는 선행 조건 미충족으로 제외. 인증 도입 이후 별도 Phase로 분리 권장.

---

## 구현 순서 (순차 실행 가능한 태스크 단위)

### Step 1 — 백엔드: DB 마이그레이션
- `PolicyDocument`에 `file_path`, `policy_summary`(JSON, nullable), `policy_summary_status`(기본 `"pending"`) 컬럼 추가
- Alembic 리비전 생성 + 적용
- 업로드 라우트(`upload_document`)에서 `dest_path`를 `doc.file_path`에 저장하도록 수정

**Exit criteria**: 업로드 후 DB에서 `file_path`가 실제 디스크 경로와 일치함을 확인. 기존 업로드 통합 테스트(`test_knowledge_base_api.py`) 통과 유지.

### Step 2 — 백엔드: 파일 열람 + 삭제 엔드포인트
- `GET /documents/{doc_id}/file`
- `DELETE /documents/{doc_id}` (진행 중 상태 삭제 거부 포함)
- pytest: 업로드→열람 200, 업로드→삭제→목록에서 사라짐+파일 없음+Chroma 청크 0건, 진행 중 삭제 시 409

**Exit criteria**: 위 테스트 전부 통과.

### Step 3 — 프론트: 문서 상세 모달 + 파일 열람 + 삭제 UI
- `api-client.ts`: `kbDocumentFileUrl`, `deleteKbDocument`
- `hooks/use-kb-documents.ts`: `useDeleteKbDocument`
- `components/kb/document-detail-modal.tsx`, `components/kb/confirm-dialog.tsx`
- `knowledge-base/page.tsx`: 목록 항목 클릭 → 모달 오픈, 모달 내 원문 보기/삭제 버튼

**Exit criteria**: 브라우저에서 문서 클릭 → 모달 → 새 탭 PDF 열람 확인, 삭제 → 확인 모달 → 목록에서 즉시 사라짐 확인 (Dev server 구동 후 수동 검증).

### Step 4 — 백엔드: 정책 요약 추출 파이프라인
- `schemas/policy_summary.py`(`PolicyItem`), `rag/policy_summarizer.py`
- `kb_runner.py`의 인제스천 완료 콜백에서 fire-and-forget 트리거
- `GET /api/knowledge-base/policies` 집계 엔드포인트
- pytest: 인덱싱 완료 후 `policy_summary_status`가 `done`으로 전이, `/policies`가 카테고리별로 묶어 반환하는지 검증(LLM 호출은 기존 테스트 컨벤션대로 fake/mocked)

**Exit criteria**: 테스트 문서 업로드 후 일정 시간 내 `policy_summary_status=done`, `/policies` 응답에 반영됨.

### Step 5 — 프론트: 정책 한눈에 보기 대시보드
- `useKbPolicies()` 훅
- KB 페이지 상단 "적용 중인 정책" 섹션(카테고리별 카드)
- 문서 상세 모달에 해당 문서의 `policy_summary` 표시

**Exit criteria**: 여러 문서 업로드 후 카테고리별로 정책이 한 화면에 정리되어 보임(수동 검증).

### Step 6 (권장, 선택) — 재시도 버튼 + 정책 검색 테스트 도구
- `POST /documents/{doc_id}/retry`, 프론트 재시도 버튼
- `GET /api/knowledge-base/search?q=...` (기존 `search_policy_chunks` 래핑), KB 페이지 내 간단한 쿼리 입력창 + 결과 리스트

**Exit criteria**: `failed` 문서에서 재시도 클릭 시 인제스천 재개, 검색창에 쿼리 입력 시 실제 청크 결과 표시.

---

## 리스크 / 확인 필요 사항

- LLM 기반 정책 요약(Step 4)은 API 비용·지연을 유발한다. 문서 수가 적은 현재는 문제없지만, 재추출 트리거(재시도 등)를 남발하지 않도록 UI에서 방지가 필요하다.
- `DELETE`가 진행 중인 인제스천과 경합하는 경우(막 업로드해서 아직 `chunking` 단계) 409로 막는 것으로 충분한지, 아니면 백그라운드 태스크를 명시적으로 취소해야 하는지는 실제 사용 빈도를 보고 재검토.

# 송월타월 서울상사 AI Agent V2

`new-agent-maker` 스킬을 적용해 기존 송월타월 SQLite 데이터·읽기 전용 조회 도구를 유지하고 React 19 · TypeScript · Vite 7 + FastAPI 화면을 추가했습니다. 기존 Streamlit V1도 `app.py`로 실행할 수 있습니다.

## V2 실행

프로젝트 루트에서 실행합니다. Python 3.12와 Node 22 이상을 사용합니다.

```bash
python3.12 -m venv .venv-v2
.venv-v2/bin/pip install -r v2/requirements.lock
npm ci --prefix v2/web
npm run build --prefix v2/web
.venv-v2/bin/uvicorn v2.api:app --host 127.0.0.1 --port 8513 --no-proxy-headers
```

접속: http://127.0.0.1:8513. 데모 조회는 API 키 없이 동작합니다. 기본 포트 8510은 기존 다른 앱과 충돌하여 송월타월에는 8513을 사용합니다.

개발할 때는 별도 터미널에서 `npm run dev --prefix v2/web`를 실행합니다. Vite는 `/api`를 8513으로 전달합니다.

## V2 기능

- 왼쪽 지식베이스·문서 검색·본문 / 데이터허브 8개 테이블의 첫 10개 레코드
- 중앙 대화·인쇄 LOT 선택·데모/AI 전환·새 대화·실시간 음성
- 오른쪽 세션 질문 이력 최대 20개, 생산·품질 및 문서·규칙 각 10개 추천질문
- 모바일 자료·질문 패널, 키보드로 닫을 수 있는 문서·설정 대화상자
- 직접 입력·추천질문·이력 재질문의 동일한 처리 경로
- 문서 개정번호·미승인 상태와 실제 호출된 도구의 원본 결과·출처·조회시각 표시
- LOT 전환·새 대화·모드 변경 시 요청 취소 및 이전 응답 무시
- LOT 추적에 완제품뿐 아니라 작업지시에 연결된 원단 재고 포함

데모는 규칙에 따른 키워드 검색입니다. AI 요약·원인 분석을 수행하지 않습니다. V2의 문서는 `sample_docs/*.md`를 직접 읽으며 클라우드 업로드 없이 조회합니다. AI는 기존 제조 도구 8개와 로컬 `search_documents` 도구를 사용합니다. 현재는 SQLite 샘플 자료이며 운영 MES·ERP·PostgreSQL은 연결하지 않았습니다.

샘플 기준일은 **2026-09-03**입니다. 수량의 원본 단위는 **EA**이며 품질 값은 ΔE, 흡수시간 초, 강도 N으로 표시합니다. 샘플 문서는 실제 승인 문서가 아니므로 기존의 `상태: 승인` 표시를 미승인 샘플로 수정했습니다. 실제 품질 기준이나 공정 최적화 수치를 만들지 않습니다.

## AI와 음성 설정

`v2/.env.example`을 참고해 필요한 값을 루트 `.env`에 설정합니다. API 키는 서버에만 저장하며 `VITE_*`에 넣지 않습니다.

- `OPENAI_API_KEY`: 서버의 OpenAI 키
- `OPENAI_MODEL`: 기존 기본값 `gpt-5.6`, 계정에서 사용 가능한 모델로 설정
- `OPENAI_REALTIME_MODEL`: 스킬 기본값 `gpt-realtime-2.1`
- `OPENAI_REALTIME_VOICE`: 기본값 `marin`
- `COCKPIT_ACCESS_TOKEN`: 브라우저 설정에 입력할 접근 코드. API 키와 다릅니다.
- `SONGWOL_DB_PATH`: 기본 `data/songwol_demo.db`; 기존 V1의 샘플 DB와 공유

직접 localhost 접속은 서버 접근 코드가 없을 때만 코드 입력을 생략합니다. 클라이언트 주소와 요청 호스트가 모두 로컬이어야 하며 전달된 프록시 주소가 있으면 예외를 적용하지 않습니다. 서버에 접근 코드가 설정되면 로컬도 코드를 요구합니다. 외부에서는 문서·레코드 조회를 포함한 모든 업무 API에 코드를 요구합니다. 이 코드는 개인 계정·역할 권한 기능이 아닙니다. 외부 운영 배포 시 HTTPS, 사용자 인증·RBAC 및 실데이터 출처 정리가 별도로 필요합니다.

실시간 음성은 WebRTC, 한국어 자막, 발화 종료 감지, 끼어들기, 음소거·종료, LOT 전환 시 자원 해제를 구현했습니다. 서버 도구 핸들러와 실제 SQLite 어댑터를 연결하고 음성 조회 근거도 화면에 표시합니다. 마이크는 HTTPS 또는 localhost에서 사용합니다. 음성과 문자 대화는 각각 별도 AI 문맥이며 선택 LOT를 공유합니다.

API 형식 참고: [OpenAI 공식 WebRTC 가이드](https://developers.openai.com/api/docs/guides/voice-webrtc), [Realtime 대화 이벤트](https://developers.openai.com/api/docs/guides/realtime-conversations). 모델 접근 권한과 실제 음성 품질은 별도로 확인해야 합니다.

## 검증

```bash
.venv-v2/bin/python -m pytest tests v2/tests -q
npm run build --prefix v2/web
# Playwright 설치 환경에서 서버 실행 후:
node v2/tests/ui-smoke.cjs
```

- 기존 테스트 6개 + 신규 API 테스트 10개: **16개 통과**
- TypeScript 검사 및 Vite 프로덕션 빌드 통과
- Chromium 1440×960 / 390×844: 문서 검색·본문, 테이블, 직접 질문·추천·이력, 근거, 새 대화, LOT 변경 중 지연 응답 차단, 가로 넘침·JS 오류 확인
- 음성 경계 모의 테스트: 연결 실패, 마이크 권한 거부, 음소거, 발화 시작 이벤트, 종료 및 LOT 전환 시 트랙 해제 확인
- 실제 유료 AI·음성, 실기기 마이크, PostgreSQL, Docker, 외부 배포는 미검증
- 테스트 환경 Starlette의 httpx TestClient 사용 중단 예정 경고 1건은 테스트 실패가 아닙니다.

브라우저 검증 파일은 `v2/tests/ui-smoke.cjs`입니다. 설치된 Playwright의 경로를 `PLAYWRIGHT_MODULE` 환경변수로 지정할 수도 있습니다. 결과 이미지는 로컬 `artifacts/desktop.png`, `desktop-answer.png`, `mobile.png`, `mobile-answer.png`에 저장됩니다.

## V2 파일 지도

```text
v2/api.py                       접근 제어, REST, AI와 Realtime 프록시
v2/domain.py                    송월 추천질문, 데모 라우팅, 도구 근거 수집
v2/knowledge.py                 미승인 샘플 문서 검색
v2/web/src/App.tsx              반응형 3단 대화 화면
v2/web/src/hooks/useRealtimeVoice.ts   스킬 기반 음성 연결 및 자원 관리
v2/tests/                       API·브라우저 회귀 검증
songwol_agent/                  기존 송월타월 저장소·도구·Responses 서비스
```

---

## 기존 Streamlit V1 안내

아래는 이전 프로토타입의 실행 안내입니다. V2의 구성과 검증 범위는 위 설명을 따릅니다.

### 송월타월 서울상사 제조 RAG Agent

송월타월 서울상사의 **문서 지식**과 **MES형 제조 데이터**를 함께 검색하는 실행형 Streamlit 프로토타입입니다. 색차 예측이나 공정 최적화 모델은 제외하고 RAG 질의응답에만 집중했습니다.

## Agent Cockpit 화면

- 상단 KPI, 대화이력·추천질문, 중앙 RAG 채팅, 선택 인쇄 LOT의 품질·출하·클레임 및 승인대기를 한 화면에 배치했습니다.
- 추천질문, 과거 질문 재실행, 선택 LOT 브리핑은 동일한 채팅 라우트로 처리합니다.
- RAG-only 범위를 유지하며 색차 예측·공정 최적화·Vision AI·자동 제어/승인은 추가하지 않았습니다.

## RAG 범위

- 비정형 지식: 작업표준서(SOP), 품질 기준서, 상품설명서, 클레임·유지보수 매뉴얼
- 정형 지식: 수주, 작업지시, 원단/인쇄 LOT, 생산실적, 품질, 재고, 출하, 품목 기준정보
- 제조 조회: 주문 현황, LOT 정·역추적, 품질 보류, 안전재고, 출하 승인, 클레임 조회
- 근거 표시: 검색 문서명, 문서 검색 결과, 호출한 제조 Data Hub 도구
- 운영 통제: 읽기 전용 도구, 사람 승인, 최소권한, 감사로그, 문서 버전 관리 원칙

화면의 주문·LOT·수치·고객명은 검증용 가상 데이터입니다. 약 200종 품목과 재고 약 8억원, 구글시트·수기 중심 운영, MES+AI Agent 구축 방향은 제공된 기준정보를 반영했습니다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

`.env`에 `OPENAI_API_KEY`를 설정해야 RAG 채팅과 문서 인덱싱을 사용할 수 있습니다. API 키 없이도 제조 데이터 미리보기는 가능합니다.

## 데모 절차

1. 앱을 실행하고 OpenAI API 키를 입력합니다.
2. `지식문서` 탭에서 `sample_docs/` 파일을 업로드합니다.
3. RAG Agent에서 아래 질문을 시험합니다.

```text
PRT-260903-C LOT가 왜 보류됐고 출하에 어떤 영향이 있어?
SO-260901의 생산·품질·출하 상태를 요약해줘.
안전재고 미달 품목을 알려줘.
색상 클레임 처리절차를 문서 근거와 함께 알려줘.
```

## 프로젝트 구조

```text
app.py                         Streamlit 화면
songwol_agent/data_hub.py      SQLite 데모 제조 데이터
songwol_agent/tools.py         8개 읽기 전용 Function 도구
songwol_agent/service.py       Responses API + File Search 호출 루프
songwol_agent/prompts.py       근거·승인·보안 답변 정책
sample_docs/                   검증용 지식문서
tests/                         저장소·도구·Agent 테스트
```

## 운영 전 교체·확인

- SQLite 데모 저장소를 MES/ERP/WMS/QMS 읽기 전용 API 또는 조회 View로 교체
- 주문·작업지시·원단 LOT·인쇄 LOT·품목·출하 키의 일관성 검증
- 문서별 소유자·개정번호·승인상태·시행일·폐기상태 메타데이터 적용
- 부서별 RBAC와 고객·단가·클레임 민감정보 마스킹
- 대표질문 평가셋으로 근거정확성, 답변충실도, 미답변, 권한위반 검증
- 질문·검색문서·도구호출·응답 감사로그 및 백업·복구 절차 적용

## 테스트

```bash
python -m pytest -q
python -m py_compile app.py songwol_agent/*.py
```

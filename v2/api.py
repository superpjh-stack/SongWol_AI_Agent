from __future__ import annotations
import hmac
import json
import os
from pathlib import Path
import re
from threading import BoundedSemaphore
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

from songwol_agent.data_hub import SongwolRepository
from songwol_agent.service import RagAgent
from songwol_agent.prompts import AGENT_INSTRUCTIONS
from .wake import calls_songwol
from .compound import analyze, context_lot, COMPOUND_QUESTIONS, DOCUMENT_QUESTIONS
from .domain import QUESTIONS, TABLES, Registry, demo_answer, questions_for, tables_for, stamp
from .knowledge import documents
from .openai_settings import save_api_key
from . import daily, reports
from .studio import StudioRequest, build_studio

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = Path(os.getenv('SONGWOL_SETTINGS_PATH', str(ROOT / '.env')))
load_dotenv(SETTINGS_PATH)

class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    lot_id: str | None = Field(default=None, max_length=80)
    mode: Literal['demo', 'ai'] = 'demo'
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)

class ToolCall(BaseModel):
    name: str = Field(max_length=80)
    arguments: dict = Field(default_factory=dict)


def local_request(request: Request):
    return (request.client is not None and request.client.host in {'127.0.0.1', '::1'}
            and request.url.hostname in {'localhost', '127.0.0.1', '::1'}
            and not request.headers.get('forwarded') and not request.headers.get('x-forwarded-for'))


def same_origin_request(request: Request, origin: str) -> bool:
    allowed = {str(request.base_url).rstrip('/')}
    allowed.update(item.strip().rstrip('/') for item in os.getenv('SONGWOL_PUBLIC_ORIGINS', '').split(',') if item.strip())
    return origin.rstrip('/') in allowed


def create_app(db_path=None, settings_path=None):
    app = FastAPI(title='송월타월 AI Agent V3')
    app.state.repo = SongwolRepository(db_path or os.getenv('SONGWOL_DB_PATH', str(ROOT / 'data/songwol_demo.db')))
    if not app.state.repo.is_mes_data:
        daily.seed_daily(app.state.repo)
    reports.install(app)
    capacity = BoundedSemaphore(3)
    settings_file = Path(settings_path) if settings_path is not None else SETTINGS_PATH

    def require_access(request):
        expected = os.getenv('COCKPIT_ACCESS_TOKEN', '')
        if local_request(request):
            return
        supplied = request.headers.get('authorization', '').removeprefix('Bearer ')
        if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
            raise HTTPException(401, '설정에서 AI 접근 코드를 입력하세요. 외부 접속은 서버 접근 코드 설정이 필요합니다.')

    def require_key(request):
        require_access(request)
        key = os.getenv('OPENAI_API_KEY', '')
        if not key:
            raise HTTPException(503, '서버 OPENAI_API_KEY가 설정되지 않았습니다. 데모 조회를 이용하세요.')
        return key

    def check_lot(lot):
        if lot and not app.state.repo.get_production(print_lot=lot):
            raise HTTPException(404, 'LOT를 찾지 못했습니다.')

    @app.middleware('http')
    async def guard(request, call_next):
        # Protect all manufacturing records externally, not only paid AI endpoints.
        if request.url.path.startswith('/api/') and request.url.path != '/api/health':
            try:
                require_access(request)
            except HTTPException as exc:
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
            origin = request.headers.get('origin')
            if request.method == 'POST' and origin and not same_origin_request(request, origin):
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail': '동일 출처 요청만 허용합니다.'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '3.0'}

    @app.get('/api/workspace')
    def workspace(request: Request):
        repo = app.state.repo
        meta = repo.mes_meta() if repo.is_mes_data else {'demo_data': 'true', 'as_of': '2026-09-03', 'source': '송월타월 SQLite 샘플'}
        return {'summary': repo.summary(), 'lots': repo.get_production(), 'tables': tables_for(repo),
                'questions': {'데이터 대시보드': [q.removeprefix('송월아, ') for q in (questions_for(repo).get('MES 실데이터') or sum(questions_for(repo).values(), []))][:10], '지식베이스': DOCUMENT_QUESTIONS, '복합질문': COMPOUND_QUESTIONS}, 'meta': {'demo_data': meta.get('demo_data', 'true') == 'true', 'as_of': meta.get('as_of', '2026-09-03'),
                'source': meta.get('source', '송월타월 SQLite 샘플'), 'approval': meta.get('approval', '가상 샘플·미승인'), 'retrieved_at': stamp(),
                'access_required': not local_request(request),
                'daily_start': None if repo.is_mes_data else daily.START, 'daily_end': None if repo.is_mes_data else daily.END, 'daily_anchor': None if repo.is_mes_data else daily.ANCHOR, 'today': daily.today_kst().isoformat(),
                'realtime_model': os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1'),
                'realtime_voice': os.getenv('OPENAI_REALTIME_VOICE', 'marin'),
                'ai_configured': bool(os.getenv('OPENAI_API_KEY'))}}

    @app.post('/api/settings/openai')
    async def configure_openai(request: Request):
        if not local_request(request):
            raise HTTPException(403, 'API 키는 이 컴퓨터에서 직접 접속해 설정하세요.')
        if not same_origin_request(request, request.headers.get('origin', '')):
            raise HTTPException(403, '동일 출처 설정 화면에서 입력하세요.')
        raw = await request.body()
        if len(raw) > 4096:
            raise HTTPException(413, '입력 크기를 확인하세요.')
        try:
            payload = json.loads(raw)
            key = payload.get('api_key', '') if isinstance(payload, dict) else ''
            if not isinstance(key, str):
                raise ValueError
            key = key.strip()
            if not re.fullmatch(r'sk-[A-Za-z0-9_-]{20,1024}', key):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, 'OpenAI API 키 형식을 확인하세요.') from None
        model = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1')
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(f'https://api.openai.com/v1/models/{model}',
                                            headers={'Authorization': f'Bearer {key}'})
        except httpx.HTTPError:
            raise HTTPException(502, 'OpenAI에 연결하지 못했습니다. 네트워크를 확인한 뒤 다시 시도하세요.') from None
        if response.status_code == 401:
            raise HTTPException(422, 'API 키가 유효하지 않습니다. 키를 다시 확인하세요.')
        if response.status_code in {403, 404}:
            raise HTTPException(422, '이 키로 음성 모델을 확인하지 못했습니다. 프로젝트의 모델·API 권한을 확인하세요.')
        if response.is_error:
            raise HTTPException(502, 'OpenAI 연결 확인에 실패했습니다. 잠시 후 다시 시도하세요.')
        try:
            save_api_key(settings_file, key)
        except OSError:
            raise HTTPException(500, '서버 설정을 저장하지 못했습니다. 파일 권한을 확인하세요.') from None
        return {'configured': True, 'realtime_model': model}

    @app.get('/api/documents')
    def document_list(q: str = ''):
        return documents(q[:200])

    @app.get('/api/tables/{table}')
    def table_records(table: str, business_date: str | None = None):
        if table not in tables_for(app.state.repo):
            raise HTTPException(404, '허용된 테이블이 아닙니다.')
        if table in daily.TABLES:
            selected = business_date or daily.ANCHOR
            try:
                daily.query_range(selected)
                from datetime import date
                date.fromisoformat(selected)
            except ValueError:
                raise HTTPException(422, '날짜를 YYYY-MM-DD 형식으로 입력하세요.') from None
            return app.state.repo._query(f'SELECT * FROM {table} WHERE business_date = ? ORDER BY 1', (selected,))
        return app.state.repo._query(f'SELECT * FROM {table} LIMIT 10')

    @app.get('/api/daily')
    def daily_records(kind: str = 'all', start_date: str = daily.ANCHOR, end_date: str = daily.ANCHOR,
                      issues_only: bool = False):
        try:
            return daily.daily_operations(app.state.repo, kind, start_date, end_date, issues_only)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get('/api/lots/{lot_id}')
    def lot_detail(lot_id: str):
        check_lot(lot_id)
        return app.state.repo.trace_lot(lot_id)

    @app.post('/api/studio')
    def studio(body: StudioRequest, request: Request):
        try:
            if body.use_ai and body.mode == 'ideas':
                key = require_key(request)
                if not capacity.acquire(blocking=False):
                    raise HTTPException(429, '다른 요청을 처리 중입니다. 잠시 후 다시 시도하세요.')
                try:
                    with OpenAI(api_key=key, timeout=35, max_retries=0) as client:
                        return build_studio(app.state.repo, body, client, os.getenv('OPENAI_MODEL', 'gpt-5.6'))
                finally:
                    capacity.release()
            return build_studio(app.state.repo, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except OpenAIError as exc:
            raise HTTPException(502, 'AI 기획 생성에 실패했습니다. 연결 설정을 확인하세요.') from exc

    @app.post('/api/chat/reset')
    def reset():
        return {'status': 'ok'}  # Stateless: conversation exists only in the requesting browser.

    @app.post('/api/chat')
    def chat(body: Question, request: Request):
        if not body.question.strip():
            raise HTTPException(422, '질문을 입력하세요.')
        if not calls_songwol(body.question):
            return {'text': '', 'evidence': [], 'mode': body.mode, 'ignored': True}
        try:
            report_input = reports.chat_request(body.question, body.lot_id)
            if report_input:
                if report_input.kind == 'daily-production' and not report_input.business_date:
                    return {'text':'생산일을 선택하고 보고서를 생성하세요.', 'report_picker':'daily-production', 'mode':body.mode}
                report = reports.create(app.state.repo, report_input)
                return {'text':report['title']+' 생성 완료. 원본 기준과 미입력 항목을 확인하세요.', 'report':report, 'mode':body.mode}
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        history = [{'role':h.get('role'), 'text':str(h.get('text',''))[:4000]} for h in body.history if h.get('role') in {'user','assistant'}]
        try:
            lot, clarification = context_lot(body.question, body.lot_id, history)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if clarification:return {'text':clarification,'evidence':[],'mode':body.mode,'needs_clarification':True}
        check_lot(lot)
        if body.mode == 'demo':
            return analyze(app.state.repo, body.question, lot, history)
        key = require_key(request)
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, '다른 질문을 처리 중입니다. 잠시 후 다시 시도하세요.')
        try:
            with OpenAI(api_key=key, timeout=45, max_retries=0) as client:
                return analyze(app.state.repo, body.question, lot, history, client, os.getenv('OPENAI_MODEL', 'gpt-5.6'))
        except OpenAIError as exc:
            raise HTTPException(502, 'AI 연결에 실패했습니다. 서버 키와 모델 설정을 확인하세요.') from exc
        finally:
            capacity.release()

    @app.post('/api/realtime/tool')
    def realtime_tool(body: ToolCall, request: Request):
        require_key(request)
        if body.name == 'analyze_manufacturing_question':
            answer = chat(Question(**{**body.arguments, 'mode':'ai'}), request)
            return {'output':json.dumps(answer,ensure_ascii=False),'evidence':answer.get('evidence',[])}
        registry = Registry(app.state.repo)
        output = registry.execute(body.name, body.arguments)
        return {'output': output, 'evidence': registry.evidence}

    @app.post('/api/realtime/session')
    async def realtime_session(request: Request, lot_id: str | None = None):
        key = require_key(request)
        check_lot(lot_id)
        if request.headers.get('content-type', '').split(';')[0] != 'application/sdp':
            raise HTTPException(415, 'WebRTC 연결 정보가 필요합니다.')
        offer = await request.body()
        if not offer or len(offer) > 100_000:
            raise HTTPException(413, 'WebRTC 연결 정보 크기가 올바르지 않습니다.')
        registry = Registry(app.state.repo)
        voice_context = ('송월타월 MES 원본 기준일 2026-10-28이다. 실데이터 질문은 분석 도구에 전달하고 반환된 원본 시트명·행을 말하세요. 원본 조회 데이터이며 자동 승인·변경을 수행하지 않습니다.' if app.state.repo.is_mes_data else
                         f'한국시간 오늘 {daily.today_kst().isoformat()}. 날짜별 재고·출하는 날짜를 포함해 분석 도구에 전달하세요. 샘플 {daily.START}~{daily.END}, {daily.ANCHOR} 이후는 예상재고와 출하계획만 있습니다. 모든 자료는 가상 샘플입니다.')
        session = {'type': 'realtime', 'model': os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1'),
                   'instructions': AGENT_INSTRUCTIONS + '\n호출명 없이 모든 질문에 답하세요. 제조 질문 전체를 analyze_manufacturing_question으로 분석하고 voice_summary를 짧게 읽으세요.' + f'\n{voice_context} 선택 LOT: {lot_id or "전체"}. 한국어로 짧게 답하세요. 기록 질문은 반드시 조회 도구를 호출하고 식별자를 말하세요. 미등록 정보는 미확인입니다.',
                   'output_modalities': ['audio'], 'tools': [{k: v for k, v in d.items() if k != 'strict'} for d in [registry._tool('analyze_manufacturing_question','송월 제조 복합질문을 LangGraph로 분석한다.',{'question':{'type':'string'},'lot_id':{'type':['string','null']}})]],
                   'audio': {'input': {'transcription': {'model': 'gpt-4o-mini-transcribe', 'language': 'ko'},
                                       'turn_detection': {'type': 'semantic_vad', 'eagerness': 'auto', 'create_response': False, 'interrupt_response': True}},
                             'output': {'voice': os.getenv('OPENAI_REALTIME_VOICE', 'marin')}}}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                upstream = await client.post('https://api.openai.com/v1/realtime/calls', headers={'Authorization': f'Bearer {key}'},
                    files={'sdp': (None, offer.decode('utf-8'), 'application/sdp'), 'session': (None, json.dumps(session), 'application/json')})
        except (httpx.HTTPError, UnicodeDecodeError) as exc:
            raise HTTPException(502, '음성 서비스에 연결하지 못했습니다.') from exc
        if upstream.is_error:
            raise HTTPException(502, '음성 세션 생성 실패. 서버 모델과 사용 권한을 확인하세요.')
        return Response(upstream.text, media_type='application/sdp')

    dist = ROOT / 'v2/web/dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')
        @app.get('/')
        def index():
            return FileResponse(dist / 'index.html')
    return app

app = create_app()

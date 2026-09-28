import json
import pytest
from fastapi.testclient import TestClient
from v2.api import create_app
from v2.domain import Registry

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'test-code')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    app = create_app(tmp_path / 'test.db')
    with TestClient(app, headers={'Authorization': 'Bearer test-code'}) as client:
        yield client


def test_workspace_documents_and_allowed_tables(client):
    workspace = client.get('/api/workspace').json()
    assert len(workspace['lots']) == 3
    assert all(len(v) == 10 for v in workspace['questions'].values())
    assert workspace['meta']['demo_data'] is True
    docs = client.get('/api/documents?q=인쇄').json()
    assert docs and all('미승인' in d['approval'] and '상태: 미승인' in d['body'] for d in docs)
    assert client.get('/api/documents?q=zzzzzz').json() == []
    for table in workspace['tables']:
        assert client.get('/api/tables/' + table).status_code == 200
    assert client.get('/api/tables/sqlite_master').status_code == 404


def test_lot_demo_has_records_and_documents(client):
    answer = client.post('/api/chat', json={'question': '품질과 출하 상태', 'lot_id': 'PRT-260903-C'}).json()
    assert answer['mode'] == 'demo'
    assert '보류' in answer['text'] and '미승인' in answer['text']
    assert {e['kind'] for e in answer['evidence']} == {'record', 'document'}
    trace = client.get('/api/lots/PRT-260901-A').json()
    assert {r['fabric_lot'] for r in trace['inventory']} == {'PRT-260901-A', 'FAB-260825-A'}


def test_bad_context_and_empty_question(client):
    assert client.post('/api/chat', json={'question': 'PRT-260903-C', 'lot_id': 'PRT-260901-A'}).status_code == 422
    assert client.post('/api/chat', json={'question': 'PRT-UNKNOWN'}).status_code == 404
    assert client.post('/api/chat', json={'question': ' '}).status_code == 422
    assert client.post('/api/chat', json={'question': '상태', 'history': [{}] * 13}).status_code == 422
    assert client.post('/api/chat/reset').json()['status'] == 'ok'


def test_access_and_key_protection(client):
    for path in ['/api/workspace', '/api/documents', '/api/tables/orders', '/api/lots/PRT-260901-A']:
        assert client.get(path, headers={'Authorization': ''}).status_code == 401
    assert client.post('/api/chat', json={'question': '상태', 'mode': 'ai'}).status_code == 503
    assert client.post('/api/realtime/session', content='sdp').status_code == 503
    assert client.post('/api/chat', headers={'Origin': 'https://other.test'}, json={'question':'상태'}).status_code == 403


def test_registry_rejects_writes(client):
    registry = Registry(client.app.state.repo)
    result = json.loads(registry.execute('delete_orders', {}))
    assert 'error' in result
    result = json.loads(registry.execute('trace_lot', {'print_lot': 'PRT-260903-C'}))
    assert result['demo_data'] and result['retrieved_at'] and result['source']


def test_every_recommended_question_returns_evidence(client):
    groups = client.get('/api/workspace').json()['questions']
    for questions in groups.values():
        for question in questions:
            response = client.post('/api/chat', json={'question': question})
            assert response.status_code == 200, question
            assert response.json()['evidence'], question


def test_stateless_lot_switch(client):
    first = client.post('/api/chat', json={'question': '품질', 'lot_id': 'PRT-260903-C'}).json()
    second = client.post('/api/chat', json={'question': '품질', 'lot_id': 'PRT-260901-A'}).json()
    assert 'PRT-260903-C' in first['text']
    assert 'PRT-260903-C' not in json.dumps(second)


def test_local_access_requires_both_client_and_host(tmp_path, monkeypatch):
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    app = create_app(tmp_path / 'local.db')
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 123)) as c:
        assert c.get('/api/workspace').status_code == 200
        assert c.get('/api/workspace', headers={'X-Forwarded-For':'10.0.0.1'}).status_code == 401
    with TestClient(app, base_url='http://external.test', client=('127.0.0.1', 123)) as c:
        assert c.get('/api/workspace').status_code == 401


def test_ai_uses_server_model_and_captures_record_evidence(client, monkeypatch):
    from types import SimpleNamespace
    import v2.api as api
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key-never-sent')
    monkeypatch.setenv('OPENAI_MODEL', 'configured-model')
    requests = []
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = self
            assert kwargs['api_key'] == 'test-key-never-sent'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def create(self, **kwargs):
            requests.append(kwargs)
            if len(requests) == 1:
                return SimpleNamespace(id='r1', output=[SimpleNamespace(type='function_call', name='trace_lot', arguments='{"print_lot":"PRT-260903-C"}', call_id='c1')])
            return SimpleNamespace(id='r2', output=[], output_text='QI-260903: 보류 상태입니다.')
    monkeypatch.setattr(api, 'OpenAI', FakeOpenAI)
    response = client.post('/api/chat', json={'question': '품질', 'lot_id': 'PRT-260903-C', 'mode': 'ai'})
    assert response.status_code == 200
    assert response.json()['evidence'][0]['result']['quality'][0]['inspection_id'] == 'QI-260903'
    assert all(r['model'] == 'configured-model' for r in requests)
    assert 'test-key' not in response.text


def test_realtime_session_has_all_real_handlers(client, monkeypatch):
    import v2.api as api
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    captured = {}
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            from types import SimpleNamespace
            captured.update(kwargs)
            return SimpleNamespace(is_error=False, text='mock-sdp-answer')
    monkeypatch.setattr(api.httpx, 'AsyncClient', FakeClient)
    response = client.post('/api/realtime/session?lot_id=PRT-260903-C', content='mock-offer', headers={'Content-Type':'application/sdp'})
    assert response.status_code == 200 and response.text == 'mock-sdp-answer'
    session = json.loads(captured['files']['session'][1])
    assert session['audio']['input']['turn_detection']['interrupt_response'] is True
    assert {d['name'] for d in session['tools']} == set(Registry(client.app.state.repo)._handlers)
    assert 'PRT-260903-C' in session['instructions']
    result = client.post('/api/realtime/tool', json={'name':'search_documents','arguments':{'query':'클레임'}})
    assert result.json()['evidence'][0]['kind'] == 'document'
    assert client.post('/api/realtime/session', content='offer').status_code == 415

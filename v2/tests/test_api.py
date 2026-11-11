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
    assert len(workspace['lots']) == 10
    assert sum(map(len, workspace['questions'].values())) == 30
    assert len(workspace['questions']['데이터 대시보드']) == 10
    assert len(workspace['questions']['지식베이스']) == len(workspace['questions']['복합질문']) == 10
    assert workspace['meta']['demo_data'] is True
    docs = client.get('/api/documents?q=인쇄').json()
    assert docs and all('미승인' in d['approval'] and '상태: 미승인' in d['body'] for d in docs)
    assert client.get('/api/documents?q=zzzzzz').json() == []
    for table in workspace['tables']:
        records = client.get('/api/tables/' + table)
        assert records.status_code == 200
        assert len(records.json()) == {'shipment_plans':4, 'shipment_actuals':2}.get(table,10), table
    assert client.get('/api/tables/sqlite_master').status_code == 404


def test_lot_demo_has_records_and_documents(client):
    answer = client.post('/api/chat', json={'question': '송월아, 품질과 출하 상태', 'lot_id': 'PRT-260903-C'}).json()
    assert answer['mode'] == 'demo'
    assert '보류' in answer['text'] and '미승인' in answer['text']
    assert {e['kind'] for e in answer['evidence']} == {'record', 'document'}
    assert len(client.get('/api/documents').json()) == 10
    trace = client.get('/api/lots/PRT-260901-A').json()
    assert {r['fabric_lot'] for r in trace['inventory']} == {'PRT-260901-A', 'FAB-260825-A'}


def test_bad_context_and_empty_question(client):
    assert client.post('/api/chat', json={'question': '송월아, PRT-260903-C', 'lot_id': 'PRT-260901-A'}).status_code == 422
    assert client.post('/api/chat', json={'question': '송월아, PRT-UNKNOWN'}).status_code == 404
    assert client.post('/api/chat', json={'question': ' '}).status_code == 422
    assert client.post('/api/chat', json={'question': '송월아, 상태', 'history': [{}] * 13}).status_code == 422
    assert client.post('/api/chat/reset').json()['status'] == 'ok'


def test_access_and_key_protection(client):
    for path in ['/api/workspace', '/api/documents', '/api/tables/orders', '/api/lots/PRT-260901-A']:
        assert client.get(path, headers={'Authorization': ''}).status_code == 401
    assert client.post('/api/chat', json={'question': '송월아, 상태', 'mode': 'ai'}).status_code == 503
    assert client.post('/api/realtime/session', content='sdp').status_code == 503
    assert client.post('/api/chat', headers={'Origin': 'https://other.test'}, json={'question':'송월아, 상태'}).status_code == 403


def test_public_cloudfront_origin_is_allowed_behind_proxy(client, monkeypatch):
    monkeypatch.setenv('SONGWOL_PUBLIC_ORIGINS', 'https://songwol.example, https://d2xkg3etofx0oq.cloudfront.net')
    response = client.post('/api/chat', headers={'Origin': 'https://d2xkg3etofx0oq.cloudfront.net'},
                           json={'question': '송월아, 상태'})
    assert response.status_code == 200


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
    first = client.post('/api/chat', json={'question': '송월아, 품질', 'lot_id': 'PRT-260903-C'}).json()
    second = client.post('/api/chat', json={'question': '송월아, 품질', 'lot_id': 'PRT-260901-A'}).json()
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


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '[::1]'])
def test_local_access_never_prompts_even_with_server_code(tmp_path, monkeypatch, host):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'configured-external-code')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    app = create_app(tmp_path / 'local-code.db')
    with TestClient(app, base_url=f'http://{host}', client=('127.0.0.1', 123)) as c:
        for authorization in ['', 'Bearer outdated-browser-code']:
            response = c.get('/api/workspace', headers={'Authorization': authorization})
            assert response.status_code == 200
            assert response.json()['meta']['access_required'] is False
        assert c.get('/api/documents').status_code == 200
        assert c.get('/api/tables/orders').status_code == 200
        assert c.get('/api/lots/PRT-260903-C').status_code == 200
        assert c.post('/api/chat', json={'question': '송월아, 품질 보류 LOT'}).status_code == 200
        assert c.post('/api/chat', json={'question': '송월아, 품질', 'mode': 'ai'}).status_code == 503
        for headers in [{'X-Forwarded-For': '10.0.0.1'}, {'Forwarded': 'for=10.0.0.1'}]:
            assert c.get('/api/workspace', headers=headers).status_code == 401
    with TestClient(app, base_url='http://localhost', client=('10.0.0.1', 123)) as c:
        assert c.get('/api/workspace').status_code == 401
        response = c.get('/api/workspace', headers={'Authorization': 'Bearer configured-external-code'})
        assert response.status_code == 200
        assert response.json()['meta']['access_required'] is True


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
        def with_options(self, **kwargs):
            return self
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
    response = client.post('/api/chat', json={'question': '송월아, 품질', 'lot_id': 'PRT-260903-C', 'mode': 'ai'})
    assert response.status_code == 200
    assert response.json()['evidence'][0]['result']['quality'][0]['inspection_id'] == 'QI-260903'
    assert all(r['model'] == 'configured-model' for r in requests)
    assert 'test-key' not in response.text


def test_demo_seeds_ten_linked_records_idempotently(client):
    repository = client.app.state.repo
    counts = {table: len(client.get('/api/tables/' + table).json()) for table in client.get('/api/workspace').json()['tables'] if table not in {'daily_inventory','shipment_plans','shipment_actuals'}}
    assert counts == {table: 10 for table in counts}
    assert repository.get_orders(order_no='SO-260910')[0]['item_code'] == 'TW-200-BL'
    trace = repository.trace_lot('PRT-260905-E')
    assert trace['order'][0]['order_no'] == 'SO-260905'
    assert trace['quality'][0]['result'] == '보류'
    assert trace['shipment'][0]['approval'] == '미승인'
    with repository._connect() as connection:
        repository._seed(connection)
    assert {table: len(client.get('/api/tables/' + table).json()) for table in counts} == counts


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
    assert session['audio']['input']['turn_detection']['create_response'] is False
    assert {d['name'] for d in session['tools']} == {'analyze_manufacturing_question'}
    assert 'PRT-260903-C' in session['instructions']
    result = client.post('/api/realtime/tool', json={'name':'search_documents','arguments':{'query':'클레임'}})
    assert result.json()['evidence'][0]['kind'] == 'document'
    assert client.post('/api/realtime/session', content='offer').status_code == 415


@pytest.mark.parametrize('question', ['오늘 재고 알려줘', '송월타월 재고 알려줘', '다음 질문', ''])
def test_unaddressed_questions_are_accepted(client, question):
    response=client.post('/api/chat', json={'question':question or ' '})
    assert response.status_code == (200 if question else 422)
    if question: assert response.json()['text'] and not response.json().get('ignored')

@pytest.mark.parametrize('question', ['송월아, 오늘 재고 알려줘', '송월아 오늘 재고 알려줘'])
def test_named_questions_answer(client, question):
    answer = client.post('/api/chat', json={'question':question}).json()
    assert answer['text'] and answer['evidence'] and not answer.get('ignored')


@pytest.mark.parametrize('question', ['송월, 오늘 재고 알려줘', '송월님! 오늘 재고 알려줘', '송월야 오늘 재고 알려줘'])
def test_legacy_addresses_are_ignored(client, question):
    response = client.post('/api/chat', json={'question': question})
    assert response.status_code == 200
    assert not response.json().get('ignored')

import os
import stat

import httpx
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from v2.api import create_app

KEY = 'sk-test-' + 'a' * 40

@pytest.fixture
def setup_client(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', '')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'external-test-code')
    config = tmp_path / '.env'
    config.write_text("# preserve settings\nCOCKPIT_ACCESS_TOKEN='unchanged'\nOPENAI_REALTIME_VOICE=marin\n")
    app = create_app(tmp_path / 'data.db', settings_path=config)
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 123),
                    headers={'Origin': 'http://localhost'}) as client:
        yield client, config, app


def provider(monkeypatch, status=200):
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers):
            assert url.startswith('https://api.openai.com/v1/models/')
            assert headers['Authorization'] == 'Bearer ' + KEY
            return httpx.Response(status, json={'id': 'gpt-realtime-2.1'})
    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeClient)


def test_key_is_saved_server_side_and_active_without_restart(setup_client, monkeypatch):
    client, config, _ = setup_client
    provider(monkeypatch)
    assert client.get('/api/workspace').json()['meta']['ai_configured'] is False
    response = client.post('/api/settings/openai', json={'api_key': KEY})
    assert response.status_code == 200
    assert KEY not in response.text
    values = dotenv_values(config)
    assert values['OPENAI_API_KEY'] == KEY
    assert values['COCKPIT_ACCESS_TOKEN'] == 'unchanged'
    assert values['OPENAI_REALTIME_VOICE'] == 'marin'
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert os.environ['OPENAI_API_KEY'] == KEY
    workspace = client.get('/api/workspace')
    assert workspace.json()['meta']['ai_configured'] is True
    assert KEY not in workspace.text
    assert not list(config.parent.glob('.openai-config-*'))


@pytest.mark.parametrize('value', ['', "sk-test-secret\nINJECTED=value", {'secret': KEY}, None])
def test_invalid_input_never_echoes_key_or_modifies_file(setup_client, value):
    client, config, _ = setup_client
    before = config.read_text()
    response = client.post('/api/settings/openai', json={'api_key': value})
    assert response.status_code == 422
    assert 'sk-test' not in response.text
    assert config.read_text() == before


def test_rejected_provider_key_is_not_saved(setup_client, monkeypatch):
    client, config, _ = setup_client
    provider(monkeypatch, 401)
    before = config.read_text()
    response = client.post('/api/settings/openai', json={'api_key': KEY})
    assert response.status_code == 422
    assert KEY not in response.text
    assert config.read_text() == before
    assert not os.environ['OPENAI_API_KEY']


def test_setting_key_requires_direct_local_and_same_origin(setup_client):
    client, config, app = setup_client
    before = config.read_text()
    assert client.post('/api/settings/openai', json={'api_key': KEY}, headers={'Origin':'https://other.test'}).status_code == 403
    assert client.post('/api/settings/openai', json={'api_key': KEY}, headers={'Origin':''}).status_code == 403
    with TestClient(app, base_url='https://external.test', client=('10.0.0.1', 123),
                    headers={'Authorization':'Bearer external-test-code', 'Origin':'https://external.test'}) as remote:
        assert remote.post('/api/settings/openai', json={'api_key': KEY}).status_code == 403
    assert config.read_text() == before

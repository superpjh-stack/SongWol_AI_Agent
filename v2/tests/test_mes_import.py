import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from v2.api import create_app
from v2.mes_import import import_mes


MES_XLSX = Path('/Users/gerardo92/Desktop/12 송월타월 서울상사 제조AI 플랫폼 구축 프로젝트/송월타월 데이터/송월타월MES_화면별데이터_20261028.xlsx')


@pytest.mark.skipif(not MES_XLSX.exists(), reason='로컬 MES 원본 엑셀이 없는 환경')
def test_import_counts_and_mes_recommendations(tmp_path):
    report = import_mes(MES_XLSX, tmp_path / 'songwol_mes.db')
    assert report['total_rows'] > 17000
    assert report['sheets']['수주관리']['rows'] == 98
    assert report['sheets']['생산실적']['rows'] == 7166

    app = create_app(tmp_path / 'songwol_mes.db')
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 123)) as client:
        workspace = client.get('/api/workspace').json()
        assert workspace['meta']['demo_data'] is False
        assert len(workspace['questions']['데이터 대시보드']) == 10
        assert not workspace['questions']['데이터 대시보드'][0].startswith('송월아')
        assert len(client.get('/api/tables/mes_inventory').json()) == 10
        response = client.post('/api/chat', json={'question': workspace['questions']['데이터 대시보드'][0]})
        assert response.status_code == 200
        data = response.json()
        assert data['evidence'][0]['demo_data'] is False
        assert '2026-10-28' in data['text']
        assert '원본' in data['text']


def test_import_rejects_missing_workbook(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_mes(tmp_path / 'missing.xlsx', tmp_path / 'mes.db')

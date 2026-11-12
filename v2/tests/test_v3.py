import json
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from v2.api import create_app
from v2 import reports

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','test-code')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(create_app(tmp_path/'sample.db',tmp_path/'missing.env'),headers={'Authorization':'Bearer test-code'}) as c: yield c

def test_reports_chat_snapshot_and_download(client):
    rows=client.app.state.repo.get_production()
    day=next(r['ended_at'][:10] for r in rows if r['ended_at'])
    answer=client.post('/api/chat',json={'question':f'{day} 일일생산보고서 만들어줘'}).json()
    report=answer['report']; rid=report['report_id']
    assert report['business_date']==day
    assert 'source_rows' not in report
    with client.app.state.repo._connect() as db: db.execute('UPDATE work_orders SET good_qty=0')
    xlsx=client.get(f'/api/reports/{rid}/xlsx')
    assert xlsx.status_code==200
    wb=load_workbook(BytesIO(xlsx.content))
    assert wb.active.cell(6,5).value==report['rows'][0][4]
    assert wb['원본 스냅샷'].max_row>1
    pdf=client.get(f'/api/reports/{rid}/pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    assert client.get(f'/api/reports/{rid}/pdf',headers={'Authorization':''}).status_code==401
    assert client.post('/api/chat',json={'question':'일일생산보고서 만들어줘'}).json()['report_picker']=='daily-production'

def test_report_filters_errors_and_formula_text(client):
    assert client.post('/api/reports',json={'kind':'daily-production','business_date':'2099-01-01'}).status_code==404
    for q in ['2026-09-01부터 2026-09-03까지 일일생산보고서','최근 생산실적 보고서','2026-09-01 재고 보고서','9월 1일 생산 보고서','PRT-260901-A 생산 보고서']:
        assert client.post('/api/chat',json={'question':q}).status_code==422,q
    assert client.post('/api/reports',json={'kind':'inventory','lot_id':'PRT-260901-A'}).status_code==422
    with client.app.state.repo._connect() as db: db.execute("UPDATE inventory SET item_name='=HYPERLINK(\"evil\")'")
    report=client.post('/api/reports',json={'kind':'inventory'}).json()
    wb=load_workbook(BytesIO(client.get(f"/api/reports/{report['report_id']}/xlsx").content))
    assert wb.active['B6'].data_type=='s'

def test_studio_modes_and_evidence(client):
    for mode in ['ideas','briefing','detective','journey']:
        response=client.post('/api/studio',json={'mode':mode,'lot_id':'PRT-260901-A'})
        assert response.status_code==200,response.text
        result=response.json(); valid={f['id'] for f in result['evidence']}
        assert len(result['pipeline'])==3
        for card in result['cards']:
            assert set(card['evidence_ids'])<=valid
            if card['kind']=='creative': assert not card['evidence_ids']
    assert client.post('/api/studio',json={'mode':'detective'}).status_code==422
    assert client.post('/api/studio',json={'mode':'ideas','use_ai':True}).status_code==503

def test_mes_missing_date_and_all_rows(client):
    repo=client.app.state.repo
    with repo._connect() as db:
        db.executescript('CREATE TABLE mes_meta(key TEXT,value TEXT); CREATE TABLE mes_production_results(source_sheet TEXT,source_row INT,payload TEXT);')
        db.executemany('INSERT INTO mes_meta VALUES (?,?)',[('source','test source'),('as_of','2026-10-28')])
        db.executemany('INSERT INTO mes_production_results VALUES (?,?,?)',[('생산실적',i,json.dumps({'생산번호':str(i),'품명 및 규격':'테스트 타월','생산량':2})) for i in range(600)])
    repo.is_mes_data=True
    assert client.post('/api/reports',json={'kind':'daily-production','business_date':'2026-10-28'}).status_code==422
    result=client.post('/api/reports',json={'kind':'production-summary'}).json()
    assert result['rows']==[['테스트 타월',600,1200.0,0]]
    assert '원본' in result['notes'][0]

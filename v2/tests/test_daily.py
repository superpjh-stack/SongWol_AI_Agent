from datetime import date, timedelta
import json

import pytest
from fastapi.testclient import TestClient
from v2.api import create_app
from v2 import daily
from v2.domain import Registry, demo_answer, QUESTIONS

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', '')
    monkeypatch.setattr(daily, 'today_kst', lambda: date(2026,10,9))
    return create_app(tmp_path / 'daily.db')


def test_fixed_window_counts_references_and_future_types(app):
    repo=app.state.repo
    assert len(repo._query('SELECT * FROM daily_inventory')) == 310
    assert len(repo._query('SELECT * FROM shipment_plans')) == 124
    assert len(repo._query('SELECT * FROM shipment_actuals')) == 32
    all_data=daily.daily_operations(repo,'all',daily.START,daily.END)
    totals=all_data['daily_totals']
    assert len(totals)==31
    assert len({r['inventory_quantity'] for r in totals})==31
    for offset in range(31):
        day=(date.fromisoformat(daily.START)+timedelta(days=offset)).isoformat()
        result=daily.daily_operations(repo,'all',day,day)
        assert len(result['inventory'])==10
        assert len(result['plans'])==4
        assert len(result['actuals'])==(0 if day>daily.ANCHOR else 2)
        for row in result['inventory']:
            assert row['source']=='demo_data' and row['unit']=='EA'
            assert row['record_type']==('예상 재고' if day>daily.ANCHOR else '재고 스냅샷')
        by_id={r['plan_id']:r for r in result['plans']}
        for actual in result['actuals']:
            plan=by_id[actual['plan_id']]
            assert 0<actual['quantity']<=plan['quantity']
            for field in ['business_date','item_code','item_name','customer','unit','source']:
                assert actual[field]==plan[field]
            assert actual['shipped_at']>=plan['planned_at']
        if day>daily.ANCHOR:
            assert result['daily_totals'][0]['shipped_quantity'] is None
        else:
            assert result['actuals'][1]['quantity']<by_id[result['actuals'][1]['plan_id']]['quantity']


def test_seed_does_not_overwrite_existing_records_or_shift_dates(app,monkeypatch):
    repo=app.state.repo
    with repo._connect() as db:
        db.execute("UPDATE daily_inventory SET quantity=123 WHERE snapshot_id='DEMO-INV-261009-01'")
    legacy=repo.get_inventory()
    monkeypatch.setattr(daily,'today_kst',lambda:date(2026,10,20))
    daily.seed_daily(repo)
    assert repo._query("SELECT quantity FROM daily_inventory WHERE snapshot_id='DEMO-INV-261009-01'")[0]['quantity']==123
    assert len(repo._query('SELECT * FROM daily_inventory'))==310
    assert repo.get_inventory()==legacy
    assert not repo._query("SELECT * FROM shipment_actuals WHERE business_date>'2026-10-09'")


@pytest.mark.parametrize('question,expected',[
 ('오늘 재고',('2026-10-09','2026-10-09')),('내일 출하',('2026-10-10','2026-10-10')),
 ('어제 출하실적',('2026-10-08','2026-10-08')),('모레 출하계획',('2026-10-11','2026-10-11')),
 ('지난 15일 출하실적',('2026-09-24','2026-10-08')),('앞으로 15일 출하계획',('2026-10-10','2026-10-24')),
 ('전체 기간 재고 추이',('2026-09-24','2026-10-24')),('10월 12일 출하',('2026-10-12','2026-10-12')),
 ('2026-09-25부터 2026-10-03 재고',('2026-09-25','2026-10-03'))])
def test_question_dates(question,expected):
    assert daily.query_range(question,date(2026,10,9))==expected


def test_recommendations_and_out_of_range_answers(app):
    for q in QUESTIONS['재고·출하']:
        answer=demo_answer(app.state.repo,q,None)
        assert answer['evidence'][0]['title']=='get_daily_operations'
        assert 'EA' in answer['text'] and '샘플' in answer['text']
    future=demo_answer(app.state.repo,'내일 실제 출하실적',None)
    assert '미래 실적 없음' in future['text']
    assert future['evidence'][0]['result']['actuals']==[]
    missing=demo_answer(app.state.repo,'2026-10-25 재고',None)
    assert '기록이 없습니다' in missing['text']
    assert missing['evidence'][0]['result']['inventory']==[]
    bad=demo_answer(app.state.repo,'2026-02-30 재고',None)
    assert not bad['evidence'] and '날짜를 확인' in bad['text']
    scoped=demo_answer(app.state.repo,'오늘 출하계획','PRT-260903-C')
    assert '선택 LOT별 출하 배분은 미확인' in scoped['text']
    assert scoped['evidence'][0]['result']['plans']==[]


def test_api_and_voice_registry_share_dated_records(app):
    with TestClient(app,base_url='http://localhost',client=('127.0.0.1',123)) as client:
        response=client.get('/api/daily?kind=all&start_date=2026-09-24&end_date=2026-10-24')
        assert response.status_code==200
        assert len(response.json()['daily_totals'])==31
        assert len(client.get('/api/tables/shipment_plans?business_date=2026-10-24').json())==4
        assert client.get('/api/tables/shipment_actuals?business_date=2026-10-24').json()==[]
        assert client.get('/api/tables/daily_inventory?business_date=bad').status_code==422
        assert client.get('/api/daily?kind=sql').status_code==422
        assert client.get('/api/daily?start_date=2026-10-10&end_date=2026-10-01').status_code==422
    registry=Registry(app.state.repo)
    assert any(t['name']=='get_daily_operations' for t in registry.definitions)
    result=json.loads(registry.execute('get_daily_operations',{'kind':'inventory','start_date':daily.ANCHOR,'end_date':daily.ANCHOR,'issues_only':True,'lot_id':None}))
    assert result['demo_data'] is True
    assert result['result']['inventory']
    assert all(r['quantity']<r['safety_stock'] for r in result['result']['inventory'])

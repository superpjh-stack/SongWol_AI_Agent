"""Fixed, synthetic Songwol logistics window. Never turn future plans into actuals."""
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo

ANCHOR = '2026-10-09'
START = '2026-09-24'
END = '2026-10-24'
TABLES = {'daily_inventory': '일별 재고·예상재고', 'shipment_plans': '일별 출하계획',
          'shipment_actuals': '일별 출하실적 (샘플)'}
QUESTIONS = ['오늘 재고현황을 알려줘', '오늘 안전재고 미달 품목을 알려줘', '오늘 출하계획을 알려줘',
             '오늘 출하실적을 알려줘', '오늘 계획 대비 미출하 수량을 알려줘', '내일 출하계획을 알려줘',
             '앞으로 15일 출하계획을 알려줘', '지난 15일 출하실적을 알려줘',
             '내일 예상 재고를 알려줘', '전체 기간 재고 추이를 알려줘']


def today_kst():
    return datetime.now(ZoneInfo('Asia/Seoul')).date()


def seed_daily(repo):
    with repo._connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS daily_inventory (
          snapshot_id TEXT PRIMARY KEY, business_date TEXT NOT NULL, item_code TEXT,
          item_name TEXT, item_type TEXT, lot_id TEXT, location TEXT,
          quantity INTEGER CHECK(quantity >= 0), safety_stock INTEGER,
          unit TEXT CHECK(unit = 'EA'), record_type TEXT, snapshot_at TEXT,
          sample_as_of TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS shipment_plans (
          plan_id TEXT PRIMARY KEY, business_date TEXT NOT NULL, item_code TEXT,
          item_name TEXT, customer TEXT, quantity INTEGER CHECK(quantity > 0),
          unit TEXT CHECK(unit = 'EA'), planned_at TEXT, approval TEXT,
          sample_as_of TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS shipment_actuals (
          dispatch_id TEXT PRIMARY KEY, plan_id TEXT REFERENCES shipment_plans(plan_id),
          business_date TEXT NOT NULL, item_code TEXT, item_name TEXT, customer TEXT,
          quantity INTEGER CHECK(quantity > 0), unit TEXT CHECK(unit = 'EA'),
          shipped_at TEXT, status TEXT, sample_as_of TEXT, source TEXT);
        CREATE INDEX IF NOT EXISTS idx_daily_inventory_date ON daily_inventory(business_date);
        CREATE INDEX IF NOT EXISTS idx_shipment_plans_date ON shipment_plans(business_date);
        CREATE INDEX IF NOT EXISTS idx_shipment_actuals_date ON shipment_actuals(business_date);
        ''')
        # Independent daily snapshots; these are not a stock movement ledger.
        inventory = db.execute('SELECT * FROM inventory ORDER BY location, item_code, fabric_lot LIMIT 10').fetchall()
        products = db.execute('SELECT * FROM orders WHERE order_no IN (?, ?, ?, ?) ORDER BY order_no',
                              ('SO-260901', 'SO-260902', 'SO-260903', 'SO-260904')).fetchall()
        for offset in range(31):
            day = date.fromisoformat(START) + timedelta(days=offset)
            day_text, compact = day.isoformat(), day.strftime('%y%m%d')
            for i, row in enumerate(inventory):
                qty = max(0, row['quantity'] + (offset - 15) * (i + 2) * 7)
                db.execute('INSERT OR IGNORE INTO daily_inventory VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (f'DEMO-INV-{compact}-{i+1:02}', day_text, row['item_code'], row['item_name'],
                            '원단' if row['item_code'].startswith('RAW-') else '완제품', row['fabric_lot'],
                            row['location'], qty, row['safety_stock'], 'EA',
                            '예상 재고' if day_text > ANCHOR else '재고 스냅샷',
                            day_text+' 09:00', ANCHOR, 'demo_data'))
            for i, row in enumerate(products):
                qty = [600, 400, 800, 500][i] + offset * [10, 5, 15, 10][i]
                plan_id = f'DEMO-SP-{compact}-{i+1:02}'
                db.execute('INSERT OR IGNORE INTO shipment_plans VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (plan_id, day_text, row['item_code'], row['item_name'], row['customer'], qty, 'EA',
                            day_text+' '+['07:00','07:30','10:00','15:00'][i],
                            '검토 대기' if i == 2 else '검토 완료 (샘플)', ANCHOR, 'demo_data'))
                if day_text <= ANCHOR and i < 2:
                    actual_qty = qty if i == 0 else qty - 100
                    db.execute('INSERT OR IGNORE INTO shipment_actuals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               (f'DEMO-OUT-{compact}-{i+1:02}', plan_id, day_text, row['item_code'],
                                row['item_name'], row['customer'], actual_qty, 'EA',
                                day_text+' '+['07:20','07:40'][i],
                                '계획수량 출하' if i == 0 else '부분 출하', ANCHOR, 'demo_data'))


def daily_operations(repo, kind, start_date, end_date, issues_only=False, lot_id=None):
    if kind not in {'inventory', 'plans', 'actuals', 'all'}:
        raise ValueError('조회 종류는 inventory, plans, actuals, all 중 하나입니다.')
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if start > end or (end - start).days > 365:
        raise ValueError('시작일·종료일 순서와 조회 기간(최대 366일)을 확인하세요.')
    result = {'requested_start': start.isoformat(), 'requested_end': end.isoformat(),
              'sample_start': START, 'sample_end': END, 'sample_as_of': ANCHOR, 'unit': 'EA',
              'demo_data': True, 'inventory': [], 'plans': [], 'actuals': [], 'daily_totals': [],
              'notes': ['모든 행은 가상 샘플입니다. 운영 재고나 출하 승인을 의미하지 않습니다.',
                        '재고는 각 날짜 09:00의 독립 스냅샷이며 출하량을 다시 차감하지 않습니다.',
                        f'{ANCHOR} 이후 재고는 예상치입니다. 미래 출하실적은 생성하지 않았습니다.']}
    if lot_id:
        result['notes'].append('일별 물류 조회는 회사 전체 기준입니다. 선택 LOT별 출하 배분은 미확인입니다. 전체 기록에서 조회하세요.')
        return result
    for key, table in [('inventory','daily_inventory'),('plans','shipment_plans'),('actuals','shipment_actuals')]:
        if kind == 'inventory' and key != 'inventory' or kind in {'plans','actuals'} and key == 'inventory':
            continue
        condition = ' AND quantity < safety_stock' if key == 'inventory' and issues_only else ''
        result[key] = repo._query(f'SELECT * FROM {table} WHERE business_date BETWEEN ? AND ?{condition} ORDER BY business_date, 1', (start.isoformat(), end.isoformat()))
    dates = sorted({row['business_date'] for key in ['inventory','plans','actuals'] for row in result[key]})
    for day in dates:
        inv = [r for r in result['inventory'] if r['business_date'] == day]
        plans = [r for r in result['plans'] if r['business_date'] == day]
        actuals = [r for r in result['actuals'] if r['business_date'] == day]
        planned, shipped = sum(r['quantity'] for r in plans), sum(r['quantity'] for r in actuals)
        result['daily_totals'].append({'business_date': day, 'inventory_quantity': sum(r['quantity'] for r in inv),
                                      'stock_issue_count': sum(r['quantity'] < r['safety_stock'] for r in inv),
                                      'planned_quantity': planned, 'shipped_quantity': shipped if day <= ANCHOR else None,
                                      'unshipped_quantity': max(0, planned-shipped) if day <= ANCHOR else None,
                                      'inventory_type': '예상 재고' if day > ANCHOR else '재고 스냅샷'})
    return result


def query_range(question, today=None):
    now = today or today_kst()
    # Explicit dates always take precedence. Invalid dates are never silently replaced.
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', question)
    if not dates:
        dates = [f'{now.year}-{int(m):02}-{int(d):02}' for m, d in re.findall(r'(\d{1,2})월\s*(\d{1,2})일', question)]
    if dates:
        if len(dates) > 2:
            raise ValueError('한 날짜 또는 시작일과 종료일 두 개를 입력하세요.')
        parsed = [date.fromisoformat(d) for d in dates]
        if parsed[0] > parsed[-1]:
            raise ValueError('시작일은 종료일보다 늦을 수 없습니다.')
        return parsed[0].isoformat(), parsed[-1].isoformat()
    if any(word in question for word in ['전체 기간', '전체기간', '한 달', '한달', '앞뒤']):
        return START, END
    count = re.search(r'(?:앞으로|향후|지난|최근|과거)\s*(\d+)일', question)
    if count:
        days = int(count.group(1))
        if not 1 <= days <= 365:
            raise ValueError('1~365일 범위로 질문해 주세요.')
        if '앞으로' in question or '향후' in question:
            return (now+timedelta(days=1)).isoformat(), (now+timedelta(days=days)).isoformat()
        return (now-timedelta(days=days)).isoformat(), (now-timedelta(days=1)).isoformat()
    delta = 2 if '모레' in question else 1 if '내일' in question else -2 if '그저께' in question else -1 if '어제' in question else 0
    day = (now+timedelta(days=delta)).isoformat()
    return day, day


def dated_question(question):
    return bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}월|오늘|내일|어제|모레|그저께|앞으로|향후|지난|최근|과거|전체\s*기간|앞뒤|한\s*달', question))


def daily_question(question):
    return ('미승인' not in question or dated_question(question)) and any(w in question for w in ['재고', '출하']) and not any(w in question for w in ['절차','기준서','체크리스트','규칙','방법','가이드','인계'])


def render_answer(result, kind):
    start, end = result['requested_start'], result['requested_end']
    title = start if start == end else f'{start}~{end}'
    lines = [f'{title} 조회 · 가상 샘플 데이터 · 단위 EA']
    totals = result['daily_totals']
    if not totals:
        lines.append(f'조건에 맞는 기록이 없습니다. 등록 기간: {START}~{END}. 다른 날짜로 대체하지 않았습니다.')
    elif kind == 'inventory':
        for row in totals:
            lines.append(f"{row['business_date']} {row['inventory_type']}: {row['inventory_quantity']:,} EA · 조회 품목 중 안전재고 미달 {row['stock_issue_count']}종")
        if start == end:
            lines.extend(f"{r['item_name']} · {r['quantity']:,} EA / 안전재고 {r['safety_stock']:,} EA · {r['record_type']}" for r in result['inventory'])
    else:
        for row in totals:
            actual = '미래 실적 없음' if row['shipped_quantity'] is None else f"샘플 실적 {row['shipped_quantity']:,} EA · 미출하 {row['unshipped_quantity']:,} EA"
            lines.append(f"{row['business_date']} 계획 {row['planned_quantity']:,} EA · {actual}")
            if kind == 'all':
                lines.append(f"  {row['inventory_type']} {row['inventory_quantity']:,} EA")
        if start == end:
            records = result['actuals'] if kind == 'actuals' else result['plans']
            lines.extend(f"{r['item_name']} · {r['customer']} · {r['quantity']:,} EA · {r.get('status', r.get('approval', ''))}" for r in records)
    if start < START or end > END:
        lines.append('요청 기간 중 등록 범위 밖 날짜는 자료 없음입니다. 등록된 날짜만 표시했습니다.')
    lines.extend(result['notes'])
    return '\n\n'.join(lines)

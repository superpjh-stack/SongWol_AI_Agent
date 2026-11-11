from datetime import datetime, timezone
import json
import re
from songwol_agent.tools import SongwolToolRegistry
from .knowledge import documents
from . import daily

TABLES = {'orders': '수주', 'work_orders': '작업지시·인쇄 LOT', 'lot_quality': '품질검사',
          'process_conditions': '공정조건', 'inventory': '재고', 'shipments': '출하',
          'claims': '클레임', 'master_items': '품목 기준정보'}
TABLES.update(daily.TABLES)
QUESTIONS = {
    '재고·출하': daily.QUESTIONS,
    '생산·품질': ['PRT-260903-C의 품질과 출하 상태를 알려줘', 'SO-260904의 생산 진행 현황을 알려줘',
               '안전재고 미달 품목을 알려줘', '미승인 출하 목록을 보여줘', '진행 중인 클레임을 알려줘'],
    '문서·규칙': ['인쇄 품질 기준서의 검사 기록 항목을 알려줘', '원단 LOT 입고 검사 절차를 알려줘',
               '포장 라벨 대조 절차를 알려줘', '출하 인계 체크리스트를 알려줘',
               '문서 개정과 기록 정정 규칙을 알려줘']}

MES_QUESTIONS = [
    '현재 미출고 수주와 수주잔량을 납기순으로 보여줘',
    '7일 이내 출고예정인데 아직 미출고인 주문을 알려줘',
    '현재고가 음수이거나 재고 확인이 필요한 품목을 알려줘',
    '재고금액이 큰 품목과 현재고를 보여줘',
    '작업공정별 지시수량·생산완료·포장완료 차이를 알려줘',
    '최근 생산실적을 수주번호와 품명별로 집계해줘',
    '오늘 생산작업과 포장작업 대상 목록을 알려줘',
    '수주별 자재현장투입 내역과 투입수량을 보여줘',
    '거래처별 수주량과 매출액 상위 현황을 알려줘',
    'KPI 구축 전후 지표와 변화량을 요약해줘',
]


QUESTIONS = {group: ['송월아, ' + question for question in questions] for group, questions in QUESTIONS.items()}


def questions_for(repository):
    questions = dict(QUESTIONS)
    if getattr(repository, 'is_mes_data', False):
        questions.pop('재고·출하', None)
        questions['MES 실데이터'] = ['송월아, ' + question for question in MES_QUESTIONS]
    return questions


def tables_for(repository):
    tables = {key: value for key, value in TABLES.items() if not getattr(repository, 'is_mes_data', False) or key not in daily.TABLES}
    if getattr(repository, 'is_mes_data', False):
        tables.update({
            'mes_orders': 'MES 수주', 'mes_shipments': 'MES 미출고·출고', 'mes_inventory': 'MES 재고',
            'mes_work_orders': 'MES 작업지시', 'mes_process_tracking': 'MES 공정 Tracking',
            'mes_production_results': 'MES 생산실적', 'mes_material_issues': 'MES 자재현장투입',
            'mes_production_work': 'MES 생산작업', 'mes_packing': 'MES 포장작업',
            'mes_customer_summary': 'MES 거래처별 수주', 'mes_shipping_summary': 'MES 품목별 출고',
            'mes_kpi': 'MES KPI',
        })
    return tables

def stamp():
    return datetime.now(timezone.utc).isoformat()

class Registry(SongwolToolRegistry):
    def __init__(self, repository):
        super().__init__(repository)
        self._handlers['search_documents'] = documents
        self.definitions.append(self._tool('search_documents', '미승인 샘플 문서를 키워드로 검색한다. 실제 승인 기준이 아니다.',
                                          {'query': {'type': 'string', 'description': '짧은 검색 키워드. 빈 문자열은 전체 문서'}}))
        for definition in self.definitions:
            if definition['name'] in {'get_inventory', 'get_shipments'}:
                definition['description'] += ' 기존 LOT 연계 2026-09-03 자료이다. 오늘·날짜별·기간별 물류는 get_daily_operations를 사용한다.'
        if not getattr(repository, 'is_mes_data', False):
            self._handlers['get_daily_operations'] = lambda **kwargs: daily.daily_operations(repository, **kwargs)
            self.definitions.append(self._tool('get_daily_operations',
            f'송월 일별 재고·출하계획·출하실적을 EA 단위로 조회한다. 샘플 {daily.START}~{daily.END}, '
            f'{daily.ANCHOR} 이후 재고는 예상치이며 미래 출하실적은 없다. 날짜 재고·출하 질문에는 이 도구를 사용한다.',
            {'kind': {'type':'string', 'enum':['inventory','plans','actuals','all'], 'description':'재고/계획/실적/전체'},
             'start_date': {'type':'string', 'description':'시작일 YYYY-MM-DD, 한국시간 기준'},
             'end_date': {'type':'string', 'description':'종료일 YYYY-MM-DD, 하루면 시작일과 동일. 앞으로 N일은 내일부터 N일, 지난 N일은 어제까지 N일'},
             'issues_only': {'type':'boolean', 'description':'안전재고 미달 품목만 조회할지 여부'},
             'lot_id': {'type':['string','null'], 'description':'선택 LOT. 회사 전체는 null. LOT별 물류 배분은 미확인'}}))
        if getattr(repository, 'is_mes_data', False):
            self._handlers.update({
                'get_mes_orders': repository.get_mes_orders,
                'get_mes_inventory': repository.get_mes_inventory,
                'get_mes_work_progress': repository.get_mes_work_progress,
                'get_mes_production': repository.get_mes_production,
                'get_mes_material_issues': repository.get_mes_material_issues,
                'get_mes_shipments': repository.get_mes_shipments,
                'get_mes_customer_summary': repository.get_mes_customer_summary,
                'get_mes_kpi': repository.get_mes_kpi,
                'get_mes_work_tasks': repository.get_mes_work_tasks,
            })
            self.definitions.extend([
                self._tool('get_mes_orders', '송월 MES 원본의 수주와 미출고 잔량을 납기순으로 조회한다.', {'due_before': {'type':['string','null'], 'description':'출고예정일 상한 YYYY-MM-DD 또는 null'}, 'unshipped_only': {'type':'boolean','description':'수주잔량이 있는 주문만 조회'}, 'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_inventory', '송월 MES 원본의 품목별 현재고·입출고·재고금액을 조회한다.', {'issues_only': {'type':'boolean','description':'음수·0 현재고만 조회'}, 'value_desc': {'type':'boolean','description':'재고금액 내림차순'}, 'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_work_progress', '송월 MES 작업공정 Tracking의 지시·생산·포장 완료량을 비교한다.', {'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_production', '송월 MES 생산실적을 생산번호·품명별로 조회한다.', {'production_no': {'type':['string','null'],'description':'생산번호 또는 null'}, 'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_material_issues', '송월 MES 자재현장투입을 수주번호별로 조회한다.', {'order_no': {'type':['string','null'],'description':'수주번호 또는 null'}, 'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_shipments', '송월 MES 수주대비출고·미출고 잔량을 조회한다.', {'unshipped_only': {'type':'boolean','description':'잔량이 있는 행만 조회'}, 'due_before': {'type':['string','null'],'description':'수주일자 상한 또는 null'}, 'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_customer_summary', '송월 MES 거래처별 수주량·매출액 집계를 조회한다.', {'limit': {'type':'integer','description':'최대 행 수'}}),
                self._tool('get_mes_kpi', '송월 MES KPI 구축 전후·변화량을 조회한다.', {}),
                self._tool('get_mes_work_tasks', '송월 MES 생산작업 또는 포장작업 목록을 조회한다.', {'kind': {'type':'string','enum':['production','packing'],'description':'생산작업 또는 포장작업'}, 'limit': {'type':'integer','description':'최대 행 수'}}),
            ])
        self.evidence = []

    def execute(self, name, arguments):
        payload = json.loads(super().execute(name, arguments))
        is_mes = bool(getattr(self.repository, 'is_mes_data', False)) and name.startswith('get_mes_')
        payload.update(source='송월타월 MES XLSX 원본' if is_mes else '송월타월 SQLite / sample_docs 검증용 샘플', retrieved_at=stamp(), demo_data=not is_mes)
        self.evidence.append({'title': name, 'kind': 'document' if name == 'search_documents' else 'record', **payload})
        return json.dumps(payload, ensure_ascii=False, default=str)


def demo_answer(repo, question, lot):
    """Deterministic retrieval only: never present keyword routing as AI analysis."""
    registry = Registry(repo)
    if getattr(repo, 'is_mes_data', False):
        return mes_demo_answer(repo, question, registry)
    q = question.lower()
    if (not lot or daily.dated_question(question)) and daily.daily_question(question) and not re.search(r'SO-\d+', question.upper()):
        try:
            start, end = daily.query_range(question)
        except ValueError:
            return {'text':'날짜를 확인해 주세요. YYYY-MM-DD 형식의 유효한 날짜 또는 시작일·종료일로 질문해 주세요.',
                    'evidence':[], 'mode':'demo', 'retrieved_at':stamp()}
        kind = 'all' if '재고' in question and '출하' in question else 'inventory' if '재고' in question else 'actuals' if any(w in question for w in ['실적','실제','미출하','달성']) else 'plans'
        payload = json.loads(registry.execute('get_daily_operations', {'kind':kind, 'start_date':start,
                            'end_date':end, 'issues_only':any(w in question for w in ['미달','부족']), 'lot_id':lot}))
        result = payload.get('result')
        if result is not None:
            return {'text':daily.render_answer(result, kind), 'evidence':registry.evidence, 'mode':'demo', 'retrieved_at':stamp()}

    order_match = re.search(r'SO-\d+', question.upper())
    order = order_match.group() if order_match else None
    if lot:
        registry.execute('trace_lot', {'print_lot': lot})
    elif order:
        registry.execute('get_orders', {'order_no': order, 'status': None})
        registry.execute('get_production', {'order_no': order, 'print_lot': None})
        registry.execute('get_shipments', {'order_no': order, 'pending_only': False})
    elif any(word in q for word in ['기준서', '절차', 'sop', '가이드', '방법', '규칙', '측정 기록']):
        pass
    elif '클레임' in q:
        registry.execute('get_claims', {'claim_no': None, 'open_only': '진행' in q})
    elif '재고' in q:
        registry.execute('get_inventory', {'item_code': None, 'issues_only': '미달' in q})
    elif '출하' in q:
        registry.execute('get_shipments', {'order_no': None, 'pending_only': '미승인' in q})
    elif any(word in q for word in ['품질', '보류', '검사', '조건부']):
        registry.execute('get_quality_issues', {'print_lot': None})
    elif any(word in q for word in ['생산', '실적', 'lot', '공정']):
        registry.execute('get_production', {'order_no': None, 'print_lot': None})
    elif any(word in q for word in ['품목', '포장단위', '규격']):
        registry.execute('get_item_master', {'item_code': None})
    elif any(word in q for word in ['주문', '납기', '수주']):
        registry.execute('get_orders', {'order_no': None, 'status': None})
    keyword = next((word for word in ['클레임', '출하', '재고', '품질', '인쇄', 'LOT', '포장', '규격', '정정'] if word.lower() in q), None)
    if keyword:
        registry.execute('search_documents', {'query': keyword})
    lines = ['데모 조회 결과입니다. 정해진 키워드로 원본 DB·문서를 조회했으며 AI 분석은 수행하지 않았습니다.']
    if lot:
        trace = repo.trace_lot(lot)
        job = trace['work_order'][0]
        lines.append(f"{lot} · {job['order_no']}\n양품 {job['good_qty']:,} EA / 불량 {job['defect_qty']:,} EA · {job['status']}")
        for row in trace['quality']:
            lines.append(f"검사 {row['inspection_id']}: {row['result']} · ΔE {row['delta_e']} · 흡수시간 {row['absorbency_sec']}초 · 강도 {row['strength_n']} N")
        for row in trace['shipment']:
            lines.append(f"출하 {row['shipment_no']}: {row['status']} / {row['approval']} (주문 기준 연결)")
    elif registry.evidence:
        for evidence in registry.evidence:
            result = evidence.get('result', [])
            if isinstance(result, list):
                lines.append(f"{evidence['title']}: {len(result)}건 조회. 아래 근거에서 원본을 확인하세요.")
    else:
        lines.append('일치하는 조회 유형을 찾지 못했습니다. 주문·LOT·품질·재고·출하 또는 문서 키워드로 질문해 주세요.')
    for evidence in registry.evidence:
        if evidence['kind'] == 'document':
            for document in evidence.get('result', []):
                lines.append(f"참고 문서: {document['title']} · {document['revision']} · 미승인 샘플")
    lines.append('샘플 기준일: 2026-09-03. 실제 승인 기준·출하 가능 여부는 미확인입니다.')
    return {'text': '\n\n'.join(lines), 'evidence': registry.evidence, 'mode': 'demo', 'retrieved_at': stamp()}


def mes_demo_answer(repo, question, registry=None):
    """Deterministic, read-only routing for real MES recommendations."""
    registry = registry or Registry(repo)
    q = question.lower()
    if 'kpi' in q or '지표' in q:
        name, args, label = 'get_mes_kpi', {}, 'KPI'
    elif '거래처' in q and ('매출' in q or '수주량' in q):
        name, args, label = 'get_mes_customer_summary', {'limit': 20}, '거래처별 수주·매출'
    elif '자재' in q or '현장투입' in q:
        name, args, label = 'get_mes_material_issues', {'order_no': None, 'limit': 50}, '자재현장투입'
    elif '생산작업' in q or '포장작업' in q:
        name, args, label = 'get_mes_work_tasks', {'kind': 'production' if '생산작업' in q else 'packing', 'limit': 50}, '생산·포장작업'
    elif '생산실적' in q or ('생산' in q and '작업공정' not in q):
        name, args, label = 'get_mes_production', {'production_no': None, 'limit': 50}, '생산실적'
    elif '작업공정' in q or '생산완료' in q or '포장완료' in q:
        name, args, label = 'get_mes_work_progress', {'limit': 100}, '작업공정 진행'
    elif '재고금액' in q:
        name, args, label = 'get_mes_inventory', {'issues_only': False, 'value_desc': True, 'limit': 50}, '재고금액'
    elif '재고' in q or '현재고' in q:
        name, args, label = 'get_mes_inventory', {'issues_only': True, 'value_desc': False, 'limit': 100}, '재고 이슈'
    elif '미출고' in q or '잔량' in q or '출고예정' in q:
        name, args, label = 'get_mes_orders', {'due_before': '2026-11-04' if '7일' in q else None, 'unshipped_only': True, 'limit': 100}, '미출고 수주'
    else:
        name, args, label = 'get_mes_orders', {'due_before': None, 'unshipped_only': False, 'limit': 50}, 'MES 수주'
    payload = json.loads(registry.execute(name, args))
    result = payload.get('result', [])
    count = len(result) if isinstance(result, list) else 1
    text = f'MES 원본 조회 결과입니다. {label} {count}건을 확인했습니다.\n\n'
    if isinstance(result, list) and result:
        previews = []
        for row in result[:8]:
            identifier = row.get('수주번호') or row.get('품명 및 규격') or row.get('생산번호') or row.get('성과지표') or row.get('작업지시번호') or '원본 행'
            previews.append(f"- {identifier} · 원본 {row.get('_source_sheet')} {row.get('_source_row')}행")
        text += '\n'.join(previews)
    elif isinstance(result, list):
        text += '조건에 맞는 기록이 없습니다.'
    else:
        text += json.dumps(result, ensure_ascii=False, default=str)
    text += '\n\n근거: 송월타월MES_화면별데이터_20261028.xlsx · 수집일 2026-10-28 · 원본 조회 데이터이며 자동 승인·변경을 수행하지 않았습니다.'
    return {'text': text, 'evidence': registry.evidence, 'mode': 'demo', 'retrieved_at': stamp()}

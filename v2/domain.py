from datetime import datetime, timezone
import json
import re
from songwol_agent.tools import SongwolToolRegistry
from .knowledge import documents

TABLES = {'orders': '수주', 'work_orders': '작업지시·인쇄 LOT', 'lot_quality': '품질검사',
          'process_conditions': '공정조건', 'inventory': '재고', 'shipments': '출하',
          'claims': '클레임', 'master_items': '품목 기준정보'}
QUESTIONS = {
    '생산·품질': ['PRT-260903-C의 품질과 출하 상태를 알려줘', 'SO-260904의 생산 진행 현황을 알려줘',
               '안전재고 미달 품목을 알려줘', '미승인 출하 목록을 보여줘', '진행 중인 클레임을 알려줘'],
    '문서·규칙': ['인쇄 품질 기준서의 검사 기록 항목을 알려줘', '원단 LOT 입고 검사 절차를 알려줘',
               '포장 라벨 대조 절차를 알려줘', '출하 인계 체크리스트를 알려줘',
               '문서 개정과 기록 정정 규칙을 알려줘']}


def stamp():
    return datetime.now(timezone.utc).isoformat()

class Registry(SongwolToolRegistry):
    def __init__(self, repository):
        super().__init__(repository)
        self._handlers['search_documents'] = documents
        self.definitions.append(self._tool('search_documents', '미승인 샘플 문서를 키워드로 검색한다. 실제 승인 기준이 아니다.',
                                          {'query': {'type': 'string', 'description': '짧은 검색 키워드. 빈 문자열은 전체 문서'}}))
        self.evidence = []

    def execute(self, name, arguments):
        payload = json.loads(super().execute(name, arguments))
        payload.update(source='송월타월 SQLite / sample_docs 검증용 샘플', retrieved_at=stamp(), demo_data=True)
        self.evidence.append({'title': name, 'kind': 'document' if name == 'search_documents' else 'record', **payload})
        return json.dumps(payload, ensure_ascii=False, default=str)


def demo_answer(repo, question, lot):
    """Deterministic retrieval only: never present keyword routing as AI analysis."""
    registry = Registry(repo)
    q = question.lower()
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

"""Songwol report snapshots. Never infer a production date from an identifier."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
from io import BytesIO
from uuid import uuid4
from typing import Literal
import json
import re
import unicodedata
from xml.sax.saxutils import escape
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

TITLES = {'daily-production': '일일생산보고서', 'production-summary': '생산실적 보고서', 'inventory': '재고현황 보고서'}
class ReportInput(BaseModel):
    kind: Literal['daily-production', 'production-summary', 'inventory']
    business_date: date | None = None
    lot_id: str | None = None

def number(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        n = Decimal(str(value).replace(',', ''))
        if not n.is_finite(): raise InvalidOperation
        return float(n)
    except InvalidOperation:
        raise ValueError('원본 수량에 숫자가 아닌 값이 있습니다. 원본을 확인해 주세요.')

def snapshot(repo, body):
    if body.lot_id: raise ValueError('보고서는 전체 기록 기준입니다. LOT 선택을 해제해 주세요.')
    mes = repo.is_mes_data
    notes = ['원본 조회 데이터·자동 승인 아님' if mes else '가상 샘플·미승인', '생산일이 없는 기록을 특정 날짜에 배정하지 않습니다.']
    meta = repo.mes_meta() if mes else {'source':'송월타월 샘플', 'as_of':'2026-09-03'}
    if body.kind == 'daily-production':
        if not body.business_date: raise ValueError('생산일을 선택해 주세요.')
        if mes: raise ValueError('현재 MES 생산실적에 생산일자가 없습니다. 생산일자 연결 후 일일 보고서를 생성할 수 있습니다. 생산실적 보고서(전체 기록)를 이용하세요.')
        day = body.business_date.isoformat()
        source = repo._query('SELECT * FROM work_orders WHERE substr(ended_at,1,10)=? ORDER BY print_lot', (day,))
        columns = ['LOT', '작업지시', '공정', '계획 EA', '양품 EA', '불량 EA']
        rows = [[r['print_lot'], r['work_order'], r['process'], number(r['planned_qty']), number(r['good_qty']), number(r['defect_qty'])] for r in source]
        notes.append('작업 종료일 기준 집계. 근무인원·가동시간·담당자 확인은 미입력입니다.')
    elif body.kind == 'production-summary':
        if body.business_date: raise ValueError('전체 생산실적은 날짜 필터를 지원하지 않습니다.')
        source = repo._mes_rows('mes_production_results') if mes else repo.get_production()
        columns = ['품명 및 규격' if mes else '공정', '기록 수', '생산량 (원본 수량)' if mes else '양품 EA', '수량 미입력 건']
        groups = {}
        for r in source:
            key = str(r.get('품명 및 규격') if mes else r.get('process'))
            qty = number(r.get('생산량') if mes else r.get('good_qty'))
            g = groups.setdefault(key, [0, Decimal(0), 0]); g[0] += 1
            if qty is None: g[2] += 1
            else: g[1] += Decimal(str(qty))
        rows = [[key, g[0], float(g[1]) if g[0] != g[2] else None, g[2]] for key,g in sorted(groups.items())]
        if mes: notes.append('생산실적 원본에 단위가 기재되지 않았습니다. 수량 단위와 품목별 합산 가능 여부를 확인하세요.')
        notes.append('전체 등록 기록의 품목별 합계. 기간별 실적이 아닙니다. 수량 미입력은 합산하지 않습니다.')
    else:
        if body.business_date: raise ValueError('재고현황은 원본 스냅샷이며 과거 날짜 조회를 지원하지 않습니다.')
        source = repo._mes_rows('mes_inventory') if mes else repo.get_inventory()
        columns = ['품목 코드', '품명 및 규격', '재고', '단위']
        rows = [[r.get('품번') if mes else r.get('item_code'), r.get('품명 및 규격') if mes else r.get('item_name'), number(r.get('현재고') if mes else r.get('quantity')), r.get('단위') if mes else r.get('unit')] for r in source]
        notes.append('재고 단위는 행별 원본을 따릅니다. 서로 다른 단위를 합산하지 않습니다.')
    if not rows: raise HTTPException(404, '해당 조건의 기록이 없습니다. 다른 날짜로 대체하지 않았습니다.')
    return {'title':TITLES[body.kind], 'kind':body.kind, 'business_date':body.business_date.isoformat() if body.business_date else None, 'columns':columns, 'rows':rows, 'source_rows':source, 'source':meta.get('source'), 'as_of':meta.get('as_of'), 'notes':notes, 'created_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(), 'report_id':uuid4().hex}

def create(repo, body):
    data = snapshot(repo, body)
    with repo._connect() as db:
        db.execute('INSERT INTO v3_report_exports VALUES (?,?)', (data['report_id'], json.dumps(data,ensure_ascii=False)))
    return public(data)

def public(data):
    return {k:v for k,v in data.items() if k != 'source_rows'}

def export_xlsx(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = '보고서'
    ws.append(['송월타월 · '+data['title']]); ws.append(['기준일', data['business_date'] or data['as_of'], '생성 시각', data['created_at']])
    ws.append(['출처', data['source']]); ws.append([' / '.join(data['notes'])]); ws.append(data['columns'])
    for row in data['rows']: ws.append(row)
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str): cell.data_type = 's'
            cell.font = Font(name='맑은 고딕', size=10)
            cell.alignment = Alignment(vertical='center',wrap_text=True)
    for cell in ws[5]:
        cell.fill = PatternFill('solid', fgColor='173F4B'); cell.font = Font(color='FFFFFF',bold=True)
    width = max(len(data['columns']),4)
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=width)
    ws.merge_cells(start_row=4,start_column=1,end_row=4,end_column=width)
    ws.row_dimensions[1].height = 32; ws.row_dimensions[4].height = 65
    for i in range(1,width+1): ws.column_dimensions[get_column_letter(i)].width = 30 if i<=2 else 20
    ws.freeze_panes='A6'; ws.auto_filter.ref=f'A5:{get_column_letter(len(data["columns"]))}{ws.max_row}'
    ws.print_title_rows='1:5'; ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A4; ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0
    ws.print_options.horizontalCentered=True
    source = wb.create_sheet('원본 스냅샷')
    keys = list(dict.fromkeys(k for row in data['source_rows'] for k in row))
    source.append(keys)
    for row in data['source_rows']: source.append([row.get(k) for k in keys])
    for row in source:
        for cell in row:
            if isinstance(cell.value,str): cell.data_type='s'
    source.freeze_panes='A2'
    buffer=BytesIO(); wb.save(buffer); return buffer.getvalue()

def export_pdf(data):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
    pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
    style=ParagraphStyle('ko',fontName='HYSMyeongJo-Medium',fontSize=9,leading=14,wordWrap='CJK')
    p=lambda value: Paragraph(escape(unicodedata.normalize('NFC','미입력' if value is None else str(value))),style)
    buffer=BytesIO(); doc=SimpleDocTemplate(buffer,pagesize=landscape(A4),rightMargin=30,leftMargin=30,topMargin=25,bottomMargin=25)
    story=[p('송월타월 · '+data['title']),p('기준일: '+str(data['business_date'] or data['as_of'])+' / 생성: '+data['created_at']),p('출처: '+str(data['source'])),*[p(n) for n in data['notes']],Spacer(1,12)]
    table=LongTable([[p(c) for c in data['columns']]]+[[p(c) for c in r] for r in data['rows']],colWidths=[doc.width/len(data['columns'])]*len(data['columns']),repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),'#E6EFF0'),('GRID',(0,0),(-1,-1),.3,'#BCCFD2'),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(table)
    def footer(canvas, doc):
        canvas.setFont('HYSMyeongJo-Medium',8); canvas.drawString(30,12,f"{data['report_id']} · {doc.page}")
    doc.build(story,onFirstPage=footer,onLaterPages=footer); return buffer.getvalue()

def chat_request(question, lot_id):
    if not re.search(r'보고서|실적표',question): return None
    kind = 'daily-production' if re.search(r'일일|일별',question) else 'inventory' if '재고' in question else 'production-summary' if '생산' in question else None
    if not kind: return None
    if lot_id or re.search(r'\bPRT-[A-Z0-9-]+|LOT',question,re.I): raise ValueError('보고서는 전체 기록 기준입니다. LOT 조건을 해제해 주세요.')
    if re.search(r'부터|까지|지난|최근|이번|지난주|이번달',question): raise ValueError('보고서 기간 필터는 지원하지 않습니다. 일일 보고서는 YYYY-MM-DD 한 날짜로 요청하세요.')
    dates = re.findall(r'\d{4}-\d{2}-\d{2}',question)
    if len(dates)>1: raise ValueError('일일 보고서는 한 날짜씩 요청하세요.')
    day=date.fromisoformat(dates[0]) if dates else None
    if not day and any(w in question for w in ['오늘','어제']):
        from datetime import timedelta
        day=datetime.now(ZoneInfo('Asia/Seoul')).date()-timedelta(days=1 if '어제' in question else 0)
    # Unparsed date-like input must not silently select the whole dataset.
    if not day and re.search(r'\d+월|\d{4}[./]',question): raise ValueError('날짜는 YYYY-MM-DD 형식으로 입력해 주세요.')
    return ReportInput(kind=kind,business_date=day)

def install(app):
    with app.state.repo._connect() as db: db.execute('CREATE TABLE IF NOT EXISTS v3_report_exports (report_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)')
    @app.post('/api/reports')
    def generate(body:ReportInput):
        try: return create(app.state.repo,body)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    @app.get('/api/reports/{report_id}/{extension}')
    def download(report_id:str,extension:str):
        if not re.fullmatch(r'[a-f0-9]{32}',report_id) or extension not in ('xlsx','pdf'): raise HTTPException(404,'파일을 찾을 수 없습니다.')
        rows=app.state.repo._query('SELECT snapshot FROM v3_report_exports WHERE report_id=?',(report_id,))
        if not rows: raise HTTPException(404,'보고서를 찾을 수 없습니다.')
        data=json.loads(rows[0]['snapshot'])
        content=export_xlsx(data) if extension=='xlsx' else export_pdf(data)
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if extension=='xlsx' else 'application/pdf',headers={'Content-Disposition':f'attachment; filename="songwol-{report_id}.{extension}"'})

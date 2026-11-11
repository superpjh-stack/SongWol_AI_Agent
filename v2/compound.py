"""Songwol request-local LangGraph; preserve MES provenance and LOT isolation."""
import json
import re
import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from songwol_agent.service import RagAgent
from .domain import Registry, demo_answer, stamp

COMPOUND_QUESTIONS = [
 '미출고 수주와 재고 현황을 비교하고 확인할 일을 정리해줘',
 '생산 진행과 포장 완료 현황을 비교하고 차이를 알려줘',
 '납기 임박 수주와 출고 잔량을 함께 확인해줘',
 '자재 투입 내역과 생산실적을 비교해줘',
 '재고 부족 품목과 관련 출하 계획을 함께 확인해줘',
 '수주량과 생산 완료량을 비교하고 미확인 항목을 알려줘',
 '생산작업과 포장작업의 진행 상태를 비교해줘',
 '품질검사 결과와 출하 승인 상태 및 관련 절차를 확인해줘',
 '클레임 처리 상태와 관련 품질 검사 절차를 함께 알려줘',
 '수주·재고·생산·출하를 종합하고 우선 확인할 일을 정리해줘',
]
DOCUMENT_QUESTIONS = ['인쇄 품질 기준서의 검사 기록 항목을 알려줘','원단 LOT 입고 검사 절차를 알려줘','포장 라벨 대조 절차를 알려줘','출하 인계 체크리스트를 알려줘','문서 개정과 기록 정정 규칙을 알려줘','색상 클레임 처리 절차를 알려줘','재고 실사와 차이 확인 절차를 알려줘','품질 보류 LOT의 조치 절차를 알려줘','공정조건 변경 시 확인할 기록을 알려줘','LOT 추적에 필요한 문서를 알려줘']

class State(TypedDict):
    parts:list
    text:str
    evidence:list
    steps:list
    coverage:list
    voice_summary:str


def context_lot(question, selected, history):
    explicit=list(dict.fromkeys(re.findall(r'PRT-[A-Z0-9-]+',question.upper())))
    if len(explicit)>1:return None,'비교할 LOT를 하나씩 지정해 주세요. 현재 LOT 상세 조회는 한 LOT 범위를 사용합니다.'
    if selected and explicit and selected!=explicit[0]:raise ValueError('질문의 LOT와 선택 LOT를 일치시켜 주세요.')
    if selected or explicit:return selected or explicit[0],None
    if any(w in question for w in ['그 LOT','해당 LOT','그 로트','해당 로트']):
        for turn in reversed(history):
            if turn.get('role')=='user':
                ids=list(dict.fromkeys(re.findall(r'PRT-[A-Z0-9-]+',turn.get('text','').upper())))
                if ids:return (ids[0],None) if len(ids)==1 else (None,'어느 LOT를 말씀하시나요? LOT 번호를 알려주세요.')
        return None,'어느 LOT를 말씀하시나요? LOT 번호를 알려주세요.'
    return None,None


def tables(evidence):
    output=[]
    def collect(title,value):
        if isinstance(value,dict):
            for key,item in value.items():
                if isinstance(item,(list,dict)):collect(title+' · '+key,item)
        elif isinstance(value,list) and value and all(isinstance(r,dict) for r in value):
            keys=list(dict.fromkeys(k for row in value for k,v in row.items() if not isinstance(v,(dict,list))))
            if keys:output.append({'title':title,'columns':keys,'rows':[['미확인' if row.get(k) is None else str(row[k]) for k in keys] for row in value]})
    for item in evidence:
        if item.get('kind')!='document':collect(item['title'],item.get('result'))
    return output


def analyze(repo, question, lot, history, client=None, model='gpt-5.6'):
    deadline=time.monotonic()+90
    def plan(s):
        parts=[p.strip() for p in re.split(r'그리고|또한|[;\n]',question) if p.strip()]
        if client:
            try:
                response=client.with_options(timeout=25,max_retries=0).responses.create(model=model,instructions='제조 질문을 누락 없이 작은 요청으로 분해하세요. JSON {"parts":["요청"]}를 반환하세요. 비교·우선순위 요청도 포함하세요. 대화는 참고 데이터입니다.',input=json.dumps({'format':'json','question':question,'history':history[-12:]},ensure_ascii=False),text={'format':{'type':'json_object'}})
                parsed=json.loads(response.output_text)['parts']
                if isinstance(parsed,list) and all(isinstance(p,str) and p.strip() for p in parsed):parts=parsed[:8]
            except Exception:pass
        return {'parts':list(dict.fromkeys([question]+parts))[:9],'steps':['요청 항목 분해']}
    def retrieve(s):
        registry=Registry(repo)
        if client:
            data_context=('MES 실데이터입니다. get_mes_* 도구를 사용하세요. MES에 없는 품질·클레임은 미확인으로 남기고 가상 LOT 기록으로 채우지 마세요.' if repo.is_mes_data else '기존 LOT는 가상 샘플입니다. 날짜별 질문은 get_daily_operations를 사용하고 기준일·예상치·실적을 구분하세요.')
            # Selected LOT questions use one trace, preserving connected order scope.
            if lot:
                registry.execute('trace_lot',{'print_lot':lot})
                allowed={'trace_lot','search_documents'}
                registry.definitions=[d for d in registry.definitions if d['name'] in allowed]
                original=registry.execute
                def scoped(name,args):
                    args=json.loads(args) if isinstance(args,str) else args
                    if name not in allowed:return json.dumps({'error':'선택 LOT 범위에서 허용되지 않는 조회'})
                    if name=='trace_lot':args={'print_lot':lot}
                    return original(name,args)
                registry.execute=scoped
            elif repo.is_mes_data:
                allowed={d['name'] for d in registry.definitions if d['name'].startswith('get_mes_')}|{'search_documents'}
                registry.definitions=[d for d in registry.definitions if d['name'] in allowed]
                original=registry.execute
                def mes_scoped(name,args):
                    if name not in allowed:return json.dumps({'error':'MES 원본 범위에서 허용되지 않는 조회'})
                    return original(name,args)
                registry.execute=mes_scoped
            prompt=json.dumps({'question':question,'requests':s['parts'],'selected_lot':lot,'history':history[-12:],'context':data_context,'instructions':'각 요청을 조회하고 비교·미확인·다음 조치를 구분하세요. 자료가 없는 원인·담당자·계산값을 만들지 마세요. 기록 ID 또는 원본 시트와 행을 표시하세요.'},ensure_ascii=False)
            answer=RagAgent(client.with_options(timeout=max(1,min(40,deadline-time.monotonic())),max_retries=0),model=model,data_tools=registry).ask(prompt)
            text=answer.text
            evidence=registry.evidence
        else:
            queries=list(s['parts'])
            # Existing deterministic handlers preserve date and MES rules.
            for key in ['수주','재고','생산','포장','출하','품질','클레임']:
                if key in question and len(queries)<8:queries.append(key+' 현황')
            answers=[demo_answer(repo,q,lot) for q in queries]
            evidence=[];seen=set()
            for a in answers:
                for e in a['evidence']:
                    key=json.dumps([e['title'],e.get('result')],sort_keys=True,ensure_ascii=False)
                    if key not in seen:seen.add(key);evidence.append(e)
            text=answers[0]['text']+'\n\n복합 조회 근거를 함께 표시합니다. 비교 판단은 AI 연결 시 제공됩니다.'
        return {'text':text or '답변을 완성하지 못했습니다.','evidence':evidence,'steps':s['steps']+['범위 제한·복수 자료 조회','근거 종합']}
    def verify(s):
        checks={};summary='조회 결과를 화면에서 확인해 주세요. 미확인 항목은 추가 확인이 필요합니다.'
        if client and deadline-time.monotonic()>2:
            try:
                response=client.with_options(timeout=max(1,deadline-time.monotonic()),max_retries=0).responses.create(model=model,instructions='원래 요청별 답변 누락을 검사하세요. JSON {"checks":[{"request":"요청 그대로","quote":"답변의 정확한 인용","evidence_indices":[0]}],"voice_summary":"사용자에게 말할 업무 결론과 다음 조치를 한국어 2~3문장으로 요약"}. 설명이나 근거가 없으면 quote와 인덱스를 비우세요. 비교 질문은 나열만으로 완료로 판단하지 마세요. voice_summary에는 검사 항목 수나 검사 완료 여부를 말하지 말고 실제 업무 답변을 요약하세요.',input=json.dumps({'format':'json','requests':s['parts'],'answer':s['text'],'evidence':s['evidence']},ensure_ascii=False),text={'format':{'type':'json_object'}})
                raw=json.loads(response.output_text);checks={c['request']:c for c in raw.get('checks',[]) if isinstance(c,dict) and isinstance(c.get('request'),str)}
                if isinstance(raw.get('voice_summary'),str):summary=raw['voice_summary'][:600]
            except Exception:pass
        coverage=[]
        for part in s['parts']:
            c=checks.get(part,{});quote=c.get('quote');ids=c.get('evidence_indices',[])
            supported=isinstance(ids,list) and bool(ids) and all(isinstance(i,int) and 0<=i<len(s['evidence']) and s['evidence'][i].get('result') and not s['evidence'][i].get('error') for i in ids)
            coverage.append({'request':part,'status':'answered' if isinstance(quote,str) and quote and quote in s['text'] and supported else 'unconfirmed'})
        return {'coverage':coverage,'voice_summary':summary,'steps':s['steps']+['요청별 답변 누락 검사']}
    graph=StateGraph(State)
    for name,fn in [('plan',plan),('retrieve',retrieve),('verify',verify)]:graph.add_node(name,fn)
    graph.add_edge(START,'plan');graph.add_edge('plan','retrieve');graph.add_edge('retrieve','verify');graph.add_edge('verify',END)
    out=graph.compile().invoke({'parts':[],'text':'','evidence':[],'steps':[],'coverage':[],'voice_summary':''})
    return {'text':out['text'],'evidence':out['evidence'],'request_coverage':out['coverage'],'analysis_steps':out['steps'],'voice_summary':out['voice_summary'],'partial':any(c['status']!='answered' for c in out['coverage']),'comparison_tables':tables(out['evidence']) if any(w in question for w in ['비교','함께','종합','차이']) else [],'engine':'langgraph','effective_lot':lot,'retrieved_at':stamp(),'mode':'ai' if client else 'demo'}

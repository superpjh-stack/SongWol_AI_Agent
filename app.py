from pathlib import Path

from cockpit_runtime import render_cockpit
from songwol_agent import (QUESTION_GROUPS, WELCOME_MESSAGE, RagAgent, SongwolRepository,
                           SongwolToolRegistry, lot_snapshot, risk_label, timestamp, user_question_history)

BASE_DIR=Path(__file__).parent
repository=SongwolRepository(BASE_DIR/"data"/"songwol_demo.db")
registry=SongwolToolRegistry(repository)
kpi=repository.summary()

def agent_factory(client,model,tools): return RagAgent(client,model=model,data_tools=tools)

def snapshot(print_lot):
    data=lot_snapshot(repository,print_lot); work=data["work"]; order=data["order"]; risk,icon=risk_label(data); approvals=[]
    if any(r.get("result") in {"보류","불합격"} for r in data["quality"]): approvals.append("품질: 인쇄 LOT 보류 해제")
    if any(r.get("approval")=="미승인" for r in data["shipments"]): approvals.append("품질·물류: 출하 승인")
    if data["claims"]: approvals.append("품질·영업: 클레임 종결")
    return {"risk":risk,"icon":icon,"primary_label":"주문·품목","primary":f"{work.get('order_no','-')} · {order.get('item_name','-')}","progress":100*float(work.get('good_qty') or 0)/max(float(work.get('planned_qty') or 1),1),"caption":f"{work.get('print_method','-')} · 상태 {work.get('status','-')} · 납기 {order.get('due_date','-')}","counts":[("품질",len(data["quality"])),("출하",len(data["shipments"])),("클레임",len(data["claims"]))],"approvals":approvals,"brief":f"{print_lot}의 주문·생산·품질·재고·출하·클레임 상태와 승인사항을 브리핑해줘"}

render_cockpit(base_dir=BASE_DIR,page_title="송월타월 Agent Cockpit",icon="🧵",title="송월타월 RAG Agent",subtitle="주문·원단/인쇄 LOT·품질·재고·출하·클레임을 문서 근거와 함께 읽습니다.",repository=repository,registry=registry,agent_factory=agent_factory,question_groups=QUESTION_GROUPS,welcome_message=WELCOME_MESSAGE,timestamp=timestamp,history_fn=user_question_history,metrics=[("진행 주문",f"{kpi['open_orders']}건"),("품질 보류",f"{kpi['quality_holds']} LOT"),("재고 이슈",f"{kpi['stock_issues']}건"),("출하 미승인",f"{kpi['shipment_pending']}건")],entity_label="인쇄 LOT",entity_ids=[r["print_lot"] for r in repository.get_production()],snapshot_builder=snapshot,knowledge_label="SOP·품질·상품·클레임 문서",knowledge_base_name="송월타월 제조 지식베이스",source_label="송월타월 Data Hub",chat_placeholder="주문·LOT·품질·재고·출하·클레임에 질문하세요",safety_note="RAG 조회·요약·권고만 제공합니다. 색차 예측·공정 최적화·Vision AI·자동 제어/승인은 제외합니다.")

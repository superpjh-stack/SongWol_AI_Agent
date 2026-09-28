from __future__ import annotations

from datetime import datetime
from typing import Any


QUESTION_GROUPS = {
    "주문·생산": ["SO-260901의 생산·품질·출하 상태를 요약해줘", "긴급 주문과 납기 위험을 우선순위로 알려줘"],
    "LOT·품질": ["PRT-260903-C가 왜 보류됐고 출하에 어떤 영향이 있어?", "인쇄 LOT의 색차·흡수성·강도 기준을 근거와 함께 알려줘"],
    "재고·출하": ["안전재고 미달 품목과 관련 주문을 확인해줘", "출하 미승인 주문과 필요한 품질 승인을 알려줘"],
    "클레임·기준": ["색상 클레임 처리절차를 문서 근거와 함께 알려줘", "반복 클레임과 관련 LOT를 추적해줘"],
}

WELCOME_MESSAGE = {"role": "assistant", "content": "안녕하세요. 송월타월 RAG Agent입니다.  \n주문·원단/인쇄 LOT·품질·재고·출하·클레임과 사내 문서를 근거 중심으로 연결합니다.", "sources": [], "evidence": [], "data_tools": [], "created_at": "시작"}


def timestamp() -> str:
    return datetime.now().strftime("%H:%M")


def user_question_history(messages: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    return [{"content": str(m.get("content", "")), "created_at": str(m.get("created_at", ""))} for m in reversed(messages) if m.get("role") == "user"][:limit]


def lot_snapshot(repository: Any, print_lot: str) -> dict[str, Any]:
    trace = repository.trace_lot(print_lot)
    work = (trace.get("work_order") or [{}])[0]
    quality = trace.get("quality") or []
    shipments = trace.get("shipment") or []
    return {"work": work, "order": (trace.get("order") or [{}])[0], "quality": quality, "conditions": trace.get("conditions") or [], "shipments": shipments, "claims": trace.get("claims") or []}


def risk_label(snapshot: dict[str, Any]) -> tuple[str, str]:
    hold = any(r.get("result") in {"보류", "불합격"} for r in snapshot["quality"])
    pending = any(r.get("approval") == "미승인" for r in snapshot["shipments"])
    score = int(hold) * 2 + int(pending) + len(snapshot["claims"])
    return ("높음", "🔴") if score >= 3 else (("주의", "🟠") if score else ("안정", "🟢"))

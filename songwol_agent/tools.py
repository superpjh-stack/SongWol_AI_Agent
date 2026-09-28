from __future__ import annotations

import json
from typing import Any, Callable

from .data_hub import SongwolRepository


def nullable_string(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


class SongwolToolRegistry:
    """RAG Agent가 사용할 수 있는 읽기 전용 제조 조회 도구."""

    def __init__(self, repository: SongwolRepository) -> None:
        self.repository = repository
        self._handlers: dict[str, Callable[..., Any]] = {
            "get_orders": repository.get_orders,
            "get_production": repository.get_production,
            "trace_lot": repository.trace_lot,
            "get_quality_issues": repository.get_quality_issues,
            "get_inventory": repository.get_inventory,
            "get_shipments": repository.get_shipments,
            "get_claims": repository.get_claims,
            "get_item_master": repository.get_item_master,
        }
        self.definitions = [
            self._tool("get_orders", "수주·고객·품목·수량·납기·진행상태를 조회한다.", {
                "order_no": nullable_string("주문번호. 전체면 null"),
                "status": nullable_string("상태 필터. 전체면 null"),
            }),
            self._tool("get_production", "작업지시·원단 LOT·인쇄 LOT·양품·불량·작업시간을 조회한다.", {
                "order_no": nullable_string("주문번호. 전체면 null"),
                "print_lot": nullable_string("인쇄 LOT. 전체면 null"),
            }),
            self._tool("trace_lot", "인쇄 LOT를 주문·원단·공정조건·품질·재고·출하·클레임까지 추적한다.", {
                "print_lot": {"type": "string", "description": "인쇄 LOT"},
            }),
            self._tool("get_quality_issues", "ΔE·흡수율·강도·외관 검사 중 조건부합격·보류 건을 조회한다.", {
                "print_lot": nullable_string("인쇄 LOT. 전체면 null"),
            }),
            self._tool("get_inventory", "원단·완제품 LOT별 재고 위치와 안전재고 이슈를 조회한다.", {
                "item_code": nullable_string("품목코드. 전체면 null"),
                "issues_only": {"type": "boolean", "description": "안전재고 미달만 조회할지 여부"},
            }),
            self._tool("get_shipments", "주문별 출하예정·상태·품질 승인 여부를 조회한다.", {
                "order_no": nullable_string("주문번호. 전체면 null"),
                "pending_only": {"type": "boolean", "description": "미승인 출하만 조회할지 여부"},
            }),
            self._tool("get_claims", "색상·포장 등 클레임과 조치상태를 조회한다.", {
                "claim_no": nullable_string("클레임 번호. 전체면 null"),
                "open_only": {"type": "boolean", "description": "미종결 건만 조회할지 여부"},
            }),
            self._tool("get_item_master", "품목명·타월유형·색상·인쇄방식·포장단위·규격버전을 조회한다.", {
                "item_code": nullable_string("품목코드. 전체면 null"),
            }),
        ]

    @staticmethod
    def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
            "strict": True,
        }

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        if name not in self._handlers:
            return json.dumps({"error": "허용되지 않은 도구입니다.", "tool": name}, ensure_ascii=False)
        try:
            payload = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = self._handlers[name](**payload)
            return json.dumps({"status": "ok", "demo_data": True, "result": result}, ensure_ascii=False, default=str)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc), "tool": name}, ensure_ascii=False)

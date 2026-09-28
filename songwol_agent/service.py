from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .citations import extract_evidence, extract_sources
from .prompts import AGENT_INSTRUCTIONS
from .tools import SongwolToolRegistry


@dataclass(frozen=True)
class AgentAnswer:
    text: str
    sources: list[str]
    evidence: list[dict[str, Any]]
    data_tools: list[str]
    response_id: str | None


class RagAgent:
    def __init__(self, client: Any, model: str = "gpt-5.6", data_tools: SongwolToolRegistry | None = None) -> None:
        self.client = client
        self.model = model
        self.data_tools = data_tools

    def create_knowledge_base(self, name: str = "송월타월 제조 지식베이스") -> str:
        return self.client.vector_stores.create(name=name).id

    def add_file(self, vector_store_id: str, file_path: str | Path) -> Any:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open("rb") as handle:
            return self.client.vector_stores.files.upload_and_poll(vector_store_id=vector_store_id, file=handle)

    def ask(self, question: str, vector_store_id: str | None = None, previous_response_id: str | None = None, max_results: int = 6) -> AgentAnswer:
        if not question.strip():
            raise ValueError("질문을 입력해 주세요.")
        tools: list[dict[str, Any]] = []
        include: list[str] = []
        if self.data_tools:
            tools.extend(self.data_tools.definitions)
        if vector_store_id:
            tools.append({"type": "file_search", "vector_store_ids": [vector_store_id], "max_num_results": max_results})
            include.append("file_search_call.results")
        if not tools:
            raise ValueError("제조 Data Hub 또는 지식문서를 연결해 주세요.")
        request: dict[str, Any] = {
            "model": self.model,
            "instructions": AGENT_INSTRUCTIONS,
            "input": question.strip(),
            "tools": tools,
            "parallel_tool_calls": False,
        }
        if previous_response_id:
            request["previous_response_id"] = previous_response_id
        if include:
            request["include"] = include
        response = self.client.responses.create(**request)
        used: list[str] = []
        for _ in range(4):
            calls = [item for item in getattr(response, "output", []) if getattr(item, "type", None) == "function_call"]
            if not calls:
                break
            outputs = []
            for call in calls:
                used.append(call.name)
                output = self.data_tools.execute(call.name, call.arguments) if self.data_tools else '{"error":"Data Hub not connected"}'
                outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": output})
            follow_up: dict[str, Any] = {
                "model": self.model,
                "instructions": AGENT_INSTRUCTIONS,
                "previous_response_id": response.id,
                "input": outputs,
                "tools": tools,
                "parallel_tool_calls": False,
            }
            if include:
                follow_up["include"] = include
            response = self.client.responses.create(**follow_up)
        return AgentAnswer(
            text=response.output_text,
            sources=extract_sources(response),
            evidence=extract_evidence(response),
            data_tools=list(dict.fromkeys(used)),
            response_id=getattr(response, "id", None),
        )

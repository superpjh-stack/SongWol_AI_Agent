from types import SimpleNamespace

import pytest

from songwol_agent import RagAgent


class FakeResponses:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(type="function_call", name="trace_lot", arguments='{"print_lot":"PRT-260903-C"}', call_id="call-1")
            return SimpleNamespace(id="resp-1", output=[call], output_text="")
        return SimpleNamespace(id="resp-2", output=[], output_text="품질 보류 LOT입니다.")


class FakeRegistry:
    definitions = [{"type": "function", "name": "trace_lot", "description": "test", "parameters": {"type": "object", "properties": {}}}]

    def execute(self, name, arguments):
        return '{"status":"ok","demo_data":true}'


def test_agent_executes_function_call_and_returns_grounding():
    responses = FakeResponses()
    answer = RagAgent(SimpleNamespace(responses=responses), data_tools=FakeRegistry()).ask("LOT 상태는?")
    assert answer.text == "품질 보류 LOT입니다."
    assert answer.data_tools == ["trace_lot"]
    assert responses.requests[1]["input"][0]["call_id"] == "call-1"


def test_agent_requires_a_question():
    with pytest.raises(ValueError):
        RagAgent(SimpleNamespace(responses=FakeResponses()), data_tools=FakeRegistry()).ask(" ")

import json
import pytest
from v2.compound import context_lot, tables
from v2.domain import Registry


def test_followup_uses_user_lot_not_assistant_guess():
    history = [{'role': 'user', 'text': 'PRT-260901-A 조회'}, {'role': 'assistant', 'text': 'PRT-260903-C'}]
    assert context_lot('그 LOT 출하는?', None, history) == ('PRT-260901-A', None)
    assert context_lot('그 LOT 출하는?', None, [history[1]])[1]
    with pytest.raises(ValueError):
        context_lot('PRT-260903-C 조회', 'PRT-260901-A', history)


def test_tables_preserve_zero_and_missing_and_exclude_documents():
    evidence = [{'title': 'inventory', 'kind': 'record', 'result': [{'qty': 0}, {'qty': None}]}, {'title': 'doc', 'kind': 'document', 'result': [{'body': 'sample'}]}]
    assert tables(evidence) == [{'title': 'inventory', 'columns': ['qty'], 'rows': [['0'], ['미확인']]}]


def test_mes_document_does_not_claim_mes_provenance(monkeypatch):
    from songwol_agent.tools import SongwolToolRegistry
    monkeypatch.setattr(SongwolToolRegistry, 'execute', lambda *a: json.dumps({'result': [{'body': 'sample'}]}))
    registry = Registry.__new__(Registry)
    registry.repository = type('Repo', (), {'is_mes_data': True})()
    registry.evidence = []
    result = json.loads(registry.execute('search_documents', {'query': '인쇄'}))
    assert result['demo_data'] is True
    assert '샘플' in result['source']
    assert json.loads(registry.execute('get_mes_inventory', {}))['demo_data'] is False

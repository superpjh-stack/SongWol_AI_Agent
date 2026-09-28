import json

from songwol_agent import SongwolRepository, SongwolToolRegistry


def test_summary_and_lot_trace(tmp_path):
    repo = SongwolRepository(tmp_path / "demo.db")
    summary = repo.summary()
    assert summary == {"open_orders": 3, "quality_holds": 1, "stock_issues": 1, "shipment_pending": 2}
    trace = repo.trace_lot("PRT-260903-C")
    assert trace["work_order"][0]["fabric_lot"] == "FAB-260830-C"
    assert trace["quality"][0]["result"] == "보류"
    assert trace["shipment"][0]["approval"] == "미승인"


def test_quality_inventory_and_claim_queries(tmp_path):
    repo = SongwolRepository(tmp_path / "demo.db")
    assert len(repo.get_quality_issues()) == 2
    assert repo.get_inventory(issues_only=True)[0]["stock_status"] == "안전재고 미달"
    assert repo.get_claims(open_only=True)[0]["status"] == "조치중"


def test_tool_registry_is_strict_and_read_only(tmp_path):
    registry = SongwolToolRegistry(SongwolRepository(tmp_path / "demo.db"))
    assert len(registry.definitions) == 8
    for tool in registry.definitions:
        assert tool["strict"] is True
        assert tool["parameters"]["required"] == list(tool["parameters"]["properties"])
        assert not tool["name"].startswith(("create_", "update_", "delete_"))
    blocked = json.loads(registry.execute("update_inventory", "{}"))
    assert "허용되지 않은" in blocked["error"]

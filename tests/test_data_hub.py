import json

from songwol_agent import SongwolRepository, SongwolToolRegistry


def test_summary_and_lot_trace(tmp_path):
    repo = SongwolRepository(tmp_path / "demo.db")
    summary = repo.summary()
    assert summary == {"open_orders": 9, "quality_holds": 2, "stock_issues": 2, "shipment_pending": 8}
    trace = repo.trace_lot("PRT-260903-C")
    assert trace["work_order"][0]["fabric_lot"] == "FAB-260830-C"
    assert trace["quality"][0]["result"] == "보류"
    assert trace["shipment"][0]["approval"] == "미승인"


def test_quality_inventory_and_claim_queries(tmp_path):
    repo = SongwolRepository(tmp_path / "demo.db")
    assert len(repo.get_quality_issues()) == 5
    assert repo.get_inventory(issues_only=True)[0]["stock_status"] == "안전재고 미달"
    assert len(repo.get_claims(open_only=True)) == 7


def test_tool_registry_is_strict_and_read_only(tmp_path):
    registry = SongwolToolRegistry(SongwolRepository(tmp_path / "demo.db"))
    assert len(registry.definitions) == 8
    for tool in registry.definitions:
        assert tool["strict"] is True
        assert tool["parameters"]["required"] == list(tool["parameters"]["properties"])
        assert not tool["name"].startswith(("create_", "update_", "delete_"))
    blocked = json.loads(registry.execute("update_inventory", "{}"))
    assert "허용되지 않은" in blocked["error"]


def test_seed_expands_each_table_to_ten_rows_without_duplicates(tmp_path):
    repo = SongwolRepository(tmp_path / "demo.db")
    tables = ("orders", "work_orders", "lot_quality", "process_conditions", "inventory", "shipments", "claims", "master_items")
    assert {table: len(repo._query(f"SELECT * FROM {table}")) for table in tables} == {table: 10 for table in tables}
    with repo._connect() as connection:
        repo._seed(connection)
    assert {table: len(repo._query(f"SELECT * FROM {table}")) for table in tables} == {table: 10 for table in tables}

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class SongwolRepository:
    """송월타월 RAG 검증용 읽기 전용 데이터 소스. 저장 레코드는 모두 가상 데모다."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS orders (
          order_no TEXT PRIMARY KEY, customer TEXT, item_code TEXT, item_name TEXT,
          order_qty INTEGER, due_date TEXT, status TEXT, priority TEXT
        );
        CREATE TABLE IF NOT EXISTS work_orders (
          work_order TEXT PRIMARY KEY, order_no TEXT, process TEXT, print_method TEXT,
          fabric_lot TEXT, print_lot TEXT, planned_qty INTEGER, good_qty INTEGER,
          defect_qty INTEGER, started_at TEXT, ended_at TEXT, status TEXT
        );
        CREATE TABLE IF NOT EXISTS lot_quality (
          inspection_id TEXT PRIMARY KEY, print_lot TEXT, inspected_at TEXT,
          delta_e REAL, absorbency_sec REAL, strength_n REAL, appearance TEXT,
          result TEXT, inspector TEXT, standard_revision TEXT
        );
        CREATE TABLE IF NOT EXISTS process_conditions (
          reading_id TEXT PRIMARY KEY, print_lot TEXT, measured_at TEXT,
          temperature_c REAL, pressure_bar REAL, ink_amount_g REAL,
          line_speed_m_min REAL, source TEXT
        );
        CREATE TABLE IF NOT EXISTS inventory (
          location TEXT, item_code TEXT, item_name TEXT, fabric_lot TEXT,
          quantity INTEGER, safety_stock INTEGER, unit TEXT, last_counted_at TEXT,
          stock_status TEXT
        );
        CREATE TABLE IF NOT EXISTS shipments (
          shipment_no TEXT PRIMARY KEY, order_no TEXT, planned_date TEXT,
          actual_date TEXT, carrier TEXT, status TEXT, approval TEXT
        );
        CREATE TABLE IF NOT EXISTS claims (
          claim_no TEXT PRIMARY KEY, order_no TEXT, print_lot TEXT, received_at TEXT,
          category TEXT, description TEXT, status TEXT, action TEXT
        );
        CREATE TABLE IF NOT EXISTS master_items (
          item_code TEXT PRIMARY KEY, item_name TEXT, towel_type TEXT, color TEXT,
          print_method TEXT, pack_unit INTEGER, active TEXT, spec_revision TEXT
        );
        """
        with self._connect() as connection:
            connection.executescript(schema)
            if connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
                self._seed(connection)

    @staticmethod
    def _seed(connection: sqlite3.Connection) -> None:
        connection.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", [
            ("SO-260901", "A호텔", "TW-170-WH", "170g 호텔타월 화이트", 3000, "2026-09-08", "포장중", "긴급"),
            ("SO-260902", "B스포츠", "TW-150-BL", "150g 스포츠타월 블루", 1800, "2026-09-10", "인쇄완료", "일반"),
            ("SO-260903", "C행사기획", "TW-130-NV", "130g 판촉타월 네이비", 5000, "2026-09-12", "인쇄중", "긴급"),
        ])
        connection.executemany("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("WO-260901", "SO-260901", "나염인쇄", "나염", "FAB-260825-A", "PRT-260901-A", 3000, 2875, 75, "2026-09-01 08:20", "2026-09-02 16:40", "포장인계"),
            ("WO-260902", "SO-260902", "승화인쇄", "승화", "FAB-260828-B", "PRT-260902-B", 1800, 1770, 30, "2026-09-02 09:10", "2026-09-03 14:20", "검사완료"),
            ("WO-260903", "SO-260903", "나염인쇄", "나염", "FAB-260830-C", "PRT-260903-C", 5000, 2180, 140, "2026-09-03 07:50", None, "진행"),
        ])
        connection.executemany("INSERT INTO lot_quality VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("QI-260901", "PRT-260901-A", "2026-09-02 15:20", 1.8, 3.2, 218, "양호", "합격", "김품질", "QC-PRINT-R3"),
            ("QI-260902", "PRT-260902-B", "2026-09-03 13:50", 2.6, 3.5, 205, "경미한 번짐", "조건부합격", "김품질", "QC-PRINT-R3"),
            ("QI-260903", "PRT-260903-C", "2026-09-03 12:10", 4.7, 4.3, 197, "색상 편차", "보류", "이검사", "QC-PRINT-R3"),
        ])
        connection.executemany("INSERT INTO process_conditions VALUES (?,?,?,?,?,?,?,?)", [
            ("PC-260901", "PRT-260901-A", "2026-09-01 10:00", 178, 2.1, 34, 18.0, "작업자입력"),
            ("PC-260902", "PRT-260902-B", "2026-09-02 11:20", 191, 2.4, 29, 17.5, "설비CSV"),
            ("PC-260903", "PRT-260903-C", "2026-09-03 11:50", 184, 2.0, 38, 20.5, "작업자입력"),
        ])
        connection.executemany("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?,?)", [
            ("R-A01", "RAW-170-WH", "170g 백색 원단타월", "FAB-260825-A", 4200, 2500, "EA", "2026-09-03 18:00", "정상"),
            ("R-B03", "RAW-150-WH", "150g 백색 원단타월", "FAB-260828-B", 900, 1500, "EA", "2026-09-03 18:00", "안전재고 미달"),
            ("P-C07", "TW-170-WH", "170g 호텔타월 화이트", "PRT-260901-A", 2875, 500, "EA", "2026-09-03 18:00", "포장대기"),
            ("P-D02", "TW-150-BL", "150g 스포츠타월 블루", "PRT-260902-B", 1770, 300, "EA", "2026-09-03 18:00", "출하대기"),
        ])
        connection.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?)", [
            ("SH-260901", "SO-260901", "2026-09-07", None, "한길물류", "포장대기", "미승인"),
            ("SH-260902", "SO-260902", "2026-09-09", None, "빠른택배", "출하대기", "품질 승인"),
            ("SH-260903", "SO-260903", "2026-09-11", None, "한길물류", "품질보류", "미승인"),
        ])
        connection.executemany("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?)", [
            ("CL-26017", "SO-260881", "PRT-260820-D", "2026-08-28", "색상", "승인 시안 대비 색상이 밝음", "조치중", "원단 LOT·인쇄조건·승인시안 비교"),
            ("CL-26018", "SO-260887", "PRT-260823-E", "2026-08-30", "포장", "박스 라벨 수량 불일치", "종결", "포장 스캔 이중 확인 적용"),
        ])
        connection.executemany("INSERT INTO master_items VALUES (?,?,?,?,?,?,?,?)", [
            ("TW-170-WH", "170g 호텔타월 화이트", "호텔타월", "화이트", "나염", 50, "Y", "ITEM-R4"),
            ("TW-150-BL", "150g 스포츠타월 블루", "스포츠타월", "블루", "승화", 30, "Y", "ITEM-R2"),
            ("TW-130-NV", "130g 판촉타월 네이비", "판촉타월", "네이비", "나염", 100, "Y", "ITEM-R5"),
        ])

    @staticmethod
    def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        return [dict(row) for row in cursor.fetchall()]

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return self._rows(connection.execute(sql, params))

    def summary(self) -> dict[str, int]:
        with self._connect() as connection:
            return {
                "open_orders": connection.execute("SELECT COUNT(*) FROM orders WHERE status != '완료'").fetchone()[0],
                "quality_holds": connection.execute("SELECT COUNT(*) FROM lot_quality WHERE result = '보류'").fetchone()[0],
                "stock_issues": connection.execute("SELECT COUNT(*) FROM inventory WHERE stock_status = '안전재고 미달'").fetchone()[0],
                "shipment_pending": connection.execute("SELECT COUNT(*) FROM shipments WHERE approval = '미승인'").fetchone()[0],
            }

    def get_orders(self, order_no: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        sql, clauses, params = "SELECT * FROM orders", [], []
        if order_no:
            clauses.append("order_no = ?")
            params.append(order_no)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._query(sql + " ORDER BY due_date", tuple(params))

    def get_production(self, order_no: str | None = None, print_lot: str | None = None) -> list[dict[str, Any]]:
        sql, clauses, params = "SELECT * FROM work_orders", [], []
        if order_no:
            clauses.append("order_no = ?")
            params.append(order_no)
        if print_lot:
            clauses.append("print_lot = ?")
            params.append(print_lot)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._query(sql + " ORDER BY started_at DESC", tuple(params))

    def trace_lot(self, print_lot: str) -> dict[str, Any]:
        jobs = self.get_production(print_lot=print_lot)
        if not jobs:
            return {"message": "인쇄 LOT를 찾지 못했습니다.", "print_lot": print_lot}
        order_no = jobs[0]["order_no"]
        return {
            "work_order": jobs,
            "order": self.get_orders(order_no=order_no),
            "quality": self._query("SELECT * FROM lot_quality WHERE print_lot = ?", (print_lot,)),
            "conditions": self._query("SELECT * FROM process_conditions WHERE print_lot = ?", (print_lot,)),
            "inventory": self._query("SELECT * FROM inventory WHERE fabric_lot IN (?, ?)", (print_lot, jobs[0]["fabric_lot"])),
            "shipment": self._query("SELECT * FROM shipments WHERE order_no = ?", (order_no,)),
            "claims": self._query("SELECT * FROM claims WHERE print_lot = ? OR order_no = ?", (print_lot, order_no)),
        }

    def get_quality_issues(self, print_lot: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM lot_quality WHERE result != '합격'"
        params: tuple[Any, ...] = ()
        if print_lot:
            sql += " AND print_lot = ?"
            params = (print_lot,)
        return self._query(sql + " ORDER BY inspected_at DESC", params)

    def get_inventory(self, item_code: str | None = None, issues_only: bool = False) -> list[dict[str, Any]]:
        sql, clauses, params = "SELECT * FROM inventory", [], []
        if item_code:
            clauses.append("item_code = ?")
            params.append(item_code)
        if issues_only:
            clauses.append("stock_status = '안전재고 미달'")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._query(sql + " ORDER BY item_code, fabric_lot", tuple(params))

    def get_shipments(self, order_no: str | None = None, pending_only: bool = False) -> list[dict[str, Any]]:
        sql, clauses, params = "SELECT * FROM shipments", [], []
        if order_no:
            clauses.append("order_no = ?")
            params.append(order_no)
        if pending_only:
            clauses.append("approval = '미승인'")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._query(sql + " ORDER BY planned_date", tuple(params))

    def get_claims(self, claim_no: str | None = None, open_only: bool = False) -> list[dict[str, Any]]:
        sql, clauses, params = "SELECT * FROM claims", [], []
        if claim_no:
            clauses.append("claim_no = ?")
            params.append(claim_no)
        if open_only:
            clauses.append("status != '종결'")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._query(sql + " ORDER BY received_at DESC", tuple(params))

    def get_item_master(self, item_code: str | None = None) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM master_items" + (" WHERE item_code = ?" if item_code else "") + " ORDER BY item_code", (item_code,) if item_code else ())

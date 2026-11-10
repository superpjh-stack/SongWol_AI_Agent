"""Import selected Songwol MES workbook grids into a local, read-only SQLite DB.

The importer deliberately uses only the XLSX ZIP/XML format so the source workbook
does not need to be copied into the repository or require a spreadsheet runtime.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

SHEET_MAP: dict[str, tuple[str, int, list[str]]] = {
    "거래처관리": ("mes_customers", 1, ["사용", "거래처코드", "거래처명", "구분", "매입", "매출"]),
    "품목마스터관리": ("mes_items", 1, ["사용", "제품구분", "제품코드", "품명 및 규격", "단위", "적정재고", "용도", "사이즈"]),
    "수주관리": ("mes_orders", 1, ["수주번호", "주문일자", "담당자", "업체구분", "거래처", "문구", "작업", "품명/색상", "수량", "총금액", "출고예정일", "배송", "케이스", "서비스"]),
    "수주대비출고현황": ("mes_shipments", 1, ["수주일자", "수주번호", "품명", "수주수량", "출고수량", "수주잔량"]),
    "미출고현황": ("mes_shipments", 1, ["수주일자", "수주번호", "품명", "수주수량", "출고수량", "수주잔량"]),
    "재고관리": ("mes_inventory", 1, ["품번", "품명 및 규격", "단위", "이월재고", "입고", "출고", "정산", "현재고", "금액"]),
    "작업지시서관리": ("mes_work_orders", 2, ["작업지시번호", "주문일자", "작업지시일", "거래처", "업체구분", "작업", "문구", "수량"]),
    "작업공정Tracking": ("mes_process_tracking", 1, ["작업지시번호", "완료", "일자", "품명/색상", "품명 및 규격", "지시수량", "생산완료", "포장완료"]),
    "생산실적": ("mes_production_results", 1, ["생산번호", "품명 및 규격", "생산량"]),
    "자재현장투입": ("mes_material_issues", 1, ["수주번호", "주문일자", "담당자", "업체구분", "거래처", "문구", "작업", "품명/색상", "수량", "출고예정일", "배송", "케이스", "서비스"]),
    "생산작업": ("mes_production_work", 1, ["수주번호", "주문일자", "담당자", "업체구분", "거래처", "문구", "작업", "품명/색상", "수량", "출고예정일", "배송", "케이스", "서비스"]),
    "포장작업": ("mes_packing", 1, ["수주번호", "주문일자", "담당자", "업체구분", "거래처", "문구", "작업", "품명/색상", "수량", "출고예정일", "배송", "케이스", "서비스"]),
    "KPI지표관리": ("mes_kpi", 2, ["NO", "분야", "성과지표", "단위", "구축전", "구축후", "변화량", "비중"]),
    "수주현황": ("mes_customer_summary", 1, ["거래처코드", "거래처", "수주량", "매출액"]),
    "출고현황": ("mes_shipping_summary", 1, ["품명 및 규격", "출고량"]),
}

SENSITIVE = {"주소", "사업자번호", "대표자", "전화번호", "휴대폰번호", "팩스번호", "이메일", "IP", "권한명", "관리자여부"}


def _column_number(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value - 1


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", NS)).strip()
    value = cell.find("a:v", NS)
    raw = "" if value is None else value.text or ""
    if kind == "s" and raw.isdigit() and int(raw) < len(shared):
        return shared[int(raw)]
    return raw.strip()


def read_workbook(path: str | Path) -> dict[str, list[list[str]]]:
    """Return non-empty worksheet rows as plain strings."""
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in si.iter("{%s}t" % NS["a"])) for si in root.findall("a:si", NS)]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        result: dict[str, list[list[str]]] = {}
        for sheet in workbook.findall("a:sheets/a:sheet", NS):
            name = sheet.attrib["name"]
            target = relmap[sheet.attrib["{%s}id" % NS["r"]]]
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(archive.read(target))
            rows: list[list[str]] = []
            for row in root.findall(".//a:sheetData/a:row", NS):
                values: list[str] = []
                for cell in row.findall("a:c", NS):
                    index = _column_number(cell.attrib.get("r", "A1"))
                    while len(values) <= index:
                        values.append("")
                    values[index] = _cell_value(cell, shared)
                if any(value for value in values):
                    rows.append(values)
            result[name] = rows
        return result


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


def _number(value: str) -> float | int | None:
    value = value.replace(",", "").strip()
    if not value:
        return None
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return None


def _row_to_dict(headers: list[str], values: list[str]) -> dict[str, Any]:
    return {header: _clean(values[index] if index < len(values) else "") for index, header in enumerate(headers) if header}


def _safe_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in SENSITIVE}


def _table_sql(table: str) -> str:
    return f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT NOT NULL, source_row INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(source_sheet, source_row))"


def _create_schema(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS mes_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS mes_source_rows (id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT NOT NULL, source_row INTEGER NOT NULL, table_name TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(source_sheet, source_row, table_name))")
    for table, _, _ in SHEET_MAP.values():
        db.execute(_table_sql(table))


def import_mes(workbook_path: str | Path, db_path: str | Path, replace: bool = True) -> dict[str, Any]:
    workbook_path = Path(workbook_path).expanduser().resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(f"MES 원본 파일을 찾지 못했습니다: {workbook_path}")
    sheets = read_workbook(workbook_path)
    db_path = Path(db_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"workbook": workbook_path.name, "db": str(db_path), "sheets": {}, "errors": []}
    with sqlite3.connect(db_path) as db:
        _create_schema(db)
        if replace:
            for table in {table for table, _, _ in SHEET_MAP.values()} | {"mes_source_rows"}:
                db.execute(f"DELETE FROM {table}")
        for sheet_name, (table, header_row, wanted) in SHEET_MAP.items():
            rows = sheets.get(sheet_name)
            if rows is None:
                report["sheets"][sheet_name] = {"table": table, "rows": 0, "missing": True}
                continue
            if len(rows) < header_row:
                report["sheets"][sheet_name] = {"table": table, "rows": 0, "error": "헤더 행 없음"}
                continue
            headers = rows[header_row - 1]
            loaded = excluded = 0
            for source_row, values in enumerate(rows[header_row:], header_row + 1):
                row = _row_to_dict(headers, values)
                if not any(row.get(column) for column in wanted):
                    excluded += 1
                    continue
                safe = _safe_payload({column: row.get(column) for column in wanted})
                db.execute(f"INSERT OR REPLACE INTO {table}(id, source_sheet, source_row, payload) VALUES ((SELECT id FROM {table} WHERE source_sheet=? AND source_row=?), ?, ?, ?)", (sheet_name, source_row, sheet_name, source_row, json.dumps(safe, ensure_ascii=False)))
                db.execute("INSERT OR REPLACE INTO mes_source_rows(id, source_sheet, source_row, table_name, payload) VALUES ((SELECT id FROM mes_source_rows WHERE source_sheet=? AND source_row=? AND table_name=?), ?, ?, ?, ?)", (sheet_name, source_row, table, sheet_name, source_row, table, json.dumps(safe, ensure_ascii=False)))
                loaded += 1
            report["sheets"][sheet_name] = {"table": table, "rows": loaded, "excluded": excluded}
        meta = {
            "demo_data": "false", "source": workbook_path.name, "as_of": "2026-10-28",
            "approval": "원본 조회 데이터·자동 승인 아님", "imported_at": datetime.now().isoformat(timespec="seconds"),
        }
        db.executemany("INSERT OR REPLACE INTO mes_meta(key, value) VALUES (?, ?)", meta.items())
        db.commit()
    report["total_rows"] = sum(item.get("rows", 0) for item in report["sheets"].values())
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="송월타월 MES XLSX를 읽기 전용 SQLite DB로 import")
    parser.add_argument("workbook")
    parser.add_argument("--db", default="data/songwol_mes.db")
    parser.add_argument("--append", action="store_true", help="기존 적재를 지우지 않음")
    args = parser.parse_args()
    print(json.dumps(import_mes(args.workbook, args.db, replace=not args.append), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

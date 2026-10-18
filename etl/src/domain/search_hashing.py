from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Sequence

from .models import CellValue


def canonical_cell(cell: CellValue) -> dict[str, Any]:
    value = cell.value
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, (float, Decimal)):
        decimal_value = Decimal(str(value))
        rendered = format(decimal_value, "f")
        return {"type": "decimal", "value": rendered}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat(sep=" ")}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"type": "time", "value": value.isoformat()}
    return {"type": type(value).__name__, "value": str(value)}


def canonical_raw_payload(headers: Sequence[str], cells: Sequence[CellValue]) -> str:
    fields = [
        {
            "position": position,
            "name": header,
            "cell": canonical_cell(cells[position - 1] if position <= len(cells) else CellValue(None)),
        }
        for position, header in enumerate(headers, start=1)
    ]
    return json.dumps(
        {"version": 1, "fields": fields},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def row_hash(raw_payload: str) -> str:
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


def record_hash(fields: Sequence[tuple[str, Any]]) -> str:
    canonical_fields = [
        {"position": position, "name": name, "value": _canonical_normalized(value)}
        for position, (name, value) in enumerate(fields, start=1)
    ]
    payload = json.dumps(
        {"version": 1, "fields": canonical_fields},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_normalized(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    return {"type": "string", "value": str(value)}

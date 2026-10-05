from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..domain.errors import StructuralFileError
from ..domain.normalizers import normalize_header

EXPECTED_COLUMNS = (
    "FECHA",
    "DOCUMENTO",
    "MONTO",
    "ACUMULADO",
    "RECAUDO",
    "OPERACION",
    "COMENTARIO",
    "HORA",
)
REQUIRED_COLUMNS = frozenset({"FECHA", "MONTO", "RECAUDO"})


def build_header_map(header_values: Sequence[Any]) -> dict[str, int]:
    header_map: dict[str, int] = {}
    duplicates: set[str] = set()

    for index, value in enumerate(header_values):
        header = normalize_header(value)
        if not header:
            continue
        if header in header_map:
            duplicates.add(header)
        header_map[header] = index

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise StructuralFileError(f"Encabezados duplicados: {duplicate_list}.")

    missing = REQUIRED_COLUMNS.difference(header_map)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise StructuralFileError(f"Faltan columnas obligatorias: {missing_list}.")

    return {column: header_map[column] for column in EXPECTED_COLUMNS if column in header_map}

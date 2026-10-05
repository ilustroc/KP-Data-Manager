from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from ..domain.errors import StructuralFileError
from ..domain.models import CellValue, SourceRow
from .base import EXPECTED_COLUMNS, build_header_map


class CsvPaymentParser:
    SAMPLE_LINES = 20
    SAMPLE_LINE_LIMIT = 8192

    def rows(self, path: Path) -> Iterator[SourceRow]:
        try:
            with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as handle:
                sample_parts: list[str] = []
                for _ in range(self.SAMPLE_LINES):
                    line = handle.readline(self.SAMPLE_LINE_LIMIT)
                    if line == "":
                        break
                    sample_parts.append(line)
                sample = "".join(sample_parts)
                handle.seek(0)

                if not sample:
                    raise StructuralFileError("El CSV está vacío.")
                delimiter = self._detect_delimiter(sample)
                reader = csv.reader(handle, delimiter=delimiter)
                try:
                    header_values = next(reader)
                except StopIteration as exception:
                    raise StructuralFileError("El CSV no contiene encabezados.") from exception
                header_map = build_header_map(header_values)

                for values in reader:
                    source_values = {
                        column: CellValue(values[index] if index < len(values) else None)
                        for column, index in header_map.items()
                    }
                    for optional_column in EXPECTED_COLUMNS:
                        source_values.setdefault(optional_column, CellValue(None))
                    if all(cell.value is None or str(cell.value).strip() == "" for cell in source_values.values()):
                        continue
                    yield SourceRow(number=reader.line_num, values=source_values)
        except UnicodeDecodeError as exception:
            raise StructuralFileError(
                f"El CSV no es UTF-8 válido cerca del byte {exception.start}."
            ) from exception
        except csv.Error as exception:
            raise StructuralFileError(f"CSV inválido: {exception}.") from exception

    @staticmethod
    def _detect_delimiter(sample: str) -> str:
        try:
            return csv.Sniffer().sniff(sample, delimiters=";,").delimiter
        except csv.Error as exception:
            raise StructuralFileError("No se pudo detectar el delimitador CSV ';' o ','.") from exception

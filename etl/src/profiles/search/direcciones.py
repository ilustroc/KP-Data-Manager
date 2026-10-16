from __future__ import annotations

import re
from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchAddressRecord, SearchRawRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, cell_to_text, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash

DOCUMENT_PATTERN = re.compile(r"^[0-9]{8}$")
ADDRESS_FIELDS = ("documento", "direccion", "departamento", "provincia", "distrito", "data_procedencia")
YEAR_PATTERN = re.compile(r"(?<![0-9])([0-9]{4})(?![0-9])")


def normalized_text(cell, maximum: int, field: str) -> str | None:
    value = cell_to_text(cell)
    if value is None:
        return None
    value = " ".join(value.split())
    if len(value) > maximum:
        raise FieldNormalizationError(f"{field} excede {maximum} caracteres")
    return value


class DireccionesV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchAddressRecord | None, list[RowError]]:
        if batch.dataset_code != "DIRECCIONES" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto DIRECCIONES completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        errors: list[RowError] = []
        normalized: dict[str, str | None] = {}
        rules = {
            "documento": self._document,
            "direccion": lambda cell: normalized_text(cell, 1000, "Dirección"),
            "departamento": lambda cell: normalized_text(cell, 150, "Departamento"),
            "provincia": lambda cell: normalized_text(cell, 150, "Provincia"),
            "distrito": lambda cell: normalized_text(cell, 150, "Distrito"),
            "data_procedencia": lambda cell: normalized_text(cell, 255, "Data procedencia"),
        }
        for field in ADDRESS_FIELDS:
            cell = row.mapped_values[field]
            try:
                normalized[field] = rules[field](cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), str(exception), ingested_at))
        if errors:
            return raw, None, errors
        if all(normalized[field] is None for field in ("direccion", "departamento", "provincia", "distrito")):
            return raw, None, []
        provenance = normalized["data_procedencia"]
        match = YEAR_PATTERN.search(provenance or "")
        year = int(match.group(1)) if match else None
        fields = tuple((field, normalized[field]) for field in ADDRESS_FIELDS) + (("procedencia_anio", year),)
        return raw, SearchAddressRecord(row.number, str(normalized["documento"]), normalized["direccion"], normalized["departamento"], normalized["provincia"], normalized["distrito"], provenance, year, batch.source_code, batch.batch_id, record_hash(fields), ingested_at), []

    @staticmethod
    def _document(cell) -> str:
        value = cell_to_text(cell)
        if value is None or DOCUMENT_PATTERN.fullmatch(value) is None:
            raise FieldNormalizationError("DOCUMENT_INVALID")
        return value

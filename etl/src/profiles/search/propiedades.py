from __future__ import annotations

import re
from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchPropertyRecord, SearchRawRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, cell_to_text, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash

DOCUMENT_PATTERN = re.compile(r"^[0-9]{8}$")
PROPERTY_FIELDS = ("documento", "partida_registral", "zona_registral", "oficina")


def normalized_text(cell, maximum: int, field: str, required: bool = False) -> str | None:
    value = cell_to_text(cell)
    if value is None:
        if required:
            raise FieldNormalizationError(f"{field} obligatorio")
        return None
    value = " ".join(value.split())
    if len(value) > maximum:
        raise FieldNormalizationError(f"{field} excede {maximum} caracteres")
    return value


class PropiedadesV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchPropertyRecord | None, list[RowError]]:
        if batch.dataset_code != "PROPIEDADES" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto PROPIEDADES completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        errors: list[RowError] = []
        normalized: dict[str, str | None] = {}
        rules = {
            "documento": self._document,
            "partida_registral": lambda cell: normalized_text(cell, 100, "Partida registral", True),
            "zona_registral": lambda cell: normalized_text(cell, 255, "Zona registral"),
            "oficina": lambda cell: normalized_text(cell, 150, "Oficina"),
        }
        for field in PROPERTY_FIELDS:
            cell = row.mapped_values[field]
            try:
                normalized[field] = rules[field](cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), "PROPERTY_INVALID" if field == "partida_registral" else str(exception), ingested_at))
        if errors:
            return raw, None, errors
        partida = str(normalized["partida_registral"]).upper()
        fields = (("documento", normalized["documento"]), ("partida_registral", partida), ("zona_registral", normalized["zona_registral"]), ("oficina", normalized["oficina"]))
        return raw, SearchPropertyRecord(row.number, str(normalized["documento"]), partida, normalized["zona_registral"], normalized["oficina"], batch.source_code, batch.batch_id, record_hash(fields), ingested_at), []

    @staticmethod
    def _document(cell) -> str:
        value = cell_to_text(cell)
        if value is None or DOCUMENT_PATTERN.fullmatch(value) is None:
            raise FieldNormalizationError("DOCUMENT_INVALID")
        return value

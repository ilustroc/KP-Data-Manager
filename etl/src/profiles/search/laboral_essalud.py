from __future__ import annotations

from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchEssaludRecord, SearchRawRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash
from .dmf5_normalizers import digits, document, optional_decimal, optional_text, period

ESSALUD_FIELDS = ("documento", "periodo", "ruc", "nombre_empresa", "sueldo", "situacion")


class LaboralEssaludV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchEssaludRecord | None, list[RowError]]:
        if batch.dataset_code != "LABORAL_ESSALUD" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto LABORAL_ESSALUD completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        rules = {"documento": document, "periodo": period, "ruc": lambda cell: digits(cell, 11, "RUC_INVALID"), "nombre_empresa": lambda cell: optional_text(cell, 255, "NOMBRE_EMPRESA"), "sueldo": lambda cell: optional_decimal(cell, "SALARY_INVALID"), "situacion": lambda cell: optional_text(cell, 20, "SITUACION", uppercase=True)}
        values: dict[str, object] = {}
        errors: list[RowError] = []
        for field in ESSALUD_FIELDS:
            cell = row.mapped_values[field]
            try:
                values[field] = rules[field](cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), str(exception), ingested_at))
        if errors:
            return raw, None, errors
        return raw, SearchEssaludRecord(row.number, values["documento"], values["periodo"], values["ruc"], values["nombre_empresa"], values["sueldo"], values["situacion"], batch.source_code, batch.batch_id, record_hash(tuple((field, values[field]) for field in ESSALUD_FIELDS)), ingested_at), []

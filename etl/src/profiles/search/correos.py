from __future__ import annotations

import re
from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchEmailRecord, SearchRawRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, cell_to_text, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash

DOCUMENT_PATTERN = re.compile(r"^[0-9]{8}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_FIELDS = ("documento", "correo_original")
PLACEHOLDER_EMAILS = frozenset({"sincorreo@sincorreo.com"})


class CorreosV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchEmailRecord | None, list[RowError]]:
        if batch.dataset_code != "CORREOS" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto CORREOS completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        errors: list[RowError] = []
        normalized: dict[str, str] = {}
        for field, rule in (("documento", self._document), ("correo_original", self._email)):
            cell = row.mapped_values[field]
            try:
                normalized[field] = rule(cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), str(exception), ingested_at))
        if errors:
            return raw, None, errors
        correo_original = normalized["correo_original"]
        correo = correo_original.lower()
        return raw, SearchEmailRecord(row.number, normalized["documento"], correo, correo_original, batch.source_code, batch.batch_id, record_hash((("documento", normalized["documento"]), ("correo", correo), ("correo_original", correo_original))), ingested_at), []

    @staticmethod
    def _document(cell) -> str:
        value = cell_to_text(cell)
        if value is None or DOCUMENT_PATTERN.fullmatch(value) is None:
            raise FieldNormalizationError("DOCUMENT_INVALID")
        return value

    @staticmethod
    def _email(cell) -> str:
        value = cell_to_text(cell)
        if value is None or len(value) > 254 or EMAIL_PATTERN.fullmatch(value) is None or value.lower() in PLACEHOLDER_EMAILS:
            raise FieldNormalizationError("EMAIL_INVALID")
        return value

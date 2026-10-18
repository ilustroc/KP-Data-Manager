from __future__ import annotations

from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchFamilyRecord, SearchRawRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, cell_to_text, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash

FAMILY_FIELDS = (
    "documento",
    "documento_familiar",
    "paterno_familiar",
    "materno_familiar",
    "nombres_familiar",
    "nacimiento_familiar",
    "tipo_familiar",
)


class FamiliaV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(
        self,
        row: SearchSourceRow,
        batch: BatchRecord,
        ingested_at: datetime,
    ) -> tuple[SearchRawRecord, SearchFamilyRecord | None, list[RowError]]:
        if batch.dataset_code != "FAMILIA" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto FAMILIA completo.")

        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(
            batch.batch_id,
            batch.dataset_code,
            batch.source_code,
            row.number,
            batch.archivo_original,
            payload,
            row_hash(payload),
            ingested_at,
        )
        values: dict[str, str | None] = {}
        errors: list[RowError] = []
        for field in FAMILY_FIELDS:
            cell = row.mapped_values[field]
            try:
                values[field] = self._source_text(cell, required=field == "documento")
            except FieldNormalizationError as exception:
                errors.append(
                    RowError(
                        batch.batch_id,
                        row.number,
                        field,
                        value_for_error(cell, self.error_value_max_length),
                        str(exception),
                        ingested_at,
                    )
                )

        if errors:
            return raw, None, errors

        fields = tuple((field, values[field]) for field in FAMILY_FIELDS)
        return raw, SearchFamilyRecord(
            source_row=row.number,
            documento=str(values["documento"]),
            documento_familiar=values["documento_familiar"],
            paterno_familiar=values["paterno_familiar"],
            materno_familiar=values["materno_familiar"],
            nombres_familiar=values["nombres_familiar"],
            nacimiento_familiar=values["nacimiento_familiar"],
            tipo_familiar=values["tipo_familiar"],
            source_code=batch.source_code,
            batch_id=batch.batch_id,
            record_hash=record_hash(fields),
            created_at=ingested_at,
        ), []

    @staticmethod
    def _source_text(cell, *, required: bool) -> str | None:
        value = cell_to_text(cell)
        if value is None and required:
            raise FieldNormalizationError("DOCUMENT_REQUIRED")
        return value

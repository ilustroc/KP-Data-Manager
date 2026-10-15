from __future__ import annotations

import re
from datetime import datetime

from ...domain.models import (
    BatchRecord,
    RowError,
    SearchPhoneRecord,
    SearchRawRecord,
    SearchSourceRow,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_optional_excel_date,
    value_for_error,
)
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash
from .operator_matcher import match_operator

DOCUMENT_PATTERN = re.compile(r"^[0-9]{8}$")
PHONE_PATTERN = re.compile(r"^9[0-9]{8}$")
BLOCKED_PHONES = frozenset({"900000000", "911111111"})
PHONE_FIELDS = ("documento", "telefono", "operador_raw", "fecha_data")
class TelefonosV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(
        self,
        row: SearchSourceRow,
        batch: BatchRecord,
        ingested_at: datetime,
    ) -> tuple[SearchRawRecord, SearchPhoneRecord | None, list[RowError]]:
        if batch.dataset_code != "TELEFONOS" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto TELEFONOS completo.")

        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(
            batch_id=batch.batch_id,
            dataset_code=batch.dataset_code,
            source_code=batch.source_code,
            source_row=row.number,
            source_file=batch.archivo_original,
            raw_payload=payload,
            row_hash=row_hash(payload),
            ingested_at=ingested_at,
        )
        errors: list[RowError] = []
        normalized: dict[str, object] = {}
        rules = {
            "documento": self._document,
            "telefono": self._phone,
            "operador_raw": self._operator,
            "fecha_data": self._date,
        }
        for field in PHONE_FIELDS:
            cell = row.mapped_values[field]
            try:
                normalized[field] = rules[field](cell)
            except (FieldNormalizationError, ValueError) as exception:
                errors.append(
                    RowError(
                        batch_id=batch.batch_id,
                        row_number=row.number,
                        field=field,
                        value=value_for_error(cell, self.error_value_max_length),
                        message=str(exception),
                        created_at=ingested_at,
                    )
                )

        if errors:
            return raw, None, errors

        operador_raw, operador = normalized["operador_raw"]
        hash_fields = (
            ("documento", normalized["documento"]),
            ("telefono", normalized["telefono"]),
            ("operador_raw", operador_raw),
            ("operador", operador),
            ("fecha_data", normalized["fecha_data"]),
        )
        phone = SearchPhoneRecord(
            source_row=row.number,
            documento=str(normalized["documento"]),
            telefono=str(normalized["telefono"]),
            operador=operador,
            operador_raw=operador_raw,
            fecha_data=normalized["fecha_data"],
            source_code=batch.source_code,
            batch_id=batch.batch_id,
            record_hash=record_hash(hash_fields),
            created_at=ingested_at,
        )
        return raw, phone, []

    @staticmethod
    def _document(cell) -> str:
        document = cell_to_text(cell)
        if document is None or DOCUMENT_PATTERN.fullmatch(document) is None:
            raise FieldNormalizationError("DOCUMENT_INVALID")
        return document

    @staticmethod
    def _phone(cell) -> str:
        phone = cell_to_text(cell)
        if (
            phone is None
            or PHONE_PATTERN.fullmatch(phone) is None
            or len(set(phone)) == 1
            or phone in BLOCKED_PHONES
        ):
            raise FieldNormalizationError("PHONE_INVALID")
        return phone

    @staticmethod
    def _operator(cell) -> tuple[str, str]:
        text = cell_to_text(cell)
        raw = " ".join(text.split()) if text is not None else ""
        uppercase = raw.upper()
        operator, error = match_operator(uppercase)
        if error is not None:
            raise FieldNormalizationError(error)
        return raw, str(operator)

    @staticmethod
    def _date(cell):
        if isinstance(cell.value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", cell.value.strip()) is None:
            raise FieldNormalizationError("DATE_INVALID")
        try:
            value = normalize_optional_excel_date(cell)
        except FieldNormalizationError as exception:
            raise FieldNormalizationError("DATE_INVALID") from exception
        if value is None:
            raise FieldNormalizationError("DATE_INVALID")
        return value

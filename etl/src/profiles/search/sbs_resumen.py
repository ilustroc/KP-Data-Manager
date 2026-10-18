from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ...domain.models import BatchRecord, RowError, SearchRawRecord, SearchSbsSummaryRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash
from .dmf5_normalizers import document, digits, nonnegative_integer, optional_decimal, period

SBS_SUMMARY_FIELDS = ("cod_sbs", "fecha_reporte_sbs", "documento", "cantidad_empresas", "calificacion_normal", "calificacion_cpp", "calificacion_deficiente", "calificacion_dudoso", "calificacion_perdida")


class SbsResumenV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchSbsSummaryRecord | None, list[RowError]]:
        if batch.dataset_code != "SBS_RESUMEN" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto SBS_RESUMEN completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        rules = {
            "cod_sbs": lambda cell: digits(cell, 10, "COD_SBS_INVALID"), "fecha_reporte_sbs": period,
            "documento": document, "cantidad_empresas": lambda cell: self._required_integer(cell),
            "calificacion_normal": lambda cell: optional_decimal(cell, "PERCENTAGE_INVALID", scale=Decimal("0.0001"), maximum=Decimal("100")),
            "calificacion_cpp": lambda cell: optional_decimal(cell, "PERCENTAGE_INVALID", scale=Decimal("0.0001"), maximum=Decimal("100")),
            "calificacion_deficiente": lambda cell: optional_decimal(cell, "PERCENTAGE_INVALID", scale=Decimal("0.0001"), maximum=Decimal("100")),
            "calificacion_dudoso": lambda cell: optional_decimal(cell, "PERCENTAGE_INVALID", scale=Decimal("0.0001"), maximum=Decimal("100")),
            "calificacion_perdida": lambda cell: optional_decimal(cell, "PERCENTAGE_INVALID", scale=Decimal("0.0001"), maximum=Decimal("100")),
        }
        normalized: dict[str, object] = {}
        errors: list[RowError] = []
        for field in SBS_SUMMARY_FIELDS:
            cell = row.mapped_values[field]
            try:
                normalized[field] = rules[field](cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), str(exception), ingested_at))
        percentages = [normalized.get(field) for field in SBS_SUMMARY_FIELDS[4:]]
        if not errors and all(value is not None for value in percentages):
            total = sum(percentages, Decimal("0"))
            if not Decimal("99.50") <= total <= Decimal("100.50"):
                errors.append(RowError(batch.batch_id, row.number, "calificaciones", str(total), "SBS_PERCENTAGE_TOTAL_INVALID", ingested_at))
        if errors:
            return raw, None, errors
        fields = tuple((field, normalized[field]) for field in SBS_SUMMARY_FIELDS)
        return raw, SearchSbsSummaryRecord(row.number, normalized["documento"], normalized["cod_sbs"], normalized["fecha_reporte_sbs"], normalized["cantidad_empresas"], normalized["calificacion_normal"], normalized["calificacion_cpp"], normalized["calificacion_deficiente"], normalized["calificacion_dudoso"], normalized["calificacion_perdida"], batch.source_code, batch.batch_id, record_hash(fields), ingested_at), []

    @staticmethod
    def _required_integer(cell) -> int:
        value = nonnegative_integer(cell, "COMPANY_COUNT_INVALID")
        if value is None:
            raise FieldNormalizationError("COMPANY_COUNT_INVALID")
        return value

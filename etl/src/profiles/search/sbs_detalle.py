from __future__ import annotations

from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchRawRecord, SearchSbsDetailRecord, SearchSourceRow
from ...domain.normalizers import FieldNormalizationError, cell_to_text, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash
from .dmf5_contract import conditions, shifted_detail_fields
from .dmf5_normalizers import document, digits, nonnegative_integer, optional_decimal, optional_text, period

SBS_DETAIL_FIELDS = ("fecha_reporte_sbs", "documento", "cod_sbs", "entidad", "tipo_credito", "condicion", "monto", "dias_atraso")


class SbsDetalleV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchSbsDetailRecord | None, list[RowError]]:
        if batch.dataset_code != "SBS_DETALLE" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto SBS_DETALLE completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        mapped = row.mapped_values
        shifted, shifted_ambiguous = self._shift(mapped)
        errors: list[RowError] = []
        if shifted_ambiguous:
            errors.append(RowError(batch.batch_id, row.number, "tipo_credito", value_for_error(mapped["tipo_credito"], self.error_value_max_length), "SBS_DETAIL_COLUMN_SHIFT_AMBIGUOUS", ingested_at))
            return raw, None, errors
        values: dict[str, object] = {}
        rules = {
            "fecha_reporte_sbs": period, "documento": document, "cod_sbs": lambda cell: digits(cell, 10, "COD_SBS_INVALID"),
            "entidad": lambda cell: optional_text(cell, 255, "ENTIDAD"), "tipo_credito": lambda cell: optional_text(cell, 500, "TIPO_CREDITO"),
            "condicion": self._condition, "monto": lambda cell: optional_decimal(cell, "AMOUNT_INVALID"),
            "dias_atraso": lambda cell: nonnegative_integer(cell, "DAYS_OVERDUE_INVALID"),
        }
        for field in SBS_DETAIL_FIELDS:
            cell = shifted.get(field, mapped[field])
            try:
                values[field] = rules[field](cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), str(exception), ingested_at))
        if errors:
            return raw, None, errors
        fields = tuple((field, values[field]) for field in SBS_DETAIL_FIELDS)
        record = SearchSbsDetailRecord(row.number, values["fecha_reporte_sbs"], values["documento"], values["cod_sbs"], values["entidad"], values["tipo_credito"], values["condicion"], values["monto"], values["dias_atraso"], batch.source_code, batch.batch_id, record_hash(fields), ingested_at)
        if shifted:
            return raw, record, [RowError(batch.batch_id, row.number, "tipo_credito", "", "SBS_DETAIL_SHIFTED_COLUMNS_RECOVERED", ingested_at)]
        return raw, record, []

    @staticmethod
    def _condition(cell) -> str | None:
        value = optional_text(cell, 8, "CONDICION", uppercase=True)
        if value is not None and value not in conditions():
            raise FieldNormalizationError("CONDITION_INVALID")
        return value

    @staticmethod
    def _shift(mapped):
        fields = shifted_detail_fields()
        code = cell_to_text(mapped["tipo_credito"])
        if code is None or code.upper() not in conditions():
            return {}, False
        original_condition = cell_to_text(mapped[fields["amount_from"].lower()])
        original_amount = cell_to_text(mapped[fields["days_from"].lower()])
        original_days = cell_to_text(mapped["dias_atraso"])
        try:
            amount = optional_decimal(mapped["condicion"], "AMOUNT_INVALID")
            days = nonnegative_integer(mapped["monto"], "DAYS_OVERDUE_INVALID")
        except FieldNormalizationError:
            return {}, True
        if amount is None or original_days is not None:
            return {}, True
        if original_amount is not None and days is None:
            return {}, True
        from ...domain.models import CellValue
        return {"tipo_credito": CellValue(None), "condicion": CellValue(code.upper()), "monto": CellValue(original_condition), "dias_atraso": CellValue(original_amount)}, False

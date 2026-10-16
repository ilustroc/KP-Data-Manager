from __future__ import annotations

import re
from datetime import datetime

from ...domain.models import BatchRecord, RowError, SearchRawRecord, SearchSourceRow, SearchVehicleRecord
from ...domain.normalizers import FieldNormalizationError, cell_to_text, normalize_year, value_for_error
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash

DOCUMENT_PATTERN = re.compile(r"^[0-9]{8}$")
VEHICLE_FIELDS = ("documento", "nombre_completo_fuente", "clase", "anio_compra", "anio_fabricacion", "marca", "placa_original", "numero_transferencias")


def normalized_text(cell, maximum: int, field: str) -> str | None:
    value = cell_to_text(cell)
    if value is None:
        return None
    value = " ".join(value.split())
    if len(value) > maximum:
        raise FieldNormalizationError(f"{field} excede {maximum} caracteres")
    return value


class VehiculosV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(self, row: SearchSourceRow, batch: BatchRecord, ingested_at: datetime) -> tuple[SearchRawRecord, SearchVehicleRecord | None, list[RowError]]:
        if batch.dataset_code != "VEHICULOS" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto VEHICULOS completo.")
        payload = canonical_raw_payload(row.headers, row.cells)
        raw = SearchRawRecord(batch.batch_id, batch.dataset_code, batch.source_code, row.number, batch.archivo_original, payload, row_hash(payload), ingested_at)
        errors: list[RowError] = []
        normalized: dict[str, object] = {}
        rules = {
            "documento": self._document,
            "nombre_completo_fuente": lambda cell: normalized_text(cell, 500, "Nombre completo"),
            "clase": lambda cell: normalized_text(cell, 100, "Clase"),
            "anio_compra": normalize_year,
            "anio_fabricacion": normalize_year,
            "marca": lambda cell: normalized_text(cell, 150, "Marca"),
            "placa_original": lambda cell: normalized_text(cell, 50, "Placa"),
            "numero_transferencias": self._transfers,
        }
        for field in VEHICLE_FIELDS:
            cell = row.mapped_values[field]
            try:
                normalized[field] = rules[field](cell)
            except FieldNormalizationError as exception:
                errors.append(RowError(batch.batch_id, row.number, field, value_for_error(cell, self.error_value_max_length), "YEAR_INVALID" if field.startswith("anio_") else str(exception), ingested_at))
        if errors:
            return raw, None, errors
        plate_original = normalized["placa_original"]
        plate = str(plate_original).upper() if plate_original is not None else None
        fields = tuple((field, normalized[field]) for field in VEHICLE_FIELDS) + (("placa", plate),)
        return raw, SearchVehicleRecord(row.number, str(normalized["documento"]), normalized["nombre_completo_fuente"], normalized["clase"], normalized["anio_compra"], normalized["anio_fabricacion"], normalized["marca"], plate, plate_original, normalized["numero_transferencias"], batch.source_code, batch.batch_id, record_hash(fields), ingested_at), []

    @staticmethod
    def _document(cell) -> str:
        value = cell_to_text(cell)
        if value is None or DOCUMENT_PATTERN.fullmatch(value) is None:
            raise FieldNormalizationError("DOCUMENT_INVALID")
        return value

    @staticmethod
    def _transfers(cell) -> int | None:
        value = cell_to_text(cell)
        if value is None:
            return None
        if re.fullmatch(r"[0-9]+", value) is None:
            raise FieldNormalizationError("TRANSFER_INVALID")
        return int(value)

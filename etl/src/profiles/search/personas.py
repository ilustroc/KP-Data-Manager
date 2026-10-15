from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ...domain.models import (
    BatchRecord,
    RowError,
    SearchPersonRecord,
    SearchRawRecord,
    SearchSourceRow,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_optional_excel_date,
    normalize_optional_text,
    value_for_error,
)
from ...domain.search_hashing import canonical_raw_payload, record_hash, row_hash

DNI_PATTERN = re.compile(r"^[0-9]{8}$")
PERSON_FIELDS = (
    "documento",
    "paterno",
    "materno",
    "nombres",
    "fecha_nacimiento",
    "direccion_origen",
    "sexo",
    "estado_civil",
    "padre",
    "madre",
)


class PersonasV1Normalizer:
    def __init__(self, error_value_max_length: int) -> None:
        self.error_value_max_length = error_value_max_length

    def normalize(
        self,
        row: SearchSourceRow,
        batch: BatchRecord,
        ingested_at: datetime,
    ) -> tuple[SearchRawRecord, SearchPersonRecord | None, list[RowError]]:
        if batch.dataset_code != "PERSONAS" or batch.source_code is None:
            raise ValueError("El batch no contiene contexto PERSONAS completo.")

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
        normalized: dict[str, Any] = {}
        errors: list[RowError] = []
        rules = {
            "documento": self._document,
            "paterno": lambda cell: normalize_optional_text(cell, 150, "Paterno"),
            "materno": lambda cell: normalize_optional_text(cell, 150, "Materno"),
            "nombres": lambda cell: normalize_optional_text(cell, 255, "Nombres"),
            "fecha_nacimiento": normalize_optional_excel_date,
            "direccion_origen": lambda cell: normalize_optional_text(cell, 65535, "Dirección"),
            "sexo": self._source_code,
            "estado_civil": lambda cell: normalize_optional_text(cell, 100, "Estado civil"),
            "padre": lambda cell: normalize_optional_text(cell, 500, "Padre"),
            "madre": lambda cell: normalize_optional_text(cell, 500, "Madre"),
        }
        for field in PERSON_FIELDS:
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

        name_parts = [
            normalized[field]
            for field in ("nombres", "paterno", "materno")
            if normalized[field] is not None
        ]
        normalized["nombre_completo"] = " ".join(name_parts) or None
        hash_fields = tuple(
            (field, normalized[field])
            for field in (
                "documento",
                "paterno",
                "materno",
                "nombres",
                "nombre_completo",
                "fecha_nacimiento",
                "direccion_origen",
                "sexo",
                "estado_civil",
                "padre",
                "madre",
            )
        )
        person = SearchPersonRecord(
            source_row=row.number,
            documento=normalized["documento"],
            paterno=normalized["paterno"],
            materno=normalized["materno"],
            nombres=normalized["nombres"],
            nombre_completo=normalized["nombre_completo"],
            fecha_nacimiento=normalized["fecha_nacimiento"],
            direccion_origen=normalized["direccion_origen"],
            sexo=normalized["sexo"],
            estado_civil=normalized["estado_civil"],
            padre=normalized["padre"],
            madre=normalized["madre"],
            source_code=batch.source_code,
            batch_id=batch.batch_id,
            record_hash=record_hash(hash_fields),
            created_at=ingested_at,
        )
        return raw, person, []

    @staticmethod
    def _document(cell) -> str:
        document = cell_to_text(cell)
        if document is None:
            raise FieldNormalizationError("Documento obligatorio")
        if DNI_PATTERN.fullmatch(document) is None:
            raise FieldNormalizationError("Documento debe ser un DNI de 8 dígitos ASCII")
        return document

    @staticmethod
    def _source_code(cell) -> str | None:
        code = cell_to_text(cell)
        if code is not None and len(code) > 50:
            raise FieldNormalizationError("Sexo excede 50 caracteres")
        return code

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from ...domain.models import (
    BBVA_SOURCE_COLUMNS,
    BbvaPortfolioRecord,
    CellValue,
    PortfolioAddress,
    PortfolioContact,
    PortfolioOperation,
    RowError,
    SourceRow,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_date,
    normalize_money,
    normalize_optional_text,
    normalize_required_text,
    value_for_error,
)
from .base import BaseCarteraProfile


class BbvaV1Profile(BaseCarteraProfile):
    entity = "BBVA"
    version = "1"
    expected_headers = BBVA_SOURCE_COLUMNS
    required_headers = frozenset(BBVA_SOURCE_COLUMNS)
    aliases: dict[str, str] = {}

    def normalize(
        self,
        row: SourceRow,
        *,
        batch_id: int,
        source_file: str,
        ingested_at: datetime,
        error_value_max_length: int,
    ) -> tuple[BbvaPortfolioRecord | None, list[RowError]]:
        errors: list[RowError] = []
        source_values: list[str | None] = []

        for field in self.expected_headers:
            cell = row.values.get(field, CellValue(None))
            try:
                source_values.append(cell_to_text(cell))
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                source_values.append(None)
                errors.append(
                    self._error(batch_id, row.number, field, cell, exception, ingested_at, error_value_max_length)
                )

        normalized: dict[str, Any] = {}
        rules: dict[str, Callable[[CellValue], Any]] = {
            "CODCENTRAL": lambda cell: normalize_required_text(cell, 100, "CODCENTRAL"),
            "CONTRATO": lambda cell: normalize_required_text(cell, 100, "CONTRATO"),
            "numdoc": lambda cell: normalize_required_text(cell, 100, "numdoc"),
            "DOCUMENTO": lambda cell: normalize_optional_text(cell, 100, "DOCUMENTO"),
            "tipodoc": lambda cell: normalize_optional_text(cell, 50, "tipodoc"),
            "NOMBRE": lambda cell: normalize_optional_text(cell, 255, "NOMBRE"),
            "MONEDA": lambda cell: normalize_optional_text(cell, 20, "MONEDA"),
            "Suma de Importes": lambda cell: normalize_money(cell, field_label="Suma de Importes"),
            "Suma de INTERES": lambda cell: self._optional_money(cell, "Suma de INTERES"),
            "Suma de MORA": lambda cell: self._optional_money(cell, "Suma de MORA"),
            "FECHAVEN": self._optional_date,
            "PRODUCTO": lambda cell: normalize_optional_text(cell, 100, "PRODUCTO"),
            "DESCPROD": lambda cell: normalize_optional_text(cell, 255, "DESCPROD"),
            "OFICINA": lambda cell: normalize_optional_text(cell, 100, "OFICINA"),
            "NOMB_OF": lambda cell: normalize_optional_text(cell, 255, "NOMB_OF"),
            "TERRITORIO": lambda cell: normalize_optional_text(cell, 100, "TERRITORIO"),
            "ubigeo": lambda cell: normalize_optional_text(cell, 50, "ubigeo"),
            "dpto": lambda cell: normalize_optional_text(cell, 100, "dpto"),
            "provincia": lambda cell: normalize_optional_text(cell, 100, "provincia"),
            "distrito": lambda cell: normalize_optional_text(cell, 100, "distrito"),
            "COSECHA": lambda cell: normalize_optional_text(cell, 100, "COSECHA"),
        }

        for field, rule in rules.items():
            cell = row.values.get(field, CellValue(None))
            try:
                normalized[field] = rule(cell)
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                errors.append(
                    self._error(batch_id, row.number, field, cell, exception, ingested_at, error_value_max_length)
                )

        contacts: list[PortfolioContact] = []
        for order in range(1, 6):
            phone = self._optional_text_field(row, f"fono{order}", 100, errors, batch_id, ingested_at, error_value_max_length)
            phone_type = self._optional_text_field(row, f"tipofono{order}", 50, errors, batch_id, ingested_at, error_value_max_length)
            prefix = self._optional_text_field(row, f"prefijo{order}", 30, errors, batch_id, ingested_at, error_value_max_length)
            extension = self._optional_text_field(row, f"extension{order}", 30, errors, batch_id, ingested_at, error_value_max_length)
            if phone is not None:
                contacts.append(
                    PortfolioContact(
                        telefono=phone,
                        tipo=phone_type,
                        prefijo=prefix,
                        extension=extension,
                        orden=order,
                    )
                )

        address_values = {
            field: self._optional_text_field(
                row,
                field,
                500 if field in {"direccion", "REFE", "referencia1", "referencia2", "ubicacion"} else 100,
                errors,
                batch_id,
                ingested_at,
                error_value_max_length,
            )
            for field in (
                "direccion",
                "REFE",
                "referencia1",
                "referencia2",
                "ubicacion",
                "codpostal",
                "ubigeo",
                "dpto",
                "provincia",
                "distrito",
            )
        }

        if errors:
            return None, errors

        address = None
        if any(value is not None for value in address_values.values()):
            address = PortfolioAddress(
                tipo_direccion="PRINCIPAL",
                direccion=address_values["direccion"],
                referencia=address_values["REFE"],
                referencia1=address_values["referencia1"],
                referencia2=address_values["referencia2"],
                ubicacion=address_values["ubicacion"],
                codigo_postal=address_values["codpostal"],
                ubigeo=address_values["ubigeo"],
                departamento=address_values["dpto"],
                provincia=address_values["provincia"],
                distrito=address_values["distrito"],
            )

        raw_values = tuple(source_values)
        row_hash = self._row_hash(raw_values)
        operation = PortfolioOperation(
            entidad=self.entity,
            cosecha=normalized["COSECHA"],
            documento_cliente=normalized["numdoc"],
            tipo_documento=normalized["tipodoc"],
            cuenta=normalized["CODCENTRAL"],
            operacion=normalized["CONTRATO"],
            identificador_origen=normalized["DOCUMENTO"],
            nombre_cliente=normalized["NOMBRE"],
            moneda=normalized["MONEDA"],
            saldo_capital=normalized["Suma de Importes"],
            deuda_total=None,
            interes=normalized["Suma de INTERES"],
            mora=normalized["Suma de MORA"],
            fecha_castigo=None,
            fecha_desembolso=None,
            fecha_vencimiento=normalized["FECHAVEN"],
            dias_atraso=None,
            producto=normalized["PRODUCTO"],
            descripcion_producto=normalized["DESCPROD"],
            agencia=normalized["NOMB_OF"],
            oficina=normalized["OFICINA"],
            territorio=normalized["TERRITORIO"],
            ubigeo=normalized["ubigeo"],
            departamento=normalized["dpto"],
            provincia=normalized["provincia"],
            distrito=normalized["distrito"],
        )
        return (
            BbvaPortfolioRecord(
                source_values=raw_values,
                source_row=row.number,
                source_file=source_file,
                batch_id=batch_id,
                row_hash=row_hash,
                ingested_at=ingested_at,
                operation=operation,
                contacts=tuple(contacts),
                address=address,
            ),
            [],
        )

    @staticmethod
    def _optional_money(cell: CellValue, label: str) -> Decimal | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_money(cell, field_label=label)

    @staticmethod
    def _optional_date(cell: CellValue) -> date | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_date(cell)

    @staticmethod
    def _row_hash(values: tuple[str | None, ...]) -> str:
        payload = json.dumps(
            ["cartera:bbva:v1", *values],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _optional_text_field(
        self,
        row: SourceRow,
        field: str,
        maximum_length: int,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        error_value_max_length: int,
    ) -> str | None:
        cell = row.values.get(field, CellValue(None))
        try:
            return normalize_optional_text(cell, maximum_length, field)
        except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
            errors.append(
                self._error(batch_id, row.number, field, cell, exception, ingested_at, error_value_max_length)
            )
            return None

    @staticmethod
    def _error(
        batch_id: int,
        row_number: int,
        field: str,
        cell: CellValue,
        exception: Exception,
        created_at: datetime,
        value_limit: int,
    ) -> RowError:
        return RowError(
            batch_id=batch_id,
            row_number=row_number,
            field=field,
            value=value_for_error(cell, value_limit),
            message=str(exception),
            created_at=created_at,
        )

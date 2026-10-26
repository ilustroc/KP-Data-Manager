from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from ...domain.errors import StructuralFileError
from ...domain.models import (
    WANDOO_SOURCE_COLUMNS,
    CellValue,
    PortfolioAddress,
    PortfolioOperation,
    RowError,
    SourceRow,
    WandooDetail,
    WandooPortfolioRecord,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_money,
    normalize_optional_excel_date,
    normalize_optional_text,
    normalize_required_text,
    value_for_error,
)
from .base import BaseCarteraProfile
from .contracts import (
    wandoo_derived_account,
    wandoo_derived_loan_instance_identifier,
)


class WandooV1Profile(BaseCarteraProfile):
    entity = "WANDOO"
    version = "1"
    expected_headers = WANDOO_SOURCE_COLUMNS
    required_headers = frozenset(WANDOO_SOURCE_COLUMNS)

    def build_header_map(self, header_values: Sequence[Any]) -> dict[str, int]:
        actual = ["" if value is None else str(value).strip() for value in header_values]
        expected = list(self.expected_headers)
        if len(actual) != len(expected):
            raise StructuralFileError(
                f"Wandoo v1 requiere exactamente 19 columnas; se recibieron {len(actual)}."
            )
        for index, (actual_header, expected_header) in enumerate(
            zip(actual, expected, strict=True),
            start=1,
        ):
            if actual_header != expected_header:
                raise StructuralFileError(
                    f"Encabezado incompatible en posición {index}: se esperaba "
                    f"'{expected_header}' y se recibió '{actual_header}'."
                )
        return {header: index for index, header in enumerate(self.expected_headers)}

    def normalize(
        self,
        row: SourceRow,
        *,
        batch_id: int,
        source_file: str,
        ingested_at: datetime,
        error_value_max_length: int,
    ) -> tuple[WandooPortfolioRecord | None, list[RowError]]:
        errors: list[RowError] = []
        source_values = self._source_values(
            row,
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        normalized: dict[str, Any] = {}
        rules: dict[str, Callable[[CellValue], Any]] = {
            "DNI": lambda cell: normalize_required_text(cell, 100, "DNI"),
            "Numero de Prestamo": lambda cell: normalize_required_text(
                cell, 100, "Numero de Prestamo"
            ),
            "Recuento de préstamos ya pagados": lambda cell: self._optional_integer(
                cell, "Recuento de préstamos ya pagados"
            ),
            "Nacionalidad": lambda cell: normalize_optional_text(cell, 100, "Nacionalidad"),
            "Saldo deudor": lambda cell: self._optional_money(cell, "Saldo deudor"),
            "Fecha Últ. Pago": normalize_optional_excel_date,
            "Total soles pagados": lambda cell: self._optional_money(
                cell, "Total soles pagados"
            ),
            "Departamento": lambda cell: normalize_optional_text(cell, 100, "Departamento"),
            "Provincia": lambda cell: normalize_optional_text(cell, 100, "Provincia"),
            "Distrito": lambda cell: normalize_optional_text(cell, 100, "Distrito"),
            "Edad": lambda cell: self._optional_integer(cell, "Edad"),
            "Días de mora": lambda cell: self._optional_integer(cell, "Días de mora"),
            "Producto crediticio": lambda cell: normalize_optional_text(
                cell, 255, "Producto crediticio"
            ),
            "Fuente de Ingreso": lambda cell: normalize_optional_text(
                cell, 255, "Fuente de Ingreso"
            ),
            "Estado Cobranza Actual": lambda cell: normalize_optional_text(
                cell, 255, "Estado Cobranza Actual"
            ),
            "Contactabilidad (Interna)": lambda cell: normalize_optional_text(
                cell, 100, "Contactabilidad (Interna)"
            ),
            "Fecha otorgamiento crédito": normalize_optional_excel_date,
            "Actividad Laboral": lambda cell: normalize_optional_text(
                cell, 255, "Actividad Laboral"
            ),
            "Cosecha": lambda cell: normalize_optional_text(cell, 100, "Cosecha"),
        }
        for field, rule in rules.items():
            self._apply_rule(
                row,
                field,
                rule,
                normalized,
                errors,
                batch_id,
                ingested_at,
                error_value_max_length,
            )

        if errors:
            return None, errors

        geography = {
            field: normalized[field] for field in ("Departamento", "Provincia", "Distrito")
        }
        addresses = ()
        if any(value is not None for value in geography.values()):
            addresses = (
                PortfolioAddress(
                    tipo_direccion="CLIENTE",
                    direccion=None,
                    referencia=None,
                    referencia1=None,
                    referencia2=None,
                    ubicacion=None,
                    codigo_postal=None,
                    ubigeo=None,
                    departamento=geography["Departamento"],
                    provincia=geography["Provincia"],
                    distrito=geography["Distrito"],
                ),
            )

        raw_values = tuple(source_values)
        operation = PortfolioOperation(
            entidad=self.entity,
            cosecha=normalized["Cosecha"],
            documento_cliente=normalized["DNI"],
            tipo_documento=None,
            cuenta=wandoo_derived_account(normalized["DNI"]),
            operacion=normalized["Numero de Prestamo"],
            identificador_origen=wandoo_derived_loan_instance_identifier(
                normalized["DNI"],
                normalized["Numero de Prestamo"],
                normalized["Fecha otorgamiento crédito"],
            ),
            nombre_cliente=None,
            moneda=None,
            saldo_capital=normalized["Saldo deudor"],
            deuda_total=normalized["Saldo deudor"],
            interes=None,
            mora=None,
            fecha_castigo=None,
            fecha_desembolso=normalized["Fecha otorgamiento crédito"],
            fecha_vencimiento=None,
            dias_atraso=normalized["Días de mora"],
            producto=normalized["Producto crediticio"],
            descripcion_producto=None,
            agencia=None,
            oficina=None,
            territorio=None,
            ubigeo=None,
            departamento=normalized["Departamento"],
            provincia=normalized["Provincia"],
            distrito=normalized["Distrito"],
        )
        detail = WandooDetail(
            recuento_prestamos_pagados=normalized["Recuento de préstamos ya pagados"],
            nacionalidad=normalized["Nacionalidad"],
            saldo_deudor=normalized["Saldo deudor"],
            fecha_ultimo_pago=normalized["Fecha Últ. Pago"],
            total_soles_pagados=normalized["Total soles pagados"],
            edad=normalized["Edad"],
            dias_mora=normalized["Días de mora"],
            producto_crediticio=normalized["Producto crediticio"],
            fuente_ingreso=normalized["Fuente de Ingreso"],
            estado_cobranza_actual=normalized["Estado Cobranza Actual"],
            contactabilidad_interna=normalized["Contactabilidad (Interna)"],
            fecha_otorgamiento_credito=normalized["Fecha otorgamiento crédito"],
            actividad_laboral=normalized["Actividad Laboral"],
        )
        return (
            WandooPortfolioRecord(
                source_values=raw_values,
                source_row=row.number,
                source_file=source_file,
                batch_id=batch_id,
                row_hash=self._row_hash(raw_values),
                ingested_at=ingested_at,
                operation=operation,
                detail=detail,
                contacts=(),
                addresses=addresses,
            ),
            [],
        )

    def _source_values(
        self,
        row: SourceRow,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> list[str | None]:
        values: list[str | None] = []
        for field in self.field_names:
            cell = row.values.get(field, CellValue(None))
            try:
                values.append(cell.value if isinstance(cell.value, str) else cell_to_text(cell))
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                values.append(None)
                errors.append(
                    self._error(
                        batch_id,
                        row.number,
                        field,
                        cell,
                        exception,
                        ingested_at,
                        value_limit,
                    )
                )
        return values

    @staticmethod
    def _optional_money(cell: CellValue, label: str) -> Decimal | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_money(cell, field_label=label)

    @staticmethod
    def _optional_integer(cell: CellValue, label: str) -> int | None:
        text = cell_to_text(cell)
        if text is None:
            return None
        try:
            value = Decimal(text)
        except InvalidOperation as exception:
            raise FieldNormalizationError(f"{label} inválido") from exception
        if not value.is_finite() or value != value.to_integral_value():
            raise FieldNormalizationError(f"{label} debe ser entero")
        integer = int(value)
        if not -(2**31) <= integer < 2**31:
            raise FieldNormalizationError(f"{label} excede el rango INT")
        return integer

    def _apply_rule(
        self,
        row: SourceRow,
        field: str,
        rule: Callable[[CellValue], Any],
        normalized: dict[str, Any],
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> None:
        cell = row.values.get(field, CellValue(None))
        try:
            normalized[field] = rule(cell)
        except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
            normalized[field] = None
            errors.append(
                self._error(
                    batch_id,
                    row.number,
                    field,
                    cell,
                    exception,
                    ingested_at,
                    value_limit,
                )
            )

    @staticmethod
    def _row_hash(values: tuple[str | None, ...]) -> str:
        payload = json.dumps(
            ["cartera:wandoo:v1", *values],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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

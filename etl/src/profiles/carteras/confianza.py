from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from ...domain.errors import StructuralFileError
from ...domain.models import (
    CONFIANZA_SOURCE_COLUMNS,
    CellValue,
    ConfianzaDetail,
    ConfianzaPortfolioRecord,
    PortfolioAddress,
    PortfolioContact,
    PortfolioOperation,
    RowError,
    SourceRow,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_money,
    normalize_optional_excel_date,
    normalize_optional_text,
    normalize_phone,
    normalize_required_text,
    value_for_error,
)
from .base import BaseCarteraProfile


class ConfianzaV1Profile(BaseCarteraProfile):
    entity = "CONFIANZA"
    version = "1"
    expected_headers = CONFIANZA_SOURCE_COLUMNS
    required_headers = frozenset(CONFIANZA_SOURCE_COLUMNS)

    def build_header_map(self, header_values: Sequence[Any]) -> dict[str, int]:
        actual = ["" if value is None else str(value).strip() for value in header_values]
        expected = list(self.expected_headers)
        if len(actual) != len(expected):
            raise StructuralFileError(
                f"Financiera Confianza v1 requiere exactamente 27 columnas; se recibieron {len(actual)}."
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
    ) -> tuple[ConfianzaPortfolioRecord | None, list[RowError]]:
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
            "Cuenta Cliente": lambda cell: normalize_required_text(cell, 100, "Cuenta Cliente"),
            "Operacion": lambda cell: normalize_required_text(cell, 100, "Operacion"),
            "Nombre del Deudor": lambda cell: normalize_optional_text(cell, 255, "Nombre del Deudor"),
            "Calle y Numero": lambda cell: normalize_optional_text(cell, 500, "Calle y Numero"),
            "Ubigeo": lambda cell: normalize_optional_text(cell, 100, "Ubigeo"),
            "Departamento_": lambda cell: normalize_optional_text(cell, 100, "Departamento_"),
            "Provincia": lambda cell: normalize_optional_text(cell, 100, "Provincia"),
            "Distrito": lambda cell: normalize_optional_text(cell, 100, "Distrito"),
            "Saldo Capital MO": lambda cell: self._optional_money(cell, "Saldo Capital MO"),
            "Saldo Capital MN": lambda cell: self._optional_money(cell, "Saldo Capital MN"),
            "Interés Vencido": lambda cell: self._optional_money(cell, "Interés Vencido"),
            "Interés Compensatorio": lambda cell: self._optional_money(cell, "Interés Compensatorio"),
            "Interés Moratorio": lambda cell: self._optional_money(cell, "Interés Moratorio"),
            "Seguros": lambda cell: self._optional_money(cell, "Seguros"),
            "Comisiones": lambda cell: self._optional_money(cell, "Comisiones"),
            "Gastos Judiciales": lambda cell: self._optional_money(cell, "Gastos Judiciales"),
            "Moneda": lambda cell: normalize_optional_text(cell, 50, "Moneda"),
            "Código de Sucursal de Crédito": lambda cell: normalize_optional_text(
                cell, 100, "Código de Sucursal de Crédito"
            ),
            "Nombre Sucursal de Crédito": lambda cell: normalize_optional_text(
                cell, 255, "Nombre Sucursal de Crédito"
            ),
            "Territorio": lambda cell: normalize_optional_text(cell, 100, "Territorio"),
            "Corredor": lambda cell: normalize_optional_text(cell, 255, "Corredor"),
            "Fecha Castigo": normalize_optional_excel_date,
            "Nombre_modulo Origen": lambda cell: normalize_optional_text(
                cell, 255, "Nombre_modulo Origen"
            ),
            "Estado de la Operación": lambda cell: normalize_optional_text(
                cell, 255, "Estado de la Operación"
            ),
            "COSECHA": lambda cell: normalize_optional_text(cell, 100, "COSECHA"),
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

        phone_source = self._optional_text(
            row,
            "Telefono",
            500,
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        phone = normalize_phone(phone_source)
        contacts = () if phone is None else (PortfolioContact(phone, "FUENTE", None, None, 1),)
        address_values = {
            field: normalized.get(field)
            for field in ("Calle y Numero", "Ubigeo", "Departamento_", "Provincia", "Distrito")
        }
        addresses = ()
        if any(value is not None for value in address_values.values()):
            addresses = (
                PortfolioAddress(
                    tipo_direccion="CLIENTE",
                    direccion=address_values["Calle y Numero"],
                    referencia=None,
                    referencia1=None,
                    referencia2=None,
                    ubicacion=None,
                    codigo_postal=None,
                    ubigeo=address_values["Ubigeo"],
                    departamento=address_values["Departamento_"],
                    provincia=address_values["Provincia"],
                    distrito=address_values["Distrito"],
                ),
            )

        currency_code = normalized.get("Moneda")
        canonical_currency = self._canonical_currency(currency_code)
        canonical_capital = self._canonical_capital(currency_code, normalized)
        debt_total = None
        if not errors:
            try:
                debt_total = self._debt_total(currency_code, canonical_capital, normalized)
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                errors.append(
                    self._error(
                        batch_id,
                        row.number,
                        "deuda_total",
                        CellValue(None),
                        exception,
                        ingested_at,
                        error_value_max_length,
                    )
                )

        if errors:
            return None, errors

        raw_values = tuple(source_values)
        operation = PortfolioOperation(
            entidad=self.entity,
            cosecha=normalized["COSECHA"],
            documento_cliente=normalized["DNI"],
            tipo_documento=None,
            cuenta=normalized["Cuenta Cliente"],
            operacion=normalized["Operacion"],
            identificador_origen=None,
            nombre_cliente=normalized["Nombre del Deudor"],
            moneda=canonical_currency,
            saldo_capital=canonical_capital,
            deuda_total=debt_total,
            interes=normalized["Interés Compensatorio"],
            mora=normalized["Interés Moratorio"],
            fecha_castigo=normalized["Fecha Castigo"],
            fecha_desembolso=None,
            fecha_vencimiento=None,
            dias_atraso=None,
            producto=None,
            descripcion_producto=None,
            agencia=normalized["Nombre Sucursal de Crédito"],
            oficina=None,
            territorio=normalized["Territorio"],
            ubigeo=normalized["Ubigeo"],
            departamento=normalized["Departamento_"],
            provincia=normalized["Provincia"],
            distrito=normalized["Distrito"],
        )
        detail = ConfianzaDetail(
            saldo_capital_mo=normalized["Saldo Capital MO"],
            saldo_capital_mn=normalized["Saldo Capital MN"],
            interes_vencido=normalized["Interés Vencido"],
            interes_compensatorio=normalized["Interés Compensatorio"],
            interes_moratorio=normalized["Interés Moratorio"],
            seguros=normalized["Seguros"],
            comisiones=normalized["Comisiones"],
            gastos_judiciales=normalized["Gastos Judiciales"],
            moneda_origen=normalized["Moneda"],
            codigo_sucursal_credito=normalized["Código de Sucursal de Crédito"],
            nombre_sucursal_credito=normalized["Nombre Sucursal de Crédito"],
            corredor=normalized["Corredor"],
            nombre_modulo_origen=normalized["Nombre_modulo Origen"],
            estado_operacion=normalized["Estado de la Operación"],
        )
        return (
            ConfianzaPortfolioRecord(
                source_values=raw_values,
                source_row=row.number,
                source_file=source_file,
                batch_id=batch_id,
                row_hash=self._row_hash(raw_values),
                ingested_at=ingested_at,
                operation=operation,
                detail=detail,
                contacts=contacts,
                addresses=addresses,
            ),
            [],
        )

    @staticmethod
    def _canonical_currency(currency_code: str | None) -> str | None:
        return {"0": "PEN", "101": "USD"}.get(currency_code)

    @staticmethod
    def _canonical_capital(
        currency_code: str | None,
        normalized: dict[str, Any],
    ) -> Decimal | None:
        if currency_code == "0":
            return normalized["Saldo Capital MN"]
        if currency_code == "101":
            return normalized["Saldo Capital MO"]
        return None

    @staticmethod
    def _debt_total(
        currency_code: str | None,
        canonical_capital: Decimal | None,
        normalized: dict[str, Any],
    ) -> Decimal | None:
        if currency_code not in {"0", "101"}:
            return None
        components = (
            canonical_capital,
            normalized["Interés Vencido"],
            normalized["Interés Compensatorio"],
            normalized["Interés Moratorio"],
            normalized["Seguros"],
            normalized["Comisiones"],
            normalized["Gastos Judiciales"],
        )
        total = sum(
            (component if component is not None else Decimal("0.00") for component in components),
            Decimal("0.00"),
        )
        return normalize_money(CellValue(total), field_label="Deuda total")

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
                values.append(cell_to_text(cell))
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                values.append(None)
                errors.append(
                    self._error(batch_id, row.number, field, cell, exception, ingested_at, value_limit)
                )
        return values

    @staticmethod
    def _optional_money(cell: CellValue, label: str) -> Decimal | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_money(cell, field_label=label)

    def _optional_text(
        self,
        row: SourceRow,
        field: str,
        maximum: int,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> str | None:
        cell = row.values.get(field, CellValue(None))
        try:
            return normalize_optional_text(cell, maximum, field)
        except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
            errors.append(
                self._error(batch_id, row.number, field, cell, exception, ingested_at, value_limit)
            )
            return None

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
                self._error(batch_id, row.number, field, cell, exception, ingested_at, value_limit)
            )

    @staticmethod
    def _row_hash(values: tuple[str | None, ...]) -> str:
        payload = json.dumps(
            ["cartera:confianza:v1", *values],
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

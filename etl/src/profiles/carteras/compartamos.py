from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from openpyxl.utils.datetime import to_excel

from ...domain.errors import StructuralFileError
from ...domain.models import (
    COMPARTAMOS_SOURCE_COLUMNS,
    CellValue,
    CompartamosDetail,
    CompartamosPortfolioRecord,
    PortfolioAddress,
    PortfolioContact,
    PortfolioOperation,
    RowError,
    SourceRow,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_decimal_18_6,
    normalize_money,
    normalize_optional_excel_date,
    normalize_optional_text,
    normalize_phone,
    normalize_required_text,
    value_for_error,
)
from .base import BaseCarteraProfile


class CompartamosV1Profile(BaseCarteraProfile):
    entity = "COMPARTAMOS"
    version = "1"
    expected_headers = COMPARTAMOS_SOURCE_COLUMNS
    required_headers = frozenset(COMPARTAMOS_SOURCE_COLUMNS)

    def build_header_map(self, header_values: Sequence[Any]) -> dict[str, int]:
        actual = ["" if value is None else str(value).strip() for value in header_values]
        expected = list(self.expected_headers)
        if len(actual) != len(expected):
            raise StructuralFileError(
                f"Compartamos v1 requiere exactamente 30 columnas; se recibieron {len(actual)}."
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
    ) -> tuple[CompartamosPortfolioRecord | None, list[RowError]]:
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
            "NumDoc": lambda cell: normalize_required_text(cell, 100, "NumDoc"),
            "Ctacliente": lambda cell: normalize_required_text(cell, 100, "Ctacliente"),
            "Operación": lambda cell: normalize_required_text(cell, 100, "Operación"),
            "Documento": lambda cell: normalize_optional_text(cell, 100, "Documento"),
            "NomCliente": lambda cell: normalize_optional_text(cell, 255, "NomCliente"),
            "oficina Agencia": lambda cell: normalize_optional_text(cell, 255, "oficina Agencia"),
            "Skapital": lambda cell: self._optional_money(cell, "Skapital"),
            "IntComp": lambda cell: self._optional_money(cell, "IntComp"),
            "IntMoratorio": lambda cell: self._optional_money(cell, "IntMoratorio"),
            "Deuda total": lambda cell: self._optional_money(cell, "Deuda total"),
            "Moneda": self._currency,
            "TipCambio": self._optional_exchange_rate,
            "SKSoles": lambda cell: self._optional_money(cell, "SKSoles"),
            "Lote": lambda cell: normalize_optional_text(cell, 100, "Lote"),
            "Empresa": lambda cell: normalize_optional_text(cell, 255, "Empresa"),
            "FecCastigo": normalize_optional_excel_date,
            "FecDesembolso": self._disbursement,
            "Dias_Atraso": lambda cell: self._optional_integer(cell, "Dias_Atraso"),
            "LinNeg": lambda cell: normalize_optional_text(cell, 100, "LinNeg"),
            "NomDistrito": lambda cell: normalize_optional_text(cell, 100, "NomDistrito"),
            "NomProvincia": lambda cell: normalize_optional_text(cell, 100, "NomProvincia"),
            "NomDepartamento": lambda cell: normalize_optional_text(cell, 100, "NomDepartamento"),
            "FecNacimiento": normalize_optional_excel_date,
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

        contacts = self._contacts(
            row,
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        addresses = self._addresses(
            row,
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        if errors:
            return None, errors

        raw_values = tuple(source_values)
        disbursement_date, disbursement_year = normalized["FecDesembolso"]
        operation = PortfolioOperation(
            entidad=self.entity,
            cosecha=normalized["Cosecha"],
            documento_cliente=normalized["NumDoc"],
            tipo_documento=None,
            cuenta=normalized["Ctacliente"],
            operacion=normalized["Operación"],
            identificador_origen=None,
            nombre_cliente=normalized["NomCliente"],
            moneda=normalized["Moneda"],
            saldo_capital=normalized["Skapital"],
            deuda_total=normalized["Deuda total"],
            interes=normalized["IntComp"],
            mora=normalized["IntMoratorio"],
            fecha_castigo=normalized["FecCastigo"],
            fecha_desembolso=disbursement_date,
            fecha_vencimiento=None,
            dias_atraso=normalized["Dias_Atraso"],
            producto=normalized["LinNeg"],
            descripcion_producto=None,
            agencia=normalized["oficina Agencia"],
            oficina=None,
            territorio=None,
            ubigeo=None,
            departamento=normalized["NomDepartamento"],
            provincia=normalized["NomProvincia"],
            distrito=normalized["NomDistrito"],
        )
        detail = CompartamosDetail(
            documento_fuente=normalized["Documento"],
            tipo_cambio=normalized["TipCambio"],
            saldo_capital_soles=normalized["SKSoles"],
            lote=normalized["Lote"],
            empresa=normalized["Empresa"],
            anio_desembolso=disbursement_year,
            fecha_nacimiento=normalized["FecNacimiento"],
        )
        return (
            CompartamosPortfolioRecord(
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
    def _disbursement(cell: CellValue) -> tuple[date | None, int | None]:
        text = cell_to_text(cell)
        if text is None:
            return None, None

        value = cell.value
        if isinstance(value, (datetime, date)):
            if cell.workbook_epoch is not None:
                try:
                    excel_serial = Decimal(str(to_excel(value, cell.workbook_epoch)))
                except (OverflowError, TypeError, ValueError) as exception:
                    raise FieldNormalizationError(
                        "Año o fecha de desembolso inválido"
                    ) from exception
                if excel_serial.is_finite() and excel_serial == excel_serial.to_integral_value():
                    possible_year = int(excel_serial)
                    if 1900 <= possible_year <= 2100:
                        return None, possible_year

            normalized_date = value.date() if isinstance(value, datetime) else value

            return normalized_date, normalized_date.year

        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            try:
                numeric = Decimal(str(value))
            except InvalidOperation as exception:
                raise FieldNormalizationError("Año o fecha de desembolso inválido") from exception
            if not numeric.is_finite() or numeric != numeric.to_integral_value():
                raise FieldNormalizationError("Año de desembolso debe ser un número entero")
            year = int(numeric)
            if not 1900 <= year <= 2100:
                raise FieldNormalizationError("Año de desembolso debe estar entre 1900 y 2100")

            return None, year

        if len(text) == 4 and text.isascii() and text.isdigit():
            year = int(text)
            if not 1900 <= year <= 2100:
                raise FieldNormalizationError("Año de desembolso debe estar entre 1900 y 2100")

            return None, year

        normalized_date = normalize_optional_excel_date(cell)
        if normalized_date is None:
            return None, None

        return normalized_date, normalized_date.year

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

    def _contacts(
        self,
        row: SourceRow,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> tuple[PortfolioContact, ...]:
        contacts: list[PortfolioContact] = []
        seen: set[str] = set()
        for field in ("Telefono1", "Telefono2", "Telefono3", "Telefono4"):
            value = self._optional_text(
                row,
                field,
                500,
                errors,
                batch_id,
                ingested_at,
                value_limit,
            )
            phone = normalize_phone(value)
            if phone is None or phone in seen:
                continue
            if len(phone) > 100:
                errors.append(
                    self._error(
                        batch_id,
                        row.number,
                        field,
                        row.values.get(field, CellValue(None)),
                        FieldNormalizationError(f"{field} contiene un teléfono mayor de 100 caracteres"),
                        ingested_at,
                        value_limit,
                    )
                )
                continue
            seen.add(phone)
            contacts.append(PortfolioContact(phone, "FUENTE", None, None, len(contacts) + 1))
        return tuple(contacts)

    def _addresses(
        self,
        row: SourceRow,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> tuple[PortfolioAddress, ...]:
        addresses: list[PortfolioAddress] = []
        for address_type, field in (
            ("CLIENTE", "Direccion Cliente"),
            ("NEGOCIO", "Direccion Negocio"),
        ):
            address = self._optional_text(
                row,
                field,
                500,
                errors,
                batch_id,
                ingested_at,
                value_limit,
            )
            if address is None:
                continue
            addresses.append(
                PortfolioAddress(
                    tipo_direccion=address_type,
                    direccion=address,
                    referencia=None,
                    referencia1=None,
                    referencia2=None,
                    ubicacion=None,
                    codigo_postal=None,
                    ubigeo=None,
                    departamento=None,
                    provincia=None,
                    distrito=None,
                )
            )
        return tuple(addresses)

    @staticmethod
    def _currency(cell: CellValue) -> str | None:
        value = normalize_optional_text(cell, 20, "Moneda")
        if value is None:
            return None
        normalized = value.upper()
        return "PEN" if normalized in {"S/", "S/.", "SOLES", "PEN"} else normalized

    @staticmethod
    def _optional_money(cell: CellValue, label: str) -> Decimal | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_money(cell, field_label=label)

    @staticmethod
    def _optional_exchange_rate(cell: CellValue) -> Decimal | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_decimal_18_6(cell, field_label="TipCambio")

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

    @staticmethod
    def _row_hash(values: tuple[str | None, ...]) -> str:
        payload = json.dumps(
            ["cartera:compartamos:v1", *values],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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

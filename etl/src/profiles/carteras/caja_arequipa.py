from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from openpyxl.utils.datetime import from_excel

from ...domain.errors import StructuralFileError
from ...domain.models import (
    CAJA_AREQUIPA_SOURCE_COLUMNS,
    CAJA_AREQUIPA_SOURCE_HEADERS,
    CajaArequipaDetail,
    CajaArequipaPortfolioRecord,
    CellValue,
    PortfolioAddress,
    PortfolioContact,
    PortfolioGuarantee,
    PortfolioGuarantor,
    PortfolioOperation,
    RowError,
    SourceRow,
)
from ...domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_date,
    normalize_decimal_15_4,
    normalize_money,
    normalize_optional_text,
    normalize_required_text,
    value_for_error,
)
from .base import BaseCarteraProfile

DATE_PLACEHOLDER_PATTERN = re.compile(r"^[\s/]*$")


class CajaArequipaV1Profile(BaseCarteraProfile):
    entity = "CAJA_AREQUIPA"
    version = "1"
    expected_headers = CAJA_AREQUIPA_SOURCE_HEADERS
    required_headers = frozenset(CAJA_AREQUIPA_SOURCE_HEADERS)

    @property
    def field_names(self) -> tuple[str, ...]:
        return CAJA_AREQUIPA_SOURCE_COLUMNS

    def build_header_map(self, header_values: Sequence[Any]) -> dict[str, int]:
        actual = ["" if value is None else str(value).strip() for value in header_values]
        expected = list(self.expected_headers)
        if len(actual) != len(expected):
            raise StructuralFileError(
                f"Caja Arequipa v1 requiere exactamente 66 columnas; se recibieron {len(actual)}."
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
        return {
            technical_name: index
            for index, technical_name in enumerate(CAJA_AREQUIPA_SOURCE_COLUMNS)
        }

    def normalize(
        self,
        row: SourceRow,
        *,
        batch_id: int,
        source_file: str,
        ingested_at: datetime,
        error_value_max_length: int,
    ) -> tuple[CajaArequipaPortfolioRecord | None, list[RowError]]:
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
            "CUENTA": lambda cell: normalize_required_text(cell, 100, "CUENTA"),
            "OPERACION": lambda cell: normalize_required_text(cell, 100, "OPERACION"),
            "AGENCIA": lambda cell: normalize_optional_text(cell, 255, "AGENCIA"),
            "ANALISTA": lambda cell: normalize_optional_text(cell, 100, "ANALISTA"),
            "TITULAR": lambda cell: normalize_optional_text(cell, 255, "TITULAR"),
            "TIPO_CONTABLE": lambda cell: normalize_optional_text(cell, 100, "TIPO_CONTABLE"),
            "TIP_SBS": lambda cell: normalize_optional_text(cell, 100, "TIP_SBS"),
            "MONEDA": self._currency,
            "SALDO_CAPITAL": lambda cell: self._optional_money(cell, "SALDO_CAPITAL"),
            "FEC_ULT_PAG": self._optional_date,
            "DIAS_ATRASO": lambda cell: self._optional_integer(cell, "DIAS_ATRASO"),
            "CUO_PAG": lambda cell: self._optional_integer(cell, "CUO_PAG"),
            "ACTIVIDAD": lambda cell: normalize_optional_text(cell, 1000, "ACTIVIDAD"),
            "NRO_AVALES": lambda cell: self._optional_integer(cell, "NRO_AVALES"),
            "TIP_DOC_TIT": lambda cell: normalize_optional_text(cell, 50, "TIP_DOC_TIT"),
            "COD_SBS": lambda cell: normalize_optional_text(cell, 100, "COD_SBS"),
            "FEC_DES": self._optional_date,
            "MTO_DES": lambda cell: self._optional_money(cell, "MTO_DES"),
            "INT_MORATORIO": lambda cell: self._optional_money(cell, "INT_MORATORIO"),
            "INT_COMP": lambda cell: self._optional_money(cell, "INT_COMP"),
            "ICV": lambda cell: self._optional_money(cell, "ICV"),
            "SEGUROS": lambda cell: self._optional_money(cell, "SEGUROS"),
            "PENALIDAD": lambda cell: self._optional_money(cell, "PENALIDAD"),
            "OTROS_RUBROS": lambda cell: self._optional_money(cell, "OTROS_RUBROS"),
            "TOT_DEUDA": lambda cell: self._optional_money(cell, "TOT_DEUDA"),
            "CAL_SBS": lambda cell: normalize_optional_text(cell, 100, "CAL_SBS"),
            "PROVISION": lambda cell: self._optional_provision(cell),
            "FEC_ING_JUD": self._optional_date,
            "FEC_ING_CAS": self._optional_date,
            "REFINANCIADO": lambda cell: normalize_optional_text(cell, 50, "REFINANCIADO"),
            "UBIGEO": lambda cell: normalize_optional_text(cell, 100, "UBIGEO"),
            "DEPARTAMENTO": lambda cell: normalize_optional_text(cell, 100, "DEPARTAMENTO"),
            "PROVINCIA": lambda cell: normalize_optional_text(cell, 100, "PROVINCIA"),
            "DISTRITO": lambda cell: normalize_optional_text(cell, 100, "DISTRITO"),
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

        document = self._effective_document(
            row,
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        contacts = self._contacts(row, errors, batch_id, ingested_at, error_value_max_length)
        addresses = self._addresses(row, errors, batch_id, ingested_at, error_value_max_length)
        guarantor = self._guarantor(
            row,
            normalized.get("NRO_AVALES"),
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        guarantees = self._guarantees(
            row,
            errors,
            batch_id,
            ingested_at,
            error_value_max_length,
        )
        if errors or document is None:
            return None, errors

        raw_values = tuple(source_values)
        operation = PortfolioOperation(
            entidad=self.entity,
            cosecha=normalized["COSECHA"],
            documento_cliente=document,
            tipo_documento=normalized["TIP_DOC_TIT"],
            cuenta=normalized["CUENTA"],
            operacion=normalized["OPERACION"],
            identificador_origen=None,
            nombre_cliente=normalized["TITULAR"],
            moneda=normalized["MONEDA"],
            saldo_capital=normalized["SALDO_CAPITAL"],
            deuda_total=normalized["TOT_DEUDA"],
            interes=normalized["INT_COMP"],
            mora=normalized["INT_MORATORIO"],
            fecha_castigo=normalized["FEC_ING_CAS"],
            fecha_desembolso=normalized["FEC_DES"],
            fecha_vencimiento=None,
            dias_atraso=normalized["DIAS_ATRASO"],
            producto=normalized["TIP_SBS"],
            descripcion_producto=None,
            agencia=normalized["AGENCIA"],
            oficina=None,
            territorio=None,
            ubigeo=normalized["UBIGEO"],
            departamento=normalized["DEPARTAMENTO"],
            provincia=normalized["PROVINCIA"],
            distrito=normalized["DISTRITO"],
        )
        detail = CajaArequipaDetail(
            analista=normalized["ANALISTA"],
            tipo_contable=normalized["TIPO_CONTABLE"],
            fecha_ultimo_pago=normalized["FEC_ULT_PAG"],
            cuo_pag=normalized["CUO_PAG"],
            actividad=normalized["ACTIVIDAD"],
            nro_avales_reportado=normalized["NRO_AVALES"],
            codigo_sbs=normalized["COD_SBS"],
            monto_desembolso=normalized["MTO_DES"],
            icv=normalized["ICV"],
            seguros=normalized["SEGUROS"],
            penalidad=normalized["PENALIDAD"],
            otros_rubros=normalized["OTROS_RUBROS"],
            calificacion_sbs=normalized["CAL_SBS"],
            provision=normalized["PROVISION"],
            fecha_ingreso_judicial=normalized["FEC_ING_JUD"],
            refinanciado=normalized["REFINANCIADO"],
        )
        return (
            CajaArequipaPortfolioRecord(
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
                guarantor=guarantor,
                guarantees=guarantees,
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
                values.append(cell_to_text(cell))
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                values.append(None)
                errors.append(self._error(batch_id, row.number, field, cell, exception, ingested_at, value_limit))
        return values

    def _effective_document(
        self,
        row: SourceRow,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> str | None:
        first_cell = row.values.get("NRO_DOC_TIT_1", CellValue(None))
        second_cell = row.values.get("NRO_DOC_TIT_2", CellValue(None))
        try:
            first = normalize_optional_text(first_cell, 100, "NRO_DOC_TIT")
            second = normalize_optional_text(second_cell, 100, "NRO_DOC_TIT")
        except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
            errors.append(
                self._error(
                    batch_id, row.number, "NRO_DOC_TIT", first_cell,
                    exception, ingested_at, value_limit,
                )
            )
            return None
        if first is None and second is None:
            exception = FieldNormalizationError("NRO_DOC_TIT obligatorio")
        elif first is not None and second is not None and first != second:
            exception = FieldNormalizationError(
                "Las dos columnas NRO_DOC_TIT contienen valores diferentes"
            )
        else:
            return first or second
        errors.append(
            self._error(
                batch_id,
                row.number,
                "NRO_DOC_TIT",
                first_cell,
                exception,
                ingested_at,
                value_limit,
            )
        )
        return None

    def _contacts(
        self,
        row: SourceRow,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> tuple[PortfolioContact, ...]:
        contacts: list[PortfolioContact] = []
        for field, contact_type in (("TEL_TIT", "TITULAR"), ("TEL_GES", "GESTION")):
            value = self._optional_text(row, field, 500, errors, batch_id, ingested_at, value_limit)
            for segment in self._phone_segments(value):
                if len(segment) > 100:
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
                contacts.append(PortfolioContact(segment, contact_type, None, None, len(contacts) + 1))
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
        definitions = (
            ("LEGAL", "DIR_LEGAL", "REF_LEGAL", "DIS_LEGAL"),
            ("GESTION", "DIR_GES", "REF_GES", "DIS_GES"),
            ("NEGOCIO", "DIR_NEG", None, "DIS_NEG"),
        )
        for address_type, address_field, reference_field, district_field in definitions:
            address = self._optional_text(row, address_field, 500, errors, batch_id, ingested_at, value_limit)
            reference = None if reference_field is None else self._optional_text(
                row, reference_field, 500, errors, batch_id, ingested_at, value_limit
            )
            district = self._optional_text(row, district_field, 100, errors, batch_id, ingested_at, value_limit)
            if any(value is not None for value in (address, reference, district)):
                addresses.append(
                    PortfolioAddress(
                        tipo_direccion=address_type,
                        direccion=address,
                        referencia=reference,
                        referencia1=None,
                        referencia2=None,
                        ubicacion=None,
                        codigo_postal=None,
                        ubigeo=None,
                        departamento=None,
                        provincia=None,
                        distrito=district,
                    )
                )
        return tuple(addresses)

    def _guarantor(
        self,
        row: SourceRow,
        reported_count: int | None,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> PortfolioGuarantor | None:
        values = {
            field: self._optional_text(row, field, maximum, errors, batch_id, ingested_at, value_limit)
            for field, maximum in {
                "NOM_AVAL": 255,
                "TIP_DOC_AVAL": 100,
                "NRO_DOC_AVAL": 100,
                "TEL_AVAL": 500,
                "DIR_AVAL": 1000,
                "REF_AVAL": 1000,
                "DIS_AVAL": 255,
            }.items()
        }
        if not any(value is not None for value in values.values()):
            return None
        return PortfolioGuarantor(
            orden=1,
            nombre_aval=values["NOM_AVAL"],
            tipo_documento=values["TIP_DOC_AVAL"],
            documento_aval=values["NRO_DOC_AVAL"],
            telefono="|".join(self._phone_segments(values["TEL_AVAL"])) or None,
            direccion=values["DIR_AVAL"],
            referencia=values["REF_AVAL"],
            distrito=values["DIS_AVAL"],
            cantidad_reportada=reported_count,
        )

    def _guarantees(
        self,
        row: SourceRow,
        errors: list[RowError],
        batch_id: int,
        ingested_at: datetime,
        value_limit: int,
    ) -> tuple[PortfolioGuarantee, ...]:
        guarantees: list[PortfolioGuarantee] = []
        for order in range(1, 7):
            type_field = f"TIP_GAR{order}"
            amount_field = f"MTO_GAR{order}"
            guarantee_type = self._optional_text(
                row, type_field, 255, errors, batch_id, ingested_at, value_limit
            )
            amount_cell = row.values.get(amount_field, CellValue(None))
            try:
                amount = self._optional_money(amount_cell, amount_field)
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                amount = None
                errors.append(self._error(batch_id, row.number, amount_field, amount_cell, exception, ingested_at, value_limit))
            if guarantee_type is not None or cell_to_text(amount_cell) is not None:
                guarantees.append(PortfolioGuarantee(order, guarantee_type, amount))
        return tuple(guarantees)

    @staticmethod
    def _phone_segments(value: str | None) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(
            normalized
            for segment in value.split("|")
            if (normalized := re.sub(r"\s+", "", segment.strip()))
        )

    @staticmethod
    def _currency(cell: CellValue) -> str | None:
        value = normalize_optional_text(cell, 20, "MONEDA")
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
    def _optional_provision(cell: CellValue) -> Decimal | None:
        if cell_to_text(cell) is None:
            return None
        return normalize_decimal_15_4(cell, field_label="PROVISION")

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
    def _optional_date(cell: CellValue) -> date | None:
        if isinstance(cell.value, str) and DATE_PLACEHOLDER_PATTERN.fullmatch(cell.value):
            return None
        if cell.value is None or cell_to_text(cell) is None:
            return None
        if (
            isinstance(cell.value, (int, float))
            and not isinstance(cell.value, bool)
            and cell.workbook_epoch is not None
        ):
            try:
                converted = from_excel(cell.value, cell.workbook_epoch)
            except (OverflowError, TypeError, ValueError) as exception:
                raise FieldNormalizationError("Fecha Excel inválida") from exception
            if isinstance(converted, datetime):
                return converted.date()
            if isinstance(converted, date):
                return converted
            raise FieldNormalizationError("Fecha Excel inválida")
        return normalize_date(cell)

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
            errors.append(self._error(batch_id, row.number, field, cell, exception, ingested_at, value_limit))
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
            errors.append(self._error(batch_id, row.number, field, cell, exception, ingested_at, value_limit))

    @staticmethod
    def _row_hash(values: tuple[str | None, ...]) -> str:
        payload = json.dumps(["cartera:caja_arequipa:v1", *values], ensure_ascii=False, separators=(",", ":"))
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

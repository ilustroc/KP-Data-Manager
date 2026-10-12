from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl.utils.datetime import CALENDAR_WINDOWS_1900

from src.domain.errors import StructuralFileError
from src.domain.models import (
    CONFIANZA_BRONZE_COLUMNS,
    CONFIANZA_SOURCE_COLUMNS,
    CellValue,
    SourceRow,
)
from src.profiles.carteras.confianza import ConfianzaV1Profile

FIXED_UTC = datetime(2026, 10, 12, 15, 0, 0)


def source_values(**overrides: object) -> dict[str, CellValue]:
    values: dict[str, object] = {column: None for column in CONFIANZA_SOURCE_COLUMNS}
    values.update(
        {
            "DNI": "00003862",
            "Cuenta Cliente": "0000123400",
            "Nombre del Deudor": "Cliente Sintético",
            "Calle y Numero": "Av. Confianza 123",
            "Ubigeo": "150101",
            "Departamento_": "LIMA",
            "Provincia": "LIMA",
            "Distrito": "LIMA",
            "Operacion": "0000987600",
            "Saldo Capital MO": "1,000.10",
            "Saldo Capital MN": "3,500.20",
            "Interés Vencido": "100.30",
            "Interés Compensatorio": "200.40",
            "Interés Moratorio": "50.50",
            "Seguros": "10.60",
            "Comisiones": "20.70",
            "Gastos Judiciales": "30.80",
            "Moneda": "0",
            "Código de Sucursal de Crédito": "001",
            "Nombre Sucursal de Crédito": "AGENCIA CENTRO",
            "Territorio": "CENTRO",
            "Corredor": "CORREDOR UNO",
            "Fecha Castigo": "23/11/2017",
            "Telefono": "+51934043966",
            "Nombre_modulo Origen": "MÓDULO CARTERA",
            "Estado de la Operación": "CASTIGADO",
            "COSECHA": "CONFIANZA_1",
        }
    )
    values.update(overrides)
    return {
        column: value if isinstance(value, CellValue) else CellValue(value)
        for column, value in values.items()
    }


def normalize(**overrides: object):
    return ConfianzaV1Profile().normalize(
        SourceRow(2, source_values(**overrides)),
        batch_id=77,
        source_file="confianza_sintetico.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )


def test_header_requires_exact_27_positions_and_trims_unicode_padding():
    headers = [f"\u00a0 {header} \u00a0" for header in CONFIANZA_SOURCE_COLUMNS]

    mapping = ConfianzaV1Profile().build_header_map(headers)

    assert len(CONFIANZA_SOURCE_COLUMNS) == 27
    assert len(CONFIANZA_BRONZE_COLUMNS) == 27
    assert tuple(mapping) == CONFIANZA_SOURCE_COLUMNS
    assert "Interés Vencido" in mapping
    assert "Código de Sucursal de Crédito" in mapping
    assert "Estado de la Operación" in mapping


def test_source_headers_map_positionally_to_snake_case_bronze_columns():
    source_to_bronze = dict(
        zip(CONFIANZA_SOURCE_COLUMNS, CONFIANZA_BRONZE_COLUMNS, strict=True)
    )

    assert source_to_bronze["Interés Vencido"] == "interes_vencido"
    assert (
        source_to_bronze["Código de Sucursal de Crédito"]
        == "codigo_sucursal_credito"
    )
    assert source_to_bronze["Estado de la Operación"] == "estado_operacion"
    assert len(source_to_bronze) == 27


@pytest.mark.parametrize(
    "headers",
    [
        CONFIANZA_SOURCE_COLUMNS[:-1],
        (*CONFIANZA_SOURCE_COLUMNS, "EXTRA"),
        (
            CONFIANZA_SOURCE_COLUMNS[1],
            CONFIANZA_SOURCE_COLUMNS[0],
            *CONFIANZA_SOURCE_COLUMNS[2:],
        ),
    ],
)
def test_header_rejects_missing_extra_or_reordered_columns(headers: tuple[str, ...]):
    with pytest.raises(StructuralFileError):
        ConfianzaV1Profile().build_header_map(headers)


def test_identity_common_values_geography_and_business_fields_are_mapped():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.entidad == "CONFIANZA"
    assert record.operation.documento_cliente == "00003862"
    assert record.operation.cuenta == "0000123400"
    assert record.operation.operacion == "0000987600"
    assert record.operation.nombre_cliente == "Cliente Sintético"
    assert record.operation.cosecha == "CONFIANZA_1"
    assert record.operation.agencia == "AGENCIA CENTRO"
    assert record.operation.territorio == "CENTRO"
    assert record.operation.ubigeo == "150101"
    assert record.operation.departamento == "LIMA"
    assert record.operation.provincia == "LIMA"
    assert record.operation.distrito == "LIMA"


def test_pen_money_fields_are_preserved_and_common_values_follow_confirmed_rules():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.moneda == "PEN"
    assert record.operation.saldo_capital == Decimal("3500.20")
    assert record.operation.deuda_total == Decimal("3913.50")
    assert record.operation.interes == Decimal("200.40")
    assert record.operation.mora == Decimal("50.50")
    assert record.detail.saldo_capital_mo == Decimal("1000.10")
    assert record.detail.saldo_capital_mn == Decimal("3500.20")
    assert record.detail.interes_vencido == Decimal("100.30")
    assert record.detail.interes_compensatorio == Decimal("200.40")
    assert record.detail.interes_moratorio == Decimal("50.50")
    assert record.detail.seguros == Decimal("10.60")
    assert record.detail.comisiones == Decimal("20.70")
    assert record.detail.gastos_judiciales == Decimal("30.80")
    assert record.detail.moneda_origen == "0"


@pytest.mark.parametrize(
    ("raw_currency", "expected_currency", "expected_origin"),
    [
        (0, "PEN", "0"),
        ("0", "PEN", "0"),
        (CellValue(0.0, is_xlsx_float=True), "PEN", "0"),
        (101, "USD", "101"),
        ("101", "USD", "101"),
        (CellValue(101.0, is_xlsx_float=True), "USD", "101"),
    ],
)
def test_known_currency_codes_map_numeric_text_and_xlsx_values(
    raw_currency: object,
    expected_currency: str,
    expected_origin: str,
):
    record, errors = normalize(Moneda=raw_currency)

    assert errors == []
    assert record is not None
    assert record.operation.moneda == expected_currency
    assert record.detail.moneda_origen == expected_origin


def test_unknown_currency_is_preserved_without_canonical_capital_or_debt():
    record, errors = normalize(Moneda="999")

    assert errors == []
    assert record is not None
    assert record.operation.moneda is None
    assert record.operation.saldo_capital is None
    assert record.operation.deuda_total is None
    assert record.detail.moneda_origen == "999"
    assert record.detail.saldo_capital_mo == Decimal("1000.10")
    assert record.detail.saldo_capital_mn == Decimal("3500.20")


def test_usd_uses_only_foreign_currency_capital_for_total_debt():
    record, errors = normalize(Moneda=101)

    assert errors == []
    assert record is not None
    assert record.operation.moneda == "USD"
    assert record.operation.saldo_capital == Decimal("1000.10")
    assert record.operation.deuda_total == Decimal("1413.40")
    assert record.operation.deuda_total != Decimal("4913.60")
    assert record.detail.saldo_capital_mo == Decimal("1000.10")
    assert record.detail.saldo_capital_mn == Decimal("3500.20")


def test_confirmed_pen_debt_example_totals_619_36():
    record, errors = normalize(
        Moneda=0,
        **{
            "Saldo Capital MO": "9999.99",
            "Saldo Capital MN": "337.55",
            "Interés Vencido": "15.49",
            "Interés Compensatorio": "116.03",
            "Interés Moratorio": "0",
            "Seguros": "0",
            "Comisiones": "0",
            "Gastos Judiciales": "150.29",
        },
    )

    assert errors == []
    assert record is not None
    assert record.operation.saldo_capital == Decimal("337.55")
    assert record.operation.deuda_total == Decimal("619.36")
    assert record.operation.deuda_total != Decimal("10619.35")


def test_missing_debt_components_are_zero_without_hiding_present_values():
    record, errors = normalize(
        **{
            "Interés Vencido": None,
            "Interés Compensatorio": None,
            "Interés Moratorio": None,
            "Seguros": None,
            "Comisiones": None,
            "Gastos Judiciales": None,
        }
    )

    assert errors == []
    assert record is not None
    assert record.operation.saldo_capital == Decimal("3500.20")
    assert record.operation.deuda_total == Decimal("3500.20")


def test_missing_selected_capital_is_zero_for_debt_when_currency_is_known():
    record, errors = normalize(
        **{
            "Saldo Capital MN": None,
            "Interés Vencido": "15.49",
            "Interés Compensatorio": None,
            "Interés Moratorio": None,
            "Seguros": None,
            "Comisiones": None,
            "Gastos Judiciales": None,
        }
    )

    assert errors == []
    assert record is not None
    assert record.operation.moneda == "PEN"
    assert record.operation.saldo_capital is None
    assert record.operation.deuda_total == Decimal("15.49")


def test_debt_total_uses_decimal_without_binary_floating_point_error():
    record, errors = normalize(
        **{
            "Saldo Capital MN": "0.10",
            "Interés Vencido": "0.20",
            "Interés Compensatorio": None,
            "Interés Moratorio": None,
            "Seguros": None,
            "Comisiones": None,
            "Gastos Judiciales": None,
        }
    )

    assert errors == []
    assert record is not None
    assert record.operation.deuda_total == Decimal("0.30")


def test_debt_total_overflow_is_reported_as_a_controlled_row_error():
    record, errors = normalize(
        **{
            "Saldo Capital MN": "9999999999999.99",
            "Interés Vencido": "0.01",
            "Interés Compensatorio": None,
            "Interés Moratorio": None,
            "Seguros": None,
            "Comisiones": None,
            "Gastos Judiciales": None,
        }
    )

    assert record is None
    assert any(error.field == "deuda_total" for error in errors)


def test_specific_fields_reach_confianza_detail():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.detail.codigo_sucursal_credito == "001"
    assert record.detail.nombre_sucursal_credito == "AGENCIA CENTRO"
    assert record.detail.corredor == "CORREDOR UNO"
    assert record.detail.nombre_modulo_origen == "MÓDULO CARTERA"
    assert record.detail.estado_operacion == "CASTIGADO"


def test_excel_serial_cast_date_uses_the_workbook_epoch():
    values = source_values()
    values["Fecha Castigo"] = CellValue(43062, workbook_epoch=CALENDAR_WINDOWS_1900)

    record, errors = ConfianzaV1Profile().normalize(
        SourceRow(2, values),
        batch_id=77,
        source_file="confianza.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.operation.fecha_castigo == date(2017, 11, 23)
    assert record.source_values[CONFIANZA_SOURCE_COLUMNS.index("Fecha Castigo")] == "43062"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("26/07/2018", date(2018, 7, 26)),
        ("2018-10-24", date(2018, 10, 24)),
        (date(2020, 1, 2), date(2020, 1, 2)),
        (datetime(2020, 1, 3, 12, 30), date(2020, 1, 3)),
    ],
)
def test_cast_date_accepts_supported_text_and_excel_date_values(
    raw_value: object,
    expected: date,
):
    record, errors = normalize(**{"Fecha Castigo": raw_value})

    assert errors == []
    assert record is not None
    assert record.operation.fecha_castigo == expected


def test_address_preserves_original_value_and_geography():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert len(record.addresses) == 1
    address = record.addresses[0]
    assert address.tipo_direccion == "CLIENTE"
    assert address.direccion == "Av. Confianza 123"
    assert address.ubigeo == "150101"
    assert address.departamento == "LIMA"
    assert address.provincia == "LIMA"
    assert address.distrito == "LIMA"


@pytest.mark.parametrize(
    ("raw_phone", "expected"),
    [
        ("934043966", "934043966"),
        ("+51934043966", "934043966"),
        ("51 934 043 966", "934043966"),
    ],
)
def test_peruvian_mobile_phone_uses_shared_normalizer(raw_phone: str, expected: str):
    record, errors = normalize(Telefono=raw_phone)

    assert errors == []
    assert record is not None
    assert [(contact.tipo, contact.telefono) for contact in record.contacts] == [
        ("FUENTE", expected)
    ]


@pytest.mark.parametrize("raw_phone", ["61577350", "016733123", "999999999", ""])
def test_invalid_phone_does_not_reject_operation_or_create_contact(raw_phone: str):
    record, errors = normalize(Telefono=raw_phone)

    assert errors == []
    assert record is not None
    assert record.contacts == ()


@pytest.mark.parametrize("required_field", ["DNI", "Cuenta Cliente", "Operacion"])
def test_required_identity_field_is_reported_as_row_error(required_field: str):
    record, errors = normalize(**{required_field: ""})

    assert record is None
    assert any(error.field == required_field for error in errors)


@pytest.mark.parametrize(
    "financial_field",
    [
        "Saldo Capital MO",
        "Saldo Capital MN",
        "Interés Vencido",
        "Interés Compensatorio",
        "Interés Moratorio",
        "Seguros",
        "Comisiones",
        "Gastos Judiciales",
    ],
)
def test_invalid_financial_value_is_reported_as_row_error(financial_field: str):
    record, errors = normalize(**{financial_field: "NO NUMÉRICO"})

    assert record is None
    assert any(error.field == financial_field for error in errors)


def test_invalid_cast_date_is_reported_as_row_error():
    record, errors = normalize(**{"Fecha Castigo": "31/02/2020"})

    assert record is None
    assert any(error.field == "Fecha Castigo" for error in errors)


def test_bronze_hash_uses_exactly_the_27_source_positions_and_metadata_is_consistent():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    payload = json.dumps(
        ["cartera:confianza:v1", *record.source_values],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert len(record.source_values) == 27
    assert record.row_hash == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert record.batch_id == 77
    assert record.source_row == 2
    assert record.source_file == "confianza_sintetico.xlsx"
    assert record.ingested_at == FIXED_UTC

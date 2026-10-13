from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.domain.errors import StructuralFileError
from src.domain.models import (
    WANDOO_BRONZE_COLUMNS,
    WANDOO_SOURCE_COLUMNS,
    CellValue,
    SourceRow,
)
from src.profiles.carteras.wandoo import WandooV1Profile

FIXED_UTC = datetime(2026, 10, 13, 12, 0, 0)
EXCEL_EPOCH = datetime(1899, 12, 30)


def source_row(**overrides: object) -> SourceRow:
    values: dict[str, CellValue] = {
        column: CellValue(None) for column in WANDOO_SOURCE_COLUMNS
    }
    defaults: dict[str, object] = {
        "DNI": "00003862",
        "Numero de Prestamo": "7277-1292-001",
        "Recuento de préstamos ya pagados": 1,
        "Nacionalidad": "PE",
        "Saldo deudor": "337.55",
        "Fecha Últ. Pago": None,
        "Total soles pagados": None,
        "Departamento": " Loreto ",
        "Provincia": " Maynas ",
        "Distrito": " Iquitos ",
        "Edad": 42,
        "Días de mora": 18,
        "Producto crediticio": "Micropréstamo",
        "Fuente de Ingreso": "INDEPENDENT",
        "Estado Cobranza Actual": "Prejudicial externa",
        "Contactabilidad (Interna)": "Si",
        "Fecha otorgamiento crédito": CellValue(
            45905,
            workbook_epoch=EXCEL_EPOCH,
        ),
        "Actividad Laboral": "AGRICULTURAL",
        "Cosecha": "WANDOO_1",
    }
    defaults.update(overrides)
    for field, value in defaults.items():
        values[field] = value if isinstance(value, CellValue) else CellValue(value)
    return SourceRow(number=2, values=values)


def normalize(**overrides: object):
    return WandooV1Profile().normalize(
        source_row(**overrides),
        batch_id=77,
        source_file="wandoo_sintetico.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )


def test_contract_preserves_exact_19_headers_and_ascii_snake_case_bronze_columns():
    mapping = WandooV1Profile().build_header_map(WANDOO_SOURCE_COLUMNS)

    assert len(WANDOO_SOURCE_COLUMNS) == 19
    assert len(WANDOO_BRONZE_COLUMNS) == 19
    assert tuple(mapping) == WANDOO_SOURCE_COLUMNS
    assert all(column.isascii() for column in WANDOO_BRONZE_COLUMNS)
    assert all(column.replace("_", "").isalnum() and column == column.lower() for column in WANDOO_BRONZE_COLUMNS)


@pytest.mark.parametrize(
    "headers",
    [
        WANDOO_SOURCE_COLUMNS[:-1],
        (*WANDOO_SOURCE_COLUMNS, "EXTRA"),
        (WANDOO_SOURCE_COLUMNS[1], WANDOO_SOURCE_COLUMNS[0], *WANDOO_SOURCE_COLUMNS[2:]),
    ],
)
def test_contract_rejects_missing_extra_or_reordered_headers(headers: tuple[str, ...]):
    with pytest.raises(StructuralFileError, match="exactamente 19|posición"):
        WandooV1Profile().build_header_map(headers)


def test_identifiers_and_common_operation_mapping_are_preserved():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.entidad == "WANDOO"
    assert record.operation.documento_cliente == "00003862"
    assert record.operation.cuenta == "000003862"
    assert record.operation.operacion == "7277-1292-001"
    assert record.operation.identificador_origen is None
    assert record.operation.cosecha == "WANDOO_1"


def test_debtor_balance_maps_to_capital_debt_and_detail_without_double_counting():
    record, errors = normalize(**{"Saldo deudor": "1,234.56", "Días de mora": 27})

    assert errors == []
    assert record is not None
    assert isinstance(record.operation.saldo_capital, Decimal)
    assert record.operation.saldo_capital == Decimal("1234.56")
    assert record.operation.deuda_total == Decimal("1234.56")
    assert record.detail.saldo_deudor == Decimal("1234.56")
    assert record.operation.saldo_capital == record.operation.deuda_total
    assert record.operation.saldo_capital == record.detail.saldo_deudor
    assert record.operation.deuda_total == record.detail.saldo_deudor
    assert record.operation.deuda_total != Decimal("2469.12")
    assert record.operation.moneda is None
    assert record.operation.interes is None
    assert record.operation.mora is None
    assert record.operation.dias_atraso == 27
    assert record.detail.dias_mora == 27


def test_null_debtor_balance_remains_null_in_operation_and_detail():
    record, errors = normalize(**{"Saldo deudor": None})

    assert errors == []
    assert record is not None
    assert record.operation.saldo_capital is None
    assert record.operation.deuda_total is None
    assert record.detail.saldo_deudor is None


def test_optional_financial_and_activity_values_remain_null():
    record, errors = normalize(
        **{
            "Total soles pagados": None,
            "Fecha Últ. Pago": None,
            "Actividad Laboral": None,
        }
    )

    assert errors == []
    assert record is not None
    assert record.detail.total_soles_pagados is None
    assert record.detail.fecha_ultimo_pago is None
    assert record.detail.actividad_laboral is None


def test_excel_dates_use_workbook_epoch_and_reach_common_and_detail_fields():
    record, errors = normalize(
        **{
            "Fecha Últ. Pago": CellValue(45966, workbook_epoch=EXCEL_EPOCH),
            "Fecha otorgamiento crédito": CellValue(45905, workbook_epoch=EXCEL_EPOCH),
        }
    )

    assert errors == []
    assert record is not None
    assert record.detail.fecha_ultimo_pago == date(2025, 11, 5)
    assert record.detail.fecha_otorgamiento_credito == date(2025, 9, 5)
    assert record.operation.fecha_desembolso == date(2025, 9, 5)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2025, 9, 5), date(2025, 9, 5)),
        (datetime(2025, 9, 5, 15, 30), date(2025, 9, 5)),
        ("05/09/2025", date(2025, 9, 5)),
        ("2025-09-05", date(2025, 9, 5)),
        (None, None),
    ],
)
def test_grant_date_accepts_supported_representations(value: object, expected: date | None):
    record, errors = normalize(**{"Fecha otorgamiento crédito": value})

    assert errors == []
    assert record is not None
    assert record.detail.fecha_otorgamiento_credito == expected


def test_geography_is_trimmed_in_silver_but_original_text_is_preserved_in_bronze_values():
    record, errors = normalize(
        Departamento="Arequip ",
        Provincia=" Provincia sin corregir ",
        Distrito=" DISTRITO ",
    )

    assert errors == []
    assert record is not None
    assert record.operation.departamento == "Arequip"
    assert record.operation.provincia == "Provincia sin corregir"
    assert record.operation.distrito == "DISTRITO"
    assert record.source_values[WANDOO_SOURCE_COLUMNS.index("Departamento")] == "Arequip "
    assert len(record.addresses) == 1
    assert record.addresses[0].tipo_direccion == "CLIENTE"
    assert record.addresses[0].direccion is None
    assert record.addresses[0].departamento == "Arequip"


def test_source_specific_fields_are_preserved_in_detail_and_product_is_projected():
    record, errors = normalize(**{"Total soles pagados": "125.40"})

    assert errors == []
    assert record is not None
    assert record.operation.producto == "Micropréstamo"
    assert record.detail.producto_crediticio == "Micropréstamo"
    assert record.detail.recuento_prestamos_pagados == 1
    assert record.detail.nacionalidad == "PE"
    assert record.detail.total_soles_pagados == Decimal("125.40")
    assert record.detail.fuente_ingreso == "INDEPENDENT"
    assert record.detail.estado_cobranza_actual == "Prejudicial externa"
    assert record.detail.contactabilidad_interna == "Si"
    assert record.detail.actividad_laboral == "AGRICULTURAL"


def test_wandoo_creates_no_contacts_and_keeps_traceability():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.contacts == ()
    assert record.batch_id == 77
    assert record.source_row == 2
    assert record.source_file == "wandoo_sintetico.xlsx"
    assert record.ingested_at == FIXED_UTC
    assert len(record.row_hash) == 64


@pytest.mark.parametrize("field", ["DNI", "Numero de Prestamo"])
def test_required_identifier_errors_are_controlled(field: str):
    record, errors = normalize(**{field: None})

    assert record is None
    assert [error.field for error in errors] == [field]


@pytest.mark.parametrize("field", ["Saldo deudor", "Total soles pagados"])
def test_non_numeric_financial_value_is_a_controlled_row_error(field: str):
    record, errors = normalize(**{field: "NO NUMÉRICO"})

    assert record is None
    assert [error.field for error in errors] == [field]


def test_row_hash_uses_all_19_source_positions_deterministically():
    first, first_errors = normalize()
    repeated, repeated_errors = normalize()
    changed, changed_errors = normalize(**{"Actividad Laboral": "ARTIST"})

    assert first_errors == repeated_errors == changed_errors == []
    assert first is not None and repeated is not None and changed is not None
    assert len(first.source_values) == 19
    assert first.row_hash == repeated.row_hash
    assert first.row_hash != changed.row_hash

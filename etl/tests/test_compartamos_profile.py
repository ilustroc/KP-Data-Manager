from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl.utils.datetime import CALENDAR_WINDOWS_1900

from src.domain.errors import StructuralFileError
from src.domain.models import (
    COMPARTAMOS_BRONZE_COLUMNS,
    COMPARTAMOS_SOURCE_COLUMNS,
    CellValue,
    SourceRow,
)
from src.profiles.carteras.compartamos import CompartamosV1Profile

FIXED_UTC = datetime(2026, 10, 6, 21, 0, 0)


def source_values(**overrides: object) -> dict[str, CellValue]:
    values: dict[str, object] = {column: None for column in COMPARTAMOS_SOURCE_COLUMNS}
    values.update(
        {
            "Ctacliente": "0012345678",
            "Operación": "0000456789",
            "Documento": "AUX-001",
            "NomCliente": "Cliente Sintético",
            "oficina Agencia": "Agencia Centro",
            "Skapital": "\u00a02,166.36\u00a0",
            "IntComp": "1,154.68",
            "IntMoratorio": "10.25",
            "Deuda total": "3,321.04",
            "Moneda": "SOLES",
            "TipCambio": "0",
            "SKSoles": "3,321.04",
            "Lote": "L-01",
            "Empresa": "Empresa Sintética",
            "FecCastigo": "6/10/2026",
            "FecDesembolso": "2001",
            "Dias_Atraso": "45",
            "LinNeg": "MICROEMPRESA",
            "NumDoc": "00112233",
            "NomDistrito": "Distrito Uno",
            "NomProvincia": "Provincia Uno",
            "NomDepartamento": "Departamento Uno",
            "FecNacimiento": "9/7/1985",
            "Direccion Cliente": "Av. Cliente 100",
            "Direccion Negocio": "Jr. Negocio 200",
            "Telefono1": "991524863",
            "Telefono2": None,
            "Telefono3": "#958622606",
            "Telefono4": "999678847.",
            "Cosecha": " COMP 01 ",
        }
    )
    values.update(overrides)
    return {column: CellValue(value) for column, value in values.items()}


def normalize(**overrides: object):
    return CompartamosV1Profile().normalize(
        SourceRow(2, source_values(**overrides)),
        batch_id=55,
        source_file="compartamos_sintetico.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )


def test_header_requires_exact_30_positions_and_trims_unicode_padding():
    headers = [f"\u00a0 {header} \u00a0" for header in COMPARTAMOS_SOURCE_COLUMNS]

    mapping = CompartamosV1Profile().build_header_map(headers)

    assert len(COMPARTAMOS_SOURCE_COLUMNS) == 30
    assert len(COMPARTAMOS_BRONZE_COLUMNS) == 30
    assert "SSS" not in COMPARTAMOS_SOURCE_COLUMNS
    assert "SSS" not in COMPARTAMOS_BRONZE_COLUMNS
    assert tuple(mapping) == COMPARTAMOS_SOURCE_COLUMNS


@pytest.mark.parametrize(
    "headers",
    [
        COMPARTAMOS_SOURCE_COLUMNS[:-1],
        (*COMPARTAMOS_SOURCE_COLUMNS, "EXTRA"),
        (
            COMPARTAMOS_SOURCE_COLUMNS[1],
            COMPARTAMOS_SOURCE_COLUMNS[0],
            *COMPARTAMOS_SOURCE_COLUMNS[2:],
        ),
    ],
)
def test_header_rejects_missing_extra_or_reordered_columns(headers: tuple[str, ...]):
    with pytest.raises(StructuralFileError):
        CompartamosV1Profile().build_header_map(headers)


def test_obsolete_31_column_structure_with_sss_is_rejected():
    obsolete_headers = (
        *COMPARTAMOS_SOURCE_COLUMNS[:3],
        "SSS",
        *COMPARTAMOS_SOURCE_COLUMNS[3:],
    )

    with pytest.raises(StructuralFileError, match="30 columnas"):
        CompartamosV1Profile().build_header_map(obsolete_headers)


def test_identity_common_values_money_currency_and_detail_are_mapped():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.entidad == "COMPARTAMOS"
    assert record.operation.documento_cliente == "00112233"
    assert record.operation.cuenta == "0012345678"
    assert record.operation.operacion == "0000456789"
    assert record.operation.identificador_origen is None
    assert record.operation.moneda == "PEN"
    assert record.operation.saldo_capital == Decimal("2166.36")
    assert record.operation.deuda_total == Decimal("3321.04")
    assert record.operation.interes == Decimal("1154.68")
    assert record.operation.mora == Decimal("10.25")
    assert record.detail.documento_fuente == "AUX-001"
    assert record.detail.tipo_cambio == Decimal("0.000000")
    assert record.detail.saldo_capital_soles == Decimal("3321.04")
    assert record.detail.lote == "L-01"
    assert record.detail.empresa == "Empresa Sintética"
    assert record.detail.anio_desembolso == 2001
    assert record.operation.fecha_desembolso is None


def test_numeric_identifiers_are_safe_text_without_dot_zero():
    record, errors = normalize(NumDoc=112233, Ctacliente=12345678, Operación=456789)

    assert errors == []
    assert record is not None
    assert record.operation.documento_cliente == "112233"
    assert record.operation.cuenta == "12345678"
    assert record.operation.operacion == "456789"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [(2000, 2000), ("2001", 2001), (None, None), ("", None)],
)
def test_disbursement_year_accepts_integer_text_and_blank(
    raw_value: object,
    expected: int | None,
):
    record, errors = normalize(FecDesembolso=raw_value)

    assert errors == []
    assert record is not None
    assert record.detail.anio_desembolso == expected
    assert record.operation.fecha_desembolso is None
    expected_source = None if expected is None else str(expected)
    assert (
        record.source_values[COMPARTAMOS_SOURCE_COLUMNS.index("FecDesembolso")]
        == expected_source
    )


def test_xlsx_integral_float_is_a_year_and_not_an_excel_serial_date():
    values = source_values()
    values["FecDesembolso"] = CellValue(
        2002.0,
        is_xlsx_float=True,
        workbook_epoch=CALENDAR_WINDOWS_1900,
    )

    record, errors = CompartamosV1Profile().normalize(
        SourceRow(2, values),
        batch_id=55,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.detail.anio_desembolso == 2002
    assert record.operation.fecha_desembolso is None
    assert record.source_values[COMPARTAMOS_SOURCE_COLUMNS.index("FecDesembolso")] == "2002"


@pytest.mark.parametrize(
    ("logical_year", "xlsx_value"),
    [
        (2000, date(1905, 6, 22)),
        (2001, datetime(1905, 6, 23)),
        (2010, datetime(1905, 7, 2)),
        (2020, datetime(1905, 7, 12)),
        (2021, datetime(1905, 7, 13)),
        (2022, datetime(1905, 7, 14)),
    ],
)
def test_xlsx_date_formatted_year_is_recovered_from_workbook_serial(
    logical_year: int,
    xlsx_value: date | datetime,
):
    values = source_values()
    values["FecDesembolso"] = CellValue(
        xlsx_value,
        workbook_epoch=CALENDAR_WINDOWS_1900,
    )

    record, errors = CompartamosV1Profile().normalize(
        SourceRow(2, values),
        batch_id=55,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.operation.fecha_desembolso is None
    assert record.detail.anio_desembolso == logical_year
    assert record.operation.fecha_desembolso != date(1905, 7, 14)


def test_modern_xlsx_disbursement_date_remains_a_real_date():
    values = source_values()
    values["FecDesembolso"] = CellValue(
        datetime(2024, 3, 30, 10, 15),
        workbook_epoch=CALENDAR_WINDOWS_1900,
    )

    record, errors = CompartamosV1Profile().normalize(
        SourceRow(2, values),
        batch_id=55,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.operation.fecha_desembolso == date(2024, 3, 30)
    assert record.detail.anio_desembolso == 2024


@pytest.mark.parametrize(
    ("raw_value", "expected_date", "expected_year"),
    [
        (date(2024, 3, 30), date(2024, 3, 30), 2024),
        (datetime(2024, 2, 29, 14, 30), date(2024, 2, 29), 2024),
        ("2024-03-30", date(2024, 3, 30), 2024),
        ("30/03/2024", date(2024, 3, 30), 2024),
    ],
)
def test_full_disbursement_date_preserves_date_and_also_extracts_year(
    raw_value: object,
    expected_date: date,
    expected_year: int,
):
    record, errors = normalize(FecDesembolso=raw_value)

    assert errors == []
    assert record is not None
    assert record.operation.fecha_desembolso == expected_date
    assert record.detail.anio_desembolso == expected_year


def test_numeric_year_is_never_interpreted_as_excel_serial_date():
    record, errors = normalize(FecDesembolso=2000)

    assert errors == []
    assert record is not None
    assert record.operation.fecha_desembolso is None
    assert record.operation.fecha_desembolso != date(1905, 6, 22)
    assert record.detail.anio_desembolso == 2000


@pytest.mark.parametrize("raw_value", [2000.5, 1899, 2101, "ABC"])
def test_invalid_disbursement_year_is_a_row_error(raw_value: object):
    record, errors = normalize(FecDesembolso=raw_value)

    assert record is None
    assert any(error.field == "FecDesembolso" for error in errors)


def test_castigo_and_birth_dates_keep_their_date_semantics():
    values = source_values(FecCastigo=datetime(2026, 10, 6, 12, 0))
    values["FecNacimiento"] = CellValue(date(1985, 7, 9))

    record, errors = CompartamosV1Profile().normalize(
        SourceRow(2, values),
        batch_id=55,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.operation.fecha_castigo == date(2026, 10, 6)
    assert record.operation.fecha_desembolso is None
    assert record.detail.anio_desembolso == 2001
    assert record.detail.fecha_nacimiento == date(1985, 7, 9)


def test_invalid_date_is_a_row_error():
    record, errors = normalize(FecNacimiento="31/02/2020")

    assert record is None
    assert any(error.field == "FecNacimiento" for error in errors)


def test_contacts_normalize_noise_filter_placeholder_and_deduplicate():
    record, errors = normalize(
        Telefono1="#952999016",
        Telefono2="999999999",
        Telefono3="952 999 016",
        Telefono4="+51912631273",
    )

    assert errors == []
    assert record is not None
    assert [(item.orden, item.tipo, item.telefono) for item in record.contacts] == [
        (1, "FUENTE", "952999016"),
        (2, "FUENTE", "912631273"),
    ]


def test_only_peruvian_mobile_phones_are_kept_in_source_order():
    record, errors = normalize(
        Telefono1='"934043966"',
        Telefono2="937 519531",
        Telefono3="(01) 673-3123",
        Telefono4="934043966.",
    )

    assert errors == []
    assert record is not None
    assert [item.telefono for item in record.contacts] == [
        "934043966",
        "937519531",
    ]


def test_four_distinct_phones_create_four_contacts():
    record, errors = normalize(
        Telefono1="900000001",
        Telefono2="900000002",
        Telefono3="900000003",
        Telefono4="900000004",
    )

    assert errors == []
    assert record is not None
    assert [(item.orden, item.telefono) for item in record.contacts] == [
        (1, "900000001"),
        (2, "900000002"),
        (3, "900000003"),
        (4, "900000004"),
    ]


def test_only_nonempty_client_and_business_addresses_are_created():
    record, errors = normalize(**{"Direccion Negocio": " \u00a0 "})

    assert errors == []
    assert record is not None
    assert [(item.tipo_direccion, item.direccion) for item in record.addresses] == [
        ("CLIENTE", "Av. Cliente 100"),
    ]
    assert record.addresses[0].departamento is None


def test_row_hash_uses_all_30_source_positions_and_metadata():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert len(record.source_values) == 30
    expected_payload = json.dumps(
        ["cartera:compartamos:v1", *record.source_values],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert record.row_hash == hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
    assert record.batch_id == 55
    assert record.source_row == 2
    assert record.source_file == "compartamos_sintetico.xlsx"
    assert record.ingested_at == FIXED_UTC


def test_xlsx_float_money_noise_remains_supported():
    values = source_values()
    values["Skapital"] = CellValue(216791.33000000002, is_xlsx_float=True)

    record, errors = CompartamosV1Profile().normalize(
        SourceRow(2, values),
        batch_id=55,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.operation.saldo_capital == Decimal("216791.33")

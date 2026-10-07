from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl.utils.datetime import CALENDAR_WINDOWS_1900

from src.domain.errors import StructuralFileError
from src.domain.models import (
    CAJA_AREQUIPA_SOURCE_COLUMNS,
    CAJA_AREQUIPA_SOURCE_HEADERS,
    CellValue,
    SourceRow,
)
from src.profiles.carteras.caja_arequipa import CajaArequipaV1Profile

FIXED_UTC = datetime(2026, 10, 6, 20, 0, 0)


def source_values(**overrides: object) -> dict[str, CellValue]:
    values: dict[str, object] = {column: None for column in CAJA_AREQUIPA_SOURCE_COLUMNS}
    values.update(
        {
            "NRO_DOC_TIT_1": "00001234",
            "NRO_DOC_TIT_2": "00001234",
            "AGENCIA": "Arequipa Centro",
            "ANALISTA": "Analista Uno",
            "TITULAR": "Cliente Sintético",
            "CUENTA": "001804548",
            "OPERACION": "002435410",
            "TIPO_CONTABLE": "VENCIDO",
            "TIP_SBS": "MICROEMPRESA",
            "MONEDA": "S/",
            "SALDO_CAPITAL": "1,250.50",
            "FEC_ULT_PAG": "25/10/2016",
            "DIAS_ATRASO": "30",
            "CUO_PAG": "4",
            "DIR_LEGAL": "Av. Sintética 100",
            "REF_LEGAL": "Frente a un parque",
            "DIS_LEGAL": "Distrito Uno",
            "TEL_TIT": "961593795|945944334",
            "DIR_GES": " ",
            "REF_GES": None,
            "DIS_GES": None,
            "TEL_GES": "   ",
            "ACTIVIDAD": "Comercio",
            "DIR_NEG": "Jr. Negocio 200",
            "DIS_NEG": "Distrito Dos",
            "NRO_AVALES": "1",
            "NOM_AVAL": "Aval Sintético",
            "DIR_AVAL": "Calle Aval 300",
            "REF_AVAL": "Referencia aval",
            "DIS_AVAL": "Distrito Tres",
            "TIP_DOC_TIT": "DNI",
            "TIP_DOC_AVAL": "DNI",
            "NRO_DOC_AVAL": "00005678",
            "TEL_AVAL": "900 111 222|900333444",
            "COD_SBS": "SBS-01",
            "FEC_DES": "2015-12-10",
            "MTO_DES": "2,000.00",
            "INT_MORATORIO": "12.50",
            "INT_COMP": "20.25",
            "ICV": "1.00",
            "SEGUROS": "2.00",
            "PENALIDAD": "3.00",
            "OTROS_RUBROS": "4.00",
            "TOT_DEUDA": "1,290.25",
            "CAL_SBS": "NORMAL",
            "PROVISION": "100",
            "FEC_ING_JUD": "  /  /  ",
            "FEC_ING_CAS": "2017-05-29",
            "REFINANCIADO": "NO",
            "TIP_GAR1": "HIPOTECA",
            "MTO_GAR1": "10,000.00",
            "TIP_GAR2": "DOCUMENTARIA",
            "MTO_GAR2": None,
            "UBIGEO": "040101",
            "DEPARTAMENTO": "AREQUIPA",
            "PROVINCIA": "AREQUIPA",
            "DISTRITO": "AREQUIPA",
            "COSECHA": "2026-10",
            "CADENA": "CAD-001",
        }
    )
    values.update(overrides)
    return {column: CellValue(value) for column, value in values.items()}


def normalize(**overrides: object):
    return CajaArequipaV1Profile().normalize(
        SourceRow(number=2, values=source_values(**overrides)),
        batch_id=44,
        source_file="caja_arequipa_sintetico.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )


def test_header_requires_exact_67_positions_and_preserves_duplicate_document():
    mapping = CajaArequipaV1Profile().build_header_map(
        [f" {header} " for header in CAJA_AREQUIPA_SOURCE_HEADERS]
    )

    assert len(mapping) == 67
    assert mapping["NRO_DOC_TIT_1"] == 0
    assert mapping["NRO_DOC_TIT_2"] == 30


@pytest.mark.parametrize(
    "headers",
    [
        CAJA_AREQUIPA_SOURCE_HEADERS[:-1],
        (*CAJA_AREQUIPA_SOURCE_HEADERS, "EXTRA"),
        (
            CAJA_AREQUIPA_SOURCE_HEADERS[1],
            CAJA_AREQUIPA_SOURCE_HEADERS[0],
            *CAJA_AREQUIPA_SOURCE_HEADERS[2:],
        ),
    ],
)
def test_header_rejects_missing_extra_or_reordered_columns(headers: tuple[str, ...]):
    with pytest.raises(StructuralFileError):
        CajaArequipaV1Profile().build_header_map(headers)


def test_normalization_maps_common_and_specific_silver_models():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.entidad == "CAJA_AREQUIPA"
    assert record.operation.documento_cliente == "00001234"
    assert record.operation.cuenta == "001804548"
    assert record.operation.operacion == "002435410"
    assert record.operation.identificador_origen == "CAD-001"
    assert record.operation.moneda == "PEN"
    assert record.operation.saldo_capital == Decimal("1250.50")
    assert record.operation.deuda_total == Decimal("1290.25")
    assert record.operation.interes == Decimal("20.25")
    assert record.operation.mora == Decimal("12.50")
    assert record.operation.fecha_desembolso == date(2015, 12, 10)
    assert record.operation.fecha_castigo == date(2017, 5, 29)
    assert record.operation.dias_atraso == 30
    assert record.detail.provision == Decimal("100.0000")
    assert record.detail.fecha_ingreso_judicial is None
    assert len(record.source_values) == 67
    assert record.batch_id == 44
    assert record.source_row == 2
    assert len(record.row_hash) == 64


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("00001234", "00001234", "00001234"),
        (None, "00001234", "00001234"),
        ("00001234", None, "00001234"),
    ],
)
def test_duplicate_document_uses_equal_or_single_available_value(first, second, expected):
    record, errors = normalize(NRO_DOC_TIT_1=first, NRO_DOC_TIT_2=second)

    assert errors == []
    assert record is not None
    assert record.operation.documento_cliente == expected


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        ("00001234", "00005678", "valores diferentes"),
        (None, None, "obligatorio"),
    ],
)
def test_duplicate_document_conflict_or_absence_is_a_row_error(first, second, message):
    record, errors = normalize(NRO_DOC_TIT_1=first, NRO_DOC_TIT_2=second)

    assert record is None
    assert any(error.field == "NRO_DOC_TIT" and message in error.message for error in errors)


def test_numeric_xlsx_account_and_operation_become_safe_text():
    record, errors = normalize(CUENTA=1804548, OPERACION=2435410)

    assert errors == []
    assert record is not None
    assert record.operation.cuenta == "1804548"
    assert record.operation.operacion == "2435410"


def test_phones_expand_in_deterministic_order_and_remove_internal_whitespace():
    record, errors = normalize(TEL_TIT="961593795|945944334", TEL_GES="937 519531")

    assert errors == []
    assert record is not None
    assert [(item.orden, item.tipo, item.telefono) for item in record.contacts] == [
        (1, "TITULAR", "961593795"),
        (2, "TITULAR", "945944334"),
        (3, "GESTION", "937519531"),
    ]
    assert record.guarantor is not None
    assert record.guarantor.telefono == "900111222|900333444"


def test_only_nonempty_holder_addresses_are_created_without_inferred_geography():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert [address.tipo_direccion for address in record.addresses] == ["LEGAL", "NEGOCIO"]
    assert all(address.ubigeo is None and address.departamento is None for address in record.addresses)


def test_guarantor_is_preserved_even_when_reported_count_is_zero():
    record, errors = normalize(NRO_AVALES=0)

    assert errors == []
    assert record is not None and record.guarantor is not None
    assert record.guarantor.cantidad_reportada == 0
    assert record.guarantor.documento_aval == "00005678"


def test_empty_guarantor_block_creates_no_row():
    record, errors = normalize(
        NRO_AVALES=0,
        NOM_AVAL=None,
        TIP_DOC_AVAL=None,
        NRO_DOC_AVAL=None,
        TEL_AVAL=None,
        DIR_AVAL=None,
        REF_AVAL=None,
        DIS_AVAL=None,
    )

    assert errors == []
    assert record is not None
    assert record.guarantor is None


def test_six_guarantees_and_partial_values_are_preserved():
    overrides = {}
    for order in range(1, 7):
        overrides[f"TIP_GAR{order}"] = f"GARANTIA {order}" if order != 6 else None
        overrides[f"MTO_GAR{order}"] = f"{order * 100}.00" if order != 5 else None

    record, errors = normalize(**overrides)

    assert errors == []
    assert record is not None
    assert len(record.guarantees) == 6
    assert record.guarantees[4].tipo_garantia == "GARANTIA 5"
    assert record.guarantees[4].monto is None
    assert record.guarantees[5].tipo_garantia is None
    assert record.guarantees[5].monto == Decimal("600.00")


@pytest.mark.parametrize(
    ("serial", "expected"),
    [(42668, date(2016, 10, 25)), (42348, date(2015, 12, 10)), (42884, date(2017, 5, 29))],
)
def test_excel_serial_dates_use_the_workbook_epoch(serial: int, expected: date):
    values = source_values()
    values["FEC_DES"] = CellValue(serial, workbook_epoch=CALENDAR_WINDOWS_1900)

    record, errors = CajaArequipaV1Profile().normalize(
        SourceRow(2, values),
        batch_id=44,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.operation.fecha_desembolso == expected


def test_native_datetime_and_date_placeholder_are_supported():
    record, errors = normalize(FEC_ULT_PAG=datetime(2020, 1, 2, 12, 30), FEC_ING_JUD=" / / ")

    assert errors == []
    assert record is not None
    assert record.detail.fecha_ultimo_pago == date(2020, 1, 2)
    assert record.detail.fecha_ingreso_judicial is None


def test_xlsx_float_noise_is_accepted_but_genuine_extra_decimals_fail():
    values = source_values()
    values["SALDO_CAPITAL"] = CellValue(216791.33000000002, is_xlsx_float=True)
    record, errors = CajaArequipaV1Profile().normalize(
        SourceRow(2, values),
        batch_id=44,
        source_file="fixture.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )
    invalid, invalid_errors = normalize(SALDO_CAPITAL="100.123")

    assert errors == []
    assert record is not None and record.operation.saldo_capital == Decimal("216791.33")
    assert invalid is None
    assert any(error.field == "SALDO_CAPITAL" for error in invalid_errors)


def test_hash_includes_both_document_positions():
    first, _ = normalize()
    second, _ = normalize(NRO_DOC_TIT_1=None, NRO_DOC_TIT_2="00001234")

    assert first is not None and second is not None
    assert first.operation.documento_cliente == second.operation.documento_cliente
    assert first.row_hash != second.row_hash

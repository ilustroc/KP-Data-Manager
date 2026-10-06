from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.domain.errors import StructuralFileError
from src.domain.models import BBVA_SOURCE_COLUMNS, CellValue, SourceRow
from src.profiles.carteras.bbva import BbvaV1Profile
from src.profiles.carteras.contracts import wandoo_derived_account

FIXED_UTC = datetime(2026, 10, 6, 19, 0, 0)


def source_values(**overrides: object) -> dict[str, CellValue]:
    values: dict[str, object] = {column: None for column in BBVA_SOURCE_COLUMNS}
    values.update(
        {
            "CODCENTRAL": "14898140",
            "CONTRATO": "00110310039600774622",
            "DOCUMENTO": "DOC-FINANCIERO-01",
            "NOMBRE": "Cliente Anónimo",
            "MONEDA": "PEN",
            "Suma de Importes": "1,250.50",
            "Suma de INTERES": "20.25",
            "Suma de MORA": "5.10",
            "FECHAVEN": "31/10/2026",
            "PRODUCTO": "P01",
            "DESCPROD": "Producto de prueba",
            "OFICINA": "001",
            "NOMB_OF": "Oficina Centro",
            "TERRITORIO": "LIMA",
            "tipodoc": "DNI",
            "numdoc": "01116950",
            "direccion": "Av. Ejemplo 123",
            "REFE": "Frente al parque",
            "referencia1": "Puerta azul",
            "referencia2": "Piso 2",
            "ubicacion": "Centro",
            "codpostal": "01501",
            "ubigeo": "150101",
            "dpto": "LIMA",
            "provincia": "LIMA",
            "distrito": "LIMA",
            "tipofono1": "MOVIL",
            "prefijo1": "51",
            "fono1": "0987654321",
            "extension1": "0000",
            "tipofono2": "FIJO",
            "prefijo2": "01",
            "fono2": "01234567",
            "extension2": "123",
            "COSECHA": "BBVA1",
        }
    )
    values.update(overrides)
    return {column: CellValue(value) for column, value in values.items()}


def normalize(**overrides: object):
    return BbvaV1Profile().normalize(
        SourceRow(number=2, values=source_values(**overrides)),
        batch_id=15,
        source_file="BBVA_OCTUBRE.xlsx",
        ingested_at=FIXED_UTC,
        error_value_max_length=100,
    )


def test_headers_accept_exact_bbva_v1_structure():
    mapping = BbvaV1Profile().build_header_map(list(BBVA_SOURCE_COLUMNS))

    assert tuple(mapping) == BBVA_SOURCE_COLUMNS


def test_missing_required_header_is_rejected():
    headers = [header for header in BBVA_SOURCE_COLUMNS if header != "numdoc"]

    with pytest.raises(StructuralFileError, match="numdoc"):
        BbvaV1Profile().build_header_map(headers)


def test_extra_header_is_rejected_as_incompatible_profile():
    with pytest.raises(StructuralFileError, match="COLUMNA_NUEVA"):
        BbvaV1Profile().build_header_map([*BBVA_SOURCE_COLUMNS, "COLUMNA_NUEVA"])


def test_confirmed_identity_mapping_preserves_text_and_origin_document():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.documento_cliente == "01116950"
    assert record.operation.cuenta == "14898140"
    assert record.operation.operacion == "00110310039600774622"
    assert record.operation.identificador_origen == "DOC-FINANCIERO-01"
    assert record.source_values[BBVA_SOURCE_COLUMNS.index("DOCUMENTO")] == "DOC-FINANCIERO-01"


def test_same_customer_with_two_contracts_produces_distinct_operations():
    first, _ = normalize(CONTRATO="00110310039600774622")
    second, _ = normalize(CONTRATO="00110310039600774623")

    assert first is not None and second is not None
    assert first.operation.documento_cliente == second.operation.documento_cliente
    assert first.operation.operacion != second.operation.operacion
    assert first.row_hash != second.row_hash


def test_money_date_currency_and_harvest_are_normalized_without_derived_debt():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.operation.moneda == "PEN"
    assert record.operation.saldo_capital == Decimal("1250.50")
    assert record.operation.interes == Decimal("20.25")
    assert record.operation.mora == Decimal("5.10")
    assert record.operation.fecha_vencimiento == date(2026, 10, 31)
    assert record.operation.cosecha == "BBVA1"


@pytest.mark.parametrize(
    ("field", "value"),
    [("Suma de Importes", "S/XYZ"), ("Suma de INTERES", "10.123"), ("Suma de MORA", "x")],
)
def test_invalid_money_creates_row_error(field: str, value: str):
    record, errors = normalize(**{field: value})

    assert record is None
    assert field in {error.field for error in errors}


def test_invalid_due_date_creates_row_error():
    record, errors = normalize(FECHAVEN="31/02/2026")

    assert record is None
    assert "FECHAVEN" in {error.field for error in errors}


def test_phones_are_expanded_to_rows_and_empty_phone_does_not_use_extension():
    record, errors = normalize(fono3="", extension3="0000")

    assert errors == []
    assert record is not None
    assert [contact.telefono for contact in record.contacts] == ["0987654321", "01234567"]
    assert record.contacts[0].extension == "0000"
    assert record.contacts[1].orden == 2


def test_address_is_normalized_as_principal_with_geography():
    record, errors = normalize()

    assert errors == []
    assert record is not None and record.address is not None
    assert record.address.tipo_direccion == "PRINCIPAL"
    assert record.address.direccion == "Av. Ejemplo 123"
    assert record.address.referencia == "Frente al parque"
    assert record.address.ubigeo == "150101"
    assert record.address.departamento == "LIMA"
    assert record.address.provincia == "LIMA"
    assert record.address.distrito == "LIMA"


def test_traceability_metadata_and_hash_are_populated():
    record, errors = normalize()

    assert errors == []
    assert record is not None
    assert record.batch_id == 15
    assert record.source_row == 2
    assert record.source_file == "BBVA_OCTUBRE.xlsx"
    assert record.ingested_at == FIXED_UTC
    assert len(record.row_hash) == 64


@pytest.mark.parametrize(
    ("document", "account"),
    [
        ("71341129", "071341129"),
        ("46009131", "046009131"),
        ("09755878", "009755878"),
    ],
)
def test_wandoo_contract_adds_exactly_one_zero(document: str, account: str):
    assert wandoo_derived_account(document) == account

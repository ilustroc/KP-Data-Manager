from datetime import date, datetime

import pytest

from src.domain.models import BatchRecord, CellValue, SearchSourceRow
from src.profiles.search.telefonos import TelefonosV1Normalizer


HEADERS = ("DOCUMENTO", "TELEFONO", "OPERADOR", "FECHA DATA")
TARGETS = ("documento", "telefono", "operador_raw", "fecha_data")


def phone_batch() -> BatchRecord:
    return BatchRecord(
        batch_id=30,
        tipo="SEARCH",
        entidad=None,
        perfil_version="1",
        archivo_original="telefonos.xlsx",
        archivo_ruta="imports/telefonos.xlsx",
        archivo_extension="xlsx",
        estado="PENDIENTE",
        archivo_sha256=None,
        dataset_code="TELEFONOS",
        source_code="BASE_TELEFONOS",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )


def normalize(phone="934043966", operator="MOVISTAR NOVIEMBRE 2024", data="2024-11-01", document="00003862"):
    values = tuple(CellValue(value) for value in (document, phone, operator, data))
    row = SearchSourceRow(
        number=2,
        headers=HEADERS,
        cells=values,
        mapped_values=dict(zip(TARGETS, values, strict=True)),
    )
    return TelefonosV1Normalizer(100).normalize(row, phone_batch(), datetime(2026, 10, 15))


@pytest.mark.parametrize("phone", ["934043966", "912345678", "987654321"])
def test_valid_phone_is_preserved_as_text(phone):
    _, record, errors = normalize(phone=phone)
    assert errors == []
    assert record is not None and record.telefono == phone


@pytest.mark.parametrize(
    "phone",
    ["93404396", "9340439660", "123456789", "900000000", "911111111", "999999999", "93404A966"],
)
def test_invalid_phone_is_rejected(phone):
    _, record, errors = normalize(phone=phone)
    assert record is None
    assert [error.message for error in errors] == ["PHONE_INVALID"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MOVISTAR NOVIEMBRE 2024", "MOVISTAR"),
        ("SEPTIEMBRE MOVISTAR 2020", "MOVISTAR"),
        ("2020 MOVISTAR SEPTIEMBRE", "MOVISTAR"),
        ("DATA CLARO AGOSTO 2026", "CLARO"),
        ("JULIO ENTEL 2026", "ENTEL"),
        ("BITEL DICIEMBRE 2025", "BITEL"),
        (" entel   julio 2026 ", "ENTEL"),
        ("MINSA MARZO 2026", "MINSA"),
        ("FLASH MOBILE ENERO 2026", "FLASH MOBILE"),
        ("GUINEA MOBILE MAYO 2026", "GUINEA MOBILE"),
    ],
)
def test_operator_is_homologated_from_the_start_of_text(raw, expected):
    _, record, errors = normalize(operator=raw)
    assert errors == []
    assert record is not None
    assert record.operador == expected
    assert record.operador_raw == " ".join(raw.split())


def test_unknown_operator_is_invalid():
    _, record, errors = normalize(operator="OTRO ENERO 2026")
    assert record is None
    assert [error.message for error in errors] == ["OPERATOR_INVALID"]


def test_two_distinct_operators_are_ambiguous():
    _, record, errors = normalize(operator="MOVISTAR CLARO 2025")
    assert record is None
    assert [error.message for error in errors] == ["OPERATOR_AMBIGUOUS"]


def test_operator_match_respects_word_boundaries():
    _, record, errors = normalize(operator="PREMOVISTARX 2025")
    assert record is None
    assert [error.message for error in errors] == ["OPERATOR_INVALID"]


@pytest.mark.parametrize("value", [date(2026, 8, 2), datetime(2026, 8, 2, 12), "2026-08-02"])
def test_typed_or_iso_date_is_accepted(value):
    _, record, errors = normalize(data=value)
    assert errors == []
    assert record is not None and record.fecha_data == date(2026, 8, 2)


@pytest.mark.parametrize("value", [None, "", "02/08/2026", "invalid"])
def test_empty_or_non_iso_date_is_invalid(value):
    _, record, errors = normalize(data=value)
    assert record is None
    assert [error.message for error in errors] == ["DATE_INVALID"]


def test_hashes_are_deterministic_and_cover_normalized_operator():
    raw_a, record_a, _ = normalize(operator="movistar   noviembre 2024")
    raw_b, record_b, _ = normalize(operator="movistar   noviembre 2024")
    assert raw_a.row_hash == raw_b.row_hash
    assert record_a is not None and record_b is not None
    assert record_a.record_hash == record_b.record_hash
    _, different, _ = normalize(operator="MOVISTAR DICIEMBRE 2024")
    assert different is not None
    assert record_a.record_hash != different.record_hash

from __future__ import annotations

from datetime import datetime

import pytest

from src.domain.models import BatchRecord, CellValue, SearchSourceRow
from src.domain.search_hashing import canonical_raw_payload, row_hash
from src.profiles.search.personas import PersonasV1Normalizer


HEADERS = (
    "DOCUMENTO",
    "PATERNO",
    "MATERNO",
    "NOMBRES",
    "NACIMIENTO",
    "DIRECCION",
    "SEXO",
    "ESTADO CIVIL",
    "PADRE",
    "MADRE",
)
TARGETS = (
    "documento",
    "paterno",
    "materno",
    "nombres",
    "fecha_nacimiento",
    "direccion_origen",
    "sexo",
    "estado_civil",
    "padre",
    "madre",
)


def search_batch() -> BatchRecord:
    return BatchRecord(
        batch_id=10,
        tipo="SEARCH",
        estado="PENDIENTE",
        archivo_original="personas.xlsx",
        archivo_ruta="2026/10/10/personas.xlsx",
        archivo_extension="xlsx",
        archivo_sha256=None,
        perfil_version="1",
        dataset_code="PERSONAS",
        source_code="BASE_PERSONAS",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )


def source_row(document="00003862", birth="2000-01-02", sex=2) -> SearchSourceRow:
    values = (
        CellValue(document, number_format="@"),
        CellValue(" PEREZ "),
        CellValue("LOPEZ"),
        CellValue("ANA"),
        CellValue(birth),
        CellValue("CALLE 1"),
        CellValue(sex),
        CellValue("SOLTERO"),
        CellValue("JUAN"),
        CellValue("MARIA"),
    )
    return SearchSourceRow(2, HEADERS, values, dict(zip(TARGETS, values, strict=True)))


def test_personas_normalization_preserves_dni_and_source_sex_code():
    normalizer = PersonasV1Normalizer(100)

    raw, person, errors = normalizer.normalize(
        source_row(), search_batch(), datetime(2026, 10, 14, 12, 0)
    )

    assert errors == []
    assert person is not None
    assert person.documento == "00003862"
    assert person.sexo == "2"
    assert person.nombre_completo == "ANA PEREZ LOPEZ"
    assert person.fecha_nacimiento.isoformat() == "2000-01-02"
    assert raw.row_hash == row_hash(raw.raw_payload)


@pytest.mark.parametrize("document", [None, "", "3862", "123456789", "12A45678"])
def test_personas_v1_rejects_documents_that_are_not_eight_ascii_digits(document):
    _, person, errors = PersonasV1Normalizer(100).normalize(
        source_row(document=document), search_batch(), datetime(2026, 10, 14, 12, 0)
    )

    assert person is None
    assert any(error.field == "documento" for error in errors)


def test_invalid_non_blank_birth_date_is_controlled_row_error():
    _, person, errors = PersonasV1Normalizer(100).normalize(
        source_row(birth="31/02/2020"), search_batch(), datetime(2026, 10, 14, 12, 0)
    )

    assert person is None
    assert any(error.field == "fecha_nacimiento" for error in errors)


def test_hashes_are_deterministic_and_distinguish_null_from_empty_source_cells():
    first = source_row()
    same = source_row()
    empty_cells = list(first.cells)
    empty_cells[8] = CellValue("")
    null_cells = list(first.cells)
    null_cells[8] = CellValue(None)

    first_payload = canonical_raw_payload(first.headers, first.cells)
    assert row_hash(first_payload) == row_hash(canonical_raw_payload(same.headers, same.cells))
    assert row_hash(canonical_raw_payload(HEADERS, empty_cells)) != row_hash(
        canonical_raw_payload(HEADERS, null_cells)
    )


def test_record_hash_is_stable_for_the_same_normalized_person():
    normalizer = PersonasV1Normalizer(100)
    created_at = datetime(2026, 10, 14, 12, 0)

    _, first, _ = normalizer.normalize(source_row(), search_batch(), created_at)
    _, second, _ = normalizer.normalize(source_row(), search_batch(), created_at)

    assert first is not None and second is not None
    assert first.record_hash == second.record_hash

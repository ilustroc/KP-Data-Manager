from datetime import datetime

import pytest

from src.domain.models import BatchRecord, CellValue, SearchSourceRow
from src.profiles.search.familia import FAMILY_FIELDS, FamiliaV1Normalizer


def family_batch() -> BatchRecord:
    return BatchRecord(
        61,
        "SEARCH",
        "PENDIENTE",
        "familia.xlsx",
        "imports/familia.xlsx",
        "xlsx",
        None,
        perfil_version="1",
        dataset_code="FAMILIA",
        source_code="BASE_FAMILIA",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )


def source_row(number: int, values: tuple[object, ...]) -> SearchSourceRow:
    cells = tuple(CellValue(value) for value in values)

    return SearchSourceRow(number, FAMILY_FIELDS, cells, dict(zip(FAMILY_FIELDS, cells, strict=True)))


def test_familia_preserves_source_values_without_family_business_validation() -> None:
    _, record, errors = FamiliaV1Normalizer(100).normalize(
        source_row(
            2,
            ("09529768", "9406251AN", " ARANA ", " RAMOS ", " LUIS ALBERTO ", "1994-06-25", " H "),
        ),
        family_batch(),
        datetime(2026, 10, 16),
    )

    assert errors == []
    assert record is not None
    assert record.documento == "09529768"
    assert record.documento_familiar == "9406251AN"
    assert record.paterno_familiar == "ARANA"
    assert record.nacimiento_familiar == "1994-06-25"
    assert record.tipo_familiar == "H"


@pytest.mark.parametrize("documento_familiar", ["09757192", "0", "00000000"])
def test_familia_accepts_historical_family_document_values(documento_familiar: str) -> None:
    _, record, errors = FamiliaV1Normalizer(100).normalize(
        source_row(2, ("09529768", documento_familiar, "ARANA", "VILLANUEVA", "OCTAVIO", "1972-03-22", "HERMANO")),
        family_batch(),
        datetime(2026, 10, 16),
    )

    assert errors == []
    assert record is not None
    assert record.documento_familiar == documento_familiar


def test_familia_converts_a_numeric_historical_zero_to_text_without_rejecting_it() -> None:
    _, record, errors = FamiliaV1Normalizer(100).normalize(
        source_row(2, ("09529768", 0, "ARANA", "VILLANUEVA", "OCTAVIO", None, "N")),
        family_batch(),
        datetime(2026, 10, 16),
    )

    assert errors == []
    assert record is not None
    assert record.documento_familiar == "0"


@pytest.mark.parametrize("tipo", ["HERMANO", "H", "C", "G", "N", "VALOR NO CATALOGADO"])
def test_familia_preserves_known_and_unknown_family_types(tipo: str) -> None:
    _, record, errors = FamiliaV1Normalizer(100).normalize(
        source_row(2, ("09529768", "09757192", "ARANA", "VILLANUEVA", "OCTAVIO", "1972-03-22", tipo)),
        family_batch(),
        datetime(2026, 10, 16),
    )

    assert errors == []
    assert record is not None
    assert record.tipo_familiar == tipo


def test_familia_preserves_non_standard_birth_text_and_nullable_names() -> None:
    _, record, errors = FamiliaV1Normalizer(100).normalize(
        source_row(2, ("09529768", "09757192", None, None, None, "22/03/1972", None)),
        family_batch(),
        datetime(2026, 10, 16),
    )

    assert errors == []
    assert record is not None
    assert record.paterno_familiar is None
    assert record.materno_familiar is None
    assert record.nombres_familiar is None
    assert record.nacimiento_familiar == "22/03/1972"
    assert record.tipo_familiar is None


def test_identical_familia_rows_keep_their_independent_source_row_identity() -> None:
    normalizer = FamiliaV1Normalizer(100)
    values = ("09529768", "09757192", "ARANA", "VILLANUEVA", "OCTAVIO", "1972-03-22", "HERMANO")
    _, first, first_errors = normalizer.normalize(source_row(2, values), family_batch(), datetime(2026, 10, 16))
    _, second, second_errors = normalizer.normalize(source_row(3, values), family_batch(), datetime(2026, 10, 16))

    assert first_errors == second_errors == []
    assert first is not None and second is not None
    assert first.record_hash == second.record_hash
    assert first.source_row != second.source_row

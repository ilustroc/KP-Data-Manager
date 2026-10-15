from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.errors import StructuralFileError
from src.loaders.search_loader import SearchLoader

from .conftest import FakeSearchDatabase, make_batch, stage_file


HEADER = "DOCUMENTO,PATERNO,MATERNO,NOMBRES,NACIMIENTO,DIRECCION,SEXO,ESTADO CIVIL,PADRE,MADRE\n"


def personas_batch(relative_path: str, sha256: str, refresh_mode: str = "FULL_REPLACE"):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="PERSONAS",
        source_code="BASE_PERSONAS",
        refresh_mode=refresh_mode,
        mapping_version=1,
        relative_path=relative_path,
        extension="csv",
        original_name="personas.csv",
        sha256=sha256,
    )


def write_csv(tmp_path: Path, body: str) -> Path:
    source = tmp_path / "source.csv"
    source.write_text(HEADER + body, encoding="utf-8")
    return source


def test_valid_personas_batch_writes_bronze_silver_scope_and_publishes(settings, tmp_path):
    source = write_csv(
        tmp_path,
        "00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n"
        "00009743,RUIZ,DIAZ,LUZ,1999-02-03,CALLE 2,2,SOLTERO,PEDRO,ROSA\n",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/personas.csv")
    database = FakeSearchDatabase(personas_batch("2026/10/123/personas.csv", sha256))

    result = SearchLoader(database, settings).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.file_rows == 2
    assert result.stats.inserted_rows == 2
    assert len(database.raw_records) == 2
    assert len(database.persons) == 2
    assert database.scope == {"00003862", "00009743"}
    assert database.published is True


def test_duplicate_document_is_an_error_and_prevents_gold_publication(settings, tmp_path):
    source = write_csv(
        tmp_path,
        "00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n"
        "00003862,RUIZ,DIAZ,LUZ,1999-02-03,CALLE 2,2,SOLTERO,PEDRO,ROSA\n",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/personas.csv")
    database = FakeSearchDatabase(personas_batch("2026/10/123/personas.csv", sha256))

    result = SearchLoader(database, settings).process(123)

    assert result.status == "COMPLETADO_CON_ERRORES"
    assert len(database.raw_records) == 2
    assert len(database.persons) == 1
    assert result.stats.duplicate_rows == 1
    assert database.published is False


def test_invalid_document_does_not_destroy_valid_rows_and_prevents_publication(settings, tmp_path):
    source = write_csv(
        tmp_path,
        "00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n"
        "3862,RUIZ,DIAZ,LUZ,1999-02-03,CALLE 2,2,SOLTERO,PEDRO,ROSA\n",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/personas.csv")
    database = FakeSearchDatabase(personas_batch("2026/10/123/personas.csv", sha256))

    result = SearchLoader(database, settings).process(123)

    assert result.stats.file_rows == 2
    assert len(database.raw_records) == 2
    assert len(database.persons) == 1
    assert result.stats.error_rows == 1
    assert database.published is False


def test_publication_failure_marks_batch_failed_without_reporting_success(settings, tmp_path):
    source = write_csv(
        tmp_path,
        "00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/personas.csv")
    database = FakeSearchDatabase(
        personas_batch("2026/10/123/personas.csv", sha256), fail_publish=True
    )

    with pytest.raises(StructuralFileError, match="RuntimeError"):
        SearchLoader(database, settings).process(123)

    assert database.published is False
    assert database.failed_message is not None

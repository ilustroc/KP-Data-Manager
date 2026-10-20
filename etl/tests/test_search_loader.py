from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.errors import (
    BatchStateError,
    FileSecurityError,
    SearchRecoveryError,
    StructuralFileError,
)
from src.domain.models import ProcessingStats
from src.loaders.search_loader import SearchLoader

from .conftest import FakeSearchDatabase, make_batch, stage_file


HEADER = "DOCUMENTO,PATERNO,MATERNO,NOMBRES,NACIMIENTO,DIRECCION,SEXO,ESTADO CIVIL,PADRE,MADRE\n"
ADDRESS_HEADER = "DOCUMENTO,DIRECCION,DEPARTAMENTO,PROVINCIA,DISTRITO,DATA PROCEDENCIA\n"
SBS_SUMMARY_HEADER = "COD_SBS,FECHA_REPORTE_SBS,DOCUMENTO,CANTIDAD_EMPRESAS,CALIFICACION_NORMAL,CALIFICACION_CPP,CALIFICACION_DEFICIENTE,CALIFICACION_DUDOSO,CALIFICACION_PERDIDAD\n"
FAMILY_HEADER = "DOCUMENTO,DOCUMENTO FAM.,PATERNO FAM.,MATERNO FAM.,NOMBRES FAM.,NACIMIENTO FAM.,TIPO FAM.\n"


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


def addresses_batch(relative_path: str, sha256: str):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="DIRECCIONES",
        source_code="BASE_DIRECCIONES",
        refresh_mode="SCOPE_REPLACE",
        mapping_version=1,
        relative_path=relative_path,
        extension="csv",
        original_name="direcciones.csv",
        sha256=sha256,
    )


def family_batch(relative_path: str, sha256: str, refresh_mode: str = "FULL_REPLACE"):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="FAMILIA",
        source_code="BASE_FAMILIA",
        refresh_mode=refresh_mode,
        mapping_version=1,
        relative_path=relative_path,
        extension="csv",
        original_name="familia.csv",
        sha256=sha256,
    )


def sbs_summary_batch(relative_path: str, sha256: str):
    return make_batch(tipo="SEARCH", perfil_version="1", dataset_code="SBS_RESUMEN", source_code="BASE_SBS", refresh_mode="FULL_REPLACE", mapping_version=1, relative_path=relative_path, extension="csv", original_name="sbs.csv", sha256=sha256)


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


def test_personas_upsert_is_rejected_before_claiming_the_batch(settings, tmp_path):
    source = write_csv(
        tmp_path,
        "00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/personas.csv")
    database = FakeSearchDatabase(
        personas_batch("2026/10/123/personas.csv", sha256, "UPSERT")
    )

    with pytest.raises(StructuralFileError, match="perfil SEARCH v1 publicable"):
        SearchLoader(database, settings).process(123)

    assert database.claimed is False
    assert database.published is False


def test_unreadable_private_file_is_rejected_before_batch_claim(settings, tmp_path, monkeypatch):
    source = write_csv(
        tmp_path,
        "00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/personas.csv")
    database = FakeSearchDatabase(
        personas_batch("2026/10/123/personas.csv", sha256)
    )
    monkeypatch.setattr("src.loaders.search_loader.os.access", lambda *_: False)

    with pytest.raises(FileSecurityError, match="no es legible"):
        SearchLoader(database, settings).process(123)

    assert database.claimed is False
    assert database.published is False


@pytest.mark.parametrize("refresh_mode", ["FULL_REPLACE", "SCOPE_REPLACE"])
def test_familia_preserves_duplicate_source_rows_through_bronze_silver_scope_and_gold(settings, tmp_path, refresh_mode):
    source = tmp_path / "familia.csv"
    source.write_text(
        FAMILY_HEADER
        + "09529768,9406251AN,ARANA,RAMOS,LUIS ALBERTO,1994-06-25,H\n"
        + "09529768,9406251AN,ARANA,RAMOS,LUIS ALBERTO,1994-06-25,H\n"
        + "09529768,00000000,,,,22/03/1972,C\n",
        encoding="utf-8",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/familia.csv")
    database = FakeSearchDatabase(family_batch("2026/10/123/familia.csv", sha256, refresh_mode))
    database.mapping = [
        {
            "source_position": position,
            "source_column": source_header,
            "target_column": target,
            "is_required": True,
            "transformation": "FAMILIA_V1",
            "default_value": None,
        }
        for position, (source_header, target) in enumerate(
            (
                ("DOCUMENTO", "documento"),
                ("DOCUMENTO FAM.", "documento_familiar"),
                ("PATERNO FAM.", "paterno_familiar"),
                ("MATERNO FAM.", "materno_familiar"),
                ("NOMBRES FAM.", "nombres_familiar"),
                ("NACIMIENTO FAM.", "nacimiento_familiar"),
                ("TIPO FAM.", "tipo_familiar"),
            ),
            start=1,
        )
    ]

    result = SearchLoader(database, settings).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.file_rows == 3
    assert result.stats.inserted_rows == 3
    assert result.stats.duplicate_rows == 0
    assert len(database.raw_records) == 3
    assert len(database.families) == 3
    assert database.families[0].record_hash == database.families[1].record_hash
    assert database.families[0].source_row != database.families[1].source_row
    assert database.scope == {"09529768"}
    assert database.published is True


def test_familia_gold_publish_failure_preserves_historical_rows(settings, tmp_path):
    source = tmp_path / "familia.csv"
    source.write_text(
        FAMILY_HEADER + "09529768,09757192,ARANA,VILLANUEVA,OCTAVIO,1972-03-22,HERMANO\n",
        encoding="utf-8",
    )
    _, sha256 = stage_file(settings, source, "2026/10/123/familia.csv")
    database = FakeSearchDatabase(
        family_batch("2026/10/123/familia.csv", sha256),
        fail_publish=True,
    )
    database.mapping = [
        {
            "source_position": position,
            "source_column": source_header,
            "target_column": target,
            "is_required": True,
            "transformation": "FAMILIA_V1",
            "default_value": None,
        }
        for position, (source_header, target) in enumerate(
            (
                ("DOCUMENTO", "documento"),
                ("DOCUMENTO FAM.", "documento_familiar"),
                ("PATERNO FAM.", "paterno_familiar"),
                ("MATERNO FAM.", "materno_familiar"),
                ("NOMBRES FAM.", "nombres_familiar"),
                ("NACIMIENTO FAM.", "nacimiento_familiar"),
                ("TIPO FAM.", "tipo_familiar"),
            ),
            start=1,
        )
    ]

    with pytest.raises(StructuralFileError, match="RuntimeError"):
        SearchLoader(database, settings).process(123)

    assert len(database.raw_records) == 1
    assert len(database.families) == 1
    assert database.published is False


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


def test_empty_address_remains_in_scope_without_silver_record_and_publishes_scope_replace(settings, tmp_path):
    source = tmp_path / "addresses.csv"
    source.write_text(ADDRESS_HEADER + "80686913,,,,,RENIEC 2022\n", encoding="utf-8")
    _, sha256 = stage_file(settings, source, "2026/10/123/direcciones.csv")
    database = FakeSearchDatabase(addresses_batch("2026/10/123/direcciones.csv", sha256))
    database.mapping = [
        {
            "source_position": position,
            "source_column": source_name,
            "target_column": target,
            "is_required": target == "documento",
            "transformation": "DIRECCIONES_V1",
            "default_value": None,
        }
        for position, (source_name, target) in enumerate(
            (
                ("DOCUMENTO", "documento"),
                ("DIRECCION", "direccion"),
                ("DEPARTAMENTO", "departamento"),
                ("PROVINCIA", "provincia"),
                ("DISTRITO", "distrito"),
                ("DATA PROCEDENCIA", "data_procedencia"),
            ),
            start=1,
        )
    ]

    result = SearchLoader(database, settings).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.inserted_rows == 0
    assert result.stats.error_rows == 0
    assert result.stats.scope_count == 1
    assert len(database.raw_records) == 1
    assert database.scope == {"80686913"}
    assert database.published is True


def test_sbs_summary_uses_generic_bronze_scope_and_publication_pipeline(settings, tmp_path):
    source = tmp_path / "sbs.csv"
    source.write_text(SBS_SUMMARY_HEADER + "0012345678,202607,00002549,1,100,0,0,0,0\n", encoding="utf-8")
    _, sha256 = stage_file(settings, source, "2026/10/123/sbs.csv")
    database = FakeSearchDatabase(sbs_summary_batch("2026/10/123/sbs.csv", sha256))
    database.mapping = [
        {"source_position": position, "source_column": source_name, "target_column": target, "is_required": target in {"documento", "cod_sbs", "fecha_reporte_sbs"}, "transformation": "SBS_RESUMEN_V1", "default_value": None}
        for position, (source_name, target) in enumerate((("COD_SBS", "cod_sbs"), ("FECHA_REPORTE_SBS", "fecha_reporte_sbs"), ("DOCUMENTO", "documento"), ("CANTIDAD_EMPRESAS", "cantidad_empresas"), ("CALIFICACION_NORMAL", "calificacion_normal"), ("CALIFICACION_CPP", "calificacion_cpp"), ("CALIFICACION_DEFICIENTE", "calificacion_deficiente"), ("CALIFICACION_DUDOSO", "calificacion_dudoso"), ("CALIFICACION_PERDIDAD", "calificacion_perdida")), start=1)
    ]

    result = SearchLoader(database, settings).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.inserted_rows == 1
    assert len(database.raw_records) == 1
    assert database.scope == {"00002549"}
    assert database.published is True


def test_sbs_summary_conflict_blocks_publication_without_losing_bronze(settings, tmp_path):
    source = tmp_path / "sbs-conflict.csv"
    source.write_text(SBS_SUMMARY_HEADER + "0012345678,202607,00002549,1,100,0,0,0,0\n0012345678,202607,00002549,1,99,1,0,0,0\n", encoding="utf-8")
    _, sha256 = stage_file(settings, source, "2026/10/123/sbs-conflict.csv")
    database = FakeSearchDatabase(sbs_summary_batch("2026/10/123/sbs-conflict.csv", sha256))
    database.mapping = [
        {"source_position": position, "source_column": source_name, "target_column": target, "is_required": target in {"documento", "cod_sbs", "fecha_reporte_sbs"}, "transformation": "SBS_RESUMEN_V1", "default_value": None}
        for position, (source_name, target) in enumerate((("COD_SBS", "cod_sbs"), ("FECHA_REPORTE_SBS", "fecha_reporte_sbs"), ("DOCUMENTO", "documento"), ("CANTIDAD_EMPRESAS", "cantidad_empresas"), ("CALIFICACION_NORMAL", "calificacion_normal"), ("CALIFICACION_CPP", "calificacion_cpp"), ("CALIFICACION_DEFICIENTE", "calificacion_deficiente"), ("CALIFICACION_DUDOSO", "calificacion_dudoso"), ("CALIFICACION_PERDIDAD", "calificacion_perdida")), start=1)
    ]

    result = SearchLoader(database, settings).process(123)

    assert result.status == "COMPLETADO_CON_ERRORES"
    assert len(database.raw_records) == 2
    assert result.stats.error_rows == 1
    assert database.published is False


@pytest.mark.parametrize("refresh_mode", ["FULL_REPLACE", "SCOPE_REPLACE"])
def test_recovery_publishes_only_without_changing_historical_rows(settings, refresh_mode):
    batch = make_batch(
        tipo="SEARCH",
        status="PROCESANDO",
        perfil_version="1",
        dataset_code="LABORAL_ESSALUD",
        source_code="BASE_ESSALUD",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )
    database = FakeSearchDatabase(batch)
    database.raw_records.append(object())
    database.persons.append(object())
    database.scope.add("00002549")
    database.recovery_stats = ProcessingStats(
        file_rows=1,
        inserted_rows=1,
        error_rows=0,
        scope_count=1,
    )
    before = (len(database.raw_records), len(database.persons), len(database.scope))

    result = SearchLoader(database, settings).recover_publish(123)

    assert result.status == "COMPLETADO"
    assert database.recovery_preflight_calls == 1
    assert database.recovery_publish_calls == 1
    assert (len(database.raw_records), len(database.persons), len(database.scope)) == before


def test_recovery_accepts_error_batch_and_propagates_publish_failure_safely(settings):
    batch = make_batch(
        tipo="SEARCH",
        status="ERROR",
        perfil_version="1",
        dataset_code="SBS_DETALLE",
        source_code="BASE_SBS_DETALLE",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )
    database = FakeSearchDatabase(batch, fail_publish=True)
    database.recovery_stats = ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1)

    with pytest.raises(SearchRecoveryError, match="No fue posible recuperar"):
        SearchLoader(database, settings).recover_publish(123)

    assert database.recovery_preflight_calls == 1
    assert database.recovery_publish_calls == 0
    assert database.published is False
    assert database.recovery_failure_marked is True


def test_phone_upsert_recovery_is_accepted_without_rewriting_history(settings):
    batch = make_batch(
        tipo="SEARCH",
        status="ERROR",
        perfil_version="1",
        dataset_code="TELEFONOS",
        source_code="BASE_TELEFONOS",
        refresh_mode="UPSERT",
        mapping_version=1,
    )
    database = FakeSearchDatabase(batch)
    database.raw_records.append(object())
    database.phones.append(object())
    database.scope.add("00003862")
    database.recovery_stats = ProcessingStats(
        file_rows=1,
        inserted_rows=1,
        scope_count=1,
    )
    before = (len(database.raw_records), len(database.phones), len(database.scope))

    result = SearchLoader(database, settings).recover_publish(123)

    assert result.status == "COMPLETADO"
    assert database.recovery_publish_calls == 1
    assert (len(database.raw_records), len(database.phones), len(database.scope)) == before


def test_recovery_preserves_preflight_failure_when_marking_error_also_fails(settings):
    class FailureMarkDatabase(FakeSearchDatabase):
        def mark_search_recovery_failed(self, batch_id: int, finished_at: datetime) -> None:
            raise RuntimeError("simulated status update failure")

    batch = make_batch(
        tipo="SEARCH",
        status="PROCESANDO",
        perfil_version="1",
        dataset_code="LABORAL_ESSALUD",
        source_code="BASE_ESSALUD",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )
    database = FailureMarkDatabase(batch)

    with pytest.raises(SearchRecoveryError) as exception:
        SearchLoader(database, settings).recover_publish(123)

    assert exception.value.stage == "recovery_preflight"
    assert isinstance(exception.value.cause, RuntimeError)
    assert str(exception.value.cause) == "missing recovery preflight"


@pytest.mark.parametrize("status", ["PENDIENTE", "COMPLETADO", "COMPLETADO_CON_ERRORES"])
def test_recovery_rejects_non_recoverable_batch_states(settings, status):
    batch = make_batch(
        tipo="SEARCH",
        status=status,
        perfil_version="1",
        dataset_code="SBS_DETALLE",
        source_code="BASE_SBS_DETALLE",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )
    database = FakeSearchDatabase(batch)

    with pytest.raises(BatchStateError):
        SearchLoader(database, settings).recover_publish(123)

    assert database.recovery_preflight_calls == 0
    assert database.recovery_publish_calls == 0

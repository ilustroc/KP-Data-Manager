from datetime import datetime
from src.loaders.search_loader import SearchLoader

from .conftest import FakeSearchDatabase, make_batch, stage_file


PHONE_MAPPING = [
    {"source_position": 1, "source_column": "DOCUMENTO", "target_column": "documento"},
    {"source_position": 2, "source_column": "TELEFONO", "target_column": "telefono"},
    {"source_position": 3, "source_column": "OPERADOR", "target_column": "operador_raw"},
    {"source_position": 4, "source_column": "FECHA DATA", "target_column": "fecha_data"},
]


def run_phone_csv(settings, tmp_path, rows):
    source = tmp_path / "telefonos-source.csv"
    source.write_text("DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n" + "\n".join(rows) + "\n", encoding="utf-8")
    _, fingerprint = stage_file(settings, source, "telefonos.csv")
    batch = make_batch(
        tipo="SEARCH", dataset_code="TELEFONOS", source_code="BASE_TELEFONOS",
        perfil_version="1", refresh_mode="FULL_REPLACE", mapping_version=1,
        original_name="telefonos.csv", relative_path="telefonos.csv", extension="csv",
        sha256=fingerprint,
    )
    database = FakeSearchDatabase(batch=batch)
    database.mapping = PHONE_MAPPING
    result = SearchLoader(database, settings, clock=lambda: datetime(2026, 10, 15)).process(batch.batch_id)
    return database, result


def test_many_phones_for_one_document_and_same_phone_for_distinct_documents_are_allowed(settings, tmp_path):
    database, result = run_phone_csv(settings, tmp_path, [
        "00003862,934043966,CLARO,2026-01-01",
        "00003862,951159659,ENTEL,2026-01-02",
        "00009743,934043966,MOVISTAR,2026-01-03",
    ])
    assert result.status == "COMPLETADO"
    assert len(database.phones) == 3
    assert len(database.raw_records) == 3
    assert database.scope == {"00003862", "00009743"}
    assert database.published is True


def test_duplicate_document_phone_is_an_error_and_blocks_publication(settings, tmp_path):
    database, result = run_phone_csv(settings, tmp_path, [
        "00003862,934043966,CLARO,2026-01-01",
        "00003862,934043966,CLARO,2026-01-02",
    ])
    assert result.status == "COMPLETADO_CON_ERRORES"
    assert len(database.raw_records) == 2
    assert len(database.phones) == 1
    assert database.errors[0].message == "DUPLICATE_DOCUMENT_PHONE"
    assert database.published is False


def test_invalid_row_remains_in_bronze_but_not_silver_or_gold(settings, tmp_path):
    database, result = run_phone_csv(settings, tmp_path, ["00003862,911111111,DESCONOCIDO,invalid"])
    assert result.status == "COMPLETADO_CON_ERRORES"
    assert len(database.raw_records) == 1
    assert database.phones == []
    assert database.published is False

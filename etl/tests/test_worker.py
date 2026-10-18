from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import logging
from pathlib import Path

import pytest

from src.domain.errors import (
    BatchNotFoundError,
    BatchStateError,
    FileSecurityError,
    StructuralFileError,
)
from src.domain.models import CellValue, SourceRow
from src.loaders.pagos_loader import PaymentLoader
from src.worker import JsonFormatter, safe_diagnostic
import pymysql

from .conftest import FakeDatabase, make_batch, stage_file

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pagos_16_anon.csv"
FIXED_UTC = datetime(2026, 10, 5, 3, 30, 0)


def fixed_clock() -> datetime:
    return FIXED_UTC


def test_realistic_16_row_csv_preserves_bronze_values_and_uses_chunk_inserts(settings) -> None:
    _, fingerprint = stage_file(settings, FIXTURE_PATH, "2026/10/123/pagos.csv")
    database = FakeDatabase(make_batch(sha256=fingerprint))

    result = PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.file_rows == 16
    assert result.stats.inserted_rows == 16
    assert result.stats.error_rows == 0
    assert result.stats.duplicate_rows == 0
    assert database.chunk_sizes == [(5, 0), (5, 0), (5, 0), (1, 0)]
    assert database.finished_status == "COMPLETADO"
    assert database.claimed_at == FIXED_UTC
    assert database.finished_at == FIXED_UTC
    assert database.payments[0].documento == "3241"
    assert database.payments[0].operacion == "0060814"
    assert database.payments[1].documento is None
    assert database.payments[1].operacion is None
    assert database.payments[1].hora is None
    assert database.payments[1].comentario is None
    assert str(database.payments[1].acumulado) == "3800.00"
    assert database.payments[2].documento == "00157405"
    assert database.payments[2].operacion == "0093273"
    assert database.payments[0].source_file == "pagos.csv"
    assert database.payments[0].batch_id == 123
    assert database.payments[0].ingested_at == FIXED_UTC
    assert len(database.payments[0].row_hash) == 64


def test_partial_row_errors_are_batched_and_finish_with_errors(settings, tmp_path: Path) -> None:
    source = tmp_path / "partial.csv"
    source.write_text(
        "FECHA;MONTO;RECAUDO;COMENTARIO\n"
        "2026-10-01;200;BCP;Correcto\n"
        "31/02/2026;S/XYZ;BCP;Dos errores\n"
        "2026-10-03;300;;Sin recaudo\n"
        f"2026-10-04;400;YAPE;{'x' * 261}\n"
        "05/10/2026;500;BBVA;Correcto\n",
        encoding="utf-8",
    )
    _, fingerprint = stage_file(settings, source, "2026/10/123/partial.csv")
    database = FakeDatabase(
        make_batch(
            relative_path="2026/10/123/partial.csv",
            sha256=fingerprint,
            original_name="partial.csv",
        )
    )

    result = PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert result.status == "COMPLETADO_CON_ERRORES"
    assert result.stats.file_rows == 5
    assert result.stats.inserted_rows == 2
    assert result.stats.error_rows == 3
    assert len(database.errors) == 4
    assert {(error.row_number, error.field) for error in database.errors} == {
        (3, "FECHA"),
        (3, "MONTO"),
        (4, "RECAUDO"),
        (5, "COMENTARIO"),
    }
    assert all(error.batch_id == 123 for error in database.errors)
    assert all(error.created_at == FIXED_UTC for error in database.errors)
    assert max(len(error.value or "") for error in database.errors) <= settings.error_value_max_length


def test_missing_required_columns_marks_batch_error_without_inserts(settings, tmp_path: Path) -> None:
    source = tmp_path / "missing.csv"
    source.write_text("FECHA;RECAUDO\n2026-10-01;BCP\n", encoding="utf-8")
    _, fingerprint = stage_file(settings, source, "2026/10/123/missing.csv")
    database = FakeDatabase(
        make_batch(
            relative_path="2026/10/123/missing.csv",
            sha256=fingerprint,
            original_name="missing.csv",
        )
    )

    with pytest.raises(StructuralFileError, match="MONTO"):
        PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert database.claimed is True
    assert database.payments == []
    assert database.errors == []
    assert "MONTO" in (database.failed_message or "")
    assert database.final_stats is not None
    assert database.final_stats.file_rows == 0


def test_missing_private_file_marks_pending_batch_error(settings) -> None:
    database = FakeDatabase(make_batch())

    with pytest.raises(FileSecurityError, match="no existe"):
        PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert database.claimed is False
    assert database.failed_message == "El archivo privado registrado no existe."
    assert database.failed_at == FIXED_UTC


def test_nonexistent_batch_is_rejected_without_writes(settings) -> None:
    database = FakeDatabase(None)

    with pytest.raises(BatchNotFoundError, match="#999"):
        PaymentLoader(database, settings, clock=fixed_clock).process(999)

    assert database.claimed is False
    assert database.failed_message is None


@pytest.mark.parametrize("status", ["PROCESANDO", "COMPLETADO", "ERROR"])
def test_non_pending_batch_is_not_reprocessed(settings, status: str) -> None:
    database = FakeDatabase(make_batch(status=status))

    with pytest.raises(BatchStateError, match=status):
        PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert database.claimed is False
    assert database.payments == []


def test_fatal_error_preserves_only_previously_committed_chunks(settings) -> None:
    _, fingerprint = stage_file(settings, FIXTURE_PATH, "2026/10/123/pagos.csv")
    small_chunks = replace(settings, insert_batch_size=2, progress_update_every=2)
    database = FakeDatabase(make_batch(sha256=fingerprint), fail_on_chunk=2)

    with pytest.raises(StructuralFileError, match="RuntimeError"):
        PaymentLoader(database, small_chunks, clock=fixed_clock).process(123)

    assert len(database.payments) == 2
    assert database.chunk_sizes == [(2, 0)]
    assert database.final_stats is not None
    assert database.final_stats.file_rows == 2
    assert database.final_stats.inserted_rows == 2
    assert database.failed_message == "Error fatal durante el procesamiento: RuntimeError."


def test_sha256_mismatch_marks_batch_error_before_inserts(settings) -> None:
    stage_file(settings, FIXTURE_PATH, "2026/10/123/pagos.csv")
    database = FakeDatabase(make_batch(sha256="0" * 64))

    with pytest.raises(FileSecurityError, match="SHA-256"):
        PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert database.payments == []
    assert database.claimed is True
    assert database.failed_message == "El SHA-256 del archivo no coincide con el batch registrado."


def test_path_traversal_is_rejected_without_reading_external_file(settings) -> None:
    database = FakeDatabase(make_batch(relative_path="../../outside.csv"))

    with pytest.raises(FileSecurityError, match="ruta privada"):
        PaymentLoader(database, settings, clock=fixed_clock).process(123)

    assert database.claimed is False
    assert database.payments == []


def test_large_iterator_is_consumed_in_bounded_chunks(settings, tmp_path: Path) -> None:
    source = tmp_path / "placeholder.csv"
    source.write_text("streamed", encoding="utf-8")
    stage_file(settings, source, "2026/10/123/generated.csv")
    bounded_settings = replace(settings, insert_batch_size=5000, progress_update_every=5000)
    database = FakeDatabase(make_batch(relative_path="2026/10/123/generated.csv", sha256=None))

    class GeneratedParser:
        def rows(self, path: Path):
            for row_number in range(2, 10003):
                yield SourceRow(
                    number=row_number,
                    values={
                        "FECHA": CellValue("2026-10-01"),
                        "MONTO": CellValue("200"),
                        "RECAUDO": CellValue("BCP"),
                    },
                )

    result = PaymentLoader(
        database,
        bounded_settings,
        clock=fixed_clock,
        parsers={"csv": GeneratedParser()},
    ).process(123)

    assert result.stats.file_rows == 10001
    assert database.chunk_sizes == [(5000, 0), (5000, 0), (1, 0)]
    assert [progress.file_rows for progress in database.progress] == [5000, 10000, 10001]


def test_worker_json_formatter_never_serializes_exception_tracebacks() -> None:
    record = logging.LogRecord(
        name="kpdm.etl",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="worker_crashed",
        args=(),
        exc_info=(RuntimeError, RuntimeError("PASSWORD=secret"), None),
    )

    payload = JsonFormatter().format(record)

    assert '"event": "worker_crashed"' in payload
    assert "PASSWORD=secret" not in payload
    assert "exception" not in payload


def test_worker_json_formatter_emits_search_phase_metric_as_one_json_line() -> None:
    record = logging.LogRecord(
        name="kpdm.etl.search",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="search_phase_metric",
        args=(),
        exc_info=None,
    )
    record.context = {
        "batch_id": 42,
        "dataset_code": "FAMILIA",
        "refresh_mode": "FULL_REPLACE",
        "phase": "gold_insert",
        "duration_seconds": 2.5,
        "rows_processed": 41040,
        "rows_per_second": 16416.0,
        "logical_statement_count": 1,
        "executemany_calls": 0,
        "physical_statement_count": 1,
        "invocations": 1,
        "peak_memory_mb": None,
        "successful": True,
    }

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "search_phase_metric"
    assert payload["batch_id"] == 42
    assert payload["phase"] == "gold_insert"
    assert payload["duration_seconds"] == 2.5
    assert payload["rows_processed"] == 41040
    assert "documento" not in payload
    assert "sql" not in payload


def test_interface_error_diagnostic_preserves_zero_code_and_hides_driver_message() -> None:
    class Database:
        connection_phase = "execute"

    diagnostic = safe_diagnostic(pymysql.err.InterfaceError(0, "PASSWORD=secret"), Database())

    assert diagnostic == {
        "error_code": 0,
        "db_driver": "pymysql",
        "connection_phase": "execute",
        "retryable": True,
    }


def test_operational_error_2013_is_retryable_without_exposing_the_driver_message() -> None:
    class Database:
        connection_phase = "execute"

    diagnostic = safe_diagnostic(
        pymysql.err.OperationalError(2013, "sensitive driver message"),
        Database(),
    )

    assert diagnostic == {
        "error_code": 2013,
        "db_driver": "pymysql",
        "connection_phase": "execute",
        "retryable": True,
    }

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from src.domain.models import (
    BBVA_SOURCE_COLUMNS,
    CAJA_AREQUIPA_SOURCE_COLUMNS,
    CellValue,
    SourceRow,
)
from src.domain.errors import StructuralFileError
from src.loaders.cartera_loader import CarteraLoader
from src.profiles.carteras.bbva import BbvaV1Profile
from src.profiles.carteras.caja_arequipa import CajaArequipaV1Profile

from .conftest import FakeCarteraDatabase, make_batch, stage_file

FIXED_UTC = datetime(2026, 10, 6, 19, 30, 0)


def fixed_clock() -> datetime:
    return FIXED_UTC


def valid_row(number: int, contract: str) -> SourceRow:
    values: dict[str, object] = {column: None for column in BBVA_SOURCE_COLUMNS}
    values.update(
        {
            "CODCENTRAL": "14898140",
            "CONTRATO": contract,
            "DOCUMENTO": contract,
            "NOMBRE": "Cliente Anónimo",
            "MONEDA": "PEN",
            "Suma de Importes": "100.00",
            "Suma de INTERES": "10.00",
            "Suma de MORA": "1.00",
            "FECHAVEN": "31/10/2026",
            "tipodoc": "DNI",
            "numdoc": "01116950",
            "fono1": "0987654321",
            "direccion": "Dirección de prueba",
            "COSECHA": "BBVA1",
        }
    )
    return SourceRow(number, {field: CellValue(value) for field, value in values.items()})


def bbva_batch(*, fingerprint: str | None = None):
    return make_batch(
        relative_path="2026/10/15/bbva.csv",
        original_name="bbva.csv",
        sha256=fingerprint,
        tipo="CARTERA",
        entidad="BBVA",
        perfil_version="1",
    )


def test_bbva_loader_streams_chunks_and_keeps_bronze_silver_traceability(settings, tmp_path: Path):
    source = tmp_path / "bbva.csv"
    source.write_text("placeholder", encoding="utf-8")
    _, fingerprint = stage_file(settings, source, "2026/10/15/bbva.csv")
    database = FakeCarteraDatabase(bbva_batch(fingerprint=fingerprint))

    class GeneratedParser:
        def rows(self, path: Path):
            for number in range(2, 14):
                yield valid_row(number, f"0011031003960077{number:04d}")

    result = CarteraLoader(
        database,
        replace(settings, insert_batch_size=5, progress_update_every=5),
        BbvaV1Profile(),
        clock=fixed_clock,
        parsers={"csv": GeneratedParser()},
    ).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.file_rows == 12
    assert result.stats.inserted_rows == 12
    assert result.stats.error_rows == 0
    assert database.chunk_sizes == [(5, 0), (5, 0), (2, 0)]
    assert database.portfolio_records[0].batch_id == 123
    assert database.portfolio_records[0].source_row == 2
    assert database.portfolio_records[0].operation.documento_cliente == "01116950"
    assert database.portfolio_records[0].operation.cuenta == "14898140"
    assert database.portfolio_records[0].contacts[0].telefono == "0987654321"
    assert database.portfolio_records[0].address is not None
    assert database.finished_status == "COMPLETADO"


def test_bbva_loader_records_partial_row_error_and_completes_with_observations(settings, tmp_path: Path):
    source = tmp_path / "bbva.csv"
    source.write_text("placeholder", encoding="utf-8")
    _, fingerprint = stage_file(settings, source, "2026/10/15/bbva.csv")
    database = FakeCarteraDatabase(bbva_batch(fingerprint=fingerprint))

    class GeneratedParser:
        def rows(self, path: Path):
            yield valid_row(2, "001")
            invalid = valid_row(3, "002")
            values = dict(invalid.values)
            values["Suma de Importes"] = CellValue("INVALIDO")
            yield SourceRow(3, values)

    result = CarteraLoader(
        database,
        settings,
        BbvaV1Profile(),
        clock=fixed_clock,
        parsers={"csv": GeneratedParser()},
    ).process(123)

    assert result.status == "COMPLETADO_CON_ERRORES"
    assert result.stats.file_rows == 2
    assert result.stats.inserted_rows == 1
    assert result.stats.error_rows == 1
    assert database.errors[0].field == "Suma de Importes"


def test_caja_arequipa_loader_uses_existing_chunk_pipeline_and_traceability(settings, tmp_path: Path):
    source = tmp_path / "caja.csv"
    source.write_text("placeholder", encoding="utf-8")
    _, fingerprint = stage_file(settings, source, "2026/10/16/caja.csv")
    database = FakeCarteraDatabase(
        make_batch(
            relative_path="2026/10/16/caja.csv",
            original_name="caja.csv",
            sha256=fingerprint,
            tipo="CARTERA",
            entidad="CAJA_AREQUIPA",
            perfil_version="1",
        )
    )
    values = {column: CellValue(None) for column in CAJA_AREQUIPA_SOURCE_COLUMNS}
    values.update(
        {
            "NRO_DOC_TIT_1": CellValue("00001234"),
            "NRO_DOC_TIT_2": CellValue("00001234"),
            "CUENTA": CellValue(1804548),
            "OPERACION": CellValue(2435410),
            "SALDO_CAPITAL": CellValue("100.00"),
        }
    )

    class GeneratedParser:
        def rows(self, path: Path):
            yield SourceRow(2, values)

    result = CarteraLoader(
        database,
        settings,
        CajaArequipaV1Profile(),
        clock=fixed_clock,
        parsers={"csv": GeneratedParser()},
    ).process(123)

    assert result.status == "COMPLETADO"
    assert result.stats.inserted_rows == 1
    assert database.chunk_sizes == [(1, 0)]
    record = database.portfolio_records[0]
    assert record.operation.entidad == "CAJA_AREQUIPA"
    assert record.source_row == 2
    assert record.source_file == "caja.csv"


def test_caja_arequipa_failed_chunk_is_not_counted_as_inserted(settings, tmp_path: Path):
    source = tmp_path / "caja.csv"
    source.write_text("placeholder", encoding="utf-8")
    _, fingerprint = stage_file(settings, source, "2026/10/16/caja.csv")
    database = FakeCarteraDatabase(
        make_batch(
            relative_path="2026/10/16/caja.csv",
            original_name="caja.csv",
            sha256=fingerprint,
            tipo="CARTERA",
            entidad="CAJA_AREQUIPA",
            perfil_version="1",
        ),
        fail_on_chunk=1,
    )
    values = {column: CellValue(None) for column in CAJA_AREQUIPA_SOURCE_COLUMNS}
    values.update(
        {
            "NRO_DOC_TIT_1": CellValue("00001234"),
            "NRO_DOC_TIT_2": CellValue("00001234"),
            "CUENTA": CellValue("001"),
            "OPERACION": CellValue("002"),
        }
    )

    class GeneratedParser:
        def rows(self, path: Path):
            yield SourceRow(2, values)

    with pytest.raises(StructuralFileError):
        CarteraLoader(
            database,
            settings,
            CajaArequipaV1Profile(),
            clock=fixed_clock,
            parsers={"csv": GeneratedParser()},
        ).process(123)

    assert database.portfolio_records == []
    assert database.final_stats is not None
    assert database.final_stats.inserted_rows == 0
    assert database.failed_message is not None

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Sequence

import pytest

from src.config import Settings
from src.domain.models import (
    BatchRecord,
    PaymentRecord,
    ProcessingStats,
    RowError,
)


class FakeDatabase:
    def __init__(self, batch: BatchRecord | None, *, fail_on_chunk: int | None = None) -> None:
        self.batch = batch
        self.fail_on_chunk = fail_on_chunk
        self.claimed = False
        self.claimed_at: datetime | None = None
        self.closed = False
        self.payments: list[PaymentRecord] = []
        self.errors: list[RowError] = []
        self.chunk_sizes: list[tuple[int, int]] = []
        self.progress: list[ProcessingStats] = []
        self.finished_status: str | None = None
        self.finished_at: datetime | None = None
        self.failed_message: str | None = None
        self.failed_at: datetime | None = None
        self.final_stats: ProcessingStats | None = None

    def get_batch(self, batch_id: int) -> BatchRecord | None:
        if self.batch is None or self.batch.batch_id != batch_id:
            return None
        return self.batch

    def claim_batch(self, batch_id: int, started_at: datetime) -> bool:
        if self.batch is None or self.batch.batch_id != batch_id or self.batch.estado != "PENDIENTE":
            return False
        if self.claimed:
            return False
        self.claimed = True
        self.claimed_at = started_at
        self.batch = BatchRecord(
            batch_id=self.batch.batch_id,
            tipo=self.batch.tipo,
            estado="PROCESANDO",
            archivo_original=self.batch.archivo_original,
            archivo_ruta=self.batch.archivo_ruta,
            archivo_extension=self.batch.archivo_extension,
            archivo_sha256=self.batch.archivo_sha256,
            entidad=self.batch.entidad,
            perfil_version=self.batch.perfil_version,
        )
        return True

    def insert_chunk(
        self,
        payments: Sequence[PaymentRecord],
        errors: Sequence[RowError],
    ) -> None:
        call_number = len(self.chunk_sizes) + 1
        if self.fail_on_chunk == call_number:
            raise RuntimeError("simulated chunk failure")
        self.chunk_sizes.append((len(payments), len(errors)))
        self.payments.extend(payments)
        self.errors.extend(errors)

    def update_progress(self, batch_id: int, stats: ProcessingStats) -> None:
        self.progress.append(copy_stats(stats))

    def finish_batch(
        self,
        batch_id: int,
        status: str,
        finished_at: datetime,
        stats: ProcessingStats,
    ) -> None:
        self.finished_status = status
        self.finished_at = finished_at
        self.final_stats = copy_stats(stats)

    def fail_batch(
        self,
        batch_id: int,
        finished_at: datetime,
        message: str,
        stats: ProcessingStats,
    ) -> None:
        self.failed_message = message
        self.failed_at = finished_at
        self.final_stats = copy_stats(stats)

    def close(self) -> None:
        self.closed = True


class FakeCarteraDatabase(FakeDatabase):
    def __init__(self, batch: BatchRecord | None, *, fail_on_chunk: int | None = None) -> None:
        super().__init__(batch, fail_on_chunk=fail_on_chunk)
        self.portfolio_records: list[object] = []

    def insert_cartera_chunk(
        self,
        records: Sequence[object],
        errors: Sequence[RowError],
    ) -> None:
        call_number = len(self.chunk_sizes) + 1
        if self.fail_on_chunk == call_number:
            raise RuntimeError("simulated chunk failure")
        self.chunk_sizes.append((len(records), len(errors)))
        self.portfolio_records.extend(records)
        self.errors.extend(errors)


def copy_stats(stats: ProcessingStats) -> ProcessingStats:
    return ProcessingStats(
        file_rows=stats.file_rows,
        inserted_rows=stats.inserted_rows,
        error_rows=stats.error_rows,
        duplicate_rows=stats.duplicate_rows,
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        db_host="127.0.0.1",
        db_port=3306,
        db_username="kp_data_manager_etl",
        db_password="test-only",
        control_database="kp_control_test",
        bronze_database="kp_bronze_test",
        silver_database="kp_silver_test",
        storage_root=tmp_path / "imports",
        insert_batch_size=5,
        progress_update_every=5,
        allow_zero_amount=True,
        error_value_max_length=40,
        log_level="CRITICAL",
    )


def stage_file(settings: Settings, source: Path, relative_path: str) -> tuple[Path, str]:
    destination = settings.storage_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    with destination.open("rb") as handle:
        fingerprint = hashlib.file_digest(handle, "sha256").hexdigest()
    return destination, fingerprint


def make_batch(
    *,
    batch_id: int = 123,
    status: str = "PENDIENTE",
    relative_path: str = "2026/10/123/pagos.csv",
    extension: str = "csv",
    sha256: str | None = None,
    original_name: str = "pagos.csv",
    tipo: str = "PAGOS",
    entidad: str | None = None,
    perfil_version: str | None = None,
) -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        tipo=tipo,
        estado=status,
        archivo_original=original_name,
        archivo_ruta=relative_path,
        archivo_extension=extension,
        archivo_sha256=sha256,
        entidad=entidad,
        perfil_version=perfil_version,
    )

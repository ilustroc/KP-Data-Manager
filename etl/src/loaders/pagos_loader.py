from __future__ import annotations

import hashlib
import logging
import os
import time as monotonic_time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath
from typing import Callable, Mapping

from ..config import Settings
from ..domain.errors import (
    BatchNotFoundError,
    BatchStateError,
    EtlError,
    FileSecurityError,
    StructuralFileError,
)
from ..domain.models import (
    BatchRecord,
    Chunk,
    DatabasePort,
    ProcessingStats,
    RowParser,
)
from ..domain.normalizers import PaymentNormalizer, utc_now_naive
from ..parsers.csv_parser import CsvPaymentParser
from ..parsers.xlsx_parser import XlsxPaymentParser

LOGGER = logging.getLogger("kpdm.etl.pagos")


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    batch_id: int
    status: str
    stats: ProcessingStats


class PaymentLoader:
    def __init__(
        self,
        database: DatabasePort,
        settings: Settings,
        *,
        clock: Callable[[], datetime] = utc_now_naive,
        monotonic: Callable[[], float] = monotonic_time.monotonic,
        parsers: Mapping[str, RowParser] | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.clock = clock
        self.monotonic = monotonic
        self.parsers = parsers or {
            "csv": CsvPaymentParser(),
            "xlsx": XlsxPaymentParser(),
        }
        self.normalizer = PaymentNormalizer(
            allow_zero_amount=settings.allow_zero_amount,
            error_value_max_length=settings.error_value_max_length,
        )

    def process(self, batch_id: int) -> ProcessingResult:
        stats = ProcessingStats()
        batch = self.database.get_batch(batch_id)
        if batch is None:
            raise BatchNotFoundError(f"No existe el batch #{batch_id}.")
        if batch.estado != "PENDIENTE":
            raise BatchStateError(
                f"El batch #{batch_id} está en {batch.estado}; solo se procesa PENDIENTE."
            )

        try:
            source_path = self._validated_source_path(batch)
        except EtlError as exception:
            self.database.fail_batch(batch_id, self.clock(), str(exception), stats)
            raise

        started_at = self.clock()
        if not self.database.claim_batch(batch_id, started_at):
            raise BatchStateError(f"El batch #{batch_id} ya fue reclamado por otro worker.")

        start_monotonic = self.monotonic()
        LOGGER.info(
            "batch_started",
            extra={
                "context": {
                    "batch_id": batch_id,
                    "tipo": batch.tipo,
                    "archivo": batch.archivo_original,
                }
            },
        )

        try:
            parser = self.parsers[batch.archivo_extension]
            self._verify_source_hash(batch, source_path)
            self._consume_rows(batch, source_path, parser, stats, started_at)
            final_status = "COMPLETADO_CON_ERRORES" if stats.error_rows else "COMPLETADO"
            self.database.finish_batch(batch_id, final_status, self.clock(), stats)
            result = ProcessingResult(batch_id=batch_id, status=final_status, stats=stats)
            LOGGER.info(
                "batch_finished",
                extra={
                    "context": self._log_context(
                        batch,
                        stats,
                        self.monotonic() - start_monotonic,
                        final_status,
                    )
                },
            )
            return result
        except Exception as exception:
            message = self._fatal_message(exception)
            self.database.fail_batch(batch_id, self.clock(), message, stats)
            LOGGER.exception(
                "batch_failed",
                extra={
                    "context": self._log_context(
                        batch,
                        stats,
                        self.monotonic() - start_monotonic,
                        "ERROR",
                    )
                },
            )
            if isinstance(exception, EtlError):
                raise
            raise StructuralFileError(message) from exception

    def _consume_rows(
        self,
        batch: BatchRecord,
        source_path: Path,
        parser: RowParser,
        stats: ProcessingStats,
        ingested_at: datetime,
    ) -> None:
        chunk = Chunk()
        last_progress = 0

        for source_row in parser.rows(source_path):
            payment, row_errors = self.normalizer.normalize(
                source_row,
                batch_id=batch.batch_id,
                source_file=batch.archivo_original,
                ingested_at=ingested_at,
            )
            chunk.file_rows += 1
            if payment is None:
                chunk.error_rows += 1
                chunk.errors.extend(row_errors)
            else:
                chunk.payments.append(payment)

            if chunk.file_rows >= self.settings.insert_batch_size:
                self._flush_chunk(batch.batch_id, chunk, stats)
                if stats.file_rows - last_progress >= self.settings.progress_update_every:
                    self.database.update_progress(batch.batch_id, stats)
                    last_progress = stats.file_rows

        if chunk.file_rows:
            self._flush_chunk(batch.batch_id, chunk, stats)
        if stats.file_rows != last_progress:
            self.database.update_progress(batch.batch_id, stats)

    def _flush_chunk(self, batch_id: int, chunk: Chunk, stats: ProcessingStats) -> None:
        self.database.insert_chunk(chunk.payments, chunk.errors)
        stats.file_rows += chunk.file_rows
        stats.inserted_rows += len(chunk.payments)
        stats.error_rows += chunk.error_rows
        LOGGER.info(
            "chunk_committed",
            extra={
                "context": {
                    "batch_id": batch_id,
                    "filas_procesadas": stats.file_rows,
                    "filas_insertadas": stats.inserted_rows,
                    "filas_error": stats.error_rows,
                }
            },
        )
        chunk.clear()

    def _validated_source_path(self, batch: BatchRecord) -> Path:
        if batch.tipo != "PAGOS":
            raise StructuralFileError(f"Tipo de batch no soportado en Fase 5: {batch.tipo}.")
        extension = batch.archivo_extension.lower()
        if extension not in self.parsers:
            raise StructuralFileError(f"Extensión no soportada: {extension}.")
        relative_path = PurePath(batch.archivo_ruta)
        if not batch.archivo_ruta or relative_path.is_absolute() or ".." in relative_path.parts:
            raise FileSecurityError("La ruta privada registrada no es segura.")

        storage_root = Path(os.path.abspath(self.settings.storage_root))
        source_path = Path(os.path.abspath(storage_root / Path(batch.archivo_ruta)))
        if not source_path.is_relative_to(storage_root):
            raise FileSecurityError("El archivo resuelve fuera del storage privado permitido.")
        relative_parts = source_path.relative_to(storage_root).parts
        current_path = storage_root
        for part in relative_parts:
            current_path /= part
            if current_path.is_symlink():
                raise FileSecurityError("No se permiten enlaces simbólicos en la ruta privada.")
        if not source_path.is_file():
            raise FileSecurityError("El archivo privado registrado no existe.")
        if source_path.suffix.lower() != f".{extension}":
            raise FileSecurityError("La extensión física no coincide con el batch registrado.")

        return source_path

    @staticmethod
    def _verify_source_hash(batch: BatchRecord, source_path: Path) -> None:
        if not batch.archivo_sha256:
            return
        with source_path.open("rb") as source:
            actual_hash = hashlib.file_digest(source, "sha256").hexdigest()
        if actual_hash.lower() != batch.archivo_sha256.lower():
            raise FileSecurityError("El SHA-256 del archivo no coincide con el batch registrado.")

    @staticmethod
    def _fatal_message(exception: Exception) -> str:
        if isinstance(exception, EtlError):
            return str(exception)
        return f"Error fatal durante el procesamiento: {type(exception).__name__}."

    @staticmethod
    def _log_context(
        batch: BatchRecord,
        stats: ProcessingStats,
        duration: float,
        status: str,
    ) -> dict[str, object]:
        return {
            "batch_id": batch.batch_id,
            "tipo": batch.tipo,
            "archivo": batch.archivo_original,
            "estado": status,
            "filas_procesadas": stats.file_rows,
            "filas_insertadas": stats.inserted_rows,
            "filas_error": stats.error_rows,
            "duracion_segundos": round(duration, 3),
        }

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path, PurePath
from typing import Callable

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
    ProcessingStats,
    RowError,
    SearchChunk,
    SearchDatabasePort,
    SearchNormalizedRecord,
)
from ..domain.normalizers import utc_now_naive
from ..parsers.search_parser import SearchParser
from ..profiles.search.personas import PersonasV1Normalizer
from ..profiles.search.personas import PERSON_FIELDS
from ..profiles.search.telefonos import PHONE_FIELDS, TelefonosV1Normalizer
from .pagos_loader import ProcessingResult

LOGGER = logging.getLogger("kpdm.etl.search")


class SearchLoader:
    def __init__(
        self,
        database: SearchDatabasePort,
        settings: Settings,
        *,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.database = database
        self.settings = settings
        self.clock = clock

    def process(self, batch_id: int) -> ProcessingResult:
        stats = ProcessingStats()
        batch = self.database.get_batch(batch_id)
        if batch is None:
            raise BatchNotFoundError(f"No existe el batch #{batch_id}.")
        self._validate_batch(batch)
        try:
            source_path = self._validated_source_path(batch)
        except EtlError as exception:
            self.database.fail_batch(batch_id, self.clock(), str(exception), stats)
            raise
        started_at = self.clock()
        if not self.database.claim_batch(batch_id, started_at):
            raise BatchStateError(f"El batch #{batch_id} ya fue reclamado por otro worker.")

        try:
            self._verify_source_hash(batch, source_path)
            mapping = self.database.get_search_mapping(batch)
            target_fields, normalizer = self._profile(batch)
            parser = SearchParser(batch.archivo_extension, mapping, target_fields)
            self._consume_rows(batch, source_path, parser, normalizer, stats, started_at)
            if stats.file_rows == 0:
                raise StructuralFileError("El archivo SEARCH no contiene filas de datos.")
            if stats.error_rows:
                self.database.finish_search_with_errors(batch_id, self.clock(), stats)
                return ProcessingResult(batch_id, "COMPLETADO_CON_ERRORES", stats)
            self.database.publish_search(batch, self.clock(), stats)
            return ProcessingResult(batch_id, "COMPLETADO", stats)
        except Exception as exception:
            message = str(exception) if isinstance(exception, EtlError) else (
                f"Error fatal durante el procesamiento SEARCH: {type(exception).__name__}."
            )
            self.database.fail_batch(batch_id, self.clock(), message, stats)
            LOGGER.exception("search_batch_failed", extra={"context": {"batch_id": batch_id}})
            if isinstance(exception, EtlError):
                raise
            raise StructuralFileError(message) from exception

    def _consume_rows(
        self,
        batch: BatchRecord,
        source_path: Path,
        parser: SearchParser,
        normalizer,
        stats: ProcessingStats,
        ingested_at: datetime,
    ) -> None:
        chunk = SearchChunk()
        for row in parser.rows(source_path):
            raw, record, errors = normalizer.normalize(row, batch, ingested_at)
            chunk.raw_records.append(raw)
            chunk.file_rows += 1
            if record is None:
                chunk.error_rows += 1
                chunk.errors.extend(errors)
            else:
                chunk.records.append(record)
            if chunk.file_rows >= self.settings.insert_batch_size:
                self._flush_chunk(batch, chunk, stats)
        if chunk.file_rows:
            self._flush_chunk(batch, chunk, stats)
        self.database.update_progress(batch.batch_id, stats)

    def _flush_chunk(self, batch: BatchRecord, chunk: SearchChunk, stats: ProcessingStats) -> None:
        unique_records: list[SearchNormalizedRecord] = []
        seen_in_chunk: set[tuple[str, ...]] = set()
        for record in chunk.records:
            if record.deduplication_key in seen_in_chunk:
                self._append_duplicate_error(chunk, record)
                continue
            seen_in_chunk.add(record.deduplication_key)
            unique_records.append(record)

        existing = self.database.existing_search_record_keys(batch, unique_records)
        accepted: list[SearchNormalizedRecord] = []
        for record in unique_records:
            if record.deduplication_key in existing:
                self._append_duplicate_error(chunk, record)
            else:
                accepted.append(record)

        inserted_scope_documents = self.database.insert_search_chunk(
            chunk.raw_records,
            accepted,
            chunk.errors,
        )
        stats.file_rows += chunk.file_rows
        stats.inserted_rows += len(accepted)
        stats.error_rows += chunk.error_rows
        stats.duplicate_rows += chunk.duplicate_rows
        stats.scope_count += inserted_scope_documents
        LOGGER.info(
            "search_chunk_committed",
            extra={
                "context": {
                    "batch_id": batch.batch_id,
                    "filas_procesadas": stats.file_rows,
                    "filas_validas": stats.inserted_rows,
                    "filas_invalidas": stats.error_rows,
                }
            },
        )
        chunk.clear()

    def _append_duplicate_error(
        self,
        chunk: SearchChunk,
        record: SearchNormalizedRecord,
    ) -> None:
        is_phone = len(record.deduplication_key) == 2
        chunk.errors.append(
            RowError(
                batch_id=chunk.raw_records[0].batch_id,
                row_number=record.source_row,
                field="telefono" if is_phone else "documento",
                value="|".join(record.deduplication_key),
                message=(
                    "DUPLICATE_DOCUMENT_PHONE"
                    if is_phone
                    else "Documento duplicado dentro del mismo batch PERSONAS"
                ),
                created_at=record.created_at,
            )
        )
        chunk.error_rows += 1
        chunk.duplicate_rows += 1

    @staticmethod
    def _validate_batch(batch: BatchRecord) -> None:
        if batch.estado != "PENDIENTE":
            raise BatchStateError(
                f"El batch #{batch.batch_id} está en {batch.estado}; solo se procesa PENDIENTE."
            )
        if (
            batch.tipo != "SEARCH"
            or batch.dataset_code not in {"PERSONAS", "TELEFONOS"}
            or batch.source_code is None
            or batch.mapping_version is None
            or batch.perfil_version != "1"
            or batch.refresh_mode not in {"FULL_REPLACE", "SCOPE_REPLACE"}
        ):
            raise StructuralFileError("El batch no corresponde a un perfil SEARCH v1 publicable.")

    def _profile(self, batch: BatchRecord):
        if batch.dataset_code == "PERSONAS":
            return PERSON_FIELDS, PersonasV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "TELEFONOS":
            return PHONE_FIELDS, TelefonosV1Normalizer(self.settings.error_value_max_length)
        raise StructuralFileError("Dataset SEARCH no soportado.")

    def _validated_source_path(self, batch: BatchRecord) -> Path:
        if batch.archivo_extension not in {"csv", "xlsx"}:
            raise StructuralFileError(f"Extensión no soportada: {batch.archivo_extension}.")
        relative_path = PurePath(batch.archivo_ruta)
        if not batch.archivo_ruta or relative_path.is_absolute() or ".." in relative_path.parts:
            raise FileSecurityError("La ruta privada registrada no es segura.")
        storage_root = Path(os.path.abspath(self.settings.storage_root))
        source_path = Path(os.path.abspath(storage_root / Path(batch.archivo_ruta)))
        if not source_path.is_relative_to(storage_root) or not source_path.is_file():
            raise FileSecurityError("El archivo privado SEARCH no existe o está fuera del storage.")
        return source_path

    @staticmethod
    def _verify_source_hash(batch: BatchRecord, source_path: Path) -> None:
        if not batch.archivo_sha256:
            return
        with source_path.open("rb") as source:
            actual_hash = hashlib.file_digest(source, "sha256").hexdigest()
        if actual_hash.lower() != batch.archivo_sha256.lower():
            raise FileSecurityError("El SHA-256 del archivo no coincide con el batch registrado.")

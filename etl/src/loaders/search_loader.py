from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime
from pathlib import Path, PurePath
from typing import Callable

from ..config import Settings
from ..domain.errors import (
    BatchNotFoundError,
    BatchStateError,
    EtlError,
    FileSecurityError,
    SearchRecoveryError,
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
from ..domain.normalizers import cell_to_text
from ..parsers.search_parser import SearchParser
from ..profiles.search.personas import PersonasV1Normalizer
from ..profiles.search.personas import PERSON_FIELDS
from ..profiles.search.telefonos import PHONE_FIELDS, TelefonosV1Normalizer
from ..profiles.search.correos import EMAIL_FIELDS, CorreosV1Normalizer
from ..profiles.search.direcciones import ADDRESS_FIELDS, DireccionesV1Normalizer
from ..profiles.search.vehiculos import VEHICLE_FIELDS, VehiculosV1Normalizer
from ..profiles.search.propiedades import PROPERTY_FIELDS, PropiedadesV1Normalizer
from ..profiles.search.sbs_resumen import SBS_SUMMARY_FIELDS, SbsResumenV1Normalizer
from ..profiles.search.sbs_detalle import SBS_DETAIL_FIELDS, SbsDetalleV1Normalizer
from ..profiles.search.laboral_essalud import ESSALUD_FIELDS, LaboralEssaludV1Normalizer
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
        stage = "search_ingestion"
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
            stage = "search_gold_publish"
            self.database.publish_search(batch, self.clock(), stats)
            return ProcessingResult(batch_id, "COMPLETADO", stats)
        except Exception as exception:
            message = str(exception) if isinstance(exception, EtlError) else (
                f"Error fatal durante el procesamiento SEARCH: {type(exception).__name__}."
            )
            self.database.fail_batch(batch_id, self.clock(), message, stats)
            LOGGER.error(
                "search_batch_failed",
                extra={
                    "context": {
                        "batch_id": batch_id,
                        "stage": stage,
                        "error_type": type(exception).__name__,
                        "error_code": self._safe_error_code(exception),
                    }
                },
            )
            if isinstance(exception, EtlError):
                raise
            raise StructuralFileError(message) from exception

    def recover_publish(self, batch_id: int) -> ProcessingResult:
        batch = self.database.get_batch(batch_id)
        if batch is None:
            raise BatchNotFoundError(f"No existe el batch #{batch_id}.")
        self._validate_recovery_batch(batch)

        stage = "recovery_preflight"
        stats = ProcessingStats()
        LOGGER.info("recovery_started", extra={"context": {"batch_id": batch_id}})
        try:
            stats = self.database.preflight_search_recovery(batch)
            LOGGER.info(
                "recovery_preflight_ok",
                extra={"context": {"batch_id": batch_id}},
            )
            stage = "search_gold_publish"
            LOGGER.info(
                "search_gold_publish_started",
                extra={"context": {"batch_id": batch_id}},
            )
            self.database.publish_search(batch, self.clock(), stats, recovery=True)
            LOGGER.info(
                "search_gold_publish_completed",
                extra={"context": {"batch_id": batch_id}},
            )
            LOGGER.info("recovery_completed", extra={"context": {"batch_id": batch_id}})

            return ProcessingResult(batch_id, "COMPLETADO", stats)
        except Exception as exception:
            try:
                self.database.mark_search_recovery_failed(batch_id, self.clock())
            except Exception as failure_mark_exception:
                LOGGER.error(
                    "search_recovery_failure_mark_failed",
                    extra={
                        "context": {
                            "batch_id": batch_id,
                            "stage": stage,
                            "error_type": type(failure_mark_exception).__name__,
                            "error_code": self._safe_error_code(failure_mark_exception),
                        }
                    },
                )
            LOGGER.error(
                "search_recovery_failed",
                extra={
                    "context": {
                        "batch_id": batch_id,
                        "stage": stage,
                        "error_type": type(exception).__name__,
                        "error_code": self._safe_error_code(exception),
                    }
                },
            )
            raise SearchRecoveryError(stage, exception) from exception

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
        conflicts: dict[tuple[str, str], tuple[object, ...]] = {}
        for row in parser.rows(source_path):
            raw, record, errors = normalizer.normalize(row, batch, ingested_at)
            chunk.raw_records.append(raw)
            chunk.file_rows += 1
            scope_document = self._scope_document(row)
            if scope_document is not None and (record is not None or not errors):
                chunk.scope_documents.append(scope_document)
            if record is None and errors:
                chunk.error_rows += 1
                chunk.errors.extend(errors)
            elif record is not None:
                conflict = self._conflict_error(batch, record, conflicts, ingested_at)
                if conflict is not None:
                    chunk.error_rows += 1
                    chunk.errors.append(conflict)
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
                self._append_duplicate(chunk, record, batch)
                continue
            seen_in_chunk.add(record.deduplication_key)
            unique_records.append(record)

        existing = self.database.existing_search_record_keys(batch, unique_records)
        accepted: list[SearchNormalizedRecord] = []
        for record in unique_records:
            if record.deduplication_key in existing:
                self._append_duplicate(chunk, record, batch)
            else:
                accepted.append(record)

        inserted_scope_documents = self.database.insert_search_chunk(
            chunk.raw_records,
            accepted,
            chunk.errors,
            list(dict.fromkeys(chunk.scope_documents)),
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

    @staticmethod
    def _scope_document(row) -> str | None:
        try:
            document = cell_to_text(row.mapped_values["documento"])
        except (KeyError, ValueError):
            return None
        if document is None or re.fullmatch(r"[0-9]{8}", document) is None:
            return None
        return document

    def _append_duplicate(
        self,
        chunk: SearchChunk,
        record: SearchNormalizedRecord,
        batch: BatchRecord,
    ) -> None:
        if batch.dataset_code in {"CORREOS", "DIRECCIONES", "VEHICULOS", "PROPIEDADES", "SBS_RESUMEN", "SBS_DETALLE", "LABORAL_ESSALUD"}:
            chunk.duplicate_rows += 1
            return
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
    def _conflict_error(
        batch: BatchRecord,
        record: SearchNormalizedRecord,
        conflicts: dict[tuple[str, str], tuple[object, ...]],
        created_at: datetime,
    ) -> RowError | None:
        if batch.dataset_code not in {"VEHICULOS", "PROPIEDADES", "SBS_RESUMEN"}:
            return None
        key = getattr(record, "conflict_key", None)
        if key is None:
            return None
        signature = getattr(record, "conflict_signature")
        previous = conflicts.setdefault(key, signature)
        if previous == signature:
            return None
        messages = {
            "VEHICULOS": ("placa", "VEHICLE_PLATE_CONFLICT"),
            "PROPIEDADES": ("partida_registral", "PROPERTY_CONFLICT"),
            "SBS_RESUMEN": ("cod_sbs", "SBS_SUMMARY_CONFLICT"),
        }
        field, message = messages[batch.dataset_code]
        return RowError(batch.batch_id, record.source_row, field, "|".join(key), message, created_at)

    @staticmethod
    def _validate_batch(batch: BatchRecord) -> None:
        if batch.estado != "PENDIENTE":
            raise BatchStateError(
                f"El batch #{batch.batch_id} está en {batch.estado}; solo se procesa PENDIENTE."
            )
        if (
            batch.tipo != "SEARCH"
            or batch.dataset_code not in {"PERSONAS", "TELEFONOS", "CORREOS", "DIRECCIONES", "VEHICULOS", "PROPIEDADES", "SBS_RESUMEN", "SBS_DETALLE", "LABORAL_ESSALUD"}
            or batch.source_code is None
            or batch.mapping_version is None
            or batch.perfil_version != "1"
            or batch.refresh_mode not in {"FULL_REPLACE", "SCOPE_REPLACE"}
        ):
            raise StructuralFileError("El batch no corresponde a un perfil SEARCH v1 publicable.")

    @staticmethod
    def _validate_recovery_batch(batch: BatchRecord) -> None:
        if batch.estado not in {"PROCESANDO", "ERROR"}:
            raise BatchStateError(
                f"El batch #{batch.batch_id} está en {batch.estado}; no es recuperable."
            )
        if (
            batch.tipo != "SEARCH"
            or batch.dataset_code not in {
                "PERSONAS", "TELEFONOS", "CORREOS", "DIRECCIONES", "VEHICULOS",
                "PROPIEDADES", "SBS_RESUMEN", "SBS_DETALLE", "LABORAL_ESSALUD",
            }
            or batch.source_code is None
            or batch.refresh_mode not in {"FULL_REPLACE", "SCOPE_REPLACE"}
        ):
            raise StructuralFileError("El batch no corresponde a una recuperación SEARCH publicable.")

    @staticmethod
    def _safe_error_code(exception: Exception) -> int | None:
        for value in getattr(exception, "args", ()):
            if isinstance(value, int):
                return value
        return None

    def _profile(self, batch: BatchRecord):
        if batch.dataset_code == "PERSONAS":
            return PERSON_FIELDS, PersonasV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "TELEFONOS":
            return PHONE_FIELDS, TelefonosV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "CORREOS":
            return EMAIL_FIELDS, CorreosV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "DIRECCIONES":
            return ADDRESS_FIELDS, DireccionesV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "VEHICULOS":
            return VEHICLE_FIELDS, VehiculosV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "PROPIEDADES":
            return PROPERTY_FIELDS, PropiedadesV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "SBS_RESUMEN":
            return SBS_SUMMARY_FIELDS, SbsResumenV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "SBS_DETALLE":
            return SBS_DETAIL_FIELDS, SbsDetalleV1Normalizer(self.settings.error_value_max_length)
        if batch.dataset_code == "LABORAL_ESSALUD":
            return ESSALUD_FIELDS, LaboralEssaludV1Normalizer(self.settings.error_value_max_length)
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

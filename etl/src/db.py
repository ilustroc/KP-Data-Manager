from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime
from typing import Sequence

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from .config import Settings
from .metrics import SearchMetrics
from .domain.models import (
    BBVA_SOURCE_COLUMNS,
    CAJA_AREQUIPA_BRONZE_COLUMNS,
    COMPARTAMOS_BRONZE_COLUMNS,
    CONFIANZA_BRONZE_COLUMNS,
    WANDOO_BRONZE_COLUMNS,
    BatchRecord,
    BbvaPortfolioRecord,
    CajaArequipaPortfolioRecord,
    CompartamosPortfolioRecord,
    ConfianzaPortfolioRecord,
    PaymentRecord,
    PortfolioRecord,
    ProcessingStats,
    RowError,
    SearchNormalizedRecord,
    SearchFamilyRecord,
    SearchPersonRecord,
    SearchPhoneRecord,
    SearchEmailRecord,
    SearchAddressRecord,
    SearchVehicleRecord,
    SearchPropertyRecord,
    SearchSbsSummaryRecord,
    SearchSbsDetailRecord,
    SearchEssaludRecord,
    SearchRawRecord,
    WandooPortfolioRecord,
)


class MetricsDictCursor(DictCursor):
    def execute(self, query, args=None):
        observer = getattr(self.connection, "_kpdm_statement_observer", None)
        if observer is not None:
            observer()

        return super().execute(query, args)


class MySqlDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection_phase = "connect"
        self._transaction_active = False
        self.last_cleanup_error_type: str | None = None
        self._active_metrics: SearchMetrics | None = None
        self._active_metric_phase: str | None = None
        self.connection: Connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_username,
            password=settings.db_password,
            database=settings.control_database,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=MetricsDictCursor,
            connect_timeout=settings.db_connect_timeout,
            read_timeout=settings.db_read_timeout,
            write_timeout=settings.db_write_timeout,
        )
        self.connection._kpdm_statement_observer = self._record_physical_statement
        try:
            self.connection_phase = "session_setup"
            with self.connection.cursor() as cursor:
                cursor.execute("SET time_zone = '+00:00'")
        except Exception:
            self.close()
            raise
        self.connection_phase = "ready"

    def get_batch(self, batch_id: int) -> BatchRecord | None:
        self.connection_phase = "execute"
        sql = f"""
            SELECT batch_id, tipo, entidad, perfil_version, dataset_code, source_code,
                   refresh_mode, mapping_version, estado, archivo, archivo_original,
                   archivo_ruta, archivo_extension, archivo_sha256
            FROM `{self.settings.control_database}`.`import_batch`
            WHERE batch_id = %s
            LIMIT 1
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (batch_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        original_name = row["archivo_original"] or row["archivo"]
        extension = row["archivo_extension"] or original_name.rsplit(".", 1)[-1]
        return BatchRecord(
            batch_id=int(row["batch_id"]),
            tipo=str(row["tipo"]),
            estado=str(row["estado"]),
            archivo_original=str(original_name),
            archivo_ruta=str(row["archivo_ruta"] or ""),
            archivo_extension=str(extension).lower(),
            archivo_sha256=None if row["archivo_sha256"] is None else str(row["archivo_sha256"]),
            entidad=None if row["entidad"] is None else str(row["entidad"]),
            perfil_version=None if row["perfil_version"] is None else str(row["perfil_version"]),
            dataset_code=None if row["dataset_code"] is None else str(row["dataset_code"]),
            source_code=None if row["source_code"] is None else str(row["source_code"]),
            refresh_mode=None if row["refresh_mode"] is None else str(row["refresh_mode"]),
            mapping_version=None
            if row["mapping_version"] is None
            else int(row["mapping_version"]),
        )

    def claim_batch(self, batch_id: int, started_at: datetime) -> bool:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = 'PROCESANDO', fecha_inicio = %s, fecha_fin = NULL,
                filas_archivo = 0, filas_insertadas = 0,
                filas_duplicadas = 0, filas_error = 0, mensaje_error = NULL
                , rows_valid = IF(tipo = 'SEARCH', 0, rows_valid),
                rows_invalid = IF(tipo = 'SEARCH', 0, rows_invalid),
                rows_published = IF(tipo = 'SEARCH', 0, rows_published),
                scope_count = IF(tipo = 'SEARCH', 0, scope_count),
                validated_at = IF(tipo = 'SEARCH', NULL, validated_at),
                published_at = IF(tipo = 'SEARCH', NULL, published_at)
            WHERE batch_id = %s AND estado = 'PENDIENTE'
        """
        with self.connection.cursor() as cursor:
            affected = cursor.execute(sql, (started_at, batch_id))
        return affected == 1

    def insert_chunk(
        self,
        payments: Sequence[PaymentRecord],
        errors: Sequence[RowError],
    ) -> None:
        payment_sql = f"""
            INSERT INTO `{self.settings.bronze_database}`.`raw_pagos`
                (`FECHA`, `DOCUMENTO`, `MONTO`, `ACUMULADO`, `RECAUDO`,
                 `OPERACION`, `COMENTARIO`, `HORA`, `source_file`, `batch_id`,
                 `ingested_at`, `row_hash`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        error_sql = f"""
            INSERT INTO `{self.settings.control_database}`.`import_error`
                (`batch_id`, `numero_fila`, `campo`, `valor`, `error`, `created_at`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        self._begin_transaction()
        try:
            with self.connection.cursor() as cursor:
                if payments:
                    cursor.executemany(payment_sql, [payment.as_insert_tuple() for payment in payments])
                if errors:
                    cursor.executemany(error_sql, [error.as_insert_tuple() for error in errors])
            self._commit_transaction()
        except Exception:
            self._rollback_transaction_safely()
            raise

    def update_progress(self, batch_id: int, stats: ProcessingStats) -> None:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET filas_archivo = %s, filas_insertadas = %s,
                filas_duplicadas = %s, filas_error = %s,
                rows_valid = IF(tipo = 'SEARCH', %s, rows_valid),
                rows_invalid = IF(tipo = 'SEARCH', %s, rows_invalid),
                scope_count = IF(tipo = 'SEARCH', %s, scope_count)
            WHERE batch_id = %s AND estado = 'PROCESANDO'
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    stats.file_rows,
                    stats.inserted_rows,
                    stats.duplicate_rows,
                    stats.error_rows,
                    stats.inserted_rows,
                    stats.error_rows,
                    stats.scope_count,
                    batch_id,
                ),
            )

    def get_search_mapping(self, batch: BatchRecord) -> Sequence[dict[str, object]]:
        if (
            batch.dataset_code is None
            or batch.source_code is None
            or batch.mapping_version is None
        ):
            raise RuntimeError("El batch SEARCH no tiene mapping completo.")
        sql = f"""
            SELECT source_position, source_column, target_column, is_required,
                   transformation, default_value
            FROM `{self.settings.control_database}`.`import_column_mapping`
            WHERE dataset_code = %s AND source_code = %s
              AND mapping_version = %s AND is_active = 1
            ORDER BY source_position
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (batch.dataset_code, batch.source_code, batch.mapping_version),
            )
            return list(cursor.fetchall())

    def existing_search_record_keys(
        self,
        batch: BatchRecord,
        records: Sequence[SearchNormalizedRecord],
    ) -> set[tuple[str, ...]]:
        if not records:
            return set()
        if batch.dataset_code == "PERSONAS":
            documents = [record.documento for record in records]
            placeholders = ", ".join(["%s"] * len(documents))
            sql = f"""
                SELECT documento
                FROM `{self.settings.silver_database}`.`search_personas`
                WHERE batch_id = %s AND documento IN ({placeholders})
            """
            values: tuple[object, ...] = (batch.batch_id, *documents)
        elif batch.dataset_code == "TELEFONOS":
            clauses = " OR ".join(["(documento = %s AND telefono = %s)"] * len(records))
            sql = f"""
                SELECT documento, telefono
                FROM `{self.settings.silver_database}`.`search_telefonos`
                WHERE batch_id = %s AND ({clauses})
            """
            values = (
                batch.batch_id,
                *(value for record in records for value in record.deduplication_key),
            )
        elif batch.dataset_code in {"CORREOS", "DIRECCIONES", "VEHICULOS", "PROPIEDADES", "SBS_RESUMEN", "SBS_DETALLE", "LABORAL_ESSALUD"}:
            tables = {
                "CORREOS": "search_correos",
                "DIRECCIONES": "search_direcciones",
                "VEHICULOS": "search_vehiculos",
                "PROPIEDADES": "search_propiedades",
                "SBS_RESUMEN": "search_sbs_resumen",
                "SBS_DETALLE": "search_sbs_detalle",
                "LABORAL_ESSALUD": "search_laboral_essalud",
            }
            hashes = [record.record_hash for record in records]
            placeholders = ", ".join(["%s"] * len(hashes))
            sql = f"""
                SELECT record_hash
                FROM `{self.settings.silver_database}`.`{tables[batch.dataset_code]}`
                WHERE batch_id = %s AND record_hash IN ({placeholders})
            """
            values = (batch.batch_id, *hashes)
        else:
            raise RuntimeError("Dataset SEARCH no soportado para deduplicación.")
        with self.connection.cursor() as cursor:
            cursor.execute(sql, values)
            if batch.dataset_code == "PERSONAS":
                return {(str(row["documento"]),) for row in cursor.fetchall()}
            if batch.dataset_code in {"CORREOS", "DIRECCIONES", "VEHICULOS", "PROPIEDADES", "SBS_RESUMEN", "SBS_DETALLE", "LABORAL_ESSALUD"}:
                return {(str(row["record_hash"]),) for row in cursor.fetchall()}
            return {
                (str(row["documento"]), str(row["telefono"])) for row in cursor.fetchall()
            }

    def insert_search_chunk(
        self,
        raw_records: Sequence[SearchRawRecord],
        records: Sequence[SearchNormalizedRecord],
        errors: Sequence[RowError],
        scope_documents: Sequence[str],
        *,
        metrics: SearchMetrics | None = None,
    ) -> int:
        if not raw_records:
            return 0
        raw_sql = f"""
            INSERT INTO `{self.settings.bronze_database}`.`search_raw_row`
                (`batch_id`, `dataset_code`, `source_code`, `source_row`, `source_file`,
                 `raw_payload`, `row_hash`, `ingested_at`)
            VALUES ({", ".join(["%s"] * 8)})
        """
        person_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_personas`
                (`documento`, `paterno`, `materno`, `nombres`, `nombre_completo`,
                 `fecha_nacimiento`, `direccion_origen`, `sexo`, `estado_civil`, `padre`,
                 `madre`, `source_code`, `batch_id`, `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 16)})
        """
        phone_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_telefonos`
                (`documento`, `telefono`, `operador`, `operador_raw`, `fecha_data`,
                 `source_code`, `batch_id`, `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 10)})
        """
        family_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_familiares`
                (`documento`, `documento_familiar`, `paterno_familiar`, `materno_familiar`,
                 `nombres_familiar`, `nacimiento_familiar`, `tipo_familiar`, `source_code`,
                 `batch_id`, `source_row_number`, `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 13)})
        """
        email_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_correos`
                (`documento`, `correo`, `correo_original`, `source_code`, `batch_id`,
                 `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 8)})
        """
        address_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_direcciones`
                (`documento`, `direccion`, `departamento`, `provincia`, `distrito`,
                 `data_procedencia`, `procedencia_anio`, `source_code`, `batch_id`,
                 `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 12)})
        """
        vehicle_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_vehiculos`
                (`documento`, `nombre_completo_fuente`, `clase`, `anio_compra`,
                 `anio_fabricacion`, `marca`, `placa`, `placa_original`,
                 `numero_transferencias`, `source_code`, `batch_id`, `source_raw_id`,
                 `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 14)})
        """
        property_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_propiedades`
                (`documento`, `partida_registral`, `zona_registral`, `oficina`,
                 `source_code`, `batch_id`, `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 9)})
        """
        summary_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_sbs_resumen`
                (`documento`, `cod_sbs`, `fecha_reporte_sbs`, `cantidad_empresas`,
                 `calificacion_normal`, `calificacion_cpp`, `calificacion_deficiente`,
                 `calificacion_dudoso`, `calificacion_perdida`, `source_code`, `batch_id`,
                 `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 14)})
        """
        detail_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_sbs_detalle`
                (`fecha_reporte_sbs`, `documento`, `cod_sbs`, `entidad`, `tipo_credito`,
                 `condicion`, `monto`, `dias_atraso`, `source_code`, `batch_id`,
                 `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 13)})
        """
        essalud_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`search_laboral_essalud`
                (`documento`, `periodo`, `ruc`, `nombre_empresa`, `sueldo`, `situacion`,
                 `source_code`, `batch_id`, `source_raw_id`, `record_hash`, `created_at`)
            VALUES ({", ".join(["%s"] * 11)})
        """
        scope_sql = f"""
            INSERT INTO `{self.settings.control_database}`.`import_scope_document`
                (`batch_id`, `documento`, `created_at`)
            VALUES (%s, %s, %s)
        """
        error_sql = f"""
            INSERT INTO `{self.settings.control_database}`.`import_error`
                (`batch_id`, `numero_fila`, `campo`, `valor`, `error`, `created_at`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        self._begin_transaction()
        inserted_scope_documents = 0
        try:
            with self.connection.cursor() as cursor:
                with self._measure(
                    metrics,
                    "bronze_insert",
                    rows_processed=len(raw_records),
                    logical_statement_count=1,
                    executemany_calls=1,
                ):
                    cursor.executemany(
                        raw_sql,
                        [record.as_insert_tuple() for record in raw_records],
                    )
                row_numbers = [record.source_row for record in raw_records]
                placeholders = ", ".join(["%s"] * len(row_numbers))
                with self._measure(
                    metrics,
                    "bronze_id_lookup",
                    rows_processed=len(raw_records),
                    logical_statement_count=1,
                ):
                    cursor.execute(
                        f"""
                            SELECT raw_id, source_row
                            FROM `{self.settings.bronze_database}`.`search_raw_row`
                            WHERE batch_id = %s AND source_row IN ({placeholders})
                        """,
                        (raw_records[0].batch_id, *row_numbers),
                    )
                    raw_ids = {
                        int(row["source_row"]): int(row["raw_id"])
                        for row in cursor.fetchall()
                    }
                if len(raw_ids) != len(raw_records):
                    raise RuntimeError("No se pudieron correlacionar todas las filas Bronze SEARCH.")
                if records:
                    record_type = type(records[0])
                    if any(type(record) is not record_type for record in records):
                        raise RuntimeError("Un chunk SEARCH no puede mezclar datasets.")
                    if record_type is SearchPersonRecord:
                        silver_sql = person_sql
                    elif record_type is SearchPhoneRecord:
                        silver_sql = phone_sql
                    elif record_type is SearchFamilyRecord:
                        silver_sql = family_sql
                    elif record_type is SearchEmailRecord:
                        silver_sql = email_sql
                    elif record_type is SearchAddressRecord:
                        silver_sql = address_sql
                    elif record_type is SearchVehicleRecord:
                        silver_sql = vehicle_sql
                    elif record_type is SearchPropertyRecord:
                        silver_sql = property_sql
                    elif record_type is SearchSbsSummaryRecord:
                        silver_sql = summary_sql
                    elif record_type is SearchSbsDetailRecord:
                        silver_sql = detail_sql
                    elif record_type is SearchEssaludRecord:
                        silver_sql = essalud_sql
                    else:
                        raise RuntimeError("Tipo de registro SEARCH no soportado.")
                    with self._measure(
                        metrics,
                        "silver_insert",
                        rows_processed=len(records),
                        logical_statement_count=1,
                        executemany_calls=1,
                    ):
                        cursor.executemany(
                            silver_sql,
                            [
                                record.as_insert_tuple(raw_ids[record.source_row])
                                for record in records
                            ],
                        )
                    documents = list(dict.fromkeys(scope_documents))
                    if not documents:
                        documents = list(dict.fromkeys(record.documento for record in records))
                    if documents:
                        placeholders = ", ".join(["%s"] * len(documents))
                        with self._measure(
                            metrics,
                            "scope_lookup",
                            rows_processed=len(documents),
                            logical_statement_count=1,
                        ):
                            cursor.execute(
                                f"""
                                    SELECT documento
                                    FROM `{self.settings.control_database}`.`import_scope_document`
                                    WHERE batch_id = %s AND documento IN ({placeholders})
                                """,
                                (raw_records[0].batch_id, *documents),
                            )
                            existing_documents = {
                                str(row["documento"]) for row in cursor.fetchall()
                            }
                        new_documents = [
                            document for document in documents if document not in existing_documents
                        ]
                        if new_documents:
                            with self._measure(
                                metrics,
                                "scope_insert",
                                rows_processed=len(new_documents),
                                logical_statement_count=1,
                                executemany_calls=1,
                            ):
                                cursor.executemany(
                                    scope_sql,
                                    [
                                        (
                                            raw_records[0].batch_id,
                                            document,
                                            raw_records[0].ingested_at,
                                        )
                                        for document in new_documents
                                    ],
                                )
                            inserted_scope_documents = len(new_documents)
                elif scope_documents:
                    documents = list(dict.fromkeys(scope_documents))
                    placeholders = ", ".join(["%s"] * len(documents))
                    with self._measure(
                        metrics,
                        "scope_lookup",
                        rows_processed=len(documents),
                        logical_statement_count=1,
                    ):
                        cursor.execute(
                            f"SELECT documento FROM `{self.settings.control_database}`.`import_scope_document` WHERE batch_id = %s AND documento IN ({placeholders})",
                            (raw_records[0].batch_id, *documents),
                        )
                        existing_documents = {
                            str(row["documento"]) for row in cursor.fetchall()
                        }
                    new_documents = [document for document in documents if document not in existing_documents]
                    if new_documents:
                        with self._measure(
                            metrics,
                            "scope_insert",
                            rows_processed=len(new_documents),
                            logical_statement_count=1,
                            executemany_calls=1,
                        ):
                            cursor.executemany(
                                scope_sql,
                                [
                                    (
                                        raw_records[0].batch_id,
                                        document,
                                        raw_records[0].ingested_at,
                                    )
                                    for document in new_documents
                                ],
                            )
                        inserted_scope_documents = len(new_documents)
                if errors:
                    cursor.executemany(error_sql, [error.as_insert_tuple() for error in errors])
            with self._measure(
                metrics,
                "commit",
                rows_processed=len(raw_records),
                logical_statement_count=1,
            ):
                self._commit_transaction()
            return inserted_scope_documents
        except Exception:
            self._rollback_transaction_safely()
            raise

    def finish_search_with_errors(
        self,
        batch_id: int,
        finished_at: datetime,
        stats: ProcessingStats,
    ) -> None:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = 'COMPLETADO_CON_ERRORES', fecha_fin = %s, validated_at = %s,
                filas_archivo = %s, filas_insertadas = %s, filas_duplicadas = %s,
                filas_error = %s, rows_valid = %s, rows_invalid = %s,
                rows_published = 0, scope_count = %s, mensaje_error = NULL
            WHERE batch_id = %s AND estado = 'PROCESANDO'
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    finished_at,
                    finished_at,
                    stats.file_rows,
                    stats.inserted_rows,
                    stats.duplicate_rows,
                    stats.error_rows,
                    stats.inserted_rows,
                    stats.error_rows,
                    stats.scope_count,
                    batch_id,
                ),
            )

    def preflight_search_recovery(
        self,
        batch: BatchRecord,
        *,
        metrics: SearchMetrics | None = None,
    ) -> ProcessingStats:
        with self._measure(
            metrics,
            "preflight",
            logical_statement_count=5,
        ):
            return self._preflight_search_recovery(batch)

    def _preflight_search_recovery(self, batch: BatchRecord) -> ProcessingStats:
        self.connection_phase = "execute"
        if batch.source_code is None or batch.dataset_code is None:
            raise RuntimeError("El batch SEARCH no tiene contexto de recuperación completo.")
        tables = {
            "PERSONAS": "search_personas",
            "TELEFONOS": "search_telefonos",
            "FAMILIA": "search_familiares",
            "CORREOS": "search_correos",
            "DIRECCIONES": "search_direcciones",
            "VEHICULOS": "search_vehiculos",
            "PROPIEDADES": "search_propiedades",
            "SBS_RESUMEN": "search_sbs_resumen",
            "SBS_DETALLE": "search_sbs_detalle",
            "LABORAL_ESSALUD": "search_laboral_essalud",
        }
        silver_table = tables.get(batch.dataset_code)
        if silver_table is None:
            raise RuntimeError("El dataset SEARCH no admite recuperación.")

        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                    SELECT estado, filas_archivo, filas_duplicadas, rows_valid, rows_invalid,
                           scope_count
                    FROM `{self.settings.control_database}`.`import_batch`
                    WHERE batch_id = %s
                    LIMIT 1
                """,
                (batch.batch_id,),
            )
            persisted = cursor.fetchone()
            if persisted is None or persisted["estado"] not in {"PROCESANDO", "ERROR"}:
                raise RuntimeError("El estado actual del batch no permite recuperación.")
            if int(persisted["rows_invalid"] or 0) != 0:
                raise RuntimeError("El batch SEARCH contiene filas inválidas y no es recuperable.")

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM `{self.settings.bronze_database}`.`search_raw_row` WHERE dataset_code = %s AND source_code = %s AND batch_id = %s",
                (batch.dataset_code, batch.source_code, batch.batch_id),
            )
            bronze_count = int(cursor.fetchone()["total"])
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM `{self.settings.silver_database}`.`{silver_table}` WHERE batch_id = %s",
                (batch.batch_id,),
            )
            silver_count = int(cursor.fetchone()["total"])
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM `{self.settings.control_database}`.`import_scope_document` WHERE batch_id = %s",
                (batch.batch_id,),
            )
            scope_count = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                    SELECT dataset_source.source_code, dataset_source.allows_full_replace,
                           dataset_source.allows_scope_replace, dataset_source.allows_upsert
                    FROM `{self.settings.control_database}`.`import_dataset_source` AS dataset_source
                    INNER JOIN `{self.settings.control_database}`.`import_source` AS source
                        ON source.source_code = dataset_source.source_code
                    WHERE dataset_source.dataset_code = %s
                      AND dataset_source.source_code = %s
                      AND dataset_source.is_active = 1
                      AND source.is_active = 1
                    LIMIT 1
                """,
                (batch.dataset_code, batch.source_code),
            )
            source = cursor.fetchone()

        expected_file_rows = int(persisted["filas_archivo"] or 0)
        expected_valid_rows = int(persisted["rows_valid"] or 0)
        expected_scope_count = int(persisted["scope_count"] or 0)
        if bronze_count != expected_file_rows:
            raise RuntimeError("Bronze no coincide con las filas persistidas del batch SEARCH.")
        if silver_count != expected_valid_rows:
            raise RuntimeError("Silver no coincide con las filas válidas persistidas del batch SEARCH.")
        if scope_count != expected_scope_count:
            raise RuntimeError("El scope no coincide con el batch SEARCH.")
        if source is None:
            raise RuntimeError("La fuente SEARCH no está activa ni autorizada.")
        permission_column = self._search_permission_column(batch)
        if int(source[permission_column]) != 1:
            raise RuntimeError("El modo de actualización SEARCH no está autorizado.")

        return ProcessingStats(
            file_rows=expected_file_rows,
            inserted_rows=expected_valid_rows,
            error_rows=0,
            duplicate_rows=int(persisted["filas_duplicadas"] or 0),
            scope_count=expected_scope_count,
        )

    def mark_search_recovery_failed(self, batch_id: int, finished_at: datetime) -> None:
        self.connection_phase = "execute"
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = 'ERROR', fecha_fin = %s,
                mensaje_error = 'No fue posible recuperar la publicación Gold SEARCH. Revisa el log técnico.'
            WHERE batch_id = %s AND estado = 'PROCESANDO'
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (finished_at, batch_id))

    def publish_search(
        self,
        batch: BatchRecord,
        published_at: datetime,
        stats: ProcessingStats,
        *,
        recovery: bool = False,
        metrics: SearchMetrics | None = None,
    ) -> None:
        if batch.source_code is None:
            raise RuntimeError("El publicador SEARCH recibió un batch incompatible.")
        self._search_permission_column(batch)
        tables = {
            "PERSONAS": ("search_personas", "person_id", "search_person_index"),
            "TELEFONOS": ("search_telefonos", "phone_id", "search_telefonos"),
            "FAMILIA": ("search_familiares", "family_id", "search_familiares"),
            "CORREOS": ("search_correos", "email_id", "search_correos"),
            "DIRECCIONES": ("search_direcciones", "address_id", "search_direcciones"),
            "VEHICULOS": ("search_vehiculos", "vehicle_id", "search_vehiculos"),
            "PROPIEDADES": ("search_propiedades", "property_id", "search_propiedades"),
            "SBS_RESUMEN": ("search_sbs_resumen", "summary_id", "search_sbs_resumen"),
            "SBS_DETALLE": ("search_sbs_detalle", "detail_id", "search_sbs_detalle"),
            "LABORAL_ESSALUD": ("search_laboral_essalud", "employment_id", "search_laboral_essalud"),
        }
        if batch.dataset_code not in tables:
            raise RuntimeError("El publicador SEARCH recibió un dataset no soportado.")
        silver_table, silver_id, gold_table = tables[batch.dataset_code]
        (
            silver_to_scope_document_match,
            scope_to_silver_document_match,
        ) = self._search_scope_integrity_predicates(batch.dataset_code)
        publication_lock_name = self._search_publication_lock_name(batch)
        publication_lock_acquired = False
        try:
            with self.connection.cursor() as cursor:
                with self._measure(
                    metrics,
                    "gold_source_validation",
                    logical_statement_count=1,
                ):
                    self._acquire_search_publication_lock(cursor, publication_lock_name)
            publication_lock_acquired = True

            self._begin_transaction()
            try:
                self.connection_phase = "execute"
                with self.connection.cursor() as cursor:
                    with self._measure(
                        metrics,
                        "gold_source_validation",
                        logical_statement_count=2,
                    ):
                        self._validate_active_search_source(cursor, batch, lock=False)
                        self._ensure_gold_source_is_compatible(
                            cursor,
                            batch.source_code,
                            gold_table,
                        )

                    if batch.refresh_mode == "SCOPE_REPLACE":
                        with self._measure(
                            metrics,
                            "gold_delete",
                            logical_statement_count=1,
                        ) as measurement:
                            cursor.execute(
                                f"""
                                    DELETE gold
                                    FROM `{self.settings.gold_database}`.`{gold_table}` AS gold
                                    INNER JOIN `{self.settings.control_database}`.`import_scope_document` AS scope
                                        ON scope.documento = gold.documento
                                    WHERE scope.batch_id = %s
                                      AND gold.source_code = %s
                                """,
                                (batch.batch_id, batch.source_code),
                            )
                            if measurement is not None:
                                measurement.rows_processed = max(0, cursor.rowcount)
                        with self._measure(
                            metrics,
                            "gold_insert",
                            rows_processed=stats.inserted_rows,
                            logical_statement_count=1,
                        ):
                            self._insert_gold_search(
                                cursor,
                                batch,
                                published_at,
                                upsert=False,
                            )
                    elif batch.refresh_mode == "FULL_REPLACE":
                        with self._measure(
                            metrics,
                            "gold_insert",
                            rows_processed=stats.inserted_rows,
                            logical_statement_count=1,
                        ):
                            self._insert_gold_search(
                                cursor,
                                batch,
                                published_at,
                                upsert=True,
                            )
                        with self._measure(
                            metrics,
                            "gold_delete",
                            logical_statement_count=1,
                        ) as measurement:
                            cursor.execute(
                                f"DELETE FROM `{self.settings.gold_database}`.`{gold_table}` WHERE source_code = %s AND batch_id <> %s",
                                (batch.source_code, batch.batch_id),
                            )
                            if measurement is not None:
                                measurement.rows_processed = max(0, cursor.rowcount)
                    elif batch.refresh_mode == "UPSERT":
                        with self._measure(
                            metrics,
                            "gold_insert",
                            rows_processed=stats.inserted_rows,
                            logical_statement_count=1,
                        ):
                            self._insert_gold_search(
                                cursor,
                                batch,
                                published_at,
                                upsert=True,
                            )
                    else:
                        raise RuntimeError("Modo de publicación SEARCH no soportado.")

                    with self._measure(
                        metrics,
                        "integrity_validation",
                        rows_processed=stats.file_rows,
                        logical_statement_count=6,
                    ):
                        cursor.execute(
                            f"SELECT COUNT(*) AS total FROM `{self.settings.silver_database}`.`{silver_table}` WHERE batch_id = %s",
                            (batch.batch_id,),
                        )
                        silver_count = int(cursor.fetchone()["total"])
                        cursor.execute(
                            f"SELECT COUNT(*) AS total FROM `{self.settings.bronze_database}`.`search_raw_row` WHERE dataset_code = %s AND source_code = %s AND batch_id = %s",
                            (batch.dataset_code, batch.source_code, batch.batch_id),
                        )
                        bronze_count = int(cursor.fetchone()["total"])
                        cursor.execute(
                            f"SELECT COUNT(*) AS total FROM `{self.settings.control_database}`.`import_scope_document` WHERE batch_id = %s",
                            (batch.batch_id,),
                        )
                        scope_count = int(cursor.fetchone()["total"])
                        if (
                            stats.error_rows != 0
                            or bronze_count != stats.file_rows
                            or silver_count != stats.inserted_rows
                            or scope_count != stats.scope_count
                        ):
                            raise RuntimeError(
                                "Silver, scope y contadores del batch SEARCH no coinciden."
                            )

                        cursor.execute(
                            f"""
                                SELECT 1 AS found
                                FROM `{self.settings.silver_database}`.`{silver_table}` AS silver
                                LEFT JOIN `{self.settings.control_database}`.`import_scope_document` AS scope
                                  ON scope.batch_id = silver.batch_id
                                 AND {silver_to_scope_document_match}
                                WHERE silver.batch_id = %s AND scope.id IS NULL
                                LIMIT 1
                            """,
                            (batch.batch_id,),
                        )
                        silver_without_scope = cursor.fetchone() is not None
                        cursor.execute(
                            f"""
                                SELECT 1 AS found
                                FROM `{self.settings.control_database}`.`import_scope_document` AS scope
                                LEFT JOIN `{self.settings.silver_database}`.`{silver_table}` AS silver
                                  ON silver.batch_id = scope.batch_id
                                 AND {scope_to_silver_document_match}
                                WHERE scope.batch_id = %s AND silver.{silver_id} IS NULL
                                LIMIT 1
                            """,
                            (batch.batch_id,),
                        )
                        scope_without_silver = cursor.fetchone() is not None
                        allows_scope_without_silver = batch.dataset_code == "DIRECCIONES"
                        if silver_without_scope or (
                            scope_without_silver and not allows_scope_without_silver
                        ):
                            raise RuntimeError(
                                "El scope oficial no corresponde exactamente a Silver SEARCH."
                            )

                        cursor.execute(
                            f"SELECT COUNT(*) AS total FROM `{self.settings.gold_database}`.`{gold_table}` WHERE source_code = %s AND batch_id = %s",
                            (batch.source_code, batch.batch_id),
                        )
                        published_count = int(cursor.fetchone()["total"])
                        if published_count != silver_count:
                            raise RuntimeError(
                                "La cantidad publicada en Gold no coincide con Silver."
                            )

                    with self._measure(
                        metrics,
                        "batch_final_lock",
                        logical_statement_count=1,
                    ):
                        cursor.execute(
                            f"""
                                SELECT estado, filas_archivo, rows_valid, rows_invalid, scope_count
                                FROM `{self.settings.control_database}`.`import_batch`
                                WHERE batch_id = %s FOR UPDATE
                            """,
                            (batch.batch_id,),
                        )
                        locked_batch = cursor.fetchone()
                    allowed_states = (
                        {"PROCESANDO", "ERROR"} if recovery else {"PROCESANDO"}
                    )
                    if locked_batch is None or locked_batch["estado"] not in allowed_states:
                        raise RuntimeError("El batch dejó de estar publicable.")
                    persisted_counters = (
                        int(locked_batch["filas_archivo"] or 0),
                        int(locked_batch["rows_valid"] or 0),
                        int(locked_batch["rows_invalid"] or 0),
                        int(locked_batch["scope_count"] or 0),
                    )
                    expected_counters = (
                        stats.file_rows,
                        stats.inserted_rows,
                        stats.error_rows,
                        stats.scope_count,
                    )
                    if persisted_counters != expected_counters:
                        raise RuntimeError(
                            "Los contadores persistidos del batch SEARCH no coinciden."
                        )
                    with self._measure(
                        metrics,
                        "gold_source_validation",
                        logical_statement_count=1,
                    ):
                        self._validate_active_search_source(cursor, batch, lock=True)
                    with self._measure(
                        metrics,
                        "batch_finalize",
                        logical_statement_count=1,
                    ):
                        cursor.execute(
                            f"""
                                UPDATE `{self.settings.control_database}`.`import_batch`
                                SET estado = 'COMPLETADO', fecha_fin = %s, validated_at = %s,
                                    published_at = %s, filas_archivo = %s, filas_insertadas = %s,
                                    filas_duplicadas = %s, filas_error = %s, rows_valid = %s,
                                    rows_invalid = 0, rows_published = %s, scope_count = %s,
                                    mensaje_error = NULL
                                WHERE batch_id = %s
                                  AND estado {"IN ('PROCESANDO', 'ERROR')" if recovery else "= 'PROCESANDO'"}
                            """,
                            (
                                published_at,
                                published_at,
                                published_at,
                                stats.file_rows,
                                stats.inserted_rows,
                                stats.duplicate_rows,
                                stats.error_rows,
                                stats.inserted_rows,
                                published_count,
                                scope_count,
                                batch.batch_id,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise RuntimeError(
                                "No se pudo confirmar el estado publicado del batch."
                            )
                with self._measure(
                    metrics,
                    "commit",
                    rows_processed=published_count,
                    logical_statement_count=1,
                ):
                    self._commit_transaction()
            except Exception:
                self._rollback_transaction_safely()
                raise
        finally:
            if publication_lock_acquired:
                try:
                    with self.connection.cursor() as cursor:
                        with self._measure(
                            metrics,
                            "gold_source_validation",
                            logical_statement_count=1,
                        ):
                            self._release_search_publication_lock(
                                cursor,
                                publication_lock_name,
                            )
                except Exception as exception:
                    self.last_cleanup_error_type = type(exception).__name__

    def _validate_active_search_source(
        self,
        cursor: DictCursor,
        batch: BatchRecord,
        *,
        lock: bool,
    ) -> None:
        lock_clause = " FOR UPDATE" if lock else ""
        cursor.execute(
            f"""
                SELECT dataset_source.source_code,
                       dataset_source.allows_full_replace,
                       dataset_source.allows_scope_replace,
                       dataset_source.allows_upsert
                FROM `{self.settings.control_database}`.`import_dataset_source`
                    AS dataset_source
                INNER JOIN `{self.settings.control_database}`.`import_source` AS source
                    ON source.source_code = dataset_source.source_code
                WHERE dataset_source.dataset_code = %s
                  AND dataset_source.is_active = 1
                  AND source.is_active = 1{lock_clause}
            """,
            (batch.dataset_code,),
        )
        active_sources = list(cursor.fetchall())
        if len(active_sources) != 1 or str(active_sources[0]["source_code"]) != batch.source_code:
            raise RuntimeError("SEARCH Gold exige exactamente una fuente activa y autorizada.")

        permission_column = self._search_permission_column(batch)
        if int(active_sources[0][permission_column]) != 1:
            raise RuntimeError("El modo del batch SEARCH dejó de estar autorizado para la fuente.")

    @staticmethod
    def _search_permission_column(batch: BatchRecord) -> str:
        permission_columns = {
            "FULL_REPLACE": "allows_full_replace",
            "SCOPE_REPLACE": "allows_scope_replace",
            "UPSERT": "allows_upsert",
        }
        permission_column = permission_columns.get(batch.refresh_mode)
        if permission_column is None:
            raise RuntimeError("Modo de publicación SEARCH no soportado.")
        if batch.refresh_mode == "UPSERT" and (
            batch.dataset_code != "TELEFONOS"
            or batch.source_code != "BASE_TELEFONOS"
        ):
            raise RuntimeError(
                "UPSERT está autorizado únicamente para TELEFONOS / BASE_TELEFONOS."
            )

        return permission_column

    def _ensure_gold_source_is_compatible(
        self,
        cursor: DictCursor,
        source_code: str,
        gold_table: str,
    ) -> None:
        cursor.execute(
            f"""
                SELECT 1 AS found
                FROM `{self.settings.gold_database}`.`{gold_table}`
                WHERE source_code <> %s
                LIMIT 1
            """,
            (source_code,),
        )
        if cursor.fetchone() is not None:
            raise RuntimeError("Gold SEARCH contiene otra fuente; no existe una política de precedencia.")

    def _search_publication_lock_name(self, batch: BatchRecord) -> str:
        identity = f"{batch.dataset_code}|{batch.source_code}".encode("utf-8")
        digest = hashlib.sha256(identity).hexdigest()[:40]

        return f"kpdm:search:{digest}"

    def _acquire_search_publication_lock(self, cursor: DictCursor, lock_name: str) -> None:
        cursor.execute(
            "SELECT GET_LOCK(%s, %s) AS lock_acquired",
            (lock_name, self.settings.search_publication_lock_timeout),
        )
        result = cursor.fetchone()
        if result is None or int(result["lock_acquired"] or 0) != 1:
            raise RuntimeError("Otra publicación SEARCH del mismo dataset y fuente está activa.")

    @staticmethod
    def _release_search_publication_lock(cursor: DictCursor, lock_name: str) -> None:
        cursor.execute("SELECT RELEASE_LOCK(%s) AS lock_released", (lock_name,))

    @staticmethod
    def _search_scope_integrity_predicates(dataset_code: str) -> tuple[str, str]:
        if dataset_code == "LABORAL_ESSALUD":
            return (
                "scope.documento = (CONVERT(silver.documento USING utf8mb4) "
                "COLLATE utf8mb4_unicode_ci)",
                "silver.documento = (CONVERT(scope.documento USING ascii) "
                "COLLATE ascii_bin)",
            )

        return (
            "scope.documento = silver.documento",
            "silver.documento = scope.documento",
        )

    def _insert_gold_search(
        self,
        cursor: DictCursor,
        batch: BatchRecord,
        published_at: datetime,
        *,
        upsert: bool,
    ) -> None:
        if batch.dataset_code == "TELEFONOS":
            self._insert_gold_phones(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "FAMILIA":
            self._insert_gold_familiares(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "CORREOS":
            self._insert_gold_correos(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "DIRECCIONES":
            self._insert_gold_direcciones(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "VEHICULOS":
            self._insert_gold_vehiculos(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "PROPIEDADES":
            self._insert_gold_propiedades(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "SBS_RESUMEN":
            self._insert_gold_sbs_resumen(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "SBS_DETALLE":
            self._insert_gold_sbs_detalle(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code == "LABORAL_ESSALUD":
            self._insert_gold_essalud(cursor, batch.batch_id, published_at, upsert=upsert)
            return
        if batch.dataset_code != "PERSONAS":
            raise RuntimeError("Dataset SEARCH no soportado para publicación Gold.")
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_person_index`
                (`documento`, `tipo_documento`, `nombre_completo`, `paterno`, `materno`,
                 `nombres`, `fecha_nacimiento`, `sexo`, `estado_civil`, `direccion_origen`,
                 `padre`, `madre`, `source_code`, `batch_id`, `updated_at`)
            SELECT documento, 'DNI', nombre_completo, paterno, materno, nombres,
                   fecha_nacimiento, sexo, estado_civil, direccion_origen,
                   padre, madre, source_code, batch_id, %s
            FROM `{self.settings.silver_database}`.`search_personas`
            WHERE batch_id = %s
        """
        if upsert:
            sql += """
                ON DUPLICATE KEY UPDATE
                    tipo_documento = VALUES(tipo_documento),
                    nombre_completo = VALUES(nombre_completo),
                    paterno = VALUES(paterno),
                    materno = VALUES(materno),
                    nombres = VALUES(nombres),
                    fecha_nacimiento = VALUES(fecha_nacimiento),
                    sexo = VALUES(sexo),
                    estado_civil = VALUES(estado_civil),
                    direccion_origen = VALUES(direccion_origen),
                    padre = VALUES(padre),
                    madre = VALUES(madre),
                    source_code = VALUES(source_code),
                    batch_id = VALUES(batch_id),
                    updated_at = VALUES(updated_at)
            """
        cursor.execute(sql, (published_at, batch.batch_id))

    def _insert_gold_phones(
        self,
        cursor: DictCursor,
        batch_id: int,
        published_at: datetime,
        *,
        upsert: bool,
    ) -> None:
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_telefonos`
                (`documento`, `telefono`, `operador`, `fecha_data`, `source_code`,
                 `batch_id`, `updated_at`)
            SELECT documento, telefono, operador, fecha_data, source_code, batch_id, %s
            FROM `{self.settings.silver_database}`.`search_telefonos`
            WHERE batch_id = %s
        """
        if upsert:
            sql += """
                ON DUPLICATE KEY UPDATE
                    operador = VALUES(operador),
                    fecha_data = VALUES(fecha_data),
                    source_code = VALUES(source_code),
                    batch_id = VALUES(batch_id),
                    updated_at = VALUES(updated_at)
            """
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_familiares(
        self,
        cursor: DictCursor,
        batch_id: int,
        published_at: datetime,
        *,
        upsert: bool,
    ) -> None:
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_familiares`
                (`documento`, `documento_familiar`, `paterno_familiar`, `materno_familiar`,
                 `nombres_familiar`, `nacimiento_familiar`, `tipo_familiar`, `record_hash`,
                 `source_code`, `batch_id`, `source_row_number`, `updated_at`)
            SELECT documento, documento_familiar, paterno_familiar, materno_familiar,
                   nombres_familiar, nacimiento_familiar, tipo_familiar, record_hash,
                   source_code, batch_id, source_row_number, %s
            FROM `{self.settings.silver_database}`.`search_familiares`
            WHERE batch_id = %s
        """
        if upsert:
            sql += """
                ON DUPLICATE KEY UPDATE
                    documento = VALUES(documento),
                    documento_familiar = VALUES(documento_familiar),
                    paterno_familiar = VALUES(paterno_familiar),
                    materno_familiar = VALUES(materno_familiar),
                    nombres_familiar = VALUES(nombres_familiar),
                    nacimiento_familiar = VALUES(nacimiento_familiar),
                    tipo_familiar = VALUES(tipo_familiar),
                    record_hash = VALUES(record_hash),
                    updated_at = VALUES(updated_at)
            """
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_correos(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_correos`
                (`documento`, `correo`, `correo_original`, `source_code`, `batch_id`, `updated_at`)
            SELECT documento, correo, correo_original, source_code, batch_id, %s
            FROM `{self.settings.silver_database}`.`search_correos` WHERE batch_id = %s
        """
        if upsert:
            sql += """ ON DUPLICATE KEY UPDATE correo_original = VALUES(correo_original), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at) """
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_direcciones(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_direcciones`
                (`documento`, `direccion`, `departamento`, `provincia`, `distrito`, `data_procedencia`, `procedencia_anio`, `record_hash`, `source_code`, `batch_id`, `updated_at`)
            SELECT documento, direccion, departamento, provincia, distrito, data_procedencia, procedencia_anio, record_hash, source_code, batch_id, %s
            FROM `{self.settings.silver_database}`.`search_direcciones` WHERE batch_id = %s
        """
        if upsert:
            sql += """ ON DUPLICATE KEY UPDATE direccion = VALUES(direccion), departamento = VALUES(departamento), provincia = VALUES(provincia), distrito = VALUES(distrito), data_procedencia = VALUES(data_procedencia), procedencia_anio = VALUES(procedencia_anio), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at) """
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_vehiculos(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_vehiculos`
                (`documento`, `nombre_completo_fuente`, `clase`, `anio_compra`, `anio_fabricacion`, `marca`, `placa`, `placa_original`, `numero_transferencias`, `record_hash`, `source_code`, `batch_id`, `updated_at`)
            SELECT documento, nombre_completo_fuente, clase, anio_compra, anio_fabricacion, marca, placa, placa_original, numero_transferencias, record_hash, source_code, batch_id, %s
            FROM `{self.settings.silver_database}`.`search_vehiculos` WHERE batch_id = %s
        """
        if upsert:
            sql += """ ON DUPLICATE KEY UPDATE nombre_completo_fuente = VALUES(nombre_completo_fuente), clase = VALUES(clase), anio_compra = VALUES(anio_compra), anio_fabricacion = VALUES(anio_fabricacion), marca = VALUES(marca), placa = VALUES(placa), placa_original = VALUES(placa_original), numero_transferencias = VALUES(numero_transferencias), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at) """
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_propiedades(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_propiedades`
                (`documento`, `partida_registral`, `zona_registral`, `oficina`, `record_hash`, `source_code`, `batch_id`, `updated_at`)
            SELECT documento, partida_registral, zona_registral, oficina, record_hash, source_code, batch_id, %s
            FROM `{self.settings.silver_database}`.`search_propiedades` WHERE batch_id = %s
        """
        if upsert:
            sql += """ ON DUPLICATE KEY UPDATE partida_registral = VALUES(partida_registral), zona_registral = VALUES(zona_registral), oficina = VALUES(oficina), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at) """
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_sbs_resumen(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`search_sbs_resumen` (`documento`, `cod_sbs`, `fecha_reporte_sbs`, `cantidad_empresas`, `calificacion_normal`, `calificacion_cpp`, `calificacion_deficiente`, `calificacion_dudoso`, `calificacion_perdida`, `source_code`, `batch_id`, `updated_at`) SELECT documento, cod_sbs, fecha_reporte_sbs, cantidad_empresas, calificacion_normal, calificacion_cpp, calificacion_deficiente, calificacion_dudoso, calificacion_perdida, source_code, batch_id, %s FROM `{self.settings.silver_database}`.`search_sbs_resumen` WHERE batch_id = %s"""
        if upsert:
            sql += " ON DUPLICATE KEY UPDATE cantidad_empresas = VALUES(cantidad_empresas), calificacion_normal = VALUES(calificacion_normal), calificacion_cpp = VALUES(calificacion_cpp), calificacion_deficiente = VALUES(calificacion_deficiente), calificacion_dudoso = VALUES(calificacion_dudoso), calificacion_perdida = VALUES(calificacion_perdida), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at)"
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_sbs_detalle(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`search_sbs_detalle` (`fecha_reporte_sbs`, `documento`, `cod_sbs`, `entidad`, `tipo_credito`, `condicion`, `monto`, `dias_atraso`, `record_hash`, `source_code`, `batch_id`, `updated_at`) SELECT fecha_reporte_sbs, documento, cod_sbs, entidad, tipo_credito, condicion, monto, dias_atraso, record_hash, source_code, batch_id, %s FROM `{self.settings.silver_database}`.`search_sbs_detalle` WHERE batch_id = %s"""
        if upsert:
            sql += " ON DUPLICATE KEY UPDATE fecha_reporte_sbs = VALUES(fecha_reporte_sbs), cod_sbs = VALUES(cod_sbs), entidad = VALUES(entidad), tipo_credito = VALUES(tipo_credito), condicion = VALUES(condicion), monto = VALUES(monto), dias_atraso = VALUES(dias_atraso), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at)"
        cursor.execute(sql, (published_at, batch_id))

    def _insert_gold_essalud(self, cursor: DictCursor, batch_id: int, published_at: datetime, *, upsert: bool) -> None:
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`search_laboral_essalud` (`documento`, `periodo`, `ruc`, `nombre_empresa`, `sueldo`, `situacion`, `record_hash`, `source_code`, `batch_id`, `updated_at`) SELECT documento, periodo, ruc, nombre_empresa, sueldo, situacion, record_hash, source_code, batch_id, %s FROM `{self.settings.silver_database}`.`search_laboral_essalud` WHERE batch_id = %s"""
        if upsert:
            sql += " ON DUPLICATE KEY UPDATE periodo = VALUES(periodo), ruc = VALUES(ruc), nombre_empresa = VALUES(nombre_empresa), sueldo = VALUES(sueldo), situacion = VALUES(situacion), source_code = VALUES(source_code), batch_id = VALUES(batch_id), updated_at = VALUES(updated_at)"
        cursor.execute(sql, (published_at, batch_id))

    def insert_cartera_chunk(
        self,
        records: Sequence[PortfolioRecord],
        errors: Sequence[RowError],
    ) -> None:
        error_sql = f"""
            INSERT INTO `{self.settings.control_database}`.`import_error`
                (`batch_id`, `numero_fila`, `campo`, `valor`, `error`, `created_at`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        self._begin_transaction()
        try:
            with self.connection.cursor() as cursor:
                if records:
                    record_type = type(records[0])
                    if any(type(record) is not record_type for record in records):
                        raise RuntimeError("Un chunk de cartera no puede mezclar perfiles.")
                    if record_type is BbvaPortfolioRecord:
                        self._insert_portfolio_records(
                            cursor,
                            records,
                            "raw_cartera_bbva",
                            BBVA_SOURCE_COLUMNS,
                        )
                    elif record_type is CajaArequipaPortfolioRecord:
                        narrowed_records = [
                            record
                            for record in records
                            if isinstance(record, CajaArequipaPortfolioRecord)
                        ]
                        correlations = self._insert_portfolio_records(
                            cursor,
                            narrowed_records,
                            "raw_cartera_caja_arequipa",
                            CAJA_AREQUIPA_BRONZE_COLUMNS,
                        )
                        self._insert_caja_arequipa_children(cursor, narrowed_records, correlations)
                    elif record_type is CompartamosPortfolioRecord:
                        narrowed_records = [
                            record
                            for record in records
                            if isinstance(record, CompartamosPortfolioRecord)
                        ]
                        correlations = self._insert_portfolio_records(
                            cursor,
                            narrowed_records,
                            "raw_cartera_compartamos",
                            COMPARTAMOS_BRONZE_COLUMNS,
                        )
                        self._insert_compartamos_children(cursor, narrowed_records, correlations)
                    elif record_type is ConfianzaPortfolioRecord:
                        narrowed_records = [
                            record
                            for record in records
                            if isinstance(record, ConfianzaPortfolioRecord)
                        ]
                        correlations = self._insert_portfolio_records(
                            cursor,
                            narrowed_records,
                            "raw_cartera_confianza",
                            CONFIANZA_BRONZE_COLUMNS,
                        )
                        self._insert_confianza_children(cursor, narrowed_records, correlations)
                    elif record_type is WandooPortfolioRecord:
                        narrowed_records = [
                            record for record in records if isinstance(record, WandooPortfolioRecord)
                        ]
                        correlations = self._insert_portfolio_records(
                            cursor,
                            narrowed_records,
                            "raw_cartera_wandoo",
                            WANDOO_BRONZE_COLUMNS,
                        )
                        self._insert_wandoo_children(cursor, narrowed_records, correlations)
                    else:
                        raise RuntimeError("Tipo de registro de cartera no soportado.")
                if errors:
                    cursor.executemany(error_sql, [error.as_insert_tuple() for error in errors])
            self._commit_transaction()
        except Exception:
            self._rollback_transaction_safely()
            raise

    def _insert_portfolio_records(
        self,
        cursor: DictCursor,
        records: Sequence[PortfolioRecord],
        raw_table: str,
        source_columns: tuple[str, ...],
    ) -> dict[int, tuple[int, int]]:
        quoted_source_columns = ", ".join(f"`{column}`" for column in source_columns)
        raw_placeholders = ", ".join(["%s"] * (len(source_columns) + 5))
        raw_sql = f"""
            INSERT INTO `{self.settings.bronze_database}`.`{raw_table}`
                ({quoted_source_columns}, `batch_id`, `source_row`, `source_file`,
                 `row_hash`, `ingested_at`)
            VALUES ({raw_placeholders})
        """
        operation_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_operaciones`
                (`entidad`, `cosecha`, `documento_cliente`, `tipo_documento`, `cuenta`,
                 `operacion`, `identificador_origen`, `nombre_cliente`, `moneda`,
                 `saldo_capital`, `deuda_total`, `interes`, `mora`, `fecha_castigo`,
                 `fecha_desembolso`, `fecha_vencimiento`, `dias_atraso`, `producto`,
                 `descripcion_producto`, `agencia`, `oficina`, `territorio`, `ubigeo`,
                 `departamento`, `provincia`, `distrito`, `batch_id`, `source_raw_id`,
                 `created_at`)
            VALUES ({", ".join(["%s"] * 29)})
        """
        contact_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_contactos`
                (`operacion_id`, `documento_cliente`, `entidad`, `telefono`, `tipo`,
                 `prefijo`, `extension`, `orden`, `batch_id`, `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 11)})
        """
        address_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_direcciones`
                (`operacion_id`, `documento_cliente`, `entidad`, `tipo_direccion`,
                 `direccion`, `referencia`, `referencia1`, `referencia2`, `ubicacion`,
                 `codigo_postal`, `ubigeo`, `departamento`, `provincia`, `distrito`,
                 `batch_id`, `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 17)})
        """
        cursor.executemany(raw_sql, [record.raw_insert_tuple() for record in records])
        raw_ids = self._raw_ids_by_source_row(cursor, records, raw_table)
        cursor.executemany(
            operation_sql,
            [self._operation_tuple(record, raw_ids[record.source_row]) for record in records],
        )
        operation_ids = self._operation_ids_by_raw_id(cursor, records, raw_ids)
        contacts = []
        addresses = []
        correlations: dict[int, tuple[int, int]] = {}
        for record in records:
            raw_id = raw_ids[record.source_row]
            operation_id = operation_ids[raw_id]
            correlations[record.source_row] = (raw_id, operation_id)
            for contact in record.contacts:
                contacts.append(
                    (
                        operation_id, record.operation.documento_cliente,
                        record.operation.entidad, contact.telefono, contact.tipo,
                        contact.prefijo, contact.extension, contact.orden, record.batch_id,
                        raw_id, record.ingested_at,
                    )
                )
            for address in record.addresses:
                addresses.append(
                    (
                        operation_id, record.operation.documento_cliente,
                        record.operation.entidad, address.tipo_direccion, address.direccion,
                        address.referencia, address.referencia1, address.referencia2,
                        address.ubicacion, address.codigo_postal, address.ubigeo,
                        address.departamento, address.provincia, address.distrito,
                        record.batch_id, raw_id, record.ingested_at,
                    )
                )
        if contacts:
            cursor.executemany(contact_sql, contacts)
        if addresses:
            cursor.executemany(address_sql, addresses)
        return correlations

    def _insert_caja_arequipa_children(
        self,
        cursor: DictCursor,
        records: Sequence[CajaArequipaPortfolioRecord],
        correlations: dict[int, tuple[int, int]],
    ) -> None:
        detail_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_caja_arequipa_detalle`
                (`operacion_id`, `documento_cliente`, `analista`, `tipo_contable`,
                 `fecha_ultimo_pago`, `cuo_pag`, `actividad`, `nro_avales_reportado`,
                 `codigo_sbs`, `monto_desembolso`, `icv`, `seguros`, `penalidad`,
                 `otros_rubros`, `calificacion_sbs`, `provision`,
                 `fecha_ingreso_judicial`, `refinanciado`, `batch_id`, `source_raw_id`,
                 `created_at`)
            VALUES ({", ".join(["%s"] * 21)})
        """
        guarantor_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_avales`
                (`operacion_id`, `documento_cliente`, `entidad`, `orden`, `nombre_aval`,
                 `tipo_documento`, `documento_aval`, `telefono`, `direccion`, `referencia`,
                 `distrito`, `cantidad_reportada`, `batch_id`, `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 15)})
        """
        guarantee_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_garantias`
                (`operacion_id`, `documento_cliente`, `entidad`, `orden`, `tipo_garantia`,
                 `monto`, `batch_id`, `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 9)})
        """
        details = []
        guarantors = []
        guarantees = []
        for record in records:
            raw_id, operation_id = correlations[record.source_row]
            detail = record.detail
            details.append(
                (
                    operation_id, record.operation.documento_cliente, detail.analista,
                    detail.tipo_contable, detail.fecha_ultimo_pago, detail.cuo_pag,
                    detail.actividad, detail.nro_avales_reportado, detail.codigo_sbs,
                    detail.monto_desembolso, detail.icv, detail.seguros, detail.penalidad,
                    detail.otros_rubros, detail.calificacion_sbs, detail.provision,
                    detail.fecha_ingreso_judicial, detail.refinanciado, record.batch_id,
                    raw_id, record.ingested_at,
                )
            )
            if record.guarantor is not None:
                guarantor = record.guarantor
                guarantors.append(
                    (
                        operation_id, record.operation.documento_cliente,
                        record.operation.entidad, guarantor.orden, guarantor.nombre_aval,
                        guarantor.tipo_documento, guarantor.documento_aval,
                        guarantor.telefono, guarantor.direccion, guarantor.referencia,
                        guarantor.distrito, guarantor.cantidad_reportada, record.batch_id,
                        raw_id, record.ingested_at,
                    )
                )
            for guarantee in record.guarantees:
                guarantees.append(
                    (
                        operation_id, record.operation.documento_cliente,
                        record.operation.entidad, guarantee.orden, guarantee.tipo_garantia,
                        guarantee.monto, record.batch_id, raw_id, record.ingested_at,
                    )
                )
        cursor.executemany(detail_sql, details)
        if guarantors:
            cursor.executemany(guarantor_sql, guarantors)
        if guarantees:
            cursor.executemany(guarantee_sql, guarantees)

    def _insert_compartamos_children(
        self,
        cursor: DictCursor,
        records: Sequence[CompartamosPortfolioRecord],
        correlations: dict[int, tuple[int, int]],
    ) -> None:
        detail_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_compartamos_detalle`
                (`operacion_id`, `documento_cliente`, `documento_fuente`, `tipo_cambio`,
                 `saldo_capital_soles`, `lote`, `empresa`, `anio_desembolso`,
                 `fecha_nacimiento`, `batch_id`, `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 12)})
        """
        details = []
        for record in records:
            raw_id, operation_id = correlations[record.source_row]
            detail = record.detail
            details.append(
                (
                    operation_id,
                    record.operation.documento_cliente,
                    detail.documento_fuente,
                    detail.tipo_cambio,
                    detail.saldo_capital_soles,
                    detail.lote,
                    detail.empresa,
                    detail.anio_desembolso,
                    detail.fecha_nacimiento,
                    record.batch_id,
                    raw_id,
                    record.ingested_at,
                )
            )
        cursor.executemany(detail_sql, details)

    def _insert_confianza_children(
        self,
        cursor: DictCursor,
        records: Sequence[ConfianzaPortfolioRecord],
        correlations: dict[int, tuple[int, int]],
    ) -> None:
        detail_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_confianza_detalle`
                (`operacion_id`, `documento_cliente`, `saldo_capital_mo`,
                 `saldo_capital_mn`, `interes_vencido`, `interes_compensatorio`,
                 `interes_moratorio`, `seguros`, `comisiones`, `gastos_judiciales`,
                 `moneda_origen`, `codigo_sucursal_credito`, `nombre_sucursal_credito`,
                 `corredor`, `nombre_modulo_origen`, `estado_operacion`, `batch_id`,
                 `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 19)})
        """
        details = []
        for record in records:
            raw_id, operation_id = correlations[record.source_row]
            detail = record.detail
            details.append(
                (
                    operation_id,
                    record.operation.documento_cliente,
                    detail.saldo_capital_mo,
                    detail.saldo_capital_mn,
                    detail.interes_vencido,
                    detail.interes_compensatorio,
                    detail.interes_moratorio,
                    detail.seguros,
                    detail.comisiones,
                    detail.gastos_judiciales,
                    detail.moneda_origen,
                    detail.codigo_sucursal_credito,
                    detail.nombre_sucursal_credito,
                    detail.corredor,
                    detail.nombre_modulo_origen,
                    detail.estado_operacion,
                    record.batch_id,
                    raw_id,
                    record.ingested_at,
                )
            )
        cursor.executemany(detail_sql, details)

    def _insert_wandoo_children(
        self,
        cursor: DictCursor,
        records: Sequence[WandooPortfolioRecord],
        correlations: dict[int, tuple[int, int]],
    ) -> None:
        detail_sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_wandoo_detalle`
                (`operacion_id`, `documento_cliente`, `recuento_prestamos_pagados`,
                 `nacionalidad`, `saldo_deudor`, `fecha_ultimo_pago`,
                 `total_soles_pagados`, `edad`, `dias_mora`, `producto_crediticio`,
                 `fuente_ingreso`, `estado_cobranza_actual`, `contactabilidad_interna`,
                 `fecha_otorgamiento_credito`, `actividad_laboral`, `batch_id`,
                 `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 18)})
        """
        details = []
        for record in records:
            raw_id, operation_id = correlations[record.source_row]
            detail = record.detail
            details.append(
                (
                    operation_id,
                    record.operation.documento_cliente,
                    detail.recuento_prestamos_pagados,
                    detail.nacionalidad,
                    detail.saldo_deudor,
                    detail.fecha_ultimo_pago,
                    detail.total_soles_pagados,
                    detail.edad,
                    detail.dias_mora,
                    detail.producto_crediticio,
                    detail.fuente_ingreso,
                    detail.estado_cobranza_actual,
                    detail.contactabilidad_interna,
                    detail.fecha_otorgamiento_credito,
                    detail.actividad_laboral,
                    record.batch_id,
                    raw_id,
                    record.ingested_at,
                )
            )
        cursor.executemany(detail_sql, details)

    def _raw_ids_by_source_row(
        self,
        cursor: DictCursor,
        records: Sequence[PortfolioRecord],
        raw_table: str,
    ) -> dict[int, int]:
        source_rows = [record.source_row for record in records]
        placeholders = ", ".join(["%s"] * len(source_rows))
        sql = f"""
            SELECT raw_id, source_row
            FROM `{self.settings.bronze_database}`.`{raw_table}`
            WHERE batch_id = %s AND source_row IN ({placeholders})
        """
        cursor.execute(sql, (records[0].batch_id, *source_rows))
        result = {int(row["source_row"]): int(row["raw_id"]) for row in cursor.fetchall()}
        if len(result) != len(records):
            raise RuntimeError("No se pudieron correlacionar todas las filas Bronze del chunk.")
        return result

    def _operation_ids_by_raw_id(
        self,
        cursor: DictCursor,
        records: Sequence[PortfolioRecord],
        raw_ids: dict[int, int],
    ) -> dict[int, int]:
        values = list(raw_ids.values())
        placeholders = ", ".join(["%s"] * len(values))
        sql = f"""
            SELECT id, source_raw_id
            FROM `{self.settings.silver_database}`.`cartera_operaciones`
            WHERE batch_id = %s AND source_raw_id IN ({placeholders})
        """
        cursor.execute(sql, (records[0].batch_id, *values))
        result = {int(row["source_raw_id"]): int(row["id"]) for row in cursor.fetchall()}
        if len(result) != len(records):
            raise RuntimeError("No se pudieron correlacionar todas las operaciones Silver del chunk.")
        return result

    @staticmethod
    def _operation_tuple(record: PortfolioRecord, raw_id: int) -> tuple[object, ...]:
        operation = record.operation
        return (
            operation.entidad,
            operation.cosecha,
            operation.documento_cliente,
            operation.tipo_documento,
            operation.cuenta,
            operation.operacion,
            operation.identificador_origen,
            operation.nombre_cliente,
            operation.moneda,
            operation.saldo_capital,
            operation.deuda_total,
            operation.interes,
            operation.mora,
            operation.fecha_castigo,
            operation.fecha_desembolso,
            operation.fecha_vencimiento,
            operation.dias_atraso,
            operation.producto,
            operation.descripcion_producto,
            operation.agencia,
            operation.oficina,
            operation.territorio,
            operation.ubigeo,
            operation.departamento,
            operation.provincia,
            operation.distrito,
            record.batch_id,
            raw_id,
            record.ingested_at,
        )

    def finish_batch(
        self,
        batch_id: int,
        status: str,
        finished_at: datetime,
        stats: ProcessingStats,
    ) -> None:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = %s, fecha_fin = %s, filas_archivo = %s,
                filas_insertadas = %s, filas_duplicadas = %s,
                filas_error = %s, mensaje_error = NULL
            WHERE batch_id = %s AND estado = 'PROCESANDO'
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    status,
                    finished_at,
                    stats.file_rows,
                    stats.inserted_rows,
                    stats.duplicate_rows,
                    stats.error_rows,
                    batch_id,
                ),
            )

    def fail_batch(
        self,
        batch_id: int,
        finished_at: datetime,
        message: str,
        stats: ProcessingStats,
    ) -> None:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = 'ERROR', fecha_fin = %s, filas_archivo = %s,
                filas_insertadas = %s, filas_duplicadas = %s,
                filas_error = %s, mensaje_error = %s
            WHERE batch_id = %s AND estado IN ('PENDIENTE', 'PROCESANDO')
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    finished_at,
                    stats.file_rows,
                    stats.inserted_rows,
                    stats.duplicate_rows,
                    stats.error_rows,
                    message[:2000],
                    batch_id,
                ),
            )

    def _begin_transaction(self) -> None:
        self.connection_phase = "transaction_begin"
        self.connection.begin()
        self._transaction_active = True

    @contextmanager
    def _measure(
        self,
        metrics: SearchMetrics | None,
        phase: str,
        *,
        rows_processed: int = 0,
        logical_statement_count: int = 0,
        executemany_calls: int = 0,
    ):
        if metrics is None:
            yield
            return

        previous_metrics = getattr(self, "_active_metrics", None)
        previous_phase = getattr(self, "_active_metric_phase", None)
        self._active_metrics = metrics
        self._active_metric_phase = phase
        try:
            with metrics.measure(
                phase,
                rows_processed=rows_processed,
                logical_statement_count=logical_statement_count,
                executemany_calls=executemany_calls,
            ) as measurement:
                yield measurement
        finally:
            self._active_metrics = previous_metrics
            self._active_metric_phase = previous_phase

    def _record_physical_statement(self) -> None:
        metrics = getattr(self, "_active_metrics", None)
        phase = getattr(self, "_active_metric_phase", None)
        if metrics is not None and phase is not None:
            metrics.record_physical_statement(phase)

    def _commit_transaction(self) -> None:
        self.connection_phase = "commit"
        self.connection.commit()
        self._transaction_active = False

    def _rollback_transaction_safely(self) -> None:
        if not getattr(self, "_transaction_active", False):
            return

        self.connection_phase = "rollback"
        try:
            self.connection.rollback()
        except Exception as exception:
            self.last_cleanup_error_type = type(exception).__name__
        finally:
            self._transaction_active = False

    def close(self) -> bool:
        self._rollback_transaction_safely()
        self.connection_phase = "close"
        try:
            self.connection.close()
        except Exception as exception:
            self.last_cleanup_error_type = type(exception).__name__

            return False

        return True

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from .config import Settings
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
    SearchPersonRecord,
    SearchPhoneRecord,
    SearchEmailRecord,
    SearchAddressRecord,
    SearchVehicleRecord,
    SearchPropertyRecord,
    SearchRawRecord,
    WandooPortfolioRecord,
)


class MySqlDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection: Connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_username,
            password=settings.db_password,
            database=settings.control_database,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=DictCursor,
            connect_timeout=15,
            read_timeout=120,
            write_timeout=120,
        )
        with self.connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")

    def get_batch(self, batch_id: int) -> BatchRecord | None:
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

        self.connection.begin()
        try:
            with self.connection.cursor() as cursor:
                if payments:
                    cursor.executemany(payment_sql, [payment.as_insert_tuple() for payment in payments])
                if errors:
                    cursor.executemany(error_sql, [error.as_insert_tuple() for error in errors])
            self.connection.commit()
        except Exception:
            self.connection.rollback()
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
        elif batch.dataset_code in {"CORREOS", "DIRECCIONES", "VEHICULOS", "PROPIEDADES"}:
            tables = {
                "CORREOS": "search_correos",
                "DIRECCIONES": "search_direcciones",
                "VEHICULOS": "search_vehiculos",
                "PROPIEDADES": "search_propiedades",
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
            if batch.dataset_code in {"CORREOS", "DIRECCIONES", "VEHICULOS", "PROPIEDADES"}:
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
        self.connection.begin()
        inserted_scope_documents = 0
        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(raw_sql, [record.as_insert_tuple() for record in raw_records])
                row_numbers = [record.source_row for record in raw_records]
                placeholders = ", ".join(["%s"] * len(row_numbers))
                cursor.execute(
                    f"""
                        SELECT raw_id, source_row
                        FROM `{self.settings.bronze_database}`.`search_raw_row`
                        WHERE batch_id = %s AND source_row IN ({placeholders})
                    """,
                    (raw_records[0].batch_id, *row_numbers),
                )
                raw_ids = {int(row["source_row"]): int(row["raw_id"]) for row in cursor.fetchall()}
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
                    elif record_type is SearchEmailRecord:
                        silver_sql = email_sql
                    elif record_type is SearchAddressRecord:
                        silver_sql = address_sql
                    elif record_type is SearchVehicleRecord:
                        silver_sql = vehicle_sql
                    elif record_type is SearchPropertyRecord:
                        silver_sql = property_sql
                    else:
                        raise RuntimeError("Tipo de registro SEARCH no soportado.")
                    cursor.executemany(
                        silver_sql,
                        [record.as_insert_tuple(raw_ids[record.source_row]) for record in records],
                    )
                    documents = list(dict.fromkeys(scope_documents))
                    if not documents:
                        documents = list(dict.fromkeys(record.documento for record in records))
                    if documents:
                        placeholders = ", ".join(["%s"] * len(documents))
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
                    cursor.execute(
                        f"SELECT documento FROM `{self.settings.control_database}`.`import_scope_document` WHERE batch_id = %s AND documento IN ({placeholders})",
                        (raw_records[0].batch_id, *documents),
                    )
                    existing_documents = {str(row["documento"]) for row in cursor.fetchall()}
                    new_documents = [document for document in documents if document not in existing_documents]
                    if new_documents:
                        cursor.executemany(scope_sql, [(raw_records[0].batch_id, document, raw_records[0].ingested_at) for document in new_documents])
                        inserted_scope_documents = len(new_documents)
                if errors:
                    cursor.executemany(error_sql, [error.as_insert_tuple() for error in errors])
            self.connection.commit()
            return inserted_scope_documents
        except Exception:
            self.connection.rollback()
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

    def publish_search(
        self,
        batch: BatchRecord,
        published_at: datetime,
        stats: ProcessingStats,
    ) -> None:
        if batch.source_code is None:
            raise RuntimeError("El publicador SEARCH recibió un batch incompatible.")
        tables = {
            "PERSONAS": ("search_personas", "person_id", "search_person_index"),
            "TELEFONOS": ("search_telefonos", "phone_id", "search_telefonos"),
            "CORREOS": ("search_correos", "email_id", "search_correos"),
            "DIRECCIONES": ("search_direcciones", "address_id", "search_direcciones"),
            "VEHICULOS": ("search_vehiculos", "vehicle_id", "search_vehiculos"),
            "PROPIEDADES": ("search_propiedades", "property_id", "search_propiedades"),
        }
        if batch.dataset_code not in tables:
            raise RuntimeError("El publicador SEARCH recibió un dataset no soportado.")
        silver_table, silver_id, gold_table = tables[batch.dataset_code]
        self.connection.begin()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    f"""
                        SELECT estado, filas_archivo, rows_valid, rows_invalid, scope_count
                        FROM `{self.settings.control_database}`.`import_batch`
                        WHERE batch_id = %s FOR UPDATE
                    """,
                    (batch.batch_id,),
                )
                locked_batch = cursor.fetchone()
                if locked_batch is None or locked_batch["estado"] != "PROCESANDO":
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
                    raise RuntimeError("Los contadores persistidos del batch SEARCH no coinciden.")
                cursor.execute(
                    f"""
                        SELECT dataset_source.source_code,
                               dataset_source.allows_full_replace,
                               dataset_source.allows_scope_replace
                        FROM `{self.settings.control_database}`.`import_dataset_source`
                            AS dataset_source
                        INNER JOIN `{self.settings.control_database}`.`import_source` AS source
                            ON source.source_code = dataset_source.source_code
                        WHERE dataset_source.dataset_code = %s
                          AND dataset_source.is_active = 1
                          AND source.is_active = 1
                        FOR UPDATE
                    """,
                    (batch.dataset_code,),
                )
                active_sources = list(cursor.fetchall())
                if (
                    len(active_sources) != 1
                    or str(active_sources[0]["source_code"]) != batch.source_code
                ):
                    raise RuntimeError(
                        "SEARCH Gold exige exactamente una fuente activa y autorizada."
                    )
                permission_column = (
                    "allows_full_replace"
                    if batch.refresh_mode == "FULL_REPLACE"
                    else "allows_scope_replace"
                )
                if int(active_sources[0][permission_column]) != 1:
                    raise RuntimeError(
                        "El modo del batch SEARCH dejó de estar autorizado para la fuente."
                    )
                cursor.execute(
                    f"""
                        SELECT DISTINCT source_code
                        FROM `{self.settings.gold_database}`.`{gold_table}`
                        WHERE source_code <> %s
                        LIMIT 1
                    """,
                    (batch.source_code,),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError(
                        "Gold SEARCH contiene otra fuente; no existe una política de precedencia."
                    )
                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM `{self.settings.silver_database}`.`{silver_table}` WHERE batch_id = %s",
                    (batch.batch_id,),
                )
                silver_count = int(cursor.fetchone()["total"])
                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM `{self.settings.bronze_database}`.`search_raw_row` WHERE batch_id = %s AND dataset_code = %s",
                    (batch.batch_id, batch.dataset_code),
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
                    raise RuntimeError("Silver, scope y contadores del batch SEARCH no coinciden.")
                cursor.execute(
                    f"""
                        SELECT COUNT(*) AS total
                        FROM `{self.settings.silver_database}`.`{silver_table}` AS silver
                        LEFT JOIN `{self.settings.control_database}`.`import_scope_document` AS scope
                          ON scope.batch_id = silver.batch_id AND scope.documento = silver.documento
                        WHERE silver.batch_id = %s AND scope.id IS NULL
                    """,
                    (batch.batch_id,),
                )
                silver_without_scope = int(cursor.fetchone()["total"])
                cursor.execute(
                    f"""
                        SELECT COUNT(*) AS total
                        FROM `{self.settings.control_database}`.`import_scope_document` AS scope
                        LEFT JOIN `{self.settings.silver_database}`.`{silver_table}` AS silver
                          ON silver.batch_id = scope.batch_id AND silver.documento = scope.documento
                        WHERE scope.batch_id = %s AND silver.{silver_id} IS NULL
                    """,
                    (batch.batch_id,),
                )
                scope_without_silver = int(cursor.fetchone()["total"])
                allows_scope_without_silver = batch.dataset_code == "DIRECCIONES"
                if silver_without_scope or (scope_without_silver and not allows_scope_without_silver):
                    raise RuntimeError("El scope oficial no corresponde exactamente a Silver SEARCH.")

                if batch.refresh_mode == "SCOPE_REPLACE":
                    cursor.execute(
                        f"""
                            DELETE gold
                            FROM `{self.settings.gold_database}`.`{gold_table}` AS gold
                            INNER JOIN `{self.settings.control_database}`.`import_scope_document` AS scope
                                ON scope.documento = gold.documento
                            WHERE scope.batch_id = %s
                        """,
                        (batch.batch_id,),
                    )
                    self._insert_gold_search(cursor, batch, published_at, upsert=False)
                elif batch.refresh_mode == "FULL_REPLACE":
                    self._insert_gold_search(cursor, batch, published_at, upsert=True)
                    cursor.execute(
                        f"DELETE FROM `{self.settings.gold_database}`.`{gold_table}` WHERE batch_id <> %s",
                        (batch.batch_id,),
                    )
                else:
                    raise RuntimeError("Modo de publicación SEARCH no soportado.")

                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM `{self.settings.gold_database}`.`{gold_table}` WHERE batch_id = %s",
                    (batch.batch_id,),
                )
                published_count = int(cursor.fetchone()["total"])
                if published_count != silver_count:
                    raise RuntimeError("La cantidad publicada en Gold no coincide con Silver.")
                cursor.execute(
                    f"""
                        UPDATE `{self.settings.control_database}`.`import_batch`
                        SET estado = 'COMPLETADO', fecha_fin = %s, validated_at = %s,
                            published_at = %s, filas_archivo = %s, filas_insertadas = %s,
                            filas_duplicadas = %s, filas_error = %s, rows_valid = %s,
                            rows_invalid = 0, rows_published = %s, scope_count = %s,
                            mensaje_error = NULL
                        WHERE batch_id = %s AND estado = 'PROCESANDO'
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
                    raise RuntimeError("No se pudo confirmar el estado publicado del batch.")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

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
        if batch.dataset_code != "PERSONAS":
            raise RuntimeError("Dataset SEARCH no soportado para publicación Gold.")
        sql = f"""
            INSERT INTO `{self.settings.gold_database}`.`search_person_index`
                (`documento`, `tipo_documento`, `nombre_completo`, `paterno`, `materno`,
                 `nombres`, `fecha_nacimiento`, `sexo`, `estado_civil`, `direccion_origen`,
                 `source_code`, `batch_id`, `updated_at`)
            SELECT documento, 'DNI', nombre_completo, paterno, materno, nombres,
                   fecha_nacimiento, sexo, estado_civil, direccion_origen,
                   source_code, batch_id, %s
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

        self.connection.begin()
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
            self.connection.commit()
        except Exception:
            self.connection.rollback()
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

    def close(self) -> None:
        self.connection.close()

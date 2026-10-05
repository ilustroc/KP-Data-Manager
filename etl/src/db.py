from __future__ import annotations

from datetime import datetime
from typing import Sequence

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from .config import Settings
from .domain.models import (
    BatchRecord,
    PaymentRecord,
    ProcessingStats,
    RowError,
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
            SELECT batch_id, tipo, estado, archivo, archivo_original,
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
        )

    def claim_batch(self, batch_id: int, started_at: datetime) -> bool:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = 'PROCESANDO', fecha_inicio = %s, fecha_fin = NULL,
                filas_archivo = 0, filas_insertadas = 0,
                filas_duplicadas = 0, filas_error = 0, mensaje_error = NULL
            WHERE batch_id = %s AND estado = 'PENDIENTE' AND tipo = 'PAGOS'
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
                filas_duplicadas = %s, filas_error = %s
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
                    batch_id,
                ),
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

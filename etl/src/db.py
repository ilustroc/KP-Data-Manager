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
            SELECT batch_id, tipo, entidad, perfil_version, estado, archivo,
                   archivo_original, archivo_ruta, archivo_extension, archivo_sha256
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
        )

    def claim_batch(self, batch_id: int, started_at: datetime) -> bool:
        sql = f"""
            UPDATE `{self.settings.control_database}`.`import_batch`
            SET estado = 'PROCESANDO', fecha_inicio = %s, fecha_fin = NULL,
                filas_archivo = 0, filas_insertadas = 0,
                filas_duplicadas = 0, filas_error = 0, mensaje_error = NULL
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

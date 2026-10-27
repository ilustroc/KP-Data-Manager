"""Manual, draft-only monthly-assignment generator.

This module deliberately has no publication command.  It reads selected Silver
operations, runs the existing ``MonthlyAssignmentConsolidator``, and can persist
only a validated DRAFT generation when the caller supplies an explicit command
confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from typing import Sequence

from .config import Settings
from .db import MySqlDatabase
from .domain.monthly_assignment import AssignmentAnomaly
from .domain.monthly_assignment import AssignmentConsolidationResult
from .domain.monthly_assignment import AssignmentOperation
from .domain.monthly_assignment import CurrencyPolicy
from .domain.monthly_assignment import ExchangeRate
from .domain.monthly_assignment import HarvestAlias
from .domain.monthly_assignment import HarvestCatalogEntry
from .domain.monthly_assignment import MonthlyAssignmentConsolidator
from .domain.monthly_assignment import PersonasDemographics


WANDOO_REFERENCE = {
    "operations": 13044,
    "clients": 13042,
    "capital": Decimal("6615373.31"),
    "debt_total": Decimal("6615373.31"),
    "components": Decimal("0.00"),
}
BLOCKING_ANOMALIES = frozenset(
    {
        "ambiguous_portfolio_batches",
        "harvest_entity_mismatch",
        "harvest_without_entity",
        "missing_business_key",
        "missing_exchange_rate",
        "unresolved_currency",
        "unknown_harvest",
    }
)
WANDOO_IDENTIFIER_PATTERN = re.compile(r"WAN1:[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class AssignmentGenerationRequest:
    periodo: str
    fecha_corte: date
    entidad: str
    cosecha: str
    batch_id: int
    batch_personas_id: int
    generator_version: str = "monthly-assignment-v1"
    exchange_rate_class: str = "SBS_VENTA"

    @property
    def confirmation_token(self) -> str:
        return f"{self.periodo}:{self.entidad}:{self.cosecha}:{self.batch_id}"


@dataclass(frozen=True, slots=True)
class BatchMetadata:
    batch_id: int
    tipo: str | None
    entidad: str | None
    dataset_code: str | None
    source_code: str | None
    refresh_mode: str | None
    estado: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class AssignmentGenerationInput:
    portfolio_batch: BatchMetadata
    personas_batch: BatchMetadata
    operations: tuple[AssignmentOperation, ...]
    demographics_by_document: dict[str, PersonasDemographics]
    harvests: dict[str, HarvestCatalogEntry]
    zones_by_department: dict[str, str]
    aliases: tuple[HarvestAlias, ...]
    currency_policies: tuple[CurrencyPolicy, ...]
    exchange_rates: tuple[ExchangeRate, ...]


@dataclass(frozen=True, slots=True)
class DraftValidation:
    blocking_reasons: tuple[str, ...]
    anomaly_counts: dict[str, int]

    @property
    def is_valid(self) -> bool:
        return not self.blocking_reasons


@dataclass(frozen=True, slots=True)
class AssignmentGenerationSummary:
    mode: str
    periodo: str
    entidad: str
    cosecha: str
    batch_id: int
    batch_personas_id: int
    rows: int
    operations: int
    flg_clientes: int
    flg_cuentas: int
    anomaly_counts: dict[str, int]
    blocking_reasons: tuple[str, ...]
    generation_id: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "periodo": self.periodo,
            "entidad": self.entidad,
            "cosecha": self.cosecha,
            "batch_id": self.batch_id,
            "batch_personas_id": self.batch_personas_id,
            "rows": self.rows,
            "operations": self.operations,
            "flg_clientes": self.flg_clientes,
            "flg_cuentas": self.flg_cuentas,
            "anomaly_counts": self.anomaly_counts,
            "blocking_reasons": list(self.blocking_reasons),
            "generation_id": self.generation_id,
        }


class AssignmentGenerationRepository(Protocol):
    def load_input(self, request: AssignmentGenerationRequest) -> AssignmentGenerationInput: ...

    def persist_draft(
        self,
        request: AssignmentGenerationRequest,
        generation_input: AssignmentGenerationInput,
        result: AssignmentConsolidationResult,
    ) -> int: ...


class MonthlyAssignmentDraftGenerator:
    """Orchestrates existing consolidation rules and validated DRAFT persistence."""

    def __init__(self, repository: AssignmentGenerationRepository) -> None:
        self.repository = repository
        self.consolidator = MonthlyAssignmentConsolidator()

    def generate(
        self,
        request: AssignmentGenerationRequest,
        *,
        write_draft: bool = False,
    ) -> AssignmentGenerationSummary:
        generation_input = self.repository.load_input(request)
        _validate_batches(request, generation_input)
        result = self.consolidator.consolidate(
            periodo=request.periodo,
            fecha_corte=request.fecha_corte,
            operations=generation_input.operations,
            harvests=generation_input.harvests,
            zones_by_department=generation_input.zones_by_department,
            demographics_by_document=generation_input.demographics_by_document,
            batch_personas_id=request.batch_personas_id,
            exchange_rates=generation_input.exchange_rates,
            currency_policies=generation_input.currency_policies,
            harvest_aliases=generation_input.aliases,
            exchange_rate_class=request.exchange_rate_class,
        )
        validation = _validate_result(request, result)
        summary = _summary("DRY_RUN", request, result, validation, None)
        if not write_draft:
            return summary
        if not validation.is_valid:
            raise ValueError("La conciliación no es apta para crear una generación DRAFT.")
        generation_id = self.repository.persist_draft(request, generation_input, result)
        return _summary("DRAFT", request, result, validation, generation_id)


class MySqlMonthlyAssignmentRepository:
    """Read Silver/control and persist only a transactionally validated DRAFT."""

    def __init__(self, database: MySqlDatabase) -> None:
        self.database = database
        self.settings = database.settings

    def load_input(self, request: AssignmentGenerationRequest) -> AssignmentGenerationInput:
        portfolio_batch = self._batch(request.batch_id)
        personas_batch = self._batch(request.batch_personas_id)
        harvests = self._harvests()
        return AssignmentGenerationInput(
            portfolio_batch=portfolio_batch,
            personas_batch=personas_batch,
            operations=self._operations_with_demographics(request),
            demographics_by_document=self._demographics_within_scope(request),
            harvests=harvests,
            zones_by_department=self._zones(),
            aliases=self._aliases(),
            currency_policies=self._currency_policies(),
            exchange_rates=self._exchange_rates(request),
        )

    def persist_draft(
        self,
        request: AssignmentGenerationRequest,
        generation_input: AssignmentGenerationInput,
        result: AssignmentConsolidationResult,
    ) -> int:
        lock_name = _lock_name(request)
        self._acquire_lock(lock_name)
        try:
            with self.database.transaction():
                with self.database.connection.cursor() as cursor:
                    self._validate_foundation(cursor)
                    locked_portfolio = self._batch(request.batch_id, cursor=cursor, lock=True)
                    locked_personas = self._batch(request.batch_personas_id, cursor=cursor, lock=True)
                    _validate_batches(
                        request,
                        AssignmentGenerationInput(
                            locked_portfolio, locked_personas, (), {}, {}, {}, (), (), ()
                        ),
                    )
                    self._validate_locked_catalogs(cursor, request)
                    self._ensure_open_period(cursor, request, locked_personas)
                    self._ensure_selected_batch(cursor, request)
                    self._ensure_no_scope_draft(cursor, request)
                    self._verify_source_count(cursor, request, len(result.operation_traces))
                    generation_id = self._insert_generation(cursor, request, result)
                    client_ids = self._insert_clients(cursor, generation_id, result)
                    self._insert_operation_traces(cursor, client_ids, result)
                    self._insert_reconciliation(cursor, generation_id, result)
                    self._insert_anomalies(cursor, generation_id, result.anomalies)
            return generation_id
        finally:
            self._release_lock(lock_name)

    def _batch(
        self,
        batch_id: int,
        *,
        cursor=None,
        lock: bool = False,
    ) -> BatchMetadata:
        sql = f"""
            SELECT batch_id, tipo, entidad, dataset_code, source_code, refresh_mode,
                   estado, published_at
            FROM `{self.settings.control_database}`.`import_batch`
            WHERE batch_id = %s{' FOR UPDATE' if lock else ''}
        """
        if cursor is None:
            with self.database.connection.cursor() as owned_cursor:
                owned_cursor.execute(sql, (batch_id,))
                row = owned_cursor.fetchone()
        else:
            cursor.execute(sql, (batch_id,))
            row = cursor.fetchone()
        if row is None:
            raise ValueError(f"No existe el batch #{batch_id}.")
        return BatchMetadata(
            int(row["batch_id"]), _text(row["tipo"]), _text(row["entidad"]),
            _text(row["dataset_code"]), _text(row["source_code"]),
            _text(row["refresh_mode"]), _text(row["estado"]), row["published_at"],
        )

    def _harvests(self) -> dict[str, HarvestCatalogEntry]:
        sql = f"SELECT cosecha, entidad, fecha_compra, origen FROM `{self.settings.control_database}`.`cartera_cosechas`"
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql)
            return {
                str(row["cosecha"]): HarvestCatalogEntry(str(row["cosecha"]), _text(row["entidad"]), row["fecha_compra"], str(row["origen"]))
                for row in cursor.fetchall()
            }

    def _zones(self) -> dict[str, str]:
        sql = f"SELECT departamento, zona FROM `{self.settings.control_database}`.`zonas_departamento`"
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql)
            return {str(row["departamento"]): str(row["zona"]) for row in cursor.fetchall()}

    def _aliases(self) -> tuple[HarvestAlias, ...]:
        sql = f"""SELECT entidad, cosecha_origen, cosecha_canonica, evidence
                   FROM `{self.settings.control_database}`.`asignacion_cosecha_aliases`
                   WHERE is_active = 1"""
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql)
            return tuple(HarvestAlias(str(row["entidad"]), str(row["cosecha_origen"]), str(row["cosecha_canonica"]), str(row["evidence"])) for row in cursor.fetchall())

    def _currency_policies(self) -> tuple[CurrencyPolicy, ...]:
        sql = f"""SELECT entidad, cosecha_scope, moneda_confirmada, evidence
                   FROM `{self.settings.control_database}`.`asignacion_politicas_moneda`
                   WHERE is_active = 1"""
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql)
            return tuple(CurrencyPolicy(str(row["entidad"]), str(row["moneda_confirmada"]), None if row["cosecha_scope"] == "*" else str(row["cosecha_scope"]), str(row["evidence"])) for row in cursor.fetchall())

    def _exchange_rates(self, request: AssignmentGenerationRequest) -> tuple[ExchangeRate, ...]:
        sql = f"""SELECT fecha_tipo_cambio, moneda_origen, moneda_destino, tipo_cambio,
                          tipo_cambio_clase, fuente
                   FROM `{self.settings.control_database}`.`tipos_cambio`
                   WHERE moneda_destino = 'PEN' AND tipo_cambio_clase = %s
                     AND fecha_tipo_cambio <= %s"""
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql, (request.exchange_rate_class, request.fecha_corte))
            return tuple(ExchangeRate(row["fecha_tipo_cambio"], str(row["moneda_origen"]), str(row["moneda_destino"]), Decimal(str(row["tipo_cambio"])), str(row["tipo_cambio_clase"]), str(row["fuente"])) for row in cursor.fetchall())

    def _operations_with_demographics(self, request: AssignmentGenerationRequest) -> tuple[AssignmentOperation, ...]:
        sql = f"""
            SELECT operation_row.id, operation_row.batch_id, operation_row.source_raw_id,
                   operation_row.entidad, operation_row.cosecha,
                   operation_row.documento_cliente, operation_row.nombre_cliente,
                   operation_row.departamento, operation_row.moneda,
                   operation_row.saldo_capital, operation_row.deuda_total,
                   operation_row.fecha_castigo, operation_row.interes, operation_row.mora,
                   operation_row.identificador_origen
            FROM `{self.settings.silver_database}`.`cartera_operaciones` AS operation_row
            LEFT JOIN `{self.settings.control_database}`.`asignacion_cosecha_aliases` AS alias_row
              ON alias_row.entidad = operation_row.entidad
             AND alias_row.cosecha_origen = operation_row.cosecha
             AND alias_row.is_active = 1
            WHERE operation_row.entidad = %s
              AND operation_row.batch_id = %s
              AND COALESCE(alias_row.cosecha_canonica, operation_row.cosecha) = %s
            ORDER BY operation_row.id
        """
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql, (request.entidad, request.batch_id, request.cosecha))
            rows = cursor.fetchall()
        return tuple(_operation_from_row(row) for row in rows)

    def _demographics_within_scope(self, request: AssignmentGenerationRequest) -> dict[str, PersonasDemographics]:
        sql = f"""
            SELECT DISTINCT operation_row.documento_cliente, person.fecha_nacimiento,
                   person.sexo, person.estado_civil
            FROM `{self.settings.silver_database}`.`cartera_operaciones` AS operation_row
            LEFT JOIN `{self.settings.control_database}`.`asignacion_cosecha_aliases` AS alias_row
              ON alias_row.entidad = operation_row.entidad
             AND alias_row.cosecha_origen = operation_row.cosecha
             AND alias_row.is_active = 1
            LEFT JOIN `{self.settings.silver_database}`.`search_personas` AS person
              ON person.batch_id = %s
             AND person.documento = operation_row.documento_cliente
            WHERE operation_row.entidad = %s
              AND operation_row.batch_id = %s
              AND COALESCE(alias_row.cosecha_canonica, operation_row.cosecha) = %s
        """
        with self.database.connection.cursor() as cursor:
            cursor.execute(sql, (request.batch_personas_id, request.entidad, request.batch_id, request.cosecha))
            return {
                str(row["documento_cliente"]): PersonasDemographics(row["fecha_nacimiento"], _text(row["sexo"]), _text(row["estado_civil"]))
                for row in cursor.fetchall()
                if row["fecha_nacimiento"] is not None or row["sexo"] is not None or row["estado_civil"] is not None
            }

    def _validate_locked_catalogs(self, cursor, request: AssignmentGenerationRequest) -> None:
        cursor.execute(f"SELECT entidad FROM `{self.settings.control_database}`.`cartera_cosechas` WHERE cosecha = %s FOR UPDATE", (request.cosecha,))
        row = cursor.fetchone()
        if row is None or row["entidad"] != request.entidad:
            raise ValueError("La cosecha no pertenece a la entidad del alcance solicitado.")
        if request.entidad == "WANDOO" and request.cosecha == "WANDOO_1":
            cursor.execute(f"""SELECT moneda_confirmada FROM `{self.settings.control_database}`.`asignacion_politicas_moneda`
                               WHERE entidad = 'WANDOO' AND cosecha_scope = 'WANDOO_1'
                                 AND is_active = 1 FOR UPDATE""")
            policy = cursor.fetchone()
            if policy is None or policy["moneda_confirmada"] != "PEN":
                raise ValueError("La política activa WANDOO_1 = PEN no está disponible.")

    def _validate_foundation(self, cursor) -> None:
        """Refuse writes when the verified monthly-assignment foundation is incomplete."""
        expected = (
            (self.settings.control_database, "cartera_cosechas"),
            (self.settings.control_database, "zonas_departamento"),
            (self.settings.control_database, "tipos_cambio"),
            (self.settings.control_database, "asignacion_politicas_moneda"),
            (self.settings.control_database, "asignacion_cosecha_aliases"),
            (self.settings.control_database, "asignacion_catalogo_cambios"),
            (self.settings.control_database, "asignacion_periodos"),
            (self.settings.control_database, "asignacion_periodo_cartera_batch"),
            (self.settings.gold_database, "asignacion_mensual_generaciones"),
            (self.settings.gold_database, "asignacion_mensual_clientes"),
            (self.settings.gold_database, "asignacion_mensual_operaciones"),
            (self.settings.gold_database, "asignacion_mensual_conciliacion"),
            (self.settings.gold_database, "asignacion_mensual_anomalias"),
        )
        placeholders = ", ".join(["(%s, %s)"] * len(expected))
        cursor.execute(
            f"""SELECT TABLE_SCHEMA AS source_schema, TABLE_NAME AS source_table
                FROM information_schema.tables
                WHERE (table_schema, table_name) IN ({placeholders})""",
            tuple(value for item in expected for value in item),
        )
        found = {(str(row["source_schema"]), str(row["source_table"])) for row in cursor.fetchall()}
        missing = sorted(set(expected) - found)
        if missing:
            raise ValueError(
                "La fundación de asignación mensual está incompleta: "
                + ", ".join(f"{schema}.{table}" for schema, table in missing)
            )

    def _ensure_open_period(self, cursor, request: AssignmentGenerationRequest, personas: BatchMetadata) -> None:
        cursor.execute(f"SELECT periodo, fecha_corte, estado, active_generation_id, closed_at, batch_personas_id FROM `{self.settings.control_database}`.`asignacion_periodos` WHERE periodo = %s FOR UPDATE", (request.periodo,))
        period = cursor.fetchone()
        if period is None:
            cursor.execute(f"""INSERT INTO `{self.settings.control_database}`.`asignacion_periodos`
                (periodo, fecha_corte, estado, active_generation_id, batch_personas_id,
                 batch_personas_published_at, batch_personas_refresh_mode, tipo_cambio_clase,
                 fecha_generacion, published_at, closed_at, cantidad_clientes,
                 cantidad_operaciones, total_capital, total_deuda,
                 total_componentes_no_capital, generator_version, audit_message,
                 created_at, updated_at)
                VALUES (%s, %s, 'ABIERTO', NULL, %s, %s, %s, %s, NULL, NULL, NULL,
                        NULL, NULL, NULL, NULL, NULL, %s, NULL, UTC_TIMESTAMP(), UTC_TIMESTAMP())""",
                (request.periodo, request.fecha_corte, request.batch_personas_id, personas.published_at,
                 personas.refresh_mode, request.exchange_rate_class, request.generator_version),
            )
            return
        if period["closed_at"] is not None or period["estado"] == "CERRADO":
            raise ValueError("El periodo está cerrado y no admite una generación DRAFT.")
        if period["fecha_corte"] != request.fecha_corte or period["batch_personas_id"] != request.batch_personas_id:
            raise ValueError("El periodo ya existe con fecha de corte o batch PERSONAS diferente.")
        if period["active_generation_id"] is not None:
            raise ValueError("El periodo ya tiene una generación oficial activa; no se crea otro DRAFT en este alcance.")

    def _ensure_selected_batch(self, cursor, request: AssignmentGenerationRequest) -> None:
        cursor.execute(f"SELECT entidad, batch_id FROM `{self.settings.control_database}`.`asignacion_periodo_cartera_batch` WHERE periodo = %s AND cosecha = %s FOR UPDATE", (request.periodo, request.cosecha))
        selected = cursor.fetchone()
        if selected is None:
            cursor.execute(f"""INSERT INTO `{self.settings.control_database}`.`asignacion_periodo_cartera_batch`
                               (periodo, cosecha, entidad, batch_id, selected_at, selected_by, selection_reason)
                               VALUES (%s, %s, %s, %s, UTC_TIMESTAMP(), NULL, 'generación manual DRAFT validada')""",
                           (request.periodo, request.cosecha, request.entidad, request.batch_id))
        elif selected["entidad"] != request.entidad or int(selected["batch_id"]) != request.batch_id:
            raise ValueError("La cosecha ya está seleccionada con otra entidad o batch para este periodo.")

    def _ensure_no_scope_draft(self, cursor, request: AssignmentGenerationRequest) -> None:
        cursor.execute(f"""SELECT generation.generation_id
                           FROM `{self.settings.gold_database}`.`asignacion_mensual_generaciones` AS generation
                           INNER JOIN `{self.settings.gold_database}`.`asignacion_mensual_clientes` AS client
                             ON client.generation_id = generation.generation_id
                           WHERE generation.periodo = %s
                             AND generation.estado = 'DRAFT'
                             AND client.entidad = %s
                             AND client.cosecha = %s
                           LIMIT 1 FOR UPDATE""",
                       (request.periodo, request.entidad, request.cosecha))
        if cursor.fetchone() is not None:
            raise ValueError("Ya existe una generación DRAFT para el mismo periodo y alcance; revisar o revertirla antes de reintentar.")

    def _verify_source_count(self, cursor, request: AssignmentGenerationRequest, expected: int) -> None:
        cursor.execute(f"""SELECT COUNT(*) AS total
                           FROM `{self.settings.silver_database}`.`cartera_operaciones` AS operation_row
                           LEFT JOIN `{self.settings.control_database}`.`asignacion_cosecha_aliases` AS alias_row
                             ON alias_row.entidad = operation_row.entidad
                            AND alias_row.cosecha_origen = operation_row.cosecha
                            AND alias_row.is_active = 1
                           WHERE operation_row.entidad = %s AND operation_row.batch_id = %s
                             AND COALESCE(alias_row.cosecha_canonica, operation_row.cosecha) = %s""",
                       (request.entidad, request.batch_id, request.cosecha))
        if int(cursor.fetchone()["total"]) != expected:
            raise ValueError("Las operaciones fuente cambiaron durante la generación; se revierte el DRAFT.")

    def _insert_generation(self, cursor, request: AssignmentGenerationRequest, result: AssignmentConsolidationResult) -> int:
        cursor.execute(f"""INSERT INTO `{self.settings.gold_database}`.`asignacion_mensual_generaciones`
            (periodo, generator_version, batch_personas_id, fecha_corte, tipo_cambio_clase,
             started_at, finished_at, estado, published_at, superseded_at, failure_message,
             rows_generated, operations_selected, anomaly_count, created_at)
            VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), 'DRAFT', NULL,
                    NULL, NULL, %s, %s, %s, UTC_TIMESTAMP())""",
            (request.periodo, request.generator_version, request.batch_personas_id,
             request.fecha_corte, request.exchange_rate_class, len(result.rows),
             len(result.operation_traces), len(result.anomalies)),
        )
        return int(cursor.lastrowid)

    def _insert_clients(self, cursor, generation_id: int, result: AssignmentConsolidationResult) -> dict[str, int]:
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`asignacion_mensual_clientes`
            (generation_id, cadena, fecha_compra, documento_cliente, titular, flg_cliente,
             flg_cuenta, tipo_monto, anio_cast, dpto, zona, ran_cap, fecha_nacimiento,
             sexo, estado_civil, origen, entidad, cosecha, cons_deuda_k, cons_intereses,
             cons_deuda_total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s)"""
        values = [(generation_id, *row.business_values()) for row in result.rows]
        _executemany_in_chunks(cursor, sql, values, self.settings.insert_batch_size)
        cursor.execute(f"SELECT assignment_client_id, cadena FROM `{self.settings.gold_database}`.`asignacion_mensual_clientes` WHERE generation_id = %s", (generation_id,))
        client_ids = {str(row["cadena"]): int(row["assignment_client_id"]) for row in cursor.fetchall()}
        if len(client_ids) != len(result.rows):
            raise ValueError("No se persistieron exactamente todos los clientes de la generación DRAFT.")
        return client_ids

    def _insert_operation_traces(self, cursor, client_ids: dict[str, int], result: AssignmentConsolidationResult) -> None:
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`asignacion_mensual_operaciones`
            (assignment_client_id, operacion_id, batch_id, source_raw_id, identificador_origen,
             cosecha_origen, moneda_original, moneda_resuelta, capital_original,
             deuda_total_original, tipo_cambio, fecha_tipo_cambio, tipo_cambio_clase,
             fuente_tipo_cambio, capital_convertido_pen, deuda_total_convertida_pen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        values = []
        for trace in result.operation_traces:
            client_id = client_ids.get(trace.cadena)
            if client_id is None:
                raise ValueError("Una traza no tiene cliente Gold asociado.")
            values.append((client_id, trace.operation_id, trace.batch_id, trace.source_raw_id,
                           trace.identificador_origen, trace.cosecha_origen,
                           trace.moneda_original, trace.moneda_resuelta,
                           trace.capital_original, trace.deuda_total_original,
                           trace.tipo_cambio, trace.fecha_tipo_cambio,
                           trace.tipo_cambio_clase, trace.fuente_tipo_cambio,
                           trace.capital_convertido_pen, trace.deuda_total_convertida_pen))
        _executemany_in_chunks(cursor, sql, values, self.settings.insert_batch_size)

    def _insert_reconciliation(self, cursor, generation_id: int, result: AssignmentConsolidationResult) -> None:
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`asignacion_mensual_conciliacion`
            (generation_id, batch_id, entidad, cosecha, moneda_origen, operation_count,
             client_count, capital_original_pen, capital_original_usd, capital_convertido_pen,
             deuda_total_convertida_pen, componentes_no_capital_pen,
             operations_without_currency, operations_without_debt_total,
             operations_without_exchange_rate, assignment_capital_pen,
             assignment_debt_total_pen, difference_capital_pen, difference_debt_total_pen,
             status, warnings, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())"""
        values = [(generation_id, item.batch_id, item.entidad, item.cosecha, item.moneda_origen,
                   item.operation_count, item.client_count, item.capital_original_pen,
                   item.capital_original_usd, item.capital_convertido_pen,
                   item.deuda_total_convertida_pen, item.componentes_no_capital_pen,
                   item.operations_without_currency, item.operations_without_debt_total,
                   item.operations_without_exchange_rate, item.assignment_capital_pen,
                   item.assignment_debt_total_pen, item.difference_capital_pen,
                   item.difference_debt_total_pen, item.status,
                   "; ".join(item.warnings) or None) for item in result.financial_reconciliation]
        _executemany_in_chunks(cursor, sql, values, self.settings.insert_batch_size)

    def _insert_anomalies(self, cursor, generation_id: int, anomalies: Sequence[AssignmentAnomaly]) -> None:
        if not anomalies:
            return
        sql = f"""INSERT INTO `{self.settings.gold_database}`.`asignacion_mensual_anomalias`
                   (generation_id, code, cosecha, documento_cliente, message, created_at)
                   VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP())"""
        values = [(generation_id, item.code, item.cosecha, item.documento_cliente, item.message) for item in anomalies]
        _executemany_in_chunks(cursor, sql, values, self.settings.insert_batch_size)

    def _acquire_lock(self, lock_name: str) -> None:
        with self.database.connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s) AS lock_acquired", (lock_name, self.settings.search_publication_lock_timeout))
            row = cursor.fetchone()
        if row is None or int(row["lock_acquired"] or 0) != 1:
            raise RuntimeError("No se pudo adquirir el bloqueo de generación mensual.")

    def _release_lock(self, lock_name: str) -> None:
        try:
            with self.database.connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s) AS lock_released", (lock_name,))
        except Exception:
            logging.getLogger("kpdm.assignment").exception("monthly_assignment_lock_release_failed")


def _validate_batches(request: AssignmentGenerationRequest, generation_input: AssignmentGenerationInput) -> None:
    portfolio = generation_input.portfolio_batch
    personas = generation_input.personas_batch
    if portfolio.batch_id != request.batch_id or portfolio.tipo != "CARTERA" or portfolio.entidad != request.entidad or portfolio.estado != "COMPLETADO":
        raise ValueError("El batch de cartera no coincide con el alcance o no está COMPLETADO.")
    if (personas.batch_id != request.batch_personas_id or personas.dataset_code != "PERSONAS"
            or personas.source_code != "BASE_PERSONAS" or personas.estado != "COMPLETADO"
            or personas.refresh_mode not in {"FULL_REPLACE", "SCOPE_REPLACE"}
            or personas.published_at is None):
        raise ValueError("El batch PERSONAS no está publicado o no cumple el contrato de enriquecimiento.")


def _validate_result(request: AssignmentGenerationRequest, result: AssignmentConsolidationResult) -> DraftValidation:
    anomaly_counts = dict(sorted(Counter(item.code for item in result.anomalies).items()))
    reasons = [f"anomaly:{code}" for code in anomaly_counts if code in BLOCKING_ANOMALIES]
    if not result.rows or not result.operation_traces:
        reasons.append("empty_generation")
    if sum(row.flg_cliente for row in result.rows) != len(result.rows):
        reasons.append("invalid_flg_cliente")
    if sum(row.flg_cuenta for row in result.rows) != len(result.operation_traces):
        reasons.append("flg_cuenta_mismatch")
    for item in result.financial_reconciliation:
        if item.moneda_origen == "ALL" and (
            item.status != "COMPLETE"
            or item.difference_capital_pen != Decimal("0")
            or item.difference_debt_total_pen != Decimal("0")
        ):
            reasons.append(f"financial_reconciliation:{item.entidad}:{item.cosecha}")
    if request.entidad == "WANDOO" and request.cosecha == "WANDOO_1":
        reasons.extend(_validate_wandoo_result(result))
    return DraftValidation(tuple(sorted(set(reasons))), anomaly_counts)


def _validate_wandoo_result(result: AssignmentConsolidationResult) -> list[str]:
    rows = result.rows
    traces = result.operation_traces
    capital = sum((row.cons_deuda_k or Decimal("0")) for row in rows)
    debt = sum((row.cons_deuda_total or Decimal("0")) for row in rows)
    components = sum((row.cons_intereses or Decimal("0")) for row in rows)
    mismatches = []
    if len(traces) != WANDOO_REFERENCE["operations"]:
        mismatches.append("wandoo_operation_count")
    if len(rows) != WANDOO_REFERENCE["clients"]:
        mismatches.append("wandoo_client_count")
    if (capital, debt, components) != (WANDOO_REFERENCE["capital"], WANDOO_REFERENCE["debt_total"], WANDOO_REFERENCE["components"]):
        mismatches.append("wandoo_financial_reference")
    if any(trace.moneda_resuelta != "PEN" for trace in traces):
        mismatches.append("wandoo_currency_policy")
    if any(
        trace.identificador_origen is None
        or WANDOO_IDENTIFIER_PATTERN.fullmatch(trace.identificador_origen) is None
        for trace in traces
    ):
        mismatches.append("wandoo_identity_reference")
    return mismatches


def _summary(mode: str, request: AssignmentGenerationRequest, result: AssignmentConsolidationResult, validation: DraftValidation, generation_id: int | None) -> AssignmentGenerationSummary:
    return AssignmentGenerationSummary(mode, request.periodo, request.entidad, request.cosecha,
                                       request.batch_id, request.batch_personas_id, len(result.rows),
                                       len(result.operation_traces), sum(row.flg_cliente for row in result.rows),
                                       sum(row.flg_cuenta for row in result.rows), validation.anomaly_counts,
                                       validation.blocking_reasons, generation_id)


def _operation_from_row(row) -> AssignmentOperation:
    return AssignmentOperation(int(row["id"]), int(row["batch_id"]), int(row["source_raw_id"]),
                               str(row["entidad"]), _text(row["cosecha"]), str(row["documento_cliente"]),
                               _text(row["nombre_cliente"]), _text(row["departamento"]), _text(row["moneda"]),
                               _decimal(row["saldo_capital"]), _decimal(row["deuda_total"]), row["fecha_castigo"],
                               _decimal(row["interes"]), _decimal(row["mora"]), _text(row["identificador_origen"]))


def _executemany_in_chunks(cursor, sql: str, values: Sequence[tuple[object, ...]], chunk_size: int) -> None:
    for start in range(0, len(values), chunk_size):
        cursor.executemany(sql, values[start:start + chunk_size])


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _lock_name(request: AssignmentGenerationRequest) -> str:
    scope = f"{request.periodo}|{request.entidad}|{request.cosecha}".encode("utf-8")
    return f"kpdm:assignment:{hashlib.sha256(scope).hexdigest()[:40]}"


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exception:
        raise argparse.ArgumentTypeError("fecha-corte debe tener formato YYYY-MM-DD.") from exception


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exception:
        raise argparse.ArgumentTypeError("El batch debe ser entero.") from exception
    if number < 1:
        raise argparse.ArgumentTypeError("El batch debe ser positivo.")
    return number


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera una asignación mensual manual en modo dry-run o DRAFT.")
    parser.add_argument("--periodo", required=True)
    parser.add_argument("--fecha-corte", required=True, type=_parse_date)
    parser.add_argument("--entidad", required=True)
    parser.add_argument("--cosecha", required=True)
    parser.add_argument("--batch", required=True, type=_positive)
    parser.add_argument("--batch-personas", default=44, type=_positive)
    parser.add_argument("--generator-version", default="monthly-assignment-v1")
    parser.add_argument("--write-draft", action="store_true")
    parser.add_argument("--confirm-write-draft")
    arguments = parser.parse_args(argv)
    request = AssignmentGenerationRequest(arguments.periodo, arguments.fecha_corte,
                                          arguments.entidad, arguments.cosecha,
                                          arguments.batch, arguments.batch_personas,
                                          arguments.generator_version)
    if arguments.write_draft and arguments.confirm_write_draft != request.confirmation_token:
        parser.error(f"--write-draft requiere --confirm-write-draft {request.confirmation_token}")
    if not arguments.write_draft and arguments.confirm_write_draft is not None:
        parser.error("--confirm-write-draft solo se acepta junto con --write-draft")
    database: MySqlDatabase | None = None
    try:
        settings = Settings.from_environment()
        _configure_logging(settings.log_level)
        database = MySqlDatabase(settings)
        summary = MonthlyAssignmentDraftGenerator(MySqlMonthlyAssignmentRepository(database)).generate(
            request, write_draft=arguments.write_draft
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, default=str, sort_keys=True))
        return 0 if not summary.blocking_reasons else 2
    except Exception as exception:
        logging.getLogger("kpdm.assignment").error(json.dumps({"event": "monthly_assignment_failed", "error_type": type(exception).__name__}, ensure_ascii=False))
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(main())

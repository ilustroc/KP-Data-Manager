from dataclasses import replace
from datetime import date
from datetime import datetime
from decimal import Decimal

import pytest

from src.db import MySqlDatabase
from src.domain.monthly_assignment import AssignmentOperation
from src.domain.monthly_assignment import CurrencyPolicy
from src.domain.monthly_assignment import HarvestCatalogEntry
from src.domain.monthly_assignment import MonthlyAssignmentConsolidator
from src.monthly_assignment_generator import AssignmentGenerationInput
from src.monthly_assignment_generator import AssignmentGenerationRequest
from src.monthly_assignment_generator import BatchMetadata
from src.monthly_assignment_generator import MySqlMonthlyAssignmentRepository
from src.monthly_assignment_generator import MonthlyAssignmentDraftGenerator


class RecordingRepository:
    def __init__(self, generation_input: AssignmentGenerationInput) -> None:
        self.generation_input = generation_input
        self.persisted = []

    def load_input(self, request: AssignmentGenerationRequest) -> AssignmentGenerationInput:
        return self.generation_input

    def persist_draft(self, request, generation_input, result) -> int:
        self.persisted.append((request, generation_input, result))
        return 701


def wandoo_request() -> AssignmentGenerationRequest:
    return AssignmentGenerationRequest(
        periodo="202610",
        fecha_corte=date(2026, 10, 26),
        entidad="WANDOO",
        cosecha="WANDOO_1",
        batch_id=29,
        batch_personas_id=44,
    )


def wandoo_input(*, invalid_identity: bool = False) -> AssignmentGenerationInput:
    operations = tuple(
        AssignmentOperation(
            operation_id=operation_id,
            batch_id=29,
            source_raw_id=10_000 + operation_id,
            entidad="WANDOO",
            cosecha="WANDOO_1",
            documento_cliente=(
                "00000001" if operation_id <= 2 else "00000002" if operation_id <= 4
                else f"{operation_id - 2:08d}"
            ),
            titular="CLIENTE DE PRUEBA",
            departamento="LIMA",
            moneda="SIN_MONEDA",
            saldo_capital=Decimal("500.00") if operation_id < 13_044 else Decimal("93873.31"),
            deuda_total=Decimal("500.00") if operation_id < 13_044 else Decimal("93873.31"),
            fecha_castigo=None,
            identificador_origen=(
                None if invalid_identity and operation_id == 1 else f"WAN1:{operation_id:064x}"
            ),
        )
        for operation_id in range(1, 13_045)
    )
    return AssignmentGenerationInput(
        portfolio_batch=BatchMetadata(29, "CARTERA", "WANDOO", None, None, None, "COMPLETADO", None),
        personas_batch=BatchMetadata(
            44,
            "SEARCH",
            None,
            "PERSONAS",
            "BASE_PERSONAS",
            "SCOPE_REPLACE",
            "COMPLETADO",
            datetime(2026, 10, 20, 16, 34, 16),
        ),
        operations=operations,
        demographics_by_document={},
        harvests={
            "WANDOO_1": HarvestCatalogEntry(
                "WANDOO_1", "WANDOO", date(2026, 4, 10), "KP INVEST"
            )
        },
        zones_by_department={"LIMA": "CENTRO"},
        aliases=(),
        currency_policies=(
            CurrencyPolicy(
                "WANDOO",
                "PEN",
                "WANDOO_1",
                "confirmación funcional del negocio del 2026-10-26",
            ),
        ),
        exchange_rates=(),
    )


def test_wandoo_dry_run_validates_the_real_reference_without_persisting() -> None:
    repository = RecordingRepository(wandoo_input())

    summary = MonthlyAssignmentDraftGenerator(repository).generate(wandoo_request())

    assert summary.mode == "DRY_RUN"
    assert summary.generation_id is None
    assert (summary.rows, summary.operations, summary.flg_clientes, summary.flg_cuentas) == (
        13_042,
        13_044,
        13_042,
        13_044,
    )
    assert summary.blocking_reasons == ()
    assert repository.persisted == []


def test_wandoo_write_creates_only_a_draft_after_all_validations_pass() -> None:
    repository = RecordingRepository(wandoo_input())

    summary = MonthlyAssignmentDraftGenerator(repository).generate(wandoo_request(), write_draft=True)

    assert (summary.mode, summary.generation_id, summary.blocking_reasons) == ("DRAFT", 701, ())
    assert len(repository.persisted) == 1
    persisted_result = repository.persisted[0][2]
    assert sum(row.flg_cliente for row in persisted_result.rows) == 13_042
    assert sum(row.flg_cuenta for row in persisted_result.rows) == 13_044
    assert sum(row.cons_deuda_k for row in persisted_result.rows) == Decimal("6615373.31")
    assert sum(row.cons_deuda_total for row in persisted_result.rows) == Decimal("6615373.31")
    assert sum(row.cons_intereses for row in persisted_result.rows) == Decimal("0.00")
    assert all(
        trace.identificador_origen and trace.identificador_origen.startswith("WAN1:")
        for trace in persisted_result.operation_traces
    )


def test_invalid_wandoo_identity_blocks_draft_persistence() -> None:
    repository = RecordingRepository(wandoo_input(invalid_identity=True))

    with pytest.raises(ValueError, match="no es apta"):
        MonthlyAssignmentDraftGenerator(repository).generate(wandoo_request(), write_draft=True)

    assert repository.persisted == []


def test_malformed_wandoo_identity_also_blocks_draft_persistence() -> None:
    generation_input = wandoo_input()
    malformed = replace(generation_input.operations[0], identificador_origen="WAN1:not-a-sha256")
    repository = RecordingRepository(
        replace(generation_input, operations=(malformed, *generation_input.operations[1:]))
    )

    with pytest.raises(ValueError, match="no es apta"):
        MonthlyAssignmentDraftGenerator(repository).generate(wandoo_request(), write_draft=True)

    assert repository.persisted == []


def test_confirmation_token_binds_the_period_scope_and_batch() -> None:
    request = wandoo_request()

    assert request.confirmation_token == "202610:WANDOO:WANDOO_1:29"


class PersistenceCursor:
    def __init__(self, settings, *, source_count: int = 1) -> None:
        self.settings = settings
        self.source_count = source_count
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.executed_many: list[tuple[str, list[tuple[object, ...]]]] = []
        self.last_sql = ""
        self.last_values: tuple[object, ...] = ()
        self.lastrowid = 901

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def execute(self, sql: str, values=()) -> None:
        self.last_sql = sql
        self.last_values = tuple(values)
        self.executed.append((sql, self.last_values))

    def executemany(self, sql: str, values) -> None:
        self.executed_many.append((sql, list(values)))

    def fetchone(self):
        if "GET_LOCK" in self.last_sql or "RELEASE_LOCK" in self.last_sql:
            return {"lock_acquired": 1, "lock_released": 1}
        if "`import_batch`" in self.last_sql:
            batch_id = int(self.last_values[0])
            if batch_id == 14:
                return {
                    "batch_id": 14, "tipo": "CARTERA", "entidad": "CAJA_AREQUIPA",
                    "dataset_code": None, "source_code": None, "refresh_mode": None,
                    "estado": "COMPLETADO", "published_at": None,
                }
            return {
                "batch_id": 44, "tipo": "SEARCH", "entidad": None,
                "dataset_code": "PERSONAS", "source_code": "BASE_PERSONAS",
                "refresh_mode": "SCOPE_REPLACE", "estado": "COMPLETADO",
                "published_at": datetime(2026, 10, 20, 16, 34, 16),
            }
        if "SELECT entidad FROM" in self.last_sql:
            return {"entidad": "CAJA_AREQUIPA"}
        if "FROM `" + self.settings.control_database + "`.`asignacion_periodos`" in self.last_sql:
            return None
        if "FROM `" + self.settings.control_database + "`.`asignacion_periodo_cartera_batch`" in self.last_sql:
            return None
        if "AS generation" in self.last_sql and "estado = 'DRAFT'" in self.last_sql:
            return None
        if "COUNT(*) AS total" in self.last_sql:
            return {"total": self.source_count}
        return None

    def fetchall(self):
        if "information_schema.tables" in self.last_sql:
            return [
                {"table_schema": schema, "table_name": table}
                for schema, table in zip(self.last_values[::2], self.last_values[1::2], strict=True)
            ]
        if "assignment_client_id, cadena" in self.last_sql:
            return [{"assignment_client_id": 3001, "cadena": "CAJAAQP330561135"}]
        return []


class PersistenceConnection:
    def __init__(self, cursor: PersistenceCursor) -> None:
        self.recording_cursor = cursor
        self.began = False
        self.committed = False
        self.rolled_back = False

    def begin(self) -> None:
        self.began = True

    def cursor(self) -> PersistenceCursor:
        return self.recording_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def persisted_caja_result():
    operation = AssignmentOperation(
        operation_id=11,
        batch_id=14,
        source_raw_id=1011,
        entidad="CAJA_AREQUIPA",
        cosecha="CAJAAQP3",
        documento_cliente="30561135",
        titular="CLIENTE DE PRUEBA",
        departamento="AREQUIPA",
        moneda="PEN",
        saldo_capital=Decimal("100.00"),
        deuda_total=Decimal("150.00"),
        fecha_castigo=None,
    )
    return MonthlyAssignmentConsolidator().consolidate(
        periodo="202610",
        fecha_corte=date(2026, 10, 26),
        operations=(operation,),
        harvests={
            "CAJAAQP3": HarvestCatalogEntry(
                "CAJAAQP3", "CAJA_AREQUIPA", date(2020, 12, 22), "FONDO I"
            )
        },
        zones_by_department={"AREQUIPA": "SUR"},
        demographics_by_document={},
        batch_personas_id=44,
    )


def persistence_database(settings, *, source_count: int = 1):
    cursor = PersistenceCursor(settings, source_count=source_count)
    database = MySqlDatabase.__new__(MySqlDatabase)
    database.settings = settings
    database.connection = PersistenceConnection(cursor)
    database._transaction_active = False
    database.connection_phase = "ready"
    database.last_cleanup_error_type = None
    return database, cursor


def caja_request() -> AssignmentGenerationRequest:
    return AssignmentGenerationRequest(
        periodo="202610",
        fecha_corte=date(2026, 10, 26),
        entidad="CAJA_AREQUIPA",
        cosecha="CAJAAQP3",
        batch_id=14,
        batch_personas_id=44,
    )


def caja_input() -> AssignmentGenerationInput:
    return AssignmentGenerationInput(
        portfolio_batch=BatchMetadata(14, "CARTERA", "CAJA_AREQUIPA", None, None, None, "COMPLETADO", None),
        personas_batch=BatchMetadata(
            44, "SEARCH", None, "PERSONAS", "BASE_PERSONAS", "SCOPE_REPLACE",
            "COMPLETADO", datetime(2026, 10, 20, 16, 34, 16),
        ),
        operations=(),
        demographics_by_document={},
        harvests={},
        zones_by_department={},
        aliases=(),
        currency_policies=(),
        exchange_rates=(),
    )


def test_mysql_adapter_persists_a_draft_transaction_without_publication(settings) -> None:
    database, cursor = persistence_database(settings)
    repository = MySqlMonthlyAssignmentRepository(database)

    generation_id = repository.persist_draft(caja_request(), caja_input(), persisted_caja_result())

    statements = "\n".join(sql for sql, _ in cursor.executed)
    inserted = "\n".join(sql for sql, _ in cursor.executed_many)
    assert generation_id == 901
    assert database.connection.began and database.connection.committed
    assert not database.connection.rolled_back
    assert "asignacion_mensual_generaciones" in statements
    assert "'DRAFT'" in statements
    assert "active_generation_id" in statements
    assert "asignacion_mensual_clientes" in inserted
    assert "asignacion_mensual_operaciones" in inserted
    assert "asignacion_mensual_conciliacion" in inserted
    assert "'PUBLISHED'" not in statements + inserted


def test_mysql_adapter_rolls_back_when_source_changes_before_draft_insert(settings) -> None:
    database, cursor = persistence_database(settings, source_count=0)
    repository = MySqlMonthlyAssignmentRepository(database)

    with pytest.raises(ValueError, match="fuente cambiaron"):
        repository.persist_draft(caja_request(), caja_input(), persisted_caja_result())

    assert database.connection.began
    assert database.connection.rolled_back
    assert not database.connection.committed
    assert not cursor.executed_many

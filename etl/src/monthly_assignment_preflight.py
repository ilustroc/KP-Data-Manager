from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Sequence

from .domain.monthly_assignment import HarvestCatalogEntry
from .domain.monthly_assignment import audit_catalogs


COMPLETED_STATUS = "COMPLETADO"
PERSONAS_EXPECTATION = {
    "batch_id": 44,
    "dataset_code": "PERSONAS",
    "source_code": "BASE_PERSONAS",
    "refresh_modes": frozenset({"FULL_REPLACE", "SCOPE_REPLACE"}),
}
PORTFOLIO_BATCHES = {
    "BBVA": 7,
    "CAJA_AREQUIPA": 14,
    "COMPARTAMOS": 21,
    "CONFIANZA": 26,
    "WANDOO": 29,
}
WANDOO_REFERENCE = {
    "operations": 13044,
    "documents": 13042,
    "capital": Decimal("6615373.31"),
    "debt_total": Decimal("6615373.31"),
}
PROPOSED_TABLES = frozenset(
    {
        ("kp_control", "cartera_cosechas"),
        ("kp_control", "zonas_departamento"),
        ("kp_control", "tipos_cambio"),
        ("kp_control", "asignacion_politicas_moneda"),
        ("kp_control", "asignacion_cosecha_aliases"),
        ("kp_control", "asignacion_catalogo_cambios"),
        ("kp_control", "asignacion_periodos"),
        ("kp_control", "asignacion_periodo_cartera_batch"),
        ("kp_gold", "asignacion_mensual_generaciones"),
        ("kp_gold", "asignacion_mensual_clientes"),
        ("kp_gold", "asignacion_mensual_operaciones"),
        ("kp_gold", "asignacion_mensual_conciliacion"),
        ("kp_gold", "asignacion_mensual_anomalias"),
    }
)
REQUIRED_SOURCE_TABLES = frozenset(
    {
        ("kp_control", "import_batch"),
        ("kp_silver", "cartera_operaciones"),
        ("kp_silver", "search_personas"),
    }
)


@dataclass(frozen=True, slots=True)
class CatalogAlias:
    entidad: str
    cosecha_origen: str
    cosecha_canonica: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class CurrencyPolicySnapshot:
    entidad: str
    cosecha_scope: str
    moneda_confirmada: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    schema: str
    name: str
    engine: str | None = None
    collation: str | None = None


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    batch_id: int
    entidad: str | None
    tipo: str | None
    dataset_code: str | None
    source_code: str | None
    refresh_mode: str | None
    estado: str | None
    published_at: str | None
    rows_published: int | None


@dataclass(frozen=True, slots=True)
class AggregateSnapshot:
    entidad: str
    batch_id: int
    cosecha: str | None
    moneda: str | None
    operations: int
    documents: int
    capital: Decimal | None
    debt_total: Decimal | None


@dataclass(frozen=True, slots=True)
class DuplicateSnapshot:
    entidad: str
    cosecha: str | None
    groups: int
    rows: int


@dataclass(frozen=True, slots=True)
class PreflightSnapshot:
    tables: tuple[TableSnapshot, ...]
    harvests: tuple[HarvestCatalogEntry, ...]
    zones: Mapping[str, str]
    aliases: tuple[CatalogAlias, ...]
    currency_policies: tuple[CurrencyPolicySnapshot, ...]
    batches: tuple[BatchSnapshot, ...]
    aggregates: tuple[AggregateSnapshot, ...]
    duplicates: tuple[DuplicateSnapshot, ...]


@dataclass(frozen=True, slots=True)
class PreflightFinding:
    severity: str
    code: str
    message: str
    context: Mapping[str, str | int | None]


@dataclass(frozen=True, slots=True)
class ReconciliationIndicator:
    entidad: str
    batch_id: int
    cosecha_origen: str | None
    cosecha_canonica: str | None
    moneda_original: str | None
    operations: int
    documents: int
    valid_equivalence: bool
    exclusion_reason: str | None
    capital: Decimal | None
    debt_total: Decimal | None


@dataclass(frozen=True, slots=True)
class PreflightReport:
    decision: str
    findings: tuple[PreflightFinding, ...]
    indicators: tuple[ReconciliationIndicator, ...]
    proposed_table_count: int
    required_source_tables: tuple[tuple[str, str], ...]

    @property
    def blockers(self) -> tuple[PreflightFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "BLOCKER")

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "proposed_table_count": self.proposed_table_count,
            "required_source_tables": [list(table) for table in self.required_source_tables],
            "finding_counts": {
                severity: sum(finding.severity == severity for finding in self.findings)
                for severity in ("BLOCKER", "WARNING", "INFO")
            },
            "findings": [_json_value(asdict(finding)) for finding in self.findings],
            "indicators": [_json_value(asdict(indicator)) for indicator in self.indicators],
        }


@dataclass(frozen=True, slots=True)
class ProposedCatalog:
    harvests: Mapping[str, HarvestCatalogEntry]
    zones: Mapping[str, str]
    aliases: tuple[CatalogAlias, ...]
    currency_policies: tuple[CurrencyPolicySnapshot, ...]
    ddl_table_count: int
    has_database_official_generation_constraint: bool


class MonthlyAssignmentPreflight:
    """Offline-only validator for an aggregated, non-personal database snapshot."""

    def __init__(self, proposed_catalog: ProposedCatalog) -> None:
        self.proposed_catalog = proposed_catalog

    def run(self, snapshot: PreflightSnapshot) -> PreflightReport:
        findings: list[PreflightFinding] = []
        self._validate_schema(snapshot, findings)
        self._review_ddl_strategy(findings)
        self._validate_catalogs(snapshot, findings)
        self._validate_aliases(snapshot, findings)
        self._validate_currency_policies(snapshot, findings)
        self._validate_batches(snapshot, findings)
        indicators = self._build_indicators(snapshot, findings)
        self._validate_wandoo(snapshot, findings)
        self._record_duplicates(snapshot, findings)

        decision = "NO_GO" if any(item.severity == "BLOCKER" for item in findings) else "LOCAL_VALIDATED_REAL_DATA_REQUIRED"
        return PreflightReport(
            decision=decision,
            findings=tuple(sorted(findings, key=lambda item: (item.severity, item.code, str(item.context)))),
            indicators=tuple(sorted(indicators, key=lambda item: (item.entidad, item.batch_id, item.cosecha_origen or "", item.moneda_original or ""))),
            proposed_table_count=len(PROPOSED_TABLES),
            required_source_tables=tuple(sorted(REQUIRED_SOURCE_TABLES)),
        )

    def _validate_schema(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        present = {(table.schema, table.name) for table in snapshot.tables}
        for schema, table in sorted(REQUIRED_SOURCE_TABLES - present):
            findings.append(_finding("BLOCKER", "missing_source_table", "Falta una tabla fuente requerida para el diagnóstico.", schema=schema, table=table))
        for schema, table in sorted(PROPOSED_TABLES & present):
            findings.append(_finding("BLOCKER", "existing_proposed_table", "SQL 059 no es reejecutable: la tabla propuesta ya existe y requiere revisión estructural manual.", schema=schema, table=table))

    def _review_ddl_strategy(self, findings: list[PreflightFinding]) -> None:
        findings.append(_finding("WARNING", "ddl_partial_failure_risk", "SQL 059 crea varias tablas; MySQL confirma DDL implícitamente y exige respaldo, orden de ejecución y validación posterior para recuperarse de fallos parciales.", table_count=self.proposed_catalog.ddl_table_count))
        if not self.proposed_catalog.has_database_official_generation_constraint:
            findings.append(_finding("WARNING", "official_generation_constraint_missing", "La unicidad de una generación oficial por periodo se modela en el servicio, no mediante una restricción verificable en SQL 059.", table="kp_control.asignacion_periodos"))

    def _validate_catalogs(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        duplicate_harvests = {
            entry.cosecha for entry in snapshot.harvests if sum(item.cosecha == entry.cosecha for item in snapshot.harvests) > 1
        }
        for cosecha in sorted(duplicate_harvests):
            findings.append(_finding("BLOCKER", "duplicate_catalog_harvest", "El snapshot contiene más de una versión de una cosecha; no puede compararse de forma determinística.", cosecha=cosecha))
        current_harvests = {entry.cosecha: entry for entry in snapshot.harvests}
        catalog_audit = audit_catalogs(
            expected_harvests=self.proposed_catalog.harvests,
            current_harvests=current_harvests,
            expected_zones=self.proposed_catalog.zones,
            current_zones=snapshot.zones,
        )
        for difference in catalog_audit.differences:
            if difference.current is None:
                findings.append(_finding("INFO", "catalog_seed_missing", "El valor propuesto no existe aún y sería creado por el seed.", catalog=difference.catalog, key=difference.key))
            else:
                findings.append(_finding("BLOCKER", "catalog_existing_drift", "Un valor existente difiere del catálogo propuesto; INSERT IGNORE lo ocultaría sin registrar una solicitud de revisión.", catalog=difference.catalog, key=difference.key))

    def _validate_currency_policies(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        actual = {(item.entidad, item.cosecha_scope): item for item in snapshot.currency_policies}
        for proposed in self.proposed_catalog.currency_policies:
            current = actual.get((proposed.entidad, proposed.cosecha_scope))
            if current is None:
                findings.append(_finding("INFO", "currency_policy_seed_missing", "La política de moneda propuesta no existe aún y sería creada por SQL 059.", entidad=proposed.entidad, cosecha_scope=proposed.cosecha_scope))
            elif current.moneda_confirmada != proposed.moneda_confirmada or current.is_active != proposed.is_active:
                findings.append(_finding("BLOCKER", "currency_policy_existing_drift", "Una política existente contradice la política de moneda propuesta; INSERT IGNORE no la corregiría.", entidad=proposed.entidad, cosecha_scope=proposed.cosecha_scope))

    def _validate_aliases(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        expected = {(item.entidad, item.cosecha_origen): item for item in self.proposed_catalog.aliases}
        actual_by_source: dict[tuple[str, str], list[CatalogAlias]] = {}
        for alias in snapshot.aliases:
            actual_by_source.setdefault((alias.entidad, alias.cosecha_origen), []).append(alias)

        for key, aliases in sorted(actual_by_source.items()):
            targets = {alias.cosecha_canonica for alias in aliases if alias.is_active}
            if len(targets) > 1:
                findings.append(_finding("BLOCKER", "ambiguous_alias", "Una cosecha origen tiene más de un destino activo.", entidad=key[0], cosecha_origen=key[1]))

        for key, proposed in sorted(expected.items()):
            current = actual_by_source.get(key, [])
            active = [alias for alias in current if alias.is_active]
            if not active:
                findings.append(_finding("INFO", "alias_seed_missing", "El alias histórico propuesto no existe aún y sería creado por SQL 059.", entidad=proposed.entidad, cosecha_origen=proposed.cosecha_origen, cosecha_canonica=proposed.cosecha_canonica))
                continue
            if {alias.cosecha_canonica for alias in active} != {proposed.cosecha_canonica}:
                findings.append(_finding("BLOCKER", "alias_existing_drift", "Un alias existente difiere del destino canónico propuesto; INSERT IGNORE no lo corregiría.", entidad=proposed.entidad, cosecha_origen=proposed.cosecha_origen, cosecha_canonica=proposed.cosecha_canonica))

        for key, aliases in sorted(actual_by_source.items()):
            if key not in expected and key[0] == "CONFIANZA" and any(alias.is_active for alias in aliases):
                findings.append(_finding("WARNING", "unexpected_confianza_alias", "Existe un alias Confianza activo fuera del catálogo propuesto; requiere revisión manual.", entidad=key[0], cosecha_origen=key[1]))

        for alias in self.proposed_catalog.aliases:
            catalog = self.proposed_catalog.harvests.get(alias.cosecha_canonica)
            if catalog is None or catalog.entidad != alias.entidad:
                findings.append(_finding("BLOCKER", "alias_owner_mismatch", "El destino de alias no pertenece a la entidad esperada en el catálogo propuesto.", entidad=alias.entidad, cosecha_origen=alias.cosecha_origen, cosecha_canonica=alias.cosecha_canonica))

    def _validate_batches(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        by_id = {batch.batch_id: batch for batch in snapshot.batches}
        for entidad, batch_id in PORTFOLIO_BATCHES.items():
            batch = by_id.get(batch_id)
            if batch is None:
                findings.append(_finding("BLOCKER", "missing_portfolio_batch", "Falta el batch candidato de cartera en el snapshot.", entidad=entidad, batch_id=batch_id))
                continue
            if batch.entidad != entidad or batch.tipo != "CARTERA" or batch.estado != COMPLETED_STATUS:
                findings.append(_finding("BLOCKER", "invalid_portfolio_batch", "El batch de cartera no coincide con entidad, tipo CARTERA y estado COMPLETADO requeridos.", entidad=entidad, batch_id=batch_id))

        personas = by_id.get(PERSONAS_EXPECTATION["batch_id"])
        if personas is None:
            findings.append(_finding("BLOCKER", "missing_personas_batch", "Falta el batch PERSONAS 44 en el snapshot.", batch_id=44))
            return
        if (
            personas.dataset_code != PERSONAS_EXPECTATION["dataset_code"]
            or personas.source_code != PERSONAS_EXPECTATION["source_code"]
            or personas.refresh_mode not in PERSONAS_EXPECTATION["refresh_modes"]
            or personas.estado != COMPLETED_STATUS
            or personas.published_at is None
        ):
            findings.append(_finding("BLOCKER", "invalid_personas_batch", "El batch 44 no cumple el contrato PERSONAS publicado para enriquecimiento.", batch_id=44))

    def _build_indicators(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> list[ReconciliationIndicator]:
        aliases = {(alias.entidad, alias.cosecha_origen): alias.cosecha_canonica for alias in self.proposed_catalog.aliases}
        indicators: list[ReconciliationIndicator] = []
        expected_by_batch = {batch_id: entidad for entidad, batch_id in PORTFOLIO_BATCHES.items()}
        aggregate_batches = {(row.entidad, row.batch_id) for row in snapshot.aggregates}
        for entidad, batch_id in PORTFOLIO_BATCHES.items():
            if (entidad, batch_id) not in aggregate_batches:
                findings.append(_finding("BLOCKER", "missing_batch_aggregate", "El snapshot no contiene indicadores de cartera para el batch candidato.", entidad=entidad, batch_id=batch_id))

        for row in snapshot.aggregates:
            expected_entity = expected_by_batch.get(row.batch_id)
            if expected_entity is None or expected_entity != row.entidad:
                findings.append(_finding("BLOCKER", "unexpected_aggregate_batch", "El agregado no corresponde a uno de los batches candidatos esperados.", entidad=row.entidad, batch_id=row.batch_id))
            source = row.cosecha
            canonical = None if source is None else aliases.get((row.entidad, source), source)
            valid = canonical in self.proposed_catalog.harvests
            exclusion_reason = None if valid else "unknown_harvest"
            if valid and self.proposed_catalog.harvests[canonical].entidad != row.entidad:
                valid = False
                exclusion_reason = "harvest_owner_mismatch"
            if not valid:
                severity = "BLOCKER" if row.entidad == "CONFIANZA" and source == "CONFIANZA_1" else "WARNING"
                code = "blocked_confianza_1" if severity == "BLOCKER" else "excluded_harvest"
                findings.append(_finding(severity, code, "Una cosecha agregada no tiene equivalencia o propietario válido; se excluiría de una generación.", entidad=row.entidad, batch_id=row.batch_id, cosecha_origen=source, cosecha_canonica=canonical))
            indicators.append(ReconciliationIndicator(row.entidad, row.batch_id, source, canonical, row.moneda, row.operations, row.documents, valid, exclusion_reason, row.capital, row.debt_total))
        return indicators

    def _validate_wandoo(self, snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        records = [row for row in snapshot.aggregates if row.entidad == "WANDOO" and row.batch_id == 29 and row.cosecha == "WANDOO_1"]
        if not records:
            findings.append(_finding("BLOCKER", "missing_wandoo_aggregate", "No existe el agregado WANDOO_1 del batch 29.", entidad="WANDOO", batch_id=29))
            return
        operations = sum(row.operations for row in records)
        documents = sum(row.documents for row in records)
        capital = _decimal_sum(row.capital for row in records)
        debt_total = _decimal_sum(row.debt_total for row in records)
        if (operations, documents, capital, debt_total) != (
            WANDOO_REFERENCE["operations"], WANDOO_REFERENCE["documents"], WANDOO_REFERENCE["capital"], WANDOO_REFERENCE["debt_total"],
        ):
            findings.append(_finding("BLOCKER", "wandoo_reference_mismatch", "WANDOO_1 no coincide con los conteos o saldos de referencia; no debe publicarse.", entidad="WANDOO", batch_id=29))
        policy = next((item for item in snapshot.currency_policies if item.entidad == "WANDOO" and item.cosecha_scope == "WANDOO_1" and item.is_active), None)
        if policy is not None and policy.moneda_confirmada != "PEN":
            findings.append(_finding("BLOCKER", "wandoo_currency_policy_conflict", "La política WANDOO_1 existente contradice PEN.", entidad="WANDOO", cosecha_scope="WANDOO_1"))

    @staticmethod
    def _record_duplicates(snapshot: PreflightSnapshot, findings: list[PreflightFinding]) -> None:
        for duplicate in snapshot.duplicates:
            if duplicate.groups > 0:
                findings.append(_finding("WARNING", "possible_duplicate_group", "Hay grupos repetidos para investigar; el preflight no los descarta ni los trata automáticamente como error.", entidad=duplicate.entidad, cosecha=duplicate.cosecha, groups=duplicate.groups, rows=duplicate.rows))


def parse_proposed_catalog(sql_path: Path) -> ProposedCatalog:
    sql = sql_path.read_text(encoding="utf-8")
    harvest_rows = _rows(sql, "cartera_cosechas", r"\('([^']+)', (NULL|'([^']*)'), (NULL|'([^']*)'), '([^']+)', UTC_TIMESTAMP\(\), UTC_TIMESTAMP\(\)\)")
    zone_rows = _rows(sql, "zonas_departamento", r"\('([^']+)', '([^']+)', UTC_TIMESTAMP\(\), UTC_TIMESTAMP\(\)\)")
    alias_rows = _rows(sql, "asignacion_cosecha_aliases", r"\('([^']+)', '([^']+)', '([^']+)', '([^']+)', ([01]), UTC_TIMESTAMP\(\), UTC_TIMESTAMP\(\)\)")
    policy_rows = _rows(sql, "asignacion_politicas_moneda", r"\('([^']+)', '([^']+)', '([^']+)', '([^']+)', ([01]),\s*UTC_TIMESTAMP\(\), UTC_TIMESTAMP\(\)\)")
    if len(harvest_rows) != 30 or len(zone_rows) != 25 or len(alias_rows) != 11 or len(policy_rows) != 1:
        raise ValueError("SQL 059 no contiene el catálogo esperado; revise el parser antes de usar el preflight.")
    harvests = {
        row[0]: HarvestCatalogEntry(row[0], None if row[1] == "NULL" else row[2], None if row[3] == "NULL" else date.fromisoformat(row[4]), row[5])
        for row in harvest_rows
    }
    return ProposedCatalog(
        harvests=harvests,
        zones={row[0]: row[1] for row in zone_rows},
        aliases=tuple(CatalogAlias(row[0], row[1], row[2], row[4] == "1") for row in alias_rows),
        currency_policies=tuple(CurrencyPolicySnapshot(row[0], row[1], row[2], row[4] == "1") for row in policy_rows),
        ddl_table_count=len(re.findall(r"(?m)^CREATE TABLE ", sql)),
        has_database_official_generation_constraint=False,
    )


def load_snapshot(path: Path) -> PreflightSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("El snapshot debe ser un objeto JSON.")
    _reject_personal_keys(payload)
    return PreflightSnapshot(
        tables=tuple(TableSnapshot(str(item["schema"]), str(item["name"]), _optional_text(item.get("engine")), _optional_text(item.get("collation"))) for item in _items(payload, "tables")),
        harvests=tuple(HarvestCatalogEntry(str(item["cosecha"]), _optional_text(item.get("entidad")), _optional_date(item.get("fecha_compra")), str(item["origen"])) for item in _items(payload, "harvests")),
        zones={str(item["departamento"]): str(item["zona"]) for item in _items(payload, "zones")},
        aliases=tuple(CatalogAlias(str(item["entidad"]), str(item["cosecha_origen"]), str(item["cosecha_canonica"]), bool(item.get("is_active", True))) for item in _items(payload, "aliases")),
        currency_policies=tuple(CurrencyPolicySnapshot(str(item["entidad"]), str(item["cosecha_scope"]), str(item["moneda_confirmada"]), bool(item.get("is_active", True))) for item in _items(payload, "currency_policies")),
        batches=tuple(BatchSnapshot(int(item["batch_id"]), _optional_text(item.get("entidad")), _optional_text(item.get("tipo")), _optional_text(item.get("dataset_code")), _optional_text(item.get("source_code")), _optional_text(item.get("refresh_mode")), _optional_text(item.get("estado")), _optional_text(item.get("published_at")), _optional_int(item.get("rows_published"))) for item in _items(payload, "batches")),
        aggregates=tuple(AggregateSnapshot(str(item["entidad"]), int(item["batch_id"]), _optional_text(item.get("cosecha")), _optional_text(item.get("moneda")), int(item["operations"]), int(item["documents"]), _optional_decimal(item.get("capital")), _optional_decimal(item.get("debt_total"))) for item in _items(payload, "aggregates")),
        duplicates=tuple(DuplicateSnapshot(str(item["entidad"]), _optional_text(item.get("cosecha")), int(item["groups"]), int(item["rows"])) for item in _items(payload, "duplicates")),
    )


def mysql_select_plan() -> str:
    """Return only aggregate SELECT diagnostics; callers run them manually after approval."""
    return """-- KP Data Manager: preflight Fase 1. SOLO SELECT, no ejecutar sin autorización.\n\n-- 1. Existencia, motor y collation de fuentes y tablas propuestas.\nSELECT table_schema, table_name, engine, table_collation\nFROM information_schema.tables\nWHERE (table_schema = 'kp_silver' AND table_name IN ('cartera_operaciones', 'search_personas'))\n   OR (table_schema = 'kp_control' AND table_name IN ('import_batch', 'cartera_cosechas', 'zonas_departamento', 'asignacion_cosecha_aliases', 'asignacion_politicas_moneda'))\n   OR (table_schema = 'kp_gold' AND table_name LIKE 'asignacion_mensual_%')\nORDER BY table_schema, table_name;\n\n-- 2. Columnas y collations de objetos existentes; no asumir que IF NOT EXISTS valida su estructura.\nSELECT table_schema, table_name, column_name, column_type, is_nullable, column_key,\n       character_set_name, collation_name\nFROM information_schema.columns\nWHERE (table_schema = 'kp_silver' AND table_name IN ('cartera_operaciones', 'search_personas'))\n   OR (table_schema = 'kp_control' AND table_name LIKE 'asignacion_%')\n   OR (table_schema = 'kp_gold' AND table_name LIKE 'asignacion_mensual_%')\nORDER BY table_schema, table_name, ordinal_position;\n\n-- 3. Índices y referencias existentes para evaluar unicidad, trazabilidad y recuperación.\nSELECT stats.table_schema, stats.table_name, stats.index_name, stats.non_unique,\n       stats.seq_in_index, stats.column_name, refs.referenced_table_schema, refs.referenced_table_name\nFROM information_schema.statistics AS stats\nLEFT JOIN information_schema.key_column_usage AS refs\n  ON refs.table_schema = stats.table_schema\n AND refs.table_name = stats.table_name\n AND refs.column_name = stats.column_name\n AND refs.referenced_table_name IS NOT NULL\nWHERE (stats.table_schema = 'kp_control' AND stats.table_name LIKE 'asignacion_%')\n   OR (stats.table_schema = 'kp_gold' AND stats.table_name LIKE 'asignacion_mensual_%')\nORDER BY stats.table_schema, stats.table_name, stats.index_name, stats.seq_in_index;\n\n-- 4. Inventario no personal de Confianza batch 26.\nSELECT cosecha AS cosecha_origen, COUNT(*) AS operaciones, COUNT(DISTINCT documento_cliente) AS documentos\nFROM kp_silver.cartera_operaciones\nWHERE entidad = 'CONFIANZA' AND batch_id = 26\nGROUP BY cosecha\nORDER BY cosecha;\n\n-- 5. Estado de los cinco batches de cartera y PERSONAS 44.\nSELECT batch_id, tipo, entidad, dataset_code, source_code, refresh_mode, estado, published_at, rows_published\nFROM kp_control.import_batch\nWHERE batch_id IN (7, 14, 21, 26, 29, 44)\nORDER BY batch_id;\n\n-- 6. Cobertura financiera agregada, sin conversiones.\nSELECT entidad, batch_id, cosecha, moneda, COUNT(*) AS operaciones,\n       COUNT(DISTINCT documento_cliente) AS documentos,\n       SUM(saldo_capital) AS capital_original, SUM(deuda_total) AS deuda_total_original\nFROM kp_silver.cartera_operaciones\nWHERE (entidad = 'BBVA' AND batch_id = 7)\n   OR (entidad = 'CAJA_AREQUIPA' AND batch_id = 14)\n   OR (entidad = 'COMPARTAMOS' AND batch_id = 21)\n   OR (entidad = 'CONFIANZA' AND batch_id = 26)\n   OR (entidad = 'WANDOO' AND batch_id = 29)\nGROUP BY entidad, batch_id, cosecha, moneda\nORDER BY entidad, batch_id, cosecha, moneda;\n\n-- 7. Posibles grupos duplicados; devuelve solo conteos agregados.\nSELECT entidad, cosecha, COUNT(*) AS grupos_duplicados, SUM(filas) AS filas_involucradas\nFROM (\n    SELECT entidad, cosecha, documento_cliente, operacion, identificador_origen, COUNT(*) AS filas\n    FROM kp_silver.cartera_operaciones\n    WHERE (entidad = 'BBVA' AND batch_id = 7)\n       OR (entidad = 'CAJA_AREQUIPA' AND batch_id = 14)\n       OR (entidad = 'COMPARTAMOS' AND batch_id = 21)\n       OR (entidad = 'CONFIANZA' AND batch_id = 26)\n       OR (entidad = 'WANDOO' AND batch_id = 29)\n    GROUP BY entidad, cosecha, documento_cliente, operacion, identificador_origen\n    HAVING COUNT(*) > 1\n) AS duplicates\nGROUP BY entidad, cosecha\nORDER BY entidad, cosecha;\n\n-- 8. Ejecutar solo si los catálogos ya existen; confirma propietarios y aliases.\nSELECT alias_row.entidad, alias_row.cosecha_origen, alias_row.cosecha_canonica,\n       alias_row.is_active, catalogo.entidad AS entidad_catalogo, catalogo.origen AS origen_catalogo\nFROM kp_control.asignacion_cosecha_aliases AS alias_row\nLEFT JOIN kp_control.cartera_cosechas AS catalogo\n  ON catalogo.cosecha = alias_row.cosecha_canonica\nWHERE alias_row.entidad = 'CONFIANZA'\nORDER BY alias_row.cosecha_origen;\n"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta el preflight local y desconectado de asignación mensual.")
    parser.add_argument("--snapshot", required=True, type=Path, help="JSON agregado y sin datos personales.")
    parser.add_argument("--sql059", type=Path, default=Path("../database/sql/059_create_monthly_assignment_foundation.sql"))
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--select-plan", type=Path, help="Ruta opcional para el plan SELECT manual.")
    args = parser.parse_args(argv)

    report = MonthlyAssignmentPreflight(parse_proposed_catalog(args.sql059)).run(load_snapshot(args.snapshot))
    _write_report(args.report, report, args.format)
    if args.select_plan is not None:
        args.select_plan.write_text(mysql_select_plan(), encoding="utf-8")
    print(json.dumps({"decision": report.decision, "blockers": len(report.blockers), "report": str(args.report)}, ensure_ascii=False))
    return 0 if report.decision == "LOCAL_VALIDATED_REAL_DATA_REQUIRED" else 2


def _rows(sql: str, table: str, pattern: str) -> list[tuple[str, ...]]:
    statement = re.search(
        rf"INSERT(?: IGNORE)? INTO `kp_control`\.`{table}`.*?VALUES(?P<rows>.*?);(?=\s*(?:--|\Z))",
        sql,
        re.DOTALL,
    )
    if statement is None:
        return []
    return [tuple(match.groups()) for match in re.finditer(pattern, statement.group("rows"), re.DOTALL)]


def _items(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{key} debe ser una lista JSON de objetos.")
    return value


def _reject_personal_keys(payload: Mapping[str, Any]) -> None:
    prohibited = {"documento", "documento_cliente", "nombre", "titular", "telefono", "direccion", "email"}
    stack: list[object] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            if prohibited & set(current):
                raise ValueError("El snapshot de preflight no admite campos personales.")
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _decimal_sum(values: Iterable[Decimal | None]) -> Decimal | None:
    values = tuple(values)
    return None if any(value is None for value in values) else sum(values, Decimal("0"))


def _finding(severity: str, code: str, message: str, **context: str | int | None) -> PreflightFinding:
    return PreflightFinding(severity, code, message, context)


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _write_report(path: Path, report: PreflightReport, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("record_type", "severity", "code", "message", "context", "entidad", "batch_id", "cosecha_origen", "cosecha_canonica", "moneda_original", "operations", "documents", "valid_equivalence", "exclusion_reason", "capital", "debt_total"))
        writer.writeheader()
        for finding in report.findings:
            writer.writerow({"record_type": "finding", "severity": finding.severity, "code": finding.code, "message": finding.message, "context": json.dumps(finding.context, ensure_ascii=False, sort_keys=True)})
        for indicator in report.indicators:
            writer.writerow({"record_type": "indicator", **_json_value(asdict(indicator))})


if __name__ == "__main__":
    raise SystemExit(main())

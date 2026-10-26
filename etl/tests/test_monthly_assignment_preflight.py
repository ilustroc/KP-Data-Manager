from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.monthly_assignment_preflight import AggregateSnapshot
from src.monthly_assignment_preflight import CatalogAlias
from src.monthly_assignment_preflight import DuplicateSnapshot
from src.monthly_assignment_preflight import TableSnapshot
from src.domain.monthly_assignment import HarvestCatalogEntry
from src.monthly_assignment_preflight import MonthlyAssignmentPreflight
from src.monthly_assignment_preflight import PreflightSnapshot
from src.monthly_assignment_preflight import load_snapshot
from src.monthly_assignment_preflight import main
from src.monthly_assignment_preflight import mysql_select_plan
from src.monthly_assignment_preflight import parse_proposed_catalog


ROOT = Path(__file__).parents[2]
SQL_059 = ROOT / "database/sql/059_create_monthly_assignment_foundation.sql"
FIXTURE = Path(__file__).parent / "fixtures/monthly_assignment_preflight_local.json"


def preflight(snapshot: PreflightSnapshot | None = None):
    proposed = parse_proposed_catalog(SQL_059)
    return MonthlyAssignmentPreflight(proposed).run(snapshot or load_snapshot(FIXTURE))


def test_sql_059_parser_reads_the_complete_proposed_catalog_without_manual_duplication():
    proposed = parse_proposed_catalog(SQL_059)

    assert len(proposed.harvests) == 30
    assert len(proposed.zones) == 25
    assert {(alias.cosecha_origen, alias.cosecha_canonica) for alias in proposed.aliases} == {
        (f"CONFIANZA {number}", f"CONFIANZA_{number}") for number in range(2, 13)
    }
    assert proposed.harvests["CONFIANZA_5"].origen == "FONDO II"


def test_local_fixture_generates_only_non_personal_indicators_and_requires_real_data_validation():
    report = preflight()

    assert report.decision == "LOCAL_VALIDATED_REAL_DATA_REQUIRED"
    confianza = next(item for item in report.indicators if item.entidad == "CONFIANZA")
    assert (confianza.cosecha_origen, confianza.cosecha_canonica, confianza.valid_equivalence) == (
        "CONFIANZA 5", "CONFIANZA_5", True
    )
    wandoo = next(item for item in report.indicators if item.entidad == "WANDOO")
    assert (wandoo.operations, wandoo.documents, wandoo.capital, wandoo.debt_total) == (
        13044, 13042, Decimal("6615373.31"), Decimal("6615373.31")
    )
    assert {finding.code for finding in report.findings} >= {"catalog_seed_missing", "alias_seed_missing"}
    serialized = json.dumps(report.to_dict(), ensure_ascii=False)
    assert all(term not in serialized.lower() for term in ("documento_cliente", "telefono", "direccion", "titular"))


def test_existing_catalog_or_alias_drift_is_a_blocker_not_an_insert_ignore_warning():
    snapshot = load_snapshot(FIXTURE)
    snapshot = replace(
        snapshot,
        aliases=(CatalogAlias("CONFIANZA", "CONFIANZA 5", "CONFIANZA_6"),),
    )

    report = preflight(snapshot)

    assert report.decision == "NO_GO"
    assert {finding.code for finding in report.blockers} >= {"alias_existing_drift"}


def test_audit_catalogs_is_executed_by_preflight_and_blocks_existing_catalog_drift():
    snapshot = load_snapshot(FIXTURE)
    snapshot = replace(
        snapshot,
        harvests=(HarvestCatalogEntry("CONFIANZA_5", "CONFIANZA", date(2022, 12, 1), "KP INVEST"),),
    )

    report = preflight(snapshot)

    assert "catalog_existing_drift" in {finding.code for finding in report.blockers}


def test_existing_sql_059_object_or_missing_source_table_blocks_reapplication():
    snapshot = load_snapshot(FIXTURE)
    snapshot = replace(
        snapshot,
        tables=(
            TableSnapshot("kp_control", "import_batch"),
            TableSnapshot("kp_silver", "cartera_operaciones"),
            TableSnapshot("kp_gold", "asignacion_mensual_clientes"),
        ),
    )

    report = preflight(snapshot)

    assert {finding.code for finding in report.blockers} >= {
        "missing_source_table", "existing_proposed_table"
    }


def test_ambiguous_alias_unknown_harvest_and_duplicate_group_are_reported_without_data_mutation():
    snapshot = load_snapshot(FIXTURE)
    snapshot = replace(
        snapshot,
        aliases=(
            CatalogAlias("CONFIANZA", "CONFIANZA 5", "CONFIANZA_5"),
            CatalogAlias("CONFIANZA", "CONFIANZA 5", "CONFIANZA_6"),
        ),
        aggregates=snapshot.aggregates + (
            AggregateSnapshot("CONFIANZA", 26, "CONFIANZA_1", "PEN", 1, 1, None, None),
        ),
        duplicates=(DuplicateSnapshot("CONFIANZA", "CONFIANZA 5", 1, 2),),
    )

    report = preflight(snapshot)

    codes = {finding.code for finding in report.findings}
    assert {"ambiguous_alias", "blocked_confianza_1", "possible_duplicate_group"} <= codes
    assert any(item.cosecha_origen == "CONFIANZA_1" and not item.valid_equivalence for item in report.indicators)


def test_invalid_personas_publication_and_wandoo_reference_mismatch_block_the_preflight():
    snapshot = load_snapshot(FIXTURE)
    broken_batches = tuple(
        replace(batch, published_at=None) if batch.batch_id == 44 else batch for batch in snapshot.batches
    )
    broken_aggregates = tuple(
        replace(item, operations=1) if item.entidad == "WANDOO" else item
        for item in snapshot.aggregates
    )

    report = preflight(replace(snapshot, batches=broken_batches, aggregates=broken_aggregates))

    assert {finding.code for finding in report.blockers} >= {
        "invalid_personas_batch", "wandoo_reference_mismatch"
    }


def test_invalid_portfolio_batch_is_blocked_before_any_generation_attempt():
    snapshot = load_snapshot(FIXTURE)
    batches = tuple(
        replace(batch, estado="ERROR") if batch.batch_id == 26 else batch
        for batch in snapshot.batches
    )

    report = preflight(replace(snapshot, batches=batches))

    assert "invalid_portfolio_batch" in {finding.code for finding in report.blockers}


def test_snapshot_rejects_personal_fields(tmp_path):
    unsafe = tmp_path / "unsafe.json"
    unsafe.write_text('{"aggregates": [{"documento_cliente": "001"}]}', encoding="utf-8")

    with pytest.raises(ValueError, match="campos personales"):
        load_snapshot(unsafe)


def test_cli_writes_json_csv_and_select_only_plan_without_connecting_to_mysql(tmp_path, capsys):
    json_report = tmp_path / "report.json"
    select_plan = tmp_path / "preflight.sql"

    exit_code = main(
        [
            "--snapshot", str(FIXTURE),
            "--sql059", str(SQL_059),
            "--report", str(json_report),
            "--select-plan", str(select_plan),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_report.read_text(encoding="utf-8"))["decision"] == "LOCAL_VALIDATED_REAL_DATA_REQUIRED"
    assert mysql_select_plan() == select_plan.read_text(encoding="utf-8")
    assert "LOCAL_VALIDATED_REAL_DATA_REQUIRED" in capsys.readouterr().out

    csv_report = tmp_path / "report.csv"
    assert main(["--snapshot", str(FIXTURE), "--sql059", str(SQL_059), "--report", str(csv_report), "--format", "csv"]) == 0
    with csv_report.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and {row["record_type"] for row in rows} == {"finding", "indicator"}


def test_select_plan_contains_only_select_statements():
    plan = mysql_select_plan().upper()

    assert plan.count("\nSELECT ") == 8
    assert not any(token in plan for token in ("\nCREATE ", "\nALTER ", "\nINSERT ", "\nUPDATE ", "\nDELETE ", "\nDROP "))

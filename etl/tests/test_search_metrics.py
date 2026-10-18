from __future__ import annotations

import logging

import pytest

from src.metrics import SearchMetrics


class Clock:
    def __init__(self, *values: float) -> None:
        self.values = iter(values)

    def __call__(self) -> float:
        return next(self.values)


def test_metrics_use_injected_monotonic_clock_and_emit_safe_aggregate(caplog) -> None:
    metrics = SearchMetrics(
        42,
        "FAMILIA",
        "FULL_REPLACE",
        clock=Clock(0.0, 1.0, 3.0, 5.0),
        memory_probe=lambda: 12.5,
    )

    with metrics.measure(
        "gold_insert",
        rows_processed=100,
        logical_statement_count=1,
    ):
        pass

    with caplog.at_level(logging.INFO, logger="kpdm.etl.search"):
        metrics.emit(logging.getLogger("kpdm.etl.search"), successful=True)

    contexts = [record.context for record in caplog.records if record.message == "search_phase_metric"]
    insert = next(context for context in contexts if context["phase"] == "gold_insert")
    total = next(context for context in contexts if context["phase"] == "total")

    assert insert["duration_seconds"] == 2.0
    assert insert["rows_processed"] == 100
    assert insert["rows_per_second"] == 50.0
    assert insert["logical_statement_count"] == 1
    assert insert["physical_statement_count"] == 0
    assert insert["peak_memory_mb"] == 12.5
    assert total["duration_seconds"] == 5.0
    assert total["last_phase"] == "gold_insert"
    assert total["failed_phase"] is None


def test_failed_phase_is_recorded_without_free_form_exception_data(caplog) -> None:
    metrics = SearchMetrics(
        7,
        "TELEFONOS",
        "SCOPE_REPLACE",
        clock=Clock(0.0, 1.0, 2.5, 4.0),
        memory_probe=lambda: None,
    )

    with pytest.raises(RuntimeError, match="sensitive-value"):
        with metrics.measure("silver_insert", logical_statement_count=1):
            raise RuntimeError("sensitive-value")

    with caplog.at_level(logging.INFO, logger="kpdm.etl.search"):
        metrics.emit(logging.getLogger("kpdm.etl.search"), successful=False)

    serialized = " ".join(str(record.context) for record in caplog.records)
    total = next(
        record.context
        for record in caplog.records
        if record.message == "search_phase_metric" and record.context["phase"] == "total"
    )

    assert total["failed_phase"] == "silver_insert"
    assert "sensitive-value" not in serialized
    assert "sql" not in serialized.lower()
    assert "password" not in serialized.lower()


def test_physical_statements_are_counted_without_capturing_sql() -> None:
    metrics = SearchMetrics(
        42,
        "FAMILIA",
        "FULL_REPLACE",
        clock=Clock(0.0),
        memory_probe=lambda: None,
    )

    metrics.record_physical_statement("bronze_insert")
    metrics.record_physical_statement("bronze_insert")

    assert metrics._totals["bronze_insert"].physical_statement_count == 2

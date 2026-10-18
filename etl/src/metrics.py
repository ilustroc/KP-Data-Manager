from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator


@dataclass(slots=True)
class PhaseTotals:
    duration_seconds: float = 0.0
    rows_processed: int = 0
    logical_statement_count: int = 0
    executemany_calls: int = 0
    physical_statement_count: int = 0
    invocations: int = 0


@dataclass(slots=True)
class PhaseMeasurement:
    rows_processed: int = 0
    logical_statement_count: int = 0
    executemany_calls: int = 0


class SearchMetrics:
    def __init__(
        self,
        batch_id: int,
        dataset_code: str | None,
        refresh_mode: str | None,
        *,
        clock: Callable[[], float] = time.perf_counter,
        memory_probe: Callable[[], float | None] | None = None,
    ) -> None:
        self.batch_id = batch_id
        self.dataset_code = dataset_code
        self.refresh_mode = refresh_mode
        self.clock = clock
        self.memory_probe = memory_probe or process_peak_memory_mb
        self.started_at = clock()
        self.last_phase: str | None = None
        self.failed_phase: str | None = None
        self._totals: dict[str, PhaseTotals] = {}

    def now(self) -> float:
        return self.clock()

    def record(
        self,
        phase: str,
        duration_seconds: float,
        *,
        rows_processed: int = 0,
        logical_statement_count: int = 0,
        executemany_calls: int = 0,
        failed: bool = False,
    ) -> None:
        totals = self._totals.setdefault(phase, PhaseTotals())
        totals.duration_seconds += max(0.0, duration_seconds)
        totals.rows_processed += max(0, rows_processed)
        totals.logical_statement_count += max(0, logical_statement_count)
        totals.executemany_calls += max(0, executemany_calls)
        totals.invocations += 1
        if failed:
            self.last_phase = phase
            self.failed_phase = phase
        elif self.failed_phase is None:
            self.last_phase = phase

    def record_physical_statement(self, phase: str) -> None:
        totals = self._totals.setdefault(phase, PhaseTotals())
        totals.physical_statement_count += 1

    @contextmanager
    def measure(
        self,
        phase: str,
        *,
        rows_processed: int = 0,
        logical_statement_count: int = 0,
        executemany_calls: int = 0,
    ) -> Iterator[PhaseMeasurement]:
        started_at = self.clock()
        self.last_phase = phase
        measurement = PhaseMeasurement(
            rows_processed=rows_processed,
            logical_statement_count=logical_statement_count,
            executemany_calls=executemany_calls,
        )
        try:
            yield measurement
        except Exception:
            self.record(
                phase,
                self.clock() - started_at,
                rows_processed=measurement.rows_processed,
                logical_statement_count=measurement.logical_statement_count,
                executemany_calls=measurement.executemany_calls,
                failed=True,
            )
            raise
        else:
            self.record(
                phase,
                self.clock() - started_at,
                rows_processed=measurement.rows_processed,
                logical_statement_count=measurement.logical_statement_count,
                executemany_calls=measurement.executemany_calls,
            )

    def emit(self, logger: logging.Logger, *, successful: bool) -> None:
        peak_memory_mb = self.memory_probe()
        total_duration = max(0.0, self.clock() - self.started_at)

        for phase, totals in self._totals.items():
            logger.info(
                "search_phase_metric",
                extra={
                    "context": self._context(
                        phase,
                        totals,
                        peak_memory_mb=peak_memory_mb,
                        successful=successful and phase != self.failed_phase,
                    )
                },
            )

        aggregate = PhaseTotals(
            duration_seconds=total_duration,
            rows_processed=max(
                (totals.rows_processed for totals in self._totals.values()),
                default=0,
            ),
            logical_statement_count=sum(
                totals.logical_statement_count for totals in self._totals.values()
            ),
            executemany_calls=sum(totals.executemany_calls for totals in self._totals.values()),
            physical_statement_count=sum(
                totals.physical_statement_count for totals in self._totals.values()
            ),
            invocations=sum(totals.invocations for totals in self._totals.values()),
        )
        context = self._context(
            "total",
            aggregate,
            peak_memory_mb=peak_memory_mb,
            successful=successful,
        )
        context["last_phase"] = self.last_phase
        context["failed_phase"] = self.failed_phase
        logger.info("search_phase_metric", extra={"context": context})

    def _context(
        self,
        phase: str,
        totals: PhaseTotals,
        *,
        peak_memory_mb: float | None,
        successful: bool,
    ) -> dict[str, object]:
        duration = round(totals.duration_seconds, 6)
        rows_per_second = (
            round(totals.rows_processed / totals.duration_seconds, 3)
            if totals.rows_processed and totals.duration_seconds > 0
            else 0.0
        )
        return {
            "batch_id": self.batch_id,
            "dataset_code": self.dataset_code,
            "refresh_mode": self.refresh_mode,
            "phase": phase,
            "duration_seconds": duration,
            "rows_processed": totals.rows_processed,
            "rows_per_second": rows_per_second,
            "logical_statement_count": totals.logical_statement_count,
            "executemany_calls": totals.executemany_calls,
            "physical_statement_count": totals.physical_statement_count,
            "invocations": totals.invocations,
            "peak_memory_mb": peak_memory_mb,
            "successful": successful,
        }


def process_peak_memory_mb() -> float | None:
    try:
        import resource
    except ImportError:
        return None

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    bytes_used = usage if sys.platform == "darwin" else usage * 1024
    return round(bytes_used / (1024 * 1024), 3)

from __future__ import annotations

import math
import os
import tracemalloc
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from src.domain.models import (
    CellValue,
    ProcessingStats,
    SearchFamilyRecord,
    SearchRawRecord,
    SearchSourceRow,
)
from src.loaders.search_loader import SearchLoader
from src.metrics import SearchMetrics

from .conftest import make_batch


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_ETL_MASS_TESTS") != "1",
    reason="benchmark sintético masivo opt-in",
)


class SyntheticParser:
    def __init__(self, row_count: int) -> None:
        self.row_count = row_count

    def rows(self, source_path: Path):
        del source_path
        for row_number in range(2, self.row_count + 2):
            document = f"{row_number % 20_000:08d}"
            cell = CellValue(document)
            yield SearchSourceRow(
                number=row_number,
                headers=("DOCUMENTO",),
                cells=(cell,),
                mapped_values={"documento": cell},
            )


class SyntheticFamilyNormalizer:
    def normalize(self, row, batch, ingested_at):
        document = str(row.mapped_values["documento"].value)
        digest = f"{row.number:064x}"[-64:]
        return (
            SearchRawRecord(
                batch.batch_id,
                "FAMILIA",
                str(batch.source_code),
                row.number,
                "synthetic.csv",
                "{}",
                digest,
                ingested_at,
            ),
            SearchFamilyRecord(
                row.number,
                document,
                None,
                None,
                None,
                None,
                None,
                None,
                str(batch.source_code),
                batch.batch_id,
                digest,
                ingested_at,
            ),
            [],
        )


class CountingDatabase:
    def __init__(self) -> None:
        self.chunk_sizes: list[int] = []
        self.scope: set[str] = set()

    def insert_search_chunk(
        self,
        raw_records,
        records,
        errors,
        scope_documents,
        *,
        metrics=None,
    ) -> int:
        assert len(raw_records) == len(records)
        assert not errors
        self.chunk_sizes.append(len(raw_records))
        previous = len(self.scope)
        self.scope.update(scope_documents)
        return len(self.scope) - previous

    def update_progress(self, batch_id: int, stats: ProcessingStats) -> None:
        del batch_id, stats


@pytest.mark.parametrize(
    ("row_count", "chunk_size"),
    [(100_000, 2_000), (100_000, 5_000), (100_000, 10_000), (300_000, 5_000), (1_000_000, 5_000)],
)
def test_search_streaming_capacity_is_chunk_bounded(settings, row_count: int, chunk_size: int) -> None:
    database = CountingDatabase()
    loader = SearchLoader(database, replace(settings, insert_batch_size=chunk_size))
    batch = make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="FAMILIA",
        source_code="BASE_FAMILIA",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )
    stats = ProcessingStats()
    metrics = SearchMetrics(
        batch.batch_id,
        batch.dataset_code,
        batch.refresh_mode,
        memory_probe=lambda: None,
    )

    tracemalloc.start()
    try:
        loader._consume_rows(
            batch,
            Path("synthetic.csv"),
            SyntheticParser(row_count),
            SyntheticFamilyNormalizer(),
            stats,
            datetime(2026, 10, 18, 12, 0),
            metrics,
        )
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert stats.file_rows == row_count
    assert stats.inserted_rows == row_count
    assert len(database.chunk_sizes) == math.ceil(row_count / chunk_size)
    assert max(database.chunk_sizes) <= chunk_size
    assert peak_bytes < 256 * 1024 * 1024

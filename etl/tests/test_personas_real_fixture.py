from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from src.parsers.search_parser import SearchParser
from src.profiles.search.personas import PersonasV1Normalizer

from .test_search_personas_profile import HEADERS, TARGETS, search_batch


def test_personas_real_fixture_opt_in():
    configured_path = os.getenv("PERSONAS_REAL_FIXTURE_PATH")
    if not configured_path:
        pytest.skip("PERSONAS_REAL_FIXTURE_PATH no está configurado")
    path = Path(configured_path)
    if not path.is_file():
        pytest.skip("PERSONAS_REAL_FIXTURE_PATH no existe")

    mapping = [
        {
            "source_position": position,
            "source_column": source,
            "target_column": target,
        }
        for position, (source, target) in enumerate(zip(HEADERS, TARGETS, strict=True), start=1)
    ]
    rows = list(SearchParser("xlsx", mapping, TARGETS).rows(path))
    normalizer = PersonasV1Normalizer(100)
    results = [
        normalizer.normalize(row, search_batch(), datetime(2026, 10, 14, 12, 0))
        for row in rows
    ]

    assert rows[0].headers == HEADERS
    assert len(rows) == 3
    assert len([person for _, person, _ in results if person is not None]) == 3
    assert sum(len(errors) for _, _, errors in results) == 0
    documents = [person.documento for _, person, _ in results if person is not None]
    assert len(documents) == len(set(documents))
    assert all(len(document) == 8 and document.isascii() and document.isdigit() for document in documents)

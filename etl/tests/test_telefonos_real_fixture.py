import os
from datetime import datetime
from pathlib import Path

import pytest

from src.parsers.search_parser import SearchParser
from src.profiles.search.telefonos import PHONE_FIELDS, TelefonosV1Normalizer

from .test_search_telefonos_profile import HEADERS, phone_batch


def test_real_telefonos_fixture_has_the_approved_contract():
    configured = os.getenv("TELEFONOS_REAL_FIXTURE_PATH")
    if not configured:
        pytest.skip("TELEFONOS_REAL_FIXTURE_PATH no configurado")
    path = Path(configured)
    if not path.is_file():
        pytest.skip("Fixture privado TELEFONOS no disponible")

    mapping = [
        {"source_position": index + 1, "source_column": header, "target_column": target}
        for index, (header, target) in enumerate(zip(HEADERS, PHONE_FIELDS, strict=True))
    ]
    row_count = 0
    valid_count = 0
    error_count = 0
    duplicate_count = 0
    seen_pairs: set[str] = set()
    first_headers = None
    normalizer = TelefonosV1Normalizer(100)

    for row in SearchParser("xlsx", mapping, PHONE_FIELDS).rows(path):
        first_headers = first_headers or row.headers
        row_count += 1
        _, record, errors = normalizer.normalize(row, phone_batch(), datetime(2026, 10, 15))
        error_count += len(errors)
        if record is None:
            continue
        pair = f"{record.documento}\0{record.telefono}"
        if pair in seen_pairs:
            duplicate_count += 1
            error_count += 1
            continue
        seen_pairs.add(pair)
        valid_count += 1

    assert first_headers == HEADERS
    assert row_count == 175_998
    assert valid_count == 175_275
    assert error_count == 723
    assert duplicate_count == 23

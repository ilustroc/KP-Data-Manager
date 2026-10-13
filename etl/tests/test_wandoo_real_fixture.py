from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import pytest

from src.domain.models import WANDOO_SOURCE_COLUMNS, WandooPortfolioRecord
from src.parsers.cartera_parser import XlsxCarteraParser
from src.profiles.carteras.wandoo import WandooV1Profile


def private_fixture_path() -> Path:
    configured_path = os.getenv("WANDOO_REAL_FIXTURE_PATH")
    if configured_path is None:
        pytest.skip("Configura WANDOO_REAL_FIXTURE_PATH para validar la muestra privada.")

    path = Path(configured_path)
    if not path.is_file():
        pytest.skip("La muestra privada de Wandoo no está disponible en la ruta configurada.")
    return path


def test_real_wandoo_sample_matches_v1_contract_without_persistence():
    path = private_fixture_path()
    profile = WandooV1Profile()
    source_rows = list(XlsxCarteraParser(profile).rows(path))
    normalized = [
        profile.normalize(
            source_row,
            batch_id=1,
            source_file=path.name,
            ingested_at=datetime(2026, 10, 13, 12, 0, 0),
            error_value_max_length=100,
        )
        for source_row in source_rows
    ]
    errors = [error for _, row_errors in normalized for error in row_errors]
    records = [record for record, _ in normalized if record is not None]

    assert len(profile.expected_headers) == 19
    assert tuple(profile.expected_headers) == WANDOO_SOURCE_COLUMNS
    assert len(source_rows) == 20
    assert errors == []
    assert len(records) == 20
    assert all(isinstance(record, WandooPortfolioRecord) for record in records)
    assert all(record.operation.entidad == "WANDOO" for record in records)
    assert all(record.operation.cuenta == "0" + record.operation.documento_cliente for record in records)
    assert all(record.operation.moneda is None for record in records)
    assert all(
        record.operation.saldo_capital
        == record.operation.deuda_total
        == record.detail.saldo_deudor
        for record in records
    )
    assert all(record.operation.interes is None for record in records)
    assert all(record.operation.mora is None for record in records)
    assert all(record.operation.cosecha == "WANDOO_1" for record in records)
    assert all(record.contacts == () for record in records)
    assert all(len(record.addresses) == 1 for record in records)
    assert all(record.operation.fecha_desembolso is not None for record in records)
    assert any(record.detail.fecha_ultimo_pago is None for record in records)
    assert any(record.detail.total_soles_pagados is None for record in records)
    assert any(record.detail.actividad_laboral is None for record in records)
    assert records[0].detail.fecha_otorgamiento_credito == date(2025, 9, 5)

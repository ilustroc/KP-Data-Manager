from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from src.domain.normalizers import (
    FieldNormalizationError,
    cell_to_text,
    normalize_date,
    normalize_money,
    normalize_time,
)
from src.domain.models import CellValue


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2026-10-01", date(2026, 10, 1)),
        ("01/10/2026", date(2026, 10, 1)),
    ],
)
def test_supported_dates_are_normalized(raw_value: str, expected: date) -> None:
    assert normalize_date(CellValue(raw_value)) == expected


def test_invalid_date_is_rejected() -> None:
    with pytest.raises(FieldNormalizationError, match="Fecha inválida"):
        normalize_date(CellValue("31/02/2026"))


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (200, Decimal("200.00")),
        ("200.50", Decimal("200.50")),
        ("S/200.00", Decimal("200.00")),
        ("S/ 200.00", Decimal("200.00")),
        ("1,250.50", Decimal("1250.50")),
        ("S/3,800.00", Decimal("3800.00")),
        (0, Decimal("0.00")),
    ],
)
def test_supported_money_values_use_decimal(raw_value: object, expected: Decimal) -> None:
    assert normalize_money(CellValue(raw_value)) == expected


def test_invalid_money_is_rejected() -> None:
    with pytest.raises(FieldNormalizationError, match="Monto inválido"):
        normalize_money(CellValue("S/XYZ"))


def test_zero_amount_can_be_disabled() -> None:
    with pytest.raises(FieldNormalizationError, match="Monto cero"):
        normalize_money(CellValue("0"), allow_zero=False)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("21:05", time(21, 5, 0)),
        ("17:44:53", time(17, 44, 53)),
        (None, None),
        ("", None),
    ],
)
def test_supported_times_preserve_null(raw_value: object, expected: time | None) -> None:
    assert normalize_time(CellValue(raw_value)) == expected


def test_invalid_time_is_rejected() -> None:
    with pytest.raises(FieldNormalizationError, match="Hora inválida"):
        normalize_time(CellValue("25:61"))


def test_excel_zero_number_format_restores_visible_leading_zeroes() -> None:
    assert cell_to_text(CellValue(60814, "0000000")) == "0060814"


def test_excel_general_number_does_not_invent_leading_zeroes() -> None:
    assert cell_to_text(CellValue(60814, "General")) == "60814"

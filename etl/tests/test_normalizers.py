from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from src.domain.normalizers import (
    FieldNormalizationError,
    PaymentNormalizer,
    cell_to_text,
    normalize_date,
    normalize_money,
    normalize_time,
)
from src.domain.models import CellValue, SourceRow


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


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (216791.33000000002, Decimal("216791.33")),
        (1000.0000000000001, Decimal("1000.00")),
        (-216791.33000000002, Decimal("-216791.33")),
        (0.0, Decimal("0.00")),
    ],
)
def test_xlsx_float_binary_noise_is_quantized_to_two_decimals(
    raw_value: float,
    expected: Decimal,
) -> None:
    cell = CellValue(raw_value, is_xlsx_float=True)

    assert normalize_money(cell) == expected


@pytest.mark.parametrize("raw_value", [100.123, 100.125, 216791.335, 216791.331])
def test_xlsx_float_with_real_additional_precision_is_rejected(raw_value: float) -> None:
    cell = CellValue(raw_value, is_xlsx_float=True)

    with pytest.raises(FieldNormalizationError, match="máximo dos decimales"):
        normalize_money(cell)


def test_csv_money_with_two_decimals_remains_valid() -> None:
    assert normalize_money(CellValue("216791.33")) == Decimal("216791.33")


@pytest.mark.parametrize("raw_value", ["216791.33000000002", "100.123"])
def test_csv_money_with_additional_decimals_remains_strict(raw_value: str) -> None:
    with pytest.raises(FieldNormalizationError, match="máximo dos decimales"):
        normalize_money(CellValue(raw_value))


def test_payment_normalizer_applies_xlsx_float_tolerance_to_both_money_fields() -> None:
    normalizer = PaymentNormalizer(allow_zero_amount=True, error_value_max_length=500)
    row = SourceRow(
        number=2,
        values={
            "FECHA": CellValue("2026-10-01"),
            "MONTO": CellValue(216791.33000000002, is_xlsx_float=True),
            "ACUMULADO": CellValue(1000.0000000000001, is_xlsx_float=True),
            "RECAUDO": CellValue("BCP"),
        },
    )

    record, errors = normalizer.normalize(
        row,
        batch_id=1,
        source_file="pagos.xlsx",
        ingested_at=datetime(2026, 10, 6),
    )

    assert errors == []
    assert record is not None
    assert record.monto == Decimal("216791.33")
    assert record.acumulado == Decimal("1000.00")


def test_payment_normalizer_preserves_optional_accumulated_null_and_zero_amount() -> None:
    normalizer = PaymentNormalizer(allow_zero_amount=True, error_value_max_length=500)
    row = SourceRow(
        number=2,
        values={
            "FECHA": CellValue("2026-10-01"),
            "MONTO": CellValue(0.0, is_xlsx_float=True),
            "ACUMULADO": CellValue(None),
            "RECAUDO": CellValue("BCP"),
        },
    )

    record, errors = normalizer.normalize(
        row,
        batch_id=1,
        source_file="pagos.xlsx",
        ingested_at=datetime(2026, 10, 6),
    )

    assert errors == []
    assert record is not None
    assert record.monto == Decimal("0.00")
    assert record.acumulado is None


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

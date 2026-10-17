from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ...domain.normalizers import FieldNormalizationError, cell_to_text
from .dmf5_contract import contract

DOCUMENT_PATTERN = re.compile(contract()["document_pattern"])
PERIOD_PATTERN = re.compile(contract()["period_pattern"])
MONEY_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def document(cell) -> str:
    value = cell_to_text(cell)
    if value is None or DOCUMENT_PATTERN.fullmatch(value) is None:
        raise FieldNormalizationError("DOCUMENT_INVALID")
    return value


def period(cell) -> str:
    value = cell_to_text(cell)
    if value is None or PERIOD_PATTERN.fullmatch(value) is None:
        raise FieldNormalizationError("PERIOD_INVALID")
    year, month = int(value[:4]), int(value[4:])
    rules = contract()
    if not rules["period_year_min"] <= year <= rules["period_year_max"] or not 1 <= month <= 12:
        raise FieldNormalizationError("PERIOD_INVALID")
    return value


def digits(cell, length: int, code: str) -> str:
    value = cell_to_text(cell)
    if value is None or re.fullmatch(rf"[0-9]{{{length}}}", value) is None:
        raise FieldNormalizationError(code)
    return value


def optional_text(cell, maximum: int, field: str, *, uppercase: bool = False) -> str | None:
    value = cell_to_text(cell)
    if value is None:
        return None
    value = " ".join(value.split())
    if len(value) > maximum:
        raise FieldNormalizationError(f"{field}_INVALID")
    return value.upper() if uppercase else value


def optional_decimal(cell, code: str, *, scale: Decimal = Decimal("0.01"), minimum: Decimal = Decimal("0"), maximum: Decimal = Decimal("9999999999999999.99")) -> Decimal | None:
    value = cell_to_text(cell)
    if value is None:
        return None
    value = value.replace(",", "")
    if MONEY_PATTERN.fullmatch(value) is None:
        raise FieldNormalizationError(code)
    try:
        decimal = Decimal(value)
        normalized = decimal.quantize(scale)
    except InvalidOperation as exception:
        raise FieldNormalizationError(code) from exception
    if decimal != normalized or not minimum <= normalized <= maximum:
        raise FieldNormalizationError(code)
    return normalized


def nonnegative_integer(cell, code: str) -> int | None:
    value = cell_to_text(cell)
    if value is None:
        return None
    if re.fullmatch(r"[0-9]+", value) is None:
        raise FieldNormalizationError(code)
    return int(value)

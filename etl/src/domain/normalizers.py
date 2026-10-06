from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import CellValue, PaymentRecord, RowError, SourceRow

MONEY_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
ZERO_NUMBER_FORMAT_PATTERN = re.compile(r"^0+$")
TWO_DECIMALS = Decimal("0.01")
# XLSX numeric cells are IEEE-754 floats; one billionth isolates representation noise
# while remaining far below the smallest genuine third decimal (0.001).
XLSX_FLOAT_MONEY_TOLERANCE = Decimal("0.000000001")
MAX_DECIMAL_15_2 = Decimal("9999999999999.99")


class FieldNormalizationError(ValueError):
    """Raised when one Bronze field cannot be represented safely."""


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_header(value: Any) -> str:
    return "" if value is None else str(value).strip().upper()


def cell_to_text(cell: CellValue) -> str | None:
    value = cell.value
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite():
            raise FieldNormalizationError("Valor numérico no finito")
        rendered = format(decimal_value, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        number_format = (cell.number_format or "").strip()
        if (
            ZERO_NUMBER_FORMAT_PATTERN.fullmatch(number_format)
            and decimal_value >= 0
            and decimal_value == decimal_value.to_integral_value()
        ):
            return rendered.zfill(len(number_format))
        return rendered
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    return str(value).strip() or None


def normalize_date(cell: CellValue) -> date:
    value = cell.value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = cell_to_text(cell)
    if text is None:
        raise FieldNormalizationError("Fecha obligatoria")
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise FieldNormalizationError("Fecha inválida; usa YYYY-MM-DD o DD/MM/YYYY")


def normalize_money(
    cell: CellValue,
    *,
    allow_zero: bool = True,
    field_label: str = "Monto",
) -> Decimal:
    text = cell_to_text(cell)
    if text is None:
        raise FieldNormalizationError(f"{field_label} obligatorio")

    normalized = re.sub(r"^S/\s*", "", text, flags=re.IGNORECASE).replace(",", "").strip()
    if not MONEY_PATTERN.fullmatch(normalized):
        raise FieldNormalizationError(f"{field_label} inválido")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exception:
        raise FieldNormalizationError(f"{field_label} inválido") from exception
    if not value.is_finite():
        raise FieldNormalizationError(f"{field_label} inválido")

    try:
        quantized = value.quantize(TWO_DECIMALS)
    except InvalidOperation as exception:
        raise FieldNormalizationError(f"{field_label} inválido") from exception
    difference = abs(value - quantized)
    is_acceptable_xlsx_float_noise = (
        cell.is_xlsx_float and difference <= XLSX_FLOAT_MONEY_TOLERANCE
    )
    if value != quantized and not is_acceptable_xlsx_float_noise:
        raise FieldNormalizationError(f"{field_label} admite como máximo dos decimales")
    if abs(quantized) > MAX_DECIMAL_15_2:
        raise FieldNormalizationError(f"{field_label} excede DECIMAL(15,2)")
    if quantized == 0 and not allow_zero:
        raise FieldNormalizationError(f"{field_label} cero no está permitido por configuración")
    return quantized


def normalize_time(cell: CellValue) -> time | None:
    value = cell.value
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, time):
        return value.replace(microsecond=0)

    text = cell_to_text(cell)
    if text is None:
        return None
    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue
    raise FieldNormalizationError("Hora inválida; usa HH:MM o HH:MM:SS")


def normalize_optional_text(cell: CellValue, maximum_length: int, field: str) -> str | None:
    text = cell_to_text(cell)
    if text is not None and len(text) > maximum_length:
        raise FieldNormalizationError(f"{field} excede {maximum_length} caracteres")
    return text


def normalize_required_text(cell: CellValue, maximum_length: int, field: str) -> str:
    text = normalize_optional_text(cell, maximum_length, field)
    if text is None:
        raise FieldNormalizationError(f"{field} obligatorio")
    return text


def payment_row_hash(
    fecha: date,
    documento: str | None,
    monto: Decimal,
    acumulado: Decimal | None,
    recaudo: str,
    operacion: str | None,
    comentario: str | None,
    hora: time | None,
) -> str:
    canonical_values = [
        "pagos:v1",
        fecha.isoformat(),
        documento,
        format(monto, ".2f"),
        None if acumulado is None else format(acumulado, ".2f"),
        recaudo,
        operacion,
        comentario,
        None if hora is None else hora.strftime("%H:%M:%S"),
    ]
    payload = json.dumps(canonical_values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def value_for_error(cell: CellValue, maximum_length: int) -> str | None:
    try:
        rendered = cell_to_text(cell)
    except (FieldNormalizationError, InvalidOperation, ValueError):
        rendered = repr(cell.value)
    if rendered is None:
        return None
    if len(rendered) <= maximum_length:
        return rendered
    return rendered[: max(0, maximum_length - 1)] + "…"


class PaymentNormalizer:
    def __init__(self, *, allow_zero_amount: bool, error_value_max_length: int) -> None:
        self.allow_zero_amount = allow_zero_amount
        self.error_value_max_length = error_value_max_length

    def normalize(
        self,
        row: SourceRow,
        *,
        batch_id: int,
        source_file: str,
        ingested_at: datetime,
    ) -> tuple[PaymentRecord | None, list[RowError]]:
        errors: list[RowError] = []
        normalized: dict[str, Any] = {}

        rules = {
            "FECHA": lambda cell: normalize_date(cell),
            "DOCUMENTO": lambda cell: normalize_optional_text(cell, 30, "DOCUMENTO"),
            "MONTO": lambda cell: normalize_money(cell, allow_zero=self.allow_zero_amount),
            "ACUMULADO": lambda cell: (
                None
                if cell_to_text(cell) is None
                else normalize_money(cell, field_label="Acumulado")
            ),
            "RECAUDO": lambda cell: normalize_required_text(cell, 50, "RECAUDO"),
            "OPERACION": lambda cell: normalize_optional_text(cell, 100, "OPERACION"),
            "COMENTARIO": lambda cell: normalize_optional_text(cell, 260, "COMENTARIO"),
            "HORA": lambda cell: normalize_time(cell),
        }

        for field, rule in rules.items():
            cell = row.values.get(field, CellValue(None))
            try:
                normalized[field] = rule(cell)
            except (FieldNormalizationError, InvalidOperation, ValueError) as exception:
                errors.append(
                    RowError(
                        batch_id=batch_id,
                        row_number=row.number,
                        field=field,
                        value=value_for_error(cell, self.error_value_max_length),
                        message=str(exception),
                        created_at=ingested_at,
                    )
                )

        if errors:
            return None, errors

        row_hash = payment_row_hash(
            normalized["FECHA"],
            normalized["DOCUMENTO"],
            normalized["MONTO"],
            normalized["ACUMULADO"],
            normalized["RECAUDO"],
            normalized["OPERACION"],
            normalized["COMENTARIO"],
            normalized["HORA"],
        )
        return (
            PaymentRecord(
                fecha=normalized["FECHA"],
                documento=normalized["DOCUMENTO"],
                monto=normalized["MONTO"],
                acumulado=normalized["ACUMULADO"],
                recaudo=normalized["RECAUDO"],
                operacion=normalized["OPERACION"],
                comentario=normalized["COMENTARIO"],
                hora=normalized["HORA"],
                source_file=source_file,
                batch_id=batch_id,
                ingested_at=ingested_at,
                row_hash=row_hash,
            ),
            [],
        )

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class BatchRecord:
    batch_id: int
    tipo: str
    estado: str
    archivo_original: str
    archivo_ruta: str
    archivo_extension: str
    archivo_sha256: str | None


@dataclass(frozen=True, slots=True)
class CellValue:
    value: Any
    number_format: str | None = None
    is_xlsx_float: bool = False


@dataclass(frozen=True, slots=True)
class SourceRow:
    number: int
    values: Mapping[str, CellValue]


@dataclass(frozen=True, slots=True)
class PaymentRecord:
    fecha: date
    documento: str | None
    monto: Decimal
    acumulado: Decimal | None
    recaudo: str
    operacion: str | None
    comentario: str | None
    hora: time | None
    source_file: str
    batch_id: int
    ingested_at: datetime
    row_hash: str

    def as_insert_tuple(self) -> tuple[Any, ...]:
        return (
            self.fecha,
            self.documento,
            self.monto,
            self.acumulado,
            self.recaudo,
            self.operacion,
            self.comentario,
            self.hora,
            self.source_file,
            self.batch_id,
            self.ingested_at,
            self.row_hash,
        )


@dataclass(frozen=True, slots=True)
class RowError:
    batch_id: int
    row_number: int
    field: str
    value: str | None
    message: str
    created_at: datetime

    def as_insert_tuple(self) -> tuple[Any, ...]:
        return (
            self.batch_id,
            self.row_number,
            self.field,
            self.value,
            self.message,
            self.created_at,
        )


@dataclass(slots=True)
class ProcessingStats:
    file_rows: int = 0
    inserted_rows: int = 0
    error_rows: int = 0
    duplicate_rows: int = 0


@dataclass(slots=True)
class Chunk:
    payments: list[PaymentRecord] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    file_rows: int = 0
    error_rows: int = 0

    def clear(self) -> None:
        self.payments.clear()
        self.errors.clear()
        self.file_rows = 0
        self.error_rows = 0


class RowParser(Protocol):
    def rows(self, path: Path) -> Iterator[SourceRow]: ...


class DatabasePort(Protocol):
    def get_batch(self, batch_id: int) -> BatchRecord | None: ...

    def claim_batch(self, batch_id: int, started_at: datetime) -> bool: ...

    def insert_chunk(
        self,
        payments: Sequence[PaymentRecord],
        errors: Sequence[RowError],
    ) -> None: ...

    def update_progress(self, batch_id: int, stats: ProcessingStats) -> None: ...

    def finish_batch(
        self,
        batch_id: int,
        status: str,
        finished_at: datetime,
        stats: ProcessingStats,
    ) -> None: ...

    def fail_batch(
        self,
        batch_id: int,
        finished_at: datetime,
        message: str,
        stats: ProcessingStats,
    ) -> None: ...

    def close(self) -> None: ...

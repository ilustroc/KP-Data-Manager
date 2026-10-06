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
    entidad: str | None = None
    perfil_version: str | None = None


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


BBVA_SOURCE_COLUMNS = (
    "CODCENTRAL",
    "CONTRATO",
    "CLAVE",
    "DESJUDICIA",
    "DOCUMENTO",
    "UGA",
    "TERRITORIO",
    "NOMBRE",
    "MONEDA",
    "Suma de Importes",
    "Suma de INTERES",
    "Suma de MORA",
    "OFICINA",
    "NOMB_OF",
    "FECHAVEN",
    "PRODUCTO",
    "DESCPROD",
    "tipodoc",
    "numdoc",
    "direccion",
    "REFE",
    "referencia1",
    "referencia2",
    "ubicacion",
    "codpostal",
    "ubigeo",
    "dpto",
    "provincia",
    "distrito",
    "tipofono1",
    "prefijo1",
    "fono1",
    "extension1",
    "tipofono2",
    "prefijo2",
    "fono2",
    "extension2",
    "tipofono3",
    "prefijo3",
    "fono3",
    "extension3",
    "tipofono4",
    "prefijo4",
    "fono4",
    "extension4",
    "tipofono5",
    "prefijo5",
    "fono5",
    "extension5",
    "NOMB_ESTUD",
    "nomb_est_saehost",
    "COSECHA",
)


@dataclass(frozen=True, slots=True)
class PortfolioOperation:
    entidad: str
    cosecha: str | None
    documento_cliente: str
    tipo_documento: str | None
    cuenta: str
    operacion: str
    identificador_origen: str | None
    nombre_cliente: str | None
    moneda: str | None
    saldo_capital: Decimal
    interes: Decimal | None
    mora: Decimal | None
    fecha_vencimiento: date | None
    producto: str | None
    descripcion_producto: str | None
    agencia: str | None
    oficina: str | None
    territorio: str | None
    ubigeo: str | None
    departamento: str | None
    provincia: str | None
    distrito: str | None


@dataclass(frozen=True, slots=True)
class PortfolioContact:
    telefono: str
    tipo: str | None
    prefijo: str | None
    extension: str | None
    orden: int


@dataclass(frozen=True, slots=True)
class PortfolioAddress:
    tipo_direccion: str
    direccion: str | None
    referencia: str | None
    referencia1: str | None
    referencia2: str | None
    ubicacion: str | None
    codigo_postal: str | None
    ubigeo: str | None
    departamento: str | None
    provincia: str | None
    distrito: str | None


@dataclass(frozen=True, slots=True)
class BbvaPortfolioRecord:
    source_values: tuple[str | None, ...]
    source_row: int
    source_file: str
    batch_id: int
    row_hash: str
    ingested_at: datetime
    operation: PortfolioOperation
    contacts: tuple[PortfolioContact, ...]
    address: PortfolioAddress | None

    def raw_insert_tuple(self) -> tuple[Any, ...]:
        return (
            *self.source_values,
            self.batch_id,
            self.source_row,
            self.source_file,
            self.row_hash,
            self.ingested_at,
        )


@dataclass(slots=True)
class PortfolioChunk:
    records: list[BbvaPortfolioRecord] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    file_rows: int = 0
    error_rows: int = 0

    def clear(self) -> None:
        self.records.clear()
        self.errors.clear()
        self.file_rows = 0
        self.error_rows = 0


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


class CarteraDatabasePort(DatabasePort, Protocol):
    def insert_cartera_chunk(
        self,
        records: Sequence[BbvaPortfolioRecord],
        errors: Sequence[RowError],
    ) -> None: ...

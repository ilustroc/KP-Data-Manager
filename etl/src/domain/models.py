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
    workbook_epoch: datetime | None = None


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
    saldo_capital: Decimal | None
    deuda_total: Decimal | None
    interes: Decimal | None
    mora: Decimal | None
    fecha_castigo: date | None
    fecha_desembolso: date | None
    fecha_vencimiento: date | None
    dias_atraso: int | None
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

    @property
    def addresses(self) -> tuple[PortfolioAddress, ...]:
        return () if self.address is None else (self.address,)


CAJA_AREQUIPA_SOURCE_HEADERS = (
    "NRO_DOC_TIT", "AGENCIA", "ANALISTA", "TITULAR", "CUENTA", "OPERACION",
    "TIPO_CONTABLE", "TIP_SBS", "MONEDA", "SALDO_CAPITAL", "FEC_ULT_PAG",
    "DIAS_ATRASO", "CUO_PAG", "DIR_LEGAL", "REF_LEGAL", "DIS_LEGAL",
    "TEL_TIT", "DIR_GES", "REF_GES", "DIS_GES", "TEL_GES", "ACTIVIDAD",
    "DIR_NEG", "DIS_NEG", "NRO_AVALES", "NOM_AVAL", "DIR_AVAL", "REF_AVAL",
    "DIS_AVAL", "TIP_DOC_TIT", "NRO_DOC_TIT", "TIP_DOC_AVAL", "NRO_DOC_AVAL",
    "TEL_AVAL", "COD_SBS", "FEC_DES", "MTO_DES", "INT_MORATORIO", "INT_COMP",
    "ICV", "SEGUROS", "PENALIDAD", "OTROS_RUBROS", "TOT_DEUDA", "CAL_SBS",
    "PROVISION", "FEC_ING_JUD", "FEC_ING_CAS", "REFINANCIADO", "TIP_GAR1",
    "MTO_GAR1", "TIP_GAR2", "MTO_GAR2", "TIP_GAR3", "MTO_GAR3", "TIP_GAR4",
    "MTO_GAR4", "TIP_GAR5", "MTO_GAR5", "TIP_GAR6", "MTO_GAR6", "UBIGEO",
    "DEPARTAMENTO", "PROVINCIA", "DISTRITO", "COSECHA",
)

CAJA_AREQUIPA_SOURCE_COLUMNS = (
    "NRO_DOC_TIT_1",
    *CAJA_AREQUIPA_SOURCE_HEADERS[1:30],
    "NRO_DOC_TIT_2",
    *CAJA_AREQUIPA_SOURCE_HEADERS[31:],
)

CAJA_AREQUIPA_BRONZE_COLUMNS = (
    "NRO_DOC_TIT",
    *CAJA_AREQUIPA_SOURCE_COLUMNS[1:],
)


COMPARTAMOS_SOURCE_COLUMNS = (
    "Ctacliente",
    "Operación",
    "Documento",
    "NomCliente",
    "oficina Agencia",
    "Skapital",
    "IntComp",
    "IntMoratorio",
    "Deuda total",
    "Moneda",
    "TipCambio",
    "SKSoles",
    "Lote",
    "Empresa",
    "FecCastigo",
    "FecDesembolso",
    "Dias_Atraso",
    "LinNeg",
    "NumDoc",
    "NomDistrito",
    "NomProvincia",
    "NomDepartamento",
    "FecNacimiento",
    "Direccion Cliente",
    "Direccion Negocio",
    "Telefono1",
    "Telefono2",
    "Telefono3",
    "Telefono4",
    "Cosecha",
)

COMPARTAMOS_BRONZE_COLUMNS = COMPARTAMOS_SOURCE_COLUMNS


CONFIANZA_SOURCE_COLUMNS = (
    "DNI",
    "Cuenta Cliente",
    "Nombre del Deudor",
    "Calle y Numero",
    "Ubigeo",
    "Departamento_",
    "Provincia",
    "Distrito",
    "Operacion",
    "Saldo Capital MO",
    "Saldo Capital MN",
    "Interés Vencido",
    "Interés Compensatorio",
    "Interés Moratorio",
    "Seguros",
    "Comisiones",
    "Gastos Judiciales",
    "Moneda",
    "Código de Sucursal de Crédito",
    "Nombre Sucursal de Crédito",
    "Territorio",
    "Corredor",
    "Fecha Castigo",
    "Telefono",
    "Nombre_modulo Origen",
    "Estado de la Operación",
    "COSECHA",
)

CONFIANZA_BRONZE_COLUMNS = CONFIANZA_SOURCE_COLUMNS


@dataclass(frozen=True, slots=True)
class CajaArequipaDetail:
    analista: str | None
    tipo_contable: str | None
    fecha_ultimo_pago: date | None
    cuo_pag: int | None
    actividad: str | None
    nro_avales_reportado: int | None
    codigo_sbs: str | None
    monto_desembolso: Decimal | None
    icv: Decimal | None
    seguros: Decimal | None
    penalidad: Decimal | None
    otros_rubros: Decimal | None
    calificacion_sbs: str | None
    provision: Decimal | None
    fecha_ingreso_judicial: date | None
    refinanciado: str | None


@dataclass(frozen=True, slots=True)
class PortfolioGuarantor:
    orden: int
    nombre_aval: str | None
    tipo_documento: str | None
    documento_aval: str | None
    telefono: str | None
    direccion: str | None
    referencia: str | None
    distrito: str | None
    cantidad_reportada: int | None


@dataclass(frozen=True, slots=True)
class PortfolioGuarantee:
    orden: int
    tipo_garantia: str | None
    monto: Decimal | None


@dataclass(frozen=True, slots=True)
class CajaArequipaPortfolioRecord:
    source_values: tuple[str | None, ...]
    source_row: int
    source_file: str
    batch_id: int
    row_hash: str
    ingested_at: datetime
    operation: PortfolioOperation
    detail: CajaArequipaDetail
    contacts: tuple[PortfolioContact, ...]
    addresses: tuple[PortfolioAddress, ...]
    guarantor: PortfolioGuarantor | None
    guarantees: tuple[PortfolioGuarantee, ...]

    def raw_insert_tuple(self) -> tuple[Any, ...]:
        return (
            *self.source_values,
            self.batch_id,
            self.source_row,
            self.source_file,
            self.row_hash,
            self.ingested_at,
        )


@dataclass(frozen=True, slots=True)
class CompartamosDetail:
    documento_fuente: str | None
    tipo_cambio: Decimal | None
    saldo_capital_soles: Decimal | None
    lote: str | None
    empresa: str | None
    anio_desembolso: int | None
    fecha_nacimiento: date | None


@dataclass(frozen=True, slots=True)
class CompartamosPortfolioRecord:
    source_values: tuple[str | None, ...]
    source_row: int
    source_file: str
    batch_id: int
    row_hash: str
    ingested_at: datetime
    operation: PortfolioOperation
    detail: CompartamosDetail
    contacts: tuple[PortfolioContact, ...]
    addresses: tuple[PortfolioAddress, ...]

    def raw_insert_tuple(self) -> tuple[Any, ...]:
        return (
            *self.source_values,
            self.batch_id,
            self.source_row,
            self.source_file,
            self.row_hash,
            self.ingested_at,
        )


@dataclass(frozen=True, slots=True)
class ConfianzaDetail:
    saldo_capital_mo: Decimal | None
    saldo_capital_mn: Decimal | None
    interes_vencido: Decimal | None
    interes_compensatorio: Decimal | None
    interes_moratorio: Decimal | None
    seguros: Decimal | None
    comisiones: Decimal | None
    gastos_judiciales: Decimal | None
    moneda_origen: str | None
    codigo_sucursal_credito: str | None
    nombre_sucursal_credito: str | None
    corredor: str | None
    nombre_modulo_origen: str | None
    estado_operacion: str | None


@dataclass(frozen=True, slots=True)
class ConfianzaPortfolioRecord:
    source_values: tuple[str | None, ...]
    source_row: int
    source_file: str
    batch_id: int
    row_hash: str
    ingested_at: datetime
    operation: PortfolioOperation
    detail: ConfianzaDetail
    contacts: tuple[PortfolioContact, ...]
    addresses: tuple[PortfolioAddress, ...]

    def raw_insert_tuple(self) -> tuple[Any, ...]:
        return (
            *self.source_values,
            self.batch_id,
            self.source_row,
            self.source_file,
            self.row_hash,
            self.ingested_at,
        )


PortfolioRecord = (
    BbvaPortfolioRecord
    | CajaArequipaPortfolioRecord
    | CompartamosPortfolioRecord
    | ConfianzaPortfolioRecord
)


@dataclass(slots=True)
class PortfolioChunk:
    records: list[PortfolioRecord] = field(default_factory=list)
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
        records: Sequence[PortfolioRecord],
        errors: Sequence[RowError],
    ) -> None: ...

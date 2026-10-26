"""Pure business rules for the monthly portfolio-assignment snapshot.

The module deliberately receives operations already selected by an explicit
batch policy.  It must never merge every historical portfolio batch merely
because it has the same harvest code.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import re
import unicodedata
from typing import Callable, Iterable, Mapping, Sequence


PERIOD_PATTERN = re.compile(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])$")
PERSONAS_DATASET = "PERSONAS"
PERSONAS_SOURCE = "BASE_PERSONAS"
COMPLETED_STATUS = "COMPLETADO"
ALLOWED_PERSONAS_MODES = frozenset({"FULL_REPLACE", "SCOPE_REPLACE"})
PEN = "PEN"
USD = "USD"
PEN_MONEY_QUANTUM = Decimal("0.01")
SUPPORTED_CURRENCIES = frozenset({PEN, USD})


@dataclass(frozen=True, slots=True)
class AssignmentOperation:
    """The traceable subset of a selected Silver portfolio operation."""

    operation_id: int
    batch_id: int
    source_raw_id: int
    entidad: str
    cosecha: str | None
    documento_cliente: str
    titular: str | None
    departamento: str | None
    moneda: str | None
    saldo_capital: Decimal | None
    deuda_total: Decimal | None
    fecha_castigo: date | None
    interes: Decimal | None = None
    mora: Decimal | None = None
    identificador_origen: str | None = None


@dataclass(frozen=True, slots=True)
class HarvestCatalogEntry:
    cosecha: str
    entidad: str | None
    fecha_compra: date | None
    origen: str


@dataclass(frozen=True, slots=True)
class HarvestAlias:
    """An approved one-to-one mapping from a stored harvest value to catalog code."""

    entidad: str
    cosecha_origen: str
    cosecha_catalogo: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ExchangeRate:
    """A manually approved rate copied from an official source, never fetched here."""

    fecha_tipo_cambio: date
    moneda_origen: str
    moneda_destino: str
    tipo_cambio: Decimal
    tipo_cambio_clase: str
    fuente: str


@dataclass(frozen=True, slots=True)
class CurrencyPolicy:
    """Explicit confirmation for a source whose stored currency is unresolved."""

    entidad: str
    moneda_confirmada: str
    cosecha: str | None
    evidence: str


@dataclass(frozen=True, slots=True)
class FinancialConversion:
    moneda_original: str | None
    moneda_resuelta: str | None
    capital_original: Decimal | None
    deuda_total_original: Decimal | None
    tipo_cambio: Decimal | None
    fecha_tipo_cambio: date | None
    tipo_cambio_clase: str | None
    fuente_tipo_cambio: str | None
    capital_pen: Decimal | None
    deuda_total_pen: Decimal | None


@dataclass(frozen=True, slots=True)
class PersonasDemographics:
    fecha_nacimiento: date | None
    sexo: str | None
    estado_civil: str | None


@dataclass(frozen=True, slots=True)
class PersonasSilverRecord:
    """Projection read from ``kp_silver.search_personas`` for enrichment only."""

    batch_id: int
    documento: str
    fecha_nacimiento: date | None
    sexo: str | None
    estado_civil: str | None


@dataclass(frozen=True, slots=True)
class PersonasPublication:
    batch_id: int
    dataset_code: str
    source_code: str
    estado: str
    refresh_mode: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class AssignmentAnomaly:
    code: str
    message: str
    cosecha: str | None = None
    documento_cliente: str | None = None
    operation_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MonthlyAssignmentRow:
    """Exactly the 20 business fields of the monthly-assignment contract."""

    cadena: str
    fecha_compra: date | None
    documento_cliente: str
    titular: str | None
    flg_cliente: int
    flg_cuenta: int
    tipo_monto: None
    anio_cast: int | None
    dpto: str | None
    zona: str | None
    ran_cap: None
    fecha_nacimiento: date | None
    sexo: str | None
    estado_civil: str | None
    origen: str
    entidad: str
    cosecha: str
    cons_deuda_k: Decimal | None
    cons_intereses: Decimal | None
    cons_deuda_total: Decimal | None

    def business_values(self) -> tuple[object, ...]:
        return (
            self.cadena,
            self.fecha_compra,
            self.documento_cliente,
            self.titular,
            self.flg_cliente,
            self.flg_cuenta,
            self.tipo_monto,
            self.anio_cast,
            self.dpto,
            self.zona,
            self.ran_cap,
            self.fecha_nacimiento,
            self.sexo,
            self.estado_civil,
            self.origen,
            self.entidad,
            self.cosecha,
            self.cons_deuda_k,
            self.cons_intereses,
            self.cons_deuda_total,
        )


@dataclass(frozen=True, slots=True)
class ReconciliationRow:
    entidad: str
    cosecha: str
    origen: str
    operation_count: int
    excluded_operation_count: int
    document_count: int
    client_count: int
    original_capital: Decimal | None
    consolidated_capital: Decimal | None
    original_debt_total: Decimal | None
    consolidated_debt_total: Decimal | None
    non_capital_components: Decimal | None


@dataclass(frozen=True, slots=True)
class FinancialReconciliationRow:
    """Financial coverage at source-currency and all-currency reconciliation grains."""

    periodo: str
    entidad: str
    cosecha: str
    batch_id: int
    moneda_origen: str
    operation_count: int
    client_count: int
    capital_original_pen: Decimal | None
    capital_original_usd: Decimal | None
    capital_convertido_pen: Decimal | None
    deuda_total_convertida_pen: Decimal | None
    componentes_no_capital_pen: Decimal | None
    operations_without_currency: int
    operations_without_debt_total: int
    operations_without_exchange_rate: int
    assignment_capital_pen: Decimal | None
    assignment_debt_total_pen: Decimal | None
    difference_capital_pen: Decimal | None
    difference_debt_total_pen: Decimal | None
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CatalogDifference:
    catalog: str
    key: str
    expected: tuple[object, ...] | str
    current: tuple[object, ...] | str | None


@dataclass(frozen=True, slots=True)
class CatalogAuditResult:
    differences: tuple[CatalogDifference, ...]

    @property
    def is_clean(self) -> bool:
        return not self.differences


@dataclass(frozen=True, slots=True)
class AssignmentOperationTrace:
    """Link a published client row back to Silver and its original Bronze row."""

    cadena: str
    entidad: str
    cosecha: str
    cosecha_origen: str
    operation_id: int
    batch_id: int
    source_raw_id: int
    identificador_origen: str | None
    moneda_original: str | None
    moneda_resuelta: str | None
    capital_original: Decimal | None
    deuda_total_original: Decimal | None
    tipo_cambio: Decimal | None
    fecha_tipo_cambio: date | None
    tipo_cambio_clase: str | None
    fuente_tipo_cambio: str | None
    capital_convertido_pen: Decimal | None
    deuda_total_convertida_pen: Decimal | None


@dataclass(frozen=True, slots=True)
class AssignmentConsolidationResult:
    periodo: str
    fecha_corte: date
    batch_personas_id: int | None
    rows: tuple[MonthlyAssignmentRow, ...]
    operation_traces: tuple[AssignmentOperationTrace, ...]
    anomalies: tuple[AssignmentAnomaly, ...]
    reconciliation: tuple[ReconciliationRow, ...]
    financial_reconciliation: tuple[FinancialReconciliationRow, ...]


def normalize_department(value: str | None) -> str | None:
    """Canonicalize lookup input without changing the source value in Silver."""
    if value is None:
        return None
    compact = " ".join(value.strip().split())
    if not compact:
        return None
    decomposed = unicodedata.normalize("NFKD", compact)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_marks.upper()


def validate_period(periodo: str) -> str:
    if not PERIOD_PATTERN.fullmatch(periodo):
        raise ValueError("El periodo debe tener el formato YYYYMM y representar un mes válido.")
    return periodo


class PersonasBatchSelector:
    """Select one confirmed PERSONAS publication; partial publications are valid."""

    @staticmethod
    def select_latest(publications: Iterable[PersonasPublication]) -> PersonasPublication | None:
        candidates = [
            publication
            for publication in publications
            if publication.dataset_code == PERSONAS_DATASET
            and publication.source_code == PERSONAS_SOURCE
            and publication.estado == COMPLETED_STATUS
            and publication.refresh_mode in ALLOWED_PERSONAS_MODES
            and publication.published_at is not None
        ]
        return max(candidates, key=lambda item: (item.published_at, item.batch_id), default=None)

    @staticmethod
    def select_exact(
        publications: Iterable[PersonasPublication], batch_id: int
    ) -> PersonasPublication:
        publication = next((item for item in publications if item.batch_id == batch_id), None)
        if publication is None:
            raise ValueError(f"No existe el batch PERSONAS {batch_id}.")
        if PersonasBatchSelector.select_latest((publication,)) is None:
            raise ValueError(f"El batch PERSONAS {batch_id} no está publicado correctamente.")
        return publication


class DemographicEnricher:
    """Build the LEFT-JOIN payload from one and only one PERSONAS batch."""

    @staticmethod
    def for_selected_batch(
        selected_batch: PersonasPublication,
        records: Iterable[PersonasSilverRecord],
    ) -> dict[str, PersonasDemographics]:
        enrichment: dict[str, PersonasDemographics] = {}
        for record in records:
            documento = _clean_document(record.documento)
            if record.batch_id != selected_batch.batch_id or documento is None:
                continue
            enrichment[documento] = PersonasDemographics(
                fecha_nacimiento=record.fecha_nacimiento,
                sexo=_clean_text(record.sexo),
                estado_civil=_clean_text(record.estado_civil),
            )
        return enrichment


@dataclass(frozen=True, slots=True)
class _ResolvedOperation:
    operation: AssignmentOperation
    cosecha: str
    cosecha_origen: str


class ExchangeRateResolver:
    """Resolve a previously approved rate as of a cut-off date."""

    def __init__(self, rates: Sequence[ExchangeRate], rate_class: str) -> None:
        self.rates = tuple(rates)
        self.rate_class = rate_class

    def resolve(self, moneda_origen: str, fecha_corte: date) -> tuple[ExchangeRate | None, str | None]:
        if moneda_origen == PEN:
            return None, None
        candidates = [
            rate
            for rate in self.rates
            if rate.moneda_origen == moneda_origen
            and rate.moneda_destino == PEN
            and rate.tipo_cambio_clase == self.rate_class
            and rate.fecha_tipo_cambio <= fecha_corte
            and rate.tipo_cambio > Decimal("0")
        ]
        if not candidates:
            return None, "missing_exchange_rate"
        latest_date = max(rate.fecha_tipo_cambio for rate in candidates)
        latest = [rate for rate in candidates if rate.fecha_tipo_cambio == latest_date]
        if len({rate.tipo_cambio for rate in latest}) != 1:
            return None, "ambiguous_exchange_rate"
        return latest[0], None


class MonthlyAssignmentConsolidator:
    """Consolidate selected operations by harvest and document after solarization."""

    def consolidate(
        self,
        *,
        periodo: str,
        fecha_corte: date,
        operations: Sequence[AssignmentOperation],
        harvests: Mapping[str, HarvestCatalogEntry],
        zones_by_department: Mapping[str, str],
        demographics_by_document: Mapping[str, PersonasDemographics],
        batch_personas_id: int | None,
        exchange_rates: Sequence[ExchangeRate] = (),
        currency_policies: Sequence[CurrencyPolicy] = (),
        harvest_aliases: Sequence[HarvestAlias] = (),
        exchange_rate_class: str = "SBS_VENTA",
    ) -> AssignmentConsolidationResult:
        validate_period(periodo)
        normalized_zones = {
            normalized: zone
            for department, zone in zones_by_department.items()
            if (normalized := normalize_department(department)) is not None
        }
        aliases = self._aliases_by_source(harvest_aliases)
        resolver = ExchangeRateResolver(exchange_rates, exchange_rate_class)
        anomalies: list[AssignmentAnomaly] = []
        groups: dict[tuple[str, str], list[_ResolvedOperation]] = {}
        batches_by_harvest: dict[str, set[int]] = {}

        for operation in operations:
            cosecha_origen = _clean_text(operation.cosecha)
            documento = _clean_document(operation.documento_cliente)
            if cosecha_origen is None or documento is None:
                anomalies.append(
                    AssignmentAnomaly(
                        "missing_business_key",
                        "La operación no tiene cosecha o documento; no puede consolidarse.",
                        cosecha=cosecha_origen,
                        documento_cliente=documento,
                        operation_ids=(operation.operation_id,),
                    )
                )
                continue
            cosecha = self._resolve_harvest(operation.entidad, cosecha_origen, aliases)
            resolved = _ResolvedOperation(operation, cosecha, cosecha_origen)
            groups.setdefault((cosecha, documento), []).append(resolved)
            batches_by_harvest.setdefault(cosecha, set()).add(operation.batch_id)

        unsafe_harvests = {
            cosecha for cosecha, batch_ids in batches_by_harvest.items() if len(batch_ids) != 1
        }
        for cosecha in sorted(unsafe_harvests):
            involved = tuple(
                item.operation.operation_id
                for (group_harvest, _), grouped_operations in groups.items()
                if group_harvest == cosecha
                for item in grouped_operations
            )
            anomalies.append(
                AssignmentAnomaly(
                    "ambiguous_portfolio_batches",
                    "La cosecha tiene más de un batch seleccionado; la publicación queda bloqueada.",
                    cosecha=cosecha,
                    operation_ids=involved,
                )
            )

        rows: list[MonthlyAssignmentRow] = []
        operation_traces: list[AssignmentOperationTrace] = []
        for (cosecha, documento), grouped in sorted(groups.items()):
            operations_for_group = tuple(item.operation for item in grouped)
            if cosecha in unsafe_harvests:
                continue
            catalog_entry = harvests.get(cosecha)
            if catalog_entry is None:
                anomalies.append(
                    AssignmentAnomaly(
                        "unknown_harvest",
                        "La cosecha no existe en el catálogo centralizado.",
                        cosecha,
                        documento,
                        tuple(item.operation_id for item in operations_for_group),
                    )
                )
                continue
            if catalog_entry.entidad is None:
                anomalies.append(
                    AssignmentAnomaly(
                        "harvest_without_entity",
                        "La cosecha no tiene entidad Silver aprobada y no puede publicarse.",
                        cosecha,
                        documento,
                        tuple(item.operation_id for item in operations_for_group),
                    )
                )
                continue
            if any(item.entidad != catalog_entry.entidad for item in operations_for_group):
                anomalies.append(
                    AssignmentAnomaly(
                        "harvest_entity_mismatch",
                        "La entidad de Silver no coincide con el catálogo de cosechas.",
                        cosecha,
                        documento,
                        tuple(item.operation_id for item in operations_for_group),
                    )
                )
                continue

            titular = _single_consistent_value(item.titular for item in operations_for_group)
            if titular is None and any(_clean_text(item.titular) is not None for item in operations_for_group):
                anomalies.append(
                    AssignmentAnomaly(
                        "conflicting_holder",
                        "Las operaciones del cliente tienen titulares contradictorios.",
                        cosecha,
                        documento,
                        tuple(item.operation_id for item in operations_for_group),
                    )
                )
            dpto = _single_consistent_value(
                normalize_department(item.departamento) for item in operations_for_group
            )
            if dpto is None:
                anomalies.append(
                    AssignmentAnomaly(
                        "unknown_department",
                        "El departamento está vacío o es contradictorio; la zona queda NULL.",
                        cosecha,
                        documento,
                        tuple(item.operation_id for item in operations_for_group),
                    )
                )
            zona = normalized_zones.get(dpto) if dpto is not None else None
            if dpto is not None and zona is None:
                anomalies.append(
                    AssignmentAnomaly(
                        "unknown_zone",
                        "El departamento no existe en el catálogo de zonas; la zona queda NULL.",
                        cosecha,
                        documento,
                        tuple(item.operation_id for item in operations_for_group),
                    )
                )

            capital, debt_total, interests, conversions = self._financial_totals(
                cosecha,
                documento,
                operations_for_group,
                fecha_corte,
                resolver,
                currency_policies,
                anomalies,
            )
            anio_cast = self._cast_year(cosecha, documento, operations_for_group, anomalies)
            demographics = demographics_by_document.get(documento)
            cadena = f"{cosecha}{documento}"
            rows.append(
                MonthlyAssignmentRow(
                    cadena=cadena,
                    fecha_compra=catalog_entry.fecha_compra,
                    documento_cliente=documento,
                    titular=titular,
                    flg_cliente=1,
                    flg_cuenta=len(operations_for_group),
                    tipo_monto=None,
                    anio_cast=anio_cast,
                    dpto=dpto,
                    zona=zona,
                    ran_cap=None,
                    fecha_nacimiento=None if demographics is None else demographics.fecha_nacimiento,
                    sexo=None if demographics is None else demographics.sexo,
                    estado_civil=None if demographics is None else demographics.estado_civil,
                    origen=catalog_entry.origen,
                    entidad=catalog_entry.entidad,
                    cosecha=cosecha,
                    cons_deuda_k=capital,
                    cons_intereses=interests,
                    cons_deuda_total=debt_total,
                )
            )
            operation_traces.extend(
                AssignmentOperationTrace(
                    cadena=cadena,
                    entidad=item.operation.entidad,
                    cosecha=cosecha,
                    cosecha_origen=item.cosecha_origen,
                    operation_id=item.operation.operation_id,
                    batch_id=item.operation.batch_id,
                    source_raw_id=item.operation.source_raw_id,
                    identificador_origen=item.operation.identificador_origen,
                    moneda_original=conversion.moneda_original,
                    moneda_resuelta=conversion.moneda_resuelta,
                    capital_original=conversion.capital_original,
                    deuda_total_original=conversion.deuda_total_original,
                    tipo_cambio=conversion.tipo_cambio,
                    fecha_tipo_cambio=conversion.fecha_tipo_cambio,
                    tipo_cambio_clase=conversion.tipo_cambio_clase,
                    fuente_tipo_cambio=conversion.fuente_tipo_cambio,
                    capital_convertido_pen=conversion.capital_pen,
                    deuda_total_convertida_pen=conversion.deuda_total_pen,
                )
                for item, conversion in zip(grouped, conversions, strict=True)
            )

        reconciliation = self._reconcile(rows, operation_traces, harvests)
        financial_reconciliation = self._financial_reconciliation(
            periodo, rows, operation_traces
        )
        return AssignmentConsolidationResult(
            periodo=periodo,
            fecha_corte=fecha_corte,
            batch_personas_id=batch_personas_id,
            rows=tuple(rows),
            operation_traces=tuple(operation_traces),
            anomalies=tuple(anomalies),
            reconciliation=tuple(reconciliation),
            financial_reconciliation=tuple(financial_reconciliation),
        )

    @staticmethod
    def _aliases_by_source(
        aliases: Sequence[HarvestAlias],
    ) -> dict[tuple[str, str], HarvestAlias]:
        result: dict[tuple[str, str], HarvestAlias] = {}
        for alias in aliases:
            source = _clean_text(alias.cosecha_origen)
            target = _clean_text(alias.cosecha_catalogo)
            if source is None or target is None:
                raise ValueError("Una equivalencia de cosecha debe tener origen y destino.")
            key = (alias.entidad, source)
            if key in result and result[key] != alias:
                raise ValueError("Una cosecha de origen no puede tener dos equivalencias aprobadas.")
            result[key] = alias
        return result

    @staticmethod
    def _resolve_harvest(
        entidad: str, cosecha_origen: str, aliases: Mapping[tuple[str, str], HarvestAlias]
    ) -> str:
        alias = aliases.get((entidad, cosecha_origen))
        return cosecha_origen if alias is None else alias.cosecha_catalogo

    def _financial_totals(
        self,
        cosecha: str,
        documento: str,
        operations: Sequence[AssignmentOperation],
        fecha_corte: date,
        resolver: ExchangeRateResolver,
        currency_policies: Sequence[CurrencyPolicy],
        anomalies: list[AssignmentAnomaly],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None, tuple[FinancialConversion, ...]]:
        conversions = tuple(
            self._convert_operation(
                cosecha,
                documento,
                operation,
                fecha_corte,
                resolver,
                currency_policies,
                anomalies,
            )
            for operation in operations
        )
        if any(item.capital_pen is None for item in conversions):
            anomalies.append(
                AssignmentAnomaly(
                    "incomplete_capital_coverage",
                    "Falta capital solarizado o moneda/tipo de cambio aprobado; no se publica capital parcial.",
                    cosecha,
                    documento,
                    tuple(item.operation_id for item in operations),
                )
            )
            return None, None, None, conversions
        capital = sum((item.capital_pen for item in conversions), Decimal("0"))
        if any(item.deuda_total_pen is None for item in conversions):
            anomalies.append(
                AssignmentAnomaly(
                    "incomplete_debt_coverage",
                    "El capital válido se conserva, pero falta deuda total solarizada para el grupo.",
                    cosecha,
                    documento,
                    tuple(item.operation_id for item in operations),
                )
            )
            return capital, None, None, conversions
        debt_total = sum((item.deuda_total_pen for item in conversions), Decimal("0"))
        return capital, debt_total, debt_total - capital, conversions

    def _convert_operation(
        self,
        cosecha: str,
        documento: str,
        operation: AssignmentOperation,
        fecha_corte: date,
        resolver: ExchangeRateResolver,
        currency_policies: Sequence[CurrencyPolicy],
        anomalies: list[AssignmentAnomaly],
    ) -> FinancialConversion:
        moneda_original, moneda_resuelta = self._resolve_currency(
            operation, cosecha, currency_policies
        )
        if moneda_resuelta is None:
            anomalies.append(
                AssignmentAnomaly(
                    "unresolved_currency",
                    "La operación no tiene una moneda confirmada; no puede solarizarse.",
                    cosecha,
                    documento,
                    (operation.operation_id,),
                )
            )
            return FinancialConversion(
                moneda_original, None, operation.saldo_capital, operation.deuda_total,
                None, None, None, None, None, None,
            )
        rate, rate_error = resolver.resolve(moneda_resuelta, fecha_corte)
        if rate_error is not None:
            anomalies.append(
                AssignmentAnomaly(
                    rate_error,
                    "No existe un tipo de cambio oficial aprobado al corte para solarizar la operación.",
                    cosecha,
                    documento,
                    (operation.operation_id,),
                )
            )
            return FinancialConversion(
                moneda_original, moneda_resuelta, operation.saldo_capital, operation.deuda_total,
                None, None, resolver.rate_class, None, None, None,
            )
        factor = Decimal("1") if moneda_resuelta == PEN else rate.tipo_cambio
        return FinancialConversion(
            moneda_original=moneda_original,
            moneda_resuelta=moneda_resuelta,
            capital_original=operation.saldo_capital,
            deuda_total_original=operation.deuda_total,
            tipo_cambio=factor,
            fecha_tipo_cambio=None if rate is None else rate.fecha_tipo_cambio,
            tipo_cambio_clase="IDENTITY_PEN" if rate is None else rate.tipo_cambio_clase,
            fuente_tipo_cambio="IDENTITY_PEN" if rate is None else rate.fuente,
            capital_pen=_solarize(operation.saldo_capital, factor),
            deuda_total_pen=_solarize(operation.deuda_total, factor),
        )

    @staticmethod
    def _resolve_currency(
        operation: AssignmentOperation,
        cosecha: str,
        policies: Sequence[CurrencyPolicy],
    ) -> tuple[str | None, str | None]:
        moneda_original = _clean_text(operation.moneda)
        direct = _canonical_currency(moneda_original)
        if direct in SUPPORTED_CURRENCIES:
            return moneda_original, direct
        exact_matches = [
            policy
            for policy in policies
            if policy.entidad == operation.entidad
            and policy.cosecha == cosecha
        ]
        entity_matches = [
            policy
            for policy in policies
            if policy.entidad == operation.entidad and policy.cosecha is None
        ]
        matches = exact_matches or entity_matches
        if not matches:
            return moneda_original, None
        confirmed = {_canonical_currency(policy.moneda_confirmada) for policy in matches}
        if len(confirmed) != 1 or None in confirmed:
            return moneda_original, None
        return moneda_original, next(iter(confirmed))

    @staticmethod
    def _cast_year(
        cosecha: str,
        documento: str,
        operations: Sequence[AssignmentOperation],
        anomalies: list[AssignmentAnomaly],
    ) -> int | None:
        years = {item.fecha_castigo.year for item in operations if item.fecha_castigo is not None}
        if not years:
            return None
        if len(years) == 1 and all(item.fecha_castigo is not None for item in operations):
            return next(iter(years))
        anomalies.append(
            AssignmentAnomaly(
                "ambiguous_cast_year",
                "No existe una única fecha de castigo inequívoca para el cliente consolidado.",
                cosecha,
                documento,
                tuple(item.operation_id for item in operations),
            )
        )
        return None

    @staticmethod
    def _reconcile(
        rows: Sequence[MonthlyAssignmentRow],
        operation_traces: Sequence[AssignmentOperationTrace],
        harvests: Mapping[str, HarvestCatalogEntry],
    ) -> list[ReconciliationRow]:
        rows_by_harvest: dict[str, list[MonthlyAssignmentRow]] = {}
        traces_by_harvest: dict[str, list[AssignmentOperationTrace]] = {}
        for row in rows:
            rows_by_harvest.setdefault(row.cosecha, []).append(row)
        for trace in operation_traces:
            traces_by_harvest.setdefault(trace.cosecha, []).append(trace)
        report: list[ReconciliationRow] = []
        for cosecha, grouped_rows in sorted(rows_by_harvest.items()):
            catalog = harvests[cosecha]
            grouped_traces = traces_by_harvest.get(cosecha, [])
            currencies = {trace.moneda_resuelta for trace in grouped_traces}
            original_capital = (
                _sum_if_complete(trace.capital_original for trace in grouped_traces)
                if len(currencies) == 1 else None
            )
            original_debt = (
                _sum_if_complete(trace.deuda_total_original for trace in grouped_traces)
                if len(currencies) == 1 else None
            )
            consolidated_capital = _sum_if_complete(row.cons_deuda_k for row in grouped_rows)
            consolidated_debt = _sum_if_complete(row.cons_deuda_total for row in grouped_rows)
            report.append(
                ReconciliationRow(
                    entidad=catalog.entidad or "",
                    cosecha=cosecha,
                    origen=catalog.origen,
                    operation_count=len(grouped_traces),
                    excluded_operation_count=0,
                    document_count=len({row.documento_cliente for row in grouped_rows}),
                    client_count=len(grouped_rows),
                    original_capital=original_capital,
                    consolidated_capital=consolidated_capital,
                    original_debt_total=original_debt,
                    consolidated_debt_total=consolidated_debt,
                    non_capital_components=(
                        None
                        if consolidated_capital is None or consolidated_debt is None
                        else consolidated_debt - consolidated_capital
                    ),
                )
            )
        return report

    @staticmethod
    def _financial_reconciliation(
        periodo: str,
        rows: Sequence[MonthlyAssignmentRow],
        traces: Sequence[AssignmentOperationTrace],
    ) -> list[FinancialReconciliationRow]:
        report: list[FinancialReconciliationRow] = []
        by_currency: dict[tuple[str, str, int, str], list[AssignmentOperationTrace]] = {}
        by_batch: dict[tuple[str, str, int], list[AssignmentOperationTrace]] = {}
        for trace in traces:
            currency = trace.moneda_original or "UNKNOWN"
            by_currency.setdefault((trace.entidad, trace.cosecha, trace.batch_id, currency), []).append(trace)
            by_batch.setdefault((trace.entidad, trace.cosecha, trace.batch_id), []).append(trace)

        for (entidad, cosecha, batch_id, currency), grouped in sorted(by_currency.items()):
            status, warnings = _financial_status(grouped)
            report.append(
                FinancialReconciliationRow(
                    periodo=periodo,
                    entidad=entidad,
                    cosecha=cosecha,
                    batch_id=batch_id,
                    moneda_origen=currency,
                    operation_count=len(grouped),
                    client_count=len({trace.cadena for trace in grouped}),
                    capital_original_pen=_sum_available(
                        trace.capital_original for trace in grouped if trace.moneda_resuelta == PEN
                    ),
                    capital_original_usd=_sum_available(
                        trace.capital_original for trace in grouped if trace.moneda_resuelta == USD
                    ),
                    capital_convertido_pen=_sum_available(trace.capital_convertido_pen for trace in grouped),
                    deuda_total_convertida_pen=_sum_available(
                        trace.deuda_total_convertida_pen for trace in grouped
                    ),
                    componentes_no_capital_pen=_sum_available(
                        trace.deuda_total_convertida_pen - trace.capital_convertido_pen
                        for trace in grouped
                        if trace.deuda_total_convertida_pen is not None
                        and trace.capital_convertido_pen is not None
                    ),
                    operations_without_currency=sum(trace.moneda_resuelta is None for trace in grouped),
                    operations_without_debt_total=sum(trace.deuda_total_original is None for trace in grouped),
                    operations_without_exchange_rate=sum(
                        trace.moneda_resuelta == USD and trace.tipo_cambio is None for trace in grouped
                    ),
                    assignment_capital_pen=None,
                    assignment_debt_total_pen=None,
                    difference_capital_pen=None,
                    difference_debt_total_pen=None,
                    status=status,
                    warnings=warnings,
                )
            )

        for (entidad, cosecha, batch_id), grouped in sorted(by_batch.items()):
            status, warnings = _financial_status(grouped)
            assignment_rows = [row for row in rows if row.entidad == entidad and row.cosecha == cosecha]
            assignment_capital = _sum_if_complete(row.cons_deuda_k for row in assignment_rows)
            assignment_debt = _sum_if_complete(row.cons_deuda_total for row in assignment_rows)
            capital_converted = _sum_available(trace.capital_convertido_pen for trace in grouped)
            debt_converted = _sum_available(trace.deuda_total_convertida_pen for trace in grouped)
            can_compare = (
                status == "COMPLETE"
                and capital_converted is not None
                and debt_converted is not None
                and assignment_capital is not None
                and assignment_debt is not None
            )
            report.append(
                FinancialReconciliationRow(
                    periodo=periodo,
                    entidad=entidad,
                    cosecha=cosecha,
                    batch_id=batch_id,
                    moneda_origen="ALL",
                    operation_count=len(grouped),
                    client_count=len({trace.cadena for trace in grouped}),
                    capital_original_pen=_sum_available(
                        trace.capital_original for trace in grouped if trace.moneda_resuelta == PEN
                    ),
                    capital_original_usd=_sum_available(
                        trace.capital_original for trace in grouped if trace.moneda_resuelta == USD
                    ),
                    capital_convertido_pen=capital_converted,
                    deuda_total_convertida_pen=debt_converted,
                    componentes_no_capital_pen=_sum_available(
                        trace.deuda_total_convertida_pen - trace.capital_convertido_pen
                        for trace in grouped
                        if trace.deuda_total_convertida_pen is not None
                        and trace.capital_convertido_pen is not None
                    ),
                    operations_without_currency=sum(trace.moneda_resuelta is None for trace in grouped),
                    operations_without_debt_total=sum(trace.deuda_total_original is None for trace in grouped),
                    operations_without_exchange_rate=sum(
                        trace.moneda_resuelta == USD and trace.tipo_cambio is None for trace in grouped
                    ),
                    assignment_capital_pen=assignment_capital,
                    assignment_debt_total_pen=assignment_debt,
                    difference_capital_pen=(capital_converted - assignment_capital) if can_compare else None,
                    difference_debt_total_pen=(debt_converted - assignment_debt) if can_compare else None,
                    status=status,
                    warnings=warnings,
                )
            )
        return report


def audit_catalogs(
    *,
    expected_harvests: Mapping[str, HarvestCatalogEntry],
    current_harvests: Mapping[str, HarvestCatalogEntry],
    expected_zones: Mapping[str, str],
    current_zones: Mapping[str, str],
) -> CatalogAuditResult:
    """Detect drift without changing a manually corrected catalog row."""
    differences: list[CatalogDifference] = []
    for cosecha, expected in sorted(expected_harvests.items()):
        current = current_harvests.get(cosecha)
        expected_values = (expected.entidad, expected.fecha_compra, expected.origen)
        current_values = (
            None if current is None else (current.entidad, current.fecha_compra, current.origen)
        )
        if expected_values != current_values:
            differences.append(
                CatalogDifference("cartera_cosechas", cosecha, expected_values, current_values)
            )
    for department, expected_zone in sorted(expected_zones.items()):
        normalized = normalize_department(department)
        if normalized is None:
            raise ValueError("El catálogo esperado de zonas no puede tener un departamento vacío.")
        current_zone = current_zones.get(normalized)
        if expected_zone != current_zone:
            differences.append(
                CatalogDifference("zonas_departamento", normalized, expected_zone, current_zone)
            )
    return CatalogAuditResult(tuple(differences))


@dataclass(frozen=True, slots=True)
class AssignmentGeneration:
    generation_id: int
    periodo: str
    rows: tuple[MonthlyAssignmentRow, ...]
    fingerprint: str
    status: str
    failure_message: str | None = None


class InMemoryOfficialGenerationRegistry:
    """Models atomic promotion of one official generation per open period."""

    def __init__(self) -> None:
        self._next_generation_id = 1
        self._generations: dict[int, AssignmentGeneration] = {}
        self._active_by_period: dict[str, int] = {}
        self._closed_periods: set[str] = set()

    def begin(self, periodo: str, rows: Sequence[MonthlyAssignmentRow]) -> AssignmentGeneration:
        validate_period(periodo)
        candidate_rows = tuple(rows)
        fingerprint = _rows_fingerprint(candidate_rows)
        active = self.active(periodo)
        if active is not None and active.fingerprint == fingerprint:
            return active
        if periodo in self._closed_periods:
            raise ValueError("Un periodo cerrado no admite nuevas generaciones.")
        for generation in self._generations.values():
            if (
                generation.periodo == periodo
                and generation.status == "DRAFT"
                and generation.fingerprint == fingerprint
            ):
                return generation
        generation = AssignmentGeneration(
            generation_id=self._next_generation_id,
            periodo=periodo,
            rows=candidate_rows,
            fingerprint=fingerprint,
            status="DRAFT",
        )
        self._generations[generation.generation_id] = generation
        self._next_generation_id += 1
        return generation

    def publish(
        self,
        generation_id: int,
        *,
        pre_commit_validation: Callable[[], None] | None = None,
    ) -> AssignmentGeneration:
        generation = self._generations[generation_id]
        if generation.status == "PUBLISHED":
            return generation
        if generation.status != "DRAFT":
            raise ValueError("Solo una generación de prueba puede publicarse.")
        if generation.periodo in self._closed_periods:
            raise ValueError("Un periodo cerrado no puede cambiar su generación oficial.")
        if pre_commit_validation is not None:
            pre_commit_validation()

        previous = self.active(generation.periodo)
        published = replace(generation, status="PUBLISHED")
        self._generations[generation_id] = published
        if previous is not None and previous.generation_id != generation_id:
            self._generations[previous.generation_id] = replace(previous, status="SUPERSEDED")
        self._active_by_period[generation.periodo] = generation_id
        return published

    def fail(self, generation_id: int, message: str) -> AssignmentGeneration:
        generation = self._generations[generation_id]
        if generation.status != "DRAFT":
            raise ValueError("Solo una generación de prueba puede fallar.")
        failed = replace(generation, status="FAILED", failure_message=message)
        self._generations[generation_id] = failed
        return failed

    def close(self, periodo: str) -> AssignmentGeneration:
        active = self.active(periodo)
        if active is None:
            raise ValueError("No existe una generación oficial para cerrar el periodo.")
        self._closed_periods.add(periodo)
        return active

    def active(self, periodo: str) -> AssignmentGeneration | None:
        generation_id = self._active_by_period.get(periodo)
        return None if generation_id is None else self._generations[generation_id]

    def generation(self, generation_id: int) -> AssignmentGeneration:
        return self._generations[generation_id]


@dataclass(frozen=True, slots=True)
class AssignmentSnapshot:
    periodo: str
    rows: tuple[MonthlyAssignmentRow, ...]
    closed: bool = False


class InMemoryAssignmentSnapshots:
    """Small policy object used by tests; persistence belongs to the Gold proposal."""

    def __init__(self) -> None:
        self._snapshots: dict[str, AssignmentSnapshot] = {}

    def generate(
        self, periodo: str, rows: Sequence[MonthlyAssignmentRow], *, replace_open: bool = False
    ) -> AssignmentSnapshot:
        validate_period(periodo)
        candidate = tuple(rows)
        existing = self._snapshots.get(periodo)
        if existing is None:
            snapshot = AssignmentSnapshot(periodo, candidate)
            self._snapshots[periodo] = snapshot
            return snapshot
        if existing.rows == candidate:
            return existing
        if existing.closed:
            raise ValueError("Un periodo cerrado no puede sobrescribirse.")
        if not replace_open:
            raise ValueError("Regenerar un periodo abierto exige una acción explícita.")
        snapshot = AssignmentSnapshot(periodo, candidate)
        self._snapshots[periodo] = snapshot
        return snapshot

    def close(self, periodo: str) -> AssignmentSnapshot:
        snapshot = self._snapshots[periodo]
        closed = replace(snapshot, closed=True)
        self._snapshots[periodo] = closed
        return closed

    def refresh_marital_status(
        self,
        periodo: str,
        status_by_document: Mapping[str, str | None],
        *,
        refreshed_on: date,
    ) -> AssignmentSnapshot:
        snapshot = self._snapshots[periodo]
        if snapshot.closed:
            raise ValueError("No se actualiza estado civil en un periodo cerrado.")
        if refreshed_on.day != 1:
            raise ValueError("El refresco de estado civil solo se permite el primer día del mes.")
        refreshed = tuple(
            replace(row, estado_civil=status_by_document.get(row.documento_cliente))
            for row in snapshot.rows
        )
        result = AssignmentSnapshot(periodo, refreshed)
        self._snapshots[periodo] = result
        return result

    def fingerprint(self, periodo: str) -> str:
        snapshot = self._snapshots[periodo]
        return _rows_fingerprint(snapshot.rows)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    result = " ".join(value.strip().split())
    return result or None


def _clean_document(value: str | None) -> str | None:
    return _clean_text(value)


def _single_consistent_value(values: Iterable[str | None]) -> str | None:
    distinct = {_clean_text(value) for value in values if _clean_text(value) is not None}
    return next(iter(distinct)) if len(distinct) == 1 else None


def _sum_if_complete(values: Iterable[Decimal | None]) -> Decimal | None:
    collected = tuple(values)
    if any(value is None for value in collected):
        return None
    return sum(collected, Decimal("0"))


def _sum_available(values: Iterable[Decimal | None]) -> Decimal | None:
    available = tuple(value for value in values if value is not None)
    return None if not available else sum(available, Decimal("0"))


def _canonical_currency(value: str | None) -> str | None:
    normalized = _clean_text(value)
    if normalized is None:
        return None
    upper = normalized.upper()
    if upper in {"PEN", "S/", "S/.", "SOLES"}:
        return PEN
    if upper in {"USD", "US$", "DOLARES", "DÓLARES"}:
        return USD
    return None


def _solarize(value: Decimal | None, factor: Decimal) -> Decimal | None:
    if value is None:
        return None
    return (value * factor).quantize(PEN_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _financial_status(
    traces: Sequence[AssignmentOperationTrace],
) -> tuple[str, tuple[str, ...]]:
    warnings: list[str] = []
    if any(trace.moneda_resuelta is None for trace in traces):
        warnings.append("unresolved_currency")
    if any(trace.moneda_resuelta == USD and trace.tipo_cambio is None for trace in traces):
        warnings.append("missing_exchange_rate")
    if warnings:
        return "BLOCKED", tuple(warnings)
    if any(
        trace.capital_convertido_pen is None or trace.deuda_total_convertida_pen is None
        for trace in traces
    ):
        return "PARTIAL", ("incomplete_financial_coverage",)
    return "COMPLETE", ()


def _rows_fingerprint(rows: Sequence[MonthlyAssignmentRow]) -> str:
    serialized = repr(tuple(row.business_values() for row in rows)).encode("utf-8")
    return sha256(serialized).hexdigest()

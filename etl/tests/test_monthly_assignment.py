from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re

import pytest

from src.domain.monthly_assignment import (
    AssignmentOperation,
    InMemoryOfficialGenerationRegistry,
    CurrencyPolicy,
    DemographicEnricher,
    ExchangeRate,
    HarvestCatalogEntry,
    HarvestAlias,
    InMemoryAssignmentSnapshots,
    MonthlyAssignmentConsolidator,
    MonthlyAssignmentRow,
    PersonasBatchSelector,
    PersonasPublication,
    PersonasSilverRecord,
    audit_catalogs,
    normalize_department,
    validate_period,
)


CATALOG = {
    "CAJAAQP3": HarvestCatalogEntry("CAJAAQP3", "CAJA_AREQUIPA", date(2020, 12, 22), "FONDO I"),
    "BBVA3": HarvestCatalogEntry("BBVA3", "BBVA", date(2020, 11, 1), "FONDO I"),
    "BBVA7": HarvestCatalogEntry("BBVA7", "BBVA", date(2020, 12, 30), "FONDO II"),
    "BBVA1": HarvestCatalogEntry("BBVA1", "BBVA", date(2020, 9, 30), "KP INVEST"),
    "CONFIANZA": HarvestCatalogEntry("CONFIANZA", "CONFIANZA", date(2019, 12, 9), "KP INVEST"),
    "CONFIANZA_2": HarvestCatalogEntry("CONFIANZA_2", "CONFIANZA", date(2020, 12, 22), "KP INVEST"),
    "CONFIANZA_3": HarvestCatalogEntry("CONFIANZA_3", "CONFIANZA", date(2021, 11, 30), "KP INVEST"),
    "CONFIANZA_4": HarvestCatalogEntry("CONFIANZA_4", "CONFIANZA", date(2022, 7, 30), "KP INVEST"),
    "CONFIANZA_5": HarvestCatalogEntry("CONFIANZA_5", "CONFIANZA", date(2022, 12, 1), "FONDO II"),
    "CONFIANZA_6": HarvestCatalogEntry("CONFIANZA_6", "CONFIANZA", date(2023, 6, 30), "KP INVEST"),
    "CONFIANZA_7": HarvestCatalogEntry("CONFIANZA_7", "CONFIANZA", date(2023, 9, 12), "KP INVEST"),
    "CONFIANZA_8": HarvestCatalogEntry("CONFIANZA_8", "CONFIANZA", date(2023, 11, 28), "KP INVEST"),
    "CONFIANZA_9": HarvestCatalogEntry("CONFIANZA_9", "CONFIANZA", date(2023, 12, 7), "KP INVEST"),
    "CONFIANZA_10": HarvestCatalogEntry("CONFIANZA_10", "CONFIANZA", date(2024, 2, 29), "KP INVEST"),
    "CONFIANZA_11": HarvestCatalogEntry("CONFIANZA_11", "CONFIANZA", date(2024, 5, 31), "KP INVEST"),
    "CONFIANZA_12": HarvestCatalogEntry("CONFIANZA_12", "CONFIANZA", date(2024, 12, 26), "KP INVEST"),
    "WANDOO_1": HarvestCatalogEntry("WANDOO_1", "WANDOO", date(2026, 4, 10), "KP INVEST"),
    "SEMBRANDO": HarvestCatalogEntry("SEMBRANDO", None, None, "KP INVEST"),
}


def usd_rate(fecha=date(2026, 10, 30), factor="3.50000000") -> ExchangeRate:
    return ExchangeRate(fecha, "USD", "PEN", Decimal(factor), "SBS_VENTA", "BCRP PD04640PD")

ZONES = {
    "AMAZONAS": "ORIENTE", "ANCASH": "NORTE", "APURIMAC": "SUR", "AREQUIPA": "SUR",
    "AYACUCHO": "SUR", "CAJAMARCA": "NORTE", "CALLAO": "CENTRO", "CUSCO": "SUR",
    "HUANCAVELICA": "CENTRO", "HUANUCO": "CENTRO", "ICA": "SUR", "JUNIN": "CENTRO",
    "LA LIBERTAD": "NORTE", "LAMBAYEQUE": "NORTE", "LIMA": "CENTRO", "LORETO": "ORIENTE",
    "MADRE DE DIOS": "ORIENTE", "MOQUEGUA": "SUR", "PASCO": "CENTRO", "PIURA": "NORTE",
    "PUNO": "SUR", "SAN MARTIN": "ORIENTE", "TACNA": "SUR", "TUMBES": "NORTE",
    "UCAYALI": "ORIENTE",
}


def operation(
    operation_id: int,
    *,
    cosecha: str = "CAJAAQP3",
    entidad: str = "CAJA_AREQUIPA",
    documento: str = "30561135",
    batch_id: int = 91,
    capital: str | None = "100.00",
    deuda: str | None = "150.00",
    moneda: str | None = "PEN",
    titular: str | None = "ANA PEREZ",
    departamento: str | None = "Arequipa",
    castigo: date | None = date(2020, 1, 2),
    interes: str | None = None,
    mora: str | None = None,
    identificador_origen: str | None = None,
) -> AssignmentOperation:
    return AssignmentOperation(
        operation_id=operation_id,
        batch_id=batch_id,
        source_raw_id=1000 + operation_id,
        entidad=entidad,
        cosecha=cosecha,
        documento_cliente=documento,
        titular=titular,
        departamento=departamento,
        moneda=moneda,
        saldo_capital=None if capital is None else Decimal(capital),
        deuda_total=None if deuda is None else Decimal(deuda),
        fecha_castigo=castigo,
        interes=None if interes is None else Decimal(interes),
        mora=None if mora is None else Decimal(mora),
        identificador_origen=identificador_origen,
    )


def consolidate(
    *operations: AssignmentOperation,
    demographics=None,
    fecha_corte=date(2026, 10, 31),
    exchange_rates=(),
    currency_policies=(),
    harvest_aliases=(),
):
    return MonthlyAssignmentConsolidator().consolidate(
        periodo="202610",
        fecha_corte=fecha_corte,
        operations=operations,
        harvests=CATALOG,
        zones_by_department=ZONES,
        demographics_by_document={} if demographics is None else demographics,
        batch_personas_id=44,
        exchange_rates=exchange_rates,
        currency_policies=currency_policies,
        harvest_aliases=harvest_aliases,
    )


def assignment_row(*, titular="ANA") -> MonthlyAssignmentRow:
    return MonthlyAssignmentRow(
        "BBVA1001", date(2020, 9, 30), "001", titular, 1, 1, None, None, "LIMA", "CENTRO",
        None, None, None, "SOLTERA", "KP INVEST", "BBVA", "BBVA1", Decimal("1"), Decimal("0"), Decimal("1"),
    )


def test_caja_arequipa_four_operations_are_consolidated_with_exact_decimals():
    result = consolidate(
        operation(1, capital="3105.65", deuda="6065.77"),
        operation(2, capital="3744.44", deuda="7740.10"),
        operation(3, capital="17069.19", deuda="35828.29"),
        operation(4, capital="2682.51", deuda="7418.15"),
    )

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.cadena == "CAJAAQP330561135"
    assert row.fecha_compra == date(2020, 12, 22)
    assert row.origen == "FONDO I"
    assert row.flg_cliente == 1
    assert row.flg_cuenta == 4
    assert row.cons_deuda_k == Decimal("26601.79")
    assert row.cons_intereses == Decimal("30450.52")
    assert row.cons_deuda_total == Decimal("57052.31")
    assert len(row.business_values()) == 20
    assert {(trace.operation_id, trace.batch_id, trace.source_raw_id) for trace in result.operation_traces} == {
        (1, 91, 1001), (2, 91, 1002), (3, 91, 1003), (4, 91, 1004)
    }


def test_same_document_in_two_harvests_creates_two_rows_and_preserves_leading_zeros():
    result = consolidate(
        operation(1, documento="00003862", cosecha="BBVA3", entidad="BBVA"),
        operation(2, documento="00003862", cosecha="BBVA7", entidad="BBVA"),
    )

    assert {(row.cosecha, row.documento_cliente, row.cadena) for row in result.rows} == {
        ("BBVA3", "00003862", "BBVA300003862"),
        ("BBVA7", "00003862", "BBVA700003862"),
    }


def test_catalog_origins_cover_kp_invest_fondo_i_and_fondo_ii():
    result = consolidate(
        operation(1, cosecha="BBVA1", entidad="BBVA", documento="1"),
        operation(2, cosecha="BBVA3", entidad="BBVA", documento="2"),
        operation(3, cosecha="BBVA7", entidad="BBVA", documento="3"),
    )

    assert {row.origen for row in result.rows} == {"KP INVEST", "FONDO I", "FONDO II"}


def test_wandoo_rows_with_the_same_operation_number_are_counted_without_deduplication():
    result = consolidate(
        operation(1, cosecha="WANDOO_1", entidad="WANDOO", capital="10", deuda="10"),
        operation(2, cosecha="WANDOO_1", entidad="WANDOO", capital="20", deuda="20"),
    )

    assert result.rows[0].flg_cuenta == 2
    assert result.rows[0].cons_deuda_k == Decimal("30")
    assert result.rows[0].cons_deuda_total == Decimal("30")


def test_multiple_batches_for_one_harvest_are_blocked_instead_of_duplicated():
    result = consolidate(operation(1, batch_id=91), operation(2, batch_id=92))

    assert result.rows == ()
    assert [anomaly.code for anomaly in result.anomalies] == ["ambiguous_portfolio_batches"]


def test_missing_debt_total_preserves_complete_capital_but_not_a_partial_debt_total():
    result = consolidate(operation(1, deuda=None))

    row = result.rows[0]
    assert (row.cons_deuda_k, row.cons_intereses, row.cons_deuda_total) == (Decimal("100.00"), None, None)
    assert "incomplete_debt_coverage" in {item.code for item in result.anomalies}


def test_mixed_currencies_are_blocked_when_the_usd_rate_is_not_approved():
    result = consolidate(operation(1, moneda="PEN"), operation(2, moneda="USD"))

    assert result.rows[0].cons_deuda_total is None
    assert "missing_exchange_rate" in {item.code for item in result.anomalies}


def test_pen_operation_preserves_amounts_with_the_identity_conversion_factor():
    result = consolidate(operation(1, capital="10.10", deuda="15.15", moneda="PEN"))

    row = result.rows[0]
    trace = result.operation_traces[0]
    assert (row.cons_deuda_k, row.cons_intereses, row.cons_deuda_total) == (
        Decimal("10.10"), Decimal("5.05"), Decimal("15.15")
    )
    assert (trace.tipo_cambio, trace.fuente_tipo_cambio) == (Decimal("1"), "IDENTITY_PEN")
    assert trace.fecha_tipo_cambio is None


def test_usd_operation_is_solarized_using_the_latest_approved_rate_on_or_before_cutoff():
    result = consolidate(
        operation(1, capital="10.00", deuda="15.00", moneda="USD"),
        fecha_corte=date(2026, 10, 31),
        exchange_rates=(usd_rate(date(2026, 10, 29), "3.40000000"), usd_rate(date(2026, 10, 30), "3.50000000")),
    )

    row = result.rows[0]
    trace = result.operation_traces[0]
    assert (row.cons_deuda_k, row.cons_intereses, row.cons_deuda_total) == (
        Decimal("35.00"), Decimal("17.50"), Decimal("52.50")
    )
    assert (trace.tipo_cambio, trace.fecha_tipo_cambio, trace.fuente_tipo_cambio) == (
        Decimal("3.50000000"), date(2026, 10, 30), "BCRP PD04640PD"
    )


def test_client_with_pen_and_usd_operations_is_consolidated_only_after_each_operation_is_solarized():
    result = consolidate(
        operation(1, capital="100.00", deuda="120.00", moneda="PEN"),
        operation(2, capital="10.00", deuda="15.00", moneda="USD"),
        exchange_rates=(usd_rate(factor="3.50000000"),),
    )

    row = result.rows[0]
    assert (row.cons_deuda_k, row.cons_intereses, row.cons_deuda_total) == (
        Decimal("135.00"), Decimal("37.50"), Decimal("172.50")
    )
    assert row.cons_deuda_k + row.cons_intereses == row.cons_deuda_total


def test_solarization_rounds_each_operation_deterministically_before_aggregation():
    result = consolidate(
        operation(1, capital="1.00", deuda="1.00", moneda="USD"),
        operation(2, capital="1.00", deuda="1.00", moneda="USD"),
        exchange_rates=(usd_rate(factor="3.00500000"),),
    )

    assert result.rows[0].cons_deuda_k == Decimal("6.02")
    assert result.rows[0].cons_deuda_total == Decimal("6.02")


def test_future_exchange_rate_is_not_used_when_no_rate_exists_at_or_before_cutoff():
    result = consolidate(
        operation(1, moneda="USD"),
        fecha_corte=date(2026, 10, 30),
        exchange_rates=(usd_rate(date(2026, 10, 31)),),
    )

    assert result.rows[0].cons_deuda_k is None
    assert "missing_exchange_rate" in {item.code for item in result.anomalies}


def test_wandoo_unknown_currency_keeps_operation_count_but_blocks_solarized_amounts():
    result = consolidate(
        operation(1, cosecha="WANDOO_1", entidad="WANDOO", moneda="SIN_MONEDA", capital="10", deuda="10")
    )

    row = result.rows[0]
    assert row.flg_cuenta == 1
    assert (row.cons_deuda_k, row.cons_deuda_total) == (None, None)
    assert "unresolved_currency" in {item.code for item in result.anomalies}


def test_wandoo_amounts_are_solarized_only_with_an_explicit_confirmed_currency_policy():
    result = consolidate(
        operation(1, cosecha="WANDOO_1", entidad="WANDOO", moneda="SIN_MONEDA", capital="10", deuda="10"),
        currency_policies=(
            CurrencyPolicy("WANDOO", "PEN", "WANDOO_1", "Contrato de origen aprobado"),
        ),
    )

    assert (result.rows[0].cons_deuda_k, result.rows[0].cons_deuda_total) == (
        Decimal("10.00"), Decimal("10.00")
    )
    assert result.operation_traces[0].moneda_original == "SIN_MONEDA"
    assert result.operation_traces[0].moneda_resuelta == "PEN"


def test_wandoo_batch_29_reference_totals_reconcile_by_document_without_hardcoding_business_logic():
    operations = tuple(
        operation(
            operation_id,
            cosecha="WANDOO_1",
            entidad="WANDOO",
            documento=(
                "00000001" if operation_id <= 2 else "00000002" if operation_id <= 4
                else f"{operation_id - 2:08d}"
            ),
            batch_id=29,
            moneda="SIN_MONEDA",
            capital="500.00" if operation_id < 13044 else "93873.31",
            deuda="500.00" if operation_id < 13044 else "93873.31",
            identificador_origen=f"WAN1:{operation_id:064x}",
        )
        for operation_id in range(1, 13045)
    )

    result = consolidate(
        *operations,
        currency_policies=(
            CurrencyPolicy(
                "WANDOO", "PEN", "WANDOO_1", "confirmación funcional del negocio del 2026-10-26"
            ),
        ),
    )

    assert len(result.rows) == 13042
    assert sum(row.flg_cliente for row in result.rows) == 13042
    assert sum(row.flg_cuenta for row in result.rows) == 13044
    assert sum(row.cons_deuda_k for row in result.rows) == Decimal("6615373.31")
    assert sum(row.cons_deuda_total for row in result.rows) == Decimal("6615373.31")
    assert sum(row.cons_intereses for row in result.rows) == Decimal("0.00")
    assert len(result.operation_traces) == 13044
    assert all(trace.identificador_origen and trace.identificador_origen.startswith("WAN1:") for trace in result.operation_traces)


def test_conflicting_currency_policies_do_not_silently_choose_a_wandoo_currency():
    result = consolidate(
        operation(1, cosecha="WANDOO_1", entidad="WANDOO", moneda="SIN_MONEDA", capital="10", deuda="10"),
        currency_policies=(
            CurrencyPolicy("WANDOO", "PEN", "WANDOO_1", "Documento A"),
            CurrencyPolicy("WANDOO", "USD", "WANDOO_1", "Documento B"),
        ),
    )

    assert result.rows[0].cons_deuda_k is None
    assert "unresolved_currency" in {item.code for item in result.anomalies}


def test_bbva_keeps_total_debt_null_when_contract_only_has_capital_interest_and_mora():
    result = consolidate(
        operation(
            1,
            cosecha="BBVA1",
            entidad="BBVA",
            moneda="USD",
            capital="100.00",
            deuda=None,
            interes="20.00",
            mora="10.00",
        ),
        exchange_rates=(usd_rate(factor="3.50000000"),),
    )

    row = result.rows[0]
    assert row.cons_deuda_k == Decimal("350.00")
    assert (row.cons_intereses, row.cons_deuda_total) == (None, None)
    assert "incomplete_debt_coverage" in {item.code for item in result.anomalies}


def test_confianza_harvest_with_spaces_requires_an_explicit_approved_alias():
    source_operation = operation(
        1, cosecha="CONFIANZA 3", entidad="CONFIANZA", capital="10", deuda="15"
    )

    blocked = consolidate(source_operation)
    mapped = consolidate(
        source_operation,
        harvest_aliases=(
            HarvestAlias("CONFIANZA", "CONFIANZA 3", "CONFIANZA_3", "Auditoría de cosecha aprobada"),
        ),
    )

    assert blocked.rows == ()
    assert mapped.rows[0].cosecha == "CONFIANZA_3"
    assert mapped.operation_traces[0].cosecha_origen == "CONFIANZA 3"


@pytest.mark.parametrize(
    ("source_harvest", "canonical_harvest"),
    (
        ("CONFIANZA 2", "CONFIANZA_2"),
        ("CONFIANZA 3", "CONFIANZA_3"),
        ("CONFIANZA 4", "CONFIANZA_4"),
        ("CONFIANZA 5", "CONFIANZA_5"),
        ("CONFIANZA 6", "CONFIANZA_6"),
        ("CONFIANZA 7", "CONFIANZA_7"),
        ("CONFIANZA 8", "CONFIANZA_8"),
        ("CONFIANZA 9", "CONFIANZA_9"),
        ("CONFIANZA 10", "CONFIANZA_10"),
        ("CONFIANZA 11", "CONFIANZA_11"),
        ("CONFIANZA 12", "CONFIANZA_12"),
    ),
)
def test_confianza_aliases_map_each_approved_source_value_to_one_canonical_harvest(
    source_harvest, canonical_harvest
):
    result = consolidate(
        operation(1, cosecha=source_harvest, entidad="CONFIANZA"),
        harvest_aliases=(
            HarvestAlias("CONFIANZA", source_harvest, canonical_harvest, "Auditoría aprobada"),
        ),
    )

    assert [row.cosecha for row in result.rows] == [canonical_harvest]
    assert result.rows[0].origen == CATALOG[canonical_harvest].origen


def test_confianza_5_alias_preserves_the_fondo_ii_catalog_classification():
    result = consolidate(
        operation(1, cosecha="CONFIANZA 5", entidad="CONFIANZA"),
        harvest_aliases=(
            HarvestAlias("CONFIANZA", "CONFIANZA 5", "CONFIANZA_5", "Auditoría aprobada"),
        ),
    )

    assert result.rows[0].cosecha == "CONFIANZA_5"
    assert result.rows[0].origen == "FONDO II"


def test_confianza_rejects_an_ambiguous_alias_for_the_same_source_harvest():
    aliases = (
        HarvestAlias("CONFIANZA", "CONFIANZA 5", "CONFIANZA_5", "Evidencia A"),
        HarvestAlias("CONFIANZA", "CONFIANZA 5", "CONFIANZA_6", "Evidencia B"),
    )

    with pytest.raises(ValueError, match="no puede tener dos equivalencias aprobadas"):
        consolidate(operation(1, cosecha="CONFIANZA 5", entidad="CONFIANZA"), harvest_aliases=aliases)


def test_catalog_audit_detects_differences_without_overwriting_current_values():
    expected_harvests = {"BBVA1": CATALOG["BBVA1"]}
    current_harvest = HarvestCatalogEntry("BBVA1", "BBVA", date(2020, 10, 1), "KP INVEST")

    audit = audit_catalogs(
        expected_harvests=expected_harvests,
        current_harvests={"BBVA1": current_harvest},
        expected_zones={"LIMA": "CENTRO"},
        current_zones={"LIMA": "NORTE"},
    )

    assert not audit.is_clean
    assert {(difference.catalog, difference.key) for difference in audit.differences} == {
        ("cartera_cosechas", "BBVA1"), ("zonas_departamento", "LIMA")
    }
    assert current_harvest.fecha_compra == date(2020, 10, 1)


def test_catalog_audit_reports_a_manual_confianza_5_origin_without_changing_it():
    current_harvest = HarvestCatalogEntry(
        "CONFIANZA_5", "CONFIANZA", date(2022, 12, 1), "KP INVEST"
    )

    audit = audit_catalogs(
        expected_harvests={"CONFIANZA_5": CATALOG["CONFIANZA_5"]},
        current_harvests={"CONFIANZA_5": current_harvest},
        expected_zones={},
        current_zones={},
    )

    assert audit.differences[0].catalog == "cartera_cosechas"
    assert audit.differences[0].key == "CONFIANZA_5"
    assert current_harvest.origen == "KP INVEST"


def test_generation_registry_keeps_one_active_official_generation_per_open_period():
    registry = InMemoryOfficialGenerationRegistry()
    first = registry.begin("202610", (assignment_row(titular="ANA"),))
    second = registry.begin("202610", (assignment_row(titular="BEA"),))

    registry.publish(first.generation_id)
    published_second = registry.publish(second.generation_id)

    assert registry.active("202610") == published_second
    assert registry.generation(first.generation_id).status == "SUPERSEDED"
    assert registry.generation(second.generation_id).status == "PUBLISHED"


def test_failed_publication_keeps_previous_official_generation_active():
    registry = InMemoryOfficialGenerationRegistry()
    official = registry.begin("202610", (assignment_row(titular="ANA"),))
    registry.publish(official.generation_id)
    candidate = registry.begin("202610", (assignment_row(titular="BEA"),))

    with pytest.raises(RuntimeError, match="simulated publication failure"):
        registry.publish(
            candidate.generation_id,
            pre_commit_validation=lambda: (_ for _ in ()).throw(RuntimeError("simulated publication failure")),
        )

    assert registry.active("202610").generation_id == official.generation_id
    assert registry.generation(candidate.generation_id).status == "DRAFT"
    assert registry.fail(candidate.generation_id, "simulated publication failure").status == "FAILED"


def test_closed_period_is_immutable_and_retry_of_same_official_snapshot_is_idempotent():
    registry = InMemoryOfficialGenerationRegistry()
    official = registry.begin("202610", (assignment_row(),))
    registry.publish(official.generation_id)
    registry.close("202610")

    assert registry.begin("202610", (assignment_row(),)).generation_id == official.generation_id
    with pytest.raises(ValueError, match="cerrado"):
        registry.begin("202610", (assignment_row(titular="BEA"),))


def test_financial_reconciliation_reports_currency_coverage_and_zero_assignment_difference():
    result = consolidate(
        operation(1, capital="100.00", deuda="120.00", moneda="PEN"),
        operation(2, capital="10.00", deuda="15.00", moneda="USD"),
        exchange_rates=(usd_rate(factor="3.50000000"),),
    )

    aggregate = next(item for item in result.financial_reconciliation if item.moneda_origen == "ALL")
    usd = next(item for item in result.financial_reconciliation if item.moneda_origen == "USD")
    assert (aggregate.status, aggregate.capital_original_pen, aggregate.capital_original_usd) == (
        "COMPLETE", Decimal("100.00"), Decimal("10.00")
    )
    assert (aggregate.capital_convertido_pen, aggregate.deuda_total_convertida_pen) == (
        Decimal("135.00"), Decimal("172.50")
    )
    assert (aggregate.difference_capital_pen, aggregate.difference_debt_total_pen) == (
        Decimal("0.00"), Decimal("0.00")
    )
    assert (usd.assignment_capital_pen, usd.difference_capital_pen) == (None, None)


def test_trace_freezes_original_values_and_the_rate_used_for_each_operation_without_mutating_source():
    source_operation = operation(
        1, moneda="USD", capital="10.00", deuda="15.00", identificador_origen="WAN1:trace"
    )

    result = consolidate(source_operation, exchange_rates=(usd_rate(factor="3.50000000"),))

    assert source_operation.saldo_capital == Decimal("10.00")
    assert source_operation.deuda_total == Decimal("15.00")
    assert result.operation_traces[0].capital_original == Decimal("10.00")
    assert result.operation_traces[0].deuda_total_original == Decimal("15.00")
    assert result.operation_traces[0].capital_convertido_pen == Decimal("35.00")
    assert result.operation_traces[0].identificador_origen == "WAN1:trace"


def test_same_approved_rate_is_idempotent_and_a_closed_period_rejects_recalculation_with_new_rate():
    source_operation = operation(1, moneda="USD", capital="10.00", deuda="15.00")
    first = consolidate(source_operation, exchange_rates=(usd_rate(factor="3.50000000"),))
    repeated = consolidate(source_operation, exchange_rates=(usd_rate(factor="3.50000000"),))
    recalculated = consolidate(source_operation, exchange_rates=(usd_rate(factor="3.60000000"),))
    snapshots = InMemoryAssignmentSnapshots()

    assert first.rows == repeated.rows
    assert first.operation_traces == repeated.operation_traces
    snapshots.generate("202610", first.rows)
    snapshots.close("202610")
    with pytest.raises(ValueError, match="cerrado"):
        snapshots.generate("202610", recalculated.rows, replace_open=True)


@pytest.mark.parametrize("department,expected_zone", ZONES.items())
def test_all_official_departments_are_normalized_and_mapped(department, expected_zone):
    result = consolidate(operation(1, departamento=department.lower()))

    assert result.rows[0].dpto == department
    assert result.rows[0].zona == expected_zone


def test_department_normalization_handles_accents_spaces_and_unknown_values():
    assert normalize_department("  Huánuco  ") == "HUANUCO"

    result = consolidate(operation(1, departamento="Atlántida"))
    assert result.rows[0].dpto == "ATLANTIDA"
    assert result.rows[0].zona is None
    assert "unknown_zone" in {item.code for item in result.anomalies}


def test_demographics_only_use_the_selected_personas_batch_and_leave_missing_values_null():
    selected = PersonasPublication(
        44, "PERSONAS", "BASE_PERSONAS", "COMPLETADO", "SCOPE_REPLACE", datetime(2026, 10, 20, 16, 34, 16)
    )
    demographics = DemographicEnricher.for_selected_batch(
        selected,
        (
            PersonasSilverRecord(44, "30561135", date(1980, 2, 3), "F", "CASADA"),
            PersonasSilverRecord(34, "99999999", date(1970, 1, 1), "M", "CASADO"),
            PersonasSilverRecord(44, "77777777", None, "", ""),
        ),
    )
    result = consolidate(
        operation(1, documento="30561135"),
        operation(2, documento="99999999"),
        operation(3, documento="77777777"),
        demographics=demographics,
    )

    rows = {row.documento_cliente: row for row in result.rows}
    assert (rows["30561135"].fecha_nacimiento, rows["30561135"].sexo, rows["30561135"].estado_civil) == (
        date(1980, 2, 3), "F", "CASADA"
    )
    assert (rows["99999999"].fecha_nacimiento, rows["99999999"].sexo, rows["99999999"].estado_civil) == (None, None, None)
    assert (rows["77777777"].fecha_nacimiento, rows["77777777"].sexo, rows["77777777"].estado_civil) == (None, None, None)


def test_personas_selector_accepts_batch_44_and_never_selects_cancelled_or_error_batches():
    publications = [
        PersonasPublication(31, "PERSONAS", "BASE_PERSONAS", "COMPLETADO", "FULL_REPLACE", datetime(2026, 9, 1)),
        PersonasPublication(34, "PERSONAS", "BASE_PERSONAS", "COMPLETADO", "SCOPE_REPLACE", datetime(2026, 10, 1)),
        PersonasPublication(43, "PERSONAS", "BASE_PERSONAS", "CANCELADO", "FULL_REPLACE", datetime(2026, 10, 19)),
        PersonasPublication(44, "PERSONAS", "BASE_PERSONAS", "COMPLETADO", "SCOPE_REPLACE", datetime(2026, 10, 20, 16, 34, 16)),
        PersonasPublication(45, "PERSONAS", "BASE_PERSONAS", "ERROR", "SCOPE_REPLACE", datetime(2026, 10, 21)),
    ]

    assert PersonasBatchSelector.select_exact(publications, 44).batch_id == 44
    assert PersonasBatchSelector.select_latest(publications).batch_id == 44


def test_unknown_harvest_and_harvest_without_entity_are_not_published():
    result = consolidate(
        operation(1, cosecha="NO_EXISTE"),
        operation(2, cosecha="SEMBRANDO", entidad="SEMBRANDO"),
    )

    assert result.rows == ()
    assert {item.code for item in result.anomalies} == {"unknown_harvest", "harvest_without_entity"}


def test_reconciliation_matches_selected_original_operations_and_consolidated_rows():
    result = consolidate(
        operation(1, capital="10.50", deuda="15.00"),
        operation(2, capital="20.25", deuda="31.00"),
    )

    report = result.reconciliation[0]
    assert (report.operation_count, report.excluded_operation_count, report.document_count, report.client_count) == (2, 0, 1, 1)
    assert report.original_capital == report.consolidated_capital == Decimal("30.75")
    assert report.original_debt_total == report.consolidated_debt_total == Decimal("46.00")
    assert report.non_capital_components == Decimal("15.25")


def test_period_snapshots_are_idempotent_and_closed_history_is_immutable():
    row = MonthlyAssignmentRow(
        "BBVA1001", date(2020, 9, 30), "001", "ANA", 1, 1, None, None, "LIMA", "CENTRO",
        None, None, None, "SOLTERA", "KP INVEST", "BBVA", "BBVA1", Decimal("1"), Decimal("0"), Decimal("1"),
    )
    snapshots = InMemoryAssignmentSnapshots()

    first = snapshots.generate("202610", (row,))
    assert snapshots.generate("202610", (row,)) is first
    snapshots.close("202610")
    with pytest.raises(ValueError, match="cerrado"):
        snapshots.generate("202610", (row, replace(row, titular="OTRA")), replace_open=True)


def test_marital_status_refresh_is_limited_to_open_period_on_first_day():
    row = MonthlyAssignmentRow(
        "BBVA1001", date(2020, 9, 30), "001", "ANA", 1, 1, None, None, "LIMA", "CENTRO",
        None, date(1980, 1, 1), "F", "SOLTERA", "KP INVEST", "BBVA", "BBVA1", Decimal("1"), Decimal("0"), Decimal("1"),
    )
    snapshots = InMemoryAssignmentSnapshots()
    snapshots.generate("202611", (row,))
    refreshed = snapshots.refresh_marital_status("202611", {"001": "CASADA"}, refreshed_on=date(2026, 11, 1))
    assert refreshed.rows[0].fecha_nacimiento == date(1980, 1, 1)
    assert refreshed.rows[0].sexo == "F"
    assert refreshed.rows[0].estado_civil == "CASADA"
    with pytest.raises(ValueError, match="primer día"):
        snapshots.refresh_marital_status("202611", {"001": "DIVORCIADA"}, refreshed_on=date(2026, 11, 2))
    snapshots.close("202611")
    with pytest.raises(ValueError, match="cerrado"):
        snapshots.refresh_marital_status("202611", {"001": "DIVORCIADA"}, refreshed_on=date(2026, 12, 1))


def test_period_requires_month_not_harvest_code():
    assert validate_period("202612") == "202612"
    with pytest.raises(ValueError):
        validate_period("CAJAAQP3")


def test_versioned_sql_contains_exactly_the_official_harvest_and_zone_seed_counts():
    sql = (Path(__file__).parents[2] / "database/sql/059_create_monthly_assignment_foundation.sql").read_text(
        encoding="utf-8"
    )
    harvest_section = sql.split("INSERT INTO `kp_control`.`cartera_cosechas`", 1)[1].split(
        "INSERT INTO `kp_control`.`zonas_departamento`", 1
    )[0]
    zone_section = sql.split("INSERT INTO `kp_control`.`zonas_departamento`", 1)[1].split(
        "INSERT INTO `kp_control`.`asignacion_politicas_moneda`", 1
    )[0]

    assert harvest_section.count("UTC_TIMESTAMP(), UTC_TIMESTAMP())") == 30
    assert zone_section.count("UTC_TIMESTAMP(), UTC_TIMESTAMP())") == 25
    assert "('CAJAAQP3', 'CAJA_AREQUIPA', '2020-12-22', 'FONDO I'" in harvest_section
    assert "('WANDOO_1', 'WANDOO', '2026-04-10', 'KP INVEST'" in harvest_section
    assert "('SEMBRANDO', NULL, NULL, 'KP INVEST'" in harvest_section


def test_phase_1a_sql_adds_exchange_rate_audit_without_writing_bronze_or_silver():
    sql = (Path(__file__).parents[2] / "database/sql/059_create_monthly_assignment_foundation.sql").read_text(
        encoding="utf-8"
    ).upper()

    assert "CREATE TABLE `KP_CONTROL`.`TIPOS_CAMBIO`" in sql
    assert "DECIMAL(18,8)" in sql
    assert "CREATE TABLE `KP_GOLD`.`ASIGNACION_MENSUAL_CONCILIACION`" in sql
    assert "('WANDOO', 'WANDOO_1', 'PEN', 'CONFIRMACIÓN FUNCIONAL DEL NEGOCIO DEL 2026-10-26'" in sql
    assert "`IDENTIFICADOR_ORIGEN` VARCHAR(100)" in sql
    assert "ALTER TABLE `KP_SILVER`" not in sql
    assert "UPDATE `KP_SILVER`" not in sql
    assert "UPDATE `KP_BRONZE`" not in sql


def test_202610_reconciliation_script_is_read_only_and_does_not_expose_personal_fields():
    sql = (Path(__file__).parents[2] / "database/sql/060_assignment_202610_reconciliation_read_only.sql").read_text(
        encoding="utf-8"
    ).upper()

    assert not re.search(
        r"\b(?:CREATE|ALTER|DROP|TRUNCATE|INSERT|UPDATE|DELETE|REPLACE|CALL|GRANT|REVOKE|PROCEDURE)\b",
        sql,
    )
    assert "TELEFONO" not in sql
    assert "DIRECCION" not in sql
    assert "NOMBRE" not in sql
    assert "KP_GOLD" not in sql
    assert "ASIGNACION_PERIODOS" not in sql
    assert "ASIGNACION_POLITICAS_MONEDA" not in sql


def test_confianza_aliases_are_explicit_complete_and_sql_060_remains_preliminary():
    root = Path(__file__).parents[2]
    foundation_sql = (root / "database/sql/059_create_monthly_assignment_foundation.sql").read_text(
        encoding="utf-8"
    )
    reconciliation_sql = (root / "database/sql/060_assignment_202610_reconciliation_read_only.sql").read_text(
        encoding="utf-8"
    )

    for number in range(2, 13):
        source = f"CONFIANZA {number}"
        canonical = f"CONFIANZA_{number}"
        assert f"'{source}', '{canonical}'" in foundation_sql
        assert reconciliation_sql.count(f"'{source}' THEN '{canonical}'") == 6

    assert "('CONFIANZA_5', 'CONFIANZA', '2022-12-01', 'FONDO II'" in foundation_sql
    assert len(re.findall(r"^SELECT ", reconciliation_sql, re.MULTILINE)) == 7
    assert "No genera una fotografía oficial ni aplica un corte temporal" in reconciliation_sql


def test_strict_installation_sql_has_thirteen_tables_fk_traces_and_no_ignore_seed():
    sql = (Path(__file__).parents[2] / "database/sql/059_create_monthly_assignment_foundation.sql").read_text(
        encoding="utf-8"
    ).upper()

    assert len(re.findall(r"^CREATE TABLE ", sql, re.MULTILINE)) == 13
    assert "CREATE TABLE IF NOT EXISTS" not in sql
    assert "INSERT IGNORE" not in sql
    assert "START TRANSACTION;" in sql
    assert "COMMIT;" in sql
    assert "UNIQUE KEY `UQ_ASIGNACION_GENERACION_OFFICIAL_PERIODO` (`OFFICIAL_PERIODO`)" in sql
    assert "FOREIGN KEY (`ACTIVE_GENERATION_ID`, `PERIODO`)" in sql
    assert "REFERENCES `KP_GOLD`.`ASIGNACION_MENSUAL_GENERACIONES` (`GENERATION_ID`, `PERIODO`)" in sql
    assert len(re.findall(r"FOREIGN KEY", sql)) == 8
    assert len(re.findall(r"CREATE TRIGGER", sql)) == 2


@pytest.mark.parametrize(
    ("filename", "expected_selects"),
    (
            ("061_monthly_assignment_installation_preflight_read_only.sql", 12),
            ("062_verify_monthly_assignment_foundation_read_only.sql", 10),
            ("063_verify_monthly_assignment_draft_read_only.sql", 6),
    ),
)
def test_installation_verification_scripts_are_select_only(filename, expected_selects):
    sql = (Path(__file__).parents[2] / "database/sql" / filename).read_text(encoding="utf-8")
    sql_without_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    ).upper()

    assert len([statement for statement in sql_without_comments.split(";") if statement.strip()]) == expected_selects
    assert not re.search(
        r"\b(?:CREATE|ALTER|DROP|TRUNCATE|INSERT|UPDATE|DELETE|REPLACE|CALL|GRANT|REVOKE|PROCEDURE)\b",
        sql_without_comments,
    )

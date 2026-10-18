from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models import BatchRecord, CellValue, SearchSourceRow
from src.profiles.search.laboral_essalud import LaboralEssaludV1Normalizer
from src.profiles.search.sbs_detalle import SbsDetalleV1Normalizer
from src.profiles.search.sbs_resumen import SbsResumenV1Normalizer


def batch(dataset: str) -> BatchRecord:
    return BatchRecord(51, "SEARCH", "PENDIENTE", "source.xlsx", "imports/source.xlsx", "xlsx", None, perfil_version="1", dataset_code=dataset, source_code=f"BASE_{dataset}", refresh_mode="FULL_REPLACE", mapping_version=1)


def row(headers: tuple[str, ...], values: tuple[object, ...]) -> SearchSourceRow:
    cells = tuple(CellValue(value) for value in values)
    return SearchSourceRow(2, headers, cells, dict(zip(headers, cells, strict=True)))


SUMMARY_HEADERS = ("cod_sbs", "fecha_reporte_sbs", "documento", "cantidad_empresas", "calificacion_normal", "calificacion_cpp", "calificacion_deficiente", "calificacion_dudoso", "calificacion_perdida")
DETAIL_HEADERS = ("fecha_reporte_sbs", "documento", "cod_sbs", "entidad", "tipo_credito", "condicion", "monto", "dias_atraso")
ESSALUD_HEADERS = ("documento", "periodo", "ruc", "nombre_empresa", "sueldo", "situacion")


def test_sbs_summary_preserves_leading_code_and_accepts_percentage_tolerance():
    _, record, errors = SbsResumenV1Normalizer(100).normalize(row(SUMMARY_HEADERS, ("0012345678", "202607", "00002549", "2", "99.99", "0", "0", "0", "0")), batch("SBS_RESUMEN"), datetime(2026, 10, 16))

    assert errors == []
    assert record is not None
    assert record.cod_sbs == "0012345678"
    assert record.calificacion_normal == Decimal("99.9900")


@pytest.mark.parametrize("period", ["202613", "20260", "2026AA"])
def test_sbs_summary_rejects_invalid_period(period: str):
    _, record, errors = SbsResumenV1Normalizer(100).normalize(row(SUMMARY_HEADERS, ("0012345678", period, "00002549", "2", "100", None, None, None, None)), batch("SBS_RESUMEN"), datetime(2026, 10, 16))

    assert record is None
    assert errors[0].message == "PERIOD_INVALID"


def test_sbs_summary_rejects_percentage_total_outside_tolerance():
    _, record, errors = SbsResumenV1Normalizer(100).normalize(row(SUMMARY_HEADERS, ("0012345678", "202607", "00002549", "2", "98", "0", "0", "0", "0")), batch("SBS_RESUMEN"), datetime(2026, 10, 16))

    assert record is None
    assert errors[0].message == "SBS_PERCENTAGE_TOTAL_INVALID"


def test_sbs_detail_recovers_the_confirmed_shifted_columns_pattern():
    _, record, warnings = SbsDetalleV1Normalizer(100).normalize(row(DETAIL_HEADERS, ("202607", "00002549", "0176078057", "BANCO CENCOSUD S.A.", "PER", "15.8", "2678", None)), batch("SBS_DETALLE"), datetime(2026, 10, 16))

    assert record is not None
    assert record.tipo_credito is None
    assert record.condicion == "PER"
    assert record.monto == Decimal("15.80")
    assert record.dias_atraso == 2678
    assert warnings[0].message == "SBS_DETAIL_SHIFTED_COLUMNS_RECOVERED"


def test_sbs_detail_recovers_shifted_row_without_days_overdue():
    _, record, warnings = SbsDetalleV1Normalizer(100).normalize(row(DETAIL_HEADERS, ("202607", "00002549", "0176078057", "BANCO RIPLEY PERU S A", "NOR", "1000", None, None)), batch("SBS_DETALLE"), datetime(2026, 10, 16))

    assert record is not None
    assert record.condicion == "NOR"
    assert record.monto == Decimal("1000.00")
    assert record.dias_atraso is None
    assert warnings[0].message == "SBS_DETAIL_SHIFTED_COLUMNS_RECOVERED"


def test_sbs_detail_rejects_ambiguous_shift():
    _, record, errors = SbsDetalleV1Normalizer(100).normalize(row(DETAIL_HEADERS, ("202607", "00002549", "0176078057", "Entidad", "NOR", "texto", "2678", None)), batch("SBS_DETALLE"), datetime(2026, 10, 16))

    assert record is None
    assert errors[0].message == "SBS_DETAIL_COLUMN_SHIFT_AMBIGUOUS"


def test_essalud_preserves_open_situation_and_nullable_salary_and_company():
    _, record, errors = LaboralEssaludV1Normalizer(100).normalize(row(ESSALUD_HEADERS, ("00002549", "202607", "00123456789", None, None, "x")), batch("LABORAL_ESSALUD"), datetime(2026, 10, 16))

    assert errors == []
    assert record is not None
    assert record.nombre_empresa is None
    assert record.sueldo is None
    assert record.situacion == "X"


def test_essalud_rejects_negative_salary_and_invalid_ruc():
    _, record, errors = LaboralEssaludV1Normalizer(100).normalize(row(ESSALUD_HEADERS, ("00002549", "202607", "123", "Empresa", "-1", "A")), batch("LABORAL_ESSALUD"), datetime(2026, 10, 16))

    assert record is None
    assert {error.message for error in errors} == {"RUC_INVALID", "SALARY_INVALID"}


def test_financial_record_hash_is_deterministic():
    source = row(ESSALUD_HEADERS, ("00002549", "202607", "00123456789", "Empresa", "1000.50", "A"))
    normalizer = LaboralEssaludV1Normalizer(100)

    _, first, first_errors = normalizer.normalize(source, batch("LABORAL_ESSALUD"), datetime(2026, 10, 16))
    _, second, second_errors = normalizer.normalize(source, batch("LABORAL_ESSALUD"), datetime(2026, 10, 16))

    assert first_errors == second_errors == []
    assert first is not None and second is not None
    assert first.record_hash == second.record_hash

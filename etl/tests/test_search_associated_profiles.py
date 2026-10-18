from datetime import datetime

import pytest

from src.domain.models import BatchRecord, CellValue, SearchSourceRow
from src.profiles.search.correos import CorreosV1Normalizer
from src.profiles.search.direcciones import DireccionesV1Normalizer
from src.profiles.search.propiedades import PropiedadesV1Normalizer
from src.profiles.search.vehiculos import VehiculosV1Normalizer


def batch(dataset: str) -> BatchRecord:
    return BatchRecord(40, "SEARCH", "PENDIENTE", "source.xlsx", "imports/source.xlsx", "xlsx", None, perfil_version="1", dataset_code=dataset, source_code=f"BASE_{dataset}", refresh_mode="FULL_REPLACE", mapping_version=1)


def row(headers: tuple[str, ...], values: tuple[object, ...]) -> SearchSourceRow:
    cells = tuple(CellValue(value) for value in values)
    return SearchSourceRow(2, headers, cells, dict(zip(headers, cells, strict=True)))


def test_email_normalizes_and_rejects_placeholder():
    headers = ("documento", "correo_original")
    _, record, errors = CorreosV1Normalizer(100).normalize(row(headers, ("00001836", " Name@Example.COM ")), batch("CORREOS"), datetime(2026, 10, 15))
    assert errors == [] and record is not None
    assert record.correo == "name@example.com"
    _, record, errors = CorreosV1Normalizer(100).normalize(row(headers, ("00001836", "SINCORREO@SINCORREO.COM")), batch("CORREOS"), datetime(2026, 10, 15))
    assert record is None and errors[0].message == "EMAIL_INVALID"


def test_empty_address_is_not_an_error_or_publishable_record():
    headers = ("documento", "direccion", "departamento", "provincia", "distrito", "data_procedencia")
    _, record, errors = DireccionesV1Normalizer(100).normalize(row(headers, ("00001836", None, None, None, None, "RENIEC 2022")), batch("DIRECCIONES"), datetime(2026, 10, 15))
    assert record is None and errors == []


def test_vehicle_supports_missing_plate_and_historical_years():
    headers = ("documento", "nombre_completo_fuente", "clase", "anio_compra", "anio_fabricacion", "marca", "placa_original", "numero_transferencias")
    _, record, errors = VehiculosV1Normalizer(100).normalize(row(headers, ("08286093", "Persona", "AUTOMOVIL", "1967", "1965", "Marca", None, "3")), batch("VEHICULOS"), datetime(2026, 10, 15))
    assert errors == [] and record is not None
    assert record.placa is None and record.anio_compra == 1967 and record.numero_transferencias == 3


@pytest.mark.parametrize("partida", ["P02086269", "12345678"])
def test_property_preserves_alphanumeric_partida(partida: str):
    headers = ("documento", "partida_registral", "zona_registral", "oficina")
    _, record, errors = PropiedadesV1Normalizer(100).normalize(row(headers, ("09666686", partida, "Zona", "Lima")), batch("PROPIEDADES"), datetime(2026, 10, 15))
    assert errors == [] and record is not None and record.partida_registral == partida

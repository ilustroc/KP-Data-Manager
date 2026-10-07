from __future__ import annotations

import pytest

from src.domain.errors import StructuralFileError
from src.loaders.cartera_loader import CarteraLoader
from src.loaders.pagos_loader import PaymentLoader
from src.loaders.registry import LoaderRegistry

from .conftest import FakeCarteraDatabase, FakeDatabase, make_batch


def test_registry_keeps_payments_loader_unchanged(settings):
    database = FakeDatabase(make_batch())

    loader = LoaderRegistry().resolve(database.batch, database, settings)

    assert isinstance(loader, PaymentLoader)


def test_registry_routes_bbva_v1_portfolio(settings):
    database = FakeCarteraDatabase(
        make_batch(tipo="CARTERA", entidad="BBVA", perfil_version="1")
    )

    loader = LoaderRegistry().resolve(database.batch, database, settings)

    assert isinstance(loader, CarteraLoader)
    assert loader.profile.entity == "BBVA"
    assert loader.profile.version == "1"


def test_registry_routes_caja_arequipa_v1_portfolio(settings):
    database = FakeCarteraDatabase(
        make_batch(tipo="CARTERA", entidad="CAJA_AREQUIPA", perfil_version="1")
    )

    loader = LoaderRegistry().resolve(database.batch, database, settings)

    assert isinstance(loader, CarteraLoader)
    assert loader.profile.entity == "CAJA_AREQUIPA"
    assert loader.profile.version == "1"


def test_registry_rejects_portfolio_without_supported_profile(settings):
    database = FakeCarteraDatabase(
        make_batch(tipo="CARTERA", entidad="WANDOO", perfil_version="1")
    )

    with pytest.raises(StructuralFileError, match="perfil soportado"):
        LoaderRegistry().resolve(database.batch, database, settings)

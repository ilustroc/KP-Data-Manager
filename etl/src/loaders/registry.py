from __future__ import annotations

from typing import Callable, Protocol, cast

from ..config import Settings
from ..domain.errors import StructuralFileError
from ..domain.models import BatchRecord, CarteraDatabasePort, DatabasePort, SearchDatabasePort
from ..profiles.registry import ProfileRegistry
from .cartera_loader import CarteraLoader
from .pagos_loader import PaymentLoader
from .search_loader import SearchLoader


class BatchLoader(Protocol):
    def process(self, batch_id: int): ...


class LoaderRegistry:
    def __init__(self, profiles: ProfileRegistry | None = None) -> None:
        self.profiles = profiles or ProfileRegistry()

    def resolve(
        self,
        batch: BatchRecord,
        database: DatabasePort,
        settings: Settings,
    ) -> BatchLoader:
        factories: dict[str, Callable[[], BatchLoader]] = {
            "PAGOS": lambda: PaymentLoader(database, settings),
            "CARTERA": lambda: self._cartera_loader(batch, database, settings),
            "SEARCH": lambda: SearchLoader(cast(SearchDatabasePort, database), settings),
        }
        factory = factories.get(batch.tipo)
        if factory is None:
            raise StructuralFileError(f"Tipo de carga no soportado: {batch.tipo}.")
        return factory()

    def _cartera_loader(
        self,
        batch: BatchRecord,
        database: DatabasePort,
        settings: Settings,
    ) -> BatchLoader:
        profile = self.profiles.get_cartera(batch.entidad, batch.perfil_version)
        if profile is None:
            raise StructuralFileError("La entidad o versión de cartera no tiene un perfil soportado.")
        return CarteraLoader(cast(CarteraDatabasePort, database), settings, profile)

from __future__ import annotations

from .carteras.base import BaseCarteraProfile
from .carteras.bbva import BbvaV1Profile
from .carteras.caja_arequipa import CajaArequipaV1Profile
from .carteras.compartamos import CompartamosV1Profile
from .carteras.confianza import ConfianzaV1Profile


class ProfileRegistry:
    def __init__(self, profiles: tuple[BaseCarteraProfile, ...] | None = None) -> None:
        configured = profiles or (
            BbvaV1Profile(),
            CajaArequipaV1Profile(),
            CompartamosV1Profile(),
            ConfianzaV1Profile(),
        )
        self._profiles = {
            (profile.entity, profile.version): profile for profile in configured
        }

    def get_cartera(self, entity: str | None, version: str | None) -> BaseCarteraProfile | None:
        if entity is None or version is None:
            return None
        return self._profiles.get((entity, version))

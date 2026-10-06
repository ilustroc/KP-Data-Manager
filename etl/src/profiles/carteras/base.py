from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ...domain.errors import StructuralFileError
from ...domain.models import BbvaPortfolioRecord, RowError, SourceRow
from ...domain.normalizers import normalize_header


class BaseCarteraProfile(ABC):
    entity: str
    version: str
    expected_headers: tuple[str, ...]
    required_headers: frozenset[str]
    aliases: dict[str, str] = {}

    def build_header_map(self, header_values: Sequence[Any]) -> dict[str, int]:
        canonical_by_normalized = {
            normalize_header(header): header for header in self.expected_headers
        }
        canonical_by_normalized.update(
            {
                normalize_header(alias): canonical
                for alias, canonical in self.aliases.items()
            }
        )
        header_map: dict[str, int] = {}
        duplicates: set[str] = set()
        extras: set[str] = set()

        for index, value in enumerate(header_values):
            normalized = normalize_header(value)
            if not normalized:
                continue
            canonical = canonical_by_normalized.get(normalized)
            if canonical is None:
                extras.add(str(value).strip())
                continue
            if canonical in header_map:
                duplicates.add(canonical)
            header_map[canonical] = index

        if duplicates:
            raise StructuralFileError(
                f"Encabezados duplicados para {self.entity} v{self.version}: "
                + ", ".join(sorted(duplicates))
                + "."
            )

        missing = self.required_headers.difference(header_map)
        if missing:
            raise StructuralFileError(
                f"Faltan columnas obligatorias para {self.entity} v{self.version}: "
                + ", ".join(sorted(missing))
                + "."
            )

        if extras:
            raise StructuralFileError(
                f"Columnas no reconocidas para {self.entity} v{self.version}: "
                + ", ".join(sorted(extras))
                + "."
            )

        return {
            header: header_map[header]
            for header in self.expected_headers
            if header in header_map
        }

    @abstractmethod
    def normalize(
        self,
        row: SourceRow,
        *,
        batch_id: int,
        source_file: str,
        ingested_at: datetime,
        error_value_max_length: int,
    ) -> tuple[BbvaPortfolioRecord | None, list[RowError]]: ...

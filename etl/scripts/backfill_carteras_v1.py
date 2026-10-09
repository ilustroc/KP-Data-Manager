from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from collections.abc import Iterator, Sequence
from typing import Protocol, TypeVar

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from src.config import Settings
from src.domain.normalizers import normalize_phone, remove_all_whitespace

SUPPORTED_ENTITIES = ("BBVA", "CAJA_AREQUIPA")
SQL_BATCH_SIZE = 500
BatchValue = TypeVar("BatchValue")


@dataclass(frozen=True, slots=True)
class ContactRow:
    id: int
    operation_id: int
    entity: str
    phone: str | None
    order: int


@dataclass(frozen=True, slots=True)
class HarvestRow:
    id: int
    harvest: str | None


@dataclass(frozen=True, slots=True)
class ContactUpdate:
    id: int
    entity: str
    phone: str


@dataclass(frozen=True, slots=True)
class HarvestUpdate:
    id: int
    harvest: str | None


@dataclass(frozen=True, slots=True)
class EntitySummary:
    analyzed: int
    changed: int
    invalid: int
    duplicates: int
    estimated_final: int


@dataclass(frozen=True, slots=True)
class HarvestSummary:
    analyzed: int
    changed: int


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    phone_updates: tuple[ContactUpdate, ...]
    invalid_contact_ids: tuple[int, ...]
    duplicate_contact_ids: tuple[int, ...]
    harvest_updates: tuple[HarvestUpdate, ...]
    contact_summaries: dict[str, EntitySummary]
    harvest_summary: HarvestSummary


class BackfillRepository(Protocol):
    def begin(self) -> None: ...

    def fetch_contacts(self, *, for_update: bool) -> Sequence[ContactRow]: ...

    def fetch_harvests(self, *, for_update: bool) -> Sequence[HarvestRow]: ...

    def apply(self, plan: BackfillPlan) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


def build_backfill_plan(
    contacts: Sequence[ContactRow],
    harvests: Sequence[HarvestRow],
) -> BackfillPlan:
    phone_updates: list[ContactUpdate] = []
    invalid_ids: list[int] = []
    duplicate_ids: list[int] = []
    counters: dict[str, dict[str, int]] = {
        entity: {"analyzed": 0, "changed": 0, "invalid": 0, "duplicates": 0}
        for entity in SUPPORTED_ENTITIES
    }
    seen_by_operation: dict[int, set[str]] = defaultdict(set)

    ordered_contacts = sorted(
        (contact for contact in contacts if contact.entity in SUPPORTED_ENTITIES),
        key=lambda contact: (
            contact.entity,
            contact.operation_id,
            contact.order,
            contact.id,
        ),
    )
    for contact in ordered_contacts:
        entity_counters = counters[contact.entity]
        entity_counters["analyzed"] += 1
        normalized = normalize_phone(contact.phone)
        if normalized is None:
            invalid_ids.append(contact.id)
            entity_counters["invalid"] += 1
            continue
        if normalized in seen_by_operation[contact.operation_id]:
            duplicate_ids.append(contact.id)
            entity_counters["duplicates"] += 1
            continue
        seen_by_operation[contact.operation_id].add(normalized)
        if normalized != contact.phone:
            phone_updates.append(ContactUpdate(contact.id, contact.entity, normalized))
            entity_counters["changed"] += 1

    harvest_updates: list[HarvestUpdate] = []
    for harvest in harvests:
        normalized = remove_all_whitespace(harvest.harvest)
        if normalized != harvest.harvest:
            harvest_updates.append(HarvestUpdate(harvest.id, normalized))

    summaries = {
        entity: EntitySummary(
            analyzed=values["analyzed"],
            changed=values["changed"],
            invalid=values["invalid"],
            duplicates=values["duplicates"],
            estimated_final=(
                values["analyzed"] - values["invalid"] - values["duplicates"]
            ),
        )
        for entity, values in counters.items()
    }
    return BackfillPlan(
        phone_updates=tuple(phone_updates),
        invalid_contact_ids=tuple(invalid_ids),
        duplicate_contact_ids=tuple(duplicate_ids),
        harvest_updates=tuple(harvest_updates),
        contact_summaries=summaries,
        harvest_summary=HarvestSummary(
            analyzed=len(harvests),
            changed=len(harvest_updates),
        ),
    )


def run_backfill(repository: BackfillRepository, *, apply: bool) -> BackfillPlan:
    repository.begin()
    try:
        if apply:
            print("[1/4] Preparando contactos...", flush=True)
        harvests = repository.fetch_harvests(for_update=False)
        contacts = repository.fetch_contacts(for_update=apply)
        plan = build_backfill_plan(contacts, harvests)
        if apply:
            repository.apply(plan)
            repository.commit()
        else:
            repository.rollback()
        return plan
    except Exception:
        repository.rollback()
        raise


class MySqlBackfillRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection: Connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_username,
            password=settings.db_password,
            database=settings.silver_database,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=DictCursor,
            connect_timeout=15,
            read_timeout=120,
            write_timeout=120,
        )
        with self.connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")

    def begin(self) -> None:
        self.connection.begin()

    def fetch_contacts(self, *, for_update: bool) -> Sequence[ContactRow]:
        locking = " FOR UPDATE" if for_update else ""
        sql = f"""
            SELECT id, operacion_id, entidad, telefono, orden
            FROM `{self.settings.silver_database}`.`cartera_contactos`
            WHERE entidad IN (%s, %s)
            ORDER BY entidad ASC, operacion_id ASC, orden ASC, id ASC{locking}
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, SUPPORTED_ENTITIES)
            rows = cursor.fetchall()
        return tuple(
            ContactRow(
                id=int(row["id"]),
                operation_id=int(row["operacion_id"]),
                entity=str(row["entidad"]),
                phone=None if row["telefono"] is None else str(row["telefono"]),
                order=int(row["orden"]),
            )
            for row in rows
        )

    def fetch_harvests(self, *, for_update: bool) -> Sequence[HarvestRow]:
        locking = " FOR UPDATE" if for_update else ""
        sql = f"""
            SELECT id, cosecha
            FROM `{self.settings.silver_database}`.`cartera_operaciones`
            WHERE entidad = %s
            ORDER BY id ASC{locking}
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, ("CAJA_AREQUIPA",))
            rows = cursor.fetchall()
        return tuple(
            HarvestRow(
                id=int(row["id"]),
                harvest=None if row["cosecha"] is None else str(row["cosecha"]),
            )
            for row in rows
        )

    def apply(self, plan: BackfillPlan) -> None:
        with self.connection.cursor() as cursor:
            print("[2/4] Actualizando teléfonos...", flush=True)
            self._update_phones(cursor, plan.phone_updates)
            print("[3/4] Eliminando inválidos/duplicados...", flush=True)
            self._delete_contacts(cursor, plan.invalid_contact_ids)
            self._delete_contacts(cursor, plan.duplicate_contact_ids)
            print("[4/4] Normalizando cosechas...", flush=True)
            if plan.harvest_updates:
                self._normalize_caja_harvests(cursor)

    def _update_phones(
        self,
        cursor: DictCursor,
        updates: Sequence[ContactUpdate],
    ) -> None:
        for batch in _batches(updates, SQL_BATCH_SIZE):
            cases = " ".join("WHEN %s THEN %s" for _ in batch)
            ids = ", ".join("%s" for _ in batch)
            sql = f"""
                UPDATE `{self.settings.silver_database}`.`cartera_contactos`
                SET telefono = CASE id {cases} ELSE telefono END
                WHERE entidad IN (%s, %s)
                  AND id IN ({ids})
            """
            parameters: list[object] = []
            for update in batch:
                parameters.extend((update.id, update.phone))
            parameters.extend(SUPPORTED_ENTITIES)
            parameters.extend(update.id for update in batch)
            cursor.execute(sql, parameters)

    def _delete_contacts(
        self,
        cursor: DictCursor,
        contact_ids: Sequence[int],
    ) -> None:
        for batch in _batches(contact_ids, SQL_BATCH_SIZE):
            placeholders = ", ".join("%s" for _ in batch)
            sql = f"""
                DELETE FROM `{self.settings.silver_database}`.`cartera_contactos`
                WHERE entidad IN (%s, %s)
                  AND id IN ({placeholders})
            """
            cursor.execute(sql, (*SUPPORTED_ENTITIES, *batch))

    def _normalize_caja_harvests(self, cursor: DictCursor) -> None:
        normalized = """
            NULLIF(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(cosecha, ' ', ''),
                                    CHAR(9), ''
                                ),
                                CHAR(10), ''
                            ),
                            CHAR(11), ''
                        ),
                        CHAR(12), ''
                    ),
                    CHAR(13), ''
                ),
                ''
            )
        """
        sql = f"""
            UPDATE `{self.settings.silver_database}`.`cartera_operaciones`
            SET cosecha = {normalized}
            WHERE entidad = %s
              AND NOT (cosecha <=> {normalized})
        """
        cursor.execute(sql, ("CAJA_AREQUIPA",))

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def _batches(
    values: Sequence[BatchValue],
    size: int,
) -> Iterator[Sequence[BatchValue]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def print_summary(plan: BackfillPlan, *, applied: bool) -> None:
    mode = "APPLY" if applied else "DRY-RUN"
    print(f"Modo: {mode}")
    for entity in SUPPORTED_ENTITIES:
        summary = plan.contact_summaries[entity]
        print(f"{entity}:")
        print(f"  contactos analizados: {summary.analyzed}")
        if applied:
            print(f"  teléfonos modificados: {summary.changed}")
            print(f"  inválidos eliminados: {summary.invalid}")
            print(f"  duplicados eliminados: {summary.duplicates}")
            print(f"  filas finales: {summary.estimated_final}")
        else:
            print(f"  teléfonos que cambiarían: {summary.changed}")
            print(f"  inválidos que se eliminarían: {summary.invalid}")
            print(f"  duplicados que se eliminarían: {summary.duplicates}")
            print(f"  filas finales estimadas: {summary.estimated_final}")
    print("CAJA_AREQUIPA cosecha:")
    print(f"  operaciones analizadas: {plan.harvest_summary.analyzed}")
    if applied:
        print(f"  cosechas modificadas: {plan.harvest_summary.changed}")
    else:
        print(f"  cosechas que cambiarían: {plan.harvest_summary.changed}")


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normaliza teléfonos BBVA/Caja y cosechas Caja en Silver."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Solo calcula e informa cambios.")
    mode.add_argument("--apply", action="store_true", help="Aplica cambios en una transacción.")
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    settings = Settings.from_environment()
    repository = MySqlBackfillRepository(settings)
    try:
        plan = run_backfill(repository, apply=arguments.apply)
        print_summary(plan, applied=arguments.apply)
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

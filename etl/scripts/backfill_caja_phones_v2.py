from __future__ import annotations

import argparse
import re
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from src.config import Settings
from src.domain.normalizers import extract_phones, normalize_phone
from src.profiles.carteras.caja_arequipa import (
    extract_caja_contact_values,
    normalize_caja_guarantor_phone,
)

ENTITY = "CAJA_AREQUIPA"
SQL_BATCH_SIZE = 500
BatchValue = TypeVar("BatchValue")


@dataclass(frozen=True, slots=True)
class SourcePhoneRow:
    operation_id: int
    customer_document: str
    batch_id: int
    source_raw_id: int
    created_at: datetime
    holder_phone: str | None
    management_phone: str | None
    guarantor_phone: str | None


@dataclass(frozen=True, slots=True)
class CurrentContact:
    id: int
    operation_id: int
    customer_document: str
    entity: str
    phone: str
    contact_type: str | None
    prefix: str | None
    extension: str | None
    order: int
    batch_id: int
    source_raw_id: int


@dataclass(frozen=True, slots=True)
class ExpectedContact:
    operation_id: int
    customer_document: str
    phone: str
    contact_type: str
    order: int
    batch_id: int
    source_raw_id: int
    created_at: datetime

    def as_insert_tuple(self) -> tuple[object, ...]:
        return (
            self.operation_id,
            self.customer_document,
            ENTITY,
            self.phone,
            self.contact_type,
            None,
            None,
            self.order,
            self.batch_id,
            self.source_raw_id,
            self.created_at,
        )


@dataclass(frozen=True, slots=True)
class CurrentGuarantorPhone:
    id: int
    operation_id: int
    entity: str
    phone: str | None


@dataclass(frozen=True, slots=True)
class GuarantorPhoneUpdate:
    id: int
    phone: str | None


@dataclass(frozen=True, slots=True)
class ContactSummary:
    operations_analyzed: int
    current_contacts: int
    expected_contacts: int
    contacts_to_delete: int
    contacts_to_insert: int
    short_phones_found: int
    repetitive_phones_found: int
    historical_concatenations_found: int
    expected_final_rows: int


@dataclass(frozen=True, slots=True)
class GuarantorSummary:
    guarantors_analyzed: int
    phones_to_change: int


@dataclass(frozen=True, slots=True)
class CajaPhoneBackfillPlan:
    affected_operation_ids: tuple[int, ...]
    contacts_to_insert: tuple[ExpectedContact, ...]
    guarantor_updates: tuple[GuarantorPhoneUpdate, ...]
    contact_summary: ContactSummary
    guarantor_summary: GuarantorSummary


class CajaPhoneRepository(Protocol):
    def begin(self) -> None: ...

    def fetch_sources(
        self,
        *,
        batch_id: int | None,
        for_update: bool,
    ) -> Sequence[SourcePhoneRow]: ...

    def fetch_contacts(
        self,
        *,
        batch_id: int | None,
        for_update: bool,
    ) -> Sequence[CurrentContact]: ...

    def fetch_guarantors(
        self,
        *,
        batch_id: int | None,
        for_update: bool,
    ) -> Sequence[CurrentGuarantorPhone]: ...

    def apply(self, plan: CajaPhoneBackfillPlan) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


def build_backfill_plan(
    sources: Sequence[SourcePhoneRow],
    current_contacts: Sequence[CurrentContact],
    current_guarantors: Sequence[CurrentGuarantorPhone],
) -> CajaPhoneBackfillPlan:
    sources_by_operation = {source.operation_id: source for source in sources}
    if len(sources_by_operation) != len(sources):
        raise RuntimeError("Se encontraron operaciones Caja duplicadas en la fuente del backfill.")

    caja_contacts = [contact for contact in current_contacts if contact.entity == ENTITY]
    contacts_by_operation: dict[int, list[CurrentContact]] = defaultdict(list)
    for contact in caja_contacts:
        contacts_by_operation[contact.operation_id].append(contact)

    affected_operation_ids: list[int] = []
    contacts_to_insert: list[ExpectedContact] = []
    expected_contact_count = 0
    contacts_to_delete_count = 0
    short_phones_found = 0
    repetitive_phones_found = 0
    historical_concatenations_found = 0

    for source in sources:
        expected = _expected_contacts(source)
        expected_contact_count += len(expected)
        current = sorted(
            contacts_by_operation.get(source.operation_id, []),
            key=lambda contact: (contact.order, contact.id),
        )
        if _current_contact_signature(current) != _expected_contact_signature(expected):
            affected_operation_ids.append(source.operation_id)
            contacts_to_delete_count += len(current)
            contacts_to_insert.extend(expected)

        for source_value in (source.holder_phone, source.management_phone):
            short, repetitive, concatenated = _source_diagnostics(source_value, current)
            short_phones_found += short
            repetitive_phones_found += repetitive
            historical_concatenations_found += concatenated

    unexpected_operations = set(contacts_by_operation) - set(sources_by_operation)
    if unexpected_operations:
        raise RuntimeError(
            "Existen contactos Caja sin una operación Bronze correlacionable; no se aplicaron cambios."
        )

    guarantor_updates: list[GuarantorPhoneUpdate] = []
    caja_guarantors = [
        guarantor for guarantor in current_guarantors if guarantor.entity == ENTITY
    ]
    for guarantor in caja_guarantors:
        source = sources_by_operation.get(guarantor.operation_id)
        if source is None:
            raise RuntimeError(
                "Existe un aval Caja sin una operación Bronze correlacionable; no se aplicaron cambios."
            )
        expected_phone = normalize_caja_guarantor_phone(source.guarantor_phone)
        if expected_phone != guarantor.phone:
            guarantor_updates.append(GuarantorPhoneUpdate(guarantor.id, expected_phone))

    return CajaPhoneBackfillPlan(
        affected_operation_ids=tuple(affected_operation_ids),
        contacts_to_insert=tuple(contacts_to_insert),
        guarantor_updates=tuple(guarantor_updates),
        contact_summary=ContactSummary(
            operations_analyzed=len(sources),
            current_contacts=len(caja_contacts),
            expected_contacts=expected_contact_count,
            contacts_to_delete=contacts_to_delete_count,
            contacts_to_insert=len(contacts_to_insert),
            short_phones_found=short_phones_found,
            repetitive_phones_found=repetitive_phones_found,
            historical_concatenations_found=historical_concatenations_found,
            expected_final_rows=expected_contact_count,
        ),
        guarantor_summary=GuarantorSummary(
            guarantors_analyzed=len(caja_guarantors),
            phones_to_change=len(guarantor_updates),
        ),
    )


def run_backfill(
    repository: CajaPhoneRepository,
    *,
    apply: bool,
    batch_id: int | None = None,
) -> CajaPhoneBackfillPlan:
    repository.begin()
    try:
        sources = repository.fetch_sources(
            batch_id=batch_id,
            for_update=apply,
        )
        contacts = repository.fetch_contacts(
            batch_id=batch_id,
            for_update=apply,
        )
        guarantors = repository.fetch_guarantors(
            batch_id=batch_id,
            for_update=apply,
        )
        plan = build_backfill_plan(sources, contacts, guarantors)
        if apply:
            repository.apply(plan)
            repository.commit()
        else:
            repository.rollback()
        return plan
    except Exception:
        repository.rollback()
        raise


class MySqlCajaPhoneRepository:
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

    def fetch_sources(
        self,
        *,
        batch_id: int | None,
        for_update: bool,
    ) -> Sequence[SourcePhoneRow]:
        batch_filter = " AND batch_id = %s" if batch_id is not None else ""
        parameters: tuple[object, ...] = (ENTITY,) if batch_id is None else (ENTITY, batch_id)
        locking = " FOR UPDATE" if for_update else ""
        operation_sql = f"""
            SELECT id, documento_cliente, batch_id, source_raw_id, created_at
            FROM `{self.settings.silver_database}`.`cartera_operaciones`
            WHERE entidad = %s{batch_filter}
            ORDER BY id ASC{locking}
        """
        with self.connection.cursor() as cursor:
            cursor.execute(operation_sql, parameters)
            operation_rows = cursor.fetchall()

        source_sql = f"""
            SELECT o.id AS operation_id, r.raw_id, r.batch_id,
                   r.TEL_TIT, r.TEL_GES, r.TEL_AVAL
            FROM `{self.settings.silver_database}`.`cartera_operaciones` AS o
            INNER JOIN `{self.settings.bronze_database}`.`raw_cartera_caja_arequipa` AS r
                    ON r.raw_id = o.source_raw_id
                   AND r.batch_id = o.batch_id
            WHERE o.entidad = %s{(' AND o.batch_id = %s' if batch_id is not None else '')}
            ORDER BY o.id ASC
        """
        with self.connection.cursor() as cursor:
            cursor.execute(source_sql, parameters)
            source_rows = {int(row["operation_id"]): row for row in cursor.fetchall()}

        if len(source_rows) != len(operation_rows):
            raise RuntimeError(
                "No se pudieron correlacionar todas las operaciones Caja con Bronze."
            )

        return tuple(
            SourcePhoneRow(
                operation_id=int(operation["id"]),
                customer_document=str(operation["documento_cliente"]),
                batch_id=int(operation["batch_id"]),
                source_raw_id=int(operation["source_raw_id"]),
                created_at=operation["created_at"],
                holder_phone=_optional_string(source_rows[int(operation["id"])]["TEL_TIT"]),
                management_phone=_optional_string(
                    source_rows[int(operation["id"])]["TEL_GES"]
                ),
                guarantor_phone=_optional_string(
                    source_rows[int(operation["id"])]["TEL_AVAL"]
                ),
            )
            for operation in operation_rows
        )

    def fetch_contacts(
        self,
        *,
        batch_id: int | None,
        for_update: bool,
    ) -> Sequence[CurrentContact]:
        batch_filter = " AND batch_id = %s" if batch_id is not None else ""
        parameters: tuple[object, ...] = (ENTITY,) if batch_id is None else (ENTITY, batch_id)
        locking = " FOR UPDATE" if for_update else ""
        sql = f"""
            SELECT id, operacion_id, documento_cliente, entidad, telefono, tipo,
                   prefijo, extension, orden, batch_id, source_raw_id
            FROM `{self.settings.silver_database}`.`cartera_contactos`
            WHERE entidad = %s{batch_filter}
            ORDER BY operacion_id ASC, orden ASC, id ASC{locking}
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, parameters)
            rows = cursor.fetchall()
        return tuple(
            CurrentContact(
                id=int(row["id"]),
                operation_id=int(row["operacion_id"]),
                customer_document=str(row["documento_cliente"]),
                entity=str(row["entidad"]),
                phone=str(row["telefono"]),
                contact_type=_optional_string(row["tipo"]),
                prefix=_optional_string(row["prefijo"]),
                extension=_optional_string(row["extension"]),
                order=int(row["orden"]),
                batch_id=int(row["batch_id"]),
                source_raw_id=int(row["source_raw_id"]),
            )
            for row in rows
        )

    def fetch_guarantors(
        self,
        *,
        batch_id: int | None,
        for_update: bool,
    ) -> Sequence[CurrentGuarantorPhone]:
        batch_filter = " AND batch_id = %s" if batch_id is not None else ""
        parameters: tuple[object, ...] = (ENTITY,) if batch_id is None else (ENTITY, batch_id)
        locking = " FOR UPDATE" if for_update else ""
        sql = f"""
            SELECT id, operacion_id, entidad, telefono
            FROM `{self.settings.silver_database}`.`cartera_avales`
            WHERE entidad = %s{batch_filter}
            ORDER BY operacion_id ASC, orden ASC, id ASC{locking}
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, parameters)
            rows = cursor.fetchall()
        return tuple(
            CurrentGuarantorPhone(
                id=int(row["id"]),
                operation_id=int(row["operacion_id"]),
                entity=str(row["entidad"]),
                phone=_optional_string(row["telefono"]),
            )
            for row in rows
        )

    def apply(self, plan: CajaPhoneBackfillPlan) -> None:
        with self.connection.cursor() as cursor:
            print("[1/3] Eliminando contactos Caja desactualizados...", flush=True)
            self._delete_contacts(cursor, plan.affected_operation_ids)
            print("[2/3] Insertando contactos Caja reconstruidos...", flush=True)
            self._insert_contacts(cursor, plan.contacts_to_insert)
            print("[3/3] Actualizando teléfonos de aval...", flush=True)
            self._update_guarantor_phones(cursor, plan.guarantor_updates)

    def _delete_contacts(
        self,
        cursor: DictCursor,
        operation_ids: Sequence[int],
    ) -> None:
        for batch in _batches(operation_ids, SQL_BATCH_SIZE):
            placeholders = ", ".join("%s" for _ in batch)
            sql = f"""
                DELETE FROM `{self.settings.silver_database}`.`cartera_contactos`
                WHERE entidad = %s
                  AND operacion_id IN ({placeholders})
            """
            cursor.execute(sql, (ENTITY, *batch))

    def _insert_contacts(
        self,
        cursor: DictCursor,
        contacts: Sequence[ExpectedContact],
    ) -> None:
        sql = f"""
            INSERT INTO `{self.settings.silver_database}`.`cartera_contactos`
                (`operacion_id`, `documento_cliente`, `entidad`, `telefono`, `tipo`,
                 `prefijo`, `extension`, `orden`, `batch_id`, `source_raw_id`, `created_at`)
            VALUES ({", ".join(["%s"] * 11)})
        """
        for batch in _batches(contacts, SQL_BATCH_SIZE):
            cursor.executemany(sql, [contact.as_insert_tuple() for contact in batch])

    def _update_guarantor_phones(
        self,
        cursor: DictCursor,
        updates: Sequence[GuarantorPhoneUpdate],
    ) -> None:
        for batch in _batches(updates, SQL_BATCH_SIZE):
            cases = " ".join("WHEN %s THEN %s" for _ in batch)
            placeholders = ", ".join("%s" for _ in batch)
            sql = f"""
                UPDATE `{self.settings.silver_database}`.`cartera_avales`
                SET telefono = CASE id {cases} ELSE telefono END
                WHERE entidad = %s
                  AND id IN ({placeholders})
            """
            parameters: list[object] = []
            for update in batch:
                parameters.extend((update.id, update.phone))
            parameters.append(ENTITY)
            parameters.extend(update.id for update in batch)
            cursor.execute(sql, parameters)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def _expected_contacts(source: SourcePhoneRow) -> tuple[ExpectedContact, ...]:
    contacts: list[ExpectedContact] = []
    for order, (phone, contact_type) in enumerate(
        extract_caja_contact_values(source.holder_phone, source.management_phone),
        start=1,
    ):
        if len(phone) > 100:
            raise RuntimeError(
                f"La operación {source.operation_id} produce un teléfono mayor de 100 caracteres."
            )
        contacts.append(
            ExpectedContact(
                operation_id=source.operation_id,
                customer_document=source.customer_document,
                phone=phone,
                contact_type=contact_type,
                order=order,
                batch_id=source.batch_id,
                source_raw_id=source.source_raw_id,
                created_at=source.created_at,
            )
        )
    return tuple(contacts)


def _current_contact_signature(
    contacts: Sequence[CurrentContact],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            contact.customer_document,
            contact.phone,
            contact.contact_type,
            contact.prefix,
            contact.extension,
            contact.order,
            contact.batch_id,
            contact.source_raw_id,
        )
        for contact in contacts
    )


def _expected_contact_signature(
    contacts: Sequence[ExpectedContact],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            contact.customer_document,
            contact.phone,
            contact.contact_type,
            None,
            None,
            contact.order,
            contact.batch_id,
            contact.source_raw_id,
        )
        for contact in contacts
    )


def _source_diagnostics(
    value: str | None,
    current_contacts: Sequence[CurrentContact],
) -> tuple[int, int, int]:
    if value is None:
        return 0, 0, 0

    extracted = extract_phones(value)
    short = 0
    repetitive = 0
    for segment in re.split(r"[|/;\r\n]+", value):
        digit_groups = re.findall(r"[0-9]+", segment)
        has_standalone_mobile = any(normalize_phone(group) is not None for group in digit_groups)
        candidates = digit_groups if has_standalone_mobile else ["".join(digit_groups)]
        for candidate in candidates:
            canonical = candidate[2:] if len(candidate) == 11 and candidate.startswith("51") else candidate
            short += int(0 < len(canonical) < 9)
            repetitive += int(
                len(canonical) == 9
                and canonical.startswith("9")
                and len(set(canonical)) == 1
            )

    concatenated = 0
    for contact in current_contacts:
        if len(contact.phone) <= 9:
            continue
        found = False
        for start in range(len(extracted)):
            for end in range(start + 2, len(extracted) + 1):
                if contact.phone == "".join(extracted[start:end]):
                    concatenated += 1
                    found = True
                    break
            if found:
                break
    return short, repetitive, concatenated


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _batches(values: Sequence[BatchValue], size: int) -> Iterator[Sequence[BatchValue]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def print_summary(plan: CajaPhoneBackfillPlan, *, applied: bool) -> None:
    mode = "APPLY" if applied else "DRY-RUN"
    contacts = plan.contact_summary
    guarantors = plan.guarantor_summary
    print(f"Modo: {mode}")
    print("CAJA_AREQUIPA contactos:")
    print(f"  operaciones analizadas: {contacts.operations_analyzed}")
    print(f"  contactos actuales: {contacts.current_contacts}")
    print(f"  contactos esperados: {contacts.expected_contacts}")
    print(f"  contactos a eliminar: {contacts.contacts_to_delete}")
    print(f"  contactos a insertar: {contacts.contacts_to_insert}")
    print(f"  teléfonos menores de 9 encontrados: {contacts.short_phones_found}")
    print(f"  teléfonos repetitivos encontrados: {contacts.repetitive_phones_found}")
    print(
        "  concatenados históricos detectados: "
        f"{contacts.historical_concatenations_found}"
    )
    print(f"  filas finales esperadas: {contacts.expected_final_rows}")
    print("AVALES:")
    print(f"  registros analizados: {guarantors.guarantors_analyzed}")
    print(f"  teléfonos que cambiarían: {guarantors.phones_to_change}")


def _positive_batch_id(value: str) -> int:
    batch_id = int(value)
    if batch_id < 1:
        raise argparse.ArgumentTypeError("batch-id debe ser un entero positivo")
    return batch_id


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruye teléfonos históricos de Caja Arequipa desde Bronze."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Solo calcula e informa cambios.")
    mode.add_argument("--apply", action="store_true", help="Aplica cambios en una transacción.")
    parser.add_argument(
        "--batch-id",
        type=_positive_batch_id,
        help="Limita el mantenimiento a un batch Caja específico.",
    )
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    settings = Settings.from_environment()
    repository = MySqlCajaPhoneRepository(settings)
    try:
        plan = run_backfill(
            repository,
            apply=arguments.apply,
            batch_id=arguments.batch_id,
        )
        print_summary(plan, applied=arguments.apply)
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

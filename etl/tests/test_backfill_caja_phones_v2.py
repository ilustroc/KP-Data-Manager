from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from types import SimpleNamespace

import pytest

from scripts.backfill_caja_phones_v2 import (
    CajaPhoneBackfillPlan,
    ContactSummary,
    CurrentContact,
    CurrentGuarantorPhone,
    ExpectedContact,
    GuarantorPhoneUpdate,
    GuarantorSummary,
    MySqlCajaPhoneRepository,
    SourcePhoneRow,
    build_backfill_plan,
    parse_arguments,
    run_backfill,
)
from src.domain.normalizers import normalize_phone

FIXED_AT = datetime(2026, 10, 8, 18, 0, 0)


def source_row(
    *,
    operation_id: int = 10,
    operation: str = "OP-10",
    holder_phone: str | None = None,
    management_phone: str | None = None,
    guarantor_phone: str | None = None,
) -> SourcePhoneRow:
    return SourcePhoneRow(
        operation_id=operation_id,
        customer_document=f"DOC-{operation}",
        batch_id=44,
        source_raw_id=operation_id + 1000,
        created_at=FIXED_AT,
        holder_phone=holder_phone,
        management_phone=management_phone,
        guarantor_phone=guarantor_phone,
    )


def current_contact(
    source: SourcePhoneRow,
    phone: str,
    *,
    contact_id: int = 1,
    contact_type: str = "TITULAR",
    order: int = 1,
    entity: str = "CAJA_AREQUIPA",
) -> CurrentContact:
    return CurrentContact(
        id=contact_id,
        operation_id=source.operation_id,
        customer_document=source.customer_document,
        entity=entity,
        phone=phone,
        contact_type=contact_type,
        prefix=None,
        extension=None,
        order=order,
        batch_id=source.batch_id,
        source_raw_id=source.source_raw_id,
    )


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (
            "964712028/974218406|950955940",
            ("964712028", "974218406", "950955940"),
        ),
        ("953782316 -951159659", ("953782316", "951159659")),
        ("983579309-978106052-", ("983579309", "978106052")),
        ("962770294 949914817", ("962770294", "949914817")),
        ("#988181819-956006921", ("988181819", "956006921")),
        (
            "957867321  949925599|949925599",
            ("957867321", "949925599"),
        ),
        ("951546202 NU459387|951546202", ("951546202",)),
    ],
)
def test_plan_reconstructs_real_caja_phone_cells(
    raw_value: str,
    expected: tuple[str, ...],
) -> None:
    source = source_row(holder_phone=raw_value)
    historical_phone = re.sub(r"[^0-9]", "", raw_value)

    plan = build_backfill_plan(
        (source,),
        (current_contact(source, historical_phone),),
        (),
    )

    assert tuple(contact.phone for contact in plan.contacts_to_insert) == expected
    assert all(contact.contact_type == "TITULAR" for contact in plan.contacts_to_insert)
    assert tuple(contact.order for contact in plan.contacts_to_insert) == tuple(
        range(1, len(expected) + 1)
    )


def test_plan_filters_short_and_repetitive_groups_and_deduplicates_sources() -> None:
    source = source_row(
        holder_phone="987033819|123456|999999999|950066424|950066424",
        management_phone="950066424|951159659",
    )

    plan = build_backfill_plan((source,), (), ())

    assert [
        (contact.phone, contact.contact_type, contact.order)
        for contact in plan.contacts_to_insert
    ] == [
        ("987033819", "TITULAR", 1),
        ("950066424", "TITULAR", 2),
        ("951159659", "GESTION", 3),
    ]
    assert plan.contact_summary.short_phones_found == 1
    assert plan.contact_summary.repetitive_phones_found == 1


def test_plan_updates_only_guarantor_phone_with_ordered_unique_values() -> None:
    source = source_row(
        guarantor_phone="950948070|016733123|966011932|950948070|999999999"
    )
    guarantor = CurrentGuarantorPhone(
        id=80,
        operation_id=source.operation_id,
        entity="CAJA_AREQUIPA",
        phone="950948070966011932950948070",
    )

    plan = build_backfill_plan((source,), (), (guarantor,))

    assert plan.guarantor_updates == (
        GuarantorPhoneUpdate(80, "950948070|966011932"),
    )
    assert plan.guarantor_summary == GuarantorSummary(1, 1)


def test_non_caja_contacts_and_guarantors_are_not_planned_for_changes() -> None:
    source = source_row(holder_phone="987033819")
    bbva = current_contact(source, "1111111", entity="BBVA")
    compartamos = CurrentGuarantorPhone(90, source.operation_id, "COMPARTAMOS", "1111111")

    plan = build_backfill_plan((source,), (bbva,), (compartamos,))

    assert plan.contact_summary.current_contacts == 0
    assert plan.guarantor_summary == GuarantorSummary(0, 0)
    assert plan.contacts_to_insert[0].phone == "987033819"


class InMemoryRepository:
    def __init__(
        self,
        sources,
        contacts,
        guarantors,
        *,
        fail_during_apply: bool = False,
    ) -> None:
        self.sources = tuple(sources)
        self.contacts = {contact.id: contact for contact in contacts}
        self.guarantors = {guarantor.id: guarantor for guarantor in guarantors}
        self.fail_during_apply = fail_during_apply
        self.snapshot = None
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.next_contact_id = max(self.contacts, default=0) + 1

    def begin(self) -> None:
        self.snapshot = (deepcopy(self.contacts), deepcopy(self.guarantors))

    def fetch_sources(self, *, batch_id, for_update):
        return tuple(
            source
            for source in self.sources
            if batch_id is None or source.batch_id == batch_id
        )

    def fetch_contacts(self, *, batch_id, for_update):
        return tuple(
            contact
            for contact in self.contacts.values()
            if batch_id is None or contact.batch_id == batch_id
        )

    def fetch_guarantors(self, *, batch_id, for_update):
        return tuple(self.guarantors.values())

    def apply(self, plan: CajaPhoneBackfillPlan) -> None:
        affected = set(plan.affected_operation_ids)
        self.contacts = {
            contact_id: contact
            for contact_id, contact in self.contacts.items()
            if contact.entity != "CAJA_AREQUIPA" or contact.operation_id not in affected
        }
        for expected in plan.contacts_to_insert:
            self.contacts[self.next_contact_id] = CurrentContact(
                id=self.next_contact_id,
                operation_id=expected.operation_id,
                customer_document=expected.customer_document,
                entity="CAJA_AREQUIPA",
                phone=expected.phone,
                contact_type=expected.contact_type,
                prefix=None,
                extension=None,
                order=expected.order,
                batch_id=expected.batch_id,
                source_raw_id=expected.source_raw_id,
            )
            self.next_contact_id += 1
        for update in plan.guarantor_updates:
            current = self.guarantors[update.id]
            self.guarantors[update.id] = CurrentGuarantorPhone(
                current.id,
                current.operation_id,
                current.entity,
                update.phone,
            )
        if self.fail_during_apply:
            raise RuntimeError("simulated apply failure")

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
        if self.snapshot is not None:
            self.contacts, self.guarantors = deepcopy(self.snapshot)

    def close(self) -> None:
        self.closed = True


def test_apply_is_idempotent_and_never_changes_bronze_source_values() -> None:
    source = source_row(
        holder_phone="964712028/974218406|950955940",
        guarantor_phone="950948070|966011932",
    )
    historical = current_contact(source, "964712028974218406950955940")
    bbva_contact = current_contact(
        source,
        "900111222",
        contact_id=2,
        entity="BBVA",
    )
    compartamos_contact = current_contact(
        source,
        "900333444",
        contact_id=3,
        entity="COMPARTAMOS",
    )
    guarantor = CurrentGuarantorPhone(
        80,
        source.operation_id,
        "CAJA_AREQUIPA",
        "950948070966011932",
    )
    repository = InMemoryRepository(
        (source,),
        (historical, bbva_contact, compartamos_contact),
        (guarantor,),
    )
    bronze_before = deepcopy(repository.sources)

    first = run_backfill(repository, apply=True)
    second = run_backfill(repository, apply=False)

    assert repository.committed
    assert first.contact_summary.contacts_to_delete == 1
    assert first.contact_summary.contacts_to_insert == 3
    assert first.guarantor_summary.phones_to_change == 1
    assert second.contact_summary.contacts_to_delete == 0
    assert second.contact_summary.contacts_to_insert == 0
    assert second.guarantor_summary.phones_to_change == 0
    assert repository.sources == bronze_before
    assert repository.contacts[2] == bbva_contact
    assert repository.contacts[3] == compartamos_contact


def test_apply_rolls_back_contacts_and_guarantors_after_failure() -> None:
    source = source_row(holder_phone="953782316 -951159659")
    historical = current_contact(source, "953782316951159659")
    guarantor = CurrentGuarantorPhone(
        80,
        source.operation_id,
        "CAJA_AREQUIPA",
        "950948070",
    )
    repository = InMemoryRepository(
        (source,),
        (historical,),
        (guarantor,),
        fail_during_apply=True,
    )
    contacts_before = deepcopy(repository.contacts)
    guarantors_before = deepcopy(repository.guarantors)

    with pytest.raises(RuntimeError, match="simulated apply failure"):
        run_backfill(repository, apply=True)

    assert repository.rolled_back
    assert not repository.committed
    assert repository.contacts == contacts_before
    assert repository.guarantors == guarantors_before


class RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, object, bool]] = []

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback) -> None:
        return None

    def execute(self, sql: str, parameters=None) -> None:
        self.statements.append((" ".join(sql.split()), parameters, False))

    def executemany(self, sql: str, parameters) -> None:
        self.statements.append((" ".join(sql.split()), tuple(parameters), True))


class RecordingConnection:
    def __init__(self) -> None:
        self.cursor_instance = RecordingCursor()

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance


class SourceRecordingCursor(RecordingCursor):
    def __init__(self) -> None:
        super().__init__()
        self.last_sql = ""

    def execute(self, sql: str, parameters=None) -> None:
        self.last_sql = " ".join(sql.split())
        super().execute(sql, parameters)

    def fetchall(self):
        if "INNER JOIN `kp_bronze`.`raw_cartera_caja_arequipa`" in self.last_sql:
            return (
                {
                    "operation_id": 10,
                    "raw_id": 1010,
                    "batch_id": 44,
                    "TEL_TIT": "987033819",
                    "TEL_GES": None,
                    "TEL_AVAL": "950948070",
                },
            )
        return (
            {
                "id": 10,
                "documento_cliente": "DOC-10",
                "batch_id": 44,
                "source_raw_id": 1010,
                "created_at": FIXED_AT,
            },
        )


class SourceRecordingConnection:
    def __init__(self) -> None:
        self.cursor_instance = SourceRecordingCursor()

    def cursor(self) -> SourceRecordingCursor:
        return self.cursor_instance


def test_mysql_source_read_relates_by_raw_and_batch_without_writing_bronze() -> None:
    repository = MySqlCajaPhoneRepository.__new__(MySqlCajaPhoneRepository)
    repository.settings = SimpleNamespace(
        silver_database="kp_silver",
        bronze_database="kp_bronze",
    )
    repository.connection = SourceRecordingConnection()

    sources = repository.fetch_sources(batch_id=44, for_update=True)

    assert len(sources) == 1
    assert sources[0].source_raw_id == 1010
    statements = repository.connection.cursor_instance.statements
    operation_sql = statements[0][0]
    bronze_sql = statements[1][0]
    assert operation_sql.startswith("SELECT") and operation_sql.endswith("FOR UPDATE")
    assert bronze_sql.startswith("SELECT")
    assert "r.raw_id = o.source_raw_id" in bronze_sql
    assert "r.batch_id = o.batch_id" in bronze_sql
    assert "FOR UPDATE" not in bronze_sql
    assert not any(
        bronze_sql.startswith(command)
        for command in ("INSERT", "UPDATE", "DELETE", "REPLACE")
    )


def test_mysql_apply_batches_writes_and_never_targets_bronze_or_other_entities() -> None:
    repository = MySqlCajaPhoneRepository.__new__(MySqlCajaPhoneRepository)
    repository.settings = SimpleNamespace(silver_database="kp_silver")
    repository.connection = RecordingConnection()
    contacts = tuple(
        ExpectedContact(
            operation_id=operation_id,
            customer_document=f"DOC-{operation_id}",
            phone=f"9{operation_id:08d}",
            contact_type="TITULAR",
            order=1,
            batch_id=44,
            source_raw_id=operation_id + 1000,
            created_at=FIXED_AT,
        )
        for operation_id in range(1, 1_202)
    )
    plan = CajaPhoneBackfillPlan(
        affected_operation_ids=tuple(range(1, 1_202)),
        contacts_to_insert=contacts,
        guarantor_updates=tuple(
            GuarantorPhoneUpdate(guarantor_id, f"9{guarantor_id:08d}")
            for guarantor_id in range(1, 1_202)
        ),
        contact_summary=ContactSummary(0, 0, 0, 0, 0, 0, 0, 0, 0),
        guarantor_summary=GuarantorSummary(0, 0),
    )

    repository.apply(plan)

    statements = repository.connection.cursor_instance.statements
    assert len(statements) == 9
    assert sum(sql.startswith("DELETE") for sql, _, _ in statements) == 3
    assert sum(sql.startswith("INSERT") for sql, _, _ in statements) == 3
    assert sum(sql.startswith("UPDATE") for sql, _, _ in statements) == 3
    assert all("kp_bronze" not in sql for sql, _, _ in statements)
    assert all("entidad = %s" in sql for sql, _, _ in statements if not sql.startswith("INSERT"))
    assert all("BBVA" not in str(parameters) for _, parameters, _ in statements)
    assert all("COMPARTAMOS" not in str(parameters) for _, parameters, _ in statements)


@pytest.mark.parametrize(
    ("arguments", "apply", "batch_id"),
    [
        ([], False, None),
        (["--dry-run"], False, None),
        (["--apply"], True, None),
        (["--apply", "--batch-id", "44"], True, 44),
    ],
)
def test_cli_is_dry_run_by_default_and_accepts_optional_batch_scope(
    arguments: list[str],
    apply: bool,
    batch_id: int | None,
) -> None:
    parsed = parse_arguments(arguments)

    assert parsed.apply is apply
    assert parsed.batch_id == batch_id

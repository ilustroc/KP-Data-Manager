from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts.backfill_carteras_v1 import (
    BackfillPlan,
    ContactRow,
    ContactUpdate,
    EntitySummary,
    HarvestSummary,
    HarvestRow,
    HarvestUpdate,
    MySqlBackfillRepository,
    build_backfill_plan,
    parse_arguments,
    run_backfill,
)


class InMemoryRepository:
    def __init__(self, contacts, operations, *, fail_during_apply: bool = False) -> None:
        self.contacts = {contact.id: contact for contact in contacts}
        self.operations = {
            operation[0]: {"entity": operation[1], "harvest": operation[2]}
            for operation in operations
        }
        self.fail_during_apply = fail_during_apply
        self.snapshot = None
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.actions: list[str] = []
        self.contact_lock_requests: list[bool] = []
        self.harvest_lock_requests: list[bool] = []

    def begin(self) -> None:
        self.snapshot = (deepcopy(self.contacts), deepcopy(self.operations))

    def fetch_contacts(self, *, for_update: bool):
        self.contact_lock_requests.append(for_update)
        return tuple(
            contact
            for contact in self.contacts.values()
            if contact.entity in {"BBVA", "CAJA_AREQUIPA"}
        )

    def fetch_harvests(self, *, for_update: bool):
        self.harvest_lock_requests.append(for_update)
        return tuple(
            HarvestRow(operation_id, values["harvest"])
            for operation_id, values in self.operations.items()
            if values["entity"] == "CAJA_AREQUIPA"
        )

    def apply(self, plan: BackfillPlan) -> None:
        self.actions.append("update_phones")
        for update in plan.phone_updates:
            current = self.contacts[update.id]
            self.contacts[update.id] = ContactRow(
                current.id,
                current.operation_id,
                current.entity,
                update.phone,
                current.order,
            )
        if self.fail_during_apply:
            raise RuntimeError("simulated apply failure")

        self.actions.append("delete_invalid")
        for contact_id in plan.invalid_contact_ids:
            self.contacts.pop(contact_id)
        self.actions.append("delete_duplicates")
        for contact_id in plan.duplicate_contact_ids:
            self.contacts.pop(contact_id)
        self.actions.append("update_harvests")
        for update in plan.harvest_updates:
            self.operations[update.id]["harvest"] = update.harvest

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
        if self.snapshot is not None:
            self.contacts, self.operations = deepcopy(self.snapshot)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("arguments", "apply"),
    [([], False), (["--dry-run"], False), (["--apply"], True)],
)
def test_cli_is_dry_run_by_default_and_requires_explicit_apply(arguments, apply: bool):
    assert parse_arguments(arguments).apply is apply


@pytest.mark.parametrize(
    ("raw_phone", "normalized"),
    [
        ("+51912631273", "912631273"),
        ("#952999016", "952999016"),
        ("934043966.", "934043966"),
        ('"934043966"', "934043966"),
        ("51 934 043 966", "934043966"),
    ],
)
def test_plan_reuses_phone_normalization_for_bbva_and_caja(raw_phone: str, normalized: str):
    contacts = (
        ContactRow(1, 10, "BBVA", raw_phone, 1),
        ContactRow(2, 20, "CAJA_AREQUIPA", raw_phone, 1),
    )

    plan = build_backfill_plan(contacts, ())

    assert [(update.id, update.phone) for update in plan.phone_updates] == [
        (1, normalized),
        (2, normalized),
    ]


@pytest.mark.parametrize(
    "raw_phone",
    ["3815686", "016733123", "123456789", "93404396", "999999999"],
)
def test_plan_removes_values_that_are_not_peruvian_mobile_phones(raw_phone: str):
    contacts = (
        ContactRow(1, 10, "BBVA", raw_phone, 1),
        ContactRow(2, 20, "CAJA_AREQUIPA", raw_phone, 1),
    )

    plan = build_backfill_plan(contacts, ())

    assert plan.invalid_contact_ids == (1, 2)
    assert plan.phone_updates == ()


def test_invalid_duplicate_and_first_appearance_are_resolved_per_operation():
    contacts = (
        ContactRow(4, 10, "BBVA", "952999016.", 3),
        ContactRow(3, 10, "BBVA", "952 999 016", 2),
        ContactRow(2, 10, "BBVA", "#952999016", 2),
        ContactRow(1, 10, "BBVA", "999999999", 1),
        ContactRow(5, 11, "BBVA", "952999016", 1),
    )

    plan = build_backfill_plan(contacts, ())

    assert plan.invalid_contact_ids == (1,)
    assert plan.duplicate_contact_ids == (3, 4)
    assert [(update.id, update.phone) for update in plan.phone_updates] == [
        (2, "952999016")
    ]
    assert 5 not in plan.invalid_contact_ids
    assert 5 not in plan.duplicate_contact_ids
    assert plan.contact_summaries["BBVA"].estimated_final == 2


def test_compartamos_contacts_are_never_planned_for_change_or_deletion():
    contacts = (
        ContactRow(1, 10, "COMPARTAMOS", "#900111222", 1),
        ContactRow(2, 10, "COMPARTAMOS", "999999999", 2),
    )

    plan = build_backfill_plan(contacts, ())

    assert plan.phone_updates == ()
    assert plan.invalid_contact_ids == ()
    assert plan.duplicate_contact_ids == ()
    assert all(summary.analyzed == 0 for summary in plan.contact_summaries.values())


def test_caja_harvest_removes_all_whitespace():
    plan = build_backfill_plan(
        (),
        (
            HarvestRow(1, "CAJA AQP2"),
            HarvestRow(2, " CAJA AQP3 "),
            HarvestRow(3, "CAJAAQP4"),
        ),
    )

    assert [(update.id, update.harvest) for update in plan.harvest_updates] == [
        (1, "CAJAAQP2"),
        (2, "CAJAAQP3"),
    ]
    assert plan.harvest_summary.analyzed == 3
    assert plan.harvest_summary.changed == 2


def test_apply_is_transactional_ordered_and_idempotent():
    repository = InMemoryRepository(
        contacts=(
            ContactRow(1, 10, "BBVA", "#952999016", 1),
            ContactRow(2, 10, "BBVA", "952 999 016", 2),
            ContactRow(3, 11, "CAJA_AREQUIPA", "999999999", 1),
            ContactRow(4, 12, "COMPARTAMOS", "#900111222", 1),
        ),
        operations=(
            (100, "CAJA_AREQUIPA", "CAJA AQP2"),
            (101, "BBVA", "BBVA 1"),
            (102, "COMPARTAMOS", "COMP 1"),
        ),
    )

    first = run_backfill(repository, apply=True)
    second = run_backfill(repository, apply=True)

    assert repository.committed
    assert first.contact_summaries["BBVA"].changed == 1
    assert first.contact_summaries["BBVA"].duplicates == 1
    assert first.contact_summaries["CAJA_AREQUIPA"].invalid == 1
    assert first.harvest_summary.changed == 1
    assert repository.contacts[1].phone == "952999016"
    assert 2 not in repository.contacts and 3 not in repository.contacts
    assert repository.contacts[4].phone == "#900111222"
    assert repository.operations[100]["harvest"] == "CAJAAQP2"
    assert repository.operations[101]["harvest"] == "BBVA 1"
    assert repository.operations[102]["harvest"] == "COMP 1"
    assert repository.actions[:4] == [
        "update_phones",
        "delete_invalid",
        "delete_duplicates",
        "update_harvests",
    ]
    assert sum(summary.changed for summary in second.contact_summaries.values()) == 0
    assert sum(summary.invalid for summary in second.contact_summaries.values()) == 0
    assert sum(summary.duplicates for summary in second.contact_summaries.values()) == 0
    assert second.harvest_summary.changed == 0
    assert repository.contact_lock_requests == [True, True]
    assert repository.harvest_lock_requests == [False, False]


def test_dry_run_rolls_back_without_modifying_state():
    repository = InMemoryRepository(
        contacts=(ContactRow(1, 10, "BBVA", "#952999016", 1),),
        operations=((100, "CAJA_AREQUIPA", "CAJA AQP2"),),
    )
    original_contacts = deepcopy(repository.contacts)
    original_operations = deepcopy(repository.operations)

    plan = run_backfill(repository, apply=False)

    assert plan.contact_summaries["BBVA"].changed == 1
    assert plan.harvest_summary.changed == 1
    assert repository.rolled_back
    assert not repository.committed
    assert repository.contacts == original_contacts
    assert repository.operations == original_operations


class RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback) -> None:
        return None

    def execute(self, sql: str, parameters=None) -> None:
        self.statements.append((" ".join(sql.split()), parameters))


class RecordingConnection:
    def __init__(self) -> None:
        self.cursor_instance = RecordingCursor()

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance


def test_mysql_apply_groups_contact_writes_and_uses_one_set_based_harvest_update(
    capsys,
):
    repository = MySqlBackfillRepository.__new__(MySqlBackfillRepository)
    repository.settings = SimpleNamespace(silver_database="kp_silver")
    repository.connection = RecordingConnection()
    empty_summary = EntitySummary(0, 0, 0, 0, 0)
    plan = BackfillPlan(
        phone_updates=tuple(
            ContactUpdate(contact_id, "CAJA_AREQUIPA", f"900{contact_id:06d}")
            for contact_id in range(1, 271)
        ),
        invalid_contact_ids=tuple(range(1001, 1082)),
        duplicate_contact_ids=tuple(range(2001, 2116)),
        harvest_updates=tuple(
            HarvestUpdate(operation_id, "CAJAAQP3")
            for operation_id in range(1, 31_318)
        ),
        contact_summaries={
            "BBVA": empty_summary,
            "CAJA_AREQUIPA": empty_summary,
        },
        harvest_summary=HarvestSummary(31_317, 31_317),
    )

    repository.apply(plan)

    statements = repository.connection.cursor_instance.statements
    assert len(statements) == 4
    assert sum("UPDATE `kp_silver`.`cartera_contactos`" in sql for sql, _ in statements) == 1
    assert sum("DELETE FROM `kp_silver`.`cartera_contactos`" in sql for sql, _ in statements) == 2
    harvest_statements = [
        sql
        for sql, _ in statements
        if "UPDATE `kp_silver`.`cartera_operaciones`" in sql
    ]
    assert len(harvest_statements) == 1
    assert "SET cosecha = NULLIF(" in harvest_statements[0]
    assert "REPLACE(" in harvest_statements[0]
    assert "CHAR(9)" in harvest_statements[0]
    assert "CHAR(10)" in harvest_statements[0]
    assert "CHAR(13)" in harvest_statements[0]
    assert "WHERE entidad = %s" in harvest_statements[0]
    assert "raw_" not in " ".join(sql for sql, _ in statements).lower()
    assert "bronze" not in " ".join(sql for sql, _ in statements).lower()
    assert "COMPARTAMOS" not in str(statements)
    output = capsys.readouterr().out
    assert "[2/4] Actualizando teléfonos..." in output
    assert "[4/4] Normalizando cosechas..." in output


def test_mysql_contact_writes_scale_by_batch_instead_of_by_row():
    repository = MySqlBackfillRepository.__new__(MySqlBackfillRepository)
    repository.settings = SimpleNamespace(silver_database="kp_silver")
    repository.connection = RecordingConnection()
    empty_summary = EntitySummary(0, 0, 0, 0, 0)
    plan = BackfillPlan(
        phone_updates=tuple(
            ContactUpdate(contact_id, "BBVA", f"900{contact_id:06d}")
            for contact_id in range(1, 1_202)
        ),
        invalid_contact_ids=tuple(range(2_001, 3_202)),
        duplicate_contact_ids=(),
        harvest_updates=(),
        contact_summaries={
            "BBVA": empty_summary,
            "CAJA_AREQUIPA": empty_summary,
        },
        harvest_summary=HarvestSummary(0, 0),
    )

    repository.apply(plan)

    statements = repository.connection.cursor_instance.statements
    phone_updates = [sql for sql, _ in statements if sql.startswith("UPDATE")]
    contact_deletes = [sql for sql, _ in statements if sql.startswith("DELETE")]
    assert len(phone_updates) == 3
    assert len(contact_deletes) == 3


def test_apply_rolls_back_every_change_when_an_exception_occurs():
    repository = InMemoryRepository(
        contacts=(ContactRow(1, 10, "BBVA", "#952999016", 1),),
        operations=((100, "CAJA_AREQUIPA", "CAJA AQP2"),),
        fail_during_apply=True,
    )
    original_contacts = deepcopy(repository.contacts)
    original_operations = deepcopy(repository.operations)

    with pytest.raises(RuntimeError, match="simulated apply failure"):
        run_backfill(repository, apply=True)

    assert repository.rolled_back
    assert not repository.committed
    assert repository.contacts == original_contacts
    assert repository.operations == original_operations

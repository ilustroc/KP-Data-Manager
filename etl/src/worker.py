from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

import pymysql

from .config import Settings
from .db import MySqlDatabase
from .domain.errors import BatchNotFoundError
from .domain.errors import EtlError
from .domain.errors import SearchRecoveryError
from .loaders.registry import LoaderRegistry


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def positive_batch_id(value: str) -> int:
    try:
        batch_id = int(value)
    except ValueError as exception:
        raise argparse.ArgumentTypeError("batch-id debe ser entero") from exception
    if batch_id < 1:
        raise argparse.ArgumentTypeError("batch-id debe ser mayor que cero")
    return batch_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Procesa una carga SEARCH soportada.")
    parser.add_argument("--batch-id", required=True, type=positive_batch_id)
    parser.add_argument("--publish-only", action="store_true")
    arguments = parser.parse_args(argv)

    database: MySqlDatabase | None = None
    stage = "worker"
    exit_code = 1
    configure_logging("INFO")
    try:
        settings = Settings.from_environment()
        configure_logging(settings.log_level)
        if arguments.publish_only:
            stage = "recovery_connection"
        database = MySqlDatabase(settings)
        if arguments.publish_only:
            stage = "recovery_preflight"
        batch = database.get_batch(arguments.batch_id)
        if batch is None:
            raise BatchNotFoundError(f"No existe el batch #{arguments.batch_id}.")
        loader = LoaderRegistry().resolve(batch, database, settings)
        if arguments.publish_only:
            if not hasattr(loader, "recover_publish"):
                raise BatchNotFoundError("El batch no admite recuperación SEARCH.")
            result = loader.recover_publish(arguments.batch_id)
            stage = "search_gold_finalize"
        else:
            result = loader.process(arguments.batch_id)
        logging.getLogger("kpdm.etl").info(
            "worker_completed",
            extra={
                "context": {
                    "batch_id": result.batch_id,
                    "estado": result.status,
                    "filas_procesadas": result.stats.file_rows,
                    "filas_insertadas": result.stats.inserted_rows,
                    "filas_error": result.stats.error_rows,
                }
            },
        )
        exit_code = 0
    except SearchRecoveryError as exception:
        cause = exception.cause
        logging.getLogger("kpdm.etl").error(
            "worker_crashed",
            extra={
                "context": {
                    "batch_id": arguments.batch_id,
                    "stage": exception.stage,
                    "error_type": type(cause).__name__,
                    **safe_diagnostic(cause, database),
                }
            },
        )
    except EtlError as exception:
        logging.getLogger("kpdm.etl").error(
            "worker_rejected",
            extra={
                "context": {
                    "batch_id": arguments.batch_id,
                    "stage": stage,
                    "error_type": type(exception).__name__,
                    **safe_diagnostic(exception, database),
                }
            },
        )
    except Exception as exception:
        logging.getLogger("kpdm.etl").error(
            "worker_crashed",
            extra={
                "context": {
                    "batch_id": arguments.batch_id,
                    "stage": stage,
                    "error_type": type(exception).__name__,
                    **safe_diagnostic(exception, database),
                }
            },
        )
    finally:
        if database is not None:
            closed = database.close()
            if not closed:
                logging.getLogger("kpdm.etl").error(
                    "worker_connection_cleanup_failed",
                    extra={
                        "context": {
                            "batch_id": arguments.batch_id,
                            "stage": "recovery_connection_close"
                            if arguments.publish_only
                            else "connection_close",
                            "error_type": database.last_cleanup_error_type,
                            "db_driver": "pymysql",
                            "connection_phase": database.connection_phase,
                        }
                    },
                )
                exit_code = 1

    return exit_code


def safe_error_code(exception: Exception) -> int | None:
    for value in getattr(exception, "args", ()):
        if isinstance(value, int):
            return value
    return None


def safe_diagnostic(exception: Exception, database: MySqlDatabase | None) -> dict[str, object]:
    driver_exception = isinstance(exception, pymysql.MySQLError)
    retryable = isinstance(exception, (pymysql.err.InterfaceError, pymysql.err.OperationalError))

    return {
        "error_code": safe_error_code(exception),
        "db_driver": "pymysql" if driver_exception else None,
        "connection_phase": (
            database.connection_phase if driver_exception and database is not None else None
        ),
        "retryable": retryable if driver_exception else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())

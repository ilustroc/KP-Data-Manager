from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from .config import Settings
from .db import MySqlDatabase
from .domain.errors import EtlError
from .domain.errors import BatchNotFoundError
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
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
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
    parser = argparse.ArgumentParser(description="Procesa una carga PENDIENTE soportada.")
    parser.add_argument("--batch-id", required=True, type=positive_batch_id)
    arguments = parser.parse_args(argv)

    database = None
    configure_logging("INFO")
    try:
        settings = Settings.from_environment()
        configure_logging(settings.log_level)
        database = MySqlDatabase(settings)
        batch = database.get_batch(arguments.batch_id)
        if batch is None:
            raise BatchNotFoundError(f"No existe el batch #{arguments.batch_id}.")
        loader = LoaderRegistry().resolve(batch, database, settings)
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
        return 0
    except EtlError as exception:
        logging.getLogger("kpdm.etl").error(
            "worker_rejected",
            extra={"context": {"batch_id": arguments.batch_id, "error": str(exception)}},
        )
        return 1
    except Exception:
        logging.getLogger("kpdm.etl").exception(
            "worker_crashed",
            extra={"context": {"batch_id": arguments.batch_id}},
        )
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(main())

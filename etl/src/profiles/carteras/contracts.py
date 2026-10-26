import hashlib
from datetime import date


def wandoo_derived_account(documento_cliente: str) -> str:
    """Contract only: Wandoo prepends exactly one zero to the textual DNI."""
    return "0" + documento_cliente


def wandoo_derived_loan_instance_identifier(
    documento_cliente: str,
    numero_prestamo: str,
    fecha_otorgamiento: date | None,
) -> str | None:
    """Return a technical, non-official Wandoo loan-instance reference."""
    if fecha_otorgamiento is None:
        return None

    identity_parts = (
        "WAN1",
        _wandoo_identity_component(documento_cliente),
        _wandoo_identity_component(numero_prestamo),
        _wandoo_identity_component(fecha_otorgamiento.isoformat()),
    )
    payload = "|".join(identity_parts)

    return f"WAN1:{hashlib.sha256(payload.encode('ascii')).hexdigest()}"


def _wandoo_identity_component(value: str) -> str:
    encoded_value = value.encode("utf-8")

    return f"{len(encoded_value)}:{encoded_value.hex()}"

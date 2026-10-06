def wandoo_derived_account(documento_cliente: str) -> str:
    """Contract only: Wandoo prepends exactly one zero to the textual DNI."""
    return "0" + documento_cliente

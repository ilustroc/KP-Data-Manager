class EtlError(Exception):
    """Base exception for controlled ETL failures."""


class ConfigurationError(EtlError):
    """Raised when required ETL configuration is invalid."""


class BatchNotFoundError(EtlError):
    """Raised when the requested import batch does not exist."""


class BatchStateError(EtlError):
    """Raised when a batch cannot be claimed from PENDIENTE."""


class StructuralFileError(EtlError):
    """Raised when the whole source file is structurally invalid."""


class FileSecurityError(EtlError):
    """Raised when a stored path or file fingerprint is unsafe."""

class NVIQError(Exception):
    """Base NVIQ error."""


class CaseValidationError(NVIQError):
    """Raised when a benchmark case violates the canonical schema."""


class ObservationValidationError(NVIQError):
    """Raised when a track observation is invalid."""


class AuditValidationError(NVIQError):
    """Raised when a commercial audit artifact is invalid."""


class EvidenceValidationError(NVIQError):
    """Raised when a raw execution evidence bundle is invalid."""

"""Domain exception hierarchy for FinHealth components."""


class FinHealthError(Exception):
    """Base exception for all FinHealth domain failures."""


class ConfigurationError(FinHealthError):
    """Application configuration cannot be applied."""


class SecIngestionError(FinHealthError):
    """SEC retrieval or ingestion failed."""


class SecRateLimitError(SecIngestionError):
    """SEC Fair Access rejected a request or rate-limit retries were exhausted."""


class SecResourceNotFoundError(SecIngestionError):
    """The requested registrant or SEC resource does not exist."""


class EtlProcessingError(FinHealthError):
    """Financial data extraction, transformation, or loading failed."""


class ModelPipelineError(FinHealthError):
    """Model training, evaluation, or inference failed."""

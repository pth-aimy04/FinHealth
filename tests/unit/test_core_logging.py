"""Observable logging behavior and domain exception contracts."""

import io
import logging
from collections.abc import Iterator

import pytest

from finhealth.core.exceptions import (
    ConfigurationError,
    EtlProcessingError,
    FinHealthError,
    ModelPipelineError,
    SecIngestionError,
)
from finhealth.core.logging import setup_logging


@pytest.fixture
def isolated_logger() -> Iterator[logging.Logger]:
    """Restore global logger state and close handlers created during a test."""
    logger = logging.getLogger("finhealth")
    old_handlers = logger.handlers[:]
    old_level, old_propagate = logger.level, logger.propagate
    logger.handlers = []
    try:
        yield logger
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = old_handlers
        logger.setLevel(old_level)
        logger.propagate = old_propagate


def test_logging_is_idempotent_and_updates_level(isolated_logger: logging.Logger) -> None:
    """Repeated setup preserves handler identity and emits a child record once."""
    logger = setup_logging()
    original_handler = logger.handlers[0]
    assert setup_logging("debug") is logger is isolated_logger
    assert logger.handlers == [original_handler]
    assert logger.level == original_handler.level == logging.DEBUG
    assert logger.propagate is False
    assert isinstance(original_handler, logging.StreamHandler)
    output = io.StringIO()
    original_handler.setStream(output)
    logging.getLogger("finhealth.ingestion").info("retrieved filing")
    lines = output.getvalue().splitlines()
    assert len(lines) == 1
    assert " | finhealth.ingestion | test_core_logging | INFO | retrieved filing" in lines[0]
    assert lines[0][:4].isdigit()
    assert lines[0][10] == "T"
    setup_logging("ERROR")
    logging.getLogger("finhealth.ingestion").warning("must be filtered")
    assert output.getvalue().splitlines() == lines


def test_invalid_logging_level_has_no_side_effects(isolated_logger: logging.Logger) -> None:
    """Invalid levels fail explicitly before installing a handler."""
    with pytest.raises(ValueError, match="Invalid logging level"):
        setup_logging("unrecognized")
    assert isolated_logger.handlers == []


@pytest.mark.parametrize(
    "exception_type",
    [ConfigurationError, SecIngestionError, EtlProcessingError, ModelPipelineError],
)
def test_domain_exceptions_preserve_message(exception_type: type[FinHealthError]) -> None:
    """Domain failures remain catchable through the common exception base."""
    with pytest.raises(FinHealthError, match="concrete failure") as error:
        raise exception_type("concrete failure")
    assert type(error.value) is exception_type
    assert str(error.value) == "concrete failure"

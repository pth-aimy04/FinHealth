"""Optional Spark startup with an explicit UTC session timezone."""

from typing import TYPE_CHECKING

from finhealth.core.exceptions import EtlProcessingError

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def create_spark_session(
    app_name: str = "FinHealthETL", master: str = "local[*]"
) -> "SparkSession":
    """Start Spark lazily or raise an actionable dependency/Java startup error."""
    try:
        from pyspark.sql import SparkSession
    except ImportError as error:
        raise EtlProcessingError(
            "Spark requires the optional finhealth[spark] dependency"
        ) from error
    try:
        return (
            SparkSession.builder.appName(app_name)
            .master(master)
            .config("spark.sql.session.timeZone", "UTC")
            .getOrCreate()
        )
    except Exception as error:
        # Py4J, JVM, environment, and Spark-specific startup failures share no single base.
        raise EtlProcessingError(
            "Cannot start Spark; check Java and Spark runtime configuration"
        ) from error

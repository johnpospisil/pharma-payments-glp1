import pytest

from ppg import config


@pytest.fixture(scope="session")
def con():
    """DuckDB connection for tests on the real data; skips if the Parquet is not present."""
    if (
        not (config.PARQUET_DIR / "open_payments" / "general").exists()
        or not (config.PARQUET_DIR / "partd" / "by_provider_drug").exists()
    ):
        pytest.skip("real data not present (PPG_DATA_DIR/parquet)")
    from ppg.ingest.quality import connect

    return connect()

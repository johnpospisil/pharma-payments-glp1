import importlib

import pytest

MODULES = [
    "duckdb",
    "polars",
    "pyarrow",
    "pandas",
    "numpy",
    "httpx",
    "tenacity",
    "pyfixest",
    "differences",
    "statsmodels",
    "linearmodels",
    "scipy",
    "matplotlib",
    "plotly",
    "ppg",
    "ppg.ingest",
    "ppg.build",
    "ppg.models",
    "ppg.viz",
    "ppg.check_env",
]


@pytest.mark.parametrize("name", MODULES)
def test_import(name):
    importlib.import_module(name)

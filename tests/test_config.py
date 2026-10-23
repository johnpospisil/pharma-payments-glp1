from pathlib import Path

from ppg import config


def test_paths_are_paths():
    for p in (config.RAW_DIR, config.DATA_DIR, config.REFERENCE_DIR, config.REPORT_DIR):
        assert isinstance(p, Path)


def test_reference_dir_is_in_repo():
    assert config.REFERENCE_DIR.is_relative_to(config.REPO_ROOT)


def test_min_cell_matches_cms_suppression():
    assert config.MIN_CELL == 11


def test_relative_env_paths_resolve_from_repo_root(monkeypatch):
    monkeypatch.setenv("PPG_DATA_DIR", "./data")
    assert config._path("PPG_DATA_DIR", "x") == config.REPO_ROOT / "data"

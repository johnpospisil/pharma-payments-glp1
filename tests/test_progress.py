import json

from ppg import progress


def test_progress_roundtrip_and_render(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "PROGRESS_DIR", tmp_path)
    with progress.Progress("job") as p:
        p.add("a", total=100, unit="B")
        p.add("b", total=300, unit="B")
        p.start("a")
        p.advance("a", 100)
        p.finish("a")
        p.start("b")
        p.advance("b", 150)
        p._write(force=True)
        state = json.loads((tmp_path / "job.json").read_text())
        line = progress.render(state)
        assert "62.5%" in line  # (100 + 150) / 400, weighted by task totals
        assert "1/2 tasks" in line and "↳ b" in line
    assert json.loads((tmp_path / "job.json").read_text())["status"] == "done"


def test_finished_tasks_survive_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "PROGRESS_DIR", tmp_path)
    with progress.Progress("job") as p:
        p.add("a", total=10)
        p.start("a")
        p.finish("a")
    with progress.Progress("job") as p:
        p.add("a", total=10)
        assert p.is_done("a")

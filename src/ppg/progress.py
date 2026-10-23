"""Live progress for long jobs, readable from any terminal.

Jobs write `DATA_DIR/progress/<job>.json` (atomically, at most once a second).
`make progress` prints one overall bar per job; `make progress WATCH=1` refreshes it.

    with Progress("open_payments") as p:
        p.add("download PY2024", total=1_146_832_771, unit="B")
        p.advance("download PY2024", n)
"""

from __future__ import annotations

import json
import os
import sys
import time

from ppg import config

PROGRESS_DIR = config.DATA_DIR / "progress"


class Progress:
    def __init__(self, job: str):
        self.job = job
        self.path = PROGRESS_DIR / f"{job}.json"
        self.state: dict = {"job": job, "started": time.time(), "pid": os.getpid(), "tasks": {}}
        self._last = 0.0

    def __enter__(self) -> Progress:
        if self.path.exists():  # keep tasks already finished in an earlier run
            old = json.loads(self.path.read_text())
            self.state["tasks"] = {
                k: v for k, v in old.get("tasks", {}).items() if v.get("status") == "done"
            }
        self.state["status"] = "running"
        self._write(force=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.state["status"] = "failed" if exc_type else "done"
        self.state["finished"] = time.time()
        self._write(force=True)

    def add(self, task: str, total: float, unit: str = "") -> None:
        t = self.state["tasks"].get(task)
        if t is None or t.get("status") != "done":
            self.state["tasks"][task] = {
                "done": 0,
                "total": total,
                "unit": unit,
                "status": "pending",
                "t0": None,
            }
        self._write()

    def is_done(self, task: str) -> bool:
        return self.state["tasks"].get(task, {}).get("status") == "done"

    def start(self, task: str, done: float = 0) -> None:
        t = self.state["tasks"][task]
        t.update(status="running", done=done, t0=time.time(), done0=done)
        self._write(force=True)

    def advance(self, task: str, n: float) -> None:
        self.state["tasks"][task]["done"] += n
        self._write()

    def finish(self, task: str) -> None:
        t = self.state["tasks"][task]
        t.update(status="done", done=t["total"])
        self._write(force=True)

    def _write(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last < 1.0:
            return
        self._last = now
        self.state["updated"] = now
        PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state))
        tmp.replace(self.path)


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1000:
            return f"{n:,.1f} {unit}"
        n /= 1000
    return f"{n:,.1f} PB"


def _fmt_secs(s: float) -> str:
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


def render(state: dict, width: int = 30) -> str:
    """One overall line per job (weighted by each task's total), plus the running task."""
    tasks = state["tasks"].values()
    total = sum(t["total"] for t in tasks) or 1
    done = sum(min(t["done"], t["total"]) for t in tasks)
    frac = done / total
    bar = "█" * int(frac * width) + "░" * (width - int(frac * width))
    n_done = sum(t["status"] == "done" for t in tasks)
    line = f"{state['job']:<16} {bar} {frac:6.1%}  {n_done}/{len(state['tasks'])} tasks"
    status = state.get("status", "?")
    if status != "running":
        return f"{line}  [{status}]"
    if time.time() - state.get("updated", 0) > 120:
        line += "  [stalled? no update for >2 min]"
    for name, t in state["tasks"].items():
        if t["status"] == "running" and t.get("t0"):
            elapsed = max(time.time() - t["t0"], 1e-6)
            rate = (t["done"] - t.get("done0", 0)) / elapsed
            left = (t["total"] - t["done"]) / rate if rate > 0 else float("nan")
            unit = t["unit"]
            fmt = _fmt_bytes if unit == "B" else (lambda x, u=unit: f"{x:,.0f} {u}")
            line += (
                f"\n  ↳ {name}: {fmt(t['done'])} / {fmt(t['total'])}"
                f"  {fmt(rate)}/s  ETA {_fmt_secs(left) if left == left else '?'}"
            )
    return line


def main(argv: list[str]) -> int:
    watch = "--watch" in argv
    jobs = [a for a in argv if not a.startswith("--")]
    while True:
        files = sorted(PROGRESS_DIR.glob("*.json")) if PROGRESS_DIR.exists() else []
        files = [f for f in files if not jobs or f.stem in jobs]
        out = "\n".join(render(json.loads(f.read_text())) for f in files) or "no jobs found"
        if watch:
            sys.stdout.write(
                "\033[2J\033[H" + time.strftime("%H:%M:%S  (Ctrl-C to stop)\n") + out + "\n"
            )
            sys.stdout.flush()
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                return 0
        else:
            print(out)
            return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

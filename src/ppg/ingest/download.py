"""Idempotent, resumable downloads into RAW_DIR, logged to data/reference/retrievals.csv.

A file is fetched only if it is missing or smaller than the server's size. Partial
files resume with HTTP Range requests. Every completed file is logged once with its
retrieval date, size and SHA-256.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ppg import config
from ppg.progress import Progress

log = logging.getLogger(__name__)

RETRIEVALS = config.REFERENCE_DIR / "retrievals.csv"
FIELDS = ["retrieved_utc", "source", "url", "path", "bytes", "sha256"]
CHUNK = 8 * 1024 * 1024
# identity: CMS gzips some responses in transit, which breaks size checks and Range resumes.
HEADERS = {
    "User-Agent": "ppg-research-pipeline (github.com/johnpospisil/pharma-payments-glp1)",
    "Accept-Encoding": "identity",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def _remote_size(client: httpx.Client, url: str) -> int | None:
    """Size in bytes, or None if the server reports neither Content-Range nor Content-Length."""
    with client.stream("GET", url, headers={"Range": "bytes=0-0"}) as r:
        r.raise_for_status()
        if "content-range" in r.headers:
            return int(r.headers["content-range"].rsplit("/", 1)[1])
        if "content-length" in r.headers:
            return int(r.headers["content-length"])
    return None


def _logged_paths() -> set[str]:
    if not RETRIEVALS.exists():
        return set()
    with RETRIEVALS.open() as f:
        return {row["path"] for row in csv.DictReader(f)}


def _log_retrieval(source: str, url: str, path: Path) -> None:
    new = not RETRIEVALS.exists()
    RETRIEVALS.parent.mkdir(parents=True, exist_ok=True)
    with RETRIEVALS.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(
            {
                "retrieved_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": source,
                "url": url,
                "path": str(path.relative_to(config.RAW_DIR)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )


def remote_size(url: str) -> int | None:
    with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
        return _remote_size(client, url)


def fetch(
    url: str,
    dest: Path,
    source: str,
    retries: int = 8,
    progress: Progress | None = None,
    task: str | None = None,
) -> Path:
    """Download `url` to `dest` and log it. Returns `dest`.

    Bytes go to `dest.part`, renamed to `dest` only when complete, so an existing `dest`
    is always a finished download. A partial `.part` resumes with a Range request when the
    server reports the size; otherwise it is restarted. If `progress` and `task` are given,
    bytes are reported to that task as they arrive.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    rel = str(dest.relative_to(config.RAW_DIR))
    part = dest.with_name(dest.name + ".part")
    if dest.exists():
        if rel not in _logged_paths():
            _log_retrieval(source, url, dest)
        return dest
    with httpx.Client(
        timeout=httpx.Timeout(60, read=300), follow_redirects=True, headers=HEADERS
    ) as client:
        total = _remote_size(client, url)
        for attempt in range(1, retries + 1):
            have = part.stat().st_size if part.exists() else 0
            if total is None or have > total:
                have = 0
            if progress and task:
                progress.start(task, done=have)
            if total is not None and have == total:
                break
            try:
                headers = {"Range": f"bytes={have}-"} if have else {}
                with client.stream("GET", url, headers=headers) as r:
                    r.raise_for_status()
                    if have and r.status_code != 206:
                        raise RuntimeError("server ignored Range request")
                    t0, got = time.monotonic(), 0
                    with part.open("ab" if have else "wb") as f:
                        for block in r.iter_raw(CHUNK):
                            f.write(block)
                            got += len(block)
                            if progress and task:
                                progress.advance(task, len(block))
                    secs = time.monotonic() - t0
                    log.info(
                        "%s: %.1f MB in %.0fs (%.1f MB/s)",
                        dest.name,
                        got / 1e6,
                        secs,
                        got / 1e6 / max(secs, 1e-6),
                    )
                if total is None:
                    break
            except (httpx.HTTPError, RuntimeError) as e:
                wait = min(2**attempt, 120)
                log.warning(
                    "%s attempt %d failed (%s); retrying in %ds", dest.name, attempt, e, wait
                )
                time.sleep(wait)
        else:
            raise RuntimeError(f"failed to download {url} after {retries} attempts")
    if total is not None and part.stat().st_size != total:
        raise RuntimeError(f"{dest.name}: size {part.stat().st_size} != remote {total}")
    part.replace(dest)
    _log_retrieval(source, url, dest)
    return dest

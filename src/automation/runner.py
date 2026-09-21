"""Content-addressed, single-writer local research runner."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RunnerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["paper"] = "paper"
    manifest_path: Path = Path("config/momentum_universe.json")
    output_root: Path = Path("results/automation")
    workers: int = Field(default=1, ge=1, le=4)
    interval_seconds: int = Field(default=3600, ge=300, le=86400)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict) -> None:
    """Replace a small state file only after flushing the complete JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(path: Path) -> RunnerConfig:
    config = RunnerConfig.model_validate_json(path.read_text(encoding="utf-8"))
    updates = {}
    for name in ("manifest_path", "output_root"):
        selected = getattr(config, name)
        updates[name] = (PROJECT_ROOT / selected).resolve() if not selected.is_absolute() else selected.resolve()
    return config.model_copy(update=updates)


@contextmanager
def single_writer(path: Path):
    """An OS lock is released on process exit, including an unexpected crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            raise RuntimeError("another research run holds the lock") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def input_fingerprint(config: RunnerConfig) -> str:
    """Hash input bytes and implementation, so edited data invalidates old results."""
    digest = hashlib.sha256(config.model_dump_json().encode())
    manifest_path = config.manifest_path.resolve()
    paths = [manifest_path]
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            for asset in payload.get("assets", {}).values():
                path = (manifest_path.parent / asset["local_file"]).resolve()
                path.relative_to(manifest_path.parent.parent)
                paths.append(path)
        except (ValueError, KeyError, TypeError, AttributeError):
            # The research validator records the exact malformed-manifest error.
            digest.update(b"invalid_manifest")
    for folder in ("automation", "backtest", "strategies"):
        paths.extend((PROJECT_ROOT / "src" / folder).glob("*.py"))
    for path in sorted(set(paths)):
        digest.update(str(path).encode("utf-8"))
        if not path.is_file():
            digest.update(b"missing")
            continue
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def read_state(output_root: Path) -> dict:
    path = output_root / "state.json"
    if not path.exists():
        return {"status": "never_run", "mode": "paper"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise RuntimeError("automation state is unreadable; preserve it and inspect before resuming") from exc


def run_once(config: RunnerConfig, *, force: bool = False, research: Callable | None = None) -> dict:
    if research is None:
        from .research import run_research
        research = run_research
    root = config.output_root
    root.mkdir(parents=True, exist_ok=True)
    with single_writer(root / "runner.lock"):
        fingerprint = input_fingerprint(config)
        prior = read_state(root)
        if not force and prior.get("fingerprint") == fingerprint and prior.get("status") in {"completed", "blocked"}:
            return {**prior, "unchanged": True, "checked_at_utc": utc_now()}
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
        output = root / "runs" / run_id
        output.mkdir(parents=True, exist_ok=False)
        state = {
            "run_id": run_id, "status": "running", "mode": "paper",
            "started_at_utc": utc_now(), "fingerprint": fingerprint,
            "output_dir": str(output.resolve()), "last_success": prior.get("last_success"),
            "network_enabled": False, "promotion_allowed": False,
        }
        atomic_json(root / "state.json", state)
        started = time.monotonic()
        try:
            result = research(config.manifest_path, output, workers=config.workers)
            status = result.get("status")
            if status not in {"completed", "blocked"}:
                raise RuntimeError("research returned an unsupported status")
            # Discard a result if an input changed while the computation ran.
            if input_fingerprint(config) != fingerprint:
                state.update(status="failed", error_type="InputsChangedDuringRun")
            else:
                state.update(status=status, result=result)
                if status == "completed":
                    state["last_success"] = {"run_id": run_id, "output_dir": str(output.resolve())}
        except Exception as exc:
            # Do not copy exception text into logs: inputs may contain credentials.
            state.update(status="failed", error_type=type(exc).__name__)
        state.update(finished_at_utc=utc_now(), elapsed_seconds=round(time.monotonic() - started, 3))
        atomic_json(output / "run.json", state)
        atomic_json(root / "state.json", state)
        return state

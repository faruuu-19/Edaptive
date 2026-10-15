"""The batch runner's local state: per-card status, the rolling daily token ledger, a lock file, and a proposal cache.

All of it lives under ``.assessment_batch/`` (git-ignored). Nothing here ever holds an API key.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from batch_cards import atomic_write

FINISHED = ("built_ready", "built_not_ready", "skipped")


class StateError(Exception):
    """The state file cannot be trusted. The run stops rather than overwrite it and repeat model calls."""


class LockHeld(Exception):
    """Another run holds the lock (or the lock file cannot be understood, which is treated the same way)."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BatchState:
    def __init__(self, path: Path, data: dict[str, Any]):
        self.path = path
        self.data = data

    @classmethod
    def load(cls, path: Path | str) -> "BatchState":
        path = Path(path)
        data: dict[str, Any] = {"version": 1, "cards": {}, "ledger": None, "resume_at": None, "stop_reason": None,
                                "push_confirmed": None, "commits": [], "runs": []}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise StateError(f"{path} cannot be read ({exc}); fix or move it by hand. It is not replaced automatically, because "
                                 "that could repeat model calls that already succeeded") from exc
            if not isinstance(loaded, dict) or not isinstance(loaded.get("cards"), dict):
                raise StateError(f"{path} is not a batch state file; fix or move it by hand")
            data.update(loaded)
        return cls(path, data)

    def save(self) -> None:
        atomic_write(self.path, self.data)

    def status(self, name: str) -> str | None:
        entry = self.data["cards"].get(name)
        return entry.get("status") if isinstance(entry, dict) else None

    def record(self, name: str, status: str, **info: Any) -> None:
        self.data["cards"][name] = {"status": status, "at": _now(), **info}

    def is_finished(self, name: str, retry_failed: bool = False) -> bool:
        status = self.status(name)
        return status in FINISHED or (status == "failed" and not retry_failed)


class RunLock:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def acquire(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    held = json.loads(self.path.read_text(encoding="utf-8"))
                    pid = int(held["pid"])
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise LockHeld(f"{self.path} exists and cannot be read; if no run is active, delete it by hand") from exc
                if self._alive(pid):
                    raise LockHeld(f"another batch run (process {pid}) holds {self.path}")
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"pid": os.getpid(), "since": _now()}))
            return self
        raise LockHeld(f"could not take {self.path}")

    def release(self) -> None:
        try:
            held = json.loads(self.path.read_text(encoding="utf-8"))
            if held.get("pid") == os.getpid():
                self.path.unlink()
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    def __enter__(self) -> "RunLock":
        return self.acquire()

    def __exit__(self, *exc: Any) -> bool:
        self.release()
        return False


def card_fingerprint(card: Any) -> str:
    """Identifies the concept card's content (not where the file sits), so cached model output is only reused for the same card."""
    data = dataclasses.asdict(card)
    data.pop("input_file", None)
    data.pop("input_location", None)
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


class ProposalCache:
    """Accepted model output for one card, saved as each call succeeds, so a stopped card never repeats a successful call."""

    def __init__(self, directory: Path | str, name: str, fingerprint: str):
        self.path = Path(directory) / f"{name}.json"
        self.fingerprint = fingerprint
        self._entries: dict[str, Any] = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("fingerprint") == fingerprint and isinstance(data.get("entries"), dict):
                self._entries = data["entries"]
        except (OSError, json.JSONDecodeError):
            pass

    def get(self, key: str) -> Any:
        return self._entries.get(key)

    def put(self, key: str, proposal: Any) -> None:
        self._entries[key] = proposal
        atomic_write(self.path, {"fingerprint": self.fingerprint, "entries": self._entries})

    def keys(self) -> list[str]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries = {}
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

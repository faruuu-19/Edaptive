"""Durable local computation jobs. No student identity or audio is persisted here."""

import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .catalog import load_catalog

SCHEDULE_LEASE_SECONDS = 300


class PreparationJobs:
    def __init__(self, root, narrator, loader, store=None, start_worker=True, catalog=None):
        self.root = Path(root)
        self.narrator = narrator
        self.loader = loader
        self.folder = Path(store or Path.home() / "edaptive-voice/jobs")
        self.folder.mkdir(parents=True, exist_ok=True)
        self.database = self.folder / "jobs.sqlite3"
        self.runtime_root = Path(__file__).resolve().parents[1]
        source_files = sorted((self.runtime_root / "script_agent").glob("*.py"))
        source_files += [Path(__file__), Path(__file__).with_name("preparation_worker.py")]
        self.generator_revision = hashlib.sha256(b"".join(p.read_bytes() for p in source_files)).hexdigest()
        self._card_cache = None
        self.catalog = {p["concept_id"]: p for p in
                        (load_catalog(self.root) if catalog is None else catalog)}
        self.lock = threading.RLock()
        self.process = None
        self.running = None
        self.idle = threading.Event()
        self.idle.set()
        self.reservation = None
        self.reservation_until = 0
        self.closed = threading.Event()
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS job (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservation (name TEXT PRIMARY KEY, job_id TEXT, expires_at REAL)"
            )
            saved = db.execute(
                "SELECT job_id, expires_at FROM reservation WHERE name='delivery'"
            ).fetchone()
            if saved:
                self.reservation, self.reservation_until = saved
            for key, body in db.execute("SELECT id, body FROM job").fetchall():
                row = json.loads(body)
                if row["status"] == "failed" and any(
                    term in row.get("message", "")
                    for term in [
                        "Swap increased",
                        "memory pressure",
                        "Not enough memory",
                        "Critical",
                    ]
                ):
                    row.update(
                        status="paused",
                        retry_at=time.time() + 30,
                        message="Memory guard paused preparation; resuming from the saved checkpoint",
                    )
                    db.execute(
                        "UPDATE job SET body=? WHERE id=?", (json.dumps(row), key)
                    )
                if row["status"] == "preparing":
                    row.update(
                        status="queued",
                        message="Resuming preparation after service restart",
                    )
                    db.execute(
                        "UPDATE job SET body=? WHERE id=?", (json.dumps(row), key)
                    )
        self.thread = threading.Thread(target=self.loop, daemon=True)
        if start_worker:
            self.thread.start()

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def get(self, key):
        with self.lock, self.connect() as db:
            row = db.execute("SELECT body FROM job WHERE id=?", (key,)).fetchone()
            if not row:
                raise ValueError("Unknown preparation job.")
            return json.loads(row[0])

    def write(self, row):
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO job VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (row["id"], json.dumps(row)),
            )

    def public(self, key):
        row = self.get(key)
        row["percent"] = 100 if row["status"] == "ready" else max(0, min(98, row.get("percent", 0)))
        return {k: v for k, v in row.items() if k not in {"script"}}

    def revision(self, cid):
        pair = self.catalog[cid]
        content = {k: pair.get(k) for k in ("concept_sha256", "assessment_sha256", "concept_version")}
        return hashlib.sha256((self.generator_revision + json.dumps(content, sort_keys=True)).encode()).hexdigest()

    def submit(self, request):
        key = str(uuid.UUID(request["job_id"]))
        cid = request["concept_id"]
        if cid not in self.catalog:
            raise ValueError("Matched content is unavailable.")
        with self.lock:
            try:
                old = self.get(key)
                if old["concept_id"] != cid:
                    raise ValueError("Job identity cannot change content.")
                changed = old["status"] == "failed" and old.get("revision") != self.revision(cid)
                expired = old["status"] == "cancelled" and old.get("cancel_reason") == "schedule_expired"
                if changed or expired:
                    old.update(status="queued", percent=0, revision=self.revision(cid),
                               message="Rechecking the lesson after an update" if changed else "Resuming scheduled preparation")
                    old.pop("cancel_reason", None)
                    if changed:
                        old.pop("script", None)
                if request.get("managed") is True:
                    old.update(managed=True, last_requested_at=time.time())
                if changed or expired or request.get("managed") is True:
                    self.write(old)
                return self.public(key)
            except ValueError as error:
                if str(error) != "Unknown preparation job.":
                    raise
            self.write(
                {
                    "id": key,
                    "concept_id": cid,
                    "status": "queued",
                    "percent": 0,
                    "completed": 0,
                    "total": None,
                    "message": "Waiting for the local model",
                    "created_at": time.time(),
                    "revision": self.revision(cid),
                    "managed": request.get("managed") is True,
                    "last_requested_at": time.time(),
                }
            )
        return self.public(key)

    def cancel(self, key, reason=None):
        with self.lock:
            row = self.get(key)
            if row["status"] != "cancelled":
                row.update(status="cancelled", message="Preparation cancelled")
                if reason:
                    row["cancel_reason"] = reason
                self.write(row)
            if self.running == key and self.process is not None:
                self.process.terminate()
        return self.public(key)

    def retry(self, key):
        with self.lock:
            row = self.get(key)
            if row["status"] != "failed":
                raise ValueError("Only a failed job can be retried.")
            row.update(
                status="queued",
                message="Resuming checked sections and repairing flagged lines",
            )
            self.write(row)
        return self.public(key)

    def lesson(self, key):
        row = self.get(key)
        if row["status"] != "ready":
            raise ValueError("The prepared lesson is not ready.")
        return self.loader(Path(row["script"]))

    def list_cards(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from script_agent import plan_lesson
        from script_agent.sample_inputs import load_card
        from .timing import estimate_timing

        with self.connect() as db:
            saved = [json.loads(r[0]) for r in db.execute("SELECT body FROM job")]
        measured = []
        for job in saved:
            if job["status"] == "ready" and job.get("script"):
                # A removed ready artifact must not make the entire curriculum catalog fail.
                if not Path(job["script"]).is_file():
                    continue
                finished = job.get("finished_at") or Path(job["script"]).stat().st_mtime
                measured.append(
                    (finished - job["created_at"]) / max(1, job.get("total", 84))
                )
        seconds_per_section = max(5, min(60, max(measured, default=12)))
        if self._card_cache is not None:
            result = copy.deepcopy(self._card_cache)
            for card in result:
                pair = self.catalog[card["id"]]
                card["recommended_prepare_minutes"] = max(10, int(pair["plan_segments"] * seconds_per_section * 1.25 / 60) + 3)
            return result
        result = []
        for p in self.catalog.values():
            concept = load_card(Path(p["concept"]), p["concept_id"])
            assessment = load_card(Path(p["assessment"]), p["assessment_id"], True)
            plan = plan_lesson(concept, assessment, "detectives", rewrite=True)
            timing = estimate_timing(
                plan["segments"], p["grade"], plan["delivery_policy"]["main_path"]
            )
            result.append(
                {
                    "id": p["concept_id"],
                    "grade": p["grade"],
                    "module": p["module"],
                    "title": p["concept_id"]
                    .split("_", 4)[-1]
                    .replace("_", " ")
                    .capitalize(),
                    "card_version": p["concept_version"],
                    "ready_for_delivery": p["ready_for_delivery"],
                    "estimated_minutes": timing["minutes"],
                    "recommended_prepare_minutes": max(
                        10,
                        int(p["plan_segments"] * seconds_per_section * 1.25 / 60) + 3,
                    ),
                    "timing": {**timing, "basis": "card_plan"},
                }
            )
        self._card_cache = copy.deepcopy(result)
        return result

    def expire_schedule(self, key):
        """Unenrolled/deleted schedules stop renewing work. Keep content checkpoints, not student identity."""
        row = self.get(key)
        expired = (row.get("managed") and row["status"] in {"queued", "preparing", "paused", "paused_for_delivery"}
                   and time.time() - row.get("last_requested_at", time.time()) > SCHEDULE_LEASE_SECONDS
                   and time.time() >= self.reservation_until)
        if expired:
            self.cancel(key, reason="schedule_expired")
        return bool(expired)

    def reserve(self, key):
        with self.lock:
            if self.get(key)["status"] != "ready":
                raise ValueError("The selected lesson is not ready.")
            if (
                self.reservation
                and self.reservation != key
                and time.time() < self.reservation_until
            ):
                raise ValueError("Another lesson is using the local teacher.")
            self.reservation = key
            self.reservation_until = time.time() + 120
            with self.connect() as db:
                db.execute(
                    "INSERT INTO reservation VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET job_id=excluded.job_id, expires_at=excluded.expires_at",
                    ("delivery", key, self.reservation_until),
                )
            if self.running and self.process:
                paused = self.get(self.running)
                paused.update(
                    status="paused_for_delivery",
                    message="Preparation paused while a class is listening",
                )
                self.write(paused)
                self.process.terminate()
        if not self.idle.wait(timeout=8):
            raise ValueError(
                "The model is switching to your teacher voice. Please try again shortly."
            )
        self.narrator.warm()
        return {"reserved": True}

    def release(self, key):
        with self.lock:
            if self.reservation != key:
                return {"released": True}
            self.reservation = None
            self.reservation_until = 0
            with self.connect() as db:
                db.execute("DELETE FROM reservation WHERE name='delivery'")
        # Free the teacher voice's memory once the class is finished, cancelled or unattended.
        # If a sentence is still playing the model stays loaded; the next narration reloads it.
        try:
            self.narrator.release()
        except ValueError:
            pass
        return {"released": True}

    def loop(self):
        while not self.closed.wait(0.5):
            with self.connect() as db:
                rows = [json.loads(r[0]) for r in db.execute("SELECT body FROM job")]
            queued = sorted(
                (
                    r
                    for r in rows
                    if r["status"] in {"queued", "paused_for_delivery"}
                    or (r["status"] == "paused" and time.time() >= r.get("retry_at", 0))
                ),
                key=lambda r: r["created_at"],
            )
            if queued and time.time() >= self.reservation_until:
                for candidate in queued:
                    if not self.expire_schedule(candidate["id"]):
                        self.run(candidate["id"])
                        break

    def update(self, key, **fields):
        with self.lock:
            row = self.get(key)
            if row["status"] in {"cancelled", "paused_for_delivery"}:
                return
            row.update(fields)
            self.write(row)

    def run(self, key):
        try:
            with self.lock:
                row = self.get(key)
                if (
                    row["status"] not in {"queued", "paused", "paused_for_delivery"}
                    or time.time() < self.reservation_until
                ):
                    return
                if row["status"] == "paused_for_delivery":
                    # The class has released the voice; continue from the saved checkpoint.
                    row.update(status="queued", message="Resuming preparation after the class")
                    self.write(row)
                self.running = key
                self.idle.clear()
                self.update(key, status="preparing", revision=self.revision(row["concept_id"]), message="Planning the lesson")
            # Model ownership is exclusive; defer rather than fail when a child is listening.
            try:
                self.narrator.release()
            except ValueError:
                self.update(
                    key,
                    status="queued",
                    message="Waiting for the current teacher narration",
                )
                return
            pair = self.catalog[row["concept_id"]]
            if row.get("script") and row.get("revision") == self.revision(row["concept_id"]):
                # Voice warm-up can run out of memory after the script passed. Retry
                # that last step without loading Qwen and generating the lesson again.
                self.loader(Path(row["script"]))
                self.narrator.warm()
                self.update(key, status="ready", percent=100, message="Lesson ready", finished_at=time.time())
                return
            command = [
                sys.executable,
                "-B",
                "-m",
                "voice_service.preparation_worker",
                "--root",
                str(self.runtime_root),
                "--concept",
                pair["concept"],
                "--assessment",
                pair["assessment"],
                "--concept-id",
                pair["concept_id"],
                "--assessment-id",
                pair["assessment_id"],
                "--output",
                str(self.folder / key),
            ]
            with self.lock:
                if self.get(key)["status"] in {"cancelled", "paused_for_delivery"}:
                    return
                self.process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                process = self.process
            # Drain diagnostics without exposing arbitrary exception text to the browser.
            threading.Thread(target=lambda: process.stderr.read(), daemon=True).start()
            script = None
            failure = None
            for line in process.stdout:
                if self.expire_schedule(key):
                    break
                try:
                    progress = json.loads(line)
                except ValueError:
                    continue
                failure = progress.get("error", failure)
                script = progress.get("script", script)
                if "percent" in progress:
                    self.update(
                        key,
                        percent=max(0, min(97, progress["percent"])),
                        completed=progress.get("completed", 0),
                        total=progress.get("total"),
                        message="Repairing flagged script sections"
                        if progress["phase"] == "repairing"
                        else "Validating the lesson"
                        if progress["phase"] == "validated"
                        else "Preparing the lesson script",
                    )
            code = process.wait()
            if self.get(key)["status"] in {"cancelled", "paused_for_delivery"}:
                return
            if code or not script:
                raise ValueError(
                    failure
                    or "Local preparation stopped. Retry after checking the model service."
                )
            self.loader(Path(script))
            self.update(key, percent=98, script=script, message="Warming the teacher voice")
            self.narrator.warm()
            self.update(
                key,
                status="ready",
                percent=100,
                message="Lesson ready",
                script=script,
                finished_at=time.time(),
            )
        except Exception as error:
            memory_guard = any(
                term in str(error).lower()
                for term in [
                    "swap increased",
                    "memory pressure",
                    "not enough memory",
                    "vm pressure",
                ]
            )
            transient = isinstance(error, (OSError, TimeoutError)) or any(
                term in str(error).lower()
                for term in ("unavailable", "timed out", "connection refused", "model_call_failed")
            )
            self.update(
                key,
                status="paused" if memory_guard or transient else "failed",
                failure_kind="memory" if memory_guard else "service" if transient else "validation",
                message=str(error)[:500],
                retry_at=time.time() + 30,
            )
        finally:
            try:
                if self.get(key)["status"] != "ready":
                    self.narrator.warm()
            except Exception:
                pass
            with self.lock:
                self.process = None
                self.running = None
                self.idle.set()

    def close(self):
        self.closed.set()
        with self.lock:
            if self.process:
                self.process.terminate()
        if self.thread.is_alive():
            self.thread.join(timeout=5)

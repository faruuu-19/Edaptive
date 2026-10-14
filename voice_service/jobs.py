"""Durable local computation jobs. No student identity or audio is persisted here."""

import json
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


class PreparationJobs:
    def __init__(self, root, narrator, loader, store=None, start_worker=True):
        self.root = Path(root)
        self.narrator = narrator
        self.loader = loader
        self.folder = Path(store or Path.home() / "edaptive-voice/jobs")
        self.folder.mkdir(parents=True, exist_ok=True)
        self.database = self.folder / "jobs.sqlite3"
        self.catalog = {
            p["concept_id"]: p
            for p in json.loads(
                (self.root / "docs/voice-module/PAIR_INVENTORY.json").read_text()
            )["pairs"]
            if p["plan_passed"]
        }
        supplementary = self.root / "docs/voice-module/LOCAL_SUPPLEMENTARY_PAIRS.json"
        if supplementary.is_file():
            sys.path.insert(0, str(self.root))
            from script_agent import plan_lesson
            from script_agent.sample_inputs import load_card

            for cid, item in json.loads(supplementary.read_text()).items():
                if "error" in item:
                    continue
                source = self.root / item["source"]
                assessment = (
                    self.root
                    / "artifacts/live-builds"
                    / item["name"]
                    / "assessment_card.json"
                )
                a = json.loads(assessment.read_text())
                c = load_card(source, cid)
                plan = plan_lesson(c, a, "detectives", rewrite=True)
                self.catalog[cid] = {
                    "concept_id": cid,
                    "concept": str(source),
                    "assessment": str(assessment),
                    "assessment_id": a["assessment_card_id"],
                    "concept_version": c["card_version"],
                    "grade": c["grade"],
                    "module": int(cid.split("_")[2][1:]),
                    "ready_for_delivery": False,
                    "plan_passed": True,
                    "plan_segments": len(plan["segments"]),
                    "main_segments": len(plan["delivery_policy"]["main_path"]),
                }
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
        return {k: v for k, v in row.items() if k not in {"script"}}

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
                }
            )
        return self.public(key)

    def cancel(self, key):
        with self.lock:
            row = self.get(key)
            if row["status"] != "cancelled":
                row.update(status="cancelled", message="Preparation cancelled")
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
        sys.path.insert(0, str(self.root))
        from script_agent import plan_lesson
        from script_agent.sample_inputs import load_card
        from .timing import estimate_timing

        with self.connect() as db:
            saved = [json.loads(r[0]) for r in db.execute("SELECT body FROM job")]
        measured = []
        for job in saved:
            if job["status"] == "ready" and job.get("script"):
                finished = job.get("finished_at") or Path(job["script"]).stat().st_mtime
                measured.append(
                    (finished - job["created_at"]) / max(1, job.get("total", 84))
                )
        seconds_per_section = max(measured, default=12)
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
        return result

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
                self.run(queued[0]["id"])

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
                self.update(key, status="preparing", message="Planning the lesson")
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
            command = [
                sys.executable,
                "-B",
                "-m",
                "voice_service.preparation_worker",
                "--root",
                str(self.root),
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
                try:
                    progress = json.loads(line)
                except ValueError:
                    continue
                failure = progress.get("error", failure)
                script = progress.get("script", script)
                if "percent" in progress:
                    self.update(
                        key,
                        percent=progress["percent"],
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
            self.update(key, percent=98, message="Warming the teacher voice")
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
                term in str(error)
                for term in [
                    "Swap increased",
                    "memory pressure",
                    "Not enough memory",
                    "Critical",
                ]
            )
            self.update(
                key,
                status="paused" if memory_guard else "failed",
                message=str(error)[:500],
                retry_at=time.time() + 30,
            )
            # Qwen has unloaded in the child; restore voice availability after a failed job.
            try:
                self.narrator.warm()
            except Exception:
                pass
        finally:
            try:
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

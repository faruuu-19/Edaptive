"""The batch runner: build assessment cards for many concept cards, one at a time, inside the free tier's limits.

Safety rules the code enforces (each has a test):
- one request at a time, paced BEFORE each call from the provider's own headers and 429 messages (see rate_budget.py);
- a card is only written when it is complete; a card stopped part way is discarded, and every model answer already accepted for it
  is kept in a cache so the next run never repeats a successful call;
- a daily limit, a wait that is too long, a provider failure, Ctrl-C, low disk or a failed commit all end the run cleanly: finished
  cards are committed, state is saved, the lock is released;
- one bad card is a recorded failure with a reason, never the end of the run;
- commits go to a dedicated branch, never main; nothing is pushed until the user has confirmed the remote and branch.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import assessment_card as ac
import batch_cards as bc
import batch_git as bg
import batch_state as bs
import rate_budget as rb
import build_assessment_card as bac
from build_assessment_card import BuildResult
from concept_card_loader import NormalizedConceptCard
from model_backends import DEFAULT_GROQ_MODEL, ModelConfigError, make_client
from question_generator import GenerationConfig, ModelRequestError, generate_one

STATE_DIR_NAME = ".assessment_batch"
OUTPUT_DIR_NAME = "assessment_cards"
PROJECT_ROOT = Path(__file__).resolve().parent
PROVIDER_RETRY_SECONDS = 600.0           # when a provider failure carries no resume time of its own


class PreflightError(Exception):
    """Something is wrong before any card is built (not a repo, protected branch, low disk, bad output folder)."""


@dataclass
class Settings:
    root: Path = PROJECT_ROOT
    out_root: Path = PROJECT_ROOT / OUTPUT_DIR_NAME
    state_dir: Path = PROJECT_ROOT / STATE_DIR_NAME
    subject: str | None = None
    grade: int | None = None
    module: int | None = None
    lesson: str | None = None
    limit: int | None = None
    dry_run: bool = False
    order: str = "module"
    commit_every: int = 10
    branch: str = "assessment-cards"
    push: bool = True
    remote: str = "origin"
    confirm_push: bool = False
    min_gap: float = 2.0
    force: bool = False
    retry_failed: bool = False
    min_free_mb: int = 200
    model: str = DEFAULT_GROQ_MODEL
    timeout: float = 90.0
    max_output_tokens: int = 1024
    repairs: int = 1
    max_short_wait: float = 120.0


@dataclass
class Estimate:
    calls: int
    tokens: int                  # expected tokens (prompt + reply, with the repairs we expect), what counts toward the daily total
    requested_tokens: int        # prompt + the output limit we send, what the per-minute limit counts
    levels: tuple = ()


# ---------------------------------------------------------------------------------------------------------------- estimates

class _Probe:
    """Stands in for the model: remembers the first prompt generate_one would send, then refuses. Nothing leaves the machine."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] | None = None

    def chat(self, messages: list[dict[str, str]], *, timeout: float, max_output_tokens: int) -> str:
        self.messages = messages
        raise ModelRequestError("probe only", kind="probe")


# Typical reply sizes from the live runs (completion tokens): easy/follow-up 150-300, medium ~450, hard 550-830.
EXPECTED_REPLY_TOKENS = {"easy": 300, "medium": 450, "hard": 850}
REPAIR_RATE = 0.5          # we expect about one repair request for every two questions
FOLLOW_UP_EXTRA_PROMPT_TOKENS = 150


def probe_estimator(config: GenerationConfig, chars_per_token: Callable[[], float] = lambda: rb.RateLedger.DEFAULT_CHARS_PER_TOKEN) -> Callable:
    """Estimate a card's model cost from the real prompts generate_one would build (no request is made)."""

    def prompt_tokens(messages: list[dict[str, str]]) -> int:
        return int(sum(len(m["content"]) for m in messages) / chars_per_token()) + 8 * len(messages)

    def first_prompt(card: NormalizedConceptCard, difficulty: str) -> int | None:
        probe = _Probe()
        generate_one(card, probe, config, difficulty=difficulty)
        return prompt_tokens(probe.messages) if probe.messages else None

    def estimate(ref: bc.CardRef, cache: Any) -> Estimate:
        card = ref.card
        plan = ac.plan_reuse(card, allow_asset_blocked=True)
        calls = 0
        expected = 0.0
        requested = 0.0
        levels = []
        for level in ac.LEVELS:
            if plan[level]["choice"] is not None:
                continue
            steps = []
            if not (cache is not None and cache.get(f"level:{level}")):
                prompt = first_prompt(card, level)
                if prompt is None:
                    continue                                # e.g. hard is not built for this lesson: no request at all
                steps.append((prompt, EXPECTED_REPLY_TOKENS[level]))
            if level in ac.FOLLOW_UP_LEVEL and not (cache is not None and cache.get(f"followup:{level}")):
                prompt = first_prompt(card, ac.FOLLOW_UP_LEVEL[level])
                if prompt is not None:
                    steps.append((prompt + FOLLOW_UP_EXTRA_PROMPT_TOKENS, EXPECTED_REPLY_TOKENS["easy"]))
            for prompt, reply in steps:
                calls += 1
                expected += (prompt + reply) * (1 + REPAIR_RATE)
                requested += (prompt + config.max_output_tokens) * (1 + REPAIR_RATE)
            if steps:
                levels.append(level)
        return Estimate(calls, int(math.ceil(expected)), int(math.ceil(requested)), tuple(levels))

    return estimate


def plan_days(estimates: list[Estimate], daily_tokens: float, daily_requests: float) -> int:
    """How many days the cards need if each day's budget is filled in order and a card is never started unless it fits."""
    days, used_tokens, used_calls = 1, 0.0, 0.0
    for estimate in estimates:
        if used_tokens + estimate.tokens > daily_tokens or used_calls + estimate.calls > daily_requests:
            if used_tokens > 0 or used_calls > 0:
                days += 1
            used_tokens, used_calls = 0.0, 0.0
        used_tokens += estimate.tokens
        used_calls += estimate.calls
    return days if estimates else 0


# ------------------------------------------------------------------------------------------------------------------ the runner

def real_builder(ref: bc.CardRef, client: Any, cache: Any, config: GenerationConfig) -> BuildResult:
    return bac.build(ref.card, config, client=client, backend="groq", proposal_cache=cache)


class BatchRunner:
    def __init__(self, settings: Settings, *, builder: Callable = real_builder, estimator: Callable | None = None,
                 inner_factory: Callable[[], Any] | None = None, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep, disk_free: Callable[[Path], int] | None = None,
                 environ: Any = None, say: Callable[[str], None] = print, stop_flag: Callable[[], bool] | None = None):
        self.s = settings
        self.config = GenerationConfig(timeout=settings.timeout, max_output_tokens=settings.max_output_tokens, max_repair_requests=settings.repairs)
        self.builder = builder
        self._estimator = estimator
        self._inner_factory = inner_factory or self._real_inner
        self.clock, self.sleep = clock, sleep
        self.disk_free = disk_free or (lambda path: shutil.disk_usage(path).free)
        self.environ = os.environ if environ is None else environ
        self.say = say
        self.stop_flag = stop_flag or (lambda: False)
        self.counts = {"built": 0, "ready": 0, "not_ready": 0, "skipped": 0, "failed": 0, "interrupted": 0}
        self.failures: dict[str, str] = {}
        self.not_ready: dict[str, list[str]] = {}
        self.levels = {level: {"reused": 0, "generated": 0, "missing": 0} for level in ac.LEVELS}
        self.verification: dict[str, int] = {}
        self.commits: list[dict[str, Any]] = []
        self.stop_reason: str | None = None
        self.resume_at: float | None = None
        self.commit_error: str | None = None
        self.push_status: dict[str, Any] = {"status": "not_attempted"}
        self._push_notice_shown = False
        self.state: bs.BatchState | None = None
        self.client: rb.BudgetedClient | None = None
        self.repo: bg.Repo | None = None
        self.refs: list[bc.CardRef] = []
        self._pending: list[bc.CardRef] = []

    # ---- setup
    def _real_inner(self) -> Any:
        args = argparse.Namespace(backend="groq", model=self.s.model, endpoint=None, reasoning_effort=None)
        try:
            return make_client(args)
        except ModelConfigError as exc:
            raise PreflightError(str(exc)) from exc

    def _estimate_fn(self, ledger_ratio: Callable[[], float] | None = None) -> Callable:
        return self._estimator or probe_estimator(self.config, ledger_ratio or (lambda: rb.RateLedger.DEFAULT_CHARS_PER_TOKEN))

    def _check_disk(self, where: str) -> None:
        target = self.s.out_root if self.s.out_root.exists() else self.s.out_root.parent
        while not target.exists() and target != target.parent:
            target = target.parent
        free = self.disk_free(target)
        if free < self.s.min_free_mb * 1024 * 1024:
            raise PreflightError(f"only {free // (1024 * 1024)} MB free on the disk holding {self.s.out_root} ({where}); "
                                 f"{self.s.min_free_mb} MB are needed. Free some space and run again")

    def _select(self) -> list[bc.CardRef]:
        try:
            bc.check_output_root(self.s.out_root, self.s.root)
            refs, problems = bc.discover(self.s.root, with_problems=True)
            chosen = bc.select(refs, subject=self.s.subject, grade=self.s.grade, module=self.s.module, lesson=self.s.lesson)
        except ValueError as exc:
            raise PreflightError(str(exc)) from exc
        self.refs = refs
        for problem in problems:
            self.say(f"note: a concept file could not be read and is skipped: {problem}")
        return chosen

    # ---- entry points
    def run(self) -> dict[str, Any]:
        chosen = self._select()
        if self.s.dry_run:
            return self._dry_run(chosen)
        return self._real_run(chosen)

    def _dry_run(self, chosen: list[bc.CardRef]) -> dict[str, Any]:
        state_path = self.s.state_dir / "state.json"
        state = bs.BatchState.load(state_path) if state_path.exists() else None
        todo = [r for r in chosen if self.s.force or state is None or not state.is_finished(r.concept_id, self.s.retry_failed)]
        finished = len(chosen) - len(todo)
        estimate = self._estimate_fn()
        rows = []
        for ref in todo:
            cache = bs.ProposalCache(self.s.state_dir / "proposals", ref.concept_id, bs.card_fingerprint(ref.card))
            rows.append((ref, estimate(ref, cache)))
        if self.s.order == "cheapest":
            rows.sort(key=lambda row: (row[1].calls, row[1].tokens))
        limits = rb.load_limits(self.s.model)
        daily_tokens = limits.tokens_per_day * (1 - rb.RateLedger.SAFETY)
        daily_requests = limits.requests_per_day * (1 - rb.RateLedger.SAFETY)
        estimates = [e for _, e in rows]
        total_tokens = sum(e.tokens for e in estimates)
        total_calls = sum(e.calls for e in estimates)
        days = plan_days(estimates, daily_tokens, daily_requests)
        minutes = max(sum(e.requested_tokens for e in estimates) / limits.tokens_per_minute, total_calls * self.s.min_gap / 60.0)
        report = {"dry_run": {
            "cards": len(rows), "already_finished": finished, "estimated_calls": total_calls, "estimated_tokens": total_tokens,
            "tokens_per_card": round(total_tokens / len(rows)) if rows else 0, "calls_per_card": round(total_calls / len(rows), 2) if rows else 0,
            "cards_per_day": (math.floor(len(rows) / days) if days else 0) if not rows else _cards_first_day(estimates, daily_tokens, daily_requests),
            "days": days, "daily_token_limit": limits.tokens_per_day, "usable_daily_tokens": int(daily_tokens),
            "daily_request_limit": limits.requests_per_day, "minimum_run_minutes": round(minutes, 1),
            "cards_with_no_model_calls": sum(1 for e in estimates if e.calls == 0),
            "per_card": [{"concept_id": r.concept_id, "calls": e.calls, "tokens": e.tokens, "levels_to_generate": list(e.levels)} for r, e in rows]},
            "counts": dict(self.counts)}
        self.say(self._dry_run_text(report["dry_run"]))
        return report

    @staticmethod
    def _dry_run_text(d: dict[str, Any]) -> str:
        lines = ["DRY RUN: no model calls were made, nothing was written or committed.",
                 f"cards to build: {d['cards']}   already finished (skipped): {d['already_finished']}",
                 f"cards that need no model call at all: {d['cards_with_no_model_calls']}",
                 f"estimated model calls: {d['estimated_calls']} ({d['calls_per_card']} per card)",
                 f"estimated tokens: {d['estimated_tokens']} ({d['tokens_per_card']} per card)",
                 f"daily limit {d['daily_token_limit']} tokens ({d['usable_daily_tokens']} used after a 5% safety margin), "
                 f"{d['daily_request_limit']} requests",
                 f"cards per day: about {d['cards_per_day']}   days needed: {d['days']}",
                 f"fastest possible wall-clock time (per-minute limit only): about {d['minimum_run_minutes']} minutes in total, "
                 "spread over those days"]
        return "\n".join(lines)

    def _real_run(self, chosen: list[bc.CardRef]) -> dict[str, Any]:
        self.s.state_dir.mkdir(parents=True, exist_ok=True)
        self._check_disk("before starting")
        with bs.RunLock(self.s.state_dir / "lock"):
            self.repo = bg.Repo(self.s.root)
            try:
                self.repo.require_repo()
                self.repo.switch_to_branch(self.s.branch)
            except bg.GitError as exc:
                raise PreflightError(str(exc)) from exc
            self.state = bs.BatchState.load(self.s.state_dir / "state.json")
            inner = self._inner_factory()
            limits = rb.load_limits(self.s.model)
            ledger = rb.RateLedger(limits, clock=self.clock, saved=self.state.data.get("ledger"))
            self.client = rb.BudgetedClient(inner, ledger, clock=self.clock, sleep=self.sleep, min_gap=self.s.min_gap,
                                            max_short_wait=self.s.max_short_wait, should_stop=self.stop_flag,
                                            log_path=self.s.state_dir / "rate_limit.jsonl", on_record=self._save_ledger)
            self.ledger = ledger
            self.secrets = bg.collect_secrets(self.environ, self.s.root / ".env")
            pending_ids = [c for c in self.state.data.get("pending_commit", [])]
            by_id = {r.concept_id: r for r in self.refs}
            self._pending = [by_id[c] for c in pending_ids if c in by_id and bc.card_paths(self.s.out_root, by_id[c])[0].exists()]
            if self.s.confirm_push:
                self._confirm_push()
            try:
                self._loop(chosen, ledger)
            except KeyboardInterrupt:
                self.stop_reason = "interrupted"
                self.say("interrupted: committing finished cards and saving state")
            finally:
                self._finish()
        return self._report()

    def _save_ledger(self) -> None:
        assert self.state is not None
        self.state.data["ledger"] = self.ledger.to_dict()
        self.state.save()

    # ---- the loop
    def _loop(self, chosen: list[bc.CardRef], ledger: rb.RateLedger) -> None:
        state = self.state
        assert state is not None and self.client is not None
        todo = [r for r in chosen if self.s.force or not state.is_finished(r.concept_id, self.s.retry_failed)]
        self.say(f"{len(chosen)} cards selected, {len(chosen) - len(todo)} already finished, {len(todo)} to build")
        resume = state.data.get("resume_at")
        if todo and resume and resume > self.clock():
            self.stop_reason = "waiting_for_daily_reset"
            self.resume_at = resume
            self.say(f"the last run stopped for the day; it can resume after {_when(resume)}")
            return
        state.data["resume_at"] = None
        estimate = self._estimate_fn(lambda: ledger.chars_per_token)
        sized: dict[str, Estimate] = {}
        if self.s.order == "cheapest":
            for ref in todo:
                cache = self._cache(ref)
                sized[ref.concept_id] = estimate(ref, cache)
            todo.sort(key=lambda r: (sized[r.concept_id].calls, sized[r.concept_id].tokens))
        built_now = 0
        for ref in todo:
            if self.stop_flag():
                self.stop_reason = "stop_requested"
                return
            if self.s.limit is not None and built_now >= self.s.limit:
                self.stop_reason = "limit_reached"
                return
            try:
                self._check_disk("before the next card")
            except PreflightError as exc:
                self.stop_reason = "low_disk"
                self.say(str(exc))
                return
            cache = self._cache(ref)
            est = sized.get(ref.concept_id) or estimate(ref, cache)
            if est.tokens > ledger.limits.tokens_per_day * (1 - ledger.safety):
                state.record(ref.concept_id, "skipped", reason=f"its estimated cost ({est.tokens} tokens) is more than a whole day's budget")
                self.counts["skipped"] += 1
                state.save()
                continue
            if est.tokens > ledger.remaining_daily_tokens() or est.calls > ledger.remaining_daily_requests():
                self.stop_reason = "daily_budget"
                self.resume_at = self.clock() + ledger.seconds_until_daily_fits(est.tokens)
                state.data["resume_at"] = self.resume_at
                self.say(f"stopping: the remaining daily budget cannot cover {ref.concept_id} (about {est.tokens} tokens); "
                         f"resume after {_when(self.resume_at)}")
                return
            outcome = self._build_one(ref, cache)
            state.save()
            if outcome == "built":
                built_now += 1
                if len(self._pending) >= self.s.commit_every and not self._commit_pending():
                    return
            elif outcome == "stop":
                return
        if self.stop_reason is None:
            self.stop_reason = "finished"

    def _cache(self, ref: bc.CardRef) -> bs.ProposalCache:
        return bs.ProposalCache(self.s.state_dir / "proposals", ref.concept_id, bs.card_fingerprint(ref.card))

    def _build_one(self, ref: bc.CardRef, cache: bs.ProposalCache) -> str:
        """Returns 'built', 'failed' (go on to the next card) or 'stop'."""
        state, client = self.state, self.client
        assert state is not None and client is not None
        calls_before, tokens_before = client.calls, client.tokens_used
        started = self.clock()
        try:
            result = self.builder(ref, client, cache, self.config)
        except Exception as exc:  # noqa: BLE001 - one bad card must never end a long run
            return self._fail(ref, f"{type(exc).__name__}: {exc}", calls_before, tokens_before, crash=traceback.format_exc())
        spent = {"calls": client.calls - calls_before, "tokens": client.tokens_used - tokens_before}
        provider_failure = result.run.get("provider_failure")
        if client.halt or provider_failure or (self.stop_flag() and result.card is None):
            return self._interrupt(ref, provider_failure, spent)
        if result.card is None:
            return self._fail(ref, _failure_reason(result), calls_before, tokens_before)
        try:
            bc.write_card_files(self.s.out_root, ref, result.card, result.audit)
        except OSError as exc:
            state.record(ref.concept_id, "interrupted", reason=f"could not write the card: {exc}", **spent)
            self.counts["interrupted"] += 1
            self.stop_reason = "write_failed"
            return "stop"
        ready = bool(result.card["readiness"]["ready_for_delivery"])
        state.record(ref.concept_id, "built_ready" if ready else "built_not_ready", seconds=round(self.clock() - started, 1),
                     levels=_level_summary(result.card), **spent)
        cache.clear()
        self.counts["built"] += 1
        self.counts["ready" if ready else "not_ready"] += 1
        if not ready:
            self.not_ready[ref.concept_id] = list(result.card["readiness"]["blocking_issues"])
        self._tally(result.card)
        self._pending.append(ref)
        state.data["pending_commit"] = [r.concept_id for r in self._pending]
        return "built"

    def _fail(self, ref: bc.CardRef, reason: str, calls_before: int, tokens_before: int, crash: str | None = None) -> str:
        state, client = self.state, self.client
        assert state is not None and client is not None
        state.record(ref.concept_id, "failed", reason=reason[:1200], calls=client.calls - calls_before, tokens=client.tokens_used - tokens_before)
        self.counts["failed"] += 1
        self.failures[ref.concept_id] = reason[:1200]
        if crash:
            try:
                crashes = self.s.state_dir / "crashes"
                crashes.mkdir(parents=True, exist_ok=True)
                (crashes / f"{ref.concept_id}.txt").write_text(crash, encoding="utf-8")
            except OSError:
                pass
        self.say(f"FAILED {ref.concept_id}: {reason[:300]}")
        return "failed"

    def _interrupt(self, ref: bc.CardRef, provider_failure: str | None, spent: dict[str, int]) -> str:
        state, client = self.state, self.client
        assert state is not None and client is not None
        halt = client.halt or {}
        if self.stop_flag():
            reason = "stop_requested"
        elif halt:
            reason = {"daily_limit": "daily_limit", "daily_budget": "daily_budget", "wait_too_long": "rate_limit_wait_too_long"}.get(halt.get("reason"), halt.get("reason", "halt"))
        else:
            reason = f"provider_failure:{provider_failure}"
        self.stop_reason = reason
        resume = halt.get("resume_at") if halt else None
        if resume is None and reason.startswith("provider_failure"):
            resume = self.clock() + PROVIDER_RETRY_SECONDS
        if reason != "stop_requested" and resume is not None:
            self.resume_at = resume
            state.data["resume_at"] = resume
        state.record(ref.concept_id, "interrupted", reason=reason, **spent)
        self.counts["interrupted"] += 1
        self.say(f"stopped during {ref.concept_id} ({reason}); that card is discarded and will be rebuilt next run, "
                 "reusing the model answers already accepted"
                 + (f"; resume after {_when(resume)}" if resume and reason != "stop_requested" else ""))
        return "stop"

    def _tally(self, card: dict[str, Any]) -> None:
        present = set()
        for question in card.get("questions", []):
            level = question.get("difficulty")
            origin = question.get("origin")
            if level in self.levels and origin in ("reused", "generated"):
                self.levels[level][origin] += 1
                present.add(level)
            label = question.get("answer_verification")
            if label:
                self.verification[label] = self.verification.get(label, 0) + 1
        for level in ac.LEVELS:
            if level not in present:
                self.levels[level]["missing"] += 1

    # ---- commits and pushes
    def _commit_pending(self) -> bool:
        """Commit the finished cards. Returns False when the run must stop (a possible secret, or git is not working)."""
        if not self._pending or self.repo is None or self.state is None:
            return True
        touched = {r.module_key: r for r in self._pending}
        paths: list[Path] = []
        for ref in self._pending:
            paths.extend(bc.card_paths(self.s.out_root, ref))
        for key in touched:
            paths.append(bc.rebuild_module_index(self.s.out_root, self.refs, key))
        message = bg.commit_message([(r.module_key, r.lesson) for r in self._pending])
        try:
            sha = self.repo.commit(paths, message, secrets=self.secrets)
        except bg.GitError as exc:
            self.commit_error = str(exc)
            self.stop_reason = "commit_failed"
            self.say(f"COMMIT FAILED: {exc}")
            return False
        self.commits.append({"commit": sha[:10], "message": message, "cards": [r.concept_id for r in self._pending]})
        self.state.data["commits"].append({"commit": sha, "message": message, "cards": [r.concept_id for r in self._pending]})
        self.state.data["pending_commit"] = []
        self.state.data["unpushed"] = True
        self._pending = []
        self.state.save()
        self.say(f"committed: {message} ({sha[:10]})")
        self._push()
        return True

    def _confirm_push(self) -> None:
        assert self.repo is not None and self.state is not None
        url = self.repo.remote_url(self.s.remote)
        self.say(f"git remote -v:\n{self.repo.remotes_text() or '(no remotes)'}\ncurrent branch: {self.repo.branch()}")
        if url is None:
            self.say(f"there is no remote called {self.s.remote!r}; nothing can be pushed")
            return
        self.state.data["push_confirmed"] = {"remote": self.s.remote, "url": url, "branch": self.s.branch}
        self.state.save()
        self.say(f"push confirmed for {self.s.remote} ({url}) branch {self.s.branch}")

    def _push(self) -> None:
        assert self.repo is not None and self.state is not None
        if not self.s.push:
            self.push_status = {"status": "disabled"}
            return
        url = self.repo.remote_url(self.s.remote)
        if url is None:
            self.push_status = {"status": "no_remote"}
            return
        confirmed = self.state.data.get("push_confirmed") or {}
        if not (confirmed.get("remote") == self.s.remote and confirmed.get("url") == url and confirmed.get("branch") == self.s.branch):
            self.push_status = {"status": "waiting_for_confirmation"}
            if not self._push_notice_shown:
                self._push_notice_shown = True
                self.say(f"PUSH PAUSED until you confirm the destination.\ngit remote -v:\n{self.repo.remotes_text()}\n"
                         f"current branch: {self.repo.branch()}  (commits go to {self.s.branch}; main is never pushed)\n"
                         "Commits are kept locally. After checking, run again with --confirm-push to allow pushing.")
            return
        try:
            self.repo.push(self.s.remote, self.s.branch)
        except bg.GitError as exc:
            self.push_status = {"status": "failed", "error": str(exc)}
            self.say(f"push failed (commits are kept locally and the push is retried at the next commit point): {exc}")
            return
        self.state.data["unpushed"] = False
        self.state.save()
        self.push_status = {"status": "pushed"}

    def _finish(self) -> None:
        """Always runs: commit what is complete, retry a push, save state."""
        try:
            if self.stop_reason != "commit_failed":
                self._commit_pending()
                if self.state is not None and self.state.data.get("unpushed") and self.repo is not None and self.push_status["status"] in ("not_attempted", "failed"):
                    self._push()
        finally:
            if self.state is not None:
                self.state.data["stop_reason"] = self.stop_reason
                try:
                    self.state.save()
                except OSError:
                    pass

    # ---- report
    def _report(self) -> dict[str, Any]:
        client = self.client
        observations = list(client.observations) if client else []
        statuses = [o.get("status") for o in observations]
        limits_seen = {}
        for observation in observations:
            for name, value in (observation.get("headers") or {}).items():
                if name.startswith("x-ratelimit-limit"):
                    limits_seen[name] = value
        remaining = [int(o["headers"]["x-ratelimit-remaining-tokens"]) for o in observations
                     if (o.get("headers") or {}).get("x-ratelimit-remaining-tokens", "").isdigit()]
        report = {
            "counts": dict(self.counts), "levels": self.levels, "verification": self.verification, "failures": self.failures,
            "not_ready": self.not_ready, "commits": self.commits, "commit_error": self.commit_error, "push": self.push_status,
            "stop_reason": self.stop_reason, "resume_at": self.resume_at,
            "calls": client.calls if client else 0, "tokens": client.tokens_used if client else 0,
            "rate_limit": {"wait_seconds": round(client.wait_seconds, 1) if client else 0.0, "waits": len(client.waits) if client else 0,
                           "rate_limited_429": statuses.count(429), "limits_seen_in_headers": limits_seen,
                           "lowest_tokens_remaining_seen": min(remaining) if remaining else None,
                           "daily_tokens_used_now": self.ledger.tokens_last(86400) if client else 0}}
        try:
            bc.atomic_write(self.s.state_dir / "last_report.json", report)
        except OSError:
            pass
        self.say(self._report_text(report))
        return report

    @staticmethod
    def _report_text(r: dict[str, Any]) -> str:
        c = r["counts"]
        lines = ["", "=== batch report ===",
                 f"built {c['built']} (ready {c['ready']}, not ready {c['not_ready']})   skipped {c['skipped']}   failed {c['failed']}   "
                 f"interrupted {c['interrupted']}",
                 "per level (reused / generated / missing): " + ", ".join(f"{k} {v['reused']}/{v['generated']}/{v['missing']}" for k, v in r["levels"].items()),
                 f"answers: {r['verification'] or 'none'}",
                 f"model calls {r['calls']}, tokens {r['tokens']}, waited {r['rate_limit']['wait_seconds']}s over {r['rate_limit']['waits']} waits, "
                 f"429s {r['rate_limit']['rate_limited_429']}",
                 f"commits {len(r['commits'])}; push: {r['push']['status']}",
                 f"stopped because: {r['stop_reason']}" + (f" (resume after {_when(r['resume_at'])})" if r["resume_at"] else "")]
        for key, reasons in r["not_ready"].items():
            lines.append(f"  not ready {key}: " + " | ".join(x[:140] for x in reasons))
        for key, reason in r["failures"].items():
            lines.append(f"  failed {key}: {reason[:200]}")
        lines.append("Tip: run long jobs under `caffeinate -i` so the Mac does not sleep, for example: caffeinate -i python3 build_all_assessment_cards.py")
        return "\n".join(lines)


def _cards_first_day(estimates: list[Estimate], daily_tokens: float, daily_requests: float) -> int:
    used_tokens = used_calls = 0.0
    count = 0
    for estimate in estimates:
        if used_tokens + estimate.tokens > daily_tokens or used_calls + estimate.calls > daily_requests:
            break
        used_tokens += estimate.tokens
        used_calls += estimate.calls
        count += 1
    return count


def _when(timestamp: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(timestamp)) if timestamp else "unknown"


def _level_summary(card: dict[str, Any]) -> dict[str, Any]:
    return {q["difficulty"]: {"origin": q.get("origin"), "answer_verification": q.get("answer_verification")} for q in card.get("questions", [])}


def _failure_reason(result: BuildResult) -> str:
    errors = result.run.get("errors") or {}
    if not errors:
        return "no card was built (fewer than 2 of 3 levels could be produced)"
    return "; ".join(f"{key}: {value}" for key, value in errors.items())

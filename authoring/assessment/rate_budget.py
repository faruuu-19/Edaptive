"""Rate-limit and daily-budget handling for long unattended runs against Groq's free tier.

Nothing here is hardcoded: the starting limits live in ``groq_limits.json``, every response's ``x-ratelimit-*`` headers
override them, and every 429 message ("Limit N, Used M, Requested R. Please try again in X") is read, not guessed at.
The ledger keeps its own rolling record of tokens actually used (from each response's ``usage``) so a daily total survives
a restart. ``BudgetedClient`` paces BEFORE each call, waits out a short per-minute 429, and stops cleanly on a daily one.
"""
from __future__ import annotations

import dataclasses
import json
import random
import re
import time
from pathlib import Path
from typing import Any, Callable

from question_generator import ModelRequestError, QuotaExhaustedError, RateLimitError

LIMITS_FILE = Path(__file__).with_name("groq_limits.json")
DAY = 86400.0
MINUTE = 60.0


class TooBigForOneMinute(Exception):
    """A single request is larger than the per-minute token limit: it can never be sent, however long we wait."""


class StopRequested(QuotaExhaustedError):
    """The operator asked to stop (Ctrl-C). A kind of provider stop, so a build in progress ends instead of carrying on."""

    def __init__(self, message: str = "stop requested"):
        super().__init__(message)


@dataclasses.dataclass(frozen=True)
class Limits:
    requests_per_minute: int
    requests_per_day: int
    tokens_per_minute: int
    tokens_per_day: int
    source: str = ""


def load_limits(model: str, path: Path | str | None = None) -> Limits:
    data = json.loads(Path(path or LIMITS_FILE).read_text(encoding="utf-8"))
    entry = data["models"][model]          # KeyError for an unknown model: never guess a limit
    return Limits(int(entry["requests_per_minute"]), int(entry["requests_per_day"]), int(entry["tokens_per_minute"]),
                  int(entry["tokens_per_day"]), str(data.get("source", "")))


def apply_headers(limits: Limits, headers: Any) -> Limits:
    """Limits as the provider states them on a response. ``limit-requests`` is per day, ``limit-tokens`` per minute."""
    seen = _lower(headers)
    changes = {}
    for header, field in (("x-ratelimit-limit-requests", "requests_per_day"), ("x-ratelimit-limit-tokens", "tokens_per_minute")):
        value = _number(seen.get(header))
        if value is not None and value > 0:
            changes[field] = int(value)
    return dataclasses.replace(limits, **changes) if changes else limits


_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|d|h|m|s)")
_DURATION_ALL = re.compile(r"(?:\d+(?:\.\d+)?(?:ms|d|h|m|s))+")
_UNIT_SECONDS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}


def parse_duration(text: Any) -> float | None:
    """Groq's duration strings: '2m59.56s', '34.755s', '450ms', '1h5m3s'. None for anything else."""
    if not isinstance(text, str) or not _DURATION_ALL.fullmatch(text.strip()):
        return None
    return sum(float(number) * _UNIT_SECONDS[unit] for number, unit in _DURATION_PART.findall(text.strip()))


def parse_429(body: Any) -> dict[str, Any]:
    """Read a Groq 429 message: which limit (RPM/RPD/TPM/TPD), its limit/used/requested numbers, and how long to wait."""
    message = ""
    if isinstance(body, str):
        message = body
        try:
            error = json.loads(body).get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                message = error["message"]
        except (json.JSONDecodeError, AttributeError):
            pass
    kind = "unknown"
    named = re.search(r"\((RPD|TPD|RPM|TPM)\)", message)
    if named:
        kind = named.group(1)
    else:
        phrase = re.search(r"(requests|tokens) per (day|minute)", message)
        if phrase:
            kind = ("R" if phrase.group(1) == "requests" else "T") + ("PD" if phrase.group(2) == "day" else "PM")
    numbers = re.search(r"Limit (\d+), Used (\d+), Requested (\d+)", message)
    retry = re.search(r"try again in ((?:\d+(?:\.\d+)?(?:ms|d|h|m|s))+)", message)
    return {"kind": kind, "daily": kind in ("RPD", "TPD"),
            "limit": int(numbers.group(1)) if numbers else None, "used": int(numbers.group(2)) if numbers else None,
            "requested": int(numbers.group(3)) if numbers else None,
            "retry_after": parse_duration(retry.group(1)) if retry else None}


def _lower(headers: Any) -> dict[str, Any]:
    try:
        return {str(name).lower(): value for name, value in headers.items()} if headers else {}
    except AttributeError:
        return {}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class RateLedger:
    """Our own rolling record of requests and tokens, kept across restarts through ``to_dict`` / ``saved``.

    Events are [time, tokens, expires]. ``expires`` is only set on a synthetic event added when the provider told us (in a
    429) that more was used than we had counted; such an event counts toward the daily total only until the provider's own
    retry time, then disappears, so a restart after the stated wait is not blocked by a stale guess.
    """

    DEFAULT_CHARS_PER_TOKEN = 3.5            # measured 3.63-3.71 on five live calls (artifacts/prompt-size/calibration.json); 3.5 is slightly high on purpose, then learned from usage
    SAFETY = 0.05

    def __init__(self, limits: Limits, *, clock: Callable[[], float] = time.time, saved: dict[str, Any] | None = None,
                 safety: float | None = None):
        self.limits = limits
        self._clock = clock
        self.safety = self.SAFETY if safety is None else safety
        self.events: list[list[Any]] = []
        self.resume_at: float | None = None
        self.chars_per_token = self.DEFAULT_CHARS_PER_TOKEN
        self.header_remaining_requests: int | None = None
        self.header_remaining_tokens: int | None = None
        self._header_reset_at: float | None = None
        if saved:
            self.events = [list(event) for event in saved.get("events", [])]
            self.resume_at = saved.get("resume_at")
            self.chars_per_token = float(saved.get("chars_per_token") or self.DEFAULT_CHARS_PER_TOKEN)

    # ---- persistence
    def to_dict(self) -> dict[str, Any]:
        self._prune()
        return {"events": self.events, "resume_at": self.resume_at, "chars_per_token": round(self.chars_per_token, 4)}

    def _prune(self) -> None:
        now = self._clock()
        self.events = [e for e in self.events if e[0] > now - DAY and not (len(e) > 2 and e[2] is not None and e[2] <= now)]

    # ---- recording
    def record(self, tokens: int) -> None:
        self.events.append([self._clock(), int(tokens), None])

    def sync_from_429(self, parsed: dict[str, Any], retry_after: float | None = None) -> None:
        """Bring the ledger in line with what a 429 says was used, and remember when the provider says to come back."""
        now = self._clock()
        wait = parsed.get("retry_after") if parsed.get("retry_after") is not None else retry_after
        if parsed.get("kind") == "TPD" and parsed.get("used") is not None:
            extra = parsed["used"] - self.tokens_last(DAY)
            if extra > 0:
                self.events.append([now, int(extra), now + (wait if wait is not None else DAY)])
        if parsed.get("daily"):
            self.resume_at = now + (wait if wait is not None else DAY)

    def update_from_headers(self, headers: Any) -> None:
        seen = _lower(headers)
        now = self._clock()
        remaining_requests = _number(seen.get("x-ratelimit-remaining-requests"))
        if remaining_requests is not None:
            self.header_remaining_requests = int(remaining_requests)
        remaining_tokens = _number(seen.get("x-ratelimit-remaining-tokens"))
        if remaining_tokens is not None:
            self.header_remaining_tokens = int(remaining_tokens)
            reset = parse_duration(seen.get("x-ratelimit-reset-tokens"))
            self._header_reset_at = now + reset if reset is not None else now + MINUTE
        self.limits = apply_headers(self.limits, headers)

    # ---- reading
    def _window(self, seconds: float, *, with_synthetic: bool) -> list[list[Any]]:
        self._prune()
        now = self._clock()
        return [e for e in self.events if e[0] > now - seconds and (with_synthetic or len(e) < 3 or e[2] is None)]

    def tokens_last(self, seconds: float) -> int:
        return sum(e[1] for e in self._window(seconds, with_synthetic=seconds >= DAY))

    def requests_last(self, seconds: float) -> int:
        return len([e for e in self._window(seconds, with_synthetic=False)])

    def remaining_daily_tokens(self) -> int:
        return int(self.limits.tokens_per_day - self.tokens_last(DAY) - self.safety * self.limits.tokens_per_day)

    def remaining_daily_requests(self) -> int:
        own = int(self.limits.requests_per_day - self.requests_last(DAY) - self.safety * self.limits.requests_per_day)
        if self.header_remaining_requests is not None:
            own = min(own, int(self.header_remaining_requests - self.safety * self.limits.requests_per_day))
        return own

    def wait_for_minute(self, tokens: int) -> float:
        """Seconds to wait before a request of ``tokens`` fits in the per-minute token and request limits."""
        if tokens > self.limits.tokens_per_minute:
            raise TooBigForOneMinute(f"a request of about {tokens} tokens is larger than the per-minute limit of {self.limits.tokens_per_minute}")
        now = self._clock()
        recent = sorted(self._window(MINUTE, with_synthetic=False), key=lambda e: e[0])
        waits = [0.0]
        over = sum(e[1] for e in recent) + tokens - self.limits.tokens_per_minute
        freed = 0
        for event in recent:
            if over <= 0:
                break
            freed += event[1]
            if freed >= over:
                waits.append(event[0] + MINUTE - now)
                break
        over_requests = len(recent) + 1 - self.limits.requests_per_minute
        if over_requests > 0:
            waits.append(recent[over_requests - 1][0] + MINUTE - now)
        if (self.header_remaining_tokens is not None and self._header_reset_at is not None and now < self._header_reset_at
                and tokens > self.header_remaining_tokens):
            waits.append(self._header_reset_at - now)
        return max(0.0, *waits)

    def seconds_until_daily_fits(self, tokens: int) -> float:
        """How long until the oldest events leave the 24h window enough for ``tokens`` to fit (the provider's resume time if known)."""
        now = self._clock()
        if self.resume_at is not None and self.resume_at > now:
            return self.resume_at - now
        budget = self.limits.tokens_per_day * (1 - self.safety)
        need = self.tokens_last(DAY) + tokens - budget
        freed = 0
        for event in sorted(self._window(DAY, with_synthetic=True), key=lambda e: e[0]):
            freed += event[1]
            if freed >= need:
                return max(0.0, event[0] + DAY - now)
        return DAY

    # ---- token estimates
    def estimate_prompt_tokens(self, messages: list[dict[str, str]]) -> int:
        chars = sum(len(str(m.get("content", ""))) for m in messages)
        return int(chars / self.chars_per_token) + 8 * len(messages)

    def learn_ratio(self, chars: int, prompt_tokens: int) -> None:
        if chars > 0 and prompt_tokens > 0:
            ratio = chars / prompt_tokens
            self.chars_per_token = 0.7 * self.chars_per_token + 0.3 * min(max(ratio, 1.5), 6.0)


class BudgetedClient:
    """Wrap a Groq client: pace before every call, wait out a short per-minute 429, stop cleanly on a daily limit.

    ``halt`` is set whenever the run should stop for the day: {"reason", "daily", "resume_at"}. The inner client must not do
    its own waiting (its retries are set to zero here), so every wait is decided, bounded and logged in one place.
    """

    def __init__(self, inner: Any, ledger: RateLedger, *, clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                 jitter: Callable[[], float] | None = None, min_gap: float = 0.0, max_short_wait: float = 120.0, retries: int = 2,
                 should_stop: Callable[[], bool] | None = None, log_path: Path | str | None = None,
                 on_record: Callable[[], None] | None = None):
        if hasattr(inner, "max_rate_limit_retries"):
            inner.max_rate_limit_retries = 0
        self._inner, self.ledger, self._clock, self._sleep = inner, ledger, clock, sleep
        self._jitter = jitter or (lambda: random.uniform(0.0, 1.5))
        self.min_gap, self.max_short_wait, self.retries = min_gap, max_short_wait, retries
        self._should_stop = should_stop
        self._log_path = Path(log_path) if log_path else None
        self._on_record = on_record
        self._last_end: float | None = None
        self.halt: dict[str, Any] | None = None
        self.calls = 0
        self.tokens_used = 0
        self.wait_seconds = 0.0
        self.waits: list[dict[str, Any]] = []

    @property
    def observations(self) -> list[dict[str, Any]]:
        return self._inner.observations

    def __getattr__(self, name: str) -> Any:        # backend_name, model, list_models, last_served_by ...
        return getattr(self._inner, name)

    # ---- helpers
    def _log(self, event: str, **fields: Any) -> None:
        if self._log_path is None:
            return
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock())), "event": event, **fields}
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        except OSError:
            pass                                    # a full disk must not turn into a model failure; the state file reports disk problems

    def _check_stop(self) -> None:
        if self._should_stop is not None and self._should_stop():
            raise StopRequested("stop requested; the current card is not continued")

    def _wait(self, seconds: float, why: str) -> None:
        if seconds <= 0:
            return
        self.waits.append({"seconds": round(seconds, 2), "why": why})
        self.wait_seconds += seconds
        self._log("wait", seconds=round(seconds, 2), why=why)
        if self._should_stop is None:
            self._sleep(seconds)
            return
        end = self._clock() + seconds
        while True:
            left = end - self._clock()
            if left <= 0:
                break
            self._check_stop()
            self._sleep(min(1.0, left))

    def _set_halt(self, reason: str, *, daily: bool, resume_at: float | None) -> None:
        self.halt = {"reason": reason, "daily": daily, "resume_at": resume_at}
        self._log("halt", reason=reason, daily=daily, resume_at=resume_at)

    # ---- the call
    def chat(self, messages: list[dict[str, str]], *, timeout: float, max_output_tokens: int) -> str:
        self._check_stop()
        estimate = self.ledger.estimate_prompt_tokens(messages) + max_output_tokens
        if estimate > self.ledger.remaining_daily_tokens() or self.ledger.remaining_daily_requests() < 1:
            wait = self.ledger.seconds_until_daily_fits(estimate)
            self._set_halt("daily_budget", daily=True, resume_at=self._clock() + wait)
            raise QuotaExhaustedError(f"the daily budget cannot cover this request (about {estimate} tokens); no request was made")
        attempt = 0
        while True:
            if self._last_end is not None and self.min_gap > 0:
                self._wait(self.min_gap - (self._clock() - self._last_end), "minimum gap between requests")
            try:
                wait = self.ledger.wait_for_minute(estimate)
            except TooBigForOneMinute as exc:
                raise ModelRequestError(str(exc), status=413) from exc
            if wait > self.max_short_wait:
                self._set_halt("wait_too_long", daily=False, resume_at=self._clock() + wait)
                raise RateLimitError(f"the per-minute limit needs a wait of {wait:.0f}s, longer than the {self.max_short_wait:.0f}s allowed", None, wait)
            self._wait(wait + (self._jitter() if wait > 0 else 0.0), "per-minute budget")
            self._check_stop()
            before = self._inner.last_observation
            self.calls += 1
            try:
                text = self._inner.chat(messages, timeout=timeout, max_output_tokens=max_output_tokens)
            except RateLimitError as exc:
                self._last_end = self._clock()
                parsed = parse_429(exc.raw_response)
                self._log("rate_limited", status=429, kind=parsed["kind"], limit=parsed["limit"], used=parsed["used"],
                          requested=parsed["requested"], retry_after=parsed["retry_after"])
                if isinstance(exc, QuotaExhaustedError) or parsed["daily"]:
                    self.ledger.sync_from_429(parsed, exc.retry_after)
                    resume = self.ledger.resume_at or (self._clock() + (exc.retry_after or DAY))
                    self._set_halt("daily_limit", daily=True, resume_at=resume)
                    if isinstance(exc, QuotaExhaustedError):
                        raise
                    raise QuotaExhaustedError(str(exc), exc.raw_response, exc.retry_after, "message") from exc
                retry = parsed["retry_after"] if parsed["retry_after"] is not None else exc.retry_after
                if retry is None or retry > self.max_short_wait:
                    self._set_halt("wait_too_long", daily=False, resume_at=self._clock() + (retry if retry is not None else self.max_short_wait))
                    raise
                if attempt >= self.retries:
                    raise
                attempt += 1
                self._wait(retry + self._jitter(), "per-minute 429")
                continue
            except BaseException:
                self._last_end = self._clock()
                self._account(before, messages, estimate)      # a reply that arrived but was unusable still used tokens
                raise
            self._last_end = self._clock()
            self._account(before, messages, estimate)
            return text

    def _account(self, before: Any, messages: list[dict[str, str]], estimate: int) -> None:
        observation = self._inner.last_observation
        if observation is None or observation is before or observation.get("status") != 200:
            return
        usage = observation.get("usage") or {}
        total = usage.get("total_tokens")
        tokens = int(total) if isinstance(total, (int, float)) else estimate
        self.ledger.record(tokens)
        self.tokens_used += tokens
        self.ledger.update_from_headers(observation.get("headers"))
        prompt_tokens = usage.get("prompt_tokens")
        if isinstance(prompt_tokens, (int, float)):
            self.ledger.learn_ratio(sum(len(str(m.get("content", ""))) for m in messages), int(prompt_tokens))
        headers = observation.get("headers") or {}
        if self._on_record is not None:
            self._on_record()
        self._log("response", status=200, tokens=tokens, usage=usage,
                  remaining_requests=headers.get("x-ratelimit-remaining-requests"), remaining_tokens=headers.get("x-ratelimit-remaining-tokens"),
                  reset_tokens=headers.get("x-ratelimit-reset-tokens"), reset_requests=headers.get("x-ratelimit-reset-requests"))

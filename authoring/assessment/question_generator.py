"""Generate one draft maths root-question proposal from teaching content."""

from __future__ import annotations

import json
import http.client
import math
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any, Protocol

import sympy

from concept_card_loader import NormalizedConceptCard, TeachingItem
import calc_tasks
import calculator
import lesson_profile as lp
from task_contract import (HARD_KINDS, KIND_OPERATIONS, ROLES, TEMPLATES, VERSION as TASK_VERSION, is_situation_task, kinds_for_operations,
                           kinds_for_rules, render_part_instruction, validate_task)


class ModelRequestError(Exception):
    """A request to the provider failed. ``status`` is the HTTP status when there was one; ``kind`` says what sort of failure it
    was when there was no status ("unreachable", "bad_response", "length"). Together they decide whether it is the whole batch's
    problem (a bad key, the provider down) or only this one question's (a rejected request, an over-long reply)."""

    def __init__(self, message: str, raw_response: str | None = None, *, status: int | None = None, kind: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response
        self.status = status
        self.kind = kind


class RateLimitError(ModelRequestError):
    """The provider answered 429. Carries the provider's retry-after hint; never retried without bound."""

    def __init__(self, message: str, raw_response: str | None = None, retry_after: float | None = None):
        super().__init__(message, raw_response)
        self.retry_after = retry_after


class QuotaExhaustedError(RateLimitError):
    """Groq reported that a per-DAY quota (RPD/TPD) is used up. Waiting a minute cannot help, so it is never retried."""

    def __init__(self, message: str, raw_response: str | None = None, retry_after: float | None = None,
                 signal: str = ""):
        super().__init__(message, raw_response, retry_after)
        self.signal = signal


def classify_groq_429(body: str, headers: Any = None) -> tuple[str, str]:
    """Decide what kind of 429 Groq sent, using only what the response states.

    Returns (kind, signal) with kind in 'daily_quota', 'per_minute' or 'unknown'.
    1. The error message names the limit that was hit, e.g. "on tokens per minute (TPM)" or "(RPD)"/"(TPD)".
    2. Otherwise Groq's documented header x-ratelimit-remaining-requests (always the per-DAY request quota) at 0.
    Anything else is 'unknown' and is handled exactly like a transient limit: no fallback.
    """
    message = body
    try:
        error = json.loads(body).get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            message = error["message"]
    except (json.JSONDecodeError, AttributeError):
        pass
    named = re.search(r"\((RPD|TPD|RPM|TPM)\)", message)
    if named:
        return ("daily_quota" if named.group(1) in ("RPD", "TPD") else "per_minute"), f"message:({named.group(1)})"
    phrase = re.search(r"per (day|minute)\b", message)
    if phrase:
        return ("daily_quota" if phrase.group(1) == "day" else "per_minute"), f"message:per {phrase.group(1)}"
    remaining = headers.get("x-ratelimit-remaining-requests") if headers else None
    if remaining is not None and remaining.strip() in ("0", "0.0"):
        return "daily_quota", "header:x-ratelimit-remaining-requests=0"
    return "unknown", "no period named in message or headers"


class ModelConfigError(Exception):
    """A backend cannot be used as configured (for example a missing API key). Raised before any request."""


class ModelClient(Protocol):
    def chat(self, messages: list[dict[str, str]], *, timeout: float, max_output_tokens: int) -> str: ...


@dataclass(frozen=True)
class GenerationConfig:
    timeout: float = 45.0
    max_output_tokens: int = 512
    max_repair_requests: int = 1
    max_explanations: int = 3
    max_examples: int = 1
    max_item_chars: int = 500

    def __post_init__(self):
        if self.timeout <= 0 or self.max_output_tokens < 64 or not 0 <= self.max_repair_requests <= 1:
            raise ValueError("timeout must be positive, output limit at least 64, repairs 0 or 1")
        if self.max_explanations < 1 or self.max_examples < 1 or self.max_item_chars < 80:
            raise ValueError("teaching limits must allow at least one item and 80 characters")


@dataclass(frozen=True)
class AttemptLog:
    attempt: int
    elapsed_seconds: float
    raw_response: str | None
    validation_reason: str | None
    returned_model_text: bool = False
    served_by: str | None = None


@dataclass(frozen=True)
class GenerationError:
    code: str
    message: str


@dataclass(frozen=True)
class GenerationResult:
    proposal: dict[str, Any] | None
    error: GenerationError | None
    attempts: tuple[AttemptLog, ...]
    elapsed_seconds: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_provider_response(response: Any, provider: str, timeout: float) -> str:
    """Read/decode one API body, retaining partial bytes from known read failures."""
    try:
        body = response.read()
    except (socket.timeout, TimeoutError) as exc:
        raise TimeoutError(f"model request exceeded {timeout:g}s timeout") from exc
    except (OSError, http.client.HTTPException) as exc:
        partial = getattr(exc, "partial", None)
        raw = partial.decode("utf-8", errors="replace") if isinstance(partial, bytes) else None
        raise ModelRequestError(f"{provider} response read failed: {exc}", raw, kind="unreachable") from exc
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ModelRequestError(f"{provider} returned invalid UTF-8 response", body.decode("utf-8", errors="replace"), kind="bad_response") from exc


class OllamaClient:
    """Small local Ollama chat client. It checks installed models and never pulls one."""
    backend_name = "ollama"

    def __init__(self, endpoint: str = "http://127.0.0.1:11434", model: str = "qwen3:8b"):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self._checked = False

    def _post_or_get(self, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint + path,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = _read_provider_response(response, "Ollama", timeout)
        except urllib.error.HTTPError as exc:
            raw = _read_provider_response(exc, "Ollama", timeout)
            raise ModelRequestError(f"Ollama HTTP {exc.code}: {raw[:300]}", raw, status=exc.code) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
                raise TimeoutError(f"model request exceeded {timeout:g}s timeout") from exc
            raise ModelRequestError(f"cannot reach Ollama: {exc}", kind="unreachable") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ModelRequestError("Ollama returned malformed API JSON", raw, kind="bad_response") from exc
        if not isinstance(result, dict):
            raise ModelRequestError("Ollama API response is not an object", raw, kind="bad_response")
        return result

    def chat(self, messages: list[dict[str, str]], *, timeout: float, max_output_tokens: int) -> str:
        if not self._checked:
            tags = self._post_or_get("/api/tags", None, timeout)
            models = tags.get("models")
            if not isinstance(models, list):
                raise ModelRequestError("Ollama response has no models array", json.dumps(tags))
            installed = {item.get("name") for item in models if isinstance(item, dict)}
            if self.model not in installed:
                raise ModelRequestError(f"model {self.model!r} is not installed; no download was attempted")
            self._checked = True
        response = self._post_or_get(
            "/api/chat",
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"temperature": 0.2, "num_predict": max_output_tokens},
            },
            timeout,
        )
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ModelRequestError("Ollama response has no message.content", json.dumps(response), kind="bad_response")
        return content


class GroqClient:
    """Groq chat-completions client (OpenAI-compatible, Bearer auth).

    Returns the same thing OllamaClient does: the raw text of the model's reply. The API key is read from
    the environment at construction, is only ever sent in the Authorization header, and is never logged.
    """

    DEFAULT_ENDPOINT = "https://api.groq.com/openai/v1"
    backend_name = "groq"
    KEY_VARIABLE = "GROQ_API_KEY"
    PROVIDER = "Groq"
    QUOTA_WORDS = "daily quota"
    SEND_TEMPERATURE = True

    def __init__(self, model: str, endpoint: str | None = None, *, reasoning_effort: str | None = None,
                 max_rate_limit_retries: int = 2, max_retry_wait: float = 30.0,
                 environ: Any = None, urlopen: Any = None, sleep: Any = None):
        environ = os.environ if environ is None else environ
        key = (environ.get(self.KEY_VARIABLE) or "").strip()
        if not key:
            raise ModelConfigError(f"{self.KEY_VARIABLE} environment variable is not set; export it in your shell "
                                   f"before using the {self.PROVIDER.lower()} backend, or pass --backend ollama to use the local model "
                                   "(no automatic switch to the local model happens when the key is missing)")
        if not 0 <= max_rate_limit_retries <= 2 or not math.isfinite(max_retry_wait) or max_retry_wait < 0:
            raise ValueError("rate-limit retries must be 0-2 and the retry wait must be finite and nonnegative")
        self._key = key
        self.model = model
        self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self.reasoning_effort = reasoning_effort
        self.max_rate_limit_retries = max_rate_limit_retries
        self.max_retry_wait = max_retry_wait
        self._urlopen = urlopen or urllib.request.urlopen
        self._sleep = sleep or time.sleep
        self.rate_limit_waits: list[float] = []
        self.observations: list[dict[str, Any]] = []   # one record per response: status, rate-limit headers, usage (never the key)
        self.last_observation: dict[str, Any] | None = None

    def _note(self, status: int, headers: Any, message: str | None = None) -> None:
        """Record what the provider said about its limits on this response. Only x-ratelimit-* and retry-after are kept."""
        kept = {}
        try:
            for name, value in (headers.items() if headers else []):
                if name.lower().startswith("x-ratelimit") or name.lower() == "retry-after":
                    kept[name.lower()] = value
        except AttributeError:
            pass
        self.last_observation = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": status, "headers": kept,
                                 "usage": None, "message": (message or "")[:400] or None}
        self.observations.append(self.last_observation)
        del self.observations[:-500]

    def _request(self, method: str, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint + path,
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            method=method,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                     "User-Agent": "edaptive-assessment-card-generator/1.0"},
        )
        try:
            with self._urlopen(request, timeout=timeout) as response:
                raw = _read_provider_response(response, self.PROVIDER, timeout)
                self._note(getattr(response, "status", 200), getattr(response, "headers", None))
        except urllib.error.HTTPError as exc:
            raw = _read_provider_response(exc, self.PROVIDER, timeout)
            self._note(exc.code, exc.headers, raw)
            if exc.code == 429:
                header = exc.headers.get("retry-after") if exc.headers else None
                try:
                    retry_after = float(header) if header is not None else None
                except ValueError:
                    retry_after = None
                hint = f"; provider asks to retry after {retry_after:g}s" if retry_after is not None else ""
                kind, signal = self._classify_429(raw, exc.headers)
                if kind == "daily_quota":
                    raise QuotaExhaustedError(f"{self.PROVIDER} {self.QUOTA_WORDS} exhausted (HTTP 429, {signal}){hint}: {raw[:300]}",
                                              raw, retry_after, signal) from exc
                raise RateLimitError(f"{self.PROVIDER} rate limit (HTTP 429){hint}: {raw[:300]}", raw, retry_after) from exc
            raise ModelRequestError(f"{self.PROVIDER} HTTP {exc.code}: {raw[:300]}", raw, status=exc.code) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
                raise TimeoutError(f"model request exceeded {timeout:g}s timeout") from exc
            raise ModelRequestError(f"cannot reach {self.PROVIDER}: {exc}", kind="unreachable") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ModelRequestError(f"{self.PROVIDER} returned malformed API JSON", raw, kind="bad_response") from exc
        if not isinstance(result, dict):
            raise ModelRequestError(f"{self.PROVIDER} API response is not an object", raw, kind="bad_response")
        return result

    def _classify_429(self, raw: str, headers: Any) -> tuple[str, str]:
        return classify_groq_429(raw, headers)

    def list_models(self, timeout: float = 30.0) -> list[str]:
        result = self._request("GET", "/models", None, timeout)
        return sorted(item["id"] for item in result.get("data", []) if isinstance(item, dict) and "id" in item)

    def chat(self, messages: list[dict[str, str]], *, timeout: float, max_output_tokens: int) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        if self.SEND_TEMPERATURE:
            payload["temperature"] = 0.2
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        attempt = 0
        while True:
            try:
                response = self._request("POST", "/chat/completions", payload, timeout)
                break
            except RateLimitError as exc:
                if isinstance(exc, QuotaExhaustedError):
                    raise  # a daily quota does not come back in seconds: never wait and retry
                # Bounded: at most max_rate_limit_retries waits, each no longer than max_retry_wait.
                wait = exc.retry_after
                if (attempt >= self.max_rate_limit_retries or wait is None or not math.isfinite(wait)
                        or wait < 0 or wait > self.max_retry_wait):
                    raise
                attempt += 1
                self.rate_limit_waits.append(wait)
                self._sleep(wait)
        usage = response.get("usage")
        if self.last_observation is not None and isinstance(usage, dict):
            self.last_observation["usage"] = {key: usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ModelRequestError(f"{self.PROVIDER} response has no choices", json.dumps(response), kind="bad_response")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            if choices[0].get("finish_reason") == "length":
                raise ModelRequestError("model hit the output limit before producing an answer (reasoning tokens count "
                                        "toward it); raise --max-output-tokens", json.dumps(response), kind="length")
            raise ModelRequestError(f"{self.PROVIDER} response has no message.content", json.dumps(response), kind="bad_response")
        return content


class OpenAIClient(GroqClient):
    """OpenAI chat-completions client. Same wire format, key handling and bounded-wait behaviour as the Groq client.

    Differences: its own endpoint and key variable; no temperature is sent (some OpenAI models reject any value but
    their default); and a 429 with code insufficient_quota is an exhausted account quota, never waited out or retried.
    """

    DEFAULT_ENDPOINT = "https://api.openai.com/v1"
    backend_name = "openai"
    KEY_VARIABLE = "OPENAI_API_KEY"
    PROVIDER = "OpenAI"
    QUOTA_WORDS = "account quota"
    SEND_TEMPERATURE = False

    def _classify_429(self, raw: str, headers: Any) -> tuple[str, str]:
        code = ""
        try:
            error = json.loads(raw).get("error")
            if isinstance(error, dict):
                code = str(error.get("code") or error.get("type") or "")
        except (json.JSONDecodeError, AttributeError):
            pass
        if code == "insufficient_quota":
            return "daily_quota", "code:insufficient_quota"
        return "per_minute", f"code:{code or 'unspecified'}"


class FallbackClient:
    """Use `primary` (Groq) until it reports its DAILY quota exhausted, then use the local fallback for good.

    Orchestration only: both clients are used as they are. Per-minute 429s never reach here (the Groq client
    handles them with bounded waits). Once exhausted, later calls skip Groq entirely for the rest of the run.
    served_log has one label per successful call, so callers can record which backend served each question.
    """

    def __init__(self, primary: ModelClient, make_fallback: Any, *, primary_label: str = "groq",
                 fallback_label: str = "ollama_fallback", fallback_name: str = "local model", notify: Any = None):
        self.primary = primary
        self._make_fallback = make_fallback
        self._fallback: ModelClient | None = None
        self.primary_label = primary_label
        self.fallback_label = fallback_label
        self.fallback_name = fallback_name
        self._notify = notify or (lambda text: print(text, file=sys.stderr))
        self.exhausted = False
        self.event: dict[str, Any] | None = None
        self.served_log: list[str] = []
        self.last_served_by: str | None = None

    def list_models(self, timeout: float = 30.0) -> list[str]:
        lister = getattr(self.primary, "list_models", None)
        if lister is None:
            raise ModelRequestError("the primary backend cannot list models")
        return lister(timeout)

    def chat(self, messages: list[dict[str, str]], *, timeout: float, max_output_tokens: int) -> str:
        if not self.exhausted:
            try:
                text = self.primary.chat(messages, timeout=timeout, max_output_tokens=max_output_tokens)
                self.served_log.append(self.primary_label)
                self.last_served_by = self.primary_label
                return text
            except QuotaExhaustedError as exc:
                self.exhausted = True
                self.event = {"activated": True, "signal": exc.signal, "message": str(exc)[:300],
                              "calls_served_by_primary_before": len(self.served_log), "fallback": self.fallback_name}
                self._notify(f"Groq daily quota exhausted ({exc.signal}); using {self.fallback_name} for the rest of this run")
        if self._fallback is None:
            self._fallback = self._make_fallback()
        try:
            text = self._fallback.chat(messages, timeout=timeout, max_output_tokens=max_output_tokens)
        except ModelRequestError as exc:
            raise ModelRequestError(f"Groq daily quota exhausted and the local fallback failed: {exc}",
                                    exc.raw_response) from exc
        self.served_log.append(self.fallback_label)
        self.last_served_by = self.fallback_label
        return text


def _selected_teaching(card: NormalizedConceptCard, config: GenerationConfig, difficulty: str) -> tuple[list[TeachingItem], list[TeachingItem]]:
    if difficulty == "easy":
        return list(card.explanations[: config.max_explanations]), list(card.examples[: config.max_examples])
    # Later steps should not lose a combining or application explanation merely
    # because it appears after the first three items in a card.
    cues = ("combine", "combined", "two sets", "first set", "second set", "altogether", "then add")

    def select(items: tuple[TeachingItem, ...], limit: int) -> list[TeachingItem]:
        ranked = sorted(
            enumerate(items),
            key=lambda pair: (-sum(cue in (pair[1].title or "").lower() + " " + pair[1].text.lower() for cue in cues), pair[0]),
        )
        selected_indices = {index for index, _ in ranked[:limit]}
        return [item for index, item in enumerate(items) if index in selected_indices]

    return select(card.explanations, max(config.max_explanations, 4)), select(card.examples, max(config.max_examples, 2))


# Words in the teaching content that show an operation is taught live in lesson_profile.py; these names stay for callers.
_OPERATION_CUES = lp.OPERATION_CUES
_WORKED_CUE = re.compile(r"\b(?:plus|minus|times|add|adds|subtract\w*|multipl\w*|equals?|take|makes?|gives?)\b|[+\u00d7=\u2212]", re.I)


_INVERSE_OPERATION = lp.INVERSE_OPERATION
_taught_operations = lp.taught_operations
_mentioned_operations = lp.mentioned_operations
_permitted_operations = lp.permitted_operations
_GROUP_KINDS = ("equal_groups", "two_equal_group_sets")


def contract_kinds(card: NormalizedConceptCard) -> tuple[str, ...]:
    """The typed task kinds this lesson may use, derived from what its own teaching uses. () means none apply.

    Operations give the arithmetic kinds (by the lesson's number domain); comparison, rounding and place value give the
    rule kinds. A calculation lesson gets rule kinds only for rules its objective names; a rule-checkable lesson gets all it
    teaches. A lesson with nothing code can check gets none and is generated as grounded (not code-verified) questions.
    """
    kind = lp.lesson_kind(card)
    if kind == "non_calculation":
        return ()
    domain = lp.lesson_domain(card)
    kinds = list(kinds_for_operations(lp.taught_operations(card), domain, lp.teaches_repeated_addition(card)))
    objective = card.objective.text.lower()
    rules = [rule for rule in lp.taught_rules(card) if kind == "rule_checkable" or re.search(lp.RULE_CUES[rule], objective)]
    kinds += kinds_for_rules(rules, domain)
    return tuple(dict.fromkeys(kinds))


def _is_worked(text: str) -> bool:
    """A teaching item that works a calculation: at least two numbers and an operation or result cue."""
    return len(re.findall(r"\d+", text)) >= 2 and bool(_WORKED_CUE.search(text))


def _hard_plan(card: NormalizedConceptCard, config: GenerationConfig) -> dict[str, Any]:
    """What a hard question for THIS card can be built from, derived from its own teaching items.

    A hard question needs several connected taught steps, so the card must show at least three worked items
    (two explanations and one example). If it does not, 'insufficient' says why and generation is refused.
    """
    explanations, examples = _selected_teaching(card, config, "hard")
    methods = []
    worked = {"explanation": 0, "example": 0}
    for kind, selected in (("explanation", explanations), ("example", examples)):
        for index, item in enumerate(selected):
            if _is_worked(item.text):
                worked[kind] += 1
                methods.append({"id": item.id or f"{kind}s[{index}]", "kind": kind, "title": item.title or ""})
    plan: dict[str, Any] = {"methods": methods, "operations_taught": _permitted_operations(card), "insufficient": None}
    if worked["explanation"] < 2 or worked["example"] < 1 or len(methods) < 3:
        plan["insufficient"] = (
            f"this card's teaching content has {worked['explanation']} worked explanation(s) and {worked['example']} worked "
            "example(s); a hard question needs at least 2 worked explanations and 1 worked example (3 worked items) so that "
            "several connected taught steps can be grounded in the card. Add worked explanations/examples or write the hard "
            "question by hand; no equal-groups-shaped question is forced onto it")
    return plan


def _scaffold_items(card: NormalizedConceptCard, parent: dict[str, Any]) -> list[tuple[str, str, TeachingItem]]:
    """The teaching items a scaffold question may use: exactly the ones its harder parent was grounded in."""
    wanted = [ref for ref in parent.get("teaching_refs", []) if ref != (card.objective.id or "objective")]
    if not wanted:
        raise ValueError("scaffold parent cites no teaching item besides the objective")
    available = {(item.id or f"{kind}s[{index}]"): (kind, item)
                 for kind, items in (("explanation", card.explanations), ("example", card.examples))
                 for index, item in enumerate(items)}
    missing = [ref for ref in wanted if ref not in available]
    if missing:
        raise ValueError(f"scaffold parent cites teaching items the card does not have: {', '.join(missing)}")
    return [(ref, *available[ref]) for ref in wanted]


_STOPWORDS = frozenset("the a an of to in is are and or it its this that for with on as be by at from you your".split())
_YES_NO = frozenset({"yes", "no", "true", "false"})
_ID_LOOKING = re.compile(r"\b(?:exp|ex|obj|q|r|h|a|mis|fu|aq)_[A-Za-z0-9_]+\b|\{\s*ref\b", re.I)


def _internal_ids(card: NormalizedConceptCard) -> set[str]:
    ids = {card.objective.id}
    for item in (*card.explanations, *card.examples):
        ids.add(item.id)
    for group in (card.reference_questions, card.reference_rubrics, card.reference_hints, card.misconceptions):
        ids.update(entry.get("id") for entry in group)
    ids.update(asset.get("asset_id") for asset in card.required_assets)
    return {i for i in ids if isinstance(i, str) and len(i) >= 3}


def _leaked_id(texts: list[str], card: NormalizedConceptCard) -> str | None:
    """An internal id (a teaching item, question, hint or asset id, a part id, or the {ref} syntax) in text a learner will read."""
    known = {i.lower() for i in _internal_ids(card)}
    for text in texts:
        if not isinstance(text, str):
            continue
        for match in _ID_LOOKING.finditer(text):
            return match.group(0)
        for word in re.findall(r"[A-Za-z0-9_\[\]]+", text):
            if word.lower() in known:
                return word
    return None
_IMAGE_DEPENDENT = re.compile(r"\b(?:image|picture|photo|diagram|figure|drawn above|shown below|shown above|look at the)\b", re.I)


def _grounded_items(card: NormalizedConceptCard, config: GenerationConfig) -> list[dict[str, str]]:
    """Everything a grounded question may cite: the objective, explanations, examples, practice items and misconceptions."""
    items = [{"id": card.objective.id or "objective", "kind": "objective", "text": card.objective.text[: config.max_item_chars]}]
    for index, item in enumerate(card.explanations[:4]):
        items.append({"id": item.id or f"explanations[{index}]", "kind": "explanation", "text": item.text[: config.max_item_chars]})
    for index, item in enumerate(card.examples[:2]):
        items.append({"id": item.id or f"examples[{index}]", "kind": "example", "text": item.text[: config.max_item_chars]})
    rubrics = {rubric.get("id"): rubric for rubric in card.reference_rubrics}
    practice = [q for q in card.reference_questions if q.get("kind") in ("practice", "prior_knowledge") and q.get("id")][:4]
    for question in practice:
        accepted = ((rubrics.get(question.get("rubric_id")) or {}).get("answer_key") or {}).get("accept") or []
        answer = f" (answer: {accepted[0]})" if accepted else ""
        items.append({"id": question["id"], "kind": "practice_item", "text": (str(question.get("text", "")) + answer)[: config.max_item_chars]})
    for misconception in card.misconceptions[:3]:
        if misconception.get("id"):
            items.append({"id": misconception["id"], "kind": "misconception",
                          "text": f"{misconception.get('label', '')}: {misconception.get('description', '')}"[: config.max_item_chars]})
    return items


def _card_words(card: NormalizedConceptCard) -> dict[str, set[str]]:
    """word -> ids of the card items that contain it (for checking that an answer is supported by the card)."""
    where: dict[str, set[str]] = {}

    def add(item_id: str, text: Any) -> None:
        for word in re.findall(r"[a-z0-9']+", str(text).lower()):
            where.setdefault(word, set()).add(item_id)

    add(card.objective.id or "objective", card.objective.text)
    for index, item in enumerate((*card.explanations, *card.examples)):
        add(item.id or f"item{index}", f"{item.title or ''} {item.text}")
    rubrics = {rubric.get("id"): rubric for rubric in card.reference_rubrics}
    for question in card.reference_questions:
        add(question.get("id", "question"), question.get("text", ""))
        for answer in ((rubrics.get(question.get("rubric_id")) or {}).get("answer_key") or {}).get("accept") or []:
            add(question.get("id", "question"), answer)
    for misconception in card.misconceptions:
        add(misconception.get("id", "misconception"), " ".join(str(v) for v in misconception.values() if isinstance(v, str)))
    for hint in card.reference_hints:
        add(hint.get("id", "hint"), hint.get("text", ""))
    return where


def _grounded_context(card: NormalizedConceptCard, config: GenerationConfig, difficulty: str,
                      distinct_from: list[dict[str, Any]] | None, scaffold_of: dict[str, Any] | None) -> tuple[list[dict[str, str]], set[str], str]:
    everything = _grounded_items(card, config)
    if scaffold_of is not None:
        wanted = set(scaffold_of.get("teaching_refs", []))
        items = [item for item in everything if item["kind"] == "objective" or item["id"] in wanted]
        if len(items) < 2:
            raise ValueError("scaffold parent cites no teaching item besides the objective")
    else:
        items = everything
    level = {
        "easy": "Create exactly one EASY practice question that checks recall or recognition of one idea taught in the items below, "
                "answerable in a few words. ",
        "medium": "Create exactly one MEDIUM practice question that applies one taught idea to a new example, or asks the learner "
                  "to tell two taught ideas apart. ",
        "hard": "Create exactly one HARD practice question that needs at least two taught ideas together, for example sorting with "
                "a reason, comparing two things, or spotting and correcting a mistake like one of the misconceptions listed. "
                "Cite at least two items besides the objective. ",
    }[difficulty]
    if scaffold_of is not None:
        level = ("This question is a SCAFFOLD for a learner who has just missed a harder question on the same taught idea (that "
                 "harder question is listed under must_differ_from). Make it exactly one step simpler, on the same idea, using only "
                 "the teaching items shown. ") + level
    prompt = (level +
              "Base the question only on the teaching content below: the answer must be stated in the teaching content, not "
              "added from outside it. Write for a child of the supplied grade. Keep the expected answer to a short phrase of at "
              "most eight words, and list every wording a correct learner might reasonably use. Never require an image, a "
              "picture or a drawing. This lesson is not checked by code, so the answer you give will be reviewed by a person. "
              "Return only one JSON object with keys: prompt, difficulty, difficulty_rationale, expected_answer, accepted_answers "
              "(an array of one to six short strings, including expected_answer), marking_criteria (one sentence saying what a "
              "correct answer must contain), teaching_refs (array of item IDs from teaching_items; include the objective ID and "
              + ("at least two other items). " if difficulty == "hard" else "at least one other item). ") +
              "difficulty_rationale must briefly say why this is the requested level and cite an item ID.\n")
    context: dict[str, Any] = {"subject": card.subject, "grade": card.grade, "prerequisite_ids": card.prerequisite_ids,
                               "teaching_items": items}
    if distinct_from:
        prompt = prompt.rstrip("\n") + (" A learner will also answer the " + " and ".join(o["label"] for o in distinct_from) +
                                         " question(s) in this session. Ask about a different idea or a different example.\n")
        context["must_differ_from"] = [{"question": o["label"], "prompt": o["prompt"]} for o in distinct_from]
    return items, {item["id"] for item in items}, prompt + json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def _words_of(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def _validate_grounded(data: dict[str, Any], card: NormalizedConceptCard, known_refs: set[str], objective_ref: str,
                       difficulty: str, distinct_from: list[dict[str, Any]]) -> dict[str, Any]:
    """A question in a lesson with nothing code can check. Only its structure and its grounding in the card are checked."""
    problems: list[str] = []
    prompt = data.get("prompt")
    if not _nonempty(prompt) or len(prompt.split()) < 3 or len(prompt) > 400:
        raise ValueError("prompt must be a learner-facing question of 3 to about 60 words")
    if _IMAGE_DEPENDENT.search(prompt):
        raise ValueError("the question depends on an image or picture; the assessment card never contains or needs an image")
    texts = [prompt, data.get("expected_answer"), data.get("marking_criteria")] + (data.get("accepted_answers") if isinstance(data.get("accepted_answers"), list) else [])
    leaked = _leaked_id(texts, card)
    if leaked:
        raise ValueError(f"learner-facing text names an internal id ({leaked!r}); describe the idea in plain words instead")
    accepted = data.get("accepted_answers")
    if (not isinstance(accepted, list) or not 1 <= len(accepted) <= 6
            or any(not _nonempty(a) or len(a) > 80 for a in accepted)):
        raise ValueError("accepted_answers must be an array of one to six short strings")
    expected = data.get("expected_answer")
    if not _nonempty(expected) or len(expected.split()) > 8:
        raise ValueError("expected_answer must be a short phrase of at most eight words")
    if expected.strip().lower() not in [a.strip().lower() for a in accepted]:
        raise ValueError("expected_answer must be one of the accepted_answers")
    refs, rationale = _refs_and_rationale(data, known_refs, objective_ref, difficulty, problems)
    criteria = data.get("marking_criteria")
    if criteria is not None and not isinstance(criteria, str):
        raise ValueError("marking_criteria must be text or null")
    flags = ["answer_not_code_verified", "grounding_semantics_unverified"]
    tokens = [w for w in re.findall(r"[a-z0-9']+", expected.lower()) if w not in _STOPWORDS]
    where = _card_words(card)
    supported = sorted({item for token in tokens for item in where.get(token, ())})
    if not tokens or set(tokens) <= _YES_NO:
        flags.append("answer_too_short_to_ground")
    elif not supported:
        problems.append("the expected answer is not supported anywhere in the concept card (none of its words appear in the card's "
                        "explanations, examples, practice items, misconceptions or hints); use an answer the card states")
    normalized = " ".join(sorted(_words_of(prompt)))
    for question in card.reference_questions:
        if " ".join(sorted(_words_of(str(question.get("text", ""))))) == normalized:
            flags.append(f"copy_of_concept_card_question:{question.get('id')}")
    for other in distinct_from:
        mine, theirs = _words_of(prompt), _words_of(str(other.get("prompt", "")))
        if mine and theirs and len(mine & theirs) / len(mine | theirs) >= 0.8:
            problems.append(f"{difficulty} question is nearly the same question as the {other['label']} question; ask about a different idea")
    if problems:
        raise ValueError("; ".join(problems))
    verification = {
        "status": "grounding_only",
        "scope": "The answer is NOT verified by code. It is only checked to be present in the concept card's own text; "
                 "a person must review it before use.",
        "grounding": {"supported_by": supported[:12], "answer_tokens": tokens,
                      "checked": ["prompt is a short learner-facing question that does not depend on an image",
                                  "cited teaching IDs exist and include the objective",
                                  "at least one word of the expected answer appears in the concept card's text",
                                  "differs from the other chosen questions",
                                  "compared with the concept card's own questions for copying"],
                      "not_checked": ["that the answer is correct", "that the question suits the level", "that the wording is clear",
                                      "that the question exercises the cited idea"]}}
    return {
        "id": "aq_" + uuid.uuid4().hex[:12], "concept_id": card.concept_id, "concept_version": card.card_version,
        "subject": card.subject, "grade": card.grade, "kind": "practice", "review_status": "draft", "review_flags": flags,
        "prompt": prompt.strip(), "difficulty": difficulty, "difficulty_rationale": rationale, "response_type": "short_text",
        "stimulus": None, "expected_answer": expected.strip(), "accepted_answers": [a.strip() for a in accepted],
        "marking_criteria": criteria.strip() if _nonempty(criteria) else None, "partial_credit": False,
        "partial_credit_criteria": None, "teaching_refs": refs, "calculation": None, "answer_parts": None,
        "answer_verification": "grounding_only", "verification": verification}


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _typed_common(difficulty: str, scaffold: bool) -> str:
    """Instructions for easy and medium: one short shape for every lesson. The application renders the wording and the
    calculator computes the answer."""
    level = {
        "easy": "Create exactly one EASY maths practice question: one taught calculation or rule applied directly to numbers you "
                "choose, in a single step. ",
        "medium": "Create exactly one MEDIUM maths practice question: one taught step applied in a short real-world situation. "
                  "You must choose a template listed under story for its kind. ",
    }[difficulty]
    if scaffold:
        level = ("This question is a SCAFFOLD for a learner who has just missed a harder question on the same taught idea (that "
                 "harder question is under must_differ_from). Make it exactly one step simpler, on the same idea, using only "
                 "the teaching items shown. ") + level
    return (level +
            "Base the question only on the teaching content below, for the supplied grade; do not require skills beyond the "
            "shown items. Choose numbers that suit this lesson and are not copied from the teaching examples. "
            "Return only one JSON object with keys: task, difficulty, difficulty_rationale, expected_answer, teaching_refs. "
            "task has exactly version, kind, givens, milestones, template, final_part_id: use the version in task_contract, "
            "milestones [], final_part_id null; kind and template are NAMES from task_contract (a key under allowed_kinds and a "
            "key under that kind's templates, never the template text), and each given has the value type listed in value_types. "
            "Do not write the question text: the application renders it and computes the correct answer itself. "
            "expected_answer is your own answer (a number, fraction, amount of money, symbol, or 'q remainder r'); it is only "
            "compared with the application's answer and is never used as the answer. "
            "difficulty_rationale must briefly say why this is the requested level and cite an explanation or example ID. "
            "teaching_refs must include the objective ID and at least one explanation or example ID. "
            "Do not require an image.\n")


def _contract_for(kind_names) -> dict:
    return {"version": TASK_VERSION, "value_types": calc_tasks.value_types(kind_names),
            "allowed_kinds": {kind: calc_tasks.describe(kind) for kind in kind_names}}


def _differ_context(card: NormalizedConceptCard, kinds: tuple, distinct_from: list[dict[str, Any]]) -> dict[str, Any]:
    """The 'must differ from' block shared by every prompt shape: what the other chosen questions already use."""
    context: dict[str, Any] = {}
    numeric = [other for other in distinct_from if other["quantities"]["answers"]]
    unsupported = [other["label"] for other in distinct_from if not other["quantities"]["answers"]]
    if unsupported:
        context["unsupported_comparisons"] = {"questions": unsupported, "scope": "numeric distinctness unsupported for nonnumeric questions"}
    context["must_differ_from"] = [
        {"question": other["label"], "prompt": other["prompt"], "its_input_numbers": sorted(set(other["quantities"]["inputs"])),
         "its_final_answer": other["quantities"]["answers"][-1] if other["quantities"]["answers"] else other.get("answer"),
         "numeric_distinctness": "supported" if other["quantities"]["answers"] else "unsupported",
         "values_it_computes": other["quantities"]["values"]} for other in distinct_from]
    if numeric and any(kind in _GROUP_KINDS for kind in kinds):
        context["numbers_not_used_by_them"] = _unused_small_numbers(distinct_from, card=card)
    return context


def _typed_prompt(card: NormalizedConceptCard, kinds: tuple, difficulty: str, items: list[dict[str, str]],
                  distinct_from: list[dict[str, Any]] | None, scaffold_of: dict[str, Any] | None) -> str:
    common = _typed_common(difficulty, scaffold_of is not None)
    context: dict[str, Any] = {"subject": card.subject, "grade": card.grade, "prerequisite_ids": card.prerequisite_ids,
                               "teaching_items": items}
    if distinct_from:
        common += (" A learner will also answer the " + " and ".join(o["label"] for o in distinct_from) + " question(s) in this "
                   "session. Use different numbers from each of them (see must_differ_from) and a different answer value.\n")
        context.update(_differ_context(card, kinds, distinct_from))
    context["task_contract"] = _contract_for(kinds)
    return common + _compact(context)


_HARD_GUIDANCE = {
    "add_two": "For addition, add by the taught place-value chunks and check by direct addition of the original addends.",
    "subtract_two": "For subtraction, subtract by the taught method and check by adding the difference back to the subtrahend.",
    "equal_groups": "For equal groups, use positive group counts and a common group size.",
    "two_equal_group_sets": "For two sets of equal groups, find each set's total, then combine and check from the original givens.",
    "divide_two": "For division, find the quotient and the remainder with divmod, and check by multiplying back.",
}
_HARD_DERIVE = {
    "add": "(for example add(a,b) where a and b are named givens); a bare literal equal to what another part computes is not sourced",
    "subtract": "(for example subtract(a,b) where a and b are named givens); a bare literal equal to what another part computes is not sourced",
    "multiply": "(for example multiply(add(a,b),c) where a, b and c are named givens); a bare literal equal to what another part "
                "computes is not sourced",
    "divide": "(for example remainder(a,b) where a and b are named givens); a bare literal equal to what another part computes is "
              "not sourced",
}


def _hard_prompt(card: NormalizedConceptCard, config: GenerationConfig, items: list[dict[str, str]], kinds: tuple,
                 distinct_from: list[dict[str, Any]] | None, scaffold_of: dict[str, Any] | None) -> str:
    divides = "divide" in lp.permitted_operations(card) or "divide_two" in kinds
    operations = "'add'|'subtract'|'multiply'" + ("|'divide'|'quotient'|'remainder'" if divides else "")
    first_kind = kinds[0]
    derive = _HARD_DERIVE["divide" if first_kind == "divide_two" else "multiply" if any(k in _GROUP_KINDS for k in kinds)
                          else "subtract" if first_kind == "subtract_two" else "add"]
    common = (
        "Create exactly one HARD maths practice question: several connected taught steps and a deeper check of the idea, not "
        "just bigger numbers or more sentences. Build it only from the taught methods in hard_plan.methods, following how the "
        "teaching items work their own examples, and use only the operations in hard_plan.operations_taught. "
        "Use response_type multi_part with 3 to 5 numeric answer parts; each has a short id made only of lowercase letters and "
        "underscores (no digits) and instruction {kind:'calculate'}. Never write an id or the {ref} syntax inside any "
        "learner-facing text. The parts must chain: a later part's calculation uses {ref:'<the exact id of an earlier part>'}, the "
        "path to task.final_part_id has an operation-bearing dependency, and the final derivation plus its check need at least "
        "three meaningful steps. Bare refs and +0, -0 or multiply-by-1 add no steps. "
        "You MUST include a cross-check part: one later part reaches the SAME value as an earlier part by a different calculation, "
        "or undoes the result to recover an original given (sum R=A+B: R-A=B or R-B=A; difference R=A-B: R+B=A or A-R=B), "
        "directly referring to the named result and verifying the final result or a result on its derivation path. "
        "The cross-check part is the one place you may use any mathematically exact equivalent even if the lesson does not "
        "teach it: re-add in a different order, subtract to check an addition, add back to check a subtraction, swap the "
        "factors or use repeated addition to check a multiplication, or multiply back to check a division (quotient times "
        "divisor plus remainder equals the dividend, referring to the quotient part and the remainder part). All other "
        "parts must use only the operations in hard_plan.operations_taught. ")
    if scaffold_of is not None:
        common = ("This question is a SCAFFOLD for a learner who has just missed a harder question on the same taught idea (listed "
                  "under must_differ_from). Make it exactly one step simpler, on the same idea, using only the teaching items shown. "
                  + common)
    common += (
        "Base the question only on the teaching content below, for the supplied grade; use whole numbers suited to the method and "
        "fresh operands (overlap gives review flags, not rejection). "
        "Return only one JSON object with keys: task, difficulty, difficulty_rationale, response_type, expected_answer, "
        "marking_criteria, partial_credit, partial_credit_criteria, teaching_refs, calculation, answer_parts. "
        f"An expression is a bare JSON integer or {{operation: {operations}, operands: [expression, expression]}} or "
        "{ref: '<id of an earlier part>'}. expected_answer, calculation and marking_criteria are null; answer_parts is "
        "[{id, instruction: {kind: 'calculate'}, expected_answer, calculation}]; partial_credit is true; partial_credit_criteria "
        "is [{part_id, points: 1}], one per part (criterion text is optional: the application derives the exact answer rules). "
        "Every calculation must equal its answer. Include the objective ID and at least two other taught item IDs in teaching_refs. "
        "difficulty_rationale must briefly say why this is hard and cite an explanation or example ID, naming only operations your "
        "calculation uses (repeated addition only if it contains it); a number of steps it states must match your calculation. "
        "Do not require an image.\n"
        + ("'quotient' and 'remainder' are whole-number division (divmod): quotient(a,b) is how many whole times b fits in a and "
           "remainder(a,b) is what is left over. Use 'divide' only when it divides exactly. The divisor is at least 2.\n" if divides else "")
        + "Return a task with exactly version, kind, givens, milestones, template, final_part_id. kind and template are NAMES from "
        "task_contract (a key under allowed_kinds and a key under that kind's templates), never the template text. Omit prompt and "
        "stimulus: the application renders them. Givens are bare nonnegative integers. milestones is [] unless you use a validated "
        "next_hundred target {id, kind:'next_hundred', of_given, value} (value = the next strictly greater hundred after that "
        "given). final_part_id names the answer part that answers the task; a later check need not be the final result. "
        "A split of a stated number into parts that add back to it counts as ONE step; the question must state the whole number and "
        "never use a number that is neither stated nor a part of a stated number. To use a split add a top-level decompositions "
        "array of {source: {kind: 'given'|'milestone', id}, calculation_part_id, leaves: [{part_id, path: [operand indices]}]}: at "
        "least two positive chunks summing exactly to the source, in one addition chain or one chain of subtrahends, selecting native "
        "integer leaves (not refs), none reused. A cross-check's literals and refs must trace to givens, milestones or declared "
        "leaves; write other values as explicit expressions " + derive + ".\n"
        + " ".join(_HARD_GUIDANCE[k] for k in kinds if k in _HARD_GUIDANCE) + "\n")
    context: dict[str, Any] = {"subject": card.subject, "grade": card.grade, "prerequisite_ids": card.prerequisite_ids,
                               "teaching_items": items}
    if distinct_from:
        common = common.rstrip("\n") + (
            " A learner will also answer the " + " and ".join(o["label"] for o in distinct_from) + " question(s) in this session. "
            "Use a different set of input numbers from each of them, and no value your calculation computes, including intermediate "
            "results, may equal a value they compute; check every result against values_it_computes before answering.\n")
        context.update(_differ_context(card, kinds, distinct_from))
    plan = _hard_plan(card, config)
    context["hard_plan"] = {"methods": plan["methods"], "operations_taught": plan["operations_taught"]}
    context["task_contract"] = {"version": TASK_VERSION,
                                "allowed_kinds": {kind: {"given_roles": ROLES[kind], "templates": TEMPLATES[kind]} for kind in kinds}}
    return common + _compact(context)


# Words that suggest an operation. Used only to FLAG wording that points at a different operation than the verified one.
_WORDING_CUES = {
    "multiply": r"\b(?:groups? of|each|every|times|per|rows? of|twice|double)\b",
    "divide": r"\b(?:shared? equally|split|divid\w*|equal parts)\b",
    "add": r"\b(?:plus|sum|combined|adds?|added|adding)\b",  # 'altogether' / 'in all' ask for a total in any operation
    "subtract": r"\b(?:how many (?:are )?left|remain\w*|fewer|difference|take away|takes away|how many more|left)\b(?! over)",
}
_WORDING_SCOPE = ("flag-only; it never rejects. It looks for a fixed list of cue words (for example 'each', 'groups of', "
                  "'altogether', 'left') and cannot catch synonyms, an operation implied by the story, a multi-step story, "
                  "wording that is wrong in some other way, or a cue word used innocently")


def _wording_flags(text: str, verified: set[str]) -> list[dict[str, Any]]:
    """Cue words in the learner-facing wording that suggest an operation other than the verified one(s). Never rejects."""
    if not verified:
        return []
    flags = []
    for operation, pattern in _WORDING_CUES.items():
        if operation in verified:
            continue
        match = re.search(pattern, text, re.I)
        if match:
            flags.append({"suggests": operation, "word": match.group(0).lower(), "verified": sorted(verified)})
    return flags


def _wording_record(text: str, verified: set[str]) -> tuple[dict[str, Any], list[str]]:
    flags = _wording_flags(text, verified)
    return ({"status": "flag_only", "flags": flags, "scope": _WORDING_SCOPE},
            [f"wording_suggests_operation:{flag['suggests']} ('{flag['word']}')" for flag in flags])


def _hard_unsupported_reason(card: NormalizedConceptCard, kinds: tuple[str, ...]) -> str:
    return (f"this {lp.lesson_kind(card).replace('_', '-')} lesson works with {lp.lesson_domain(card)} numbers or rules "
            f"(task kinds {list(kinds)}), and a hard question is built from connected whole-number steps; hard generation is not "
            "built for it, so hard can only be reused from the concept card")


def _teaching_context(card: NormalizedConceptCard, config: GenerationConfig, difficulty: str = "easy",
                      distinct_from: list[dict[str, Any]] | None = None,
                      scaffold_of: dict[str, Any] | None = None) -> tuple[list[dict[str, str]], set[str], str]:
    kinds = contract_kinds(card)
    if not kinds:
        return _grounded_context(card, config, difficulty, distinct_from, scaffold_of)
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(kind: str, item: TeachingItem, fallback: str) -> None:
        ref = item.id or fallback
        if ref in seen:
            raise ValueError(f"duplicate teaching reference ID: {ref}")
        seen.add(ref)
        items.append({"id": ref, "kind": kind, "text": item.text[: config.max_item_chars]})

    add("objective", card.objective, "objective")
    if scaffold_of is not None:
        for ref, kind, item in _scaffold_items(card, scaffold_of):
            add(kind, item, ref)
    else:
        explanations, examples = _selected_teaching(card, config, difficulty)
        for index, item in enumerate(explanations):
            add("explanation", item, f"explanations[{index}]")
        for index, item in enumerate(examples):
            add("example", item, f"examples[{index}]")
    if difficulty != "hard":
        return items, seen, _typed_prompt(card, kinds, difficulty, items, distinct_from, scaffold_of)
    hard_kinds = tuple(kind for kind in kinds if kind in HARD_KINDS)
    if not hard_kinds:
        raise ValueError("no whole-number task kind is available for a hard question in this lesson")
    return items, seen, _hard_prompt(card, config, items, hard_kinds, distinct_from, scaffold_of)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evaluate_expression(expression: Any, prior_parts: dict[str, int] | None = None, depth: int = 0) -> tuple[int, list[int], int]:
    """Return (value, literal inputs, operation count) for a tiny safe AST.

    The shape rules (allowed operations, two operands, depth) are checked here; the arithmetic itself is done by sympy.
    """
    value, inputs, operations = _evaluate_node(expression, prior_parts, depth)
    return int(value), inputs, operations


def _division(name: str):
    """quotient / remainder via divmod (checked against sympy by calculator.py); divide only when it comes out exactly."""
    def run(a: Any, b: Any) -> Any:
        try:
            result = calculator.divide_with_remainder(int(a), int(b)).value
        except calculator.CalculatorError as exc:
            raise ValueError(f"{name}: {exc}") from None
        if name == "divide" and result["remainder"] != 0:
            raise ValueError("divide must be exact; use quotient and remainder for a division with a remainder")
        return sympy.Integer(result["remainder"] if name == "remainder" else result["quotient"])
    return run


def _evaluate_node(expression: Any, prior_parts: dict[str, int] | None, depth: int) -> tuple[Any, list[int], int]:
    if depth > 6:
        raise ValueError("calculation is too deep")
    if type(expression) is int:
        return expression, [expression], 0
    if not isinstance(expression, dict):
        raise ValueError("unsupported calculation expression")
    if set(expression) == {"type", "value"} and expression.get("type") == "integer" and type(expression.get("value")) is int:
        return expression["value"], [expression["value"]], 0
    if set(expression) == {"operation", "value"} and expression.get("operation") == "number" and type(expression.get("value")) is int:
        return expression["value"], [expression["value"]], 0
    if set(expression) == {"number"} and type(expression.get("number")) is int:
        return expression["number"], [expression["number"]], 0
    if set(expression) == {"ref"}:
        ref = expression["ref"]
        if not isinstance(ref, str):
            raise ValueError("calculation part reference must be a string")
        if prior_parts is None or ref not in prior_parts:
            raise ValueError(f"unknown or forward calculation part reference: {ref}")
        return prior_parts[ref], [], 0
    if set(expression) != {"operation", "operands"}:
        raise ValueError("unsupported calculation; expected operation and operands")
    operations = {"add": lambda a, b: sympy.Add(a, b), "subtract": lambda a, b: sympy.Add(a, sympy.Mul(-1, b)),
                  "multiply": lambda a, b: sympy.Mul(a, b), "divide": _division("divide"),
                  "quotient": _division("quotient"), "remainder": _division("remainder")}
    operation = expression.get("operation")
    operands = expression.get("operands")
    if not isinstance(operation, str) or operation not in operations or not isinstance(operands, list) or len(operands) != 2:
        raise ValueError("unsupported calculation; use add, subtract, multiply, divide, quotient or remainder with two operands")
    left, left_inputs, left_ops = _evaluate_node(operands[0], prior_parts, depth + 1)
    right, right_inputs, right_ops = _evaluate_node(operands[1], prior_parts, depth + 1)
    return operations[operation](left, right), left_inputs + right_inputs, left_ops + right_ops + 1


_DIVISION_NODES = ("divide", "quotient", "remainder")


def _operations_used(expression: Any, found: set[str] | None = None) -> set[str]:
    found = set() if found is None else found
    if isinstance(expression, dict) and "operation" in expression and "operands" in expression:
        found.add(expression["operation"])
        if expression["operation"] in _DIVISION_NODES:
            found.add("divide")  # quotient and remainder are both division, for wording and topic-fit checks
        for operand in expression["operands"]:
            _operations_used(operand, found)
    return found


def _operations_used_all(calculations: list[Any]) -> set[str]:
    used: set[str] = set()
    for calculation in calculations:
        _operations_used(calculation, used)
    return used


def _add_leaves(expression: Any) -> list[Any] | None:
    """Flatten nested adds; None when a non-add node is inside."""
    if type(expression) is int:
        return [expression]
    if isinstance(expression, dict) and set(expression) == {"number"}:
        return [expression["number"]]
    if isinstance(expression, dict) and expression.get("operation") == "add":
        leaves: list[Any] = []
        for operand in expression["operands"]:
            part = _add_leaves(operand)
            if part is None:
                return None
            leaves += part
        return leaves
    return None


def _has_repeated_addition(expression: Any) -> bool:
    """True if some add node sums two or more copies of one integer (e.g. 5 + 5 + 5)."""
    if not (isinstance(expression, dict) and "operands" in expression):
        return False
    if expression.get("operation") == "add":
        leaves = _add_leaves(expression)
        if leaves is not None and len(leaves) >= 2 and len(set(leaves)) == 1:
            return True
    return any(_has_repeated_addition(operand) for operand in expression["operands"])


# Wording that names an operation, after trusted teaching IDs and typography are normalized.
_OPERATION_WORDS = {
    "add": r"\b(?:add|adds|added|adding|additions?|sums?|plus)\b",
    "subtract": r"\b(?:subtract|subtracts|subtracted|subtracting|subtractions?|differences?|minus|take away)\b",
    "multiply": r"\b(?:multiply|multiplies|multiplied|multiplying|multiplications?|times)\b",
    "divide": r"\b(?:divide|divides|divided|dividing|divisions?)\b",
}


def _normalize_rationale_operations(rationale: str, teaching_ids: set[str]) -> str:
    """Mask whole trusted IDs before changing their punctuation or spacing."""
    def token_character(char: str) -> bool:
        return char.isalnum() or char == "_" or unicodedata.category(char) == "Pd" or char == "\u2212"

    def mask_id(match: re.Match) -> str:
        # A supplied ID is not an exemption for a substring in a larger token.
        before = rationale[match.start() - 1:match.start()] if match.start() else ""
        after = rationale[match.end():match.end() + 1]
        if (before and token_character(before)) or (after and token_character(after)):
            return match.group()
        return " "

    if teaching_ids:
        pattern = "|".join(re.escape(item) for item in sorted(teaching_ids, key=lambda item: (-len(item), item)))
        rationale = re.sub(pattern, mask_id, rationale)
    text = unicodedata.normalize("NFKC", rationale).lower()
    text = "".join(" " if unicodedata.category(char) == "Pd" or char == "\u2212" else char for char in text)
    return re.sub(r"\s+", " ", text).strip()


def _rationale_operation_problem(rationale: str, calculations: list[Any],
                                 teaching_ids: set[str] | None = None) -> str | None:
    """Plain-code check: the rationale may not name an operation absent from the verified calculation(s)."""
    text = _normalize_rationale_operations(rationale, teaching_ids or set())
    used: set[str] = set()
    for calculation in calculations:
        _operations_used(calculation, used)
    for operation, pattern in _OPERATION_WORDS.items():
        if operation not in used and re.search(pattern, text):
            return f"difficulty_rationale names {operation!r}, which is not in the verified calculation (verified operations: {sorted(used)})"
    if re.search(r"\brepeated additions?\b", text) and not any(_has_repeated_addition(c) for c in calculations):
        return ("difficulty_rationale names 'repeated addition', which is not in the verified calculation "
                f"(verified operations: {sorted(used)})")
    return None


def _computed_values(expression: Any, prior_parts: dict[str, int] | None, out: set[int]) -> None:
    """Add the value of every operation node (intermediate steps included) to out."""
    if isinstance(expression, dict) and "operands" in expression:
        for operand in expression["operands"]:
            _computed_values(operand, prior_parts, out)
        out.add(_evaluate_expression(expression, prior_parts)[0])


def proposal_quantities(proposal: dict[str, Any]) -> dict[str, list[int]]:
    """Input numbers, answers, and every value computed on the way, recomputed from a proposal's calculations."""
    answers: list[int] = []
    inputs: list[int] = []
    values: set[int] = set()
    if proposal.get("answer_parts"):
        prior: dict[str, int] = {}
        for part in proposal["answer_parts"]:
            value, part_inputs, _ = _evaluate_expression(part["calculation"], prior)
            _computed_values(part["calculation"], prior, values)
            prior[part["id"]] = value
            inputs += part_inputs
            answers.append(value)
            values.add(value)
    if proposal.get("calculation") is not None:
        value, calc_inputs, _ = _evaluate_expression(proposal["calculation"])
        _computed_values(proposal["calculation"], None, values)
        inputs += calc_inputs
        answers.append(value)
        values.add(value)
    return {"inputs": sorted(inputs), "answers": answers, "values": sorted(values)}


def _unused_small_numbers(distinct: list[dict[str, Any]], limit: int = 9,
                          card: NormalizedConceptCard | None = None) -> list[int]:
    """Small numbers (2-12) that no compared question uses as an input: positive guidance for the model."""
    if card is not None and not any(kind in _GROUP_KINDS for kind in contract_kinds(card)):
        return []
    used = {number for other in distinct for number in other["quantities"]["inputs"]}
    return [number for number in range(2, 13) if number not in used][:limit]


_NEAR_COPY_MIN_SHARED = 2
_NEAR_COPY_MIN_FRACTION = 0.75
_PROPOSED_CLOSE_ADD_DIFFERENCE = 50


def _teaching_arithmetic_pairs(text: str) -> list[tuple[str, tuple[int, int]]]:
    """Only explicit two-operand arithmetic phrases; not unrestricted story parsing."""
    patterns = []
    for operation, cue in (("add", r"plus|\+"), ("subtract", r"minus|\u2212"), ("multiply", r"times|\u00d7")):
        for match in re.finditer(r"\b([0-9]+)\s*(?:" + cue + r")\s*([0-9]+)\b", text, re.I):
            patterns.append((operation, (int(match[1]), int(match[2]))))
    for match in re.finditer(r"\badd\s+([0-9]+)\s+to\s+([0-9]+)\b", text, re.I):
        patterns.append(("add", (int(match[2]), int(match[1]))))
    return list(dict.fromkeys(patterns))


def _near_copies(card: NormalizedConceptCard, question_numbers: set[int],
                 task: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Teaching items whose numbers the question mostly reuses (75% or more of its own numbers; at least 2 shared, 3 if all are single digits)."""
    found = []
    if task is not None:
        question_numbers = set(task["givens"].values())
    if len(question_numbers) < _NEAR_COPY_MIN_SHARED:
        return found
    for kind, items in (("explanation", card.explanations), ("example", card.examples)):
        for index, item in enumerate(items):
            record = None
            shared = sorted(question_numbers & (set(_numerals(item.text)) | set(_numerals(item.title or ""))))
            # Single-digit numbers coincide by chance (group counts, small sums), so they need three in common.
            needed = _NEAR_COPY_MIN_SHARED if any(number >= 10 for number in shared) else _NEAR_COPY_MIN_SHARED + 1
            if len(shared) >= needed and len(shared) / len(question_numbers) >= _NEAR_COPY_MIN_FRACTION:
                record = {"teaching_item": item.id or f"{kind}s[{index}]", "shared_numbers": shared,
                          "question_numbers": sorted(question_numbers),
                          "match": "all" if len(shared) == len(question_numbers) else "most"}
            operand_matches = []
            if task is not None and task["kind"] == "add_two":
                operands = tuple(task["givens"][role] for role in ROLES["add_two"])
                for operation, source in _teaching_arithmetic_pairs(item.text + " " + (item.title or "")):
                    if operation != "add":
                        continue
                    for aligned in (operands, operands[::-1]):
                        differences = [abs(a - b) for a, b in zip(aligned, source)]
                        if any(source[i] >= 100 and differences[i] == 0 and
                               differences[1 - i] <= _PROPOSED_CLOSE_ADD_DIFFERENCE for i in (0, 1)):
                            operand_matches.append({"operation": operation, "task_operands": list(aligned),
                                                    "source_operands": list(source), "operand_differences": differences,
                                                    "threshold": _PROPOSED_CLOSE_ADD_DIFFERENCE,
                                                    "threshold_status": "proposed_review_threshold"})
                            break
            if operand_matches:
                record = record or {"teaching_item": item.id or f"{kind}s[{index}]", "shared_numbers": shared,
                                    "question_numbers": sorted(question_numbers), "match": "close_operands"}
                record["operand_matches"] = operand_matches
            if record:
                found.append(record)
    return found


def _grounding(card: NormalizedConceptCard, difficulty: str, question_numbers: set[int],
               task: dict[str, Any] | None = None, *, performed: dict[str, bool]) -> tuple[dict[str, Any], list[str]]:
    """An explicit record of how far grounding was checked, so a human reviewer sees what was NOT verified."""
    near = _near_copies(card, question_numbers, task) if performed["numeric_near_copy"] else []
    checked = []
    if performed["teaching_refs"]:
        checked.append("cited teaching IDs exist and include the objective")
    if performed["numeric_near_copy"]:
        checked.append("original task operands (or legacy wording numerals) compared with teaching items (near-copy)")
    if performed["rationale_operations"]:
        checked.append("operation words in the rationale vs. the verified calculation")
    if performed["taught_operations"]:
        checked.append("the calculation uses only operations the card's teaching uses (the inverse of a taught add/subtract is allowed)")
    if performed["hard_teaching"]:
        checked.append("hard cites at least two taught items")
    grounding = {
        "confidence": "low_near_copy" if near else "structural_only",
        "checked": checked,
        "not_checked": ["that the question actually exercises the cited taught method (no semantic check is made)",
                        "that the wording is clear, unambiguous and age-appropriate",
                        "educational correctness beyond the arithmetic (see the verification scope)"],
        "near_copy": near,
        "task_scope": ("supported_bounded_task" if task is not None else
                       "unparsed_legacy_task" if performed["numeric_near_copy"] else "unsupported_arithmetic_short_text"),
    }
    if not performed["numeric_near_copy"]:
        grounding["not_checked"].append("numeric near-copy comparison skipped for unsupported short_text arithmetic")
    if not performed["rationale_operations"]:
        grounding["not_checked"].append("rationale operation/arithmetic consistency skipped for short_text")
    if task is None:
        grounding["not_checked"].append("task and wording consistency: unparsed legacy wording or unsupported short_text")
    if performed["numeric_near_copy"]:
        grounding["near_copy_scope"] = ("numeric overlap and explicit arithmetic operand patterns only; "
                                        "unparsed teaching stories are not interpreted; close-add threshold is proposed")
    flags = ["grounding_semantics_unverified"] + [f"near_copy_of_teaching_item:{item['teaching_item']}" for item in near]
    return grounding, flags


def _distinct_list(distinct_from: Any) -> list[dict[str, Any]]:
    """Normalise validated proposal(s) into comparison records; accepts one proposal or several."""
    if distinct_from is None:
        return []
    proposals = [distinct_from] if isinstance(distinct_from, dict) else list(distinct_from)
    if any(not isinstance(other, dict) for other in proposals):
        raise ValueError("distinctness comparisons must be proposal objects")
    return [{"label": other["difficulty"], "id": other["id"], "prompt": other["prompt"], "task": other.get("task"),
             "answer": other.get("expected_answer"), "quantities": proposal_quantities(other)} for other in proposals]


def _leaf_value(expression: Any) -> int | None:
    """The integer an expression leaf stands for, or None if it is not a leaf."""
    if type(expression) is int:
        return expression
    if isinstance(expression, dict):
        if set(expression) == {"number"} and type(expression["number"]) is int:
            return expression["number"]
        if set(expression) == {"type", "value"} and expression.get("type") == "integer" and type(expression["value"]) is int:
            return expression["value"]
        if set(expression) == {"operation", "value"} and expression.get("operation") == "number" and type(expression["value"]) is int:
            return expression["value"]
    return None


def _leaf_pools(expression: Any, pools: list[list[tuple[int, int]]], counter: list[int]) -> None:
    """Collect pools of (leaf id, value): the integer terms of one add chain, or the subtrahends of one subtract chain.

    A taught split of a stated number (110 = 100 + 10) can only come from inside one such pool, which is what
    makes replacing the parts by the whole an exact rewrite of the same arithmetic.
    """
    def new_leaf(value: int) -> tuple[int, int]:
        counter[0] += 1
        return counter[0], value

    def collect_add(node: dict, pool: list) -> None:
        for operand in node["operands"]:
            value = _leaf_value(operand)
            if value is not None:
                pool.append(new_leaf(value))
            elif isinstance(operand, dict) and operand.get("operation") == "add" and "operands" in operand:
                collect_add(operand, pool)
            else:
                walk(operand)

    def collect_subtrahends(node: dict, pool: list) -> None:
        left, right = node["operands"]
        value = _leaf_value(right)
        if value is not None:
            pool.append(new_leaf(value))
        elif isinstance(right, dict) and right.get("operation") == "add" and "operands" in right:
            collect_add(right, pool)
        else:
            walk(right)
        if isinstance(left, dict) and left.get("operation") == "subtract" and "operands" in left:
            collect_subtrahends(left, pool)
        elif _leaf_value(left) is None:
            walk(left)

    def walk(node: Any) -> None:
        if not (isinstance(node, dict) and isinstance(node.get("operands"), list) and len(node["operands"]) == 2):
            return
        pool: list[tuple[int, int]] = []
        if node.get("operation") == "add":
            collect_add(node, pool)
            pools.append(pool)
        elif node.get("operation") == "subtract":
            collect_subtrahends(node, pool)
            pools.append(pool)
        else:
            for operand in node["operands"]:
                walk(operand)

    walk(expression)


def _int_leaves(expression: Any) -> list[int]:
    value = _leaf_value(expression)
    if value is not None:
        return [value]
    if isinstance(expression, dict) and isinstance(expression.get("operands"), list):
        return [leaf for operand in expression["operands"] for leaf in _int_leaves(operand)]
    return []


def _has_identity_step(expression: Any) -> bool:
    """Identity nodes in a safely evaluated expanded AST, including computed operands."""
    if not (isinstance(expression, dict) and isinstance(expression.get("operands"), list)):
        return False
    if _identity_operation(expression, {}):
        return True
    return any(_has_identity_step(operand) for operand in expression["operands"])


def _identity_operation(expression: dict[str, Any], values: dict[str, int]) -> bool:
    """Whether this safely evaluated node adds no work; children still count."""
    left, right = [_evaluate_expression(operand, values)[0] for operand in expression["operands"]]
    operation = expression["operation"]
    return ((operation == "add" and (left == 0 or right == 0)) or
            (operation == "subtract" and right == 0) or
            (operation == "multiply" and (left == 1 or right == 1)) or
            (operation in _DIVISION_NODES and right == 1))


def _meaningful_operations(expression: Any, values: dict[str, int] | None = None) -> int:
    """Count native operations, excluding identities, without recounting refs."""
    if _leaf_value(expression) is not None or set(expression) == {"ref"}:
        return 0
    values = values or {}
    return (int(not _identity_operation(expression, values)) +
            sum(_meaningful_operations(operand, values) for operand in expression["operands"]))


def _part_dependencies(expression: Any) -> set[str]:
    if _leaf_value(expression) is not None:
        return set()
    if set(expression) == {"ref"}:
        return {expression["ref"]}
    return {ref for operand in expression["operands"] for ref in _part_dependencies(operand)}


def _dependency_path(part_id: str, dependencies: dict[str, set[str]]) -> set[str]:
    path = {part_id}
    for ref in dependencies[part_id]:
        path.update(_dependency_path(ref, dependencies))
    return path


def _hard_connection(final_part_id: str, dependencies: dict[str, set[str]], work: dict[str, int]) -> dict[str, Any]:
    path = _dependency_path(final_part_id, dependencies)
    edges = [{"part_id": part_id, "depends_on": source}
             for part_id in dependencies if part_id in path and work[part_id] > 0
             for source in dependencies if source != part_id and work[source] > 0
             and source in _dependency_path(part_id, dependencies)]
    return {"status": "operation_dependency_checked", "final_part_id": final_part_id,
            "dependencies": {part_id: sorted(refs) for part_id, refs in dependencies.items()},
            "meaningful_operations": work, "final_path": [part_id for part_id in dependencies if part_id in path],
            "operation_bearing_dependencies": edges}


def _route(expanded: Any) -> tuple[list[int], list[str]]:
    # Operand order is kept: re-adding in a different order or swapping the factors is a different route to the same value.
    # Repeating the identical calculation (or re-referencing a part) still has the same route and does not count.
    return _int_leaves(expanded), sorted(_operations_used(expanded))


def _cross_check_provenance(part_id: str, calculations: dict[str, Any], values: dict[str, int],
                            task: dict[str, Any], declared: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Trace a safely evaluated check AST, preserving native identities through refs.

    Only original givens and validated method data source literals. Computed
    values never enter the literal source table. A ref retains the expression
    that actually derived its value, rather than treating that value as a given.
    """
    chunks = {}
    for index, declaration in enumerate(declared):
        for leaf in declaration["leaves"]:
            chunks[(leaf["part_id"], tuple(leaf["path"]))] = {
                "kind": "decomposition", "index": index, "source": declaration["source"],
                "whole": declaration["whole"]}
    problems = []

    def trace(node: Any, native_part: str, path: tuple[int, ...]) -> dict[str, Any]:
        literal = _leaf_value(node)
        if literal is not None:
            sources = [{"kind": "given", "id": role} for role, value in task["givens"].items() if value == literal]
            sources.extend({"kind": "milestone", "id": milestone["id"], "derivation": dict(milestone)}
                           for milestone in task["milestones"] if milestone["value"] == literal)
            if (native_part, path) in chunks:
                sources.append(chunks[(native_part, path)])
            if not sources:
                problems.append(f"cross-check input provenance for {part_id}: literal {literal} at "
                                f"{native_part}{list(path)} is not an original task given, validated milestone "
                                "or declared decomposition leaf; derive it explicitly from those sources")
            return {"kind": "literal", "value": literal, "location": {"part_id": native_part, "path": list(path)},
                    "sources": sources}
        if "ref" in node:
            ref = node["ref"]
            return {"kind": "ref", "part_id": ref, "value": values[ref],
                    "derivation": trace(calculations[ref], ref, ())}
        operands = [trace(operand, native_part, path + (index,)) for index, operand in enumerate(node["operands"])]
        value, _, _ = _evaluate_expression(node, values)
        return {"kind": "expression", "operation": node["operation"], "operands": operands, "value": value}

    derivation = trace(calculations[part_id], part_id, ())
    return {"status": "inputs_traced", "part_id": part_id, "derivation": derivation}, problems


def _additive_signature(node: Any, part_id: str, path: tuple[int, ...], calculations: dict[str, Any],
                        declared: list[dict[str, Any]], legacy_splits: list[dict[str, Any]]) -> Counter | None:
    """Signed literal terms, following refs and collapsing only verified splits.

    This bounded normal form handles addition/subtraction regrouping and exact
    cancellation. It never substitutes a computed numeric total for an expression
    or expands multiplication. Native selectors govern task decomposition leaves.
    """
    occurrences = Counter()
    literals = {}

    def collect(expression: Any, native_part: str, native_path: tuple[int, ...], sign: int) -> bool:
        value = _leaf_value(expression)
        if value is not None:
            identity = (native_part, native_path)
            occurrences[identity] += sign
            literals[identity] = value
            return True
        if "ref" in expression:
            ref = expression["ref"]
            return collect(calculations[ref], ref, (), sign)
        if expression["operation"] not in ("add", "subtract"):
            return False
        left, right = expression["operands"]
        return (collect(left, native_part, native_path + (0,), sign) and
                collect(right, native_part, native_path + (1,), sign if expression["operation"] == "add" else -sign))

    if not collect(node, part_id, path, 1):
        return None
    signature = Counter()
    for declaration in declared:
        identities = [(leaf["part_id"], tuple(leaf["path"])) for leaf in declaration["leaves"]]
        coefficient = occurrences[identities[0]]
        if coefficient and all(occurrences[identity] == coefficient for identity in identities):
            for identity in identities:
                occurrences[identity] = 0
            signature[declaration["whole"]] += coefficient
    for identity, coefficient in occurrences.items():
        signature[literals[identity]] += coefficient
    # The taskless compatibility path retains its already-verified automatic
    # number splits. These never source literals in bounded-task provenance.
    for split in legacy_splits:
        chunks = Counter(split["parts"])
        for sign in (1, -1):
            count = min(sign * signature[value] // needed for value, needed in chunks.items())
            if count > 0:
                for value, needed in chunks.items():
                    signature[value] -= sign * count * needed
                signature[split["stated_number"]] += sign * count
    return Counter({value: coefficient for value, coefficient in signature.items() if coefficient})


def _additive_inverse_relation(part: dict[str, Any], calculations: dict[str, Any], values: dict[str, int],
                               wording: Counter, task: dict[str, Any] | None, declared: list[dict[str, Any]],
                               legacy_splits: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Recognize R-A=B for a sum, R+B=A or A-R=B for a difference.

    The check must directly ref R. Signed source terms establish the inverse
    relationship; numerical equality with a stated value alone is insufficient.
    """
    expression = part["calculation"]
    if not isinstance(expression, dict) or expression.get("operation") not in ("add", "subtract"):
        return None
    operation = expression["operation"]
    for ref_index, ref_node in enumerate(expression["operands"]):
        if not isinstance(ref_node, dict) or set(ref_node) != {"ref"}:
            continue
        result_id = ref_node["ref"]
        source = calculations[result_id]
        while isinstance(source, dict) and set(source) == {"ref"}:
            source = calculations[source["ref"]]
        source_operation = source.get("operation") if isinstance(source, dict) else None
        if operation == "subtract" and ref_index == 0 and source_operation == "add":
            form = "sum_minus_addend"
        elif operation == "add" and source_operation == "subtract":
            form = "difference_plus_subtrahend"
        elif operation == "subtract" and ref_index == 1 and source_operation == "subtract":
            form = "minuend_minus_difference"
        else:
            continue
        source_terms = _additive_signature(calculations[result_id], result_id, (), calculations, declared, legacy_splits)
        other_index = 1 - ref_index
        other_terms = _additive_signature(expression["operands"][other_index], part["id"], (other_index,),
                                         calculations, declared, legacy_splits)
        if not source_terms or not other_terms or any(count < 0 for count in other_terms.values()):
            continue
        positive = Counter({value: count for value, count in source_terms.items() if count > 0})
        negative = Counter({value: -count for value, count in source_terms.items() if count < 0})
        givens = list(task["givens"].items()) if task is not None else [(None, value) for value in wording]
        for role, given in givens:
            if given != values[part["id"]]:
                continue
            recovered = Counter({given: 1})
            if form == "sum_minus_addend":
                matches = not negative and positive == other_terms + recovered
            elif form == "difference_plus_subtrahend":
                matches = positive == recovered and negative == other_terms
            else:
                matches = positive == other_terms and negative == recovered
            if matches:
                return {"form": form, "checked_part_id": result_id, "checked_value": values[result_id],
                        "checked_operation": source_operation,
                        "recovered_given": ({"id": role, "value": given} if task is not None else
                                            {"source": "legacy_wording", "value": given})}
    return None


def _follow_refs(node: Any, calculations: dict[str, Any]) -> tuple[Any, str | None]:
    """Follow pure refs to the expression that really derives a value; returns (expression, the part id it came from)."""
    part_id = None
    while isinstance(node, dict) and set(node) == {"ref"}:
        part_id = node["ref"]
        node = calculations[part_id]
    return node, part_id


def _division_check_relation(part: dict[str, Any], calculations: dict[str, Any], values: dict[str, int],
                             task: dict[str, Any] | None) -> dict[str, Any] | None:
    """Recognize quotient x divisor + remainder = dividend (or quotient x divisor = dividend when nothing is left over).

    The check must directly ref the part that holds the quotient and, unless the division is exact, the part that holds the
    remainder; the divisor in the multiplication must be the task's divisor and the whole must equal the task's dividend.
    """
    if task is None or task["kind"] != "divide_two" or values[part["id"]] != task["givens"]["dividend"]:
        return None
    dividend, divisor = task["givens"]["dividend"], task["givens"]["divisor"]
    quotient, remainder = divmod(dividend, divisor)

    def product(node: Any) -> str | None:
        """The part id holding the quotient when node is (a ref to) quotient x divisor, else None."""
        expression, _ = _follow_refs(node, calculations)
        if not (isinstance(expression, dict) and expression.get("operation") == "multiply"):
            return None
        for a, b in (expression["operands"], expression["operands"][::-1]):
            holder = _follow_refs(a, calculations)[1] if isinstance(a, dict) and set(a) == {"ref"} else None
            if holder is not None and values[holder] == quotient and _leaf_value(b) == divisor:
                return holder
        return None

    def holds_remainder(node: Any) -> str | None:
        _, holder = _follow_refs(node, calculations)
        return holder if holder is not None and values[holder] == remainder else None

    expression = part["calculation"]
    if remainder == 0:
        holder = product(expression)
        if holder:
            return {"form": "quotient_times_divisor", "checked_part_id": holder, "checked_value": quotient,
                    "checked_operation": "quotient", "recovered_given": {"id": "dividend", "value": dividend}}
        return None
    if not (isinstance(expression, dict) and expression.get("operation") == "add"):
        return None
    for first, second in (expression["operands"], expression["operands"][::-1]):
        holder, left_over = product(first), holds_remainder(second)
        if holder and left_over:
            return {"form": "quotient_times_divisor_plus_remainder", "checked_part_id": holder, "checked_value": quotient,
                    "checked_operation": "quotient", "remainder_part_id": left_over,
                    "recovered_given": {"id": "dividend", "value": dividend}}
    return None


def _find_cross_check(parts: list[dict[str, Any]], expanded: list[Any], values: dict[str, int],
                      wording: Counter, *, task: dict[str, Any] | None = None,
                      declared: list[dict[str, Any]] | None = None,
                      legacy_splits: list[dict[str, Any]] | None = None,
                      checked_part_ids: set[str] | None = None,
                      provenance_problems: list[str] | None = None) -> dict[str, Any] | None:
    """Find a part that independently confirms another result. Pure code on the verified values.

    same_value_different_route: a later part reaches the same value as an earlier part using different numbers or
        different operations (references are inlined first, so repeating or re-referencing a part does not count).
    recovers_stated_number: a later part directly refs a named sum/difference and
        undoes it using a supported additive inverse form to recover an original given.
    Padding with + 0 or x 1, and parts with fewer than two numbers, never count.
    For bounded tasks, a candidate's inputs (including every ref ancestor) must
    have provenance. Try later candidates if one fails; report provenance errors
    only if no valid check exists. Taskless legacy fixtures retain their scope.
    """
    rejected = []
    calculations = {part["id"]: part["calculation"] for part in parts}
    for j, part in enumerate(parts):
        if _has_identity_step(expanded[j]) or len(_int_leaves(expanded[j])) < 2:
            continue
        value = values[part["id"]]
        candidate = None
        for i in range(j):
            if checked_part_ids is not None and parts[i]["id"] not in checked_part_ids:
                continue
            if values[parts[i]["id"]] == value and _route(expanded[i]) != _route(expanded[j]):
                candidate = {"status": "cross_check_found", "kind": "same_value_different_route",
                             "parts": [parts[i]["id"], part["id"]], "value": value}
                break
        uses_earlier = '"ref"' in json.dumps(part["calculation"])
        if candidate is None and uses_earlier and value in wording:
            candidate = {"status": "cross_check_found", "kind": "recovers_stated_number", "parts": [part["id"]], "value": value}
        if candidate is None:
            continue
        if task is not None:
            provenance, errors = _cross_check_provenance(part["id"], calculations, values, task, declared or [])
            if errors:
                rejected.extend(errors)
                continue
            candidate["input_provenance"] = provenance
        if candidate["kind"] == "recovers_stated_number":
            inverse = (_additive_inverse_relation(part, calculations, values, wording, task, declared or [], legacy_splits or [])
                       or _division_check_relation(part, calculations, values, task))
            if inverse is None:
                continue
            if checked_part_ids is not None and inverse["checked_part_id"] not in checked_part_ids:
                continue
            candidate["inverse_relation"] = inverse
            candidate["checked_part_id"] = inverse["checked_part_id"]
        else:
            candidate["checked_part_id"] = candidate["parts"][0]
        return candidate
    if provenance_problems is not None:
        provenance_problems.extend(dict.fromkeys(rejected))
    return None


_NUMBER_WORDS = {word: value for value, word in enumerate(
    ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
     "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"), 1)}
_NUMBER_WORDS["single"] = 1
_STEP_CLAIM = re.compile(
    r"(at least |a minimum of )?\b(" + "|".join(_NUMBER_WORDS) + r"|[0-9]+)"
    r"(?:[\s-]+(?!of\b|the\b|these\b|those\b|each\b|every\b|in\b|for\b|with\b|and\b|to\b|a\b|an\b|its\b|their\b)[a-z]+){0,2}?"
    r"[\s-]+steps?\b", re.I)


def _rationale_step_problem(rationale: str, effective_steps: int, nodes: int,
                            teaching_ids: set[str] | None = None) -> str | None:
    """A rationale that states a number of steps must agree with what was validated.

    'Steps' in prose means stages, not raw operations, so exact equality with the operation count would reject
    honest wording ('two taught steps: multiply, then add' for three operations). The rule is therefore:
    a question validated as ONE step may only claim one step; a multi-step question may claim 2 up to its
    operation count. 'at least N' is a lower bound.
    """
    text = _normalize_rationale_operations(rationale, teaching_ids or set())
    for match in _STEP_CLAIM.finditer(text):
        word = match.group(2).lower()
        claim = _NUMBER_WORDS.get(word) or int(word)
        at_least = bool(match.group(1))
        if effective_steps <= 1:
            ok = claim == 1 or (at_least and claim <= 1)
        else:
            ok = (2 <= claim <= nodes) or (at_least and claim <= nodes)
        if not ok:
            if effective_steps <= 1:
                return (f"difficulty_rationale claims {claim} steps, but this question validates as ONE step (calculation "
                        f"operations: {nodes}; splitting a number the question states into parts, such as 130 as 100 + 30, "
                        "counts as a single taught step). Describe it as one step, or leave the number of steps out")
            return (f"difficulty_rationale claims {claim} steps, but the verified calculation has {nodes} operations "
                    f"({effective_steps} counted steps); claim between 2 and {nodes} steps, or leave the number out")
    return None


def _numerals(text: str) -> Counter:
    return Counter(int(match) for match in re.findall(r"(?<!\d)-?\d+(?!\d)", text))


def _expand_part_refs(parts: list[tuple[str, Any]]) -> list[Any]:
    """Inline each {ref: id} with the earlier part's expression, so a chain of parts reads as one calculation."""
    import copy
    expanded: dict[str, Any] = {}

    def substitute(node: Any) -> Any:
        if isinstance(node, dict) and set(node) == {"ref"} and node["ref"] in expanded:
            return copy.deepcopy(expanded[node["ref"]])
        if isinstance(node, dict) and isinstance(node.get("operands"), list):
            return {**node, "operands": [substitute(operand) for operand in node["operands"]]}
        return node

    result = []
    for part_id, calculation in parts:
        expanded[part_id] = substitute(calculation)
        result.append(expanded[part_id])
    return result


def _reconcile_decompositions(calculations: list[Any], wording: Counter, inputs: list[int], raw_operations: int,
                              *, multiset: bool) -> tuple[list[dict[str, Any]], list[int], int]:
    """Accept calculations whose inputs add up to a number the wording states (110 stated; 100 and 10 used).

    Returns (decompositions, inputs with each stated whole accounted for, effective step count).
    Parts must be positive, lie in one add chain (or one set of subtrahends) and sum exactly to the stated whole.
      * collapse: the parts are NOT themselves stated (the whole is the question's number). The k parts become one
        operand, removing k-1 operations from the effective step count.
      * covered: the parts ARE stated too (for example each chunk appears in a part prompt). The whole is then
        accounted for by those inputs; nothing is collapsed.
    The reverse (a literal that is the SUM of two stated numbers) is deliberately not accepted.
    """
    if multiset:
        leftover = list((wording - Counter(inputs)).elements())
    else:
        leftover = sorted(set(wording) - set(inputs))
    if not leftover:
        return [], list(inputs), raw_operations
    pools: list[list[tuple[int, int]]] = []
    counter = [0]
    for calculation in calculations:
        _leaf_pools(calculation, pools, counter)
    remaining = Counter(inputs)  # a value can only be consumed as often as it is actually an input
    decompositions: list[dict[str, Any]] = []
    reconciled = list(inputs)
    steps = raw_operations

    def find(whole: int, collapse: bool) -> tuple[int, ...] | None:
        for pool in pools:
            candidates = [value for _, value in pool if 0 < value < whole and (value not in wording) == collapse]
            for size in range(2, min(len(candidates), 6) + 1):
                for group in combinations(candidates, size):
                    if sum(group) == whole and not (Counter(group) - remaining):
                        return group
        return None

    for whole in leftover:
        group = find(whole, collapse=True)
        if group:
            remaining.subtract(Counter(group))
            for part in group:
                reconciled.remove(part)
            reconciled.append(whole)
            steps -= len(group) - 1
            decompositions.append({"stated_number": whole, "parts": sorted(group, reverse=True), "mode": "collapsed"})
            continue
        group = find(whole, collapse=False)
        if group:
            reconciled.append(whole)  # the stated parts stay inputs; the whole is accounted for by them
            decompositions.append({"stated_number": whole, "parts": sorted(group, reverse=True), "mode": "parts_also_stated"})
    return decompositions, reconciled, steps


def _verify_declared_decompositions(declarations: Any, task: dict[str, Any],
                                    calculations: dict[str | None, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Check explicit splits on safely evaluated ASTs, retaining native leaf IDs.

    A selector is a part ID plus an operand-index path in that part's original
    calculation. Following refs while finding chains preserves those identities.
    The same native leaf therefore cannot be claimed again through another ref.
    """
    if not isinstance(declarations, list):
        raise ValueError("decompositions must be an array of explicit declarations")
    verified: list[dict[str, Any]] = []
    problems: list[str] = []
    consumed: set[tuple[str | None, tuple[int, ...]]] = set()
    pool_cache: dict[str | None, list[tuple[str, list[tuple[str | None, tuple[int, ...]]]]]] = {}
    sources = {
        "given": task["givens"],
        "milestone": {milestone["id"]: milestone["value"] for milestone in task["milestones"]},
    }

    def node_at(part_id: str | None, path: tuple[int, ...]) -> Any:
        node = calculations[part_id]
        for index in path:
            if not isinstance(node, dict) or "operands" not in node:
                raise ValueError("decomposition leaf path traverses a non-operation node")
            node = node["operands"][index]
        return node

    def pools_for(root: str | None) -> list[tuple[str, list[tuple[str | None, tuple[int, ...]]]]]:
        pools: list[tuple[str, list[tuple[str | None, tuple[int, ...]]]]] = []

        def dereference(part_id: str | None, path: tuple[int, ...]) -> tuple[Any, str | None, tuple[int, ...]]:
            node = node_at(part_id, path)
            while isinstance(node, dict) and set(node) == {"ref"}:
                part_id, path = node["ref"], ()
                node = calculations[part_id]
            return node, part_id, path

        def collect_add(part_id: str | None, path: tuple[int, ...], pool: list) -> None:
            node, part_id, path = dereference(part_id, path)
            if _leaf_value(node) is not None:
                pool.append((part_id, path))
            elif node.get("operation") == "add":
                collect_add(part_id, path + (0,), pool)
                collect_add(part_id, path + (1,), pool)
            else:
                walk(part_id, path)

        def collect_subtrahends(part_id: str | None, path: tuple[int, ...], pool: list) -> None:
            _, part_id, path = dereference(part_id, path)
            right, right_part, right_path = dereference(part_id, path + (1,))
            if _leaf_value(right) is not None:
                pool.append((right_part, right_path))
            elif right.get("operation") == "add":
                collect_add(right_part, right_path, pool)
            else:
                walk(right_part, right_path)
            left, left_part, left_path = dereference(part_id, path + (0,))
            if isinstance(left, dict) and left.get("operation") == "subtract":
                collect_subtrahends(left_part, left_path, pool)
            else:
                walk(left_part, left_path)

        def walk(part_id: str | None, path: tuple[int, ...]) -> None:
            node, part_id, path = dereference(part_id, path)
            if _leaf_value(node) is not None:
                return
            pool: list[tuple[str | None, tuple[int, ...]]] = []
            if node["operation"] == "add":
                collect_add(part_id, path, pool)
                pools.append(("add_chain", pool))
            elif node["operation"] == "subtract":
                collect_subtrahends(part_id, path, pool)
                pools.append(("subtract_chain", pool))
            else:
                walk(part_id, path + (0,))
                walk(part_id, path + (1,))

        walk(root, ())
        return pools

    for declaration in declarations:
        if not isinstance(declaration, dict) or set(declaration) != {"source", "calculation_part_id", "leaves"}:
            raise ValueError("decomposition requires exactly source, calculation_part_id and leaves")
        source = declaration["source"]
        if (not isinstance(source, dict) or set(source) != {"kind", "id"}
                or not isinstance(source["kind"], str) or source["kind"] not in sources or not _nonempty(source["id"])):
            raise ValueError("decomposition source needs kind given/milestone and a string id")
        root = declaration["calculation_part_id"]
        if root is not None and not _nonempty(root):
            raise ValueError("decomposition calculation_part_id must be a string or null for a number calculation")
        leaves = declaration["leaves"]
        if not isinstance(leaves, list) or len(leaves) < 2:
            raise ValueError("decomposition needs at least two exact calculation leaves")
        identities: list[tuple[str | None, tuple[int, ...]]] = []
        for leaf in leaves:
            if not isinstance(leaf, dict) or set(leaf) != {"part_id", "path"}:
                raise ValueError("decomposition leaf requires exactly part_id and path")
            if leaf["part_id"] is not None and not _nonempty(leaf["part_id"]):
                raise ValueError("decomposition leaf part_id must be a string or null")
            path = leaf["path"]
            if not isinstance(path, list) or any(type(index) is not int or index not in (0, 1) for index in path):
                raise ValueError("decomposition leaf path must be an array of operand indices 0 or 1")
            identities.append((leaf["part_id"], tuple(path)))
        if source["id"] not in sources[source["kind"]]:
            problems.append(f"decomposition source {source['id']!r} is not an original {source['kind']}")
            continue
        if root not in calculations:
            problems.append(f"decomposition calculation part {root!r} does not exist")
            continue
        if len(set(identities)) != len(identities):
            problems.append("decomposition cannot claim the same leaf occurrence twice")
            continue
        chunks: list[int] = []
        for part_id, path in identities:
            if part_id not in calculations:
                problems.append(f"decomposition leaf part {part_id!r} does not exist")
                continue
            try:
                node = node_at(part_id, path)
            except ValueError as exc:
                problems.append(str(exc))
                continue
            value = _leaf_value(node)
            if value is None:
                problems.append(f"decomposition leaf {part_id!r} at {list(path)} is not an integer literal leaf")
            else:
                chunks.append(value)
        if len(chunks) != len(identities):
            continue
        if any(value <= 0 for value in chunks):
            problems.append("decomposition chunks must be positive integers")
            continue
        whole = sources[source["kind"]][source["id"]]
        if sum(chunks) != whole:
            problems.append(f"declared decomposition of {whole} has chunks {chunks} which sum to {sum(chunks)}")
            continue
        if root not in pool_cache:
            pool_cache[root] = pools_for(root)
        placement = next((kind for kind, pool in pool_cache[root]
                          if all(Counter(pool)[identity] == 1 for identity in identities)), None)
        if placement is None:
            problems.append("decomposition leaves must lie in one permitted addition/subtraction chain of the declared calculation")
            continue
        if consumed.intersection(identities):
            problems.append("decomposition leaf occurrence is already used by another declaration")
            continue
        consumed.update(identities)
        verified.append({"source": dict(source), "whole": whole, "parts": chunks,
                         "calculation_part_id": root,
                         "leaves": [{"part_id": part_id, "path": list(path)} for part_id, path in identities],
                         "placement": placement})
    return verified, problems


def _stimulus_numbers(value: Any) -> list[int]:
    if type(value) is int:
        return [value]
    if isinstance(value, (str, type(None), bool)):
        return []
    if isinstance(value, list):
        return [number for item in value for number in _stimulus_numbers(item)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in _stimulus_numbers(item)]
    raise ValueError("stimulus contains an unsupported value")


def _canonical_partial_credit(criteria: list[Any], values: dict[str, int]) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    """Build exact grading rules and display prose from recomputed part answers."""
    for rule in criteria:
        if (not isinstance(rule, dict) or not _nonempty(rule.get("part_id")) or
                type(rule.get("points")) is not int or rule["points"] <= 0):
            raise ValueError("each partial-credit rule needs part_id and positive integer points")
        if rule.get("criterion") is not None and not isinstance(rule["criterion"], str):
            raise ValueError("partial-credit rule criterion must be text or null when supplied")
    if Counter(rule["part_id"] for rule in criteria) != Counter(values.keys()):
        return [], None, ["partial-credit rules must match answer parts exactly once"]
    rules = [{"part_id": rule["part_id"], "points": rule["points"],
              "answer_rule": {"type": "exact_integer", "value": values[rule["part_id"]]}} for rule in criteria]
    outward = [{"part_id": rule["part_id"], "points": rule["points"],
                "criterion": f"Correct: {rule['answer_rule']['value']}."} for rule in rules]
    record = {"status": "canonical_rules_derived", "rules": rules,
              "derivation": {"answer_source": "recomputed part calculations", "criterion_template": "Correct: {value}.",
                             "prose_source": "application rendering; original model prose retained in raw attempt response"}}
    return outward, record, []


def _canonical_full_credit(rules: list[dict[str, Any]], part_ids: list[str], final_part_id: str | None) -> tuple[str, dict[str, Any]]:
    """Render all required exact rules, with the task final explicitly designated."""
    by_id = {rule["part_id"]: rule for rule in rules}
    labels = {part_id: chr(ord("a") + index) for index, part_id in enumerate(part_ids)}
    total_points = sum(by_id[part_id]["points"] for part_id in part_ids)
    part_answers = "; ".join(f"part ({labels[part_id]}) = {by_id[part_id]['answer_rule']['value']}" for part_id in part_ids)
    text = f"Full credit: all {len(part_ids)} required parts correct ({total_points} points): {part_answers}."
    final_answer = None
    if final_part_id is not None:
        final_answer = by_id[final_part_id]["answer_rule"]["value"]
        text += f" Final answer: part ({labels[final_part_id]}) = {final_answer}."
    record = {"status": "canonical_full_credit_derived",
              "condition": {"type": "all_required_rules", "part_ids": part_ids}, "total_points": total_points,
              "final_part_id": final_part_id, "final_answer": final_answer,
              "derivation": {"rule_source": "verification.partial_credit.rules",
                             "final_part_source": "task.final_part_id" if final_part_id is not None else
                                                  "legacy taskless scope; no designated task final",
                             "statement_source": "application rendering of all required exact rules and designated final"}}
    return text, record


# Harmless vocabulary variants models use for the three supported response types. Anything else is still rejected.
_RESPONSE_TYPE_SYNONYMS = {
    "number": "number", "numeric": "number", "numerical": "number", "integer": "number", "int": "number",
    "whole_number": "number", "numeric_answer": "number", "number_answer": "number",
    "short_text": "short_text", "text": "short_text", "string": "short_text", "short_answer": "short_text",
    "free_text": "short_text", "short_response": "short_text",
    "multi_part": "multi_part", "multipart": "multi_part", "multiple_parts": "multi_part", "multi_step": "multi_part",
}


def _normalise_response_type(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    key = re.sub(r"[\s\-]+", "_", value.strip().lower())
    return _RESPONSE_TYPE_SYNONYMS.get(key, value)


def _refs_and_rationale(data: dict[str, Any], known_refs: set[str], objective_ref: str, difficulty: str,
                        problems: list[str]) -> tuple[list[str], str]:
    refs = data.get("teaching_refs")
    if not isinstance(refs, list) or not refs or any(not _nonempty(ref) for ref in refs):
        raise ValueError("teaching_refs must be a nonempty array of IDs")
    if len(refs) != len(set(refs)) or not set(refs) <= known_refs:
        raise ValueError(f"teaching_refs contain duplicate or unknown IDs: {refs}")
    others = [ref for ref in refs if ref != objective_ref]
    if objective_ref not in refs or len(others) < (2 if difficulty == "hard" else 1):
        raise ValueError(f"teaching_refs must include the objective ({objective_ref}) and "
                         f"{'two other taught items' if difficulty == 'hard' else 'another teaching item'}; you cited {refs}")
    rationale = data.get("difficulty_rationale")
    if difficulty == "easy" and not _nonempty(rationale):
        rationale = f"Directly checks the taught idea in {others[0]}."
    if not _nonempty(rationale):
        problems.append("difficulty_rationale must explain the requested level")
        rationale = ""
    elif not any(ref in rationale for ref in others):
        rationale = rationale.strip() + f" Grounded in {others[0]}."
    return refs, rationale


def _validate_typed(data: dict[str, Any], card: NormalizedConceptCard, known_refs: set[str], objective_ref: str,
                    difficulty: str, distinct_from: list[dict[str, Any]]) -> dict[str, Any]:
    """An easy/medium question whose task is a typed kind: the application renders it and the calculator computes the answer.

    The model's expected_answer, if it gives one, is only compared with the computed answer. It is never the source of it.
    """
    task = data["task"]
    rendered = calc_tasks.validate(task, contract_kinds(card), difficulty, card.concept_id)
    problems: list[str] = []
    refs, rationale = _refs_and_rationale(data, known_refs, objective_ref, difficulty, problems)
    claim = data.get("expected_answer")
    check = calculator.verify_claim(rendered.answer, claim)
    if claim is None:
        check["matches"] = None
    elif not check["matches"]:
        problems.append(f"incorrect answer: expected_answer {claim!r}, but code computed {rendered.answer.display}")
    for other in distinct_from:
        other_task = other.get("task") or {}
        if other.get("prompt") == rendered.prompt or other_task.get("givens") == task["givens"]:
            problems.append(f"{difficulty} question repeats the numbers of the {other['label']} question; choose different numbers")
        elif other.get("answer") is not None and str(other["answer"]) == rendered.answer.display:
            problems.append(f"{difficulty} question has the same answer as the {other['label']} question; choose different numbers")
    if problems:
        raise ValueError("; ".join(problems))
    grounding, review_flags = _grounding(card, difficulty, set(_numerals(rendered.prompt)), None,
                                         performed={"teaching_refs": True, "numeric_near_copy": True, "rationale_operations": False,
                                                    "hard_teaching": False, "taught_operations": False})
    grounding["task_scope"] = "supported_typed_task"
    grounding["not_checked"] = [note for note in grounding["not_checked"]
                                if not note.startswith(("task and wording consistency", "rationale operation/arithmetic"))]
    grounding["not_checked"].append("that the rationale's wording matches the computed operation (see wording_flags)")
    answer = rendered.answer.value if rendered.answer_type == "integer" else rendered.answer.display
    wording, wording_flags = _wording_record(rendered.prompt, set(KIND_OPERATIONS.get(task["kind"], ())))
    review_flags = review_flags + wording_flags
    verification = {
        "status": "code_verified", "computed_answer": rendered.answer.display, "answer_check": check,
        "checked_components": 1, "scope": "answer computed by calculator.py from the task givens; educational review pending",
        "calculation_steps": {"calculation_nodes": 1, "effective_steps": 1},
        "task": {"status": "task_answer_verified", "version": TASK_VERSION, "independent_answer": rendered.answer.display,
                 "wording_source": "application task template", "kind": task["kind"],
                 "scope": "typed task rendered and answered by the calculator; educational review pending"},
        "grounding": grounding, "wording_check": wording}
    if difficulty == "medium":
        verification["medium_basis"] = {"basis": "one_step_in_a_situation", "template": rendered.template,
                                        "scope": "approved situation template; educational review pending"}
    return {
        "id": "aq_" + uuid.uuid4().hex[:12], "concept_id": card.concept_id, "concept_version": card.card_version,
        "subject": card.subject, "grade": card.grade, "kind": "practice", "review_status": "draft",
        "review_flags": review_flags, "prompt": rendered.prompt, "difficulty": difficulty, "difficulty_rationale": rationale,
        "response_type": rendered.response_type, "answer_type": rendered.answer_type, "domain": rendered.domain,
        "stimulus": rendered.stimulus, "expected_answer": answer, "accepted_answers": rendered.accept,
        "marking_criteria": None, "partial_credit": False, "partial_credit_criteria": None, "teaching_refs": refs,
        "calculation": None, "answer_parts": None, "answer_verification": "code", "verification": verification, "task": task}


def _validate(raw: str, card: NormalizedConceptCard, known_refs: set[str], objective_ref: str, difficulty: str = "easy",
              distinct_from: list[dict[str, Any]] | None = None, *, allow_legacy: bool = False) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed model JSON at line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(data, dict):
        raise ValueError("model output must be one JSON object")
    # Shape errors still stop validation immediately. Independent content errors
    # are retained for the single repair, using evaluated values as their basis.
    problems: list[str] = []
    # The prompt names the level in capitals ("MEDIUM"), and some models echo that; the value is the same level.
    if not isinstance(data.get("difficulty"), str) or data["difficulty"].strip().lower() != difficulty:
        raise ValueError(f"difficulty must be {difficulty}")
    if not contract_kinds(card):
        return _validate_grounded(data, card, known_refs, objective_ref, difficulty, distinct_from or [])
    if (difficulty != "hard" and isinstance(data.get("task"), dict) and isinstance(data["task"].get("kind"), str)
            and data["task"]["kind"] in calc_tasks.KINDS
            # a reply that carries its own working calculation (the old long shape) is still checked by the old validator
            and (data["task"]["kind"] not in calc_tasks._ORIGINAL_RENDERER_KINDS or data.get("calculation") is None)):
        return _validate_typed(data, card, known_refs, objective_ref, difficulty, distinct_from or [])
    response_type = _normalise_response_type(data.get("response_type"))
    if response_type not in ("number", "short_text", "multi_part"):
        raise ValueError("unsupported response_type; expected number, short_text, or multi_part")
    if difficulty != "easy" and response_type == "short_text":
        raise ValueError("unsupported verification for medium/hard short_text response")
    if difficulty == "hard" and response_type != "multi_part":
        raise ValueError("hard question requires connected multi_part answers in this step")
    task = data.get("task")
    task_answer = None
    if "task" in data:
        if response_type == "short_text":
            raise ValueError("bounded task is not supported for short_text")
        task_answer, rendered_prompt, rendered_stimulus = validate_task(task, contract_kinds(card), difficulty, card.concept_id)
        if "prompt" in data and data["prompt"] != rendered_prompt:
            problems.append(f"prompt conflicts with task template; expected {rendered_prompt!r}")
        if data.get("stimulus") is not None and json.dumps(data["stimulus"], sort_keys=True) != json.dumps(rendered_stimulus, sort_keys=True):
            problems.append("stimulus conflicts with task; use only the application-rendered quantitative stimulus")
        data["prompt"] = rendered_prompt
        data["stimulus"] = rendered_stimulus
    elif response_type in ("number", "multi_part") and not allow_legacy:
        raise ValueError(f"new {response_type} response requires a task; legacy validation is available for saved easy proposals only")
    if not _nonempty(data.get("prompt")):
        raise ValueError("missing prompt")
    if task is None:  # model-written wording (the rendered task wording cannot contain an id)
        leaked = _leaked_id([data["prompt"]] + [part.get("prompt") for part in data.get("answer_parts") or [] if isinstance(part, dict)], card)
        if leaked:
            raise ValueError(f"learner-facing text names an internal id ({leaked!r}); describe the idea in plain words instead")
    stimulus = data.get("stimulus")
    if stimulus is not None and not isinstance(stimulus, dict):
        raise ValueError("stimulus must be an object or null")
    refs = data.get("teaching_refs")
    if not isinstance(refs, list) or not refs or any(not _nonempty(ref) for ref in refs):
        raise ValueError("teaching_refs must be a nonempty array of IDs")
    if len(refs) != len(set(refs)) or not set(refs) <= known_refs:
        raise ValueError(f"teaching_refs contain duplicate or unknown IDs: {refs}")
    if difficulty != "hard" and (objective_ref not in refs or len(refs) < 2):
        raise ValueError("teaching_refs must include the objective and another teaching item")
    if difficulty == "hard" and (objective_ref not in refs or len([ref for ref in refs if ref != objective_ref]) < 2):
        raise ValueError(f"hard question must cite the objective ({objective_ref}) AND at least two other taught items besides it "
                         f"(the methods it builds on), for example [\"{objective_ref}\", \"<first item>\", \"<second item>\"]; "
                         f"you cited {refs}")
    rationale = data.get("difficulty_rationale")
    if difficulty == "easy" and not _nonempty(rationale):
        rationale = f"Directly checks the taught idea in {next(ref for ref in refs if ref != objective_ref)}."
    if not _nonempty(rationale):
        problems.append("difficulty_rationale must explain the requested level")
    elif not any(ref in rationale for ref in refs if ref != objective_ref):
        rationale = rationale.strip() + f" Grounded in {next(ref for ref in refs if ref != objective_ref)}."
    partial = data.get("partial_credit")
    if not isinstance(partial, bool):
        raise ValueError("partial_credit must be boolean")
    partial_criteria = data.get("partial_credit_criteria")
    if partial and response_type != "multi_part" and not _nonempty(partial_criteria):
        problems.append("partial credit requires partial_credit_criteria")
    if not partial and partial_criteria not in (None, ""):
        problems.append("partial_credit_criteria must be null when partial credit is false")
    criteria = data.get("marking_criteria")
    if criteria is not None and (not isinstance(criteria, str) or (response_type != "multi_part" and not _nonempty(criteria))):
        raise ValueError("marking_criteria must be text or null")

    answer_parts = data.get("answer_parts")
    cross_check = None
    if response_type == "number":
        answer = data.get("expected_answer")
        if isinstance(answer, bool) or not isinstance(answer, int):
            raise ValueError("number response requires an integer expected_answer")
        if partial:
            problems.append("single-answer number question cannot have partial credit")
        if criteria is not None:
            problems.append("number response uses expected_answer; marking_criteria must be null")
        if answer_parts not in (None, []):
            raise ValueError("number response cannot have answer_parts")
        calc = data.get("calculation")
        if not isinstance(calc, dict):
            raise ValueError("number response requires a calculation expression")
        computed, inputs, operation_count = _evaluate_expression(calc)
        prompt_numbers = Counter(task["givens"].values()) if task is not None else _numerals(data["prompt"])
        decompositions, reconciled_inputs, effective_steps = _reconcile_decompositions(
            [calc], prompt_numbers, inputs, operation_count,
            multiset=task is None or task["kind"] != "two_equal_group_sets")
        if difficulty == "easy" and effective_steps != 1:
            problems.append(f"easy number question requires one calculation step; this one has {effective_steps}. "
                             "(Splitting a number the question states into parts that add back to it, such as 110 written "
                             "as 100 + 10, counts as one step, but only when the question states the whole number.)")
        medium_basis = None
        if difficulty == "medium":
            # Preserve taught split reconciliation, then discount only the
            # identity nodes. Easy retains its existing one-taught-step rule.
            effective_steps = max(0, effective_steps - (operation_count - _meaningful_operations(calc)))
            if effective_steps < 1:
                problems.append("medium number question requires at least one meaningful operation; a lookup, "
                                "+0, -0 or multiply-by-1 is not additional reasoning")
            elif effective_steps >= 2:
                medium_basis = "two_connected_steps"
            elif is_situation_task(task):
                medium_basis = "one_step_in_a_situation"
            else:
                problems.append(
                    "medium number question is a single bare calculation or lacks an approved situation template, "
                    "which is an easy-level question. A medium question "
                    "must either connect two taught steps (a calculation with two operations on numbers the question states) "
                    "or apply one meaningful step in a short real-world situation using an approved situation template "
                    "from its validated task. For addition use task.template add_shop_gains; the application renders "
                    "the quantities, their roles and the result question. Decoration and numeric magnitude do not qualify")
        if answer != computed:
            problems.append(f"incorrect numerical answer: expected_answer {answer}, calculation gives {computed}")
        if task is not None and computed != task_answer:
            problems.append(f"working calculation must equal independent task answer {task_answer}; calculation gives {computed}")
        verification = {"status": "arithmetic_verified", "computed_answer": computed,
                        "answer_check": {
                            "method": ("sympy exact evaluation of the working calculation, matched to the independent task formula"
                                       if task is not None else "sympy exact evaluation of the working calculation"),
                            "computed": str(computed), "engines": ["python", "sympy"], "claimed": str(answer),
                            "matches": answer == computed and (task is None or computed == task_answer)},
                        "checked_components": 1, "scope": "expression and numeric input alignment only; educational review pending",
                        "calculation_steps": {"calculation_nodes": operation_count, "effective_steps": effective_steps}}
        if decompositions:
            verification["decompositions"] = decompositions
        if medium_basis:
            verification["medium_basis"] = {"basis": medium_basis,
                "scope": "meaningful operation count and taught split reconciliation; educational review pending"}
            if medium_basis == "one_step_in_a_situation":
                verification["medium_basis"]["template"] = task["template"]
                verification["medium_basis"]["scope"] = (
                    "meaningful operation and approved rendered task situation; educational review pending")
    elif response_type == "multi_part":
        if difficulty != "hard":
            raise ValueError("multi_part is reserved for hard questions in this step")
        if data.get("expected_answer") is not None or data.get("calculation") is not None:
            raise ValueError("multi_part uses answer_parts, not expected_answer or calculation")
        if not isinstance(answer_parts, list) or len(answer_parts) < 3:
            raise ValueError("hard multi_part requires at least three answer_parts")
        if not partial:
            problems.append("multi_part requires partial credit")
        if not isinstance(partial_criteria, list):
            raise ValueError("multi_part partial_credit_criteria must be an array")
        prior_parts: dict[str, int] = {}
        inputs = []
        operation_count = 0
        prior_labels: dict[str, str] = {}
        for part in answer_parts:
            if not isinstance(part, dict) or not _nonempty(part.get("id")) or type(part.get("expected_answer")) is not int:
                raise ValueError("each answer part needs an ID and integer expected_answer")
            part_id = part["id"]
            if task is None and not _nonempty(part.get("prompt")):
                raise ValueError(f"answer part {part_id} needs a learner-facing prompt")
            if part_id in prior_parts:
                raise ValueError(f"duplicate answer part ID: {part_id}")
            value, part_inputs, part_ops = _evaluate_expression(part.get("calculation"), prior_parts)
            if task is not None:
                if not re.fullmatch(r"[a-z][a-z_]*", part_id):
                    raise ValueError("answer part ID must use lowercase letters and underscores")
                if part_id in {milestone["id"] for milestone in task["milestones"]} or part_id in task["givens"]:
                    raise ValueError("answer part ID must not shadow a task given or milestone")
                rendered_part = render_part_instruction(part.get("instruction"), part["calculation"], prior_labels)
                if "prompt" in part and part["prompt"] != rendered_part:
                    problems.append(f"answer part {part_id} prompt conflicts with its calculation instruction")
                part["prompt"] = rendered_part
            if value != part["expected_answer"]:
                problems.append(f"incorrect numerical answer for {part_id}: {part['expected_answer']}, calculation gives {value}")
            # A wrong declared answer must not corrupt later refs or rubric checks.
            prior_parts[part_id] = value
            prior_labels[part_id] = chr(ord("a") + len(prior_labels))
            inputs.extend(part_inputs)
            operation_count += part_ops
        if task is not None:
            final_part_id = task["final_part_id"]
            if final_part_id not in prior_parts:
                problems.append(f"task final_part_id {final_part_id!r} must identify an existing answer part")
            elif prior_parts[final_part_id] != task_answer:
                problems.append(f"hard final part {final_part_id}: independent task answer {task_answer}, "
                                f"recomputed answer {prior_parts[final_part_id]}")
        if task is not None:
            # Part text is derived output; it cannot establish original inputs.
            prompt_numbers = Counter(task["givens"].values())
        else:
            wording_parts = data["prompt"] + " " + " ".join(part["prompt"] for part in answer_parts)
            prompt_numbers = _numerals(wording_parts)
        expanded_parts = _expand_part_refs([(part["id"], part["calculation"]) for part in answer_parts])
        decompositions, reconciled_inputs, effective_steps = _reconcile_decompositions(
            expanded_parts, prompt_numbers, inputs, operation_count, multiset=False)
        dependencies = {part["id"]: _part_dependencies(part["calculation"]) for part in answer_parts}
        meaningful_work = {part["id"]: _meaningful_operations(part["calculation"], prior_parts) for part in answer_parts}
        meaningful_count = sum(meaningful_work.values())
        if meaningful_count < 3:
            problems.append("hard multi_part requires at least three meaningful connected calculation steps; "
                            "bare refs and +0, -0 or multiply-by-1 add no work")
        connection = None
        final_path = None
        if task is not None and task["final_part_id"] in dependencies:
            connection = _hard_connection(task["final_part_id"], dependencies, meaningful_work)
            final_path = set(connection["final_path"])
            if not connection["operation_bearing_dependencies"]:
                problems.append("hard multi_part requires an operation-bearing dependency on the path to final_part_id: "
                                "a meaningful operation builds on an earlier part with actual work; bare refs and "
                                "identity operations do not satisfy this")
        partial_criteria, partial_record, rule_problems = _canonical_partial_credit(partial_criteria, prior_parts)
        problems.extend(rule_problems)
        full_record = None
        if partial_record is not None and (task is None or task["final_part_id"] in prior_parts):
            criteria, full_record = _canonical_full_credit(partial_record["rules"], list(prior_parts),
                                                         task["final_part_id"] if task is not None else None)
        verification = {"status": "arithmetic_verified", "computed_answers": prior_parts,
                        "answer_check": {
                            "method": "sympy exact evaluation of every part, each matched to its claimed answer; the declared final "
                                      "part matched to the independent task formula",
                            "computed": str(prior_parts[task["final_part_id"]]) if task is not None and task["final_part_id"] in prior_parts
                                        else None,
                            "parts": {part_id: str(value) for part_id, value in prior_parts.items()},
                            "engines": ["python", "sympy"],
                            "matches": all(prior_parts.get(part["id"]) == part["expected_answer"] for part in answer_parts)
                                       and (task is None or prior_parts.get(task["final_part_id"]) == task_answer)},
                        "checked_components": len(answer_parts),
                        "scope": "expressions and numeric input alignment only; educational review pending",
                        "calculation_steps": {"calculation_nodes": operation_count, "effective_steps": meaningful_count}}
        if connection is not None:
            verification["connection"] = connection
        if partial_record is not None:
            verification["partial_credit"] = partial_record
        if full_record is not None:
            verification["full_credit"] = full_record
        if decompositions:
            verification["decompositions"] = decompositions
        answer = None
    else:
        if data.get("calculation") is not None:
            raise ValueError("short_text response cannot have a calculation")
        if answer_parts not in (None, []):
            raise ValueError("short_text response cannot have answer_parts")
        answer = data.get("expected_answer")
        if answer is not None and not _nonempty(answer):
            raise ValueError("short_text expected_answer must be text or null")
        if not _nonempty(answer) and not _nonempty(criteria):
            raise ValueError("short_text requires expected_answer or marking_criteria")
        if not _nonempty(criteria):
            raise ValueError("short_text requires explicit marking_criteria")
        verification = {"status": "unsupported", "scope": "free-text answer requires human review"}
        inputs = []
        reconciled_inputs = []

    if response_type != "short_text":
        number_inputs_match = (set(prompt_numbers) == set(reconciled_inputs)
                               if task is not None and task["kind"] == "two_equal_group_sets"
                               else prompt_numbers == Counter(reconciled_inputs))
        if response_type == "number" and not number_inputs_match:
            only_calc = sorted(set(reconciled_inputs) - set(prompt_numbers))
            only_wording = sorted(set(prompt_numbers) - set(reconciled_inputs))
            detail = f"; the wording states {sorted(prompt_numbers.elements())}, the calculation uses {sorted(reconciled_inputs)}"
            if only_calc:
                detail += (f"; the calculation uses {only_calc} which the wording does not state (use only numbers the question "
                           "states, or parts that ADD back to a stated number)")
            if only_wording:
                detail += f"; the wording states {only_wording} that the calculation does not use"
            problems.append("prompt digit numerals must match exactly the calculation operands" + detail)
        # Later parts legitimately reuse given numbers (e.g. recounting all groups), so
        # multi_part requires the same set of numbers, with every calculation input stated.
        if task is None and response_type == "multi_part" and set(prompt_numbers) != set(reconciled_inputs):
            only_calc = sorted(set(reconciled_inputs) - set(prompt_numbers))
            only_wording = sorted(set(prompt_numbers) - set(reconciled_inputs))
            detail = f"; wording has {sorted(prompt_numbers)}, calculations use {sorted(set(reconciled_inputs))}"
            if only_calc:
                detail += (f"; calculation uses {only_calc} which the wording does not state (a number you derive, such as "
                           "an intermediate total, must be written as an operation on stated numbers, not as a literal)")
            if only_wording:
                detail += f"; wording states {only_wording} that no calculation uses"
            problems.append("question wording numbers must match the calculation inputs" + detail)
        if task is None:
            stimulus_numbers = Counter(_stimulus_numbers(stimulus))
            if any(count > prompt_numbers[number] for number, count in stimulus_numbers.items()):
                problems.append("stimulus numbers must agree with the prompt and calculation inputs")

    calculations = [data.get("calculation")] + [part["calculation"] for part in answer_parts or []]
    calculations = [c for c in calculations if c is not None]
    declared = []
    declaration_problems = []
    if "decompositions" in data:
        if not isinstance(data["decompositions"], list):
            raise ValueError("decompositions must be an array of explicit declarations")
        if data["decompositions"] and task is None:
            raise ValueError("declared decompositions require a bounded task with named givens/milestones")
        if task is not None:
            native_calculations = ({part["id"]: part["calculation"] for part in answer_parts}
                                   if response_type == "multi_part" else {None: data["calculation"]})
            declared, declaration_problems = _verify_declared_decompositions(data["decompositions"], task, native_calculations)
            problems.extend(declaration_problems)
            if declared:
                verification["declared_decompositions"] = declared
    if response_type != "short_text":
        if _nonempty(rationale):
            teaching_ids = known_refs | {item.id for item in (card.objective, *card.explanations, *card.examples)
                                         if item.id}
            problem = _rationale_operation_problem(rationale, calculations, teaching_ids)
            if problem:
                problems.append(problem)
            step_problem = _rationale_step_problem(
                rationale, effective_steps if response_type == "number" else meaningful_count,
                operation_count if response_type == "number" else meaningful_count, teaching_ids)
            if step_problem:
                problems.append(step_problem)
        used: set[str] = set()
        for calculation in calculations:
            _operations_used(calculation, used)
        verification["rationale_ops"] = {"status": "rationale_ops_consistent", "verified_operations": sorted(used),
                                         "scope": "operation words in the rationale vs. verified calculation; not educational review"}
    if difficulty == "hard" and response_type == "multi_part":
        provenance_problems = []
        # Provenance depends on validated declarations. Do not add follow-on
        # failures while their sources are unusable; independent errors remain.
        if not declaration_problems:
            cross_check = _find_cross_check(answer_parts, expanded_parts, prior_parts, prompt_numbers,
                                          task=task, declared=declared, provenance_problems=provenance_problems,
                                          legacy_splits=verification.get("decompositions", []) if task is None else [],
                                          checked_part_ids=final_path)
            problems.extend(provenance_problems)
        if cross_check is None and not declaration_problems and not provenance_problems:
            problems.append("hard question needs a cross-check part: a later part must reach the SAME value as an earlier part "
                            "by a different route (different numbers or operations, for example the same total counted a "
                            "second taught way), or directly ref a named sum/difference and undo it with a supported "
                            "additive inverse to recover a specific original given. A coincidentally equal number is "
                            "insufficient. The check must verify the final result or a result on its derivation path. "
                            "Adding 0, multiplying by 1, or repeating a part does not count. Your part "
                            f"values were {prior_parts}")
        elif cross_check is not None:
            if task is None:
                # Legacy fixtures have no declared final. Use the named checked
                # result for their connection check without making a task claim.
                connection = _hard_connection(cross_check["checked_part_id"], dependencies, meaningful_work)
                connection["scope"] = "legacy checked-result path; no declared task final"
                verification["connection"] = connection
                final_path = set(connection["final_path"])
                if not connection["operation_bearing_dependencies"]:
                    problems.append("hard multi_part requires an operation-bearing dependency: a meaningful operation "
                                    "builds on an earlier part with actual work, rather than a bare ref or identity")
            if final_path is not None:
                work_path = final_path | _dependency_path(cross_check["parts"][-1], dependencies)
                connected_count = sum(meaningful_work[part_id] for part_id in work_path)
                verification["calculation_steps"]["effective_steps"] = connected_count
                connection["work_path"] = [part_id for part_id in dependencies if part_id in work_path]
                if connected_count < 3 and meaningful_count >= 3:
                    problems.append("hard multi_part requires at least three meaningful steps in the final derivation "
                                    "and its cross-check; unrelated calculations do not count")
            verification["cross_check"] = {**cross_check, "scope": (
                "check inputs traced to task sources and values agree by code; educational review pending"
                if task is not None else "the values agree by code; whether the part truly checks the idea is not judged")}
            if cross_check["kind"] == "recovers_stated_number":
                relation = cross_check["inverse_relation"]
                given = relation["recovered_given"]
                verification["cross_check"]["scope"] = (
                    f"{'multiplying back from' if relation['form'].startswith('quotient') else 'additive inverse of'} "
                    f"named result {relation['checked_part_id']} ({relation['checked_value']}) "
                    f"recovers original given {given.get('id', given.get('source'))} ({given['value']}); "
                    + ("inputs traced to task sources; " if task is not None else "legacy wording scope; ")
                    + "educational review pending")
    if response_type != "short_text":
        taught = _permitted_operations(card)
        # The question may use only what the lesson teaches. The one cross-check part may use any mathematically exact
        # equivalent (re-adding in another order, swapping factors, repeated addition, multiplying back from a division):
        # it is code-verified against the working, and it is not a method the learner is being taught.
        check_part = cross_check["parts"][-1] if cross_check is not None else None
        working = [data.get("calculation")] + [part["calculation"] for part in answer_parts or [] if part["id"] != check_part]
        working = [c for c in working if c is not None]
        untaught = sorted(set(_operations_used_all(working)) - set(taught) - set(_DIVISION_NODES if "divide" in taught else ()))
        if untaught:
            problems.append(f"{difficulty} question uses {untaught}, which this card's teaching items never use (taught operations: "
                            f"{taught}); build the question from the taught methods only")
        verification["taught_operations"] = {"status": "operations_checked_against_teaching", "taught": taught}
        if check_part is not None:
            exempt = sorted(set(_operations_used_all([part["calculation"] for part in answer_parts if part["id"] == check_part]))
                            - set(taught) - {"divide"})
            verification["taught_operations"]["exempt_cross_check_operations"] = exempt
            verification["taught_operations"]["cross_check_part"] = check_part
    if distinct_from:
        mine = proposal_quantities({"calculation": data.get("calculation"), "answer_parts": answer_parts})
        comparisons = []
        for other in distinct_from:
            label, theirs = other["label"], other["quantities"]
            if not mine["answers"] or not theirs["answers"]:
                comparisons.append({"label": label, "proposal_id": other["id"], "status": "unsupported",
                                    "scope": "numeric distinctness unsupported for a nonnumeric question"})
                continue
            # Compare the distinct quantities: a multi-part question restates numbers when recounting,
            # so a multiset comparison would miss a question built on the same numbers.
            if set(mine["inputs"]) == set(theirs["inputs"]):
                problems.append(f"{difficulty} question reuses the exact input numbers {sorted(set(mine['inputs']))} of the "
                                f"{label} question; use different quantities")
                continue
            # A learner who did the other question has computed all of its values, intermediate steps included.
            shared = sorted(set(mine["values"]) & set(theirs["values"]))
            if shared:
                problems.append(f"{difficulty} question computes {shared[0]}, a value the {label} question also computes "
                                f"(its values: {theirs['values']}), so solving one gives away part of the other; "
                                "use different quantities")
                continue
            comparisons.append({"label": label, "proposal_id": other["id"], "other_inputs": theirs["inputs"],
                                "other_values": theirs["values"]})
        labels = [c["label"] for c in comparisons if c.get("status") != "unsupported"]
        unsupported = [c["label"] for c in comparisons if c.get("status") == "unsupported"]
        verification["distinctness_verified_against"] = labels
        verification["distinctness"] = {
            "status": ("partial_numeric_distinctness" if labels else "unsupported_numeric_distinctness")
                      if unsupported else "distinctness_verified",
            "verified_against": labels, "unsupported_against": unsupported, "comparisons": comparisons,
            "this_inputs": mine["inputs"], "this_values": mine["values"],
            "scope": "input numbers and every computed value differ for supported numeric comparisons only; not educational review"}
    if problems:
        raise ValueError("; ".join(problems))
    if response_type != "short_text" and not (verification.get("answer_check") or {}).get("matches"):
        raise ValueError("a calculation question must record a code-verified answer_check; this one did not")
    grounding, review_flags = _grounding(
        card, difficulty, set(prompt_numbers) if response_type != "short_text" else set(), task,
        performed={"teaching_refs": True, "numeric_near_copy": response_type != "short_text",
                   "rationale_operations": "rationale_ops" in verification,
                   "hard_teaching": difficulty == "hard" and "taught_operations" in verification,
                   "taught_operations": "taught_operations" in verification})
    verification["grounding"] = grounding
    if response_type != "short_text":
        verified_ops = {"divide" if name in _DIVISION_NODES else name for name in _operations_used_all(calculations)}
        verification["wording_check"], wording_flags = _wording_record(data["prompt"], verified_ops)
        review_flags = review_flags + wording_flags
    if task is not None:
        verification["task"] = {
            "status": "task_answer_verified",
            "version": TASK_VERSION, "independent_answer": task_answer,
            "wording_source": "application task template and calculation instructions",
            "scope": "bounded task formula and rendered wording; educational review pending",
        }
        if response_type == "multi_part":
            verification["task"].update(final_part_id=task["final_part_id"],
                                        computed_final_answer=prior_parts[task["final_part_id"]])
    elif response_type != "short_text":
        verification["task"] = {"status": "legacy_arithmetic_only", "scope": "task and wording consistency not checked"}

    return {
        "id": "aq_" + uuid.uuid4().hex[:12],
        "concept_id": card.concept_id,
        "concept_version": card.card_version,
        "subject": card.subject,
        "grade": card.grade,
        "kind": "practice",
        "review_status": "draft",
        "review_flags": review_flags,
        "prompt": data["prompt"].strip(),
        "difficulty": difficulty,
        "difficulty_rationale": rationale,
        "response_type": response_type,
        "stimulus": stimulus,
        "expected_answer": answer,
        "marking_criteria": criteria,
        "partial_credit": partial,
        "partial_credit_criteria": partial_criteria,
        "teaching_refs": refs,
        "calculation": data.get("calculation"),
        "answer_parts": answer_parts,
        "answer_verification": "code" if response_type != "short_text" else "none",
        "verification": verification,
        **({"task": task} if task is not None else {}),
        **({"decompositions": data["decompositions"]} if "decompositions" in data else {}),
    }


# Codes that mean the provider itself is unusable, so a batch stops rather than failing every card the same way.
PROVIDER_FAILURE_CODES = ("quota_exhausted", "model_request_failed", "rate_limited", "auth_failed", "provider_unavailable")


def _request_error_code(exc: ModelRequestError) -> str:
    """What a failed request means for a long run. A bad key or a provider that is down is everyone's problem and stops the
    batch; a request the provider rejected, or a reply that was too long, is only this question's problem."""
    status = getattr(exc, "status", None)
    kind = getattr(exc, "kind", None)
    if status in (401, 403):
        return "auth_failed"
    if status in (400, 404, 413, 422) or kind == "length":
        return "request_rejected"
    if (isinstance(status, int) and status >= 500) or status == 408 or kind in ("unreachable", "bad_response"):
        return "provider_unavailable"
    return "model_request_failed"


def generate_one(card: NormalizedConceptCard, client: ModelClient, config: GenerationConfig | None = None,
                 *, difficulty: str = "easy", distinct_from: Any = None, scaffold_of: dict[str, Any] | None = None) -> GenerationResult:
    """distinct_from: one validated proposal, or a list of them, whose numbers and values this one must not reuse.

    scaffold_of: a validated harder proposal. The model is shown only that proposal's teaching items and asked for a
    question one step simpler on the same idea; the usual validation, including the cited-items check, is unchanged.
    """
    config = config or GenerationConfig()
    started = time.perf_counter()
    attempts: list[AttemptLog] = []
    if difficulty not in ("easy", "medium", "hard"):
        return GenerationResult(None, GenerationError("unsupported_difficulty", f"unsupported difficulty: {difficulty}"), (), time.perf_counter() - started)
    kinds = contract_kinds(card)
    if difficulty == "hard" and kinds and not any(kind in HARD_KINDS for kind in kinds):
        return GenerationResult(None, GenerationError("hard_not_supported", _hard_unsupported_reason(card, kinds)), (),
                                time.perf_counter() - started)
    if difficulty == "hard" and kinds:
        plan = _hard_plan(card, config)
        if plan["insufficient"]:
            return GenerationResult(None, GenerationError("insufficient_teaching_for_hard", plan["insufficient"]), (),
                                    time.perf_counter() - started)
    try:
        distinct = _distinct_list(distinct_from)
        items, known_refs, prompt = _teaching_context(card, config, difficulty, distinct, scaffold_of)
    except (ValueError, KeyError, TypeError) as exc:
        return GenerationResult(None, GenerationError("invalid_teaching_refs", str(exc)), (), time.perf_counter() - started)
    objective_ref = items[0]["id"]
    messages = [
        {"role": "system", "content": "You write one draft educational question. Reply with a single JSON object and nothing "
         "else: no commentary, no markdown fences, no text before or after it. Use exactly the field names the instructions list."},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(1, config.max_repair_requests + 2):
        attempt_started = time.perf_counter()
        raw: str | None = None
        returned_model_text = False
        served_by = None
        try:
            raw = client.chat(messages, timeout=config.timeout, max_output_tokens=config.max_output_tokens)
            returned_model_text = True
            served_by = getattr(client, "last_served_by", getattr(client, "backend_name", None))
            proposal = _validate(raw, card, known_refs, objective_ref, difficulty, distinct)
            attempts.append(AttemptLog(attempt, time.perf_counter() - attempt_started, raw, None, True, served_by))
            return GenerationResult(proposal, None, tuple(attempts), time.perf_counter() - started)
        except TimeoutError as exc:
            attempts.append(AttemptLog(attempt, time.perf_counter() - attempt_started, raw, str(exc)))
            return GenerationResult(None, GenerationError("timeout", str(exc)), tuple(attempts), time.perf_counter() - started)
        except QuotaExhaustedError as exc:
            attempts.append(AttemptLog(attempt, time.perf_counter() - attempt_started, exc.raw_response or raw, str(exc)))
            return GenerationResult(None, GenerationError("quota_exhausted", str(exc)), tuple(attempts), time.perf_counter() - started)
        except RateLimitError as exc:
            attempts.append(AttemptLog(attempt, time.perf_counter() - attempt_started, exc.raw_response or raw, str(exc)))
            return GenerationResult(None, GenerationError("rate_limited", str(exc)), tuple(attempts), time.perf_counter() - started)
        except ModelRequestError as exc:
            attempts.append(AttemptLog(attempt, time.perf_counter() - attempt_started, exc.raw_response or raw, str(exc)))
            return GenerationResult(None, GenerationError(_request_error_code(exc), str(exc)), tuple(attempts), time.perf_counter() - started)
        except ValueError as exc:
            reason = str(exc)
            attempts.append(AttemptLog(attempt, time.perf_counter() - attempt_started, raw, reason, returned_model_text, served_by))
            if attempt > config.max_repair_requests:
                return GenerationResult(None, GenerationError("validation_failed", reason), tuple(attempts), time.perf_counter() - started)
            messages.append({"role": "assistant", "content": raw or ""})
            hint = ""
            if "requires a task" in reason or "prompt conflicts" in reason or "stimulus conflicts with task" in reason:
                hint += (" Supply the bounded task using the allowed kind, named integer givens, milestones, template and "
                         "final_part_id from the original instructions. Omit prompt and stimulus: the application renders "
                         "them. For answer parts supply instruction:{kind:'calculate'} and omit their prompts.")
            if "independent task answer" in reason:
                if difficulty == "hard":
                    hint += (" Recompute the part named by task.final_part_id from the task givens so it answers that task, "
                             "then update that part's expected_answer and affected partial-credit criteria. A later inverse "
                             "check may remain last; it need not be the final result.")
                else:
                    hint += " Recompute the working calculation from the task givens so it answers that task, then update expected_answer."
            if "final_part_id" in reason and "existing answer part" in reason:
                hint += " Set task.final_part_id to the existing part that answers the task; do not assume the last part is the answer."
            if "decomposition" in reason:
                hint += (" Correct every declared split: name the original given or validated milestone, select the exact "
                         "native positive integer leaves by part_id and operand-index path, and make their sum equal that "
                         "source. They must belong to one addition/subtraction chain reached from calculation_part_id. "
                         "A literal whole in a check does not validate the split; each leaf occurrence can be claimed once.")
            if "cross-check input provenance" in reason:
                hint += (" Build the cross-check from named task givens, validated milestones or exact declared split leaves. "
                         "Write derived quantities as explicit expressions from those sources, or ref a part that derives "
                         "them explicitly. A matching expected/computed value or part prompt cannot source a literal.")
            if "difficulty_rationale names" in reason:
                hint += (" Rewrite difficulty_rationale so that it describes the steps using only the operations in your "
                         "verified calculation, and delete any mention of "
                         "the flagged operation or method.")
            if "use different quantities" in reason:
                # List every forbidden value, not only the ones from the comparison that failed: fixing one
                # collision blindly tends to create another with the other question.
                forbidden = sorted({value for other in distinct for value in other["quantities"]["values"]})
                hint += (f" Choose new numbers for the task givens. No value you compute, including intermediate results and totals, "
                         f"may be any of these: {forbidden}. Check each result against that list, then recompute "
                         "every answer and calculation; the application renders the rubric from verified rules.")
                if _unused_small_numbers(distinct, card=card):
                    hint += f" Numbers the other question(s) do not use: {_unused_small_numbers(distinct, card=card)}."
            if "that no calculation uses" in reason or "digit numerals must match" in reason or "names an internal id" in reason:
                hint += (" Every digit in the prompt and part prompts must be a number your calculations use. Write any "
                         "other count as a word (for example 'two sets') or remove it. Never write a part id or {ref: ...} "
                         "inside a learner-facing prompt; those are internal, so tell the learner what to do in plain words.")
            if "digit numerals must match exactly" in reason and "does not state" in reason:
                hint += (" Do not rebuild a number the question states with multiplication or other operations. If the "
                         "taught method splits a stated number, write only the parts that ADD back to it (for example 210 "
                         "as 200 and 10, in an add), or simply use the stated number itself.")
            if "partial-credit rules must match" in reason:
                if "incorrect numerical answer" in reason:
                    hint += " Recompute every expected_answer from its calculation before updating the partial-credit criteria."
                hint += (" Make partial-credit part_id values match the answer part ids, exactly one rule per part, "
                         "with positive integer points. The application derives each exact integer answer rule and "
                         "criterion prose from recomputed values; model prose cannot supply a different grading rule.")
            if "needs a cross-check part" in reason:
                hint += (" Add one more answer part (with its own prompt, calculation, expected_answer and partial-credit rule) "
                         "that reaches the same value as an earlier part by a different calculation. For an inverse check, "
                         "directly ref the named result being checked: undo R=A+B with R-A=B or R-B=A, or undo R=A-B "
                         "with R+B=A (either add order) or A-R=B. Recover a specific original task given through that "
                         "relationship; merely reaching its numeric value does not count.")
            if "operation-bearing dependency" in reason or "at least three meaningful" in reason:
                hint += (" Make actual operations on earlier working answers contribute to task.final_part_id. "
                         "Bare refs and identity operations cannot create work. Keep at least three meaningful "
                         "operations in that final derivation and its check; have the check verify the final result "
                         "or one of its dependencies.")
            if "at least one meaningful operation" in reason:
                hint += (" Replace the lookup or identity-only calculation with actual taught work on the task givens. "
                         "Identity padding cannot create a medium reasoning step; keep the task answer and rubric consistent.")
            if "which the wording does not state" in reason:
                hint += " Do not write a derived number as a literal. Build it explicitly from the original task givens."
                if any(kind in _GROUP_KINDS for kind in contract_kinds(card)):
                    hint += " For equal groups, derive combined group counts as add(a,b) before multiplying by the group size."
            if "with two operands" in reason:
                example_operation = {"add_two": "add", "subtract_two": "subtract"}.get((contract_kinds(card) or ("",))[0], "multiply")
                hint += (" Every operation needs exactly two operands, "
                         f"e.g. {{operation:'{example_operation}',operands:[x,y]}}.")
            messages.append({"role": "user", "content": f"Repair the JSON. Validation error: {reason}.{hint} "
                             "Fix every reported error in this single repair. Return one corrected JSON object only."})
    raise AssertionError("unreachable")


def validate_saved_proposal(proposal: dict[str, Any], card: NormalizedConceptCard,
                            config: GenerationConfig | None = None) -> dict[str, Any]:
    """Recheck a saved draft without changing its ID.

    Only easy caches have a taskless legacy path. Hard caches must supply the
    bounded task and pass the same recomputed final-part check as generation.
    """
    config = config or GenerationConfig()
    if not isinstance(proposal, dict):
        raise ValueError("saved proposal must be an object")
    for key, expected in (("concept_id", card.concept_id), ("concept_version", card.card_version),
                          ("subject", card.subject), ("grade", card.grade), ("review_status", "draft")):
        if proposal.get(key) != expected:
            raise ValueError(f"saved proposal {key} does not match the concept card")
    if not _nonempty(proposal.get("id")):
        raise ValueError("saved proposal is missing its application-assigned ID")
    difficulty = proposal.get("difficulty")
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError("saved proposal has unsupported difficulty")
    items, known_refs, _ = _teaching_context(card, config, difficulty)
    checked = _validate(json.dumps(proposal), card, known_refs, items[0]["id"], difficulty, allow_legacy=difficulty == "easy")
    checked["id"] = proposal["id"]
    return checked

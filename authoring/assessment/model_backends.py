"""Select the generation backend (local Ollama or Groq) from command-line options and environment."""

from __future__ import annotations

import argparse
import os
import time

from question_generator import FallbackClient, GroqClient, ModelClient, ModelConfigError, OllamaClient, OpenAIClient

DEFAULT_BACKEND = "ollama"
DEFAULT_OLLAMA_MODEL = "qwen3.5:9b-q4_K_M"
# A reasoning model that Groq's docs list on the free plan; override with --model or GROQ_MODEL.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class PacedClient:
    """Wrap a client so successive requests are at least ``gap`` seconds apart (it never changes what a 429 does).

    Groq's free tier caps tokens per minute (8,000 for gpt-oss-120b at the time of writing), and a request is counted at its
    full prompt plus its maximum output, so back-to-back requests can be refused although none is large. A gap keeps a build under
    that cap. The first request does not wait. The gap is measured from the end of the previous request, failed or not.
    """

    def __init__(self, inner: ModelClient, gap: float, *, sleep=time.sleep, clock=time.monotonic):
        if gap < 0:
            raise ValueError("the pacing gap must not be negative")
        self._inner, self._gap, self._sleep, self._clock = inner, gap, sleep, clock
        self._last_end: float | None = None

    def chat(self, messages, *, timeout, max_output_tokens):
        if self._last_end is not None:
            remaining = self._gap - (self._clock() - self._last_end)
            if remaining > 0:
                self._sleep(remaining)
        try:
            return self._inner.chat(messages, timeout=timeout, max_output_tokens=max_output_tokens)
        finally:
            self._last_end = self._clock()

    def __getattr__(self, name):  # last_served_by, backend_name, list_models ...
        return getattr(self._inner, name)


def add_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", choices=("ollama", "groq", "openai"), default=os.getenv("EDAPTIVE_BACKEND", DEFAULT_BACKEND),
                        help=f"generation backend (default: {DEFAULT_BACKEND}; ollama is the local model; openai needs OPENAI_API_KEY and an explicit model)")
    parser.add_argument("--endpoint", default=None,
                        help="override the backend endpoint (ollama: EDAPTIVE_OLLAMA_ENDPOINT or http://127.0.0.1:11434)")
    parser.add_argument("--model", default=None,
                        help=f"model name (groq default {DEFAULT_GROQ_MODEL}, ollama default {DEFAULT_OLLAMA_MODEL}; "
                             "openai has no default: pass this or set OPENAI_MODEL)")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"), default=None,
                        help="groq only; defaults to 'low' for gpt-oss models and is not sent otherwise")
    parser.add_argument("--list-models", action="store_true", help="groq or openai: print the model IDs your key can use, then exit")


def add_fallback_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-fallback", action="store_true",
                        help="groq only: stop with an error when the daily quota is exhausted instead of using the local model")
    parser.add_argument("--fallback-model", default=None, help=f"local model used after Groq's daily quota is exhausted "
                                                               f"(default EDAPTIVE_MODEL or {DEFAULT_OLLAMA_MODEL})")
    parser.add_argument("--fallback-endpoint", default=None,
                        help="local Ollama endpoint for the fallback (default EDAPTIVE_OLLAMA_ENDPOINT or http://127.0.0.1:11434)")


def resolve(args: argparse.Namespace) -> None:
    """Fill backend-specific defaults on args in place (endpoint, model, reasoning effort)."""
    if args.backend == "groq":
        args.endpoint = args.endpoint or os.getenv("GROQ_ENDPOINT", GroqClient.DEFAULT_ENDPOINT)
        args.model = args.model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        if args.reasoning_effort is None and "gpt-oss" in args.model:
            args.reasoning_effort = "low"
    elif args.backend == "openai":
        args.endpoint = args.endpoint or os.getenv("OPENAI_ENDPOINT", OpenAIClient.DEFAULT_ENDPOINT)
        args.model = args.model or os.getenv("OPENAI_MODEL")
        if not args.model:
            raise ModelConfigError("the openai backend has no default model: pass --model or set OPENAI_MODEL "
                                   "(a model name is not guessed, because the right one depends on your account)")
    else:
        args.endpoint = args.endpoint or os.getenv("EDAPTIVE_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
        args.model = args.model or os.getenv("EDAPTIVE_MODEL", DEFAULT_OLLAMA_MODEL)


def make_client(args: argparse.Namespace, ollama_factory=OllamaClient) -> ModelClient:
    """Build the chosen client. Raises ModelConfigError (e.g. no GROQ_API_KEY); never falls back to another backend."""
    resolve(args)
    if args.backend == "groq":
        return GroqClient(args.model, args.endpoint, reasoning_effort=args.reasoning_effort)
    if args.backend == "openai":
        return OpenAIClient(args.model, args.endpoint, reasoning_effort=args.reasoning_effort)
    return ollama_factory(args.endpoint, args.model)


def with_fallback(client: ModelClient, args: argparse.Namespace, ollama_factory=OllamaClient) -> ModelClient:
    """Wrap a Groq client so a daily-quota 429 moves the rest of the run to local Ollama. Other backends pass through."""
    if args.backend != "groq" or getattr(args, "no_fallback", False):
        return client
    endpoint = args.fallback_endpoint or os.getenv("EDAPTIVE_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    model = args.fallback_model or os.getenv("EDAPTIVE_MODEL", DEFAULT_OLLAMA_MODEL)
    args.fallback_endpoint, args.fallback_model = endpoint, model
    return FallbackClient(client, lambda: ollama_factory(endpoint, model), fallback_name=f"local {model}")


def returned_backend_labels(result, default_backend: str) -> list[str]:
    """Provider bodies are not model responses; rejected model text still has a backend."""
    return [attempt.served_by or default_backend for attempt in result.attempts if attempt.returned_model_text]


__all__ = ["PacedClient", "add_fallback_args", "with_fallback", "add_backend_args", "make_client", "resolve", "ModelConfigError", "DEFAULT_GROQ_MODEL", "DEFAULT_OLLAMA_MODEL"]

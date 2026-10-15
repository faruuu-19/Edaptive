"""Git handling for the batch runner: a dedicated branch, one commit per group of finished cards, a secret scan before every
commit, and a push that never forces and never touches main. It never creates a repository and never changes a remote.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

PROTECTED_BRANCHES = ("main", "master", "trunk", "develop", "production", "release")
_KEY_PATTERNS = (("a Groq-style API key (gsk_…)", re.compile(r"gsk_[A-Za-z0-9_\-]{12,}")),
                 ("an API key (sk-…)", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}")))
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.I)
MIN_SECRET_LENGTH = 8


class GitError(Exception):
    pass


class SecretFound(GitError):
    """A possible secret is in the staged content. The message names files, never the value."""


def _redact(text: str) -> str:
    return re.sub(r"://[^/@\s]+@", "://***@", text)


def collect_secrets(environ: Any, env_file: Path | str | None) -> list[str]:
    """Values worth scanning for: secret-looking environment variables, and every value in the environment file."""
    values: list[str] = []
    for name, value in dict(environ).items():
        if isinstance(value, str) and len(value.strip()) >= MIN_SECRET_LENGTH and _SECRET_NAME.search(name):
            values.append(value.strip())
    if env_file is not None:
        try:
            lines = Path(env_file).read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            value = line.split("=", 1)[1].strip().strip("'\"")
            if len(value) >= MIN_SECRET_LENGTH:
                values.append(value)
    return list(dict.fromkeys(values))


def _ranges(numbers: Sequence[int]) -> str:
    parts: list[str] = []
    ordered = sorted(set(numbers))
    start = previous = None
    for number in ordered + [None]:   # type: ignore[list-item]
        if start is None:
            start = previous = number
        elif number is not None and number == previous + 1:
            previous = number
        else:
            parts.append(f"L{start}" if start == previous else f"L{start}–L{previous}")
            start = previous = number
    return ", ".join(parts)


def commit_message(items: Iterable[tuple[str, int | None]]) -> str:
    """'Add 10 assessment cards: math_g4_m1 (L11–L20)'. ``items`` are (module key, lesson number) in the order built."""
    items = list(items)
    modules: dict[str, list[int]] = {}
    for key, lesson in items:
        modules.setdefault(key, [])
        if lesson is not None:
            modules[key].append(lesson)
    groups = [f"{key} ({_ranges(lessons)})" if lessons else key for key, lessons in modules.items()]
    noun = "assessment card" if len(items) == 1 else "assessment cards"
    return f"Add {len(items)} {noun}: {', '.join(groups)}"


class Repo:
    def __init__(self, path: Path | str, runner: Any = subprocess.run):
        self.path = Path(path)
        self._run = runner

    def _git(self, *args: str, check: bool = True, timeout: float = 120.0) -> subprocess.CompletedProcess:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        try:
            done = self._run(["git", "-C", str(self.path), *args], capture_output=True, text=True, env=env, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitError(_redact(f"git {args[0]} could not run: {exc}")) from exc
        if check and done.returncode != 0:
            raise GitError(_redact(f"git {' '.join(args[:2])} failed: {(done.stderr or done.stdout).strip()[:400]}"))
        return done

    def is_repo(self) -> bool:
        try:
            done = self._git("rev-parse", "--is-inside-work-tree", check=False)
        except GitError:
            return False
        return done.returncode == 0 and done.stdout.strip() == "true"

    def require_repo(self) -> None:
        if not self.is_repo():
            raise GitError(f"{self.path} is not inside a git repository; the batch will not create one (run `git init` yourself, "
                           "or pick a folder that is already a repository)")

    def branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def remotes_text(self) -> str:
        return _redact(self._git("remote", "-v").stdout.strip())

    def remote_url(self, name: str) -> str | None:
        done = self._git("remote", "get-url", name, check=False)
        return done.stdout.strip() if done.returncode == 0 else None

    def switch_to_branch(self, name: str) -> None:
        if name in PROTECTED_BRANCHES:
            raise GitError(f"refusing to use protected branch {name!r}; pass a dedicated branch name")
        if self.branch() == name:
            return
        exists = self._git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False).returncode == 0
        self._git("switch", name) if exists else self._git("switch", "-c", name)

    def _staged(self) -> list[str]:
        return [line for line in self._git("diff", "--cached", "--name-only").stdout.splitlines() if line]

    def _unstage(self, paths: Sequence[Path | str]) -> None:
        self._git("reset", "-q", "--", *[str(p) for p in paths], check=False)

    def _scan(self, secrets: Sequence[str]) -> list[str]:
        findings: list[str] = []
        for name in self._staged():
            blob = self._git("show", f":{name}", check=False).stdout
            reasons = [label for label, pattern in _KEY_PATTERNS if pattern.search(blob)]
            if any(secret and secret in blob for secret in secrets):
                reasons.append("a value from the environment or .env file")
            if reasons:
                findings.append(f"{name}: {'; '.join(reasons)}")
        return findings

    def commit(self, paths: Sequence[Path | str], message: str, *, secrets: Sequence[str]) -> str:
        """Stage exactly ``paths``, scan what is staged, commit. Anything else already staged stops the commit; a possible
        secret unstages everything again and stops it. Returns the new commit's hash."""
        if self._staged():
            raise GitError("something is already staged in this repository; the batch will not commit other people's changes. "
                           "Commit or unstage it first")
        self._git("add", "--", *[str(p) for p in paths])
        findings = self._scan(secrets)
        if findings:
            self._unstage(paths)
            raise SecretFound("commit aborted: possible secret in staged content (" + " | ".join(findings) + "). Nothing was committed; "
                              "remove it, and rotate the key if it is real")
        try:
            self._git("commit", "-q", "-m", message)
        except GitError:
            self._unstage(paths)
            raise
        return self._git("rev-parse", "HEAD").stdout.strip()

    def push(self, remote: str, branch: str) -> None:
        if branch in PROTECTED_BRANCHES:
            raise GitError(f"refusing to push protected branch {branch!r}")
        self._git("push", "-u", remote, f"{branch}:{branch}", timeout=300.0)

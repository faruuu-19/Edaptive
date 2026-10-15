#!/usr/bin/env python3
"""Build assessment cards for the whole curriculum (or any slice of it) inside Groq's free-tier limits, resumably.

Typical use:
    python3 build_all_assessment_cards.py --dry-run                      # plan only: no model calls, no files, no commits
    python3 build_all_assessment_cards.py --limit 10                     # build 10 new cards, one commit
    caffeinate -i python3 build_all_assessment_cards.py                  # a long run; the Mac stays awake
It resumes where it stopped, never repeats a model call that succeeded, commits every 10 finished cards to its own branch, and
never pushes until you confirm the remote with --confirm-push. See CLAUDE.md, section 16.
"""
from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

import batch_runner as br
import batch_state as bs
from batch_runner import PreflightError, Settings


class StopSwitch:
    """Ctrl-C: the first press asks the run to stop cleanly; the second interrupts at once (finished cards are still committed)."""

    def __init__(self) -> None:
        self.requested = False
        self.presses = 0

    def __call__(self) -> bool:
        return self.requested

    def handle(self, signum, frame) -> None:       # noqa: ANN001
        self.presses += 1
        self.requested = True
        if self.presses >= 2:
            raise KeyboardInterrupt
        print("\nstop requested: finishing or discarding the current card, then committing what is complete "
              "(press Ctrl-C again to stop immediately)", file=sys.stderr)


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def _non_negative(text: str) -> float:
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", help="only this subject, for example math")
    parser.add_argument("--grade", type=int, help="only this grade")
    parser.add_argument("--module", type=int, help="only this module")
    parser.add_argument("--lesson", help="only these lessons: 28, 11-20 or 1-3,7")
    parser.add_argument("--limit", type=_positive_int, help="stop after this many newly built cards")
    parser.add_argument("--dry-run", action="store_true", help="list what would be built and estimate calls, tokens and days; no model calls, no files, no commits")
    parser.add_argument("--order", choices=("module", "cheapest"), default="module", help="module (default) or cheapest (fewest model calls first)")
    parser.add_argument("--commit-every", type=_positive_int, default=10, help="commit after this many finished cards (default 10)")
    parser.add_argument("--branch", default="assessment-cards", help="the branch to commit to (default assessment-cards; main is refused)")
    parser.add_argument("--no-push", action="store_true", help="commit locally and never push")
    parser.add_argument("--remote", default="origin", help="the remote to push to (default origin)")
    parser.add_argument("--confirm-push", action="store_true",
                        help="show git remote -v and the branch, then allow pushing to that remote and branch (until then nothing is pushed)")
    parser.add_argument("--min-gap", type=_non_negative, default=2.0, help="at least this many seconds between model requests (default 2)")
    parser.add_argument("--force", action="store_true", help="rebuild cards that are already finished")
    parser.add_argument("--retry-failed", action="store_true", help="try cards that failed earlier again (they are skipped by default)")
    parser.add_argument("--min-free-mb", type=_positive_int, default=200, help="stop when the disk has less free space than this (default 200)")
    parser.add_argument("--root", type=Path, default=br.PROJECT_ROOT, help="project folder holding the concept cards (default: this folder)")
    parser.add_argument("--output-dir", type=Path, default=None, help="where assessment cards are written (default <root>/assessment_cards)")
    parser.add_argument("--state-dir", type=Path, default=None, help="local state, lock and logs (default <root>/.assessment_batch, git-ignored)")
    return parser


def settings_from(args: argparse.Namespace) -> Settings:
    root = args.root.resolve()
    return Settings(root=root, out_root=(args.output_dir or root / br.OUTPUT_DIR_NAME).resolve(),
                    state_dir=(args.state_dir or root / br.STATE_DIR_NAME).resolve(), subject=args.subject, grade=args.grade,
                    module=args.module, lesson=args.lesson, limit=args.limit, dry_run=args.dry_run, order=args.order,
                    commit_every=args.commit_every, branch=args.branch, push=not args.no_push, remote=args.remote,
                    confirm_push=args.confirm_push, min_gap=args.min_gap, force=args.force, retry_failed=args.retry_failed,
                    min_free_mb=args.min_free_mb)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from(args)
    switch = StopSwitch()
    previous = signal.signal(signal.SIGINT, switch.handle) if not settings.dry_run else None
    try:
        report = br.BatchRunner(settings, stop_flag=switch).run()
    except (PreflightError, bs.LockHeld, bs.StateError) as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)
    if settings.dry_run:
        return 0
    return 3 if report.get("stop_reason") in ("commit_failed", "write_failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())

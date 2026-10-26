#!/usr/bin/env python3
"""One-shot repository health check.

Runs every static-analysis and test gate in the repo and prints a single colored
summary. Cross-platform: pure Python stdlib, no shell dependency, works on
Windows (cmd/PowerShell), macOS, and Linux.

Usage
-----
    python check_all.py              # full gate (lint + build + tests)
    python check_all.py --fast       # skip test suites (lint + build only)
    python check_all.py --only frontend,backend
    python check_all.py --list       # show the available check names

Checks
------
    frontend-lint    frontend: `npm run lint`
    frontend-build   frontend: `npm run build`
    frontend-tests   frontend: `npm run test:unit`
    backend-lint     `uv tool run ruff check backend/app/`
    backend-tests    backend: pytest
    agent-lint       `uv tool run ruff check agent_service_v2/src/agent_service_v2/`
    agent-tests      agent service: pytest

Ruff is pinned by `RUFF_VERSION` and provisioned via `uv tool run`, so the gate
works on a fresh checkout that has never installed ruff.

Exit code is 0 only when every selected check passes.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
AGENT = ROOT / "agent_service_v2"

# Keep in sync with ruff.toml's `exclude` list.
BACKEND_LINT_PATH = "backend/app/"
AGENT_LINT_PATH = "agent_service_v2/src/agent_service_v2/"

# Ruff is pinned here and provisioned on demand via `uv tool run`, so the gate is
# reproducible on a fresh checkout. The repo root deliberately has no
# `pyproject.toml`, which means `uv run ruff` would NOT resolve a project
# environment and instead look for `ruff` on the *caller's* PATH — a machine that
# has never installed ruff would fail the gate with "Failed to spawn: `ruff`".
# Keep this in sync with the `ruff.toml` this version was validated against.
RUFF_VERSION = "0.13.0"

# These backend modules hard-require an isolated MySQL instance
# (tests/test_class_insights_query.py style guard). They are skipped so the
# default gate works on a fresh checkout without a database.
BACKEND_TEST_IGNORES = (
    "tests/test_class_insights_query.py",
    "tests/test_teacher_class_insights.py",
    "tests/test_teacher_student_learning.py",
    "tests/test_teaching_service.py",
)

# Suites that additionally need a live MySQL schema or a POSIX `bash` on PATH.
# They are part of the default run (so regressions surface), but a failure here
# on a bare Windows checkout means "missing prerequisite", not "code broken".
BACKEND_TEST_ENV_REQUIREMENTS = {
    "tests/test_kg_resource_alignment_probe.py": "MySQL schema (duagent_test)",
    "tests/test_resource_detail.py": "MySQL schema (duagent_test)",
    "tests/test_deploy_prod.py": "POSIX bash on PATH (Git Bash / WSL)",
}


# --------------------------------------------------------------------------- #
# Terminal color helpers
# --------------------------------------------------------------------------- #

class C:
    """ANSI colors, disabled automatically when the stream is not a TTY."""

    _enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

    @classmethod
    def wrap(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls._enabled else text

    @classmethod
    def green(cls, t: str) -> str:
        return cls.wrap("32", t)

    @classmethod
    def red(cls, t: str) -> str:
        return cls.wrap("31", t)

    @classmethod
    def yellow(cls, t: str) -> str:
        return cls.wrap("33", t)

    @classmethod
    def cyan(cls, t: str) -> str:
        return cls.wrap("36", t)

    @classmethod
    def bold(cls, t: str) -> str:
        return cls.wrap("1", t)

    @classmethod
    def dim(cls, t: str) -> str:
        return cls.wrap("2", t)


# --------------------------------------------------------------------------- #
# Check definitions
# --------------------------------------------------------------------------- #

@dataclass
class Check:
    name: str
    description: str
    command: list[str]
    cwd: Path
    hint: str = ""
    kind: str = "lint"  # "lint" | "build" | "test"
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Result:
    check: Check
    ok: bool
    code: int
    seconds: float
    output: str

    @property
    def status(self) -> str:
        return C.green("PASS") if self.ok else C.red("FAIL")


def _npm() -> str:
    # npm is a .cmd shim on Windows and needs the shell/binary resolution that
    # shutil.which provides.
    return shutil.which("npm") or "npm"


def _uv() -> str:
    return shutil.which("uv") or "uv"


def _ruff() -> list[str]:
    """Command prefix that runs the pinned Ruff without relying on PATH.

    `uv tool run <spec>` installs the requested version into uv's tool cache on
    first use and then reuses it, so this works on a bare checkout while staying
    deterministic across machines.
    """
    return [_uv(), "tool", "run", f"ruff=={RUFF_VERSION}"]


def _python() -> str:
    """Prefer the backend virtualenv interpreter, falling back to this one.

    `backend/.venv` holds the pinned FastAPI/SQLAlchemy test dependencies; using
    it keeps `pytest` deterministic regardless of what the caller's PATH points
    at.
    """
    candidates = [
        BACKEND / ".venv" / "Scripts" / "python.exe",  # Windows
        BACKEND / ".venv" / "bin" / "python",          # POSIX
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def build_checks() -> list[Check]:
    return [
        Check(
            name="frontend-lint",
            description="frontend: npm run lint (ESLint 9 flat config)",
            command=[_npm(), "run", "lint"],
            cwd=FRONTEND,
            hint="cd frontend && npm install",
            kind="lint",
        ),
        Check(
            name="frontend-build",
            description="frontend: npm run build (Vite production build)",
            command=[_npm(), "run", "build"],
            cwd=FRONTEND,
            hint="cd frontend && npm install",
            kind="build",
        ),
        Check(
            name="frontend-tests",
            description="frontend: npm run test:unit (Vitest)",
            command=[_npm(), "run", "test:unit"],
            cwd=FRONTEND,
            hint="cd frontend && npm install",
            kind="test",
        ),
        Check(
            name="backend-lint",
            description="backend: ruff check",
            command=[*_ruff(), "check", BACKEND_LINT_PATH],
            cwd=ROOT,
            hint=f"uv tool install ruff=={RUFF_VERSION}  # usually not needed; uv fetches it on demand",
            kind="lint",
        ),
        Check(
            name="backend-tests",
            description="backend: pytest",
            command=[
                _python(), "-m", "pytest", "tests/", "-q",
                *[f"--ignore={path}" for path in BACKEND_TEST_IGNORES],
            ],
            cwd=BACKEND,
            hint=(
                "cd backend && python -m pip install -r requirements.txt; "
                "needs MySQL `duagent_test` schema and POSIX bash for a clean run"
            ),
            kind="test",
        ),
        Check(
            name="agent-lint",
            description="agent_service_v2: ruff check",
            command=[*_ruff(), "check", AGENT_LINT_PATH],
            cwd=ROOT,
            hint=f"uv tool install ruff=={RUFF_VERSION}  # usually not needed; uv fetches it on demand",
            kind="lint",
        ),
        Check(
            name="agent-tests",
            description="agent_service_v2: pytest",
            command=[
                _uv(), "run", "--project", "agent_service_v2",
                "pytest", "agent_service_v2/tests/", "-q",
            ],
            cwd=ROOT,
            hint="uv sync --project agent_service_v2",
            kind="test",
        ),
    ]


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def run_check(check: Check) -> Result:
    if not check.cwd.exists():
        return Result(check, False, 127, 0.0, f"missing directory: {check.cwd}")

    env = {**os.environ, **check.env}
    # Force UTF-8 child output so Chinese log lines don't blow up on Windows.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # Strip ANSI colors from child output; we colorize the summary ourselves so
    # redirected logs and CI artifacts stay readable.
    env["NO_COLOR"] = "1"

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            check.command,
            cwd=str(check.cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = proc.stdout or ""
        code = proc.returncode
    except FileNotFoundError:
        output = (
            f"command not found: {check.command[0]}\n"
            f"hint: {check.hint or 'install the missing toolchain'}"
        )
        code = 127
    except OSError as exc:  # pragma: no cover - platform specific
        output = f"failed to launch {check.command[0]}: {exc}"
        code = 126

    return Result(check, code == 0, code, time.perf_counter() - started, output)


def _tail(text: str, lines: int = 40) -> str:
    """Last N non-empty-trailing lines, indented for the failure report."""
    rows = text.rstrip().splitlines()
    if len(rows) > lines:
        rows = [C.dim(f"... ({len(rows) - lines} earlier lines omitted)")] + rows[-lines:]
    return "\n".join(f"    {row}" for row in rows)


ALIAS_GROUPS: dict[str, list[str]] = {
    "frontend": ["frontend-lint", "frontend-build", "frontend-tests"],
    "backend": ["backend-lint", "backend-tests"],
    "agent": ["agent-lint", "agent-tests"],
}


def _expand_aliases(names: set[str], valid_check_names: set[str]) -> tuple[set[str], set[str]]:
    expanded = set()
    unknown = set()
    for name in names:
        if name in ALIAS_GROUPS:
            expanded.update(ALIAS_GROUPS[name])
        elif name in valid_check_names:
            expanded.add(name)
        else:
            unknown.add(name)
    return expanded, unknown


def main(argv: list[str] | None = None) -> int:
    checks = build_checks()
    valid_names = {c.name for c in checks}
    parser = argparse.ArgumentParser(
        prog="check_all.py",
        description="Run every lint/build/test gate in the DUagent repo.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="comma-separated check names or group aliases (frontend, backend, agent) to run (default: all)",
    )
    parser.add_argument(
        "--skip",
        default="",
        help="comma-separated check names or group aliases to skip",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip test suites (lint + build only)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available check names and exit",
    )
    args = parser.parse_args(argv)

    if args.list:
        print(C.bold("Available checks:"))
        width = max(len(c.name) for c in checks)
        for check in checks:
            print(f"  {C.cyan(check.name.ljust(width))}  {check.description}")
        print(f"\n{C.bold('Group aliases:')}")
        for alias, group in ALIAS_GROUPS.items():
            print(f"  {C.cyan(alias.ljust(width))}  {', '.join(group)}")
        return 0

    selected = checks
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        expanded, unknown = _expand_aliases(wanted, valid_names)
        if unknown:
            print(C.red(f"unknown check(s): {', '.join(sorted(unknown))}"))
            print(C.dim("run `python check_all.py --list` to see valid names"))
            return 2
        selected = [c for c in checks if c.name in expanded]
    if args.skip:
        skipped = {name.strip() for name in args.skip.split(",") if name.strip()}
        expanded_skip, _ = _expand_aliases(skipped, valid_names)
        selected = [c for c in selected if c.name not in expanded_skip]
    if args.fast:
        selected = [c for c in selected if c.kind != "test"]

    if not selected:
        print(C.yellow("no checks selected"))
        return 0

    print(C.bold("DUagent repository check"))
    print(C.dim(f"root: {ROOT}"))
    print(C.dim(f"running {len(selected)} check(s)\n"))

    results: list[Result] = []
    for index, check in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {check.description} ... ", end="", flush=True)
        result = run_check(check)
        results.append(result)
        print(f"{result.status} {C.dim(f'({result.seconds:.1f}s)')}")

    failures = [r for r in results if not r.ok]

    print()
    print(C.bold("summary"))
    width = max(len(r.check.name) for r in results)
    for result in results:
        print(
            f"  {result.status}  {result.check.name.ljust(width)}  "
            f"{C.dim(f'{result.seconds:5.1f}s')}"
        )

    if failures:
        print()
        print(C.red(C.bold(f"{len(failures)} check(s) failed")))
        for result in failures:
            print()
            print(C.red(f"--- {result.check.name} (exit {result.code}) ---"))
            if result.check.hint:
                print(C.dim(f"    hint: {result.check.hint}"))
            if result.check.name == "backend-tests":
                for path, requirement in BACKEND_TEST_ENV_REQUIREMENTS.items():
                    if path in result.output:
                        print(
                            C.yellow(
                                f"    note: {path} also needs {requirement}"
                            )
                        )
            print(_tail(result.output))
        return 1

    total = sum(r.seconds for r in results)
    print()
    print(C.green(C.bold(f"all {len(results)} check(s) passed")) + C.dim(f" in {total:.1f}s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

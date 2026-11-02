# Copyright 2025 OmniSecure Inc.
# Modified by the Lamia project from Strix.

"""Run directory path helpers.

New runs are written to ``lamia_runs``. An existing tree that only has
``strix_runs`` keeps receiving new runs there so history stays in one
directory. Resume, latest-run, and ``lamia view`` search both directories.
"""

from __future__ import annotations

from pathlib import Path


RUNS_DIR_NAME = "lamia_runs"
LEGACY_RUNS_DIR_NAME = "strix_runs"
RUNS_SEARCH_LABEL = f"{RUNS_DIR_NAME} or {LEGACY_RUNS_DIR_NAME}"
RUNS_SEARCH_PHRASE = f"./{RUNS_DIR_NAME} or ./{LEGACY_RUNS_DIR_NAME}"
RUNTIME_STATE_DIR_NAME = ".state"
RUN_RECORD_FILENAME = "run.json"


def runtime_state_dir(run_dir: Path) -> Path:
    return run_dir / RUNTIME_STATE_DIR_NAME


def run_record_path(run_dir: Path) -> Path:
    return run_dir / RUN_RECORD_FILENAME


def runs_base_dir(*, cwd: Path | None = None) -> Path:
    """Directory new runs are written into.

    ``lamia_runs`` when it exists or when neither directory exists.
    ``strix_runs`` only when it is the sole existing runs directory.
    """
    base = cwd or Path.cwd()
    lamia = base / RUNS_DIR_NAME
    legacy = base / LEGACY_RUNS_DIR_NAME
    if lamia.is_dir():
        return lamia
    if legacy.is_dir():
        return legacy
    return lamia


def run_search_dirs(*, cwd: Path | None = None) -> list[Path]:
    """Existing runs directories, canonical name first."""
    base = cwd or Path.cwd()
    return [
        path
        for name in (RUNS_DIR_NAME, LEGACY_RUNS_DIR_NAME)
        if (path := base / name).is_dir()
    ]


def _record_mtime(run_dir: Path) -> float | None:
    record = run_record_path(run_dir)
    try:
        if not record.is_file():
            return None
        return record.stat().st_mtime
    except OSError:
        return None


def iter_run_dirs(*, cwd: Path | None = None) -> list[Path]:
    """Run directories that have a ``run.json``, newest activity first.

    The same run name in both trees keeps the copy with the newer record.
    """
    found: dict[str, tuple[float, Path]] = {}
    for base in run_search_dirs(cwd=cwd):
        try:
            children = list(base.iterdir())
        except OSError:
            continue
        for child in children:
            modified = _record_mtime(child)
            if modified is None:
                continue
            current = found.get(child.name)
            if current is None or modified >= current[0]:
                found[child.name] = (modified, child)
    ordered = sorted(found.values(), key=lambda item: (item[0], item[1].name), reverse=True)
    return [path for _, path in ordered]


def find_run_dir(run_name: str, *, cwd: Path | None = None) -> Path | None:
    """Locate an existing run by name in either runs directory."""
    base = cwd or Path.cwd()
    best: tuple[float, Path] | None = None
    for dirname in (RUNS_DIR_NAME, LEGACY_RUNS_DIR_NAME):
        candidate = base / dirname / run_name
        modified = _record_mtime(candidate)
        if modified is None:
            continue
        if best is None or modified >= best[0]:
            best = (modified, candidate)
    return None if best is None else best[1]


def run_dir_for(run_name: str, *, cwd: Path | None = None) -> Path:
    """Path for ``run_name``.

    An existing run is returned from whichever directory holds it. A new run
    is placed in the write directory from :func:`runs_base_dir`.
    """
    existing = find_run_dir(run_name, cwd=cwd)
    if existing is not None:
        return existing
    return runs_base_dir(cwd=cwd) / run_name


def latest_run_dir(*, cwd: Path | None = None) -> Path | None:
    runs = iter_run_dirs(cwd=cwd)
    return runs[0] if runs else None

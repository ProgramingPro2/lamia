"""`lamia export [RUN]` command: write a run report to a file or stdout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markup import escape

from lamia.core.paths import (
    RUNS_SEARCH_PHRASE,
    iter_run_dirs,
    latest_run_dir,
    run_dir_for,
    run_record_path,
)
from lamia.interface.viewer.report_pdf import generate_report_pdf


if TYPE_CHECKING:
    from typing import NoReturn


# Copied artifacts. PDF is rendered, not copied.
_ARTIFACTS = {
    "sarif": "findings.sarif",
    "json": "vulnerabilities.json",
    "csv": "vulnerabilities.csv",
    "markdown": "penetration_test_report.md",
}

_EXTENSIONS = {
    "pdf": "pdf",
    "sarif": "sarif",
    "json": "json",
    "csv": "csv",
    "markdown": "md",
}


def run_export(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="lamia export",
        description="Export a Lamia run report as PDF, SARIF, JSON, CSV, or Markdown.",
    )
    parser.add_argument(
        "run",
        nargs="?",
        default=None,
        help=f"Run name under {RUNS_SEARCH_PHRASE} (defaults to the most recent run).",
    )
    parser.add_argument(
        "--format",
        choices=tuple(_EXTENSIONS),
        default="pdf",
        metavar="{pdf,sarif,json,csv,markdown}",
        help="Report format (default: pdf).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help=(
            "File to write. Defaults to lamia-report-<run>.<ext> in the current "
            "directory. Use - to print text formats to stdout (not valid for pdf)."
        ),
    )
    args = parser.parse_args(argv)

    console = Console(stderr=True)
    run_dir = _resolve_run_dir(args.run, console)
    report_format = str(args.format)

    if args.output == "-" and report_format == "pdf":
        console.print("[bold red]Cannot write a PDF to stdout. Pass --output with a file path.[/]")
        raise SystemExit(2)

    payload = _report_bytes(run_dir, report_format, console)
    if args.output == "-":
        _write_stdout(payload)
        return

    destination = _destination(args.output, run_dir.name, report_format)
    _write_file(destination, payload, console)
    console.print(f"Wrote {destination}", markup=False, highlight=False)


def _report_bytes(run_dir: Path, report_format: str, console: Console) -> bytes:
    if report_format == "pdf":
        # Plain PDF from the renderer. Do not encrypt it.
        return generate_report_pdf(run_dir)

    filename = _ARTIFACTS[report_format]
    source = run_dir / filename
    if not source.is_file():
        console.print(
            f"[bold red]No {escape(filename)} in run '{escape(run_dir.name)}'.[/]\n"
            f"Expected [cyan]{escape(str(source))}[/]"
        )
        raise SystemExit(1)
    try:
        return source.read_bytes()
    except OSError as exc:
        console.print(f"[bold red]Could not read {escape(str(source))}: {escape(str(exc))}[/]")
        raise SystemExit(1) from exc


def _destination(output: str | None, run_name: str, report_format: str) -> Path:
    if output:
        return Path(output)
    extension = _EXTENSIONS[report_format]
    return Path.cwd() / f"lamia-report-{run_name}.{extension}"


def _write_stdout(payload: bytes) -> None:
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(payload.decode("utf-8"))
        sys.stdout.flush()
        return
    buffer.write(payload)
    buffer.flush()


def _write_file(path: Path, payload: bytes, console: Console) -> None:
    try:
        path.write_bytes(payload)
    except OSError as exc:
        console.print(f"[bold red]Could not write {escape(str(path))}: {escape(str(exc))}[/]")
        raise SystemExit(1) from exc


def _resolve_run_dir(run: str | None, console: Console) -> Path:
    if run:
        run_dir = run_dir_for(run)
        if not run_record_path(run_dir).is_file():
            _fail_no_run(console, requested=run)
        return run_dir

    latest = latest_run_dir()
    if latest is None:
        _fail_no_run(console, requested=None)
    return latest


def _fail_no_run(console: Console, *, requested: str | None) -> NoReturn:
    available = [child.name for child in iter_run_dirs()]

    if requested:
        console.print(f"[bold red]No run named '{requested}' under {RUNS_SEARCH_PHRASE}.[/]")
    else:
        console.print(f"[bold red]No runs found under {RUNS_SEARCH_PHRASE}.[/]")

    if available:
        console.print("Available runs:")
        for name in available[:20]:
            console.print(f"  [cyan]{name}[/]")
    raise SystemExit(1)


__all__ = ["run_export"]

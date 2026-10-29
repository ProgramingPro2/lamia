"""Tests for `lamia export`: local PDF rendering and artifact copies."""

from __future__ import annotations

import json
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from lamia.interface.export_cli import run_export


if TYPE_CHECKING:
    from pathlib import Path


def _make_run(base: Path, name: str = "sample") -> Path:
    run_dir = base / "lamia_runs" / name
    run_dir.mkdir(parents=True)
    record = {
        "run_name": name,
        "status": "completed",
        "end_time": "2026-01-01T00:00:00Z",
        "targets_info": [{"original": "https://example.com"}],
    }
    (run_dir / "run.json").write_text(json.dumps(record), encoding="utf-8")
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [],
    }
    (run_dir / "findings.sarif").write_text(json.dumps(sarif), encoding="utf-8")
    return run_dir


def test_export_pdf_and_sarif_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = _make_run(tmp_path, "alpha")
    pdf_path = tmp_path / "alpha.pdf"

    run_export(["alpha", "--format", "pdf", "--output", str(pdf_path)])

    pdf = pdf_path.read_bytes()
    assert pdf.startswith(b"%PDF")
    assert PdfReader(BytesIO(pdf)).is_encrypted is False

    run_export(["alpha", "--format", "sarif"])

    copied = tmp_path / "lamia-report-alpha.sarif"
    assert copied.read_bytes() == (run_dir / "findings.sarif").read_bytes()


def test_export_missing_artifact_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _make_run(tmp_path, "alpha")

    with pytest.raises(SystemExit) as exc:
        run_export(["alpha", "--format", "csv"])

    assert exc.value.code == 1
    assert "vulnerabilities.csv" in capsys.readouterr().err


def test_export_pdf_stdout_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _make_run(tmp_path, "alpha")

    with pytest.raises(SystemExit) as exc:
        run_export(["alpha", "--output", "-"])

    assert exc.value.code == 2
    assert "Cannot write a PDF to stdout" in capsys.readouterr().err

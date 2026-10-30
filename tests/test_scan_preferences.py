"""Saved TUI scan preferences apply only when the flag was not passed."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from lamia.interface.cli_args import parse_arguments


if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write_config(path: Path, scan_mode: str) -> None:
    path.write_text(
        json.dumps({"env": {}, "scan": {"scan_mode": scan_mode}}),
        encoding="utf-8",
    )


def test_saved_quick_applies_to_a_bare_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "cli-config.json"
    _write_config(config, "quick")
    monkeypatch.setattr(sys, "argv", ["lamia", "--config", str(config)])

    args = parse_arguments()

    assert args.needs_setup is True
    assert args.scan_mode == "quick"


def test_explicit_scan_mode_wins_over_the_saved_preference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "cli-config.json"
    _write_config(config, "quick")
    monkeypatch.setattr(
        sys,
        "argv",
        ["lamia", "--config", str(config), "--scan-mode", "deep"],
    )

    args = parse_arguments()

    assert args.scan_mode == "deep"

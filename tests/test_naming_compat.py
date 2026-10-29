"""Config home, run directory, and LAMIA_*/STRIX_* environment resolution."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from lamia.config import loader
from lamia.config.env import first_set
from lamia.config.home import (
    CLI_CONFIG_FILENAME,
    config_home,
    config_write_path,
    resolve_config_file,
)
from lamia.config.settings import LlmSettings, RuntimeSettings
from lamia.core.paths import find_run_dir, latest_run_dir, run_dir_for, runs_base_dir


if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _touch_run(root: Path, name: str, mtime: int) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    record = run_dir / "run.json"
    record.write_text(json.dumps({"run_name": name}), encoding="utf-8")
    os.utime(record, (mtime, mtime))
    return run_dir


def test_config_home_uses_lamia_when_present(tmp_path: Path) -> None:
    (tmp_path / ".lamia").mkdir()
    assert config_home(root=tmp_path) == tmp_path / ".lamia"


def test_config_home_reuses_strix_when_lamia_is_absent(tmp_path: Path) -> None:
    (tmp_path / ".strix").mkdir()
    assert config_home(root=tmp_path) == tmp_path / ".strix"
    assert not (tmp_path / ".lamia").exists()


def test_config_home_defaults_to_lamia(tmp_path: Path) -> None:
    assert config_home(root=tmp_path) == tmp_path / ".lamia"
    assert not (tmp_path / ".lamia").exists()


def test_both_config_homes_read_missing_file_from_strix(tmp_path: Path) -> None:
    legacy = tmp_path / ".strix"
    lamia = tmp_path / ".lamia"
    legacy.mkdir()
    lamia.mkdir()
    (legacy / CLI_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    assert resolve_config_file(CLI_CONFIG_FILENAME, root=tmp_path) == legacy / CLI_CONFIG_FILENAME
    assert config_write_path(CLI_CONFIG_FILENAME, root=tmp_path) == lamia / CLI_CONFIG_FILENAME


def test_lamia_config_file_wins_when_both_homes_have_it(tmp_path: Path) -> None:
    legacy = tmp_path / ".strix"
    lamia = tmp_path / ".lamia"
    legacy.mkdir()
    lamia.mkdir()
    (legacy / CLI_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    (lamia / CLI_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    assert resolve_config_file(CLI_CONFIG_FILENAME, root=tmp_path) == lamia / CLI_CONFIG_FILENAME


def test_new_runs_use_lamia_runs_unless_only_strix_runs_exists(tmp_path: Path) -> None:
    assert runs_base_dir(cwd=tmp_path) == tmp_path / "lamia_runs"
    (tmp_path / "strix_runs").mkdir()
    assert runs_base_dir(cwd=tmp_path) == tmp_path / "strix_runs"
    (tmp_path / "lamia_runs").mkdir()
    assert runs_base_dir(cwd=tmp_path) == tmp_path / "lamia_runs"


def test_resume_and_latest_search_both_run_directories(tmp_path: Path) -> None:
    older = _touch_run(tmp_path / "strix_runs", "old", 1_000_000_000)
    newer = _touch_run(tmp_path / "lamia_runs", "new", 2_000_000_000)
    assert find_run_dir("old", cwd=tmp_path) == older
    assert run_dir_for("old", cwd=tmp_path) == older
    assert run_dir_for("fresh", cwd=tmp_path) == tmp_path / "lamia_runs" / "fresh"
    assert latest_run_dir(cwd=tmp_path) == newer


def test_lamia_env_wins_over_strix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAMIA_LLM", "lamia-model")
    monkeypatch.setenv("STRIX_LLM", "strix-model")
    monkeypatch.setenv("LAMIA_IMAGE", "example/lamia:1")
    monkeypatch.setenv("STRIX_IMAGE", "example/strix:1")
    assert LlmSettings().model == "lamia-model"
    assert RuntimeSettings().image == "example/lamia:1"
    assert first_set("LAMIA_DEBUG", "STRIX_DEBUG") is None


def test_strix_env_still_populates_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAMIA_LLM", raising=False)
    monkeypatch.delenv("LAMIA_IMAGE", raising=False)
    monkeypatch.delenv("STRIX_IMAGE", raising=False)
    monkeypatch.setenv("STRIX_LLM", "strix-model")
    assert LlmSettings().model == "strix-model"
    assert RuntimeSettings().image == "ghcr.io/usestrix/strix-sandbox:1.3.0"


def test_loader_reads_legacy_config_and_writes_lamia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = tmp_path / ".strix"
    legacy.mkdir()
    (legacy / CLI_CONFIG_FILENAME).write_text(
        json.dumps({"env": {"STRIX_LLM": "from-legacy"}}),
        encoding="utf-8",
    )
    (tmp_path / ".lamia").mkdir()
    monkeypatch.setattr(loader, "_cached", None)
    monkeypatch.setattr(loader, "_override", None)
    monkeypatch.setattr(loader, "resolve_config_file", lambda _name: legacy / CLI_CONFIG_FILENAME)
    monkeypatch.setattr(loader, "config_write_path", lambda _name: tmp_path / ".lamia" / _name)
    monkeypatch.delenv("LAMIA_LLM", raising=False)
    monkeypatch.delenv("STRIX_LLM", raising=False)

    assert loader.load_settings().llm.model == "from-legacy"

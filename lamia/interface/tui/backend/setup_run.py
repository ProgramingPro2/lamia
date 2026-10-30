"""Setup commands for files and the other scan options the CLI already accepts.

The TUI sends paths only. This module reads them with the same helpers the
argument parser uses, so a long instructions file never rides a command frame.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lamia.config.loader import apply_config_override, load_scan_preferences
from lamia.config.settings import DEFAULT_MAX_TURNS
from lamia.interface.tui.backend.projection import SCAN_MODES, SCOPE_MODES
from lamia.interface.utils import read_target_list_file, resolve_workspace_files
from lamia.report.runs import list_run_summaries
from lamia.tools.mcp.loader import load_user_mcp_configs


if TYPE_CHECKING:
    from lamia.interface.tui.backend.controller import TuiController


RUN_COMMANDS = frozenset(
    {
        "setup.set_instruction_file",
        "setup.add_target_list",
        "setup.remove_target_list",
        "setup.add_workspace_file",
        "setup.remove_workspace_file",
        "setup.set_config",
        "setup.set_mcp_config",
        "setup.list_mcp",
        "setup.set_mcp_servers",
        "setup.set_mcp_exclude",
        "setup.list_runs",
        "setup.resume",
    }
)

_MCP_SELECTION_ENV = (
    "LAMIA_MCP_ONLY",
    "LAMIA_MCP_EXCLUDE",
    "STRIX_MCP_ONLY",
    "STRIX_MCP_EXCLUDE",
)


async def dispatch_run(
    controller: TuiController,
    command: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    handler = _HANDLERS.get(command)
    if handler is None:
        return None
    return await handler(controller, payload)


async def _set_instruction_file(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    raw = payload.get("path", "")
    if raw is None:
        raw = ""
    if not isinstance(raw, str):
        raise TypeError("path must be a string")
    if not raw.strip():
        controller.instruction_file = ""
        controller.file_instruction = ""
        controller.compose_instruction()
        return {"instruction_file": "", "instruction": controller.instruction}
    path = _existing_file(raw)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Instruction file '{path}' must be valid UTF-8 text: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read instruction file '{path}': {exc}") from exc
    if not text:
        raise ValueError(f"Instruction file '{path}' is empty")
    controller.instruction_file = str(path)
    controller.file_instruction = text
    controller.compose_instruction()
    return {"instruction_file": controller.instruction_file, "instruction": controller.instruction}


async def _add_target_list(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    path = str(_existing_file(_required_string(payload, "path")))
    targets = read_target_list_file(path)
    introduced: list[str] = []
    for target in targets:
        if target not in controller.targets:
            controller.targets.append(target)
            introduced.append(target)
    if path not in controller.target_lists:
        controller.target_lists.append(path)
    controller.target_list_members[path] = introduced
    return {"path": path, "added": len(introduced), "total": len(controller.targets)}


async def _remove_target_list(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    path = _required_string(payload, "path")
    controller.target_lists = [item for item in controller.target_lists if item != path]
    introduced = controller.target_list_members.pop(path, [])
    still = {target for group in controller.target_list_members.values() for target in group}
    for target in introduced:
        if target not in still and target in controller.targets:
            controller.targets.remove(target)
    return {"path": path, "total": len(controller.targets)}


async def _add_workspace_file(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    path = str(_existing_file(_required_string(payload, "path")))
    dest = payload.get("dest", "")
    if dest is None:
        dest = ""
    if not isinstance(dest, str):
        raise TypeError("dest must be a string")
    spec = f"{path}:{dest.strip()}" if dest.strip() else path
    specs = [*controller.workspace_specs, spec]
    controller.workspace_files = resolve_workspace_files(specs)
    controller.workspace_specs = specs
    return {"path": path, "total": len(controller.workspace_specs)}


async def _remove_workspace_file(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    path = _required_string(payload, "path")
    specs = [
        spec
        for spec in controller.workspace_specs
        if spec != path and not spec.startswith(f"{path}:")
    ]
    controller.workspace_files = resolve_workspace_files(specs)
    controller.workspace_specs = specs
    return {"path": path, "total": len(controller.workspace_specs)}


async def _set_config(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    path = _config_file(_required_string(payload, "path"))
    apply_config_override(path)
    _apply_scan_preferences(controller)
    controller.config_path = str(path)
    return {
        "config_path": controller.config_path,
        "scan_mode": controller.scan_mode,
        "max_budget_usd": controller.max_budget_usd,
        "max_turns": controller.max_turns,
        "scope_mode": controller.scope_mode,
        "diff_base": controller.diff_base,
    }


async def _set_mcp_config(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    raw = payload.get("path", "")
    if raw is None:
        raw = ""
    if not isinstance(raw, str):
        raise TypeError("path must be a string")
    if not raw.strip():
        controller.mcp_config = ""
        return {"mcp_config": ""}
    path = _existing_file(raw)
    if path.suffix != ".json":
        raise ValueError("MCP config must be a .json file")
    controller.mcp_config = str(path)
    return {"mcp_config": controller.mcp_config, "names": _mcp_names(controller)}


async def _list_mcp(
    controller: TuiController,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    return {"names": _mcp_names(controller)}


async def _set_mcp_servers(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    controller.mcp_servers = _selected_names(controller, payload)
    return {"mcp_servers": controller.mcp_servers}


async def _set_mcp_exclude(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    controller.mcp_excluded = _selected_names(controller, payload)
    return {"mcp_excluded": controller.mcp_excluded}


async def _list_runs(
    _controller: TuiController,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runs": [
            {
                "name": run.run_name,
                "status": run.status,
                "target": run.target,
                "resumable": run.resumable,
            }
            for run in list_run_summaries()
        ]
    }


async def _resume(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    if controller.targets:
        raise RuntimeError("Resume cannot be combined with targets added on this screen.")
    name = _required_string(payload, "run")
    controller.resume_run = name
    try:
        await controller._begin_scan()
    except Exception:
        controller.resume_run = ""
        raise
    return {"resumed": name}


def _apply_scan_preferences(controller: TuiController) -> None:
    """Replace the dialog's scan options with the config that was just selected."""
    prefs = load_scan_preferences()
    mode = prefs.get("scan_mode")
    controller.scan_mode = str(mode) if mode in SCAN_MODES else "deep"
    scope = prefs.get("scope_mode")
    controller.scope_mode = str(scope) if scope in SCOPE_MODES else "auto"
    turns = prefs.get("max_turns")
    if isinstance(turns, int) and not isinstance(turns, bool) and turns > 0:
        controller.max_turns = turns
    else:
        controller.max_turns = DEFAULT_MAX_TURNS
    if "max_budget_usd" in prefs:
        controller.max_budget_usd = _optional_budget(prefs.get("max_budget_usd"))
    else:
        controller.max_budget_usd = None
    base = prefs.get("diff_base")
    controller.diff_base = base.strip() if isinstance(base, str) and base.strip() else None


def _optional_budget(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    amount = float(value)
    if not math.isfinite(amount) or amount <= 0:
        return None
    return amount


def _mcp_names(controller: TuiController) -> list[str]:
    """Connection names before this run's include/exclude selection."""
    saved = {key: os.environ.pop(key) for key in _MCP_SELECTION_ENV if key in os.environ}
    try:
        path = Path(controller.mcp_config).expanduser() if controller.mcp_config else None
        configs = load_user_mcp_configs(path)
    finally:
        os.environ.update(saved)
    return [config.name for config in configs]


def _selected_names(controller: TuiController, payload: dict[str, Any]) -> list[str]:
    names = payload.get("names", [])
    if names is None:
        names = []
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise TypeError("names must be a list of strings")
    chosen = [name.strip() for name in names if name.strip()]
    available = set(_mcp_names(controller))
    if available:
        unknown = [name for name in chosen if name not in available]
        if unknown:
            raise ValueError(f"Unknown MCP connection: {unknown[0]}")
    return chosen


def _existing_file(raw: str) -> Path:
    path = Path(raw.strip()).expanduser()
    if not path.is_file():
        raise ValueError(f"'{raw}' is not an existing file")
    return path


def _config_file(raw: str) -> Path:
    path = _existing_file(raw)
    if path.suffix != ".json":
        raise ValueError("Config file must be a .json file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read config file '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise TypeError("Config file must contain a JSON object")
    if not isinstance(data.get("env"), dict):
        raise TypeError("Config file must have an 'env' object")
    return path


def _required_string(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


_HANDLERS = {
    "setup.set_instruction_file": _set_instruction_file,
    "setup.add_target_list": _add_target_list,
    "setup.remove_target_list": _remove_target_list,
    "setup.add_workspace_file": _add_workspace_file,
    "setup.remove_workspace_file": _remove_workspace_file,
    "setup.set_config": _set_config,
    "setup.set_mcp_config": _set_mcp_config,
    "setup.list_mcp": _list_mcp,
    "setup.set_mcp_servers": _set_mcp_servers,
    "setup.set_mcp_exclude": _set_mcp_exclude,
    "setup.list_runs": _list_runs,
    "setup.resume": _resume,
}

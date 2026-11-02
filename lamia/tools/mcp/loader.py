# Copyright 2025 OmniSecure Inc.
# Modified by the Lamia project from Strix.

"""Read the user's MCP servers from the Lamia config directory.

A user lists the MCP servers they want the agent to reach in a small JSON
file. Lamia reads it at the start of a run and connects to each server,
holding the live sessions in the run's registry for the agent to reach on
demand. The file is optional; without it the run simply gets no MCP
connections. The file lives at ``~/.lamia/mcp-servers.json``, or under
``~/.strix`` when that is the existing config home.

Parsing is fail-open. A single malformed entry is logged and skipped rather than
raising, so one bad row never blocks the servers that are valid, and a missing
or unreadable file yields an empty list.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from lamia.config.env import first_set
from lamia.config.home import MCP_CONFIG_FILENAME, resolve_config_file
from lamia.tools.mcp.config import McpConnectionConfig


logger = logging.getLogger(__name__)


_PATH_ENV_VARS = ("LAMIA_MCP_CONFIG", "STRIX_MCP_CONFIG")
# Per-run selection, set by the --mcp-server / --mcp-exclude CLI flags. Each is a
# comma-separated list of connection names.
_ONLY_ENV_VARS = ("LAMIA_MCP_ONLY", "STRIX_MCP_ONLY")
_EXCLUDE_ENV_VARS = ("LAMIA_MCP_EXCLUDE", "STRIX_MCP_EXCLUDE")


def _resolve_path(path: Path | None) -> Path:
    if path is not None:
        return path
    override = first_set(*_PATH_ENV_VARS)
    if override:
        return Path(override)
    return resolve_config_file(MCP_CONFIG_FILENAME)


def _dedupe_by_name(configs: list[McpConnectionConfig]) -> list[McpConnectionConfig]:
    """Keep the first connection of each name, dropping later duplicates.

    A connection's name is its key in the run's registry, so two connections
    sharing a name would collide and the second would overwrite the first. Drop
    the duplicate here, with a warning, instead.
    """
    seen: set[str] = set()
    unique: list[McpConnectionConfig] = []
    for config in configs:
        if config.name in seen:
            logger.warning(
                "Ignoring MCP server %r: another connection already uses that name "
                "(names must be unique because they namespace the server's tools).",
                config.name,
            )
            continue
        seen.add(config.name)
        unique.append(config)
    return unique


def _parse_names(env_vars: tuple[str, ...]) -> set[str]:
    raw = first_set(*env_vars) or ""
    return {name.strip() for name in raw.split(",") if name.strip()}


def _apply_run_selection(configs: list[McpConnectionConfig]) -> list[McpConnectionConfig]:
    """Restrict this run's connections to an optional include/exclude selection.

    ``LAMIA_MCP_ONLY`` (if set) keeps only the named connections; then
    ``LAMIA_MCP_EXCLUDE`` drops any named connection. The legacy ``STRIX_MCP_*``
    names are accepted when the Lamia name is unset. With neither set, every
    connection is kept.
    """
    only = _parse_names(_ONLY_ENV_VARS)
    exclude = _parse_names(_EXCLUDE_ENV_VARS)
    if not only and not exclude:
        return configs

    available = {config.name for config in configs}
    for name in sorted((only | exclude) - available):
        logger.warning(
            "MCP connection selection named %r, which is not configured; ignoring it", name
        )

    selected: list[McpConnectionConfig] = []
    for config in configs:
        if only and config.name not in only:
            continue
        if config.name in exclude:
            continue
        selected.append(config)
    return selected


def load_user_mcp_configs(path: Path | None = None) -> list[McpConnectionConfig]:
    """Load MCP connection configs from the user's JSON file.

    The path is ``path`` if given, else ``$LAMIA_MCP_CONFIG`` (or
    ``$STRIX_MCP_CONFIG``), else the config-home ``mcp-servers.json``. The file
    is a JSON list of server entries.
    A missing file returns ``[]``; an unreadable or non-list file is logged and
    returns ``[]``; individual entries that fail validation are logged and
    skipped. Connections sharing a name are de-duplicated (first wins), and an
    optional per-run include/exclude selection is applied last.
    """
    source = _resolve_path(path)
    if not source.exists():
        return []

    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read MCP config at %s; ignoring it", source)
        return []

    if not isinstance(raw, list):
        logger.warning("MCP config at %s is not a JSON list; ignoring it", source)
        return []

    entries = cast("list[object]", raw)
    configs: list[McpConnectionConfig] = []
    for index, entry in enumerate(entries):
        try:
            configs.append(McpConnectionConfig.model_validate(entry))
        except ValidationError as exc:
            logger.warning("Skipping invalid MCP server entry #%d in %s: %s", index, source, exc)

    return _apply_run_selection(_dedupe_by_name(configs))

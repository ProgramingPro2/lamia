"""Shared config directory for new Lamia installs and existing Strix installs.

New names are canonical. An old install keeps working because both directories
resolve to one store:

- If ``~/.lamia`` exists, use it.
- Otherwise if ``~/.strix`` exists, use that. Nothing is copied.
- Otherwise new files are created under ``~/.lamia``.
- If both exist, writes go to ``~/.lamia`` and a missing file is read from
  ``~/.strix``.
"""

from __future__ import annotations

from pathlib import Path


LAMIA_CONFIG_DIRNAME = ".lamia"
LEGACY_CONFIG_DIRNAME = ".strix"

CLI_CONFIG_FILENAME = "cli-config.json"
MCP_CONFIG_FILENAME = "mcp-servers.json"
SUBSCRIPTION_AUTH_FILENAME = "subscription-auth.json"
UPDATE_CHECK_FILENAME = "update-check.json"
CLI_IDENTITY_FILENAME = "cli-identity.json"


def lamia_config_dir(*, root: Path | None = None) -> Path:
    return (root or Path.home()) / LAMIA_CONFIG_DIRNAME


def legacy_config_dir(*, root: Path | None = None) -> Path:
    return (root or Path.home()) / LEGACY_CONFIG_DIRNAME


def config_home(*, root: Path | None = None) -> Path:
    """Directory new config files are written into.

    ``~/.lamia`` when it already exists or when neither directory exists.
    ``~/.strix`` only when it is the sole existing config home. The directory
    is not created here.
    """
    lamia = lamia_config_dir(root=root)
    legacy = legacy_config_dir(root=root)
    if lamia.is_dir():
        return lamia
    if legacy.is_dir():
        return legacy
    return lamia


def config_write_path(name: str, *, root: Path | None = None) -> Path:
    """Path to write ``name`` to. Does not create the parent directory."""
    return config_home(root=root) / name


def resolve_config_file(name: str, *, root: Path | None = None) -> Path:
    """Path to read ``name`` from.

    Prefer the write location. When both homes exist and the file is absent
    from ``~/.lamia``, return the ``~/.strix`` copy if it is present.
    """
    write_path = config_write_path(name, root=root)
    if write_path.exists():
        return write_path
    lamia = lamia_config_dir(root=root)
    legacy = legacy_config_dir(root=root)
    if lamia.is_dir() and legacy.is_dir():
        fallback = legacy / name
        if fallback.exists():
            return fallback
    return write_path

"""Settings loader, override switch, and disk persistence."""

from __future__ import annotations

import json
import logging
import os
from types import UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from pydantic import AliasChoices, BaseModel

from lamia.config.home import CLI_CONFIG_FILENAME, config_write_path, resolve_config_file
from lamia.config.model_catalog import REASONING_EFFORTS
from lamia.config.settings import LlmSettings, Settings
from lamia.utils.secret_files import write_secret_text


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from pydantic.fields import FieldInfo


logger = logging.getLogger(__name__)


_override: Path | None = None
_cached: Settings | None = None

# Model, API key, and API base describe one provider connection. When the shell
# changes any of them, the stored values of the others no longer belong together
# and are dropped rather than mixed with the new value.
_LINKED_LLM_FIELDS = ("model", "api_key", "api_base")


def load_settings() -> Settings:
    """Resolve settings from env + JSON file + defaults. Memoized.

    Precedence: env vars win, then the JSON file, then field defaults.
    """
    global _cached  # noqa: PLW0603
    if _cached is None:
        source_path = _config_read_path()
        init_kwargs: dict[str, Any] = _read_json_overrides(source_path)
        _cached = Settings(**init_kwargs)
        logger.debug(
            "load_settings: resolved (override=%s, file_used=%s, json_keys=%d)",
            _override is not None,
            source_path.exists(),
            sum(len(v) for v in init_kwargs.values()),
        )
    return _cached


def apply_config_override(path: Path) -> None:
    """Switch the JSON source to ``path`` and invalidate the cache."""
    global _override, _cached  # noqa: PLW0603
    _override = path
    _cached = None
    logger.info("config override applied: %s", path)


def persist_current() -> None:
    """Merge currently-set env vars into the active config file (0o600).

    Values already in the file survive when their env var is unset, so a
    run that gets its settings from the file does not erase them. An env
    var set to the empty string clears the field from the file. A change to
    any linked LLM connection var drops the whole stored connection first.
    """
    s = load_settings()
    source = _config_read_path()
    target = _config_write_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    env_block = _drop_stale_llm_connection(_read_env_block(source))
    for sub_name in type(s).model_fields:
        sub_model = getattr(s, sub_name)
        if not isinstance(sub_model, BaseModel):
            continue
        for finfo in type(sub_model).model_fields.values():
            aliases = [alias.upper() for alias in _aliases_for(finfo)]
            active = next((alias for alias in aliases if alias in os.environ), None)
            if active is None:
                continue
            for alias in aliases:
                env_block.pop(alias, None)
            if os.environ[active]:
                env_block[active] = os.environ[active]

    write_secret_text(target, json.dumps({"env": env_block}, indent=2))


def _config_read_path() -> Path:
    if _override is not None:
        return _override
    return resolve_config_file(CLI_CONFIG_FILENAME)


def _config_write_path() -> Path:
    if _override is not None:
        return _override
    return config_write_path(CLI_CONFIG_FILENAME)


def _aliases_for(finfo: FieldInfo) -> list[str]:
    """Collect every env-var name that should populate ``finfo``."""
    aliases: list[str] = []
    if finfo.alias:
        aliases.append(finfo.alias)
    va = finfo.validation_alias
    if isinstance(va, AliasChoices):
        aliases.extend(c for c in va.choices if isinstance(c, str))
    elif isinstance(va, str):
        aliases.append(va)
    return aliases


def _read_json_overrides(path: Path) -> dict[str, dict[str, Any]]:
    """Read ``{"env": {...}}`` from ``path`` and remap to nested kwargs.

    Only includes keys whose env var is NOT already set, so env always
    wins over the persisted file.
    """
    env_block_upper = _drop_stale_llm_connection(_read_env_block(path))
    if not env_block_upper:
        return {}
    env_present = {k.upper() for k in os.environ}

    nested: dict[str, dict[str, Any]] = {}
    for sub_name, sub_finfo in Settings.model_fields.items():
        sub_cls = sub_finfo.annotation
        if not (isinstance(sub_cls, type) and issubclass(sub_cls, BaseModel)):
            continue
        sub_data: dict[str, Any] = {}
        for fname, finfo in sub_cls.model_fields.items():
            aliases = [alias.upper() for alias in _aliases_for(finfo)]
            if any(alias in env_present for alias in aliases):
                continue  # env wins under some alias; skip the JSON file for this field
            for alias in aliases:
                if alias in env_block_upper:
                    sub_data[fname] = _decode_saved_value(finfo, env_block_upper[alias])
                    break
        if sub_data:
            nested[sub_name] = sub_data
    return nested


def _decode_saved_value(finfo: FieldInfo, value: Any) -> Any:
    """Decode a JSON string saved for a dict field, as pydantic does for env vars.

    ``persist_current`` saves env values verbatim, so a dict setting such as
    ``LLM_EXTRA_HEADERS`` lands in the file as JSON text. Values that are
    already objects, or aren't valid JSON, are left for validation to judge.
    """
    if not isinstance(value, str) or not _is_dict_field(finfo):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


def _is_dict_field(finfo: FieldInfo) -> bool:
    annotation = finfo.annotation
    candidates = (
        get_args(annotation) if get_origin(annotation) in (Union, UnionType) else (annotation,)
    )
    return any(c is dict or get_origin(c) is dict for c in candidates)


def _first_alias_value(aliases: list[str], source: Mapping[str, Any]) -> Any | None:
    return next((source[alias] for alias in aliases if alias in source), None)


def _drop_stale_llm_connection(env_block: dict[str, Any]) -> dict[str, Any]:
    """Remove every linked LLM var from ``env_block`` if the shell changed any of them."""
    linked_aliases = [
        [alias.upper() for alias in _aliases_for(LlmSettings.model_fields[name])]
        for name in _LINKED_LLM_FIELDS
    ]
    changed = any(
        (env_value := _first_alias_value(aliases, os.environ)) is not None
        and env_value != _first_alias_value(aliases, env_block)
        for aliases in linked_aliases
    )
    if not changed:
        return env_block
    stale = {alias for aliases in linked_aliases for alias in aliases}
    return {k: v for k, v in env_block.items() if k not in stale}


def _read_env_block(path: Path) -> dict[str, Any]:
    """Return the ``env`` block stored in ``path`` with upper-cased keys, or ``{}``."""
    env_block = _read_config_document(path).get("env", {})
    if not isinstance(env_block, dict):
        return {}
    return {str(k).upper(): v for k, v in env_block.items()}


_MODEL_ENV_KEYS = ("LAMIA_LLM", "STRIX_LLM")
_KEY_ENV_KEYS = ("LLM_API_KEY", "OPENAI_API_KEY")
_BASE_ENV_KEYS = (
    "LLM_API_BASE",
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    "LITELLM_BASE_URL",
    "OLLAMA_API_BASE",
)
_REASONING_ENV_KEYS = ("LAMIA_REASONING_EFFORT", "STRIX_REASONING_EFFORT")


def shell_locks_llm_connection() -> bool:
    """Whether the shell exported a model or key that will win on the next process."""
    return any(os.environ.get(name) for name in (*_MODEL_ENV_KEYS, *_KEY_ENV_KEYS))


def save_llm_connection(
    *,
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
    update_key: bool = False,
    update_base: bool = False,
) -> None:
    """Write the model, and optionally the key and base, without dropping the others.

    ``persist_current`` treats a model change as a new provider connection and
    deletes the stored key. Choosing another model for the same key must not
    do that, so this updates only the fields the caller names.
    """
    chosen = model.strip()
    if not chosen:
        raise ValueError("model must be a non-empty string")
    settings = load_settings()
    _stage_llm_connection(
        settings,
        chosen,
        api_key=api_key,
        api_base=api_base,
        update_key=update_key,
        update_base=update_base,
    )
    doc = _read_config_document(_config_read_path())
    env = doc.get("env")
    if not isinstance(env, dict):
        env = {}
    env = _without_env_keys(env, _MODEL_ENV_KEYS)
    env["LAMIA_LLM"] = chosen
    if update_key:
        env = _without_env_keys(env, _KEY_ENV_KEYS)
        if settings.llm.api_key:
            env["LLM_API_KEY"] = settings.llm.api_key
    if update_base:
        env = _without_env_keys(env, _BASE_ENV_KEYS)
        if settings.llm.api_base:
            env["LLM_API_BASE"] = settings.llm.api_base
    doc["env"] = env
    _write_config_document(doc)


def _stage_llm_connection(
    settings: Settings,
    model: str,
    *,
    api_key: str | None,
    api_base: str | None,
    update_key: bool,
    update_base: bool,
) -> None:
    settings.llm.model = model
    os.environ["LAMIA_LLM"] = model
    if update_key:
        _stage_api_key(settings, api_key)
    if update_base:
        _stage_api_base(settings, api_base)


def _stage_api_key(settings: Settings, api_key: str | None) -> None:
    cleaned = (api_key or "").strip()
    settings.llm.api_key = cleaned or None
    if cleaned:
        os.environ["LLM_API_KEY"] = cleaned
        return
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)


def _stage_api_base(settings: Settings, api_base: str | None) -> None:
    cleaned = (api_base or "").strip()
    settings.llm.api_base = cleaned or None
    if cleaned:
        os.environ["LLM_API_BASE"] = cleaned
        return
    for name in _BASE_ENV_KEYS:
        os.environ.pop(name, None)


def save_reasoning_effort(effort: str) -> None:
    """Store reasoning effort on the cached settings and in the config file."""
    chosen = effort.strip().lower()
    if chosen not in REASONING_EFFORTS:
        choices = ", ".join(REASONING_EFFORTS)
        raise ValueError(f"reasoning_effort must be one of: {choices}")
    settings = load_settings()
    settings.llm.reasoning_effort = chosen  # type: ignore[assignment]
    os.environ["LAMIA_REASONING_EFFORT"] = chosen
    doc = _read_config_document(_config_read_path())
    env = doc.get("env")
    if not isinstance(env, dict):
        env = {}
    env = _without_env_keys(env, _REASONING_ENV_KEYS)
    env["LAMIA_REASONING_EFFORT"] = chosen
    doc["env"] = env
    _write_config_document(doc)


def load_scan_preferences() -> dict[str, Any]:
    """The ``scan`` object from the active config file, or ``{}``."""
    scan = _read_config_document(_config_read_path()).get("scan")
    return dict(scan) if isinstance(scan, dict) else {}


def save_scan_preferences(prefs: dict[str, Any]) -> None:
    """Merge scan preferences into the config file. The ``env`` block is left as it is."""
    doc = _read_config_document(_config_read_path())
    current = doc.get("scan")
    if not isinstance(current, dict):
        current = {}
    current.update(prefs)
    doc["scan"] = current
    if not isinstance(doc.get("env"), dict):
        doc["env"] = {}
    _write_config_document(doc)


def _read_config_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config_document(doc: dict[str, Any]) -> None:
    target = _config_write_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    write_secret_text(target, json.dumps(doc, indent=2))


def _without_env_keys(env: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    blocked = {name.upper() for name in names}
    return {key: value for key, value in env.items() if str(key).upper() not in blocked}

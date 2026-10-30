"""Setup commands for the in-TUI settings dialog.

Model lists come from LiteLLM. The API key is accepted on the command and
stored in the config file; it is never copied into a snapshot or a result.
"""

from __future__ import annotations

import contextlib
import math
import webbrowser
from typing import TYPE_CHECKING, Any

from lamia.config import load_settings
from lamia.config.loader import (
    save_llm_connection,
    save_reasoning_effort,
    save_scan_preferences,
)
from lamia.config.model_catalog import (
    REASONING_EFFORTS,
    key_hint,
    list_models,
    list_providers,
    model_details,
)
from lamia.interface.auth_cli import BrowserLogin
from lamia.interface.tui.backend.projection import SCAN_MODES, SCOPE_MODES


if TYPE_CHECKING:
    from lamia.interface.tui.backend.controller import TuiController


SETTINGS_COMMANDS = frozenset(
    {
        "setup.list_providers",
        "setup.list_models",
        "setup.model_info",
        "setup.save_connection",
        "setup.set_options",
        "setup.begin_auth",
        "setup.poll_auth",
        "setup.complete_auth",
        "setup.cancel_auth",
    }
)


async def dispatch_settings(
    controller: TuiController,
    command: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    handler = _HANDLERS.get(command)
    if handler is None:
        return None
    return await handler(controller, payload)


async def _list_providers(
    _controller: TuiController,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    return {"providers": list_providers()}


async def _list_models_command(
    _controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    provider = _required_string(payload, "provider")
    api_key = _optional_secret(payload, "api_key")
    api_base = _optional_text(payload, "api_base")
    result = list_models(provider, api_key=api_key, api_base=api_base)
    _assert_no_secret(result, api_key)
    return result


async def _model_info(
    _controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return model_details(_required_string(payload, "model"))


async def _save_connection(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    model = _required_string(payload, "model")
    update_key = "api_key" in payload
    update_base = "api_base" in payload
    api_key = payload.get("api_key") if update_key else None
    api_base = payload.get("api_base") if update_base else None
    if update_key and not isinstance(api_key, str):
        raise TypeError("api_key must be a string")
    if update_base and api_base is not None and not isinstance(api_base, str):
        raise TypeError("api_base must be a string")
    save_llm_connection(
        model=model,
        api_key=api_key if isinstance(api_key, str) else None,
        api_base=api_base if isinstance(api_base, str) else None,
        update_key=update_key,
        update_base=update_base,
    )
    if controller._on_connection_saved is not None:
        await controller._on_connection_saved()
    configured, hint = key_hint(load_settings().llm.api_key)
    return {
        "model": model,
        "key_configured": configured,
        "key_hint": hint,
        "shell_locks_connection": controller.shell_locks_connection,
    }


async def _set_options(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    if "scan_mode" in payload:
        mode = payload["scan_mode"]
        if mode not in SCAN_MODES:
            choices = ", ".join(SCAN_MODES)
            raise ValueError(f"scan_mode must be one of: {choices}")
        controller.scan_mode = str(mode)
    if "max_budget_usd" in payload:
        controller.max_budget_usd = _budget(payload["max_budget_usd"])
    if "max_turns" in payload:
        controller.max_turns = _turns(payload["max_turns"])
    if "scope_mode" in payload:
        scope = payload["scope_mode"]
        if scope not in SCOPE_MODES:
            choices = ", ".join(SCOPE_MODES)
            raise ValueError(f"scope_mode must be one of: {choices}")
        controller.scope_mode = str(scope)
    if "diff_base" in payload:
        diff_base = payload["diff_base"]
        if diff_base is None:
            controller.diff_base = None
        elif isinstance(diff_base, str):
            controller.diff_base = diff_base.strip() or None
        else:
            raise TypeError("diff_base must be a string")
    if "reasoning_effort" in payload:
        effort = payload["reasoning_effort"]
        if not isinstance(effort, str) or effort.strip().lower() not in REASONING_EFFORTS:
            choices = ", ".join(REASONING_EFFORTS)
            raise ValueError(f"reasoning_effort must be one of: {choices}")
        save_reasoning_effort(effort)
    save_scan_preferences(
        {
            "scan_mode": controller.scan_mode,
            "max_budget_usd": controller.max_budget_usd,
            "max_turns": controller.max_turns,
            "scope_mode": controller.scope_mode,
            "diff_base": controller.diff_base or "",
        }
    )
    return {
        "scan_mode": controller.scan_mode,
        "max_budget_usd": controller.max_budget_usd,
        "max_turns": controller.max_turns,
        "scope_mode": controller.scope_mode,
        "diff_base": controller.diff_base,
    }


async def _begin_auth(
    controller: TuiController,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    controller.close_browser_login()
    login = BrowserLogin()
    controller._browser_login = login
    with contextlib.suppress(Exception):
        webbrowser.open(login.url)
    return {"authorize_url": login.url, "waiting": login.server is not None}


async def _poll_auth(
    controller: TuiController,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    login = controller._browser_login
    if login is None:
        return {"status": "error", "message": "Sign-in has not started"}
    return login.poll()


async def _complete_auth(
    controller: TuiController,
    payload: dict[str, Any],
) -> dict[str, Any]:
    controller._require_setup_mutable()
    login = controller._browser_login
    if login is None:
        login = BrowserLogin()
        controller._browser_login = login
    return login.complete(_required_string(payload, "redirect"))


async def _cancel_auth(
    controller: TuiController,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    controller.close_browser_login()
    return {"cancelled": True}


def _optional_secret(payload: dict[str, Any], name: str) -> str | None:
    if name not in payload:
        return load_settings().llm.api_key
    value = payload[name]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value.strip() or None


def _optional_text(payload: dict[str, Any], name: str) -> str | None:
    if name not in payload:
        return load_settings().llm.api_base
    value = payload[name]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value.strip() or None


def _required_string(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _budget(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise TypeError("max_budget_usd must be a number")
    try:
        amount = float(value)
    except ValueError as exc:
        raise ValueError("max_budget_usd must be a number") from exc
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("max_budget_usd must be greater than 0")
    return amount


def _turns(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise TypeError("max_turns must be an integer")
    try:
        turns = int(value)
    except ValueError as exc:
        raise ValueError("max_turns must be an integer") from exc
    if turns <= 0:
        raise ValueError("max_turns must be greater than 0")
    return turns


def _assert_no_secret(result: dict[str, Any], api_key: str | None) -> None:
    secret = (api_key or "").strip()
    if len(secret) < 6:
        return
    if secret in str(result):
        raise RuntimeError("model list included the API key")


_HANDLERS = {
    "setup.list_providers": _list_providers,
    "setup.list_models": _list_models_command,
    "setup.model_info": _model_info,
    "setup.save_connection": _save_connection,
    "setup.set_options": _set_options,
    "setup.begin_auth": _begin_auth,
    "setup.poll_auth": _poll_auth,
    "setup.complete_auth": _complete_auth,
    "setup.cancel_auth": _cancel_auth,
}

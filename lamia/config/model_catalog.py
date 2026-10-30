"""Provider and model lists for the TUI, taken from LiteLLM.

Live account lists use ``litellm.get_valid_models`` with the caller's key.
Providers that do not expose a model endpoint fall back to LiteLLM's catalog.
"""

from __future__ import annotations

from typing import Any

import litellm


# Shown first. The rest of LiteLLM's providers follow, in name order.
# ChatGPT and Custom are Lamia routes, not LiteLLM provider ids.
PINNED_PROVIDERS: tuple[tuple[str, str, bool, bool], ...] = (
    ("openrouter", "OpenRouter", True, False),
    ("openai", "OpenAI", True, False),
    ("anthropic", "Anthropic", True, False),
    ("gemini", "Gemini", True, False),
    ("groq", "Groq", True, False),
    ("deepseek", "DeepSeek", True, False),
    ("mistral", "Mistral", True, False),
    ("ollama", "Ollama", False, True),
    ("chatgpt", "ChatGPT subscription", False, False),
    ("custom", "Custom endpoint", True, True),
)

REASONING_EFFORTS: tuple[str, ...] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)

_MAX_MODELS = 300
_BASE_PROVIDERS = frozenset({"ollama", "ollama_chat", "custom"})
_CATALOG_NOTE = "Showing LiteLLM's catalog. This provider does not list the models on this account."


def list_providers() -> list[dict[str, Any]]:
    """Pinned providers, then every other provider LiteLLM knows."""
    known = set(getattr(litellm, "models_by_provider", {}) or {})
    pinned_ids = {item[0] for item in PINNED_PROVIDERS}
    providers = [
        {
            "id": provider_id,
            "label": label,
            "needs_key": needs_key,
            "needs_base": needs_base,
            "pinned": True,
        }
        for provider_id, label, needs_key, needs_base in PINNED_PROVIDERS
    ]
    for name in sorted(known):
        if name in pinned_ids:
            continue
        providers.append(
            {
                "id": name,
                "label": name,
                "needs_key": True,
                "needs_base": name in _BASE_PROVIDERS,
                "pinned": False,
            }
        )
    return providers


def list_models(
    provider: str,
    *,
    api_key: str | None = None,
    api_base: str | None = None,
) -> dict[str, Any]:
    """Models for ``provider``, from the account endpoint or the catalog.

    The result never includes ``api_key``.
    """
    provider_id = provider.strip().lower()
    if not provider_id:
        raise ValueError("provider must be a non-empty string")
    if provider_id == "chatgpt":
        models = [_compact(qualify("chatgpt", model), model) for model in _catalog_ids("openai")]
        return _page(models, source="catalog", note="ChatGPT subscription. No API key.")
    live_provider = "openai" if provider_id == "custom" else provider_id
    live, error = _live_ids(live_provider, api_key=api_key, api_base=api_base)
    if live:
        models = [_compact(qualify(provider_id, model), model) for model in live]
        return _page(models, source="account", note="")
    catalog_provider = "openai" if provider_id == "custom" else provider_id
    models = [
        _compact(qualify(provider_id, model), model) for model in _catalog_ids(catalog_provider)
    ]
    note = _CATALOG_NOTE
    if error:
        note = f"{note} {error}"
    return _page(models, source="catalog", note=note)


def model_details(model_id: str) -> dict[str, Any]:
    """Context, price, tool support, and reasoning for one model id."""
    info = _lookup_info(model_id)
    supports_reasoning, levels = _reasoning(info)
    tools = _tools(info)
    return {
        "id": model_id,
        "max_input_tokens": _int(info.get("max_input_tokens") or info.get("max_tokens")),
        "max_output_tokens": _int(info.get("max_output_tokens")),
        "input_cost_per_million": _per_million(info.get("input_cost_per_token")),
        "output_cost_per_million": _per_million(info.get("output_cost_per_token")),
        "supports_tools": tools,
        "supports_reasoning": supports_reasoning,
        "reasoning_levels": levels,
    }


def key_hint(api_key: str | None) -> tuple[bool, str]:
    """Whether a key is set, and a last-four mask that is empty when it is not.

    A key shorter than four characters is masked entirely.
    """
    key = (api_key or "").strip()
    if not key:
        return False, ""
    if len(key) < 4:
        return True, "••••"
    return True, f"••••{key[-4:]}"


def qualify(provider: str, model: str) -> str:
    """The model id Lamia stores, including the provider prefix."""
    model = model.strip()
    if provider == "chatgpt":
        bare = model
        for prefix in ("chatgpt/", "openai/"):
            if bare.startswith(prefix):
                bare = bare[len(prefix) :]
                break
        return f"chatgpt/{bare}"
    if provider == "custom":
        if "/" not in model:
            return f"openai/{model}"
        return model
    prefix = f"{provider}/"
    if model.startswith(prefix):
        return model
    return prefix + model


def _page(models: list[dict[str, Any]], *, source: str, note: str) -> dict[str, Any]:
    ordered = sorted(models, key=lambda item: str(item.get("id", "")))
    truncated = len(ordered) > _MAX_MODELS
    return {
        "source": source,
        "note": note,
        "models": ordered[:_MAX_MODELS],
        "truncated": truncated,
    }


def _catalog_ids(provider: str) -> list[str]:
    raw = (getattr(litellm, "models_by_provider", {}) or {}).get(provider) or []
    return [str(model) for model in raw if str(model).strip()]


def _live_ids(
    provider: str,
    *,
    api_key: str | None,
    api_base: str | None,
) -> tuple[list[str], str]:
    try:
        found = litellm.get_valid_models(
            check_provider_endpoint=True,
            custom_llm_provider=provider,
            api_key=api_key or None,
            api_base=api_base or None,
        )
    except Exception as exc:  # noqa: BLE001 - a failed endpoint falls back to the catalog
        return [], _redact(exc, api_key)
    if not isinstance(found, list):
        return [], ""
    return [str(model) for model in found if str(model).strip()], ""


def _compact(model_id: str, lookup: str) -> dict[str, Any]:
    info = _lookup_info(model_id) or _lookup_info(lookup)
    return {"id": model_id, "tools": _tools(info)}


def _lookup_info(model_id: str) -> dict[str, Any]:
    candidates = [model_id]
    if "/" in model_id:
        candidates.append(model_id.split("/", 1)[1])
    for candidate in candidates:
        info = _model_info(candidate)
        if info is not None:
            return info
    return {}


def _model_info(model_id: str) -> dict[str, Any] | None:
    try:
        info = litellm.get_model_info(model_id)
    except Exception:  # noqa: BLE001 - unmapped ids have no catalog entry
        return None
    return info if isinstance(info, dict) else None


def _tools(info: dict[str, Any]) -> bool | None:
    value = info.get("supports_function_calling")
    if isinstance(value, bool):
        return value
    return None


def _reasoning(info: dict[str, Any]) -> tuple[bool, list[str]]:
    raw = info.get("reasoning_effort_levels")
    if isinstance(raw, list):
        levels = [str(item).strip().lower() for item in raw]
        levels = [level for level in levels if level in REASONING_EFFORTS]
        if levels:
            return True, levels
    if info.get("supports_reasoning") is True:
        return True, list(REASONING_EFFORTS)
    return False, []


def _per_million(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value < 0:
        return None
    return round(float(value) * 1_000_000, 6)


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)


def _redact(exc: BaseException, api_key: str | None) -> str:
    text = str(exc)
    secret = (api_key or "").strip()
    if secret and len(secret) >= 6:
        text = text.replace(secret, "••••")
    return " ".join(text.split())[:240]

# Copyright 2025 OmniSecure Inc.
# Modified by the Lamia project from Strix.

"""Lamia application settings — pydantic-settings powered."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
ApiType = Literal["responses", "chat_completions"]

DEFAULT_MAX_TURNS = 500


def _lowercase(value: object) -> object:
    """Enum-like env values are matched case-insensitively (``None`` is ``none``)."""
    return value.strip().lower() if isinstance(value, str) else value


def _env(canonical: str, *legacy: str) -> AliasChoices:
    """Canonical ``LAMIA_*`` name first, so it wins when a legacy name is also set."""
    return AliasChoices(canonical, *legacy)


_BASE_CONFIG = SettingsConfigDict(
    case_sensitive=False,
    populate_by_name=True,
    extra="ignore",
)


class LlmSettings(BaseSettings):
    model_config = _BASE_CONFIG

    model: str | None = Field(
        default=None,
        validation_alias=_env("LAMIA_LLM", "STRIX_LLM"),
    )
    api_type: ApiType | None = Field(
        default=None,
        validation_alias=_env("LAMIA_API_TYPE", "STRIX_API_TYPE", "STRIX_FORCE_API"),
        description="Force 'responses' or 'chat_completions' API path",
    )
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
        repr=False,
    )
    api_base: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_API_BASE",
            "OPENAI_API_BASE",
            "OPENAI_BASE_URL",
            "LITELLM_BASE_URL",
            "OLLAMA_API_BASE",
        ),
    )
    extra_headers: dict[str, str] | None = Field(
        default=None,
        alias="LLM_EXTRA_HEADERS",
        repr=False,
    )
    extra_body: dict[str, Any] | None = Field(
        default=None,
        alias="LLM_EXTRA_BODY",
        repr=False,
    )
    reasoning_effort: ReasoningEffort = Field(
        default="high",
        validation_alias=_env("LAMIA_REASONING_EFFORT", "STRIX_REASONING_EFFORT"),
    )
    force_required_tool_choice: bool = Field(
        default=False,
        validation_alias=_env(
            "LAMIA_FORCE_REQUIRED_TOOL_CHOICE",
            "STRIX_FORCE_REQUIRED_TOOL_CHOICE",
        ),
    )
    parallel_tool_calls: bool = Field(
        default=False,
        validation_alias=_env("LAMIA_PARALLEL_TOOL_CALLS", "STRIX_PARALLEL_TOOL_CALLS"),
    )
    prompt_cache: bool = Field(
        default=True,
        validation_alias=_env("LAMIA_PROMPT_CACHE", "STRIX_PROMPT_CACHE"),
    )
    # Providers cache prompts in fixed-size token blocks, so a fully cached prompt
    # can read back up to a block short. 128 covers the largest common size
    # (OpenAI; DeepSeek and GLM use 64, vLLM defaults to 16).
    cache_block_tokens: int = Field(
        default=128,
        ge=1,
        validation_alias=_env("LAMIA_CACHE_BLOCK_TOKENS", "STRIX_CACHE_BLOCK_TOKENS"),
    )
    openrouter_sticky_sessions: bool = Field(
        default=False,
        validation_alias=_env(
            "LAMIA_OPENROUTER_STICKY_SESSIONS",
            "STRIX_OPENROUTER_STICKY_SESSIONS",
        ),
    )
    disable_streaming: bool = Field(
        default=False,
        alias="LLM_DISABLE_STREAMING",
    )
    timeout: int = Field(default=300, alias="LLM_TIMEOUT")
    preflight_timeout: int = Field(default=30, ge=1, alias="LLM_PREFLIGHT_TIMEOUT")
    stream_idle_timeout: int = Field(default=300, ge=0, alias="LLM_STREAM_IDLE_TIMEOUT")
    stream_first_event_timeout: int = Field(
        default=120, ge=0, alias="LLM_STREAM_FIRST_EVENT_TIMEOUT"
    )
    stream_total_timeout: int = Field(default=600, ge=0, alias="LLM_STREAM_TOTAL_TIMEOUT")
    max_tool_calls_per_turn: int = Field(
        default=32,
        ge=0,
        alias="LLM_MAX_TOOL_CALLS_PER_TURN",
    )

    @field_validator("api_type", "reasoning_effort", mode="before")
    @classmethod
    def _normalize_case(cls, value: object) -> object:
        return _lowercase(value)


class DedupeSettings(BaseSettings):
    model_config = _BASE_CONFIG

    model: str | None = Field(
        default=None,
        validation_alias=_env("LAMIA_DEDUPE_MODEL", "STRIX_DEDUPE_MODEL"),
    )
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        validation_alias=_env(
            "LAMIA_DEDUPE_REASONING_EFFORT",
            "STRIX_DEDUPE_REASONING_EFFORT",
        ),
    )
    api_key: str | None = Field(default=None, alias="DEDUPE_LLM_API_KEY", repr=False)
    api_base: str | None = Field(default=None, alias="DEDUPE_LLM_API_BASE")
    extra_headers: dict[str, str] | None = Field(
        default=None,
        alias="DEDUPE_LLM_EXTRA_HEADERS",
        repr=False,
    )
    extra_body: dict[str, Any] | None = Field(
        default=None,
        alias="DEDUPE_LLM_EXTRA_BODY",
        repr=False,
    )

    @field_validator("reasoning_effort", mode="before")
    @classmethod
    def _normalize_case(cls, value: object) -> object:
        return _lowercase(value)


class ContextSettings(BaseSettings):
    """Context-window management: per-tool-output caps and history compaction."""

    model_config = _BASE_CONFIG

    auto_compact: bool = Field(
        default=True,
        validation_alias=_env("LAMIA_CONTEXT_AUTO_COMPACT", "STRIX_CONTEXT_AUTO_COMPACT"),
    )
    compact_buffer_tokens: int = Field(
        default=20_000,
        gt=0,
        validation_alias=_env("LAMIA_CONTEXT_BUFFER_TOKENS", "STRIX_CONTEXT_BUFFER_TOKENS"),
    )
    keep_tokens: int = Field(
        default=8_000,
        gt=0,
        validation_alias=_env("LAMIA_CONTEXT_KEEP_TOKENS", "STRIX_CONTEXT_KEEP_TOKENS"),
    )
    fallback_context_tokens: int = Field(
        default=200_000,
        gt=0,
        validation_alias=_env("LAMIA_CONTEXT_FALLBACK_TOKENS", "STRIX_CONTEXT_FALLBACK_TOKENS"),
    )
    summary_max_tokens: int = Field(
        default=4_096,
        gt=0,
        validation_alias=_env("LAMIA_CONTEXT_SUMMARY_TOKENS", "STRIX_CONTEXT_SUMMARY_TOKENS"),
    )
    tool_output_max_tokens: int = Field(
        default=8_000,
        gt=0,
        validation_alias=_env("LAMIA_TOOL_OUTPUT_MAX_TOKENS", "STRIX_TOOL_OUTPUT_MAX_TOKENS"),
    )
    tool_output_max_lines: int = Field(
        default=2_000,
        gt=0,
        validation_alias=_env("LAMIA_TOOL_OUTPUT_MAX_LINES", "STRIX_TOOL_OUTPUT_MAX_LINES"),
    )
    # Floor above the truncation-notice size so a preview always fits.
    tool_output_max_bytes: int = Field(
        default=50 * 1024,
        ge=1024,
        validation_alias=_env("LAMIA_TOOL_OUTPUT_MAX_BYTES", "STRIX_TOOL_OUTPUT_MAX_BYTES"),
    )


class RuntimeSettings(BaseSettings):
    model_config = _BASE_CONFIG

    image: str = Field(
        default="ghcr.io/usestrix/strix-sandbox:1.3.0",
        validation_alias=_env("LAMIA_IMAGE", "STRIX_IMAGE"),
    )
    backend: str = Field(
        default="docker",
        validation_alias=_env("LAMIA_RUNTIME_BACKEND", "STRIX_RUNTIME_BACKEND"),
    )
    # Max screenshot/image tool outputs kept live per agent context (0 = none).
    max_context_images: int = Field(
        default=3,
        ge=0,
        validation_alias=_env("LAMIA_MAX_CONTEXT_IMAGES", "STRIX_MAX_CONTEXT_IMAGES"),
    )


class TelemetrySettings(BaseSettings):
    model_config = _BASE_CONFIG

    enabled: bool = Field(
        default=True,
        validation_alias=_env("LAMIA_TELEMETRY", "STRIX_TELEMETRY"),
    )
    run_record_timings: bool = Field(
        default=False,
        validation_alias=_env("LAMIA_RUN_RECORD_TIMINGS", "STRIX_RUN_RECORD_TIMINGS"),
    )


WebSearchProvider = Literal["auto", "perplexity", "exa"]
ExaSearchType = Literal["auto", "fast", "instant", "deep-lite", "deep", "deep-reasoning"]


class IntegrationSettings(BaseSettings):
    model_config = _BASE_CONFIG

    perplexity_api_key: str | None = Field(
        default=None,
        alias="PERPLEXITY_API_KEY",
        repr=False,
    )
    exa_api_key: str | None = Field(
        default=None,
        alias="EXA_API_KEY",
        repr=False,
    )
    web_search_provider: WebSearchProvider = Field(
        default="auto",
        validation_alias=_env("LAMIA_WEB_SEARCH_PROVIDER", "STRIX_WEB_SEARCH_PROVIDER"),
    )
    exa_search_type: ExaSearchType = Field(
        default="auto",
        validation_alias=_env("LAMIA_EXA_SEARCH_TYPE", "STRIX_EXA_SEARCH_TYPE"),
    )
    exa_num_results: int = Field(
        default=5,
        ge=1,
        le=100,
        validation_alias=_env("LAMIA_EXA_NUM_RESULTS", "STRIX_EXA_NUM_RESULTS"),
    )
    postman_api_key: str | None = Field(
        default=None,
        alias="POSTMAN_API_KEY",
        repr=False,
    )


class Settings(BaseSettings):
    model_config = _BASE_CONFIG

    llm: LlmSettings = Field(default_factory=LlmSettings)
    dedupe: DedupeSettings = Field(default_factory=DedupeSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)

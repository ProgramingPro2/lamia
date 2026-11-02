# Copyright 2025 OmniSecure Inc.
# Modified by the Lamia project from Strix.

"""Exception props stay local: a category and class name, never a message."""

from __future__ import annotations

import requests

from lamia.telemetry import report_error
from lamia.telemetry._common import exception_props


PRIVATE_MESSAGE = "private message that must stay on the machine"


def test_exception_props_uses_bare_name_for_builtins() -> None:
    assert exception_props(ValueError(PRIVATE_MESSAGE)) == {"exception_type": "ValueError"}


def test_exception_props_prefixes_third_party_top_level_package() -> None:
    props = exception_props(requests.exceptions.ConnectTimeout(PRIVATE_MESSAGE))
    assert props == {"exception_type": "requests.ConnectTimeout"}


def _chained(cause: BaseException | None, *, explicit: bool) -> RuntimeError:
    exc = RuntimeError("wrapped")
    if explicit:
        exc.__cause__ = cause
        exc.__suppress_context__ = True
    else:
        exc.__context__ = cause
    return exc


def test_exception_props_reports_explicit_cause() -> None:
    props = exception_props(_chained(ConnectionError(PRIVATE_MESSAGE), explicit=True))
    assert props == {"exception_type": "RuntimeError", "exception_cause": "ConnectionError"}


def test_exception_props_reports_implicit_context() -> None:
    props = exception_props(_chained(KeyError("k"), explicit=False))
    assert props["exception_cause"] == "KeyError"


def test_exception_props_ignores_suppressed_context() -> None:
    exc = _chained(None, explicit=True)
    exc.__context__ = KeyError("k")
    assert exception_props(exc) == {"exception_type": "RuntimeError"}


def test_exception_props_unwraps_exception_group() -> None:
    group = ExceptionGroup("tasks", [TimeoutError("t"), ValueError("v")])
    assert exception_props(group) == {"exception_type": "TimeoutError"}


def test_report_error_is_a_no_op() -> None:
    report_error("scan_failed", RuntimeError(PRIVATE_MESSAGE))
    report_error("docker_not_installed")

"""Telemetry hooks.

``LAMIA_TELEMETRY`` and ``STRIX_TELEMETRY`` are still accepted by settings.
Nothing is sent: the previous clients posted to Strix-operated collectors.
"""

from __future__ import annotations

from ._common import set_scan_phase


def report_error(error_type: str, exc: BaseException | None = None) -> None:
    """Accept a failure category and do nothing with it."""
    del error_type, exc


__all__ = [
    "report_error",
    "set_scan_phase",
]

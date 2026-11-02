# Copyright 2025 OmniSecure Inc.
# Modified by the Lamia project from Strix.

"""Backend bridge for external TUI clients."""

from lamia.interface.tui.backend.controller import TuiController
from lamia.interface.tui.backend.server import TuiBackendServer


__all__ = ["TuiBackendServer", "TuiController"]

"""Copilot Confirm - Enhanced Copilot agent with confirmation workflow."""

from .__version__ import (
    __author__,
    __copyright__,
    __license__,
    __version__,
)
from .install import (
    AgentInstaller,
    InstallationResult,
    create_installer,
)

__all__ = [
    "__version__",
    "__author__",
    "__copyright__",
    "__license__",
    "AgentInstaller",
    "create_installer",
    "InstallationResult",
]

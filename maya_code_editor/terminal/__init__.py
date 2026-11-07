"""Qt-side terminal pane.

Inside Maya the terminal embeds the native ``cmdScrollFieldReporter`` so
the output is identical to the Script Editor. Outside Maya a
``QPlainTextEdit`` captures ``sys.stdout`` / ``sys.stderr`` instead.
"""

from __future__ import annotations

from typing import Optional, Protocol

from PySide6.QtWidgets import QWidget

try:
    import maya.cmds  # type: ignore  # noqa: F401

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False


class Terminal(Protocol):
    """Common surface both terminal widgets provide."""

    def clear(self) -> None:
        """Clear all output."""

    def cleanup(self) -> None:
        """Release resources before the widget is destroyed."""


def create_terminal(parent: Optional[QWidget] = None) -> QWidget:
    """Create the terminal widget appropriate for the current environment.

    Args:
        parent: Parent widget.

    Returns:
        ``MayaTerminal`` inside Maya, ``FallbackTerminal`` otherwise.
    """
    if MAYA_AVAILABLE:
        from .maya_terminal import MayaTerminal

        return MayaTerminal(parent)

    from .fallback_terminal import FallbackTerminal

    return FallbackTerminal(parent)


__all__ = ["Terminal", "create_terminal"]

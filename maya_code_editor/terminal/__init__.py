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


def create_terminal(
    parent: Optional[QWidget] = None, settings: Optional[dict] = None
) -> QWidget:
    """Create the terminal widget appropriate for the current environment.

    Args:
        parent: Parent widget.
        settings: The ``terminal`` section of the user settings, if any.

    Returns:
        ``MayaTerminal`` inside Maya, ``FallbackTerminal`` otherwise.
    """
    if MAYA_AVAILABLE:
        from .maya_terminal import MayaTerminal

        terminal_settings = settings or {}
        return MayaTerminal(
            parent,
            echo_all_commands=bool(terminal_settings.get("echoAllCommands", False)),
            show_stack_trace=bool(terminal_settings.get("showStackTrace", True)),
        )

    from .fallback_terminal import FallbackTerminal

    return FallbackTerminal(parent)


__all__ = ["Terminal", "create_terminal"]

"""Python execution inside Maya via a hidden ``cmdScrollFieldExecuter``.

Ported from the previous editor's ``command/execution.py`` and reduced to
Python only. Using Maya's native executer (rather than ``exec``) makes
printed output, undo chunks and traceback formatting identical to the
Script Editor, and the output lands in the ``cmdScrollFieldReporter``
terminal automatically.

Outside Maya the executor falls back to ``exec`` with a persistent globals
dict so the standalone window stays usable for development.
"""

from __future__ import annotations

import traceback
from logging import getLogger
from typing import Optional

logger = getLogger(__name__)

try:
    import maya.cmds as cmds  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    cmds = None  # type: ignore[assignment]
    MAYA_AVAILABLE = False

HIDDEN_WINDOW_NAME = "mayaCodeEditorHiddenExecuter"


def build_exec_globals() -> dict:
    """Return the globals dict used by the standalone ``exec`` fallback.

    This is ``__main__``'s own namespace, matching Maya where the executer
    runs code in ``__main__``; completion looks names up there as well.
    """
    import __main__

    return vars(__main__)


class PythonExecutor:
    """Run Python source through Maya's hidden executer, or ``exec`` outside Maya."""

    def __init__(self) -> None:
        self.hidden_window: Optional[str] = None
        self.executer: Optional[str] = None
        self.exec_globals: dict = build_exec_globals()
        if MAYA_AVAILABLE:
            self._setup_executer()

    def _setup_executer(self) -> None:
        """Create the hidden window and executer control."""
        if cmds.window(HIDDEN_WINDOW_NAME, exists=True):
            cmds.deleteUI(HIDDEN_WINDOW_NAME)

        self.hidden_window = cmds.window(HIDDEN_WINDOW_NAME, visible=False, retain=True)
        cmds.setParent(self.hidden_window)
        layout = cmds.columnLayout()
        self.executer = cmds.cmdScrollFieldExecuter(
            parent=layout,
            sourceType="python",
            width=100,
            height=100,
        )

    def maya_version(self) -> str:
        """Return the running Maya version string, or an empty string outside Maya."""
        if not MAYA_AVAILABLE:
            return ""
        try:
            return str(cmds.about(version=True))
        except Exception:
            return ""

    def execute(self, code: str) -> bool:
        """Execute ``code`` in full.

        Args:
            code: Python source text.

        Returns:
            True if execution was dispatched. In Maya this does not reflect
            whether the user code raised; Maya prints that to the terminal.
        """
        if MAYA_AVAILABLE and self.executer:
            return self._execute_native(code)
        return self._execute_fallback(code)

    def _execute_native(self, code: str) -> bool:
        """Run through ``cmdScrollFieldExecuter`` so output goes to the reporter."""
        try:
            cmds.cmdScrollFieldExecuter(self.executer, edit=True, text=code)
            cmds.cmdScrollFieldExecuter(self.executer, edit=True, executeAll=True)
            return True
        except Exception as exc:
            logger.error("Failed to execute code: %s", exc)
            return False

    def _execute_fallback(self, code: str) -> bool:
        """Run with ``exec`` and print tracebacks to stderr."""
        try:
            exec(compile(code, "<editor>", "exec"), self.exec_globals)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def cleanup(self) -> None:
        """Delete the hidden executer window."""
        if (
            MAYA_AVAILABLE
            and self.hidden_window
            and cmds.window(self.hidden_window, exists=True)
        ):
            cmds.deleteUI(self.hidden_window)
        self.hidden_window = None
        self.executer = None

"""Maya native terminal using ``cmdScrollFieldReporter``.

Ported from the previous editor's ``ui/panels/maya_terminal.py`` with the
theme dependency removed. Anything printed in Maya (including output from
the hidden executer) shows up here exactly as in the Script Editor.
"""

from __future__ import annotations

from logging import getLogger
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCursor, QFontDatabase
from PySide6.QtWidgets import QMenu, QSizePolicy, QVBoxLayout, QWidget

logger = getLogger(__name__)

try:
    import maya.cmds as cmds  # type: ignore
    import maya.OpenMayaUI as omui  # type: ignore
    from shiboken6 import isValid, wrapInstance

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False

HIDDEN_WINDOW_NAME = "mayaCodeEditorReporterWindow"


class MayaTerminal(QWidget):
    """Widget embedding Maya's ``cmdScrollFieldReporter``."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.reporter: Optional[str] = None
        self.hidden_window: Optional[str] = None
        self.reporter_widget: Optional[QWidget] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if MAYA_AVAILABLE:
            self._setup_reporter(layout)

    def _setup_reporter(self, layout: QVBoxLayout) -> None:
        """Create the reporter in a hidden Maya window and reparent its Qt widget."""
        if cmds.window(HIDDEN_WINDOW_NAME, exists=True):
            cmds.deleteUI(HIDDEN_WINDOW_NAME)

        self.hidden_window = cmds.window(HIDDEN_WINDOW_NAME, visible=False, retain=True)
        maya_layout = cmds.columnLayout(adjustableColumn=True)
        self.reporter = cmds.cmdScrollFieldReporter(
            parent=maya_layout,
            width=400,
            height=150,
            echoAllCommands=False,
            suppressErrors=False,
            suppressWarnings=False,
            suppressInfo=False,
            suppressResults=False,
            suppressStackTrace=False,
            lineNumbers=False,
            stackTrace=True,
            filterSourceType="",
        )

        ptr = omui.MQtUtil.findControl(self.reporter)
        if not ptr:
            logger.error("Failed to get Qt widget for cmdScrollFieldReporter")
            return

        widget = wrapInstance(int(ptr), QWidget)
        widget.setMinimumSize(100, 50)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(widget.font().pointSize())
        widget.setFont(font)

        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(widget)
        widget.setVisible(True)
        self.reporter_widget = widget

    def reporter_qwidget(self) -> Optional[QWidget]:
        """Return a live Python wrapper for the reporter's Qt widget.

        The wrapper created at setup can be reported as "already deleted" by
        shiboken even though the Maya control is alive, so re-wrap from the
        control name whenever the cached wrapper is invalid.
        """
        if self.reporter_widget is not None and isValid(self.reporter_widget):
            return self.reporter_widget
        if not self._reporter_exists():
            return None
        ptr = omui.MQtUtil.findControl(self.reporter)
        if not ptr:
            return None
        self.reporter_widget = wrapInstance(int(ptr), QWidget)
        return self.reporter_widget

    def _show_context_menu(self, position) -> None:
        """Show a Copy / Clear menu at the mouse cursor.

        Args:
            position: Reporter-local click position (unused; the cursor
                position is used so a stale widget wrapper cannot break it).
        """
        if not self._reporter_exists():
            return
        menu = QMenu(self)

        copy_action = QAction("Copy", menu)
        copy_action.triggered.connect(self.copy_selection)
        menu.addAction(copy_action)

        menu.addSeparator()
        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(self.clear)
        menu.addAction(clear_action)

        menu.exec(QCursor.pos())

    def _reporter_exists(self) -> bool:
        """Return True if the Maya reporter control is still alive."""
        return bool(
            self.reporter and cmds.cmdScrollFieldReporter(self.reporter, exists=True)
        )

    def copy_selection(self) -> None:
        """Copy the selected text in the reporter to the clipboard."""
        if self._reporter_exists():
            cmds.cmdScrollFieldReporter(self.reporter, edit=True, copySelection=True)

    def clear(self) -> None:
        """Clear the reporter output."""
        if self._reporter_exists():
            cmds.cmdScrollFieldReporter(self.reporter, edit=True, clear=True)

    def cleanup(self) -> None:
        """Delete the hidden window that owns the reporter."""
        if (
            MAYA_AVAILABLE
            and self.hidden_window
            and cmds.window(self.hidden_window, exists=True)
        ):
            cmds.deleteUI(self.hidden_window)
        self.hidden_window = None
        self.reporter = None
        self.reporter_widget = None

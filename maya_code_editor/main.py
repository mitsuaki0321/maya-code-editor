"""Main window and Maya entry point.

The window is a vertical ``QSplitter`` with two panes:

* top: ``QWebEngineView`` hosting Monaco (tabs, file tree and editor live in HTML)
* bottom: a Qt terminal. Inside Maya this is the native
  ``cmdScrollFieldReporter`` so output matches the Script Editor;
  outside Maya it is a ``QPlainTextEdit`` capturing stdout/stderr.

Importing ``QtWebEngineWidgets`` happens at module import time so that the
WebEngine process is initialised before any view is created.
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from .bridge.channel import EditorBridge
from .bridge.execution import PythonExecutor
from .bridge.workspace import resolve_workspace_root
from .terminal import create_terminal

logger = getLogger(__name__)

try:
    import maya.cmds as cmds  # type: ignore  # noqa: F401

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False

WEB_ROOT = Path(__file__).resolve().parent / "web"
INDEX_HTML = WEB_ROOT / "index.html"


class MayaCodeEditorWindow(QWidget):
    """Top-level editor widget: Monaco web view above a Qt terminal."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MayaCodeEditorWindow")

        self.executor = PythonExecutor()
        self.workspace_root = resolve_workspace_root()
        self.terminal = create_terminal(self)
        self.web_view = QWebEngineView(self)
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = EditorBridge(self.executor, self.workspace_root, self)
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.addWidget(self.web_view)
        self.splitter.addWidget(self.terminal)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([500, 200])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.splitter)

        self._page_loaded = False

    def load_page(self) -> None:
        """Load ``web/index.html`` into the web view.

        Kept separate from ``__init__`` so the view can be parented (docked)
        before the page starts rendering; reparenting a live WebEngine view
        occasionally leaves it blank.
        """
        if self._page_loaded:
            return
        self._page_loaded = True
        self.web_view.load(QUrl.fromLocalFile(str(INDEX_HTML)))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Release Maya-side resources when the widget closes."""
        self.executor.cleanup()
        self.terminal.cleanup()
        super().closeEvent(event)


# Module-level references keep the docked editor alive across calls.
_window: Optional[MayaCodeEditorWindow] = None
_dock = None


def _is_alive(widget: Optional[QWidget]) -> bool:
    """Return True if ``widget`` exists and its C++ object is still valid."""
    if widget is None:
        return False
    try:
        from shiboken6 import isValid

        return bool(isValid(widget))
    except ImportError:
        try:
            widget.isVisible()
            return True
        except RuntimeError:
            return False


def show_ui() -> MayaCodeEditorWindow:
    """Show the editor docked in Maya, creating it on first call.

    Returns:
        The editor window instance.

    Raises:
        RuntimeError: If called outside Maya. Use ``python -m maya_code_editor``
            for a standalone window.
    """
    global _window, _dock

    if not MAYA_AVAILABLE:
        raise RuntimeError(
            "show_ui() requires Maya; run `python -m maya_code_editor` instead"
        )

    from .integration.maya_dock import MayaDock

    if not _is_alive(_window):
        _window = None
        _dock = None

    if _window is None:
        _window = MayaCodeEditorWindow()
        _dock = MayaDock(_window)
        _dock.create_docked_widget()
        _window.load_page()
    else:
        _dock.show()

    return _window

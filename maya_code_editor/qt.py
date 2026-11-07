"""Qt binding shim: PySide6 (Maya 2025+) with a PySide2 fallback (Maya 2022-2024).

Every module imports Qt names from here instead of from PySide directly.
The two bindings differ only in a handful of places for this code base:

* ``QAction`` lives in ``QtGui`` (Qt 6) or ``QtWidgets`` (Qt 5)
* ``QWebEnginePage`` lives in ``QtWebEngineCore`` (Qt 6) or ``QtWebEngineWidgets`` (Qt 5)
* ``shiboken6`` vs ``shiboken2``
* ``exec()`` vs ``exec_()`` on ``QApplication`` / ``QMenu`` -- use :func:`exec_`
"""

from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Slot
    from PySide6.QtGui import (
        QAction,
        QColor,
        QCursor,
        QFontDatabase,
        QGuiApplication,
        QTextCharFormat,
        QTextCursor,
    )
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import (
        QApplication,
        QMenu,
        QPlainTextEdit,
        QSizePolicy,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
    from shiboken6 import isValid, wrapInstance

    BINDING = "PySide6"
except ImportError:
    from PySide2.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Slot
    from PySide2.QtGui import (
        QColor,
        QCursor,
        QFontDatabase,
        QGuiApplication,
        QTextCharFormat,
        QTextCursor,
    )
    from PySide2.QtWebChannel import QWebChannel
    from PySide2.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
    from PySide2.QtWidgets import (
        QAction,
        QApplication,
        QMenu,
        QPlainTextEdit,
        QSizePolicy,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
    from shiboken2 import isValid, wrapInstance

    BINDING = "PySide2"


def exec_(obj: Any, *args: Any) -> Any:
    """Run ``obj.exec()`` (Qt 6) or ``obj.exec_()`` (Qt 5) with ``args``."""
    method = getattr(obj, "exec", None) or getattr(obj, "exec_")
    return method(*args)


__all__ = [
    "BINDING",
    "QAction",
    "QApplication",
    "QColor",
    "QCursor",
    "QFontDatabase",
    "QGuiApplication",
    "QMenu",
    "QObject",
    "QPlainTextEdit",
    "QPoint",
    "QSizePolicy",
    "QSplitter",
    "QTextCharFormat",
    "QTextCursor",
    "QTimer",
    "QUrl",
    "QVBoxLayout",
    "QWebChannel",
    "QWebEnginePage",
    "QWebEngineView",
    "QWidget",
    "Qt",
    "Slot",
    "exec_",
    "isValid",
    "wrapInstance",
]

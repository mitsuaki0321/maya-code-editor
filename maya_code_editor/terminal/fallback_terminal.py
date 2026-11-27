"""Standalone terminal: a read-only ``QPlainTextEdit`` capturing stdout/stderr.

Only used outside Maya. ``sys.stdout`` and ``sys.stderr`` are replaced with
tee streams while the widget is alive; the originals are restored in
:meth:`FallbackTerminal.cleanup`.
"""

from __future__ import annotations

import sys
from typing import Callable, Optional, TextIO

from ..bridge import config
from ..qt import (
    QAction,
    QColor,
    QFontDatabase,
    QPlainTextEdit,
    QTextCharFormat,
    QTextCursor,
    QWidget,
    exec_,
)

MAX_BLOCKS = 2000


class _TeeStream:
    """File-like object that forwards writes to the original stream and a callback."""

    def __init__(self, original: TextIO, on_write: Callable[[str], None]) -> None:
        self._original = original
        self._on_write = on_write

    def write(self, text: str) -> int:
        """Write ``text`` to the original stream and the terminal."""
        self._original.write(text)
        self._on_write(text)
        return len(text)

    def flush(self) -> None:
        """Flush the original stream."""
        self._original.flush()

    def isatty(self) -> bool:
        """Report that this is not a TTY."""
        return False


class FallbackTerminal(QPlainTextEdit):
    """Read-only output pane used when Maya's reporter is unavailable.

    Args:
        parent: Parent widget.
        wrap_lines: Initial state of the Wrap Lines toggle.
    """

    def __init__(
        self, parent: Optional[QWidget] = None, wrap_lines: bool = False
    ) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.wrap_action = QAction("Wrap Lines", self, checkable=True)
        self.wrap_action.setChecked(wrap_lines)
        self.wrap_action.toggled.connect(self.set_wrap_lines)
        self.set_wrap_lines(wrap_lines, remember=False)
        self.setMaximumBlockCount(MAX_BLOCKS)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setStyleSheet(
            "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; border: none; }"
        )

        self._stdout_format = QTextCharFormat()
        self._stderr_format = QTextCharFormat()
        self._stderr_format.setForeground(QColor("#f48771"))

        self._orig_stdout: Optional[TextIO] = None
        self._orig_stderr: Optional[TextIO] = None
        self._attach()

    def set_wrap_lines(self, enabled: bool, remember: bool = True) -> None:
        """Wrap long lines at the right edge and (optionally) save the choice."""
        mode = (
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if enabled
            else QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.setLineWrapMode(mode)
        if remember:
            config.update_setting("terminal", "wrapLines", enabled)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Standard menu plus the Wrap Lines toggle."""
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(self.wrap_action)
        exec_(menu, event.globalPos())
        menu.deleteLater()

    def _attach(self) -> None:
        """Replace ``sys.stdout`` / ``sys.stderr`` with tee streams."""
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = _TeeStream(
            self._orig_stdout, lambda t: self._append(t, self._stdout_format)
        )
        sys.stderr = _TeeStream(
            self._orig_stderr, lambda t: self._append(t, self._stderr_format)
        )

    def _append(self, text: str, fmt: QTextCharFormat) -> None:
        """Append ``text`` at the end with ``fmt`` and keep the view scrolled down."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def cleanup(self) -> None:
        """Restore the original ``sys.stdout`` / ``sys.stderr``."""
        if self._orig_stdout is not None:
            sys.stdout = self._orig_stdout
            self._orig_stdout = None
        if self._orig_stderr is not None:
            sys.stderr = self._orig_stderr
            self._orig_stderr = None

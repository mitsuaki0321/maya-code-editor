"""Standalone terminal: a read-only ``QPlainTextEdit`` capturing stdout/stderr.

Only used outside Maya. ``sys.stdout`` and ``sys.stderr`` are replaced with
tee streams while the widget is alive; the originals are restored in
:meth:`FallbackTerminal.cleanup`.
"""

from __future__ import annotations

import sys
from typing import Callable, Optional, TextIO

from ..qt import (
    QColor,
    QFontDatabase,
    QPlainTextEdit,
    QTextCharFormat,
    QTextCursor,
    QWidget,
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
    """Read-only output pane used when Maya's reporter is unavailable."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
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

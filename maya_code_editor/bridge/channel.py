"""QWebChannel object exposed to JavaScript as ``bridge``.

Every public ``@Slot`` here is callable from ``web/js/bridge.js``. Keep the
methods thin: they translate between JS-friendly types (str / bool / JSON)
and the Python modules that do the real work.
"""

from __future__ import annotations

import json
import platform
import sys
from logging import getLogger
from typing import Optional

from PySide6.QtCore import QObject, Slot

from .execution import PythonExecutor

logger = getLogger(__name__)


class EditorBridge(QObject):
    """Bridge between the Monaco page and the Python side."""

    def __init__(
        self, executor: PythonExecutor, parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self._executor = executor

    @Slot(result=str)
    def ping(self) -> str:
        """Return environment information as a JSON string.

        Used by the page on startup to verify the channel round trip.

        Returns:
            JSON object with ``python``, ``platform`` and ``maya`` keys.
        """
        info = {
            "python": sys.version.split()[0],
            "platform": platform.system(),
            "maya": self._executor.maya_version(),
        }
        return json.dumps(info)

    @Slot(str, result=bool)
    def run_code(self, code: str) -> bool:
        """Execute ``code`` as Python in Maya.

        Args:
            code: Full source text to execute.

        Returns:
            True if execution was dispatched without a bridge-level error.
            Runtime errors inside the user code are reported to the terminal,
            not through this return value.
        """
        return self._executor.execute(code)

    @Slot(str)
    def log(self, message: str) -> None:
        """Forward a message from JavaScript to the Python logger."""
        logger.info("[web] %s", message)

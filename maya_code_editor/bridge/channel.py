"""QWebChannel object exposed to JavaScript as ``bridge``.

Every public ``@Slot`` here is callable from ``web/js/bridge.js``. Keep the
methods thin: they translate between JS-friendly types (str / bool / JSON)
and the Python modules that do the real work. File operations return the
JSON form of :class:`~maya_code_editor.bridge.files.FileResult`.
"""

from __future__ import annotations

import json
import platform
import sys
from logging import getLogger
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Slot

from . import files
from .execution import PythonExecutor

logger = getLogger(__name__)


class EditorBridge(QObject):
    """Bridge between the Monaco page and the Python side."""

    def __init__(
        self,
        executor: PythonExecutor,
        workspace_root: Path,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._executor = executor
        self._root = workspace_root

    # -- environment -----------------------------------------------------

    @Slot(result=str)
    def ping(self) -> str:
        """Return environment information as a JSON string.

        Returns:
            JSON object with ``python``, ``platform`` and ``maya`` keys.
        """
        info = {
            "python": sys.version.split()[0],
            "platform": platform.system(),
            "maya": self._executor.maya_version(),
        }
        return json.dumps(info)

    @Slot(result=str)
    def get_workspace(self) -> str:
        """Return the workspace root as JSON ``{"root": path}``."""
        return json.dumps({"root": self._root.as_posix(), "name": self._root.name})

    # -- execution -------------------------------------------------------

    @Slot(str, result=bool)
    def run_code(self, code: str) -> bool:
        """Execute ``code`` as Python in Maya.

        Args:
            code: Full source text to execute.

        Returns:
            True if execution was dispatched without a bridge-level error.
        """
        return self._executor.execute(code)

    # -- files -----------------------------------------------------------

    @Slot(str, result=str)
    def list_dir(self, path: str) -> str:
        """List a directory. See :func:`files.list_dir`."""
        return files.list_dir(self._root, path).to_json()

    @Slot(str, result=str)
    def read_file(self, path: str) -> str:
        """Read a text file. See :func:`files.read_text`."""
        return files.read_text(self._root, path).to_json()

    @Slot(str, str, result=str)
    def write_file(self, path: str, content: str) -> str:
        """Write a text file. See :func:`files.write_text`."""
        return files.write_text(self._root, path, content).to_json()

    @Slot(str, str, result=str)
    def create_file(self, directory: str, name: str) -> str:
        """Create an empty file. See :func:`files.create_file`."""
        return files.create_file(self._root, directory, name).to_json()

    @Slot(str, str, result=str)
    def create_folder(self, directory: str, name: str) -> str:
        """Create a folder. See :func:`files.create_folder`."""
        return files.create_folder(self._root, directory, name).to_json()

    @Slot(str, str, result=str)
    def rename_path(self, path: str, new_name: str) -> str:
        """Rename a file or folder. See :func:`files.rename_path`."""
        return files.rename_path(self._root, path, new_name).to_json()

    @Slot(str, result=str)
    def delete_path(self, path: str) -> str:
        """Delete a file or folder. See :func:`files.delete_path`."""
        return files.delete_path(self._root, path).to_json()

    # -- logging ---------------------------------------------------------

    @Slot(str)
    def log(self, message: str) -> None:
        """Forward a message from JavaScript to the Python logger."""
        logger.info("[web] %s", message)

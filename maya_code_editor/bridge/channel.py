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
from typing import Callable, Optional

from PySide6.QtCore import QObject, Slot

from . import config, files
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
        self._terminal_toggle: Optional[Callable[[], bool]] = None
        self._session_get: Optional[Callable[[], dict]] = None
        self._session_put: Optional[Callable[[dict], None]] = None

    def set_terminal_toggle(self, toggle: Callable[[], bool]) -> None:
        """Register the Qt-side callback that toggles the terminal pane.

        Args:
            toggle: Callable that flips visibility and returns the new state.
        """
        self._terminal_toggle = toggle

    def set_session_hooks(
        self, get: Callable[[], dict], put: Callable[[dict], None]
    ) -> None:
        """Register how the page reads and reports session state.

        Args:
            get: Returns the session to restore (tabs, drafts, layout).
            put: Receives the page's current state whenever it changes.
        """
        self._session_get = get
        self._session_put = put

    # -- settings / session ----------------------------------------------

    @Slot(result=str)
    def get_settings(self) -> str:
        """Return the user settings (defaults merged) as JSON."""
        return json.dumps(config.load_settings())

    @Slot(result=str)
    def get_session(self) -> str:
        """Return the session to restore as JSON."""
        session = self._session_get() if self._session_get else config.load_session()
        return json.dumps(session)

    @Slot(str)
    def save_session(self, state_json: str) -> None:
        """Store the page's session state (tabs, drafts, sidebar width).

        Args:
            state_json: JSON object produced by ``tabs.sessionState()`` plus layout.
        """
        try:
            state = json.loads(state_json)
        except ValueError:
            logger.warning("Ignoring malformed session state from page")
            return
        if self._session_put and isinstance(state, dict):
            self._session_put(state)

    @Slot(result=str)
    def open_settings_file(self) -> str:
        """Open ``settings.json`` with the OS default application."""
        return files.open_with_default_app(config.settings_path()).to_json()

    # -- terminal --------------------------------------------------------

    @Slot(result=bool)
    def toggle_terminal(self) -> bool:
        """Toggle the terminal pane. Returns True if it is visible afterwards."""
        if self._terminal_toggle is None:
            return True
        return self._terminal_toggle()

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

    @Slot(str, result=str)
    def reveal_path(self, path: str) -> str:
        """Show a file or folder in the OS file manager. See :func:`files.reveal_path`."""
        return files.reveal_path(self._root, path).to_json()

    # -- logging ---------------------------------------------------------

    @Slot(str)
    def log(self, message: str) -> None:
        """Forward a message from JavaScript to the Python logger."""
        logger.info("[web] %s", message)

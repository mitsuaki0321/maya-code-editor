"""Workspace root resolution.

The file tree shows one root folder. The location is provisional: it
defaults to ``~/Documents/maya/maya_code_editor_workspace`` and can be
overridden with the ``MAYA_CODE_EDITOR_WORKSPACE`` environment variable
(used by the smoke tests to point at a temporary folder).
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "MAYA_CODE_EDITOR_WORKSPACE"
DEFAULT_ROOT = Path.home() / "Documents" / "maya" / "maya_code_editor_workspace"


def resolve_workspace_root() -> Path:
    """Return the workspace root, creating it if needed.

    Returns:
        Absolute path to the workspace folder.
    """
    override = os.environ.get(ENV_VAR, "").strip()
    root = Path(override).expanduser() if override else DEFAULT_ROOT
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root

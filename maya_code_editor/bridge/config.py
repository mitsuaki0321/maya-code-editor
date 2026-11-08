"""User settings and session persistence.

Two small JSON files live in ``~/Documents/maya/maya_code_editor/`` (override
the folder with ``MAYA_CODE_EDITOR_CONFIG`` for tests):

* ``settings.json`` -- preferences the user edits by hand. Missing keys fall
  back to :data:`DEFAULT_SETTINGS`, so the file may be partial.
* ``session.json`` -- open tabs, Untitled drafts and pane sizes, rewritten
  whenever the page reports a change and once more when Maya exits.
"""

from __future__ import annotations

import copy
import json
import os
from logging import getLogger
from pathlib import Path
from typing import Any

logger = getLogger(__name__)

ENV_VAR = "MAYA_CODE_EDITOR_CONFIG"
DEFAULT_DIR = Path.home() / "Documents" / "maya" / "maya_code_editor"
SETTINGS_FILE = "settings.json"
SESSION_FILE = "session.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "editor": {
        "theme": "dark-modern",  # dark-modern / light-modern / vs / vs-dark / hc-black / hc-light
        "fontSize": 13,
        "tabSize": 4,
        "wordWrap": "off",
        "minimap": False,
        "acceptSuggestionOnEnter": "off",  # off: Tab accepts, Enter always inserts a newline
    },
    "terminal": {
        "echoAllCommands": False,
        "showStackTrace": True,
    },
}

EMPTY_SESSION: dict[str, Any] = {"tabs": [], "activeIndex": -1, "layout": {}}


def config_dir() -> Path:
    """Return the config folder, creating it if needed."""
    override = os.environ.get(ENV_VAR, "").strip()
    path = Path(override).expanduser() if override else DEFAULT_DIR
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    """Return the path of ``settings.json``."""
    return config_dir() / SETTINGS_FILE


def session_path() -> Path:
    """Return the path of ``session.json``."""
    return config_dir() / SESSION_FILE


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from ``path``; return ``{}`` when missing or invalid."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable %s: %s", path.name, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``path`` as indented UTF-8 JSON."""
    try:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Cannot write %s: %s", path, exc)


def _merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return ``defaults`` deep-updated with ``overrides`` (dicts merge, others replace)."""
    result = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings() -> dict[str, Any]:
    """Load settings merged over the defaults.

    The file is (re)written whenever it is missing a key, so it always lists
    every available setting with its current value. Unknown keys the user
    added are kept.
    """
    path = settings_path()
    stored = _read_json(path)
    merged = _merge(DEFAULT_SETTINGS, stored)
    if merged != stored:
        _write_json(path, merged)
    return merged


def update_setting(section: str, key: str, value: Any) -> None:
    """Set ``settings[section][key] = value`` and save, keeping other entries."""
    settings = _merge(DEFAULT_SETTINGS, _read_json(settings_path()))
    settings.setdefault(section, {})[key] = value
    _write_json(settings_path(), settings)


def load_session() -> dict[str, Any]:
    """Load the last session, or an empty one."""
    return _merge(EMPTY_SESSION, _read_json(session_path()))


def save_session(session: dict[str, Any]) -> None:
    """Write ``session`` to ``session.json``."""
    _write_json(session_path(), session)

"""File system operations for the file tree and editor tabs.

Every function returns a :class:`FileResult` instead of raising, so the
bridge can hand the outcome to JavaScript as JSON. All paths are
validated to stay inside the workspace root.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Any, Optional

logger = getLogger(__name__)


@dataclass
class FileResult:
    """Outcome of a file operation.

    Attributes:
        ok: True on success.
        error: Human-readable message when ``ok`` is False.
        data: Operation-specific payload (listing, text, new path, ...).
    """

    ok: bool
    error: str = ""
    data: Any = field(default=None)

    def to_json(self) -> str:
        """Serialise to the JSON shape the web side expects."""
        return json.dumps({"ok": self.ok, "error": self.error, "data": self.data})


def _fail(message: str) -> FileResult:
    logger.error(message)
    return FileResult(ok=False, error=message)


def _resolve_inside(root: Path, raw: str) -> Optional[Path]:
    """Resolve ``raw`` and return it only if it is inside ``root``."""
    try:
        path = Path(raw).expanduser().resolve()
    except (OSError, ValueError):
        return None
    if path == root or root in path.parents:
        return path
    return None


def _valid_name(name: str) -> bool:
    """Return True for a single path component without separators or traversal."""
    if not name or name in {".", ".."}:
        return False
    return not any(sep in name for sep in ("/", "\\", "\0"))


def list_dir(root: Path, raw_path: str) -> FileResult:
    """List a directory, folders first, case-insensitively sorted.

    Args:
        root: Workspace root used to validate ``raw_path``.
        raw_path: Directory to list.

    Returns:
        ``data`` is a list of ``{"name", "path", "is_dir"}`` dicts.
    """
    path = _resolve_inside(root, raw_path)
    if path is None or not path.is_dir():
        return _fail(f"Not a directory inside the workspace: {raw_path}")
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        return _fail(f"Cannot list {path}: {exc}")
    data = [
        {"name": p.name, "path": p.as_posix(), "is_dir": p.is_dir()}
        for p in entries
        if p.name != "__pycache__"
    ]
    return FileResult(ok=True, data=data)


def read_text(root: Path, raw_path: str) -> FileResult:
    """Read a UTF-8 text file. ``data`` is the file content."""
    path = _resolve_inside(root, raw_path)
    if path is None or not path.is_file():
        return _fail(f"Not a file inside the workspace: {raw_path}")
    try:
        return FileResult(ok=True, data=path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(f"Cannot read {path}: {exc}")


def stat_paths(root: Path, raw_paths: list[str]) -> FileResult:
    """Return modification times for open files.

    ``data`` maps each requested path to its mtime in seconds, or ``None``
    when the file no longer exists (or lies outside the workspace).
    """
    result: dict[str, Optional[float]] = {}
    for raw in raw_paths:
        path = _resolve_inside(root, raw)
        try:
            result[raw] = path.stat().st_mtime if path is not None else None
        except OSError:
            result[raw] = None
    return FileResult(ok=True, data=result)


def write_text(root: Path, raw_path: str, content: str) -> FileResult:
    """Write ``content`` to a UTF-8 text file, creating it if missing."""
    path = _resolve_inside(root, raw_path)
    if path is None:
        return _fail(f"Path is outside the workspace: {raw_path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return _fail(f"Cannot write {path}: {exc}")
    return FileResult(ok=True, data=path.as_posix())


def create_file(root: Path, raw_dir: str, name: str) -> FileResult:
    """Create an empty file ``name`` inside ``raw_dir``. ``data`` is the new path."""
    parent = _resolve_inside(root, raw_dir)
    if parent is None or not parent.is_dir():
        return _fail(f"Not a directory inside the workspace: {raw_dir}")
    if not _valid_name(name):
        return _fail(f"Invalid file name: {name!r}")
    path = parent / name
    if path.exists():
        return _fail(f"Already exists: {path.name}")
    try:
        path.touch()
    except OSError as exc:
        return _fail(f"Cannot create {path}: {exc}")
    return FileResult(ok=True, data=path.as_posix())


def create_folder(root: Path, raw_dir: str, name: str) -> FileResult:
    """Create a folder ``name`` inside ``raw_dir``. ``data`` is the new path."""
    parent = _resolve_inside(root, raw_dir)
    if parent is None or not parent.is_dir():
        return _fail(f"Not a directory inside the workspace: {raw_dir}")
    if not _valid_name(name):
        return _fail(f"Invalid folder name: {name!r}")
    path = parent / name
    if path.exists():
        return _fail(f"Already exists: {path.name}")
    try:
        path.mkdir()
    except OSError as exc:
        return _fail(f"Cannot create {path}: {exc}")
    return FileResult(ok=True, data=path.as_posix())


def rename_path(root: Path, raw_path: str, new_name: str) -> FileResult:
    """Rename a file or folder in place. ``data`` is the new path."""
    path = _resolve_inside(root, raw_path)
    if path is None or path == root or not path.exists():
        return _fail(f"Cannot rename: {raw_path}")
    if not _valid_name(new_name):
        return _fail(f"Invalid name: {new_name!r}")
    target = path.with_name(new_name)
    if target.exists() and target != path:
        return _fail(f"Already exists: {new_name}")
    try:
        path.rename(target)
    except OSError as exc:
        return _fail(f"Cannot rename {path}: {exc}")
    return FileResult(ok=True, data=target.as_posix())


def move_path(root: Path, raw_path: str, raw_dest_dir: str) -> FileResult:
    """Move a file or folder into ``raw_dest_dir`` keeping its name. ``data`` is the new path."""
    path = _resolve_inside(root, raw_path)
    dest_dir = _resolve_inside(root, raw_dest_dir)
    if path is None or path == root or not path.exists():
        return _fail(f"Cannot move: {raw_path}")
    if dest_dir is None or not dest_dir.is_dir():
        return _fail(f"Not a folder inside the workspace: {raw_dest_dir}")
    if dest_dir == path or path in dest_dir.parents:
        return _fail(f"Cannot move a folder into itself: {path.name}")
    target = dest_dir / path.name
    if target == path:
        return FileResult(ok=True, data=path.as_posix())
    if target.exists():
        return _fail(f"Already exists in destination: {path.name}")
    try:
        shutil.move(str(path), str(target))
    except OSError as exc:
        return _fail(f"Cannot move {path}: {exc}")
    return FileResult(ok=True, data=target.as_posix())


def reveal_path(root: Path, raw_path: str) -> FileResult:
    """Open the OS file manager at ``raw_path``.

    A file is shown selected inside its folder; a folder is opened directly.
    """
    path = _resolve_inside(root, raw_path)
    if path is None or not path.exists():
        return _fail(f"Cannot reveal: {raw_path}")
    system = platform.system()
    try:
        if system == "Windows":
            if path.is_dir():
                os.startfile(str(path))  # noqa: S606 - opening a folder
            else:
                subprocess.Popen(["explorer", "/select,", str(path)])
        elif system == "Darwin":
            args = ["open", "-R", str(path)] if path.is_file() else ["open", str(path)]
            subprocess.Popen(args)
        else:
            target = path if path.is_dir() else path.parent
            subprocess.Popen(["xdg-open", str(target)])
    except OSError as exc:
        return _fail(f"Cannot reveal {path}: {exc}")
    return FileResult(ok=True, data=path.as_posix())


def open_with_default_app(path: Path) -> FileResult:
    """Open ``path`` with the OS default application (used for settings.json)."""
    if not path.exists():
        return _fail(f"File not found: {path}")
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # noqa: S606 - opening a user file
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        return _fail(f"Cannot open {path}: {exc}")
    return FileResult(ok=True, data=path.as_posix())


def delete_path(root: Path, raw_path: str) -> FileResult:
    """Delete a file, or a folder and its contents."""
    path = _resolve_inside(root, raw_path)
    if path is None or path == root or not path.exists():
        return _fail(f"Cannot delete: {raw_path}")
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as exc:
        return _fail(f"Cannot delete {path}: {exc}")
    return FileResult(ok=True, data=path.as_posix())

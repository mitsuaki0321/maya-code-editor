"""Completion by introspecting live objects, the way Maya's Script Editor does.

No static analysis: the dotted expression before the cursor (``cmds``,
``om2.MFnMesh``, ``node``) is resolved against ``__main__`` (where the
executer runs code), then against the ``import`` statements found in the
buffer, then against builtins. Members come from ``dir()``; attribute
lookups use ``getattr_static`` where possible so no property or descriptor
code runs. Nothing is cached or scanned in the background, so the cost is
paid only when a completion is requested (a few milliseconds).
"""

from __future__ import annotations

import builtins
import importlib
import inspect
import keyword
import re
from logging import getLogger
from typing import Any, Optional

logger = getLogger(__name__)

_IMPORT_RE = re.compile(r"^\s*import\s+(.+?)\s*$", re.M)
_FROM_RE = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+?)\s*$", re.M)
_NAME_RE = re.compile(r"^[A-Za-z_]\w*$")

MAX_ITEMS = 8000


def _parse_imports(source: str) -> dict[str, tuple[str, Optional[str]]]:
    """Map local names to ``(module, attribute)`` from the buffer's import lines.

    ``import maya.cmds as cmds`` -> ``{"cmds": ("maya.cmds", None)}``;
    ``import os.path`` -> ``{"os": ("os", None)}``;
    ``from maya.api import OpenMaya as om2`` -> ``{"om2": ("maya.api", "OpenMaya")}``.
    """
    aliases: dict[str, tuple[str, Optional[str]]] = {}
    for match in _IMPORT_RE.finditer(source):
        for part in match.group(1).split(","):
            tokens = part.strip().split()
            if not tokens or not re.match(r"^[\w.]+$", tokens[0]):
                continue
            module = tokens[0]
            if len(tokens) == 3 and tokens[1] == "as":
                aliases[tokens[2]] = (module, None)
            else:
                aliases[module.split(".")[0]] = (module.split(".")[0], None)
    for match in _FROM_RE.finditer(source):
        module = match.group(1)
        names = match.group(2).strip("() ")
        for part in names.split(","):
            tokens = part.strip().split()
            if not tokens or tokens[0] == "*":
                continue
            local = tokens[2] if len(tokens) == 3 and tokens[1] == "as" else tokens[0]
            aliases[local] = (module, tokens[0])
    return aliases


def _resolve_root(name: str, source: str) -> tuple[bool, Any]:
    """Find the object a bare name refers to: ``__main__``, buffer imports, then builtins."""
    import __main__

    if hasattr(__main__, name):
        return True, getattr(__main__, name)
    aliases = _parse_imports(source)
    if name in aliases:
        module, attr = aliases[name]
        try:
            obj = importlib.import_module(module)
            if attr:
                try:
                    obj = getattr(obj, attr)
                except AttributeError:
                    obj = importlib.import_module(f"{module}.{attr}")
            return True, obj
        except Exception as exc:
            logger.debug("Cannot import %s for completion: %s", module, exc)
            return False, None
    if hasattr(builtins, name):
        return True, getattr(builtins, name)
    return False, None


def _safe_getattr(obj: Any, name: str) -> tuple[bool, Any]:
    """Get ``obj.name`` without running property or descriptor code where avoidable."""
    try:
        static = inspect.getattr_static(obj, name)
    except AttributeError:
        return False, None
    if isinstance(static, property) or inspect.isdatadescriptor(static):
        return False, None  # evaluating could run arbitrary code
    try:
        return True, getattr(obj, name)
    except Exception:
        return False, None


def resolve(expression: str, source: str) -> tuple[bool, Any]:
    """Resolve a dotted name such as ``om2.MFnMesh`` to a live object."""
    parts = expression.split(".")
    if not all(_NAME_RE.match(p) for p in parts):
        return False, None
    found, obj = _resolve_root(parts[0], source)
    for part in parts[1:]:
        if not found:
            break
        found, obj = _safe_getattr(obj, part)
    return found, obj


def _kind(obj: Any, static: Any) -> str:
    """Classify a member for Monaco's CompletionItemKind."""
    if inspect.ismodule(obj):
        return "Module"
    if inspect.isclass(obj):
        return "Class"
    if isinstance(static, property) or inspect.isdatadescriptor(static):
        return "Property"
    if inspect.isroutine(obj) or inspect.isroutine(static):
        return "Function"
    if isinstance(obj, (int, float, str, bytes, bool)) or obj is None:
        return "Constant"
    return "Variable"


def _detail(obj: Any) -> str:
    """First docstring line, or a short type name."""
    doc = getattr(obj, "__doc__", None)
    if isinstance(doc, str) and doc.strip():
        return doc.strip().splitlines()[0][:120]
    return type(obj).__name__


def members(obj: Any) -> list[dict[str, str]]:
    """List completion items for the attributes of ``obj``."""
    try:
        names = dir(obj)
    except Exception:
        return []
    items: list[dict[str, str]] = []
    for name in names[:MAX_ITEMS]:
        if not _NAME_RE.match(name):
            continue
        try:
            static = inspect.getattr_static(obj, name)
        except AttributeError:
            static = None
        if isinstance(static, property) or inspect.isdatadescriptor(static):
            items.append({"label": name, "kind": "Property", "detail": ""})
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            items.append({"label": name, "kind": "Variable", "detail": ""})
            continue
        items.append(
            {"label": name, "kind": _kind(value, static), "detail": _detail(value)}
        )
    return items


def top_level(source: str) -> list[dict[str, str]]:
    """Names usable without a dot: ``__main__``, buffer imports, builtins, keywords."""
    import __main__

    items: dict[str, dict[str, str]] = {}
    for name in keyword.kwlist:
        items[name] = {"label": name, "kind": "Keyword", "detail": ""}
    for name in dir(builtins):
        if _NAME_RE.match(name) and not name.startswith("_"):
            value = getattr(builtins, name)
            items[name] = {
                "label": name,
                "kind": _kind(value, None),
                "detail": "builtin",
            }
    for name in _parse_imports(source):
        items[name] = {
            "label": name,
            "kind": "Module",
            "detail": "imported in this file",
        }
    for name in dir(__main__):
        if _NAME_RE.match(name) and not name.startswith("__"):
            try:
                value = getattr(__main__, name)
            except Exception:
                continue
            items[name] = {
                "label": name,
                "kind": _kind(value, None),
                "detail": _detail(value),
            }
    return list(items.values())


def complete(expression: str, source: str) -> list[dict[str, str]]:
    """Completion items for ``expression.`` (or top-level names when empty).

    Args:
        expression: Dotted name before the cursor, without the trailing dot.
        source: Full buffer text, used to resolve import statements.
    """
    if not expression:
        return top_level(source)
    found, obj = resolve(expression, source)
    return members(obj) if found else []

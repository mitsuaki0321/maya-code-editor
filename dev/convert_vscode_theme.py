"""Convert a VS Code color theme into a Monaco theme script.

usage::

    python dev/convert_vscode_theme.py <vscode theme json> <theme id>

Writes ``maya_code_editor/web/themes/<theme id>.js``, which registers the
theme on ``window.MCE_THEMES`` for ``app.js`` to pass to
``monaco.editor.defineTheme``. The VS Code ``include`` chain and JSONC
comments are resolved here, so the output is self-contained.

Monaco's Python tokenizer only distinguishes a handful of token types, so
only the TextMate scopes listed in :data:`TOKEN_SCOPES` are mapped.
Editor colors share their ids between VS Code and Monaco and are passed
through unchanged; a small ``chrome`` block carries the colors the HTML
shell (toolbar, tree, tabs, dialogs) needs as CSS variables.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "maya_code_editor" / "web" / "themes"

# Monaco token -> TextMate scopes to try, most specific first.
TOKEN_SCOPES: dict[str, list[str]] = {
    "comment": ["comment"],
    "string": ["string"],
    "string.escape": ["constant.character.escape", "string"],
    "number": ["constant.numeric"],
    "number.hex": ["constant.numeric"],
    "keyword": ["keyword", "storage.type", "storage"],
    "tag": ["entity.name.function.decorator", "entity.name.function", "keyword"],
    "type": ["entity.name.type", "support.type", "entity.name.class"],
    "delimiter": ["punctuation"],
}

# CSS variable -> VS Code color ids to try, first hit wins.
CHROME_KEYS: dict[str, list[str]] = {
    "bg": ["editor.background"],
    "panel-bg": ["sideBar.background", "editor.background"],
    "toolbar-bg": [
        "editorGroupHeader.tabsBackground",
        "titleBar.activeBackground",
        "sideBar.background",
    ],
    "fg": ["sideBar.foreground", "foreground", "editor.foreground"],
    "muted": [
        "descriptionForeground",
        "tab.inactiveForeground",
        "editorLineNumber.foreground",
    ],
    "border": [
        "sideBar.border",
        "editorGroup.border",
        "widget.border",
        "contrastBorder",
        "panel.border",
    ],
    "hover": ["list.hoverBackground"],
    "selected": ["list.activeSelectionBackground", "list.inactiveSelectionBackground"],
    "accent": ["button.background", "focusBorder"],
    "accent-hover": ["button.hoverBackground", "button.background"],
    "danger": ["errorForeground", "inputValidation.errorBorder"],
    "tab-active-bg": ["tab.activeBackground", "editor.background"],
    "tab-active-top": ["tab.activeBorderTop", "focusBorder"],
    "menu-bg": ["menu.background", "editorWidget.background", "sideBar.background"],
    "dialog-bg": ["editorWidget.background", "menu.background", "sideBar.background"],
    "input-bg": ["input.background", "editor.background"],
    "input-border": ["input.border", "widget.border", "sideBar.border"],
}


def _load_jsonc(path: Path) -> dict[str, Any]:
    """Parse JSON with comments and trailing commas."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def load_theme(path: Path) -> dict[str, Any]:
    """Load a theme and merge its ``include`` chain (base first)."""
    theme = _load_jsonc(path)
    include = theme.get("include")
    if not include:
        return theme
    base = load_theme((path.parent / include).resolve())
    merged: dict[str, Any] = dict(base)
    merged.update(
        {
            k: v
            for k, v in theme.items()
            if k not in ("tokenColors", "colors", "include")
        }
    )
    merged["colors"] = {**base.get("colors", {}), **theme.get("colors", {})}
    merged["tokenColors"] = list(base.get("tokenColors", [])) + list(
        theme.get("tokenColors", [])
    )
    return merged


def _scope_rules(theme: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Flatten tokenColors into (scope selector, settings) pairs, in order."""
    out: list[tuple[str, dict[str, Any]]] = []
    for rule in theme.get("tokenColors", []):
        scopes = rule.get("scope", [])
        if isinstance(scopes, str):
            scopes = [s.strip() for s in scopes.split(",")]
        for selector in scopes:
            # "a.b c.d" is a descendant selector; the last part names the token itself.
            out.append(
                (
                    selector.split()[-1] if selector.strip() else "",
                    rule.get("settings", {}),
                )
            )
    return out


def _lookup(
    rules: list[tuple[str, dict[str, Any]]], scope: str
) -> Optional[dict[str, Any]]:
    """Return the settings of the most specific, latest rule matching ``scope``."""
    best: Optional[tuple[int, int, dict[str, Any]]] = None
    for index, (selector, settings) in enumerate(rules):
        if not selector or "foreground" not in settings:
            continue
        if scope == selector or scope.startswith(selector + "."):
            key = (len(selector), index)
            if best is None or key > best[:2]:
                best = (len(selector), index, settings)
    return best[2] if best else None


def _hex(color: str) -> str:
    """Normalise a color to ``#rrggbb`` or ``#rrggbbaa`` lower-case."""
    return color.strip().lower()


def _rgb(color: str) -> tuple[int, int, int]:
    """Parse ``#rrggbb`` / ``#rrggbbaa`` into an RGB tuple (alpha ignored)."""
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(a: str, b: str, t: float) -> str:
    """Blend color ``a`` towards ``b`` by ``t`` (0..1)."""
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (
        round(ra + (rb - ra) * t),
        round(ga + (gb - ga) * t),
        round(ba + (bb - ba) * t),
    )


def _is_dark(theme: dict[str, Any], colors: dict[str, str]) -> bool:
    """Use the declared type, else the editor background luminance."""
    declared = theme.get("type")
    if declared in ("dark", "light", "hcDark", "hcLight"):
        return declared in ("dark", "hcDark")
    r, g, b = _rgb(colors.get("editor.background", "#1e1e1e"))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 128


def convert(theme: dict[str, Any], theme_id: str) -> dict[str, Any]:
    """Build the Monaco theme object plus the chrome palette."""
    rules_src = _scope_rules(theme)
    colors = {k: _hex(v) for k, v in theme.get("colors", {}).items()}
    is_dark = _is_dark(theme, colors)

    rules = []
    for token, scopes in TOKEN_SCOPES.items():
        for scope in scopes:
            settings = _lookup(rules_src, scope)
            if settings:
                rule: dict[str, Any] = {
                    "token": token,
                    "foreground": _hex(settings["foreground"]).lstrip("#"),
                }
                if settings.get("fontStyle"):
                    rule["fontStyle"] = settings["fontStyle"]
                rules.append(rule)
                break

    chrome: dict[str, str] = {}
    for var, keys in CHROME_KEYS.items():
        for key in keys:
            if key in colors:
                chrome[var] = colors[key]
                break

    # Derive the few shell colors a theme may leave undefined.
    bg = chrome.get("bg", "#1e1e1e" if is_dark else "#ffffff")
    fg = chrome.get("fg", "#cccccc" if is_dark else "#333333")
    chrome.setdefault("hover", _mix(bg, fg, 0.08))
    chrome.setdefault("selected", _mix(bg, fg, 0.16))
    chrome.setdefault("border", _mix(bg, fg, 0.12))
    if chrome.get("muted", fg) == fg:
        chrome["muted"] = _mix(fg, bg, 0.35)

    return {
        "id": theme_id,
        "name": theme.get("name", theme_id),
        "base": "vs-dark" if is_dark else "vs",
        "inherit": True,
        "rules": rules,
        "colors": colors,
        "chrome": chrome,
    }


def main(argv: list[str]) -> int:
    """Entry point."""
    if len(argv) != 3:
        print(__doc__)
        return 1
    source = Path(argv[1])
    theme_id = argv[2]
    result = convert(load_theme(source), theme_id)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{theme_id}.js"
    body = json.dumps(result, indent=2, ensure_ascii=False)
    out.write_text(
        f"// Generated by dev/convert_vscode_theme.py from {source.name}. Do not edit by hand.\n"
        f"window.MCE_THEMES = window.MCE_THEMES || {{}};\n"
        f"window.MCE_THEMES[{json.dumps(theme_id)}] = {body};\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"wrote {out} ({len(result['rules'])} token rules, {len(result['colors'])} colors, chrome={len(result['chrome'])})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

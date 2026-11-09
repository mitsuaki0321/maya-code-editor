# Maya Code Editor

[日本語](README_JP.md)

An editor for writing and running Python scripts in Maya.

The editing area is Monaco Editor, the same engine as VS Code, so find and
replace, multi-cursor, folding and the rest work with the key bindings you
already know. Output appears in the terminal in the same format as the Script
Editor.

Supported versions: Maya 2023 and later

## Launch

Run this in the Python tab of the Script Editor. Change the path to wherever
you put this repository.

```python
import sys
sys.path.insert(0, r"D:\claude\maya-code-editor")
import maya_code_editor
maya_code_editor.show_ui()
```

It is handy to put this on a shelf button or in your own tool menu.

## Usage

### Run

| Action | Key |
|---|---|
| Run | Ctrl+Enter, numpad Enter, or the Run button |

Runs the selection if there is one, otherwise the whole file.

### Files and tabs

| Action | Key / location |
|---|---|
| Save | Ctrl+S |
| Save All | Ctrl+K then S |
| New file | Ctrl+N |
| Close tab | Ctrl+W |
| Create, rename, delete and more | Right-click the tree on the left |
| Multi-select | Ctrl+click, Shift+click |
| Move files or folders | Drag with the middle mouse button onto the target folder |

When a file is changed by another editor, tabs you have not edited reload
automatically. Tabs with unsaved edits ask whether to reload or keep your
version.

Open tabs and the contents of unsaved new files are restored the next time you
start the editor.

### View

| Action | Key / location |
|---|---|
| Hide / show the tree | Ctrl+B, double-click the divider, or drag the divider to the left edge |
| Hide / show the terminal | Terminal button on the toolbar |
| Toggle word wrap | Alt+Z |
| Command palette | F1 |

Right-click the terminal to toggle Echo All Commands and Show Stack Trace.

### Completion

Suggestions appear when you type `.` or two or more characters of a name.
Tab accepts, Esc closes the list.

- Members of Maya modules, such as `cmds.` and `om2.MFnMesh.`
- Modules imported in the file, such as `import os` (works before the code is run)
- Variables you have already created by running code
- Python builtins and keywords

Nothing is suggested inside comments or strings.

## Settings

The Settings button on the toolbar opens `settings.json`. Changes take effect
the next time you start the editor.

```json
{
  "editor": { "theme": "dark-modern", "fontSize": 13, "tabSize": 4, "wordWrap": "off", "minimap": true },
  "terminal": { "echoAllCommands": false, "showStackTrace": true }
}
```

### Themes

Set `theme` to one of the following.

| Value | Description |
|---|---|
| `dark-modern` | VS Code's Dark Modern (default) |
| `light-modern` | VS Code's Light Modern |
| `vs-dark` / `vs` | Monaco's standard dark / light |
| `hc-black` / `hc-light` | High contrast |

### Other editor settings

The `editor` section accepts settings with the same names as VS Code's
`editor.*`. The most common ones:

| Setting | Example values | Description |
|---|---|---|
| `fontSize` | `13` | Text size |
| `fontFamily` | `"Consolas"` | Font |
| `tabSize` | `4` | Indent width |
| `insertSpaces` | `true` | Insert spaces when pressing Tab |
| `wordWrap` | `"off"` / `"on"` | Wrap long lines |
| `minimap` | `true` / `false` | Overview on the right edge |
| `lineNumbers` | `"on"` / `"off"` / `"relative"` | Line numbers |
| `renderWhitespace` | `"none"` / `"boundary"` / `"all"` | Show whitespace characters |
| `rulers` | `[88]` | Vertical lines at the given columns |
| `cursorStyle` | `"line"` / `"block"` / `"underline"` | Cursor shape |
| `cursorBlinking` | `"blink"` / `"smooth"` / `"solid"` | Cursor blinking |
| `mouseWheelZoom` | `true` | Change the text size with Ctrl+wheel |
| `scrollBeyondLastLine` | `false` | Allow scrolling past the last line |
| `acceptSuggestionOnEnter` | `"on"` / `"off"` | With `"off"`, Enter always inserts a newline even when suggestions are shown |
| `quickSuggestions` | `true` / `false` | Show suggestions automatically while typing |

Example:

```json
"editor": {
  "theme": "dark-modern",
  "fontSize": 14,
  "lineNumbers": "relative",
  "rulers": [88],
  "acceptSuggestionOnEnter": "off"
}
```

Settings not listed here work too. The complete list is in the
[Monaco Editor API reference](https://microsoft.github.io/monaco-editor/typedoc/interfaces/editor_editor_api.editor.IEditorOptions.html).

## File locations

| Content | Path |
|---|---|
| Workspace (the folder shown in the tree) | `~/Documents/maya/maya_code_editor_workspace` |
| Settings | `~/Documents/maya/maya_code_editor/settings.json` |
| Session (open tabs and so on) | `~/Documents/maya/maya_code_editor/session.json` |

The workspace location can be changed with the `MAYA_CODE_EDITOR_WORKSPACE`
environment variable.

## For developers

### How it works

- The UI is HTML inside a QWebEngineView and talks to Python through
  QWebChannel. Only the terminal is a Qt widget, built on Maya's
  `cmdScrollFieldReporter`
- The differences between PySide6 (Maya 2025 and later) and PySide2 (Maya
  2023 / 2024) are absorbed in `maya_code_editor/qt.py`
- The bundled Monaco is 0.44.0, the newest release that runs on the
  QtWebEngine in Maya 2023 / 2024; newer builds fail to load there
- Completion is not static analysis: it inspects live objects in the Maya
  session with `dir()`. Nothing runs at startup or in the background
- Themes are converted from VS Code's theme files by
  `dev/convert_vscode_theme.py`. Monaco's Python coloring is coarser than VS
  Code's, so function and variable names are not colored separately

### Tests

```
python dev/maya_smoke.py              # launch Maya 2025 and run the automated checks (logs in dev/out/)
python dev/maya_smoke.py --maya 2023  # another Maya version
python dev/maya_smoke.py --standalone # same steps without Maya
python -m maya_code_editor            # open a standalone window without Maya
```

The tests use a temporary workspace and a temporary config folder, so your
real files are never touched. Code goes through `ruff format` and `ruff check`.

### Layout

```
maya_code_editor/
├── main.py          main window, show_ui(), session saving
├── qt.py            PySide6 / PySide2 switch
├── bridge/          Python API exposed to JS (execution, files, completion, settings)
├── terminal/        terminal pane
├── integration/     docking into Maya
└── web/             UI (HTML / CSS / JS), themes, Monaco
```

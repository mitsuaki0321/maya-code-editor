"""Paste into Maya's Script Editor (Python tab) to open the editor.

Reloads the package each time so edits are picked up without restarting Maya.
"""

import importlib
import sys

REPO = r"D:\claude\maya-code-editor"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

for name in [m for m in list(sys.modules) if m.startswith("maya_code_editor")]:
    del sys.modules[name]

maya_code_editor = importlib.import_module("maya_code_editor")
maya_code_editor.show_ui()

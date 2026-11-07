"""Standalone launcher for development outside Maya.

Usage::

    python -m maya_code_editor
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main import MayaCodeEditorWindow


def main() -> int:
    """Run the editor as a standalone Qt application.

    Returns:
        Process exit code from the Qt event loop.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = MayaCodeEditorWindow()
    window.setWindowTitle("Maya Code Editor (standalone)")
    window.resize(1000, 700)
    window.show()
    window.load_page()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

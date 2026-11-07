"""Maya Code Editor built on Monaco Editor and QWebEngineView.

Public entry point is :func:`show_ui`, which opens the editor docked in
Maya. Run ``python -m maya_code_editor`` for a standalone window outside
Maya.
"""

from .main import show_ui

__all__ = ["show_ui"]

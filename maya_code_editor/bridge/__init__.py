"""Python API exposed to the web page through QWebChannel."""

from .channel import EditorBridge
from .execution import PythonExecutor

__all__ = ["EditorBridge", "PythonExecutor"]

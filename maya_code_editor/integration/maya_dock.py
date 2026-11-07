"""Maya ``workspaceControl`` docking for the editor window.

Ported from the previous editor's ``integration/maya_dock.py``. Creates a
workspace control, wraps its Qt widget and parents the editor into it.
"""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import Optional

from ..qt import QVBoxLayout, QWidget, wrapInstance

logger = getLogger(__name__)

try:
    import maya.cmds as cmds  # type: ignore
    import maya.OpenMayaUI as omui  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False


class MayaDock:
    """Manage the workspaceControl that hosts the editor widget."""

    CONTROL_NAME = "MayaCodeEditorWorkspaceControl"
    WINDOW_TITLE = "Code Editor"

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.workspace_control: Optional[str] = None

    def create_docked_widget(self) -> Optional[str]:
        """Create the workspace control and parent the widget into it.

        Returns:
            The workspace control name, or None outside Maya.
        """
        if not MAYA_AVAILABLE:
            return None

        if cmds.workspaceControl(self.CONTROL_NAME, exists=True):
            if self.widget.parent() is not None:
                self.widget.setParent(None)
            cmds.deleteUI(self.CONTROL_NAME)

        with contextlib.suppress(Exception):
            cmds.workspaceControlState(self.CONTROL_NAME, remove=True)

        self.workspace_control = cmds.workspaceControl(
            self.CONTROL_NAME,
            label=self.WINDOW_TITLE,
            dockToControl=["ChannelBoxLayerEditor", "left"],
            initialWidth=900,
            initialHeight=600,
            minimumWidth=600,
            widthProperty="free",
            heightProperty="free",
            retain=False,
            floating=False,
            loadImmediately=True,
            visible=True,
        )

        if cmds.workspaceControl(self.workspace_control, query=True, floating=True):
            cmds.deleteUI(self.workspace_control)
            self.workspace_control = cmds.workspaceControl(
                self.CONTROL_NAME,
                label=self.WINDOW_TITLE,
                dockToMainWindow=("right", 1),
                initialWidth=900,
                initialHeight=600,
                minimumWidth=600,
                widthProperty="free",
                heightProperty="free",
                retain=False,
                floating=False,
                loadImmediately=True,
                visible=True,
            )

        self._parent_widget_into_control()

        cmds.workspaceControl(self.workspace_control, edit=True, visible=True)
        cmds.workspaceControl(self.workspace_control, edit=True, restore=True)
        with contextlib.suppress(Exception):
            cmds.workspaceControl(self.workspace_control, edit=True, selectTab=True)

        return self.workspace_control

    def _parent_widget_into_control(self) -> None:
        """Wrap the control's Qt widget and add the editor to its layout."""
        ptr = omui.MQtUtil.findControl(self.CONTROL_NAME)
        if not ptr:
            raise RuntimeError("workspaceControl widget not found")

        host = wrapInstance(int(ptr), QWidget)
        self.widget.setParent(host)

        layout = host.layout()
        if layout is None:
            layout = QVBoxLayout(host)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)

        self.widget.show()
        host.show()

    def show(self) -> None:
        """Show the control, recreating it if it was closed or is floating."""
        if not MAYA_AVAILABLE:
            return

        if not cmds.workspaceControl(self.CONTROL_NAME, exists=True):
            self.create_docked_widget()
            return

        if cmds.workspaceControl(self.CONTROL_NAME, query=True, floating=True):
            if self.widget.parent() is not None:
                self.widget.setParent(None)
            cmds.deleteUI(self.CONTROL_NAME)
            self.workspace_control = None
            self.create_docked_widget()
            return

        cmds.workspaceControl(self.CONTROL_NAME, edit=True, visible=True)
        cmds.workspaceControl(self.CONTROL_NAME, edit=True, restore=True)
        with contextlib.suppress(Exception):
            cmds.workspaceControl(self.CONTROL_NAME, edit=True, selectTab=True)
        self.widget.show()

    def hide(self) -> None:
        """Hide the control without deleting it."""
        if MAYA_AVAILABLE and cmds.workspaceControl(self.CONTROL_NAME, exists=True):
            cmds.workspaceControl(self.CONTROL_NAME, edit=True, visible=False)

    def close(self) -> None:
        """Delete the control."""
        if MAYA_AVAILABLE and cmds.workspaceControl(self.CONTROL_NAME, exists=True):
            cmds.deleteUI(self.CONTROL_NAME)
        self.workspace_control = None

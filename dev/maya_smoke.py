"""Automated smoke test for the editor, in a real Maya GUI or standalone.

Run from a normal shell::

    python dev/maya_smoke.py                # launches Maya 2025 and drives it
    python dev/maya_smoke.py --maya 2026
    python dev/maya_smoke.py --standalone   # same steps in a plain Qt app

A fresh workspace is created under ``dev/out/smoke_workspace`` and passed
via ``MAYA_CODE_EDITOR_WORKSPACE`` so the real workspace is never touched.
Results land in ``dev/out/maya_smoke.log`` and ``dev/out/maya_smoke.png``.

The same file is executed inside Maya (via ``exec``) to drive the test.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "dev" / "out"
LOG = OUT_DIR / "maya_smoke.log"
PNG = OUT_DIR / "maya_smoke.png"
WORKSPACE = OUT_DIR / "smoke_workspace"
CONFIG_DIR = OUT_DIR / "smoke_config"
ENV_VAR = "MAYA_CODE_EDITOR_WORKSPACE"
ENV_CONFIG = "MAYA_CODE_EDITOR_CONFIG"

HELLO_PY = 'print("from file")\n'

# Each step: (name, JS expression evaluated inside an async wrapper, optional
# Python-side check run after the JS result arrives).
Step = tuple[str, str, Optional[Callable[[], str]]]


def _check_hello_saved() -> str:
    text = (WORKSPACE / "hello.py").read_text(encoding="utf-8")
    return "hello.py contains edit: %s" % ('print("edited")' in text)


def _check_new_file() -> str:
    path = WORKSPACE / "new_one.py"
    return "new_one.py exists=%s content=%r" % (
        path.exists(),
        path.read_text(encoding="utf-8") if path.exists() else None,
    )


def _check_renamed() -> str:
    return "renamed.py exists=%s new_one.py exists=%s" % (
        (WORKSPACE / "renamed.py").exists(),
        (WORKSPACE / "new_one.py").exists(),
    )


def _check_deleted() -> str:
    return "renamed.py exists=%s" % (WORKSPACE / "renamed.py").exists()


def _check_session_file() -> str:
    session = json.loads((CONFIG_DIR / "session.json").read_text(encoding="utf-8"))
    settings = json.loads((CONFIG_DIR / "settings.json").read_text(encoding="utf-8"))
    tabs = [
        (t.get("kind"), t.get("path") or t.get("title"))
        for t in session.get("tabs", [])
    ]
    draft = next(
        (
            t.get("content")
            for t in session.get("tabs", [])
            if t.get("kind") == "untitled"
        ),
        None,
    )
    return "session tabs=%s active=%s draft=%r layout=%s | settings.editor=%s" % (
        tabs,
        session.get("activeIndex"),
        draft,
        session.get("layout"),
        settings.get("editor"),
    )


# The live editor window, set by the drivers so Python-side checks can reach it.
_WINDOW: dict = {"ref": None}


STEPS: list[Step] = [
    (
        "status",
        "document.getElementById('status').textContent + ' | monaco=' + (typeof monaco !== 'undefined')",
        None,
    ),
    ("workspace", "app.workspace.root", None),
    (
        "tree-initial",
        "Array.from(document.querySelectorAll('#file-tree .tree-label')).map(n => n.textContent)",
        None,
    ),
    (
        "open",
        "app.tabs.openFile(app.workspace.root + '/hello.py').then(t => ({title: t.title, tabs: app.tabs.tabs.length, dirty: app.tabs.isDirty(t)}))",
        None,
    ),
    (
        "edit",
        "(app.editor.executeEdits('smoke', [{range: new app.monaco.Range(1e6, 1, 1e6, 1), text: 'print(\"edited\")\\n'}]), {dirty: app.tabs.isDirty(app.tabs.activeTab), hasClass: app.tabs.activeTab.el.classList.contains('dirty')})",
        None,
    ),
    (
        "save",
        "app.tabs.save().then(ok => ({ok: ok, dirty: app.tabs.isDirty(app.tabs.activeTab)}))",
        _check_hello_saved,
    ),
    (
        "new-untitled-save",
        "(app.tabs.newUntitled(), app.editor.setValue('print(\"new file\")\\n'), app.tabs.save(null, 'new_one.py').then(ok => ({ok: ok, path: app.tabs.activeTab.path, tabs: app.tabs.tabs.map(t => t.title)})))",
        _check_new_file,
    ),
    (
        "tree-after-save",
        "app.tree.refresh().then(() => Array.from(document.querySelectorAll('#file-tree .tree-label')).map(n => n.textContent))",
        None,
    ),
    (
        "rename",
        "app.bridge.files.rename(app.workspace.root + '/new_one.py', 'renamed.py').then(p => { app.tabs.onPathRenamed(app.workspace.root + '/new_one.py', p, false); return app.tabs.tabs.map(t => t.title); })",
        _check_renamed,
    ),
    (
        "close-active",
        "app.tabs.close(null, true).then(ok => ({ok: ok, tabs: app.tabs.tabs.length, active: app.tabs.activeTab && app.tabs.activeTab.title}))",
        None,
    ),
    ("run", "app.runActive().then(() => 'dispatched')", None),
    (
        "run-selection",
        "(app.editor.setSelection(new app.monaco.Range(2, 1, 2, 1000)), app.runActive().then(() => ({selected: app.editor.getModel().getValueInRange(app.editor.getSelection())})))",
        None,
    ),
    (
        "terminal-hide",
        "app.toggleTerminal().then(() => ({buttonOff: document.getElementById('terminal-button').classList.contains('off')}))",
        lambda: "terminal visible=%s" % _WINDOW["ref"].terminal.isVisible(),
    ),
    (
        "terminal-show",
        "app.toggleTerminal().then(() => ({buttonOff: document.getElementById('terminal-button').classList.contains('off')}))",
        lambda: "terminal visible=%s" % _WINDOW["ref"].terminal.isVisible(),
    ),
    (
        "delete",
        "app.bridge.files.remove(app.workspace.root + '/renamed.py').then(() => app.tree.refresh()).then(() => Array.from(document.querySelectorAll('#file-tree .tree-label')).map(n => n.textContent))",
        _check_deleted,
    ),
    (
        "session-save",
        "(app.tabs.newUntitled(), app.editor.setValue('draft text'), app.tabs.activate(app.tabs.tabs[0]), app.saveSessionNow(), {tabs: app.tabs.tabs.map(t => t.title), active: app.tabs.tabs.indexOf(app.tabs.activeTab), settingsFont: app.settings.editor.fontSize})",
        _check_session_file,
    ),
]

RESTORE_JS = (
    "window.app ? JSON.stringify({restored: app.restoredTabs, tabs: app.tabs.tabs.map(t => ({title: t.title, dirty: app.tabs.isDirty(t)})),"
    " active: app.tabs.activeTab && app.tabs.activeTab.title, draft: (app.tabs.tabs.find(t => !t.path) || {model: {getValue: () => null}}).model.getValue()}) : ''"
)

WRAP_JS = (
    "window.__smoke = {done: false};"
    "(async () => { try { const r = await (%s); window.__smoke = {done: true, result: JSON.stringify(r === undefined ? null : r)}; }"
    " catch (e) { window.__smoke = {done: true, error: String(e && e.stack || e)}; } })();"
)
POLL_JS = "JSON.stringify(window.__smoke || {done: false})"


def _log(msg: str) -> None:
    """Append one line to the log file."""
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _prepare_workspace() -> None:
    """Create a fresh smoke workspace with one known file."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    (WORKSPACE / "sub").mkdir(parents=True)
    (WORKSPACE / "hello.py").write_text(HELLO_PY, encoding="utf-8")
    (WORKSPACE / "sub" / "nested.py").write_text("# nested\n", encoding="utf-8")
    if CONFIG_DIR.exists():
        shutil.rmtree(CONFIG_DIR)
    os.environ[ENV_VAR] = str(WORKSPACE)
    os.environ[ENV_CONFIG] = str(CONFIG_DIR)


def _verify_restore(
    make_window: Callable, legacy_signature: bool, on_done: Callable[[], None]
) -> None:
    """Open a second window and log what it restored from session.json."""
    from PySide6.QtCore import QTimer

    window2 = make_window()
    _WINDOW["restore_ref"] = window2  # keep alive
    page = window2.web_view.page()
    run_js = _make_run_js(page, legacy_signature)
    attempts = {"n": 0}

    def poll() -> None:
        attempts["n"] += 1

        def got(value) -> None:
            if value:
                _log("RESTORE: " + str(value))
                on_done()
            elif attempts["n"] < 40:
                QTimer.singleShot(250, poll)
            else:
                _log("RESTORE FAILED: page never became ready")
                on_done()

        run_js(RESTORE_JS, got)

    QTimer.singleShot(2500, poll)


class StepRunner:
    """Drive the page through STEPS with runJavaScript polling."""

    def __init__(self, page, run_js: Callable, on_done: Callable[[], None]) -> None:
        from PySide6.QtCore import QTimer

        self._page = page
        self._run_js = run_js
        self._on_done = on_done
        self._timer = QTimer()
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._poll)
        self._index = -1
        self._failures = 0

    def start(self) -> None:
        self._next()

    def _next(self) -> None:
        self._index += 1
        if self._index >= len(STEPS):
            _log("STEPS DONE failures=%d" % self._failures)
            self._on_done()
            return
        name, js, _ = STEPS[self._index]
        self._run_js(WRAP_JS % js)
        self._timer.start()

    def _poll(self) -> None:
        self._run_js(POLL_JS, self._on_poll)

    def _on_poll(self, value) -> None:
        state = json.loads(value) if value else {"done": False}
        if not state.get("done"):
            return
        self._timer.stop()
        name, _, check = STEPS[self._index]
        if "error" in state:
            self._failures += 1
            _log("[%s] ERROR %s" % (name, state["error"]))
        else:
            _log("[%s] %s" % (name, state.get("result")))
        if check is not None:
            try:
                _log("[%s] check: %s" % (name, check()))
            except Exception:
                self._failures += 1
                _log("[%s] check FAILED\n%s" % (name, traceback.format_exc()))
        self._next()


def _make_run_js(page, legacy_signature: bool) -> Callable:
    """Return a run_js(js, callback=None) helper for either PySide6 signature."""

    def run_js(js: str, callback: Optional[Callable] = None) -> None:
        if callback is None:
            page.runJavaScript(js)
        elif legacy_signature:
            page.runJavaScript(js, 0, callback)
        else:
            page.runJavaScript(js, 0, callback)

    return run_js


def run_inside_maya() -> None:
    """Drive the editor inside Maya and write log / screenshot."""
    import maya.cmds as cmds  # type: ignore
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication

    _prepare_workspace()
    LOG.write_text("", encoding="utf-8")
    _log(f"maya {cmds.about(version=True)}")

    def quit_maya() -> None:
        cmds.quit(force=True)

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    try:
        import maya_code_editor

        window = maya_code_editor.show_ui()
        _log(
            f"show_ui ok; terminal={type(window.terminal).__name__} workspace={window.workspace_root}"
        )
    except Exception:
        _log("show_ui FAILED\n" + traceback.format_exc())
        QTimer.singleShot(1000, quit_maya)
        return

    _WINDOW["ref"] = window
    page = window.web_view.page()
    page.loadFinished.connect(lambda ok: _log(f"loadFinished ok={ok}"))
    run_js = _make_run_js(page, legacy_signature=True)

    def check_history_menu() -> None:
        """Toggle the History menu items and read the reporter flags back."""
        terminal = window.terminal
        try:
            before = cmds.cmdScrollFieldReporter(
                terminal.reporter, query=True, echoAllCommands=True
            )
            terminal.echo_action.setChecked(True)
            after = cmds.cmdScrollFieldReporter(
                terminal.reporter, query=True, echoAllCommands=True
            )
            saved = json.loads(
                (CONFIG_DIR / "settings.json").read_text(encoding="utf-8")
            )["terminal"]
            _log(f"history menu: settings.json after toggle={saved}")
            terminal.echo_action.setChecked(False)
            trace = cmds.cmdScrollFieldReporter(
                terminal.reporter, query=True, stackTrace=True
            )
            _log(
                f"history menu: echo default={before} after toggle={after}; stackTrace default={trace}"
            )
        except Exception:
            _log("history menu FAILED\n" + traceback.format_exc())

    def check_context_menu() -> None:
        """Open the terminal context menu (closed by a timer) to catch stale wrappers."""
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu

        widget = window.terminal.reporter_qwidget()
        _log(f"reporter widget valid={widget is not None}")

        def close_menu() -> None:
            for menu in window.terminal.findChildren(QMenu):
                if menu.isVisible():
                    menu.close()
                    _log("context menu shown and closed")

        QTimer.singleShot(400, close_menu)
        try:
            window.terminal._show_context_menu(QPoint(10, 10))
            _log("context menu ok")
        except Exception:
            _log("context menu FAILED\n" + traceback.format_exc())

    def finish() -> None:
        check_history_menu()
        check_context_menu()
        try:
            text = cmds.cmdScrollFieldReporter(
                window.terminal.reporter, query=True, text=True
            )
            tail = "\n".join(str(text).splitlines()[-8:])
            _log("REPORTER TAIL >>>\n" + tail + "\n<<< END")
        except Exception:
            _log("reporter query failed\n" + traceback.format_exc())
        try:
            QGuiApplication.primaryScreen().grabWindow(0).save(str(PNG))
            _log("screenshot saved")
        except Exception:
            _log("screenshot failed\n" + traceback.format_exc())

        def make_window():
            from maya_code_editor.main import MayaCodeEditorWindow

            w = MayaCodeEditorWindow()
            w.setWindowFlags(w.windowFlags() | Qt.WindowType.Window)
            w.resize(900, 600)
            w.show()
            w.load_page()
            return w

        from PySide6.QtCore import Qt

        _verify_restore(make_window, True, lambda: QTimer.singleShot(500, quit_maya))

    runner = StepRunner(page, run_js, finish)
    window._smoke_runner = runner  # keep alive
    QTimer.singleShot(8000, runner.start)
    QTimer.singleShot(120000, quit_maya)  # safety net


def run_standalone() -> int:
    """Drive the editor in a plain QApplication (no Maya)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    _prepare_workspace()
    LOG.write_text("", encoding="utf-8")
    _log("standalone")

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from maya_code_editor.main import MayaCodeEditorWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MayaCodeEditorWindow()
    window.resize(1100, 720)
    window.show()
    window.load_page()
    _log(
        f"window ok; terminal={type(window.terminal).__name__} workspace={window.workspace_root}"
    )

    _WINDOW["ref"] = window
    page = window.web_view.page()
    run_js = _make_run_js(page, legacy_signature=False)

    def finish() -> None:
        QGuiApplication.primaryScreen().grabWindow(window.winId()).save(str(PNG))
        _log("screenshot saved")
        _log("TERMINAL >>>\n" + window.terminal.toPlainText().strip() + "\n<<< END")
        window.terminal.cleanup()

        def make_window():
            w = MayaCodeEditorWindow()
            w.resize(900, 600)
            w.show()
            w.load_page()
            return w

        def done() -> None:
            _WINDOW["restore_ref"].terminal.cleanup()
            QTimer.singleShot(200, app.quit)

        _verify_restore(make_window, False, done)

    runner = StepRunner(page, run_js, finish)
    QTimer.singleShot(3000, runner.start)
    QTimer.singleShot(90000, app.quit)
    code = app.exec()
    print(LOG.read_text(encoding="utf-8"))
    return code


def launch_maya(version: str) -> int:
    """Launch Maya with a startup MEL that execs this file, then print the log.

    Args:
        version: Maya version folder name, e.g. ``"2025"``.

    Returns:
        Maya's exit code.
    """
    maya_exe = Path(rf"C:\Program Files\Autodesk\Maya{version}\bin\maya.exe")
    if not maya_exe.exists():
        print(f"Maya not found: {maya_exe}")
        return 1

    this_file = Path(__file__).resolve().as_posix()
    # exec() does not define __file__, so pass it explicitly in the globals.
    py = (
        "import sys; sys.argv=['maya_smoke', '--in-maya']; p=r'%s'; "
        "exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), "
        "{'__file__': p, '__name__': '__main__'})" % this_file
    )
    mel = 'evalDeferred -lowestPriority "python(\\"%s\\")";\n' % py
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mel", delete=False, encoding="utf-8"
    ) as f:
        f.write(mel)
        mel_path = f.name

    env = dict(os.environ)
    env[ENV_VAR] = str(WORKSPACE)
    env[ENV_CONFIG] = str(CONFIG_DIR)
    print(f"launching {maya_exe} ...")
    proc = subprocess.run([str(maya_exe), "-script", mel_path], timeout=300, env=env)
    print(f"maya exited with {proc.returncode}")
    if LOG.exists():
        print("--- LOG ---")
        print(LOG.read_text(encoding="utf-8"))
    print(f"screenshot: {PNG} (exists={PNG.exists()})")
    return proc.returncode


def main() -> int:
    """Entry point for the launcher, the standalone runner and the in-Maya driver."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--maya", default="2025", help="Maya version folder, e.g. 2025")
    parser.add_argument("--standalone", action="store_true", help="run without Maya")
    parser.add_argument("--in-maya", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.in_maya:
        run_inside_maya()
        return 0
    if args.standalone:
        return run_standalone()
    return launch_maya(args.maya)


if __name__ == "__main__":
    exit_code = main()
    if exit_code:  # avoid raising SystemExit(0) inside Maya
        sys.exit(exit_code)

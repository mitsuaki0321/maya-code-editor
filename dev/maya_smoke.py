"""Automated smoke test inside a real Maya GUI session.

Run from a normal shell::

    python dev/maya_smoke.py [--maya 2025]

It launches ``maya.exe`` with a startup MEL script that opens the editor,
presses Run, captures the reporter text and a screenshot, then quits Maya.
Results land in ``dev/out/maya_smoke.log`` and ``dev/out/maya_smoke.png``.

The same file is executed inside Maya (via ``exec``) to drive the test.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "dev" / "out"
LOG = OUT_DIR / "maya_smoke.log"
PNG = OUT_DIR / "maya_smoke.png"

STATUS_JS = (
    "document.getElementById('status').textContent"
    " + ' | monaco=' + (typeof monaco !== 'undefined')"
)


def _log(msg: str) -> None:
    """Append one line to the log file."""
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def run_inside_maya() -> None:
    """Drive the editor inside Maya and write log / screenshot."""
    import maya.cmds as cmds  # type: ignore
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG.write_text("", encoding="utf-8")
    _log(f"maya {cmds.about(version=True)}")

    def quit_maya() -> None:
        cmds.quit(force=True)

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    try:
        import maya_code_editor

        window = maya_code_editor.show_ui()
        _log(f"show_ui ok; terminal={type(window.terminal).__name__}")
    except Exception:
        _log("show_ui FAILED\n" + traceback.format_exc())
        QTimer.singleShot(1000, quit_maya)
        return

    page = window.web_view.page()
    page.loadFinished.connect(lambda ok: _log(f"loadFinished ok={ok}"))

    def query_status() -> None:
        page.runJavaScript(STATUS_JS, 0, lambda v: _log(f"STATUS: {v}"))

    def trigger_run() -> None:
        page.runJavaScript("document.getElementById('run-button').click();")
        _log("run triggered")

    def finish() -> None:
        query_status()
        try:
            text = cmds.cmdScrollFieldReporter(
                window.terminal.reporter, query=True, text=True
            )
            tail = "\n".join(str(text).splitlines()[-12:])
            _log("REPORTER TAIL >>>\n" + tail + "\n<<< END")
        except Exception:
            _log("reporter query failed\n" + traceback.format_exc())
        try:
            QGuiApplication.primaryScreen().grabWindow(0).save(str(PNG))
            _log("screenshot saved")
        except Exception:
            _log("screenshot failed\n" + traceback.format_exc())
        QTimer.singleShot(1500, quit_maya)

    QTimer.singleShot(8000, query_status)
    QTimer.singleShot(9000, trigger_run)
    QTimer.singleShot(12000, finish)
    QTimer.singleShot(60000, quit_maya)  # safety net


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

    print(f"launching {maya_exe} ...")
    proc = subprocess.run([str(maya_exe), "-script", mel_path], timeout=300)
    print(f"maya exited with {proc.returncode}")
    if LOG.exists():
        print("--- LOG ---")
        print(LOG.read_text(encoding="utf-8"))
    print(f"screenshot: {PNG} (exists={PNG.exists()})")
    return proc.returncode


def main() -> int:
    """Entry point for both the outer launcher and the in-Maya driver."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--maya", default="2025", help="Maya version folder, e.g. 2025")
    parser.add_argument("--in-maya", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.in_maya:
        run_inside_maya()
        return 0
    return launch_maya(args.maya)


if __name__ == "__main__":
    exit_code = main()
    if exit_code:  # avoid raising SystemExit(0) inside Maya
        sys.exit(exit_code)

/**
 * Startup: connect the bridge, load Monaco, wire Run / Ctrl+Enter.
 */
(function () {
  const statusEl = document.getElementById("status");
  const runButton = document.getElementById("run-button");

  const WELCOME = [
    "# Maya Code Editor",
    "# Ctrl+Enter or the Run button executes this buffer in Maya.",
    "",
    "import sys",
    "",
    'print("hello from monaco", sys.version.split()[0])',
    "",
  ].join("\n");

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function loadMonaco() {
    return new Promise(function (resolve, reject) {
      require.config({
        paths: { vs: new URL("vendor/monaco/vs", window.location.href).href },
      });
      require(["vs/editor/editor.main"], function () {
        resolve(window.monaco);
      }, reject);
    });
  }

  function createEditor(monaco) {
    return monaco.editor.create(document.getElementById("editor"), {
      value: WELCOME,
      language: "python",
      theme: "vs-dark",
      automaticLayout: true,
      fontSize: 13,
      tabSize: 4,
      insertSpaces: true,
      minimap: { enabled: false },
      mouseWheelZoom: true,
      scrollBeyondLastLine: false,
      renderLineHighlight: "all",
    });
  }

  async function main() {
    let bridge;
    try {
      bridge = await MayaBridge.connect();
    } catch (err) {
      setStatus("bridge unavailable: " + err.message);
      return;
    }

    const info = await bridge.ping();
    setStatus(
      (info.maya ? "Maya " + info.maya : "standalone") +
        " / Python " +
        info.python
    );

    let monaco;
    try {
      monaco = await loadMonaco();
    } catch (err) {
      setStatus("failed to load Monaco: " + (err && err.message));
      return;
    }
    const editor = createEditor(monaco);

    async function runAll() {
      const ok = await bridge.runCode(editor.getValue());
      if (!ok) {
        setStatus("execution failed (see terminal)");
      }
    }

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, runAll);
    runButton.addEventListener("click", runAll);
    editor.focus();
    bridge.log("monaco ready");
  }

  main();
})();

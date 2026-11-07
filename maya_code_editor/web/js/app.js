/**
 * Startup: connect the bridge, load Monaco, build the explorer and tabs,
 * wire the toolbar and keyboard shortcuts.
 *
 * `window.app` exposes the live objects for debugging and for the
 * automated smoke test (dev/maya_smoke.py).
 */
(function () {
  const statusEl = document.getElementById("status");
  const emptyState = document.getElementById("empty-state");

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
      model: null,
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

  function setupGutter() {
    const gutter = document.getElementById("gutter");
    const sidebar = document.getElementById("sidebar");
    gutter.addEventListener("mousedown", function (e) {
      e.preventDefault();
      gutter.classList.add("dragging");
      const startX = e.clientX;
      const startWidth = sidebar.getBoundingClientRect().width;
      function onMove(ev) {
        sidebar.style.width = Math.max(120, startWidth + ev.clientX - startX) + "px";
      }
      function onUp() {
        gutter.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
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
    const envLabel = (info.maya ? "Maya " + info.maya : "standalone") + " / Python " + info.python;
    setStatus(envLabel);

    let monaco;
    try {
      monaco = await loadMonaco();
    } catch (err) {
      setStatus("failed to load Monaco: " + (err && err.message));
      return;
    }
    const editor = createEditor(monaco);
    const workspace = await bridge.getWorkspace();
    document.getElementById("workspace-name").textContent = workspace.name;
    document.getElementById("workspace-name").title = workspace.root;

    let tree;
    const tabs = new Tabs(document.getElementById("tab-bar"), monaco, editor, bridge.files, {
      onChange: function () {
        tree.setOpenPaths(tabs.openPaths());
      },
      onActivate: function (tab) {
        emptyState.hidden = !!tab;
        if (tab && tab.path) tree.select(tab.path);
        setStatus(tab && tab.path ? tab.path : envLabel);
      },
    });
    tabs.workspaceRoot = workspace.root;

    tree = new FileTree(document.getElementById("file-tree"), bridge.files, {
      onOpen: function (path) {
        tabs.openFile(path).catch(function (err) { Dialogs.error(err.message); });
      },
      onRenamed: function (oldPath, newPath, isDir) { tabs.onPathRenamed(oldPath, newPath, isDir); },
      onDeleted: function (path, isDir) { tabs.onPathDeleted(path, isDir); },
    });
    await tree.load(workspace.root);

    // -- actions -------------------------------------------------------

    /** Run the selection if there is one, otherwise the whole buffer (Script Editor behaviour). */
    async function runActive() {
      const tab = tabs.activeTab;
      if (!tab) return;
      const selection = editor.getSelection();
      const code = selection && !selection.isEmpty() ? tab.model.getValueInRange(selection) : tab.model.getValue();
      const ok = await bridge.runCode(code);
      if (!ok) setStatus("execution failed (see terminal)");
    }

    async function toggleTerminal() {
      const visible = await bridge.toggleTerminal();
      document.getElementById("terminal-button").classList.toggle("off", !visible);
    }

    async function saveActive() {
      if (await tabs.save()) await tree.refresh();
    }

    document.getElementById("run-button").addEventListener("click", runActive);
    document.getElementById("save-button").addEventListener("click", saveActive);
    document.getElementById("new-button").addEventListener("click", function () { tabs.newUntitled(); });
    document.getElementById("terminal-button").addEventListener("click", toggleTerminal);
    document.getElementById("refresh-button").addEventListener("click", function () { tree.refresh(); });

    const K = monaco.KeyMod, C = monaco.KeyCode;
    editor.addCommand(K.CtrlCmd | C.Enter, runActive);
    editor.addCommand(K.CtrlCmd | C.KeyS, saveActive);
    editor.addCommand(K.CtrlCmd | C.KeyN, function () { tabs.newUntitled(); });
    editor.addCommand(K.CtrlCmd | C.KeyW, function () { tabs.close(); });

    // Same shortcuts when focus is outside the editor (explorer, tab bar).
    document.addEventListener("keydown", function (e) {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      if (e.target.closest("#editor") || e.target.closest("#dialog")) return;
      const key = e.key.toLowerCase();
      if (key === "s") { e.preventDefault(); saveActive(); }
      else if (key === "n") { e.preventDefault(); tabs.newUntitled(); }
      else if (key === "w") { e.preventDefault(); tabs.close(); }
      else if (key === "enter") { e.preventDefault(); runActive(); }
    });

    setupGutter();
    emptyState.hidden = false;
    window.app = { bridge: bridge, monaco: monaco, editor: editor, tabs: tabs, tree: tree, workspace: workspace, runActive: runActive, saveActive: saveActive, toggleTerminal: toggleTerminal };
    bridge.log("monaco ready");
  }

  main();
})();

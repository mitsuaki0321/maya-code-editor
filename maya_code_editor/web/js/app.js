/**
 * Startup: connect the bridge, load Monaco, build the explorer and tabs,
 * wire the toolbar and keyboard shortcuts, restore and persist the session.
 *
 * `window.app` exposes the live objects for debugging and for the
 * automated smoke test (dev/maya_smoke.py).
 */
(function () {
  const statusEl = document.getElementById("status");
  const emptyState = document.getElementById("empty-state");
  const sidebar = document.getElementById("sidebar");

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

  // Shell palettes for Monaco's built-in themes (custom themes ship their own `chrome`).
  const DARK_CHROME = {
    "bg": "#1e1e1e", "panel-bg": "#252526", "toolbar-bg": "#2d2d2d", "fg": "#cccccc", "muted": "#8a8a8a",
    "border": "#3c3c3c", "hover": "#2a2d2e", "selected": "#37373d", "accent": "#0e639c", "accent-hover": "#1177bb",
    "danger": "#c74e39", "tab-active-bg": "#1e1e1e", "tab-active-top": "#0e639c", "menu-bg": "#303031",
    "dialog-bg": "#2b2b2c", "input-bg": "#1b1b1c", "input-border": "#3c3c3c",
  };
  const LIGHT_CHROME = {
    "bg": "#fffffe", "panel-bg": "#f3f3f3", "toolbar-bg": "#f3f3f3", "fg": "#333333", "muted": "#717171",
    "border": "#e5e5e5", "hover": "#e8e8e8", "selected": "#dcdcdc", "accent": "#007acc", "accent-hover": "#0062a3",
    "danger": "#c74e39", "tab-active-bg": "#fffffe", "tab-active-top": "#007acc", "menu-bg": "#f3f3f3",
    "dialog-bg": "#f3f3f3", "input-bg": "#ffffff", "input-border": "#cecece",
  };
  const BUILTIN_THEMES = ["vs", "vs-dark", "hc-black", "hc-light"];

  /**
   * Register the selected theme with Monaco and paint the shell to match.
   * @returns {string} the Monaco theme name actually in use
   */
  function applyTheme(monaco, name) {
    const custom = window.MCE_THEMES || {};
    if (!custom[name] && !BUILTIN_THEMES.includes(name)) name = custom["dark-modern"] ? "dark-modern" : "vs-dark";
    let chrome;
    if (custom[name]) {
      const t = custom[name];
      monaco.editor.defineTheme(name, { base: t.base, inherit: t.inherit !== false, rules: t.rules, colors: t.colors });
      chrome = Object.assign({}, t.base === "vs" ? LIGHT_CHROME : DARK_CHROME, t.chrome);
    } else {
      chrome = (name === "vs" || name === "hc-light") ? LIGHT_CHROME : DARK_CHROME;
    }
    const root = document.documentElement.style;
    Object.keys(chrome).forEach(function (k) { root.setProperty("--" + k, chrome[k]); });
    return name;
  }

  function createEditor(monaco, editorSettings) {
    const s = editorSettings || {};
    return monaco.editor.create(document.getElementById("editor"), {
      model: null,
      theme: applyTheme(monaco, s.theme || "dark-modern"),
      automaticLayout: true,
      fontSize: s.fontSize || 13,
      tabSize: s.tabSize || 4,
      wordWrap: s.wordWrap || "off",
      insertSpaces: true,
      minimap: { enabled: !!s.minimap },
      mouseWheelZoom: true,
      scrollBeyondLastLine: false,
      renderLineHighlight: "all",
    });
  }

  function setupGutter(onResized) {
    const gutter = document.getElementById("gutter");
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
        onResized();
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
    const settings = await bridge.getSettings();
    const session = await bridge.getSession();
    const editor = createEditor(monaco, settings.editor);
    Completion.register(monaco, bridge);
    const workspace = await bridge.getWorkspace();
    document.getElementById("workspace-name").textContent = workspace.name;
    document.getElementById("workspace-name").title = workspace.root;

    // -- session persistence ------------------------------------------

    let restoring = true;
    let saveTimer = null;

    function sessionState() {
      const state = tabs.sessionState();
      state.layout = { sidebarWidth: Math.round(sidebar.getBoundingClientRect().width) };
      return state;
    }

    function saveSessionNow() {
      if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
      bridge.saveSession(sessionState());
    }

    function scheduleSessionSave() {
      if (restoring) return;
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(saveSessionNow, 500);
    }

    // -- tabs and tree -------------------------------------------------

    let tree;
    const tabs = new Tabs(document.getElementById("tab-bar"), monaco, editor, bridge.files, {
      onChange: function () {
        tree.setOpenPaths(tabs.openPaths());
        scheduleSessionSave();
      },
      onActivate: function (tab) {
        emptyState.hidden = !!tab;
        if (tab && tab.path) tree.select(tab.path);
        setStatus(tab && tab.path ? tab.path : envLabel);
        scheduleSessionSave();
      },
      onContentChange: function (tab) {
        if (!tab.path) scheduleSessionSave(); // Untitled drafts are persisted as text
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
      Completion.invalidate(); // the live namespace may have changed
      if (!ok) setStatus("execution failed (see terminal)");
    }

    async function saveActive() {
      if (await tabs.save()) await tree.refresh();
    }

    function setTerminalButton(visible) {
      document.getElementById("terminal-button").classList.toggle("off", !visible);
    }

    async function toggleTerminal() {
      const visible = await bridge.toggleTerminal();
      setTerminalButton(visible);
      scheduleSessionSave();
    }

    function openSettings() {
      bridge.openSettingsFile().catch(function (err) { Dialogs.error(err.message); });
    }

    async function saveAll() {
      const n = await tabs.saveAll();
      if (n > 0) await tree.refresh();
      setStatus(n === 1 ? "saved 1 file" : "saved " + n + " files");
      return n;
    }

    function toggleWordWrap() {
      const next = editor.getOption(monaco.editor.EditorOption.wordWrap) === "off" ? "on" : "off";
      editor.updateOptions({ wordWrap: next });
      settings.editor.wordWrap = next;
      bridge.setSetting("editor", "wordWrap", next);
      setStatus("word wrap " + next);
      return next;
    }

    // -- external changes: poll open files every 2 s and on focus --------

    let checking = false;
    async function checkExternalChanges() {
      if (checking) return [];
      checking = true;
      try {
        const events = await tabs.checkExternalChanges();
        for (const e of events) {
          const name = e.path.slice(e.path.lastIndexOf("/") + 1);
          if (e.action === "reloaded") setStatus("reloaded " + name + " (changed on disk)");
          else if (e.action === "deleted") setStatus(name + " was deleted on disk; saving will recreate it");
        }
        return events;
      } finally {
        checking = false;
      }
    }
    setInterval(checkExternalChanges, 2000);
    window.addEventListener("focus", function () {
      checkExternalChanges();
      tree.refresh();
    });

    document.getElementById("run-button").addEventListener("click", runActive);
    document.getElementById("save-button").addEventListener("click", saveActive);
    document.getElementById("new-button").addEventListener("click", function () { tabs.newUntitled(); });
    document.getElementById("terminal-button").addEventListener("click", toggleTerminal);
    document.getElementById("settings-button").addEventListener("click", openSettings);
    document.getElementById("refresh-button").addEventListener("click", function () { tree.refresh(); });

    // Registered as actions so they also appear in the command palette (F1).
    const K = monaco.KeyMod, C = monaco.KeyCode;
    const ACTIONS = [
      { id: "mce.run", label: "Maya: Run Selection or File", keybindings: [K.CtrlCmd | C.Enter], run: runActive },
      { id: "mce.save", label: "Maya: Save File", keybindings: [K.CtrlCmd | C.KeyS], run: saveActive },
      { id: "mce.newFile", label: "Maya: New Untitled File", keybindings: [K.CtrlCmd | C.KeyN], run: function () { tabs.newUntitled(); } },
      { id: "mce.closeTab", label: "Maya: Close Tab", keybindings: [K.CtrlCmd | C.KeyW], run: function () { tabs.close(); } },
      { id: "mce.toggleTerminal", label: "Maya: Toggle Terminal", run: toggleTerminal },
      { id: "mce.saveAll", label: "Maya: Save All", keybindings: [K.chord(K.CtrlCmd | C.KeyK, C.KeyS)], run: saveAll },
      { id: "mce.toggleWordWrap", label: "Maya: Toggle Word Wrap", keybindings: [K.Alt | C.KeyZ], run: toggleWordWrap },
    ];
    ACTIONS.forEach(function (a) { editor.addAction(a); });

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

    // -- restore -------------------------------------------------------

    const layout = (session && session.layout) || {};
    if (layout.sidebarWidth > 0) sidebar.style.width = Math.max(120, layout.sidebarWidth) + "px";
    setTerminalButton(layout.terminalVisible !== false);
    setupGutter(scheduleSessionSave);
    const restored = await tabs.restoreSession(session);
    restoring = false;
    emptyState.hidden = !!tabs.activeTab;

    window.app = {
      bridge: bridge, monaco: monaco, editor: editor, tabs: tabs, tree: tree, workspace: workspace, settings: settings,
      runActive: runActive, saveActive: saveActive, saveAll: saveAll, toggleWordWrap: toggleWordWrap, toggleTerminal: toggleTerminal,
      checkExternalChanges: checkExternalChanges, saveSessionNow: saveSessionNow, restoredTabs: restored, completion: Completion,
    };
    bridge.log("monaco ready (restored " + restored + " tabs)");
  }

  main();
})();

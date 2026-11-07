/**
 * Tab bar over a single Monaco editor instance.
 *
 * Each tab owns a Monaco model plus its saved view state. Dirty tracking
 * compares the model's alternative version id against the id recorded at
 * load/save time, so undoing back to the saved state clears the marker.
 */
class Tabs {
  /**
   * @param {HTMLElement} container  the #tab-bar element
   * @param {Object} monaco
   * @param {Object} editor  monaco.editor.IStandaloneCodeEditor
   * @param {Object} files   MayaBridge.files
   * @param {Object} handlers {onChange(), onActivate(tab)}
   */
  constructor(container, monaco, editor, files, handlers) {
    this.container = container;
    this.monaco = monaco;
    this.editor = editor;
    this.files = files;
    this.handlers = handlers;
    this.tabs = [];
    this.active = null;
    this.workspaceRoot = null;
    this._untitledCounter = 0;
    this._nextId = 1;
    this._contentListener = null;
  }

  // -- queries ---------------------------------------------------------

  get activeTab() {
    return this.active;
  }

  openPaths() {
    return this.tabs.filter((t) => t.path).map((t) => t.path);
  }

  isDirty(tab) {
    return tab.model.getAlternativeVersionId() !== tab.savedVersionId;
  }

  findByPath(path) {
    return this.tabs.find((t) => t.path === path) || null;
  }

  // -- open / new ------------------------------------------------------

  /** Open `path` in a tab (reusing an existing one) and activate it. */
  async openFile(path) {
    const existing = this.findByPath(path);
    if (existing) {
      this.activate(existing);
      return existing;
    }
    const content = await this.files.read(path);
    const tab = this._createTab(path, content);
    this.activate(tab);
    return tab;
  }

  /** Create an empty Untitled tab and activate it. */
  newUntitled() {
    this._untitledCounter += 1;
    const tab = this._createTab(null, "");
    tab.title = "Untitled-" + this._untitledCounter;
    tab.el.querySelector(".tab-title").textContent = tab.title;
    this.activate(tab);
    return tab;
  }

  _createTab(path, content) {
    const language = path ? this._languageFor(path) : "python";
    const model = this.monaco.editor.createModel(content, language);
    const tab = {
      id: this._nextId++,
      path: path,
      title: path ? this._nameOf(path) : "",
      model: model,
      viewState: null,
      savedVersionId: model.getAlternativeVersionId(),
      el: null,
    };
    tab.el = this._makeTabElement(tab);
    this.container.appendChild(tab.el);
    this.tabs.push(tab);
    model.onDidChangeContent(() => this._updateDirty(tab));
    this.handlers.onChange();
    return tab;
  }

  _makeTabElement(tab) {
    const el = document.createElement("div");
    el.className = "tab";
    el.dataset.id = String(tab.id);
    const title = document.createElement("span");
    title.className = "tab-title";
    title.textContent = tab.title;
    const close = document.createElement("span");
    close.className = "tab-close";
    close.title = "Close (Ctrl+W)";
    el.append(title, close);
    el.addEventListener("click", (e) => {
      if (e.target === close) return;
      this.activate(tab);
    });
    el.addEventListener("auxclick", (e) => {
      if (e.button === 1) this.close(tab);
    });
    close.addEventListener("click", (e) => {
      e.stopPropagation();
      this.close(tab);
    });
    return el;
  }

  // -- activation ------------------------------------------------------

  activate(tab) {
    if (this.active === tab) {
      this.editor.focus();
      return;
    }
    if (this.active) {
      this.active.viewState = this.editor.saveViewState();
      this.active.el.classList.remove("active");
    }
    this.active = tab;
    this.editor.setModel(tab.model);
    if (tab.viewState) this.editor.restoreViewState(tab.viewState);
    tab.el.classList.add("active");
    tab.el.scrollIntoView({ block: "nearest", inline: "nearest" });
    this.editor.focus();
    this.handlers.onActivate(tab);
  }

  // -- save ------------------------------------------------------------

  /**
   * Save `tab` (default: active). Untitled tabs prompt for a name unless
   * `nameOverride` is given; the file is created under the workspace root.
   * @returns {Promise<boolean>} true if saved
   */
  async save(tab, nameOverride) {
    tab = tab || this.active;
    if (!tab) return false;
    if (!tab.path) {
      const name = nameOverride || (await Dialogs.prompt("Save as (in " + this._nameOf(this.workspaceRoot) + ")", "untitled.py", "stem"));
      if (!name) return false;
      const path = this.workspaceRoot + "/" + name;
      try {
        await this.files.createFile(this.workspaceRoot, name);
      } catch (err) {
        await Dialogs.error(err.message);
        return false;
      }
      tab.path = path;
      tab.title = name;
      tab.el.querySelector(".tab-title").textContent = name;
      this.monaco.editor.setModelLanguage(tab.model, this._languageFor(path));
    }
    try {
      await this.files.write(tab.path, tab.model.getValue());
    } catch (err) {
      await Dialogs.error(err.message);
      return false;
    }
    tab.savedVersionId = tab.model.getAlternativeVersionId();
    this._updateDirty(tab);
    this.handlers.onChange();
    return true;
  }

  async saveAll() {
    for (const tab of this.tabs.slice()) {
      if (this.isDirty(tab) && !(await this.save(tab))) return false;
    }
    return true;
  }

  // -- close -----------------------------------------------------------

  /**
   * Close `tab` (default: active), asking about unsaved changes.
   * @returns {Promise<boolean>} true if the tab was closed
   */
  async close(tab, force) {
    tab = tab || this.active;
    if (!tab) return false;
    if (!force && this.isDirty(tab)) {
      const choice = await Dialogs.confirmClose(tab.title);
      if (choice === null) return false;
      if (choice === "save" && !(await this.save(tab))) return false;
    }
    const index = this.tabs.indexOf(tab);
    this.tabs.splice(index, 1);
    tab.el.remove();
    if (this.active === tab) {
      this.active = null;
      const next = this.tabs[index] || this.tabs[index - 1] || null;
      if (next) {
        this.activate(next);
      } else {
        this.editor.setModel(null);
        this.handlers.onActivate(null);
      }
    }
    tab.model.dispose();
    this.handlers.onChange();
    return true;
  }

  // -- external file changes -------------------------------------------

  /** Update tabs after a rename in the explorer. */
  onPathRenamed(oldPath, newPath, isDir) {
    for (const tab of this.tabs) {
      if (!tab.path) continue;
      if (tab.path === oldPath || (isDir && tab.path.startsWith(oldPath + "/"))) {
        tab.path = newPath + tab.path.slice(oldPath.length);
        tab.title = this._nameOf(tab.path);
        tab.el.querySelector(".tab-title").textContent = tab.title;
        this.monaco.editor.setModelLanguage(tab.model, this._languageFor(tab.path));
      }
    }
    this.handlers.onChange();
  }

  /** Close tabs whose file was deleted in the explorer. */
  async onPathDeleted(path, isDir) {
    for (const tab of this.tabs.slice()) {
      if (!tab.path) continue;
      if (tab.path === path || (isDir && tab.path.startsWith(path + "/"))) {
        await this.close(tab, true);
      }
    }
  }

  // -- helpers ---------------------------------------------------------

  _updateDirty(tab) {
    tab.el.classList.toggle("dirty", this.isDirty(tab));
  }

  _languageFor(path) {
    const ext = path.slice(path.lastIndexOf(".") + 1).toLowerCase();
    return { py: "python", json: "json", md: "markdown", html: "html", css: "css", js: "javascript" }[ext] || "plaintext";
  }

  _nameOf(path) {
    return path.slice(path.lastIndexOf("/") + 1);
  }
}

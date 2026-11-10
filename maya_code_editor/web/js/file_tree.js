/**
 * Explorer tree for the workspace folder.
 *
 * Folders load lazily on first expand. Expanded folders and the selection
 * survive refresh(). Selection: click selects one, Ctrl+click toggles,
 * Shift+click extends over the visible rows. Middle-button drag moves the
 * selected entries into the folder under the cursor (or the root when
 * dropped on empty space). The right-click menu offers New File / New
 * Folder / Rename / Delete / Reveal in Explorer / Refresh; file operations
 * that affect open tabs are reported through `handlers`.
 */
class FileTree {
  /**
   * @param {HTMLElement} container
   * @param {Object} files  MayaBridge.files
   * @param {Object} handlers {onOpen(path), onRenamed(oldPath, newPath, isDir), onDeleted(path, isDir)}
   */
  constructor(container, files, handlers) {
    this.container = container;
    this.files = files;
    this.handlers = handlers;
    this.root = null;
    this.expanded = new Set();
    this.selection = [];   // ordered paths
    this.anchorPath = null; // for Shift+click ranges
    this.openPaths = new Set();
    this.menu = document.getElementById("context-menu");
    this.drag = null;

    this.container.addEventListener("contextmenu", (e) => this._onContextMenu(e));
    this.container.addEventListener("mousedown", (e) => this._onMouseDown(e));
    this.container.addEventListener("auxclick", (e) => { if (e.button === 1) e.preventDefault(); });
    document.addEventListener("mousemove", (e) => this._onDragMove(e));
    document.addEventListener("mouseup", (e) => this._onDragEnd(e));
    document.addEventListener("mousedown", (e) => {
      if (!this.menu.contains(e.target)) this._hideMenu();
    });
    window.addEventListener("blur", () => { this._hideMenu(); this._cancelDrag(); });
  }

  /** Load the tree for `rootPath`. */
  async load(rootPath) {
    this.root = rootPath;
    this.expanded.add(rootPath);
    await this.refresh();
  }

  /** Re-read every expanded folder and redraw. */
  async refresh() {
    const fragment = document.createDocumentFragment();
    await this._renderChildren(this.root, 0, fragment);
    this.container.innerHTML = "";
    this.container.appendChild(fragment);
    this._applySelectionClasses();
  }

  /** Mark which paths are open in tabs (for subtle highlighting). */
  setOpenPaths(paths) {
    this.openPaths = new Set(paths);
    this.container.querySelectorAll(".tree-node.file").forEach((node) => {
      node.classList.toggle("open-in-tab", this.openPaths.has(node.dataset.path));
    });
  }

  // -- selection -------------------------------------------------------

  /** Select exactly `path` (used when a tab is activated). */
  select(path) {
    this.setSelection(path ? [path] : []);
    this.anchorPath = path;
  }

  setSelection(paths) {
    this.selection = paths.slice();
    this._applySelectionClasses();
  }

  _applySelectionClasses() {
    const set = new Set(this.selection);
    this.container.querySelectorAll(".tree-node").forEach((node) => {
      node.classList.toggle("selected", set.has(node.dataset.path));
    });
  }

  _visibleNodes() {
    return Array.from(this.container.querySelectorAll(".tree-node")).filter((n) => n.offsetParent !== null);
  }

  _onNodeClick(event, entry) {
    if (event.shiftKey && this.anchorPath) {
      const nodes = this._visibleNodes().map((n) => n.dataset.path);
      const a = nodes.indexOf(this.anchorPath);
      const b = nodes.indexOf(entry.path);
      if (a >= 0 && b >= 0) {
        this.setSelection(nodes.slice(Math.min(a, b), Math.max(a, b) + 1));
        return;
      }
    }
    if (event.ctrlKey || event.metaKey) {
      const idx = this.selection.indexOf(entry.path);
      if (idx >= 0) this.selection.splice(idx, 1);
      else this.selection.push(entry.path);
      this.anchorPath = entry.path;
      this._applySelectionClasses();
      return;
    }
    this.select(entry.path);
    if (entry.is_dir) {
      this._toggleFolder(entry.path);
    } else {
      this.handlers.onOpen(entry.path);
    }
  }

  // -- rendering -------------------------------------------------------

  async _renderChildren(dirPath, depth, parentEl) {
    let entries;
    try {
      entries = await this.files.listDir(dirPath);
    } catch (err) {
      Dialogs.error(err.message);
      return;
    }
    for (const entry of entries) {
      const node = this._makeNode(entry, depth);
      parentEl.appendChild(node);
      if (entry.is_dir) {
        const childrenEl = document.createElement("div");
        childrenEl.className = "tree-children";
        parentEl.appendChild(childrenEl);
        if (this.expanded.has(entry.path)) {
          node.classList.add("expanded");
          await this._renderChildren(entry.path, depth + 1, childrenEl);
        }
      }
    }
  }

  _makeNode(entry, depth) {
    const node = document.createElement("div");
    node.className = "tree-node " + (entry.is_dir ? "folder" : "file");
    node.dataset.path = entry.path;
    node.dataset.isDir = entry.is_dir ? "1" : "0";
    node.dataset.depth = String(depth);
    node.style.paddingLeft = 8 + depth * 14 + "px";
    node.title = entry.path;
    if (!entry.is_dir && this.openPaths.has(entry.path)) node.classList.add("open-in-tab");

    const arrow = document.createElement("span");
    arrow.className = "tree-arrow";
    arrow.textContent = "▶";
    const icon = document.createElement("span");
    icon.className = "tree-icon";
    icon.textContent = entry.is_dir ? "■" : "≡";
    const label = document.createElement("span");
    label.className = "tree-label";
    label.textContent = entry.name;
    node.append(arrow, icon, label);

    if (!entry.is_dir && this.handlers.onRun) {
      // Hover button: run the whole file without opening it.
      const run = document.createElement("button");
      run.className = "tree-run";
      run.title = "Run file";
      run.setAttribute("aria-label", "Run " + entry.name);
      run.innerHTML = '<svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z" fill="currentColor"/></svg>';
      run.addEventListener("click", (e) => {
        e.stopPropagation();
        this.handlers.onRun(entry.path);
      });
      node.appendChild(run);
    }

    node.addEventListener("click", (e) => this._onNodeClick(e, entry));
    return node;
  }

  _nodeFor(path) {
    return this.container.querySelector('.tree-node[data-path="' + CSS.escape(path) + '"]');
  }

  async _toggleFolder(path) {
    const node = this._nodeFor(path);
    if (!node) return;
    const childrenEl = node.nextElementSibling;
    if (this.expanded.has(path)) {
      this.expanded.delete(path);
      node.classList.remove("expanded");
      return;
    }
    this.expanded.add(path);
    node.classList.add("expanded");
    if (!childrenEl.hasChildNodes()) {
      await this._renderChildren(path, parseInt(node.dataset.depth, 10) + 1, childrenEl);
      this._applySelectionClasses();
    }
  }

  // -- middle-button drag ----------------------------------------------

  _onMouseDown(event) {
    if (event.button !== 1) return;
    const node = event.target.closest(".tree-node");
    if (!node) return;
    event.preventDefault(); // suppress Chromium autoscroll
    const path = node.dataset.path;
    if (!this.selection.includes(path)) this.select(path);
    this.drag = { startX: event.clientX, startY: event.clientY, active: false, paths: this.selection.slice(), target: null, ghost: null };
  }

  _onDragMove(event) {
    const d = this.drag;
    if (!d) return;
    if (!d.active) {
      if (Math.abs(event.clientX - d.startX) < 4 && Math.abs(event.clientY - d.startY) < 4) return;
      d.active = true;
      d.ghost = document.createElement("div");
      d.ghost.className = "drag-ghost";
      d.ghost.textContent = d.paths.length === 1 ? this._nameOf(d.paths[0]) : d.paths.length + " items";
      document.body.appendChild(d.ghost);
      document.body.classList.add("dragging-files");
    }
    d.ghost.style.left = event.clientX + 12 + "px";
    d.ghost.style.top = event.clientY + 12 + "px";

    const target = this._dropTargetAt(event);
    if (target !== d.target) {
      this._setDropHighlight(d.target, false);
      d.target = target;
      this._setDropHighlight(target, true);
    }
  }

  _dropTargetAt(event) {
    const el = document.elementFromPoint(event.clientX, event.clientY);
    if (!el || !this.container.contains(el)) return null;
    const node = el.closest(".tree-node");
    let dir;
    if (!node) dir = this.root;
    else if (node.dataset.isDir === "1") dir = node.dataset.path;
    else dir = this._parentOf(node.dataset.path);
    return this._canDropInto(dir) ? dir : null;
  }

  _canDropInto(dir) {
    for (const p of this.drag.paths) {
      if (this._parentOf(p) === dir) return false;          // already there
      if (dir === p || dir.startsWith(p + "/")) return false; // folder into itself
    }
    return true;
  }

  _setDropHighlight(dir, on) {
    if (!dir) return;
    if (dir === this.root) this.container.classList.toggle("drop-root", on);
    const node = this._nodeFor(dir);
    if (node) node.classList.toggle("drop-target", on);
  }

  async _onDragEnd(event) {
    const d = this.drag;
    if (!d) return;
    if (event.button !== 1 && event.button !== 0) return;
    const target = d.active ? d.target : null;
    this._cancelDrag();
    if (target) await this.moveSelectionTo(target, d.paths);
  }

  _cancelDrag() {
    const d = this.drag;
    if (!d) return;
    this._setDropHighlight(d.target, false);
    if (d.ghost) d.ghost.remove();
    document.body.classList.remove("dragging-files");
    this.drag = null;
  }

  /**
   * Move `paths` (default: the selection) into the folder `destDir`.
   * Open tabs follow the moved files; the destination is expanded.
   */
  async moveSelectionTo(destDir, paths) {
    paths = (paths || this.selection).slice();
    const moved = [];
    for (const path of paths) {
      try {
        const newPath = await this.files.move(path, destDir);
        const isDir = this._isDirPath(path);
        if (isDir) this._remapExpanded(path, newPath);
        this.handlers.onRenamed(path, newPath, isDir);
        moved.push(newPath);
      } catch (err) {
        await Dialogs.error(err.message);
      }
    }
    this.expanded.add(destDir);
    await this.refresh();
    this.setSelection(moved);
    return moved;
  }

  _isDirPath(path) {
    const node = this._nodeFor(path);
    return !!node && node.dataset.isDir === "1";
  }

  // -- context menu ----------------------------------------------------

  _onContextMenu(event) {
    event.preventDefault();
    this._cancelDrag();
    const node = event.target.closest(".tree-node");
    const target = node
      ? { path: node.dataset.path, isDir: node.dataset.isDir === "1", isRoot: false }
      : { path: this.root, isDir: true, isRoot: true };
    if (node && !this.selection.includes(target.path)) this.select(target.path);
    const multi = node && this.selection.length > 1;

    const dir = target.isDir ? target.path : this._parentOf(target.path);
    const items = [
      { label: "New File", action: () => this._createEntry(dir, false) },
      { label: "New Folder", action: () => this._createEntry(dir, true) },
    ];
    if (!target.isRoot) {
      items.push({ separator: true });
      if (!multi) items.push({ label: "Rename", action: () => this._rename(target) });
      items.push({
        label: multi ? "Delete " + this.selection.length + " items" : "Delete",
        danger: true,
        action: () => this._deleteSelection(),
      });
    }
    items.push({ separator: true });
    items.push({ label: "Reveal in Explorer", action: () => this._reveal(target.path) });
    items.push({ label: "Refresh", action: () => this.refresh() });
    this._showMenu(event.clientX, event.clientY, items);
  }

  _showMenu(x, y, items) {
    this.menu.innerHTML = "";
    for (const item of items) {
      if (item.separator) {
        const sep = document.createElement("div");
        sep.className = "menu-separator";
        this.menu.appendChild(sep);
        continue;
      }
      const el = document.createElement("div");
      el.className = "menu-item" + (item.danger ? " danger" : "");
      el.textContent = item.label;
      el.addEventListener("click", () => {
        this._hideMenu();
        item.action();
      });
      this.menu.appendChild(el);
    }
    this.menu.hidden = false;
    const rect = this.menu.getBoundingClientRect();
    this.menu.style.left = Math.min(x, window.innerWidth - rect.width - 4) + "px";
    this.menu.style.top = Math.min(y, window.innerHeight - rect.height - 4) + "px";
  }

  _hideMenu() {
    this.menu.hidden = true;
  }

  // -- operations ------------------------------------------------------

  async _createEntry(dir, isFolder) {
    const name = await Dialogs.prompt(isFolder ? "New folder name" : "New file name", isFolder ? "" : "untitled.py", "stem");
    if (!name) return;
    try {
      const path = isFolder ? await this.files.createFolder(dir, name) : await this.files.createFile(dir, name);
      this.expanded.add(dir);
      await this.refresh();
      this.select(path);
      if (!isFolder) this.handlers.onOpen(path);
    } catch (err) {
      Dialogs.error(err.message);
    }
  }

  async _rename(target) {
    const oldName = this._nameOf(target.path);
    const newName = await Dialogs.prompt("Rename", oldName, target.isDir ? undefined : "stem");
    if (!newName || newName === oldName) return;
    try {
      const newPath = await this.files.rename(target.path, newName);
      if (target.isDir) this._remapExpanded(target.path, newPath);
      this.handlers.onRenamed(target.path, newPath, target.isDir);
      await this.refresh();
      this.select(newPath);
    } catch (err) {
      Dialogs.error(err.message);
    }
  }

  async _deleteSelection() {
    const paths = this.selection.slice();
    if (!paths.length) return;
    const title = paths.length === 1 ? "Delete " + this._nameOf(paths[0]) + "?" : "Delete " + paths.length + " items?";
    const message = paths.length === 1 && !this._isDirPath(paths[0])
      ? "This file will be deleted permanently."
      : "Folders are deleted with their contents. This cannot be undone.";
    const ok = await Dialogs.confirm(title, message, "Delete", true);
    if (!ok) return;
    await this._deletePaths(paths);
  }

  /** Delete `paths` without confirmation (the menu confirms first). */
  async _deletePaths(paths) {
    for (const path of paths) {
      try {
        const isDir = this._isDirPath(path);
        await this.files.remove(path);
        this.expanded.delete(path);
        this.handlers.onDeleted(path, isDir);
      } catch (err) {
        await Dialogs.error(err.message);
      }
    }
    this.setSelection([]);
    await this.refresh();
  }

  async _reveal(path) {
    try {
      await this.files.reveal(path);
    } catch (err) {
      Dialogs.error(err.message);
    }
  }

  _remapExpanded(oldPrefix, newPrefix) {
    const next = new Set();
    for (const p of this.expanded) {
      next.add(p === oldPrefix || p.startsWith(oldPrefix + "/") ? newPrefix + p.slice(oldPrefix.length) : p);
    }
    this.expanded = next;
  }

  _nameOf(path) {
    return path.slice(path.lastIndexOf("/") + 1);
  }

  _parentOf(path) {
    return path.slice(0, path.lastIndexOf("/"));
  }
}

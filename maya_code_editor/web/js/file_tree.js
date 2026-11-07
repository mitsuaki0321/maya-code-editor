/**
 * Explorer tree for the workspace folder.
 *
 * Folders load lazily on first expand. Expanded folders and the selected
 * node survive refresh(). The right-click menu offers New File / New
 * Folder / Rename / Delete / Refresh; the actual file operations are
 * delegated to handlers supplied by app.js so the tree stays independent
 * of tabs.
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
    this.selectedPath = null;
    this.openPaths = new Set();
    this.menu = document.getElementById("context-menu");

    this.container.addEventListener("contextmenu", (e) => this._onContextMenu(e));
    document.addEventListener("mousedown", (e) => {
      if (!this.menu.contains(e.target)) this._hideMenu();
    });
    window.addEventListener("blur", () => this._hideMenu());
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
  }

  /** Mark which paths are open in tabs (for subtle highlighting). */
  setOpenPaths(paths) {
    this.openPaths = new Set(paths);
    this.container.querySelectorAll(".tree-node.file").forEach((node) => {
      node.classList.toggle("open-in-tab", this.openPaths.has(node.dataset.path));
    });
  }

  /** Highlight `path` as the selected node. */
  select(path) {
    this.selectedPath = path;
    this.container.querySelectorAll(".tree-node").forEach((node) => {
      node.classList.toggle("selected", node.dataset.path === path);
    });
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
    node.style.paddingLeft = 8 + depth * 14 + "px";
    node.title = entry.path;
    if (entry.path === this.selectedPath) node.classList.add("selected");
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

    node.addEventListener("click", () => {
      this.select(entry.path);
      if (entry.is_dir) {
        this._toggleFolder(node, entry.path);
      } else {
        this.handlers.onOpen(entry.path);
      }
    });
    return node;
  }

  async _toggleFolder(node, path) {
    const childrenEl = node.nextElementSibling;
    if (this.expanded.has(path)) {
      this.expanded.delete(path);
      node.classList.remove("expanded");
      return;
    }
    this.expanded.add(path);
    node.classList.add("expanded");
    if (!childrenEl.hasChildNodes()) {
      const depth = (parseInt(node.style.paddingLeft, 10) - 8) / 14;
      await this._renderChildren(path, depth + 1, childrenEl);
    }
  }

  // -- context menu ----------------------------------------------------

  _onContextMenu(event) {
    event.preventDefault();
    const node = event.target.closest(".tree-node");
    const target = node
      ? { path: node.dataset.path, isDir: node.dataset.isDir === "1", isRoot: false }
      : { path: this.root, isDir: true, isRoot: true };
    if (node) this.select(target.path);

    const dir = target.isDir ? target.path : this._parentOf(target.path);
    const items = [
      { label: "New File", action: () => this._createEntry(dir, false) },
      { label: "New Folder", action: () => this._createEntry(dir, true) },
    ];
    if (!target.isRoot) {
      items.push({ separator: true });
      items.push({ label: "Rename", action: () => this._rename(target) });
      items.push({ label: "Delete", danger: true, action: () => this._delete(target) });
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

  async _delete(target) {
    const kind = target.isDir ? "folder and its contents" : "file";
    const ok = await Dialogs.confirm("Delete " + this._nameOf(target.path) + "?", "This " + kind + " will be deleted permanently.", "Delete", true);
    if (!ok) return;
    try {
      await this.files.remove(target.path);
      this.expanded.delete(target.path);
      this.handlers.onDeleted(target.path, target.isDir);
      await this.refresh();
    } catch (err) {
      Dialogs.error(err.message);
    }
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

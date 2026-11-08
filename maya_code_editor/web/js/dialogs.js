/**
 * In-page modal dialogs (confirm / prompt / error).
 *
 * The page runs inside QWebEngineView where native alert()/confirm() are
 * not shown, so every confirmation is an HTML overlay. Each call returns a
 * Promise that resolves with the id of the pressed button (or null when
 * dismissed with Escape), and for prompt() with the entered text.
 */
const Dialogs = (function () {
  const overlay = document.getElementById("dialog-overlay");
  const titleEl = document.getElementById("dialog-title");
  const messageEl = document.getElementById("dialog-message");
  const inputEl = document.getElementById("dialog-input");
  const buttonsEl = document.getElementById("dialog-buttons");

  let active = null; // {resolve, buttons, withInput}

  function close(result) {
    if (!active) return;
    const resolve = active.resolve;
    active = null;
    overlay.hidden = true;
    document.removeEventListener("keydown", onKeyDown, true);
    resolve(result);
  }

  function finish(buttonId) {
    if (!active) return;
    if (active.withInput) {
      close(buttonId === "ok" ? inputEl.value : null);
    } else {
      close(buttonId);
    }
  }

  function onKeyDown(event) {
    if (!active) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(null);
    } else if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      const primary = active.buttons.find((b) => b.primary) || active.buttons[0];
      if (primary) finish(primary.id);
    }
  }

  /**
   * @param {Object} opts
   * @param {string} opts.title
   * @param {string} [opts.message]
   * @param {Array<{id:string,label:string,primary?:boolean,danger?:boolean}>} opts.buttons
   * @param {boolean} [opts.withInput]
   * @param {string} [opts.defaultValue]
   * @param {string} [opts.selectRange] "stem" selects the file name without extension
   */
  function show(opts) {
    if (active) close(null);
    return new Promise(function (resolve) {
      active = { resolve: resolve, buttons: opts.buttons, withInput: !!opts.withInput };
      titleEl.textContent = opts.title || "";
      messageEl.textContent = opts.message || "";
      buttonsEl.innerHTML = "";
      opts.buttons.forEach(function (b) {
        const btn = document.createElement("button");
        btn.textContent = b.label;
        btn.id = "dialog-btn-" + b.id;
        if (b.primary) btn.classList.add("primary");
        if (b.danger) btn.classList.add("danger");
        btn.addEventListener("click", function () { finish(b.id); });
        buttonsEl.appendChild(btn);
      });
      inputEl.hidden = !opts.withInput;
      inputEl.value = opts.defaultValue || "";
      overlay.hidden = false;
      document.addEventListener("keydown", onKeyDown, true);
      if (opts.withInput) {
        inputEl.focus();
        if (opts.selectRange === "stem") {
          const dot = inputEl.value.lastIndexOf(".");
          inputEl.setSelectionRange(0, dot > 0 ? dot : inputEl.value.length);
        } else {
          inputEl.select();
        }
      } else {
        const primary = buttonsEl.querySelector(".primary") || buttonsEl.firstChild;
        if (primary) primary.focus();
      }
    });
  }

  function confirm(title, message, okLabel, danger) {
    return show({
      title: title,
      message: message,
      buttons: [
        { id: "ok", label: okLabel || "OK", primary: !danger, danger: !!danger },
        { id: "cancel", label: "Cancel" },
      ],
    }).then(function (id) { return id === "ok"; });
  }

  function prompt(title, defaultValue, selectRange) {
    return show({
      title: title,
      withInput: true,
      defaultValue: defaultValue,
      selectRange: selectRange,
      buttons: [
        { id: "ok", label: "OK", primary: true },
        { id: "cancel", label: "Cancel" },
      ],
    });
  }

  function error(message) {
    return show({
      title: "Error",
      message: message,
      buttons: [{ id: "ok", label: "OK", primary: true }],
    });
  }

  /** Save / Don't Save / Cancel. Resolves "save" | "discard" | null. */
  function confirmClose(title) {
    return show({
      title: "Save changes to " + title + "?",
      message: "Your changes will be lost if you don't save them.",
      buttons: [
        { id: "save", label: "Save", primary: true },
        { id: "discard", label: "Don't Save" },
        { id: "cancel", label: "Cancel" },
      ],
    }).then(function (id) { return id === "cancel" ? null : id; });
  }

  /** File changed on disk while the tab has edits. Resolves "reload" | "keep". */
  function externalChange(title) {
    return show({
      title: title + " was changed on disk",
      message: "You have unsaved changes in this tab. Reload from disk and lose them, or keep your version?",
      buttons: [
        { id: "reload", label: "Reload", danger: true },
        { id: "keep", label: "Keep Mine", primary: true },
      ],
    }).then(function (id) { return id === "reload" ? "reload" : "keep"; });
  }

  return { show: show, confirm: confirm, prompt: prompt, error: error, confirmClose: confirmClose, externalChange: externalChange };
})();

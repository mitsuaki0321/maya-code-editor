/**
 * Promise-based wrapper around the QWebChannel object registered as "bridge".
 *
 * Python slots that return a value deliver it through a trailing callback
 * argument in QWebChannel; `call()` converts that into a Promise so app
 * code can `await` them. File operations return `{ok, error, data}`; the
 * `files.*` helpers resolve with `data` and reject with `Error(error)`.
 */
const MayaBridge = (function () {
  function call(obj, name, ...args) {
    return new Promise(function (resolve) {
      obj[name](...args, resolve);
    });
  }

  function fileCall(obj, name, ...args) {
    return call(obj, name, ...args).then(function (json) {
      const result = JSON.parse(json);
      if (!result.ok) throw new Error(result.error || name + " failed");
      return result.data;
    });
  }

  function wrap(raw) {
    return {
      ping: function () { return call(raw, "ping").then(JSON.parse); },
      getWorkspace: function () { return call(raw, "get_workspace").then(JSON.parse); },
      runCode: function (code) { return call(raw, "run_code", code); },
      toggleTerminal: function () { return call(raw, "toggle_terminal"); },
      getSettings: function () { return call(raw, "get_settings").then(JSON.parse); },
      getSession: function () { return call(raw, "get_session").then(JSON.parse); },
      saveSession: function (state) { raw.save_session(JSON.stringify(state)); },
      openSettingsFile: function () { return fileCall(raw, "open_settings_file"); },
      log: function (message) { raw.log(message); },
      files: {
        listDir: function (path) { return fileCall(raw, "list_dir", path); },
        read: function (path) { return fileCall(raw, "read_file", path); },
        write: function (path, content) { return fileCall(raw, "write_file", path, content); },
        createFile: function (dir, name) { return fileCall(raw, "create_file", dir, name); },
        createFolder: function (dir, name) { return fileCall(raw, "create_folder", dir, name); },
        rename: function (path, newName) { return fileCall(raw, "rename_path", path, newName); },
        remove: function (path) { return fileCall(raw, "delete_path", path); },
        reveal: function (path) { return fileCall(raw, "reveal_path", path); },
        move: function (path, destDir) { return fileCall(raw, "move_path", path, destDir); },
      },
    };
  }

  /**
   * Connect to the Qt side.
   * @returns {Promise<Object>} the wrapped bridge API
   */
  function connect() {
    return new Promise(function (resolve, reject) {
      if (typeof qt === "undefined" || !qt.webChannelTransport) {
        reject(new Error("QWebChannel transport is not available"));
        return;
      }
      new QWebChannel(qt.webChannelTransport, function (channel) {
        const raw = channel.objects.bridge;
        if (!raw) {
          reject(new Error("bridge object is not registered"));
          return;
        }
        resolve(wrap(raw));
      });
    });
  }

  return { connect: connect };
})();

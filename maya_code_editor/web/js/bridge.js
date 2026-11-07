/**
 * Promise-based wrapper around the QWebChannel object registered as "bridge".
 *
 * Python slots that return a value deliver it through a trailing callback
 * argument in QWebChannel; `call()` converts that into a Promise so app
 * code can `await` them.
 */
const MayaBridge = (function () {
  function call(obj, name, ...args) {
    return new Promise(function (resolve) {
      obj[name](...args, resolve);
    });
  }

  /**
   * Connect to the Qt side.
   * @returns {Promise<{ping: function(): Promise<Object>, runCode: function(string): Promise<boolean>, log: function(string): void}>}
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
        resolve({
          ping: function () {
            return call(raw, "ping").then(JSON.parse);
          },
          runCode: function (code) {
            return call(raw, "run_code", code);
          },
          log: function (message) {
            raw.log(message);
          },
        });
      });
    });
  }

  return { connect: connect };
})();

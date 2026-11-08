/**
 * Monaco completion provider backed by live introspection on the Python side.
 *
 * On "." (or while typing an identifier) the dotted name before the cursor
 * is sent to the bridge, which resolves it against the Maya session and the
 * buffer's import statements and returns dir() of the object. Results are
 * cached per expression until code is executed. Nothing is suggested inside
 * comments or strings.
 */
const Completion = (function () {
  const EXPR_RE = /([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\.(\w*)$/;
  const WORD_RE = /([A-Za-z_]\w*)$/;
  const MIN_WORD = 2;
  const cache = new Map();

  function kindOf(monaco, name) {
    const K = monaco.languages.CompletionItemKind;
    return K[name] !== undefined ? K[name] : K.Text;
  }

  /** True when `position` sits inside a comment or string token. */
  function inCommentOrString(monaco, model, position) {
    const offset = Math.max(0, position.column - 2);
    try {
      const tokens = model.tokenization.getLineTokens(position.lineNumber);
      const type = tokens.getStandardTokenType(tokens.findTokenIndexAtOffset(offset));
      return type === 1 || type === 2; // StandardTokenType.Comment / String
    } catch (err) {
      // Fallback: tokenize this one line in isolation.
      const line = model.getLineContent(position.lineNumber);
      const lineTokens = monaco.editor.tokenize(line, model.getLanguageId())[0] || [];
      let current = "";
      for (const t of lineTokens) {
        if (t.offset > offset) break;
        current = t.type;
      }
      return /comment|string/.test(current);
    }
  }

  function register(monaco, bridge) {
    monaco.languages.registerCompletionItemProvider("python", {
      triggerCharacters: ["."],
      provideCompletionItems: async function (model, position) {
        if (inCommentOrString(monaco, model, position)) return { suggestions: [] };
        const before = model.getLineContent(position.lineNumber).slice(0, position.column - 1);
        let expression;
        const dotted = EXPR_RE.exec(before);
        if (dotted) {
          expression = dotted[1];
        } else {
          const word = WORD_RE.exec(before);
          if (!word || word[1].length < MIN_WORD) return { suggestions: [] };
          expression = "";
        }
        const items = await lookup(bridge, expression, model);
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };
        return {
          suggestions: items.map(function (it) {
            return {
              label: it.label,
              kind: kindOf(monaco, it.kind),
              detail: it.detail || undefined,
              insertText: it.label,
              range: range,
              sortText: (it.label.charAt(0) === "_" ? "~" : " ") + it.label,
            };
          }),
        };
      },
    });
  }

  async function lookup(bridge, expression, model) {
    const key = expression;
    if (cache.has(key)) return cache.get(key);
    const t0 = performance.now();
    let items = [];
    try {
      items = await bridge.complete(expression, model.getValue());
    } catch (err) {
      items = [];
    }
    lookup.lastMs = performance.now() - t0;
    cache.set(key, items);
    return items;
  }

  /** Forget cached results (call after executing code: the namespace changed). */
  function invalidate() {
    cache.clear();
  }

  return { register: register, invalidate: invalidate, inCommentOrString: inCommentOrString, lookup: lookup, cache: cache };
})();

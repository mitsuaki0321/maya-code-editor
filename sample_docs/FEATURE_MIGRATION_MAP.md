# 機能移行マップ — 旧 Code Editor → Monaco 版

旧エディター（`CODE_EDITOR_STRUCTURE.md` 参照）の各機能が、Monaco Editor + QWebEngineView ベースの新エディターでどうなるかの対応表。

## 決定事項

- **対象**: Maya 2025+（PySide6、QtWebEngineWidgets 同梱）
- **構成**: QWebEngineView 1枚に UI（タブ・ファイラ・エディタ）を HTML/JS で構築。ターミナルのみ Qt 側（下記）
- **言語**: Python 専用（MEL 廃止 → 言語切替機構ごと不要に）
- **補完**: v1 は Monaco 組み込みの単語補完のみ。jedi は後日プロバイダ追加で対応
- **ビルド**: なし。ビルド済み monaco-editor を同梱、素の JS
- **廃止**: MEL、シェルフ追加

## ウィンドウ構成（ターミナルは Qt 側 — マスト要件）

cmdScrollFieldReporter は Maya ネイティブの Qt ウィジェットで WebView 内に入れられないため、
ウィンドウは Qt の縦 QSplitter 2 段構成とする。

```
┌─ Qt ウィンドウ (workspaceControl) ─────┐
│ ┌─ QWebEngineView ───────────────────┐ │
│ │ タブ / ファイルツリー / Monaco      │ │
│ └────────────────────────────────────┘ │
│ ├─── QSplitter ──────────────────────┤ │
│ ┌─ ターミナル (Qt) ──────────────────┐ │
│ │ Maya 内: cmdScrollFieldReporter    │ │
│ │ 単体起動: QPlainTextEdit + stdout捕捉 │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

- Maya 内では Script Editor と同じ出力（reporter）を表示する。**他ユーザーとの出力互換のためマスト**
- 実行は現行同様の隠し executer 方式 → 出力は自動的に Script Editor 履歴（= reporter）に流れる
- 単体起動時は reporter が使えないため QPlainTextEdit + stdout/stderr 捕捉のフォールバック
- ターミナル表示切替は Web 側ツールバー → QWebChannel 経由で Qt 側をトグル

## 対応マップ

区分:

- **[Monaco標準]** — Monaco の設定・標準機能だけで置換
- **[流用]** — Python コードをほぼそのまま移植
- **[新規]** — 新規実装
- **[後日]** — jedi フェーズ（v2 以降）
- **[廃止]** — 新版では提供しない

### ルート・Maya 統合

| 現行 | 新版 |
|---|---|
| `main.py`（show_ui、インスタンス保持、終了時保存） | **[流用]** 構造そのまま、中身は WebView 構築に |
| `integration/maya_dock.py`（workspaceControl） | **[流用]** そのまま |

### command/ — 純ロジック

| 現行 | 新版 |
|---|---|
| `execution.py`（隠し executer 実行） | **[流用]** `bridge/execution.py` へ。Python のみに縮小 |
| `file_io.py` / `file_ops.py` | **[流用]** `bridge/files.py` へ |
| `search.py` | **[Monaco標準]** Ctrl+F / Ctrl+H（正規表現・全単語対応込み） |
| `refactor.py`（F2 参照解決） | **[後日]** jedi 導入時に Monaco の rename プロバイダに接続。v1 は Monaco 標準の「Change All Occurrences」（Ctrl+F2、単語ベース）で代用 |
| `stub_generator.py` | **[後日]** jedi フェーズまで温存 |
| `autocomplete/`（JediEngine、MRU 永続化） | **[後日]** engine は流用予定。MRU 永続化は Monaco の `suggestSelection: 'recentlyUsed'` が近い挙動を標準で持つため、導入時に要否を再判断 |
| `maya_shelf.py` | **[廃止]** |
| `os_launcher.py`（エクスプローラで開く） | **[流用]** ファイルツリー右クリックに残す |

### highlighting/ / languages/ / themes/

| 現行 | 新版 |
|---|---|
| `python_highlighter.py`（tokenize 走査＋デバウンス） | **[Monaco標準]** 組み込み Python 定義 |
| `mel_highlighter.py`、`languages/mel/` 一式 | **[廃止]** Python 専用 |
| `languages/profile.py`（言語プロファイル機構） | **[廃止]** 単一言語なので機構ごと不要 |
| `indent_resolver.py` / `python/indent.py` | **[Monaco標準]** 言語標準のオートインデント |
| `folding_strategy.py` / `python/folding.py` | **[Monaco標準]** インデントベース折りたたみ |
| `python/actions.py`（右クリック: dir / help / モジュール再読込） | **[新規・小]** 残すなら `editor.addAction()` で Monaco 右クリックに追加。v1 スコープ外にして後日でも可 |
| `themes/app_theme.py` / `syntax_colors.json` | **[新規・小]** CSS 変数 + `monaco.editor.defineTheme()` の JSON に置換。Qt 側ターミナルの配色だけ Qt スタイルシート |

### settings/

| 現行 | 新版 |
|---|---|
| `session_manager.py`（タブ・Draft・ウィンドウ状態） | **[流用]** `bridge/session.py` へ簡素化 |
| `user_settings.py`（フォントサイズ等） | **[流用・縮小]** 大半は Monaco オプションに直結する JSON に |
| `workspace_manager.py`（ワークスペースルート） | **[流用]** ファイルツリーのルートとして必要 |
| `settings_manager.py`（ファサード） | **[廃止]** 3 ファイルに縮むので facade 不要 |
| `startup/welcome.py` | **[新規・小]** 簡素版（キーバインドは Monaco 標準になるので内容書き直し） |

### ui/editor/ — ほぼ全て Monaco 標準で置換（今回の狙い）

| 現行 | 新版 |
|---|---|
| `code_editor.py`（本体＋Mixin 群） | **[新規・小]** `app.js` の Monaco 生成 1 回＋モデル管理のみ |
| `appearance.py`（フォント、ラップ、ホイールズーム） | **[Monaco標準]** `fontSize` / `wordWrap` / `mouseWheelZoom: true` |
| `auto_close.py`（括弧・クォート補完、三重引用符判定） | **[Monaco標準]** `autoClosingBrackets` / `autoClosingQuotes` |
| `auto_indent.py` | **[Monaco標準]** |
| `bracket_match_highlighter.py` | **[Monaco標準]** `matchBrackets` + ペア色分け |
| `code_folding.py` | **[Monaco標準]** |
| `line_number_area.py`（行番号＋ガター） | **[Monaco標準]** |
| `overlays.py`（現在行枠、インデントガイド、fold プレースホルダ） | **[Monaco標準]** `renderLineHighlight` / `guides` |
| `shortcuts.py`（行複製・移動・コメントトグル） | **[Monaco標準]** Alt+↑↓ / Shift+Alt+↓ / Ctrl+/ |
| `text_operations.py`（Smart Home 等） | **[Monaco標準]** |
| `word_navigation.py`（Ctrl+←→） | **[Monaco標準]** |
| `multi_cursor/` 全 6 ファイル | **[Monaco標準]** Alt+Click / Ctrl+D / Ctrl+Shift+L / 矩形選択（現行の Ctrl+Click と修飾キーが違う点だけ注意） |
| `rename_overlay.py` / `inline_overlay.py` | **[Monaco標準]** rename UI は標準（ロジックは後日 jedi） |
| `goto_line_overlay.py` | **[Monaco標準]** Ctrl+G |
| `context_menu.py` | **[Monaco標準]** 標準右クリック。Maya ヘルプ等の独自項目は後日 `addAction()` |
| `file_bridge.py`（dirty 管理、タブ名 `*`） | **[新規]** `tabs.js` に統合 |

### ui/ その他

| 現行 | 新版 |
|---|---|
| `_common.py`（ポップアップ外クリック監視） | **[廃止]** Monaco のポップアップは Web 内で完結、この問題自体が消滅 |
| `dialogs/base.py`（テーマ済みダイアログ群） | **[新規・小]** HTML ダイアログ（確認・入力の 2 種で足りる見込み） |
| `dialogs/find_replace.py` | **[Monaco標準]** |
| `autocomplete/`（controller / worker / namespaces / _stubs） | **[後日]** jedi ブリッジ時に `namespaces.py`（ライブ名前空間収集）は流用価値大 |
| `help/`（docstring ポップアップ＋HTML レンダラ） | **[後日]** jedi 導入時に Monaco の hover / suggest 詳細ペインに接続。renderer 資産は流用候補 |
| `operations/execution_manager.py` | **[流用・縮小]** `bridge/execution.py` に統合 |
| `operations/files.py` | **[新規]** JS 側の操作＋`bridge/files.py` に分割再編 |
| `panels/file_explorer.py` | **[新規]** `file_tree.js`（D&D・右クリック・アイコンは簡素化して再実装） |
| `panels/maya_terminal.py`（cmdScrollFieldReporter） | **[流用・マスト]** Qt 側に残す（上記ウィンドウ構成のとおり） |
| `panels/output_terminal.py`（reporter / フォールバック切替） | **[流用]** 単体起動時は QPlainTextEdit + stdout/stderr 捕捉 |
| `tabs/`（widget / tab_bar / session_manager） | **[新規]** `tabs.js`。言語別アクセントカラーは廃止。プレビュータブは v1 スコープ外 |
| `window/main.py` / `layout_manager.py` | **[流用・大幅縮小]** Qt 側は「splitter 2 段＋WebView＋ターミナル」だけに |
| `window/shortcut_handler.py` | **[Monaco標準＋新規・小]** エディタ系は標準。Ctrl+S / Ctrl+N 等アプリ系だけ `addCommand()` で JS 実装 |
| `window/toolbar.py` | **[新規]** HTML ツールバー（Run / Save / New / ターミナル切替 / ワードラップ） |
| `utils/maya_help_detector.py` | **[後日]** 右クリック「Maya ヘルプを開く」を復活させる時に流用 |

## 集計の感覚値

- **[Monaco標準]** で消えるもの: `ui/editor/` のほぼ全部（約 20 ファイル）＋ `highlighting/` ＋ `languages/` の大半 ＋ 検索ダイアログ — 現行コードの体感 6〜7 割
- **[流用]**: execution / file_io / file_ops / session / dock / ターミナル — Maya 統合の核はそのまま
- **[新規]**: JS 側の tabs / file_tree / toolbar / bridge クライアント — いずれも UI の骨組みだけ

## 新版ディレクトリ構成（案）

```
maya_code_editor/
├── __init__.py
├── main.py                  # show_ui(): QSplitter(WebView + ターミナル) + workspaceControl ドック
├── bridge/                  # QWebChannel で JS に公開する Python API
│   ├── files.py             #   read/write/list_dir/create/rename/delete
│   ├── execution.py         #   コード実行（隠し executer 方式、現行流用）
│   └── session.py           #   session.json の読み書き
├── terminal/                # Qt 側ターミナル（reporter / フォールバック切替）
└── web/                     # 静的ファイル（ビルドなし）
    ├── index.html
    ├── vendor/monaco/       # ビルド済み monaco-editor（min/vs を同梱）
    ├── css/app.css
    └── js/
        ├── bridge.js        # QWebChannel クライアントラッパ（Promise 化）
        ├── tabs.js          # タブバー（dirty マーカー、閉じる、Monaco モデル切替）
        ├── file_tree.js     # 左ペインのツリー＋右クリック
        ├── toolbar.js       # Run / Save / New / ターミナル切替 / ワードラップ
        └── app.js           # 起動と結線
```

## 実装ステップ

1. **骨組み** — QSplitter + WebView + Monaco が Maya 内で表示され、QWebChannel の往復が動く
2. **ファイル & タブ** — ツリー表示、開く/保存/新規/リネーム/削除、dirty 管理
3. **実行 & ターミナル** — Ctrl+Enter（選択実行対応）/ Run → reporter（単体時はフォールバック）に出力
4. **セッション & ドック** — タブ復元、Draft 保存、workspaceControl ドック統合
5. **（後日）** jedi 補完プロバイダ・F2 リネーム・docstring ホバー追加

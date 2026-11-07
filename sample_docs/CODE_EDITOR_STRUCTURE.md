# Code Editor 構造マップ

`scripts/faketools/tools/common/code_editor/` 配下のファイル構造とそれぞれの役割をまとめたインデックス。
コードを触る前にこのファイルだけ読めば「どこに何があるか」が把握できることを目的とする。

> このファイルは gitignore 済み（ローカル設計メモ）。常に最新とは限らないので、
> 主要 API 名は信頼してよいが、行数や細部はソースで確認すること。

---

## アーキテクチャ概要

```
┌─────────────────────────────────────────┐
│  main.py / ui/window/main.py            │  ← Maya 統合・ウィンドウ起動
└─────────────────────────────────────────┘
                ↓
┌──────────────┬──────────────┬───────────┐
│  ui/         │  command/    │ settings/ │  ← UI 層 / 純ロジック / 永続化
│              │              │           │
│  - window    │  - file_io   │  - user   │
│  - tabs      │  - execution │  - session│
│  - editor    │  - search    │  - ws     │
│  - panels    │  - file_ops  │           │
│  - dialogs   │  - autocomp  │           │
│  - operations│  - maya_shelf│           │
│  - autocomp  │  - stub_gen  │           │
│  - help      │  - os_launch │           │
└──────────────┴──────────────┴───────────┘
                ↓
┌─────────────────────────────────────────┐
│  languages/                             │  ← 言語プロファイル（PYTHON / MEL）
│   profile.py / indent_resolver.py       │     ハイライト/インデント/折りたたみ/
│   folding_strategy.py / mel/ python/    │     右クリック/シェルフ等を集約
└─────────────────────────────────────────┘
                ↓
┌──────────────┬──────────────┬───────────┐
│ highlighting/│  themes/     │integration│
└──────────────┴──────────────┴───────────┘
```

レイヤー依存ルール:
- `command/` は Qt 非依存の純ロジック（Maya API 呼び出しは可）
- `ui/` は `command/` と `languages/` を使うが、その逆は禁止
- `languages/` は `highlighting/` を遅延 import する（Qt 起動を遅らせる目的）

---

## ルート

### `__init__.py`
パッケージのエントリ。`TOOL_CONFIG` のみを公開（FakeTools のメニューシステムが参照）。

### `main.py`
Maya 統合エントリポイント。`show_editor(floating=False)` / `show_ui()` を提供。
グローバル `_editor_instance` / `_dock_instance` でインスタンスを保持し、
docked / floating の切り替えと Maya 終了時セッション保存コールバックを設定。

---

## command/ — 純ロジック層（Qt 非依存）

### `__init__.py`
UI 層が委譲するロジックモジュール群の入り口。

### `execution.py`
Maya で Python/MEL を実行するブリッジ。
- `build_exec_globals()` — `cmds` / `om` / `om2` を含む実行用辞書を生成
- `NativeExecutionBridge` — `LanguageProfile` ごとに 1 つ作られ、隠し Maya executer ウィンドウを使ってコードを実行する

### `file_io.py`
UTF-8 ファイル I/O。例外ではなく `(値, error)` タプルで返す。
- `read_text(path) -> (text, error)`
- `write_text(path, text) -> error`

### `file_ops.py`
ファイルシステム操作（純粋）。衝突時は自動で `(N)` サフィックスを付与。
- `FileOpResult`、`get_unique_name()`、`create_file()`、`delete_file()` など

### `maya_shelf.py`
コード片を Maya シェルフボタンとして追加。`LanguageProfile.shelf_config` 経由で
ソースタイプ／ラベル／アイコンを取得する。
- `add_to_active_shelf(code, language) -> (ok, info)`

### `os_launcher.py`
ネイティブファイラでディレクトリを開く（Win/Mac/Linux 判定済み）。
- `open_directory(path) -> (ok, error)`

### `refactor.py`
jedi ベースのリネーム用参照解決（F2 シンボルリネーム）。Qt 非依存。
`scope='file'` で現在ファイル内のみを対象にし、QTextCursor が直接使える絶対オフセットで返す。
- `SymbolReference`（`start` / `end` の絶対オフセット）
- `find_symbol_references(code, line, column, path) -> list[SymbolReference]` — 失敗時／jedi 未導入時は `[]`

### `search.py`
正規表現／全単語マッチ対応の検索エンジン（QTextDocument 操作）。
- `SearchOptions`、`SearchEngine`、`InvalidRegexError`

### `stub_generator.py`
Maya 用 `.pyi` スタブ生成。`cmds` コマンド一覧と OpenMaya API のフラグ抽出。
jedi のオートコンプリート精度向上用。
- `generate_all()`、`get_bundled_stubs_root()`

## command/autocomplete/

### `__init__.py`
jedi ラッパー再エクスポート。UI 層は jedi の型を直接見ない。
- `JEDI_AVAILABLE`、`CompletionItem`、`JediEngine`、`expression_root`
- `AutocompleteMruStore`、`MRU_MAX_ENTRIES`、`MRU_FILE_NAME`、`make_mru_key`

### `engine.py`
jedi の薄層アダプタ。`cmds → maya.cmds` 等の Maya エイリアスを内部で展開。
ファイルサイズ上限 `_MAX_FILE_BYTES` あり。jedi 未インストール時は no-op。
- `JediEngine`

### `persistence.py`
オートコンプリート MRU（accept 履歴ブースト）の永続化。`autocomplete_mru.json` にセッション越しで保存。
- コンテキスト付きキー（`cmds.polyCube` vs `pymel.core.polyCube` を別扱い）、`view_for_root()` で bare-name dict を要求時生成
- Dirty-flag I/O — accept があった時のみ `save_if_dirty()` が書き込む
- `MAX_ENTRIES = 100` で打ち切り（LFU + 最古から落とす）
- `AutocompleteMruStore`、`make_key(root, name)`

### `types.py`
jedi 非依存の `CompletionItem` データクラス（jedi を別実装に差し替え可能にするため）。

---

## highlighting/ — シンタックスハイライタ実装

### `__init__.py`
- `MelHighlighter`、`PythonHighlighter` を再エクスポート

### `mel_highlighter.py`
MEL 用シンタックスハイライタ。正規表現＋ブロック状態マシン（`/* ... */` 対応）。
- `MelHighlighter(QSyntaxHighlighter)`

### `python_highlighter.py`
Python 用ハイライタ。標準 `tokenize` で全文走査し span キャッシュを構築、
30ms デバウンスで再構築。f-string、デコレータ、型アノテーション、kwarg 対応。
- `PythonHighlighter(QSyntaxHighlighter)`

### `syntax_config_loader.py`
`themes/syntax_colors.json` を読み、トークン種別→`QTextCharFormat` の辞書を返す。
- `SyntaxConfigLoader`

---

## integration/ — Maya ドック統合

### `__init__.py`
- `MayaDock` を再エクスポート

### `maya_dock.py`
Maya `workspaceControl` を使ったドック／フローティング切替の管理。

---

## languages/ — 言語プロファイル

### `__init__.py`
公開 API。`get_profile_for_path(path)` が拡張子から `LanguageProfile` を解決する。
- `ALL_PROFILES`、`DEFAULT_PROFILE`(=PYTHON)、`KNOWN_EXTENSIONS`
- `LanguageProfile`、`ShelfConfig`、`PYTHON`、`MEL`

### `profile.py`
`LanguageProfile`（frozen dataclass）と `ShelfConfig`。各言語が公開する全フックを 1 つに集約:
- 識別: `id` / `display_name` / `extensions` / `default_extension`
- 構文: `line_comment` / `highlighter_factory` / `indent_resolver` / `folding_strategy`
- 実行: `source_type` / `shelf_config`
- UI: `context_menu_extender` / `accent_color` / `completion_engine_factory`

### `editor_helpers.py`
言語非依存のエディタ配管（実行マネージャ検索、`What is` などの dispatch）。
- `find_execution_manager(editor)`、`dispatch_inspection(editor, kind)`

### `folding_strategy.py`
折りたたみ戦略の基底クラス。サブクラスが `detect(doc)` で `{header_block: end_block}` 辞書を返す。

### `indent_resolver.py`
オートインデント解決の基底クラス。4 段階の優先度ルール:
- Rule 0: 言語固有（Python の `:` で +4 など）
- Rule 1: hanging（開き括弧の直後）
- Rule 2: 閉じ括弧で始まる行
- Rule 3: デフォルト（前行と同じインデント）

## languages/python/

### `__init__.py`
`PYTHON` インスタンスを組み立てるマニフェスト。

### `actions.py`
Python 専用の右クリックメニュー（`dir`、`help`、モジュール再読込み）。

### `completion.py`
Python オートコンプリートのファクトリ。プロセス全体で共有 `JediEngine` を使う。
- `python_completion_engine_factory()`

### `folding.py`
Python 折りたたみ：`:` ブロック、三重引用符、連続 import グループ。
- `PythonFoldingStrategy`

### `highlighting.py`
`PythonHighlighter` の遅延ファクトリ（Qt の import を後回しにする）。

### `indent.py`
Python のインデントルール。`:` で終わる行は +4 スペース。
- `PythonIndentResolver`

## languages/mel/

### `__init__.py`
`MEL` インスタンスのマニフェスト（オートコンプリートは意図的に未提供）。

### `actions.py`
MEL 用右クリックメニュー: `whatIs` で分類表示、ソースファイル位置を開く。

### `folding.py`
MEL 折りたたみ：`{` `}` ベース。コメント／文字列内の括弧はスキップ。
- `MelFoldingStrategy`

### `highlighting.py`
`MelHighlighter` の遅延ファクトリ。

### `indent.py`
MEL のインデント。`{` または `:` 終わりで +4 スペース。コメント／文字列内では無効。
- `MelIndentResolver`

---

## settings/ — 設定永続化

### `__init__.py`
- `SettingsManager` などを再エクスポート

### `session_manager.py`
セッション状態（ウィンドウ位置、開いているタブ、Draft 内容、最近のファイル）を `session.json` に永続化。
`MAX_RECENT_FILES = 20`。

### `settings_manager.py`
ファサード。`UserSettings` / `SessionManager` / `WorkspaceManager` をまとめて公開。
旧 API 互換のためのプロキシメソッドも持つ。

### `user_settings.py`
ユーザ設定（フォントサイズ、検索オプション、レイアウト方向等）→ `user_settings.json`。

### `workspace_manager.py`
ワークスペースルート、Python パス追加、環境変数の管理。

### `startup/welcome.py`
初回起動時の Welcome テキスト（キーバインド一覧と推奨ディレクトリ構造）。

---

## themes/ — テーマパレット

### `__init__.py`
- `AppTheme` を再エクスポート

### `app_theme.py`
- `_Palette` — 生のカラートークン
- `AppTheme` — 役割別エイリアスとスタイルシート生成（エディタ／ターミナル／ファイラ／タブ／メイン）

### `syntax_colors.json`
`SyntaxConfigLoader` が読む構文配色テーブル（`control_keyword`、`string`、`bracket_1` 等）。

---

## ui/ — Qt UI 層

### `__init__.py`
UI モジュールの集約点。循環参照回避のため遅延 import 多用。

### `_common.py`
複数 UI で共有するヘルパー。
- `_OwnerWindowWatcher` — オーナーウィンドウが閉じる／最小化／非アクティブになったらポップアップを自動非表示
- `_OutsideClickWatcher` — ポップアップ外クリックで自動非表示（`Qt.Tool` で失われる `Qt.Popup` の auto-close を application-level 再実装）。`set_exception()` で「クリックしても閉じない」許可ウィジェットを 1 つ登録可。autocomplete／help 双方が利用し、両ポップアップ共存時の取り合いを回避

## ui/autocomplete/

### `__init__.py`
- `AutocompleteController`、`CompletionRunnable`、`DocstringRunnable`、`get_shared_engine()`、`get_shared_mru_store()`、`collect_exec_namespaces`

### `controller.py`
1 エディタにつき 1 つ作られるオートコンプリートのコントローラ。
トリガー判定（`.` / 識別子 N 文字）→ デバウンス → QCompleter ポップアップ駆動まで担当。
ポップアップは `Qt.Tool` で組み立て、外クリックは `_common._OutsideClickWatcher` で処理。help ポップアップを exception 登録して両者の共存を維持。
- `AutocompleteController`、`teardown()`（タブ破棄時に飛行中ワーカーをキャンセルしデバウンスタイマーを停止。`CodeEditor.shutdown()` から呼ばれる）

### `worker.py`
QThreadPool 上で `jedi.complete()` をオフスレッド実行。stale な結果はフィルタ。
- `CompletionRunnable`、`CompletionSignals`、`DocstringRunnable`

### `namespaces.py`
`jedi.Interpreter` に渡すライブ実行名前空間の収集ロジック（Qt 非依存）。エディタ親チェーン上の `exec_globals` と Maya の `__main__` を優先順でマージ。
- `collect_exec_namespaces(editor) -> list[dict]`

### `_stubs.py`
Maya スタブパスを設定し、共有 `JediEngine` ／共有 `AutocompleteMruStore` インスタンスを返す。
- `get_shared_engine()`、`get_shared_mru_store()`、`_SHARED_JEDI_ENGINE` キャッシュ

## ui/dialogs/

### `__init__.py`
- ダイアログクラス群の再エクスポート

### `base.py`
テーマ済みダイアログの基底群と `DialogPositioner`。
- `CodeEditorDialog`、`CodeEditorMessageBox`、`CodeEditorInputDialog`、`CodeEditorFileDialog`

### `find_replace.py`
検索／置換ダイアログ。`SearchOptions` を `SearchEngine` に渡して動作する。
- `FindReplaceDialog`、`show_find_dialog()`、`show_replace_dialog()`、`find_next()`、`find_previous()`

## ui/editor/

### `__init__.py`
- `CodeEditor` を公開

### `code_editor.py`
タブごとの編集ウィジェット本体（`QPlainTextEdit` + 各種 Mixin）。
`LanguageProfile` を保持し、ハイライタ／折りたたみ／オートコンプリート／プレースホルダ等を駆動。
- `CodeEditor`、`setup_syntax_highlighting()`、`set_language()`、`load_file()`、`save_file()`、`handle_return_key()`
- `shutdown()` — タブ破棄前の後始末。飛行中の jedi ワーカーをキャンセル（`autocomplete.teardown()`）し、ハイライタを `setDocument(None)` で切り離す。`removeTab` 系は必ず `shutdown()` → `deleteLater()` の順で呼ぶこと（呼ばないとエディタ一式がセッション中リークする）。

### `appearance.py`
フォント・行高・ワードラップ・スクロールバー方針など、言語プロファイルに依存しない外観・レイアウト系設定を切り出した Mixin。ホイールズーム／`setPlainText` のオーバーライドは `CodeEditor` 側に残し、本 Mixin のヘルパを呼ぶ。
- `EditorAppearanceMixin`、`DEFAULT_TAB_SIZE`、`_MIN_FONT_SIZE` / `_MAX_FONT_SIZE`

### `auto_close.py`
カッコ／クォートの自動補完と選択囲み。`CodeEditor.keyPressEvent` から
`handle_key(editor, event)` 1 本で呼ばれる。空ペアの Backspace を 1 回の
`beginEditBlock` で両側削除。クォートは「**直後**が英数字／`_`」または
「**直前**が同じクォート」のときだけスキップする方針で、`f"..."` /
`r"..."` / `b"..."` のような英字接頭辞付き文字列は通常どおり閉じが入る
（三重引用符の 3 つ目だけは抑止）。マルチカーソル有効時は即時 `False`
を返し、既存のマルチカーソル入力パイプラインに譲る。
- `handle_key(editor, event) -> bool`

### `auto_indent.py`
オートインデントのエントリポイント。`IndentResolver` に委譲。
- `compute_indent(doc, block_no, current_line, text_before, language)`

### `bracket_match_highlighter.py`
Sublime 風の括弧ペア強調。カーソル位置を含む括弧の枠線描画。
- `BracketMatchHighlighter`

### `code_folding.py`
折りたたみ状態の管理（300ms デバウンスで再検出）。言語別 `FoldingStrategy` に委譲。
- `CodeFoldingManager`

### `context_menu.py`
右クリックメニュー構築（Maya ヘルプ、`LanguageProfile.context_menu_extender`、Insert サブメニュー、シェルフ追加）。
Insert サブメニューは `command/insert_commands.py` の `INSERT_COMMANDS` をそのまま列挙し、
`supports(language)` で出し分け＋選択無しで無効化。発火時はクリック位置にキャレットを移してから
（選択がある場合は移さず）main window の `insert_named_command` に委譲する（ツールバー split-button と同じ挿入経路）。
- `build_context_menu(editor, event) -> QMenu`

### `file_bridge.py`
`command/file_io.py` の `(値, error)` タプル API を UI 側にブリッジ。`CodeEditorMessageBox` でテーマ済みエラーダイアログを出し、成功時に `editor.file_path` / `is_modified` / `QTextDocument.setModified` を更新。タブ表示名の `*` 付与もここに集約。
- `load_file(editor, path) -> bool`、`save_file(editor, path=None) -> bool`、`get_display_name(editor) -> str`

### `line_number_area.py`
行番号 + 折りたたみガター。150ms フェードアニメーション付き。
- `LineNumberArea`

### `overlays.py`
ビューポート上の追加描画。
- `paint_current_line_border()`、`paint_indent_guides()`、`paint_fold_placeholders()`

### `rename_overlay.py`
F2 シンボルリネームの VSCode 風インライン入力。`EditorInlineOverlay` を継承し、独自部分はカーソル上の参照（"アンカー"）への位置決めと Enter 動作だけ。Enter で全参照を 1 つの `beginEditBlock` 内に逆順置換、Esc／フォーカスアウト／スクロールでキャンセル。Undo 復元位置を意図した場所にするため、編集前にエディタのカーソルをアンカー末尾にセットしてから `beginEditBlock` を呼ぶ。コミット後のキャレットはアンカーより前の参照によるシフト量を補正して着地。
- `RenameOverlay`、`_anchor_reference(references, cursor_offset)`

### `goto_line_overlay.py`
Ctrl+G の Go to Line インライン入力。`EditorInlineOverlay` を継承し、独自部分は位置決め（ビューポート上部中央、幅 240px）と Enter 動作（折りたたみ内なら `fold_manager.unfold_containing()` で展開→`centerCursor()` で画面中央へ）だけ。`QIntValidator(1, blockCount)` で範囲制限、現在行をプリフィル。
- `GoToLineOverlay`

### `inline_overlay.py`
F2 リネームと Ctrl+G Go to Line の共通基底。`QLineEdit` を `editor.viewport()` に親付けする単発オーバーレイのライフサイクル（再入ガード `_dismissed`、Esc/Enter ルーティング、focus-out / スクロールキャンセル、`_disconnect_scroll` / `_teardown`、テーマ済みスタイル）を一手に持つ。サブクラスは位置決めと `_commit()` だけ書けばよい。`__init__` → サブクラス独自セットアップ → ポジショニング → `_finish_setup()` の順で呼ぶ契約。
- `EditorInlineOverlay`

### `shortcuts.py`
編集系キーバインド（行複製、移動、コメントトグル、選択単語ジャンプ等）。
- `EditorShortcuts`

### `text_operations.py`
単一カーソル時の行操作 Mixin（複製、削除、移動、Smart Home）。
- `EditorTextOperationsMixin`

### `word_navigation.py`
VSCode/Sublime 風の単語境界ジャンプ。Ctrl+Left/Right 1 回で「水平ホワイトスペースをスキップ → 単語文字 or 非単語記号の連続を 1 まとめで越える」。改行は越えない（別キーで明示的に移動）。単一カーソル shortcuts と multi_cursor 入力ハンドラの両方で共有。
- `next_word_position(text, pos) -> int`、`previous_word_position(text, pos) -> int`

## ui/editor/multi_cursor/

### `__init__.py`
- `MultiCursorMixin` を公開

### `controller.py`
複数カーソルの状態遷移（追加／削除、矩形選択開始終了）。

### `comment.py`
複数カーソル状態でのコメントトグル（複数行同時処理）。

### `handler.py`
`MultiCursorMixin` 本体。`CodeEditor` が継承する。Ctrl+Click、Ctrl+D、Ctrl+Shift+L 等。

### `input.py`
マルチカーソル時のマウス／キー入力ハンドリング。

### `painter.py`
複数キャレット・矩形・選択範囲の描画。

## ui/help/

### `__init__.py`
- `HelpPopupController` を公開

### `controller.py`
docstring ポップアップのライフサイクル管理。Ctrl+Shift+Space トリガー、フォーカス移動で自動非表示。autocomplete オープン中は選択追従（debounce 80ms）。dismiss 条件: Esc／再トリガー／autocomplete Show・Hide／オーナー閉時／cursor モードでのタイピング再開／外側クリック（autocomplete ポップアップは exception 登録で許容）。Ctrl+Shift+Up/Down でポップアップ内スクロール、Ctrl+C で選択コピー。
- `HelpPopupController`、`toggle_help_popup(main_window)`

### `popup.py`
浮遊型 docstring ウィンドウ。フォーカスを奪わないツールチップ風（`Qt.Tool` + `WA_ShowWithoutActivating`）。本文は `QTextEdit` で読み取り専用、マウスでテキスト選択可。
- `HelpPopup`、`set_loading()`、`set_text()`、`scroll_lines()`、`copy_selection()`、`show_at(anchor_rect)`

## ui/help/renderer/  — docstring → HTML レンダラ（Qt 非依存）

### `__init__.py`
- `render_docstring()`、`render_loading()`

### `blocks.py`
共通 HTML ビルディングブロック（`signature()`、`code_block()`、`section_header()` 等）。

### `detect.py`
docstring の形式検出（Maya help / numpydoc / Google / RST）と署名行抽出。

### `maya.py`
`cmds.help()` 出力用レンダラ（Synopsis / Flags / Return value / Examples）。

### `plain.py`
フォールバック用の素の段落レンダラ。

### `structured.py`
`docstring_parser` を使う numpydoc/Google/RST 用レンダラ。

### `syntax.py`
Pygments による Python ハイライト（ヘルプ表示用）。Pygments 不在時は `html.escape` フォールバック。

### `theme.py`
ヘルプポップアップ用パレット（エディタ配色のミラー）。

## ui/operations/

### `__init__.py`
- `ExecutionManager`、`FileOperationsController` を公開

### `execution_manager.py`
コード実行の統括。言語ごとの `NativeExecutionBridge` をキャッシュ、検査用スニペット送信、出力ターミナル連携。
- `ExecutionManager`、`run_current_script()`、`execute_code()`、`cleanup_bridges()`

### `files.py`
ファイル操作のレシピ集（open / save / save_all / new / rename / delete / execute_file_directly）。
ツールバー・ファイラ・ショートカットからすべてここに集まる。
- `FileOperationsController`

## ui/panels/

### `__init__.py`
- `FileExplorer`、`OutputTerminal`

### `file_explorer.py`
左ペインのファイルツリー。コンテキストメニュー、D&D、言語別アイコン、未知拡張子フィルタ。
- `FileExplorer(QTreeView)`

### `maya_terminal.py`
Maya ネイティブの `cmdScrollFieldReporter` を埋め込むターミナル（Script Editor 互換）。

### `output_terminal.py`
出力ターミナル本体。Maya 内では `MayaTerminalWidget`、それ以外は `QTextEdit` フォールバック。
`MAX_OUTPUT_LINES = 1000`。
- `OutputTerminal`

## ui/tabs/

### `__init__.py`
- `CodeEditorWidget`、`UISessionManager`、`EditableTabBar`

### `session_manager.py`
セッションの保存／復元。`_restoring` 再入性ガードあり。
- `UISessionManager`、`save_session_state()`、`restore_session_state()`、`restore_tab(info)`

### `tab_bar.py`
カスタムタブバー。言語アクセントカラーの上端ストリップ（2px）描画、リネーム編集対応。
- `EditableTabBar`

### `widget.py`
タブ化されたコードエディタコンテナ。プレビュータブのライフサイクル、新規／開く／保存／閉じる。
- `CodeEditorWidget(QTabWidget)`、`new_file()`、`open_file_permanent()`、`open_file_preview()`、`open_preview()`（スニペット用）

## ui/window/

### `__init__.py`
- `MayaCodeEditor` などを公開

### `layout_manager.py`
ウィンドウ全体のレイアウト初期化（splitter、ツールバー、パネル配置、テーマ適用）。
セッション復元のスケジューリング（`QTimer.singleShot(100, restore)`）もここ。
- `UILayoutManager`

### `main.py`
メインウィンドウ。全コンポーネント（toolbar、code_editor、file_explorer、output_terminal、execution_manager、file_ops、shortcut_handler、layout_manager、session_manager）を保持・統合。
- `MayaCodeEditor(QWidget)`

### `shortcut_handler.py`
グローバルキーバインド（Ctrl+N／Ctrl+S／Ctrl+F／Ctrl+H／F2／F5 等）と find/replace ダイアログ管理。F2 は `language.completion_engine_factory is not None`（=Python）でゲートし、`command/refactor.py` と `ui/editor/rename_overlay.py` を遅延 import。
- `ShortcutHandler`

### `toolbar.py`
VSCode 風ツールバー。Run / Save / Save All / 新規（言語ごとボタン）/ シェルフ追加 / ターミナル切替 / ワードラップ等。
- `ToolBar`、`VSCodeButton`（アイコン状態をクリックで動的変化）

---

## utils/

### `__init__.py`
パッケージ宣言のみ。

### `maya_help_detector.py`
Maya コマンドのヘルプ URL を解決。モジュールエイリアス（`cmds → maya.cmds` 等）と
言語別ドキュメントロケーションを保持。
- `MayaHelpDetector`、`MAYA_ALIASES`、`SUPPORTED_LANGUAGES`

---

## 主要なエントリポイント早見表

| 起点 | ファイル | 主な処理 |
|------|---------|---------|
| FakeTools メニューから起動 | `main.py` `show_ui()` | → `MayaCodeEditor()` 構築・ドック化 |
| ウィンドウ初期化 | `ui/window/main.py` `MayaCodeEditor.__init__` | 全コンポーネント結線 |
| タブ作成 | `ui/tabs/widget.py` `new_file()` | `CodeEditor(language=...)` をタブに追加 |
| ファイルを開く | `ui/operations/files.py` `open_file_permanent()` → `ui/tabs/widget.py` 同名 | 既存タブ再利用 or 新規作成 |
| セッション復元 | `ui/tabs/session_manager.py` `restore_session_state()` | `restore_tab(info)` を逐次呼ぶ |
| Run | `ui/operations/execution_manager.py` `run_current_script()` | language 別 `NativeExecutionBridge` で実行 |
| シンタックスハイライト | `ui/editor/code_editor.py` `setup_syntax_highlighting()` | `language.highlighter_factory(document)` |
| オートインデント | `ui/editor/code_editor.py` `handle_return_key()` → `auto_indent.compute_indent()` | `language.indent_resolver` に委譲 |
| 折りたたみ | `ui/editor/code_folding.py` `CodeFoldingManager.detect_foldable_blocks()` | `language.folding_strategy.detect()` |
| オートコンプリート | `ui/autocomplete/controller.py` | `language.completion_engine_factory()`（None なら無効）|
| シンボルリネーム (F2) | `ui/window/shortcut_handler.py` `_handle_rename_symbol()` | `command/refactor.find_symbol_references()` → `ui/editor/rename_overlay.RenameOverlay` を起動（`completion_engine_factory` が None の言語では no-op）|
| Go to Line (Ctrl+G) | `ui/window/shortcut_handler.py` `_handle_show_goto_line_dialog()` | `ui/editor/goto_line_overlay.GoToLineOverlay(editor)` を都度生成（F2 リネームと同じシングルショット形式） |
| 右クリック | `ui/editor/context_menu.py` `build_context_menu()` | `language.context_menu_extender()` で拡張 |

---

## よくある作業 → 触るファイル

| やりたいこと | 触るファイル |
|------------|-------------|
| 新しい言語を追加 | `languages/<lang>/__init__.py` を作り `LanguageProfile` を組む。`languages/__init__.py` の `ALL_PROFILES` に追加 |
| ハイライト規則を変える | `highlighting/<lang>_highlighter.py` |
| 配色を変える | `themes/syntax_colors.json` または `themes/app_theme.py` |
| キーバインド追加 | エディタ内: `ui/editor/shortcuts.py`／グローバル: `ui/window/shortcut_handler.py` |
| 右クリックメニュー項目追加 | 共通: `ui/editor/context_menu.py`／言語固有: `languages/<lang>/actions.py` |
| ツールバーボタン追加 | `ui/window/toolbar.py` ＋ `ui/window/layout_manager.py` の `connect_signals` |
| ファイル操作を増やす | `ui/operations/files.py` ＋（必要なら）`command/file_ops.py` |
| 永続化したい設定を増やす | `settings/user_settings.py` のキーを足す |
| シンボルリネームのロジック／UI を触る | ロジック: `command/refactor.py`／UI: `ui/editor/rename_overlay.py`／F2 ゲート: `ui/window/shortcut_handler.py` `_handle_rename_symbol()` |
| Maya 実行ロジック | `command/execution.py` |

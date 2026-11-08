# Maya Code Editor

Monaco Editor を QWebEngineView に載せた Maya 用の Python スクリプトエディタ。
エディタ機能は Monaco 標準に任せ、自前で書くのは Maya 統合とファイル・タブ・セッションの最小限だけ。

対象: Maya 2023 以降。PySide6（2025+）と PySide2（2023 / 2024）の両方に対応し、Qt の違いは `maya_code_editor/qt.py` で吸収している。
同梱の Monaco は 0.44.0。Maya 2023 / 2024 の QtWebEngine（Chromium 83 / 87）で動く最新版で、それより新しい Monaco は読み込めない。

## 起動

Script Editor（Python）やシェルフボタン、自分のツールのメニューから:

```python
import sys
sys.path.insert(0, r"D:\claude\maya-code-editor")
import maya_code_editor
maya_code_editor.show_ui()
```

2 回目以降の `show_ui()` は既存のパネルを前面に出すだけ。
Maya 外で試す場合は `python -m maya_code_editor`（ターミナルは stdout 表示の簡易版）。

## 使い方

| 操作 | キー / 場所 |
|---|---|
| 実行（選択範囲、無ければ全文） | Ctrl+Enter / Run |
| 保存 / 新規 / タブを閉じる | Ctrl+S / Ctrl+N / Ctrl+W |
| すべて保存 | Ctrl+K → S、またはコマンドパレット（F1）の Maya: Save All |
| ワードラップ切替 | Alt+Z（settings.json に保存される） |
| 外部で変更されたファイル | 未編集のタブは自動で再読込。編集中なら Reload / Keep Mine を確認 |
| ファイル操作 | ツリーの右クリック（New File / New Folder / Rename / Delete / Reveal in Explorer / Refresh） |
| 複数選択 | Ctrl+クリック / Shift+クリック |
| 移動 | 中ボタンでドラッグしてフォルダへ（空白にドロップでルート） |
| 補完 | `.` を打つか識別子を 2 文字以上入力すると候補が出る（下記） |
| ターミナル表示切替 | ツールバーの Terminal |
| Echo All Commands / Show Stack Trace | ターミナルの右クリックメニュー |

エディタ内の操作（検索置換、マルチカーソル、折りたたみ、行移動など）は VS Code と同じキーバインド。

### 補完の仕組み

静的解析（jedi など）は使わず、Maya のセッションで生きているオブジェクトを `dir()` で覗く（Script Editor と同じ考え方）。

- `cmds.` / `om2.MFnMesh.` / 実行済みの変数 など、`__main__` から辿れるものはすべて対象
- バッファ内の `import` / `from ... import` 文は実行前でも解決する（`import os` と書けば `os.` が効く）
- 組み込み型（`str.` など）と、ドット無しの場合は組み込み関数・キーワード・`__main__` の名前
- コメントと文字列の中では出ない。`()` や `[]` を含む式は評価しない（副作用を避ける）
- 結果は式ごとにキャッシュし、コードを実行するたびに捨てる。起動時やバックグラウンドの処理は無い
- 候補の確定は Tab または Enter（Monaco 既定）。Enter を常に改行にしたい場合は settings.json に `"acceptSuggestionOnEnter": "off"` を書く。Esc で候補を閉じる

## ファイルの場所

| 内容 | パス |
|---|---|
| ワークスペース（ツリーのルート） | `~/Documents/maya/maya_code_editor_workspace`（環境変数 `MAYA_CODE_EDITOR_WORKSPACE` で変更） |
| 設定 | `~/Documents/maya/maya_code_editor/settings.json`（ツールバーの Settings で開く。反映は次回起動時） |
| セッション | `~/Documents/maya/maya_code_editor/session.json`（自動保存。開いていたタブと Untitled の下書き） |

`settings.json` の例:

```json
{
  "editor": { "theme": "dark-modern", "fontSize": 13, "tabSize": 4, "wordWrap": "off", "minimap": true },
  "terminal": { "echoAllCommands": false, "showStackTrace": true }
}
```

`editor` のキーは `theme` 以外そのまま Monaco に渡される（`IEditorOptions` の名前。VS Code の `editor.*` とほぼ同じ）。
例: `"lineNumbers": "relative"`, `"renderWhitespace": "boundary"`, `"cursorBlinking": "smooth"`, `"bracketPairColorization": {"enabled": true}`。
`minimap` だけは真偽値でも書ける。型が違う値は Monaco が既定値に戻す。

`theme` は `dark-modern`（既定）/ `light-modern`（VS Code から移植）か、Monaco 組み込みの `vs` / `vs-dark` / `hc-black` / `hc-light`。
移植テーマは `dev/convert_vscode_theme.py` で VS Code 同梱の JSON から生成している（`web/themes/*.js`）。
Monaco の Python トークン分けは VS Code より粗いので、関数名・変数名・制御キーワードの色分けは再現されない。

## 開発

```
python dev/maya_smoke.py              # Maya 2025 を起動して自動検証（ログは dev/out/）
python dev/maya_smoke.py --maya 2023  # 他のバージョンで検証
python dev/maya_smoke.py --standalone # Maya なしで同じ手順
```

検証は一時ワークスペースと一時設定フォルダを使うので、実データには触れない。
コードは `ruff format` / `ruff check` を通す。

## 構成

```
maya_code_editor/
├── main.py          QSplitter(WebView + ターミナル)、show_ui()、セッション保存
├── qt.py            PySide6 / PySide2 の切り替えシム
├── bridge/          QWebChannel で JS に公開する Python API
│   ├── channel.py   スロット定義（薄いラッパー）
│   ├── files.py     ワークスペース内のファイル操作
│   ├── execution.py 隠し cmdScrollFieldExecuter での実行
│   ├── config.py    settings.json / session.json
│   └── workspace.py ルートの解決
├── terminal/        cmdScrollFieldReporter（Maya）/ QPlainTextEdit（単体）
├── integration/     workspaceControl ドック
└── web/             index.html、css、js（bridge / dialogs / file_tree / tabs / app）、vendor/monaco
```

設計メモは `sample_docs/` を参照。

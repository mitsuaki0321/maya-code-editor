# Maya Code Editor

[English](README.md)

Monaco Editor を QWebEngineView に載せた、Maya 用の Python スクリプトエディタ。
編集機能は Monaco の標準機能をそのまま使い、自前で書いているのは Maya との統合と、
最小限のファイルツリー・タブ・セッション管理だけ。

対応: Maya 2023 以降。PySide6（2025 以降）と PySide2（2023 / 2024）の両方で動き、
違いは `maya_code_editor/qt.py` で吸収している。
同梱の Monaco は 0.44.0。Maya 2023 / 2024 に入っている QtWebEngine
（Chromium 83 / 87）で動く最新版で、これより新しい Monaco は読み込めない。

## 起動

Script Editor（Python）、シェルフボタン、自分のツールのメニューなどから:

```python
import sys
sys.path.insert(0, r"D:\claude\maya-code-editor")
import maya_code_editor
maya_code_editor.show_ui()
```

`show_ui()` をもう一度呼ぶと、既存のパネルが前面に出る。
Maya の外では `python -m maya_code_editor` で単体ウィンドウが開く
（ターミナルは標準出力を表示するだけの簡易版）。

## 使い方

| 操作 | キー / 場所 |
|---|---|
| 実行（選択範囲。選択が無ければバッファ全体） | Ctrl+Enter / テンキーの Enter / Run ボタン |
| エクスプローラを隠す / 出す | 境界線を左端までドラッグ（右へ引くと戻る）、境界線をダブルクリック、または Ctrl+B |
| 保存 / 新規 / タブを閉じる | Ctrl+S / Ctrl+N / Ctrl+W |
| すべて保存 | Ctrl+K の後に S、またはコマンドパレット（F1）の「Maya: Save All」 |
| ワードラップの切替 | Alt+Z（settings.json に保存される） |
| 補完 | `.` を打つか、識別子を 2 文字以上入力する（下記参照） |
| ディスク上で変更されたファイル | 未編集のタブは自動で再読込。編集中のタブは Reload / Keep Mine を確認 |
| ファイル操作 | ツリーを右クリック（New File / New Folder / Rename / Delete / Reveal in Explorer / Refresh） |
| 複数選択 | Ctrl+クリック / Shift+クリック |
| 移動 | 中ボタンでドラッグしてフォルダへ（空白にドロップするとルートへ） |
| ターミナルの表示切替 | ツールバーの Terminal ボタン |
| Echo All Commands / Show Stack Trace | ターミナルの右クリックメニュー |

編集操作（検索・置換、マルチカーソル、折りたたみ、行の移動など）は
VS Code と同じキーバインド。

### 補完の仕組み

静的解析は使っていない（jedi なし）。Maya のセッションで生きているオブジェクトを
`dir()` で調べる方式で、Script Editor と同じ考え方。

- `__main__` から辿れるものすべて: `cmds.`、`om2.MFnMesh.`、実行済みの変数、
  import 済みのサードパーティ製モジュール
- バッファ内の `import` / `from ... import` 行は実行前でも解決するので、
  `import os` と書けばすぐに `os.` が効く
- 組み込み型（`str.`）。ドットが無い場合は組み込み関数・キーワード・`__main__` の名前
- コメントと文字列の中では候補を出さない。`()` や `[]` を含む式は評価しない
  （副作用を起こさないため）
- 結果は式ごとにキャッシュし、コードを実行するたびに捨てる。
  起動時やバックグラウンドで動く処理は無い
- 候補の確定は Tab または Enter（Monaco の既定）。Enter を常に改行にしたい場合は
  settings.json に `"acceptSuggestionOnEnter": "off"` を書く。Esc で候補を閉じる

## ファイルの場所

| 内容 | パス |
|---|---|
| ワークスペース（ツリーのルート） | `~/Documents/maya/maya_code_editor_workspace`（環境変数 `MAYA_CODE_EDITOR_WORKSPACE` で変更） |
| 設定 | `~/Documents/maya/maya_code_editor/settings.json`（Settings ボタンで開く。反映は次回起動時） |
| セッション | `~/Documents/maya/maya_code_editor/session.json`（自動保存。開いていたタブと Untitled の下書き） |

## 設定

`settings.json` は、エディタが定義している全キーを書いた状態で作られる。
後のバージョンで増えたキーは次回起動時に既定値で補われ、自分で足したキーはそのまま残る。

```json
{
  "editor": { "theme": "dark-modern", "fontSize": 13, "tabSize": 4, "wordWrap": "off", "minimap": true },
  "terminal": { "echoAllCommands": false, "showStackTrace": true }
}
```

### Monaco の任意のオプション

`editor` セクションのキーは、`theme` を除いてそのまま Monaco のエディタオプションとして
渡される。つまり `IEditorOptions` の全項目が使える（名前は VS Code の `editor.*` 設定と同じ）。例:

```json
"editor": {
  "theme": "dark-modern",
  "fontSize": 13,
  "lineNumbers": "relative",
  "renderWhitespace": "boundary",
  "cursorBlinking": "smooth",
  "bracketPairColorization": { "enabled": true },
  "quickSuggestions": { "other": true, "comments": false, "strings": false },
  "acceptSuggestionOnEnter": "off"
}
```

`minimap` は真偽値でも書ける。型が違う値は Monaco が既定値に戻す。
アプリ側で設定しているオプション（`insertSpaces`、`mouseWheelZoom`、
`scrollBeyondLastLine`、`renderLineHighlight`）も同じ方法で上書きできる。

### テーマ

`theme` は `dark-modern`（既定）か `light-modern`（どちらも VS Code 同梱のテーマから変換）、
または Monaco 組み込みの `vs` / `vs-dark` / `hc-black` / `hc-light`。
ツールバー、ツリー、タブ、ダイアログも選んだテーマに追従する。

変換したテーマは `web/themes/*.js` にあり、`dev/convert_vscode_theme.py` が
VS Code の JSON ファイルから生成している。Monaco の Python トークナイザは
VS Code より粗いので、関数名・変数名・制御キーワードは色分けされない。

## 開発

```
python dev/maya_smoke.py              # Maya 2025 を起動して自動検証（ログは dev/out/）
python dev/maya_smoke.py --maya 2023  # 別の Maya バージョン
python dev/maya_smoke.py --standalone # Maya なしで同じ手順
```

検証は一時的なワークスペースと設定フォルダを使うので、実際のファイルには触れない。
コードは `ruff format` / `ruff check` で整形・チェックする。

## 構成

```
maya_code_editor/
├── main.py          QSplitter(WebView + ターミナル)、show_ui()、セッション保存
├── qt.py            PySide6 / PySide2 の切り替えシム
├── bridge/          QWebChannel 経由で JS に公開する Python API
│   ├── channel.py   スロット定義（薄いラッパー）
│   ├── files.py     ワークスペース内のファイル操作
│   ├── execution.py 隠し cmdScrollFieldExecuter による実行
│   ├── completion.py ライブオブジェクトを使った補完
│   ├── config.py    settings.json / session.json
│   └── workspace.py ワークスペースルートの解決
├── terminal/        cmdScrollFieldReporter（Maya）/ QPlainTextEdit（単体）
├── integration/     workspaceControl ドッキング
└── web/             index.html、css、js（bridge / dialogs / completion / file_tree / tabs / app）、themes、vendor/monaco
```

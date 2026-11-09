# Maya Code Editor

[English](README.md)

Maya で Python スクリプトを書いて実行するためのエディタです。

編集部分には VS Code と同じ Monaco Editor を使っているので、検索・置換、マルチカーソル、
折りたたみなどを VS Code と同じ操作で使えます。実行結果は Script Editor と同じ形式で
ターミナルに表示されます。

対応バージョン: Maya 2023 以降

## 起動

Script Editor の Python タブで次を実行します。パスはこのリポジトリを置いた場所に合わせてください。

```python
import sys
sys.path.insert(0, r"D:\claude\maya-code-editor")
import maya_code_editor
maya_code_editor.show_ui()
```

シェルフボタンや自分のツールのメニューに登録しておくと便利です。

## 使い方

### 実行

| 操作 | キー |
|---|---|
| 実行 | Ctrl+Enter、テンキーの Enter、または Run ボタン |

選択範囲があればその部分だけを、無ければファイル全体を実行します。

### ファイルとタブ

| 操作 | キー / 場所 |
|---|---|
| 保存 | Ctrl+S |
| すべて保存 | Ctrl+K の後に S |
| 新規ファイル | Ctrl+N |
| タブを閉じる | Ctrl+W |
| 新規作成・名前変更・削除など | 左のツリーを右クリック |
| 複数選択 | Ctrl+クリック、Shift+クリック |
| ファイルやフォルダの移動 | 中ボタンでドラッグして移動先のフォルダへ |

他のエディタでファイルが変更された場合、編集していないタブは自動で読み直します。
編集中のタブは、読み直すか自分の内容を残すかを確認します。

開いていたタブと、保存していない新規ファイルの内容は、次回起動時に復元されます。

### 表示

| 操作 | キー / 場所 |
|---|---|
| ツリーを隠す / 出す | Ctrl+B、境界線をダブルクリック、または境界線を左端までドラッグ |
| ターミナルを隠す / 出す | ツールバーの Terminal ボタン |
| 折り返しの切替 | Alt+Z |
| コマンドパレット | F1 |

ターミナルを右クリックすると、Echo All Commands と Show Stack Trace を切り替えられます。

### 補完

`.` を打つか、名前を 2 文字以上入力すると候補が出ます。Tab で確定、Esc で閉じます。

- `cmds.` や `om2.MFnMesh.` など、Maya のモジュールのメンバー
- `import os` のようにファイル内で import しているモジュール（実行前でも効きます）
- すでに実行して作った変数
- Python の組み込み関数とキーワード

コメントと文字列の中では候補は出ません。

## 設定

ツールバーの Settings ボタンで `settings.json` が開きます。変更は次回起動時に反映されます。

```json
{
  "editor": { "theme": "dark-modern", "fontSize": 13, "tabSize": 4, "wordWrap": "off", "minimap": true },
  "terminal": { "echoAllCommands": false, "showStackTrace": true }
}
```

### テーマ

`theme` には次のどれかを指定します。

| 値 | 内容 |
|---|---|
| `dark-modern` | VS Code の Dark Modern（既定） |
| `light-modern` | VS Code の Light Modern |
| `vs-dark` / `vs` | Monaco 標準のダーク / ライト |
| `hc-black` / `hc-light` | ハイコントラスト |

### その他のエディタ設定

`editor` には、VS Code の `editor.*` と同じ名前の設定をそのまま書けます。よく使うものは次のとおりです。

| 設定 | 値の例 | 内容 |
|---|---|---|
| `fontSize` | `13` | 文字の大きさ |
| `fontFamily` | `"Consolas"` | フォント |
| `tabSize` | `4` | インデントの幅 |
| `insertSpaces` | `true` | Tab キーで空白を入れる |
| `wordWrap` | `"off"` / `"on"` | 長い行を折り返す |
| `minimap` | `true` / `false` | 右端の縮小表示 |
| `lineNumbers` | `"on"` / `"off"` / `"relative"` | 行番号の表示 |
| `renderWhitespace` | `"none"` / `"boundary"` / `"all"` | 空白文字を見えるようにする |
| `rulers` | `[88]` | 指定した桁に縦線を引く |
| `cursorStyle` | `"line"` / `"block"` / `"underline"` | カーソルの形 |
| `cursorBlinking` | `"blink"` / `"smooth"` / `"solid"` | カーソルの点滅 |
| `mouseWheelZoom` | `true` | Ctrl+ホイールで文字サイズを変える |
| `scrollBeyondLastLine` | `false` | 最終行より下までスクロールできるようにする |
| `acceptSuggestionOnEnter` | `"on"` / `"off"` | `"off"` にすると、補完候補が出ていても Enter は常に改行 |
| `quickSuggestions` | `true` / `false` | 入力中に補完候補を自動で出す |

書き方の例:

```json
"editor": {
  "theme": "dark-modern",
  "fontSize": 14,
  "lineNumbers": "relative",
  "rulers": [88],
  "acceptSuggestionOnEnter": "off"
}
```

ここに無い設定も使えます。全部の一覧は [Monaco Editor の API リファレンス](https://microsoft.github.io/monaco-editor/typedoc/interfaces/editor_editor_api.editor.IEditorOptions.html)（英語）にあります。

## ファイルの場所

| 内容 | パス |
|---|---|
| ワークスペース（ツリーに表示されるフォルダ） | `~/Documents/maya/maya_code_editor_workspace` |
| 設定 | `~/Documents/maya/maya_code_editor/settings.json` |
| セッション（開いていたタブなど） | `~/Documents/maya/maya_code_editor/session.json` |

ワークスペースの場所は、環境変数 `MAYA_CODE_EDITOR_WORKSPACE` で変更できます。

## 開発者向け

### 仕組み

- 画面は QWebEngineView 上の HTML で、Python とは QWebChannel でやり取りします。ターミナルだけは Maya の `cmdScrollFieldReporter` を使った Qt のウィジェットです
- PySide6（Maya 2025 以降）と PySide2（Maya 2023 / 2024）の違いは `maya_code_editor/qt.py` で吸収しています
- 同梱の Monaco は 0.44.0 です。Maya 2023 / 2024 の QtWebEngine で動く最新版で、これより新しいものは読み込めません
- 補完は静的解析ではなく、Maya のセッションで生きているオブジェクトを `dir()` で調べています。起動時やバックグラウンドで動く処理はありません
- テーマは `dev/convert_vscode_theme.py` で VS Code のテーマファイルから変換しています。Monaco の Python の色分けは VS Code より粗く、関数名や変数名は色分けされません

### テスト

```
python dev/maya_smoke.py              # Maya 2025 を起動して自動検証（ログは dev/out/）
python dev/maya_smoke.py --maya 2023  # 別の Maya バージョン
python dev/maya_smoke.py --standalone # Maya なしで同じ手順
python -m maya_code_editor            # Maya なしで単体ウィンドウを開く
```

テストは一時的なワークスペースと設定フォルダを使うので、実際のファイルには触れません。
コードは `ruff format` と `ruff check` を通します。

### 構成

```
maya_code_editor/
├── main.py          ウィンドウ本体、show_ui()、セッション保存
├── qt.py            PySide6 / PySide2 の切り替え
├── bridge/          JS に公開する Python API（実行、ファイル操作、補完、設定）
├── terminal/        ターミナル
├── integration/     Maya へのドッキング
└── web/             画面（HTML / CSS / JS）、テーマ、Monaco
```

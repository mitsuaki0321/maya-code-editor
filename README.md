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
| ターミナル表示切替 | ツールバーの Terminal |
| Echo All Commands / Show Stack Trace | ターミナルの右クリックメニュー |

エディタ内の操作（検索置換、マルチカーソル、折りたたみ、行移動など）は VS Code と同じキーバインド。

## ファイルの場所

| 内容 | パス |
|---|---|
| ワークスペース（ツリーのルート） | `~/Documents/maya/maya_code_editor_workspace`（環境変数 `MAYA_CODE_EDITOR_WORKSPACE` で変更） |
| 設定 | `~/Documents/maya/maya_code_editor/settings.json`（ツールバーの Settings で開く。反映は次回起動時） |
| セッション | `~/Documents/maya/maya_code_editor/session.json`（自動保存。開いていたタブと Untitled の下書き） |

`settings.json` の例:

```json
{
  "editor": { "fontSize": 13, "tabSize": 4, "wordWrap": "off", "minimap": false },
  "terminal": { "echoAllCommands": false, "showStackTrace": true }
}
```

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

# ROADMAP — tkouter

tkouter の開発ロードマップ。

---

## 直近（v0.2.x）

### 型ヒント強化

- [ ] デコレータ引数の TypedDict / Protocol 化（Pyright/mypy 補完）
- [ ] tkinter 定数を活かした Literal 型（`tk.LEFT`, `tk.RIGHT`, `tk.NSEW` など）
- [ ] `_GridBuilder.columnconfigure` 相当の fluent API

### ウィジェット拡張

- [x] ttk widget 対応（ttk.Button, ttk.Entry, ttk.Notebook など）
- [x] `@app.notebook` デコレータ（マルチタブ）
- [ ] `bind` イベントの decorator 登録

### A11y 実適用

- [ ] Tk 9.1 `::tk::accessible::*` への role/name 結線
- [ ] `WidgetSpec.role` → 実際の accessibility 属性反映

### Layout DSL 充実

- [x] `grid` の `rowconfigure` / `columnconfigure` 相当（`col_weights`/`row_weights`/`rowspan`）
- [ ] ネストフレーム（`Layout` 内で `Layout` を入れ子に）
- [ ] `padx`/`pady` のデフォルト値一元設定

### 公開ランタイム API

- [x] `build_widgets()`, `widget()`, `widget_kind()`, `widget_specs()`
- [x] `apply_state()`, `sync()` — カスタムランナーから再利用可能
- [x] `app.run(notebook="...")` エントリポイント

### Agent / LLM 連携

- [ ] `schema()` を Function Calling 定義としての露出改善
- [ ] `@agent_tool` 統合（GUI 操作をエージェント語彙として扱う）

---

## 中長期

### ttk Style レイヤー

- [ ] `Layout.style("my_button", background=..., font=...)` 的なスタイル定義
- [ ] テーマ切替（`ttk.Style().theme_use(...)`）

### 非同期ジョブ統合

- [x] `app.run_async()` + `app.spawn()` — async event loop と Tk の共存
- [x] `app.spawn(asyncio.to_thread(...))` で非ブロッキングバックグラウンドジョブ
- [x] 実例同期版: `disk_usage_flat_viewer.py`
- [x] 実例非同期版: `disk_usage_flat_async.py`（`app.run_async()` + `app.spawn()`）
- [x] `@app.job(name)` 連携 — async コールバックの @app デコレータ登録

### 宣言的コンポーネント

- [ ] `Layout` に代わる `@app.component` デコレータ（React ライクな再利用）
- [ ] state の型定義とバリデーション（ただし Pydantic は使わない）

### テスト

- [ ] ヘッドレス実行テスト（`TKOUTER_HEADLESS=1`）
- [ ] WidgetSpec 単位のユニットテスト

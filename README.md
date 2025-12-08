# FormXtract – フォーム用 OCR & CSV 出力ツール

スキャンした申込書・アンケート・帳票などから、**指定した枠（ROI）だけを OCR して、行単位の CSV に出力する**ためのデスクトップツールです。  
「毎回同じフォームを手入力で打ち込む」作業を、**プリセット化 + 一括 OCR + CSV 書き出し**で置き換えることを目的にしています。fileciteturn9file2turn12file2

---

## 🚀 なにができるツールか

- 画像上の「取り出したい枠」を ROI（矩形）として複数定義
- ROI の読み取り順序と、CSV 上での行レイアウトを `{1}{2}{3}` のようなテンプレで指定
- PaddleOCR を使って日本語含むテキストを読み取り
- 全フィールドに対して **安全な正規化（trim / 全角→半角 / 空白圧縮 / ゼロ幅文字除去）** を実施fileciteturn8file5turn9file2
- 列ごとに「電話番号だけ数字抽出」「金額から単位を除去」などのポストプロセスルールを適用
- 結果を CSV として **追記モード／上書きモード** で書き出し（BOM・改行コードも制御可能）fileciteturn10file2
- 複数画像を **バックグラウンドスレッドで順次 OCR** しつつ、進捗バーとログで状況を把握fileciteturn12file0turn12file4
- ROI・レイアウトなどを「プリセット」として JSON 保存／複製／リネーム可能fileciteturn14file1turn14file2

---

## 🖼 想定ユースケース

- 同じフォーマットの申込書を大量にスキャンしている
- 住所や電話番号・金額など、特定の欄だけを集計したい
- 既存の RPA や Excel マクロに渡す前処理として CSV がほしい
- 「OCR 結果を目視で修正 → CSV に追記」というループを回したい

---

## 🧩 主な構成と責務

### アプリ層（core/app）

- `core/app/constants.py`  
  - アプリ名、バージョン、動作モード（DEV / AppData 保存）、UI 既定値、OCR 設定、ポストプロセス設定などを一括管理。fileciteturn9file2  
  - 例：
    - `APP_NAME = "FormXtract"`
    - `OCR_IMPL = "paddle"`（OCR エンジン選択）  
    - `PADDLE_LANG`, `PADDLE_USE_ANGLE_CLS`（PaddleOCR の言語・角度補正）  
    - `PP_TRIM`, `PP_COMPRESS_SPACES`, `PP_ASCII_DIGIT_ZEN2HAN`, `PP_REMOVE_ZERO_WIDTH`  
    - 列別ルール `PP_BY_COL = {0: ["phone_digits"], 2: ["money_number"], ...}`

- `core/app/app_paths.py`  
  - AppData の格納先やプリセットフォルダのパスを OS ごとに解決。fileciteturn9file1  
  - `DEV_MODE = True` のときはプロジェクト直下、それ以外は  
    - Windows: `%LOCALAPPDATA%\\<ORG_NAME>\\<APP_NAME>`  
    - macOS: `~/Library/Application Support/<APP_NAME>`  
    - Linux: `~/.local/share/<APP_NAME>`  
  - `presets_dir()` では、初回起動時に `assets/presets` や旧 `root/presets` から JSON をマイグレーションする仕組みも持つ。

- `core/app/datastore.py` – DataStore  
  - `appdata.json` を介して軽量な KV ストアとして動作。fileciteturn9file3  
  - ウィンドウ状態、ユーザー設定、最近使ったプリセット名などを保存。  
  - JSON の書き込みは `.tmp` に出力 → `os.replace` で原子的に切り替え。

- `core/app/window_state.py` – ウィンドウ位置・サイズの永続化  
  - `bind_with_datastore(win, ds, ...)` で QMainWindow にイベントフィルタを仕込み、  
    - 起動時にジオメトリ復元  
    - 終了時に `saveGeometry()` / 最大化状態を DataStore に保存fileciteturn9file4  

- `core/app/__init__.py`  
  - `C`, `DataStore`, `bind_with_datastore`, `appdata_dir`, `presets_dir` を公開する薄い API。fileciteturn9file0  
  - UI 層からは `from core.app import C, DataStore` のように利用する想定。

---

### CSV I/O 層（core/csvio）

- `core/csvio/layout.py` – LayoutPlan  
  - `{1}{2}{3}` や `{4}{}{5}` といったレイアウト文字列をパースして、  
    「何列目にフィールド何番を置くか」を内部表現に変換。fileciteturn10file1  
  - `{}`（中身なし）は「空セル」として扱い、固定の空列を作ることができる。
  - `materialize(fields)` で、プリセットで定義された ROI の結果配列から、行列形式の 2 次元リストを生成。

- `core/csvio/writer.py` – write_rows  
  - OCR 後の 2 次元リストを CSV に書き出す関数。fileciteturn10file2  
  - `append=True` の場合：既存ファイルに追記（存在しない場合のみ BOM 付き UTF-8 などを考慮）  
  - `append=False` の場合：`.tmp` ファイルに書き出してから `os.replace` で原子的に上書き。  
  - `CSV_BOM_UTF8` や `CSV_NEWLINE` の設定値は `core/app/constants.py` から取得。

---

### 画像ユーティリティ層（core/image）

- `core/image/io_utils.py`（推測）  
  - 画像ファイルの読み込み／保存、形式変換など。

- `core/image/qimage_convert.py`  
  - QImage と NumPy 配列 (BGR/RGB) の相互変換を担当。fileciteturn12file3  
  - OCR パイプラインに渡すため、GUI で扱う QImage を確実に OpenCV が扱える形へ変換。

---

### OCR パイプライン層（core/ocr）

#### パッケージエントリ

- `core/ocr/__init__.py`  
  - `ocr_single_image`, `OCRTask`, `OCRWorker` を公開。fileciteturn12file0  

#### エンジン選択（core/ocr/engines）

- `core/ocr/engines/__init__.py` – get_engine  
  - `constants.OCR_IMPL` を見て使用する OCR エンジンを決定。fileciteturn13file0turn9file2  
  - 現状 `"paddle"` のみ実装しており、シングルトンとして `PaddleEngine` を使い回す。

- `core/ocr/engines/paddle.py` – PaddleEngine  
  - PaddleOCR の薄いラッパ。fileciteturn13file1turn12file1  
  - `PADDLE_LANG`, `PADDLE_USE_ANGLE_CLS` などを `constants` から取得して初期化。  
  - `read_text(img_rgb_uint8)` で、1 画像の認識結果を 1 行の文字列として返却（複数行の結果は連結）。

#### 前処理・ROI 抽出（core/ocr/preprocess.py）

- QImage → BGR → グレースケール → バイラテラルフィルタ → 二値化 → アップスケール、  
  という一連の前処理を行う。すべて `constants` で有効 / 無効を切り替え可能。fileciteturn12file3turn9file2  

  - `qimage_to_bgr(qimage)`  
  - `bilateral(gray)`（`PREPROCESS_BILATERAL` で ON/OFF）  
  - `binarize(gray)`（Otsu 法、`PREPROCESS_BINARIZE` で ON/OFF）  
  - `upscale(img)`（`UPSCALE_FACTOR` で倍率指定）  
  - `rotate_if_needed(img, orientation)` – ROI に設定された向き（auto/0/90/180/270）に応じて回転  
  - `crop_to_roi(img, x, y, w, h)` – ROI 領域の切り出し

#### OCR パイプライン（core/ocr/pipeline.py）

- `ocr_single_image(qimage, preset)` が中核。fileciteturn12file2turn14file1turn10file1turn8file5  
  1. `qimage` を BGR に変換  
  2. プリセットに定義された ROI を順番に走査  
  3. 各 ROI ごとに：
     - `crop_to_roi` → `rotate_if_needed` → グレースケール → 前処理 → RGB へ変換  
     - `engine.read_text(rgb)` でテキスト認識  
     - `normalize_global()` で安全な正規化（trim / 全角英数→半角 / 空白圧縮 / ゼロ幅文字除去）  
  4. ROI ごとの値を `fields: List[str]` として保持  
  5. `LayoutPlan(preset.layout_text)` で CSV 行の形に展開  
  6. 各行に対して `apply_rules_to_row(row)` を呼び、列別ルールを適用  
  7. `List[List[str]]`（CSV 1 枚分の行リスト）として返却

#### ポストプロセス（core/postprocess.py）

- 全フィールドにかかる「安全系」正規化：fileciteturn8file5turn9file2  
  - `normalize_global(s)`  
    - ゼロ幅文字除去（`\u200B-\u200D\uFEFF`）  
    - 全角スペース → 半角スペース  
    - 連続空白 → 1 スペースに圧縮  
    - 先頭・末尾の空白を strip  
    - オプションで全角英数のみ半角化（`PP_ASCII_DIGIT_ZEN2HAN`）

- 列ごとの追加ルール（`PP_BY_COL` で列番号 → ルール名を設定）：  
  - `phone_digits` → 数字以外を除去（電話番号用）  
  - `money_number` → カンマ / 通貨記号 / 「円」などを削ぎ落として数字だけ抽出（金額用）  
  - `date_std` → 多様な日付表記を **ざっくり YYYY-MM-DD** に正規化（年・月・日を拾って判定）  

---

### OCR ワーカー（core/ocr/worker.py）

- `OCRTask` dataclass  
  - `qimage`, `preset`, `display_name` を持つ 1 件分の処理単位fileciteturn12file4turn12file2turn14file1  

- `OCRWorker(QtCore.QThread)`  
  - 複数の `OCRTask` をキューとして受け取り、バックグラウンドで `ocr_single_image` を順次処理。  
  - シグナル：
    - `sig_progress(int)` – 0〜100% の進捗通知  
    - `sig_log(str)` – UI に表示するログメッセージ  
    - `sig_done(list)` – 各タスクの結果 `{"name", "rows", "ok", "error"}` の配列  

  - `ALLOW_INTERRUPT` が有効な場合、`requestInterruption()` で安全に中断可能（例：キャンセルボタン）。fileciteturn12file4turn9file2  

---

### プリセット管理（core/presets）

- `core/presets/models.py` – ROI / Preset モデルfileciteturn14file1  
  - `ROI(x, y, w, h, orientation="auto")`  
  - `Preset(name, image_w, image_h, rois, layout_text)`  
  - `layout_text` には `{1}{2}{3}` のようなテンプレ文字列を持ち、これが CSV 行の並び順を決める。  
  - `to_dict()` / `from_dict()` で JSON シリアライズ／デシリアライズ。

- `core/presets/store.py` – JSON I/O と管理fileciteturn14file2turn9file1  
  - `list_names()` – `presets_dir()` 以下の `*.json` からプリセット名一覧を取得  
  - `load(name)` / `save(preset, name)` – JSON での読み書き  
  - `duplicate(name)` – `<name>_copy`, `<name>_copy2` … と自動採番して複製  
  - `delete(name)` – 削除  
  - `rename(old, new)` – 重複を避けつつリネームし、JSON 内の `name` も更新  
  - 書き込みは `_atomic_write_json()` で `.tmp` に書いてから `os.replace`。

- `core/presets/__init__.py`  
  - `ROI`, `Preset` と各種操作関数（list/load/save/duplicate/delete/rename/exists）を公開。fileciteturn14file0  

---

## 📂 プロジェクト構成（フォルダ構成）

あなたのスクリーンショットとアップロードファイルからみた、実際の構成イメージです：

```text
FormXtract/
│
├─ main.py                # アプリ起動・メインウィンドウ生成
├─ mainview.py            # メイン画面（画像表示 / ROI 編集 / 結果表示）の UI ロジック
├─ hook-paddleocr.py      # PaddleOCR 用のフック／セットアップスクリプト
├─ preset.py              # プリセット編集ダイアログなど（UI 側）
├─ postprocess.py         # （core/postprocess.py に配置されている実装本体）
│
└─ core/
    ├─ app/
    │   ├─ __init__.py
    │   ├─ app_paths.py
    │   ├─ constants.py
    │   ├─ datastore.py
    │   └─ window_state.py
    │
    ├─ csvio/
    │   ├─ __init__.py
    │   ├─ layout.py
    │   └─ writer.py
    │
    ├─ image/
    │   ├─ __init__.py
    │   ├─ io_utils.py
    │   └─ qimage_convert.py
    │
    ├─ ocr/
    │   ├─ __init__.py
    │   ├─ pipeline.py
    │   ├─ preprocess.py
    │   ├─ worker.py
    │   └─ engines/
    │       ├─ __init__.py
    │       └─ paddle.py
    │
    └─ presets/
        ├─ __init__.py
        ├─ models.py
        └─ store.py
```

※ 一部 UI ファイル（`mainview.py` や `preset.py` など）は中身を省略していますが、  
　上記のコアモジュール群を組み合わせて **フォーム画像 → CSV** のワークフローを構成しています。

---

## ▶ 初回起動時

- `DEV_MODE` が `True` ならプロジェクト直下に `appdata.json` / `presets/` が作成されます。fileciteturn9file1turn9file2  
- `DEV_MODE = False` にすると OS 標準の AppData 配下に保存される想定です。

---

## 💡 ポイント

- **PaddleOCR ベースの OCR パイプライン実装**  
  - QImage → NumPy(OpenCV) → 前処理 → PaddleOCR → テキスト正規化 → CSV 行、という一連の流れをモジュール単位で分離。fileciteturn12file1turn12file2turn12file3turn8file5  

- **安全志向のポストプロセス設計**  
  - 「壊しにくい順」で正規化を行い、怪しいケースは原文を返すポリシー。  
  - 電話番号・金額・日付など、よくある業務項目向けの簡易ルールを列ごとに適用可能。

- **AppData / presets の永続化レイヤーの切り出し**  
  - パス解決 / JSON 保存 / ウィンドウ状態管理を `core/app` にまとめ、UI 側からはシンプルな API で利用できるようにしている。fileciteturn9file0turn9file1turn9file3turn9file4  

- **QThread ベースの OCR ワーカー**  
  - 長時間かかる OCR 処理を UI スレッドから完全に切り離し、途中キャンセル／進捗 UI と連携。fileciteturn12file4  

- **プリセットの JSON モデル化**  
  - ROI / レイアウトをデータクラスで定義し、`Preset` として JSON 保存・複製・リネームできる仕組みを構築。fileciteturn14file1turn14file2  

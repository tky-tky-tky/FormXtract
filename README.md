# FormXtract – フォーム用 OCR & CSV 出力ツール

スキャンした申込書・アンケート・帳票などから、指定した枠（ROI）だけを OCR して、行単位の CSV に出力するためのデスクトップツールです。

「毎回同じフォームを手入力して打ち込む」作業を、プリセット化 + 一括 OCR + CSV 書き出しで置き換えることを目的にしています。

---

## 🚀 なにができるツールか

- 画像上の「取り出したい枠」を ROI（矩形）として複数定義  
- ROI の読み取り順序と、CSV 上での行レイアウトを `{1}{2}{3}` のようなテンプレで指定  
- PaddleOCR を使って日本語含むテキストを読み取り  
- 全フィールドに対して安全な正規化（trim / 全角→半角 / 空白圧縮 / ゼロ幅文字除去）を実施  
- 列ごとに「電話番号だけ数字抽出」「金額から単位を除去」などのポストプロセスルールを適用  
- 結果を CSV として追記モード／上書きモードで書き出し  
- 複数画像をバックグラウンドスレッドで順次 OCR しつつ、進捗バーとログで状況を把握  
- ROI・レイアウトなどを「プリセット」として JSON 保存／複製／リネーム可能  

---

## 🧩 主な構成と責務

### アプリ層（core/app）

- **constants.py**  
  アプリ名、バージョン、OCR 設定、ポストプロセス設定、UI の既定値などを管理。

- **app_paths.py**  
  AppData の格納先やプリセットフォルダのパスを OS ごとに解決。  
  DEV モードではプロジェクト直下、本番モードでは OS の標準 AppData を使用。

- **datastore.py**  
  appdata.json を KV ストアとして扱う軽量永続化レイヤー。  
  JSON 保存は `.tmp` → `replace` により確実に行われる。

- **window_state.py**  
  ウィンドウ位置・サイズを保存・復元するヘルパ。

- **__init__.py**  
  C, DataStore, bind_with_datastore, appdata_dir, presets_dir を公開。

---

## CSV I/O 層（core/csvio）

- **layout.py – LayoutPlan**  
  `{1}{2}{3}` や `{4}{}{5}` のようなテンプレ文法をパースし、  
  「何番の ROI を CSV のどの列に配置するか」を定義する。

- **writer.py – write_rows**  
  OCR 結果を CSV に書き込む処理。  
  BOM の扱い、追記モード／上書きモード、原子的な保存（.tmp → replace）など、実運用を想定した堅牢仕様。

---

## 画像ユーティリティ層（core/image）

- **io_utils.py**  
  画像の読み込みや共通 I/O ヘルパ。

- **qimage_convert.py**  
  QImage ⇄ NumPy(OpenCV) の RGB/BGR 変換。  
  GUI と OCR パイプラインをつなぐ重要モジュール。

---

## OCR パイプライン層（core/ocr）

### エントリ

- **__init__.py**  
  ocr_single_image, OCRTask, OCRWorker を公開する窓口。

### エンジン層（core/ocr/engines）

- **engines/__init__.py – get_engine**  
  OCR_IMPL の設定値を見て OCR エンジンを選択する抽象レイヤー。  
  PaddleOCR 以外の OCR に差し替える拡張性を持つ。

- **engines/paddle.py – PaddleEngine**  
  PaddleOCR を初期化し、1 枚の画像から 1 行分のテキストを抽出する軽量 API。

### 前処理（core/ocr/preprocess.py）

- ROI 切り出し、回転補正  
- グレースケール、バイラテラルフィルタ、二値化  
- アップスケール  
- すべて constants.py の設定で ON/OFF 可能  

### パイプライン本体（core/ocr/pipeline.py）

1. QImage を BGR に変換  
2. プリセット内のすべての ROI を走査  
3. ROI ごとに前処理  
4. OCR（PaddleEngine）  
5. グローバル正規化（trim / 半角化 / 空白圧縮 / ゼロ幅文字除去）  
6. LayoutPlan に従って CSV 行へ展開  
7. 列別ポストプロセスルールの適用  
8. 2 次元リストとして返却  

### OCR ワーカー（core/ocr/worker.py）

- QThread でバックグラウンド処理  
- 進捗、ログ、完了イベントを emit  
- 中断（interrupt）にも対応  
- GUI をブロックしない OCR を実現する中心モジュール

---

## プリセット管理（core/presets）

- **models.py**  
  ROI や Preset のデータモデル。  
  JSON にシリアライズ可能で、UI と OCR パイプラインの橋渡し役。

- **store.py**  
  プリセットの JSON 保存・読み込み・複製・削除・リネームを管理。  
  保存は `.tmp → replace` により安全。

- **__init__.py**  
  ROI, Preset とストア関連関数を公開。

---

## 📂 プロジェクト構成

```
FormXtract/
│
├─ main.py
│    アプリのエントリポイント。UI の初期化とイベントループ開始を担当。
│
├─ mainveiw.py
│    ルート側のメイン画面ロジック。
│    ・アプリ起動時に最初に読み込まれる UI
│    ・画像表示、ROI のプレビュー、メイン操作の受け口
│
├─ hook-paddleocr.py
│    PaddleOCR の初期セットアップ用スクリプト。
│    モデルダウンロードや import 時のフックなどをまとめている。
│
├─ appdata.json
│    プリセット、設定、ウィンドウ状態などの永続データ。
│
├─ inbox.csv
│    出力先 / 入力テンプレートとして利用されるサンプル CSV。
│
├─ README.md
│
└─ core/
    ├─ app/
    │   ├─ __init__.py
    │   ├─ app_paths.py
    │   │      AppData / Presets の保存ディレクトリを OS ごとに解決。
    │   │      開発時はローカル、本番時はユーザー領域へ自動切替。
    │   ├─ constants.py
    │   │      OCR 設定・前処理設定・UI 設定などのアプリ全体の定数を集中管理。
    │   ├─ datastore.py
    │   │      appdata.json の読み書きを行う軽量データストア。
    │   │      JSON は「tmp → replace」で安全に書き込み。
    │   └─ window_state.py
    │          ウィンドウ位置・サイズの保存と復元を担当。
    │
    ├─ csvio/
    │   ├─ __init__.py
    │   ├─ layout.py
    │   │      {1}{2}{3} のようなレイアウトテンプレートを解析し、
    │   │      ROI 番号 → CSV 列配置 の変換ルールを生成。
    │   └─ writer.py
    │          CSV 出力の実装。追記・上書きモード、BOM 制御、原子的保存に対応。
    │
    ├─ image/
    │   ├─ __init__.py
    │   ├─ io_utils.py
    │   │      画像のロードや基本入出力ヘルパ。
    │   └─ qimage_convert.py
    │          QImage ↔ OpenCV(Numpy) の変換処理。
    │          GUI と OCR パイプラインの橋渡しを行う重要モジュール。
    │
    ├─ ocr/
    │   ├─ __init__.py
    │   │      OCRTask や OCRWorker など OCR の外部 API をまとめて公開。
    │   ├─ paddle.py
    │   │      PaddleOCR ラッパ（旧版？）。engines/paddle とは別用途で存在。
    │   ├─ pipeline.py
    │   │      OCR 全処理の中心。
    │   │      ・ROI の切り出し
    │   │      ・前処理（ノイズ除去、二値化など）
    │   │      ・OCR 実行
    │   │      ・正規化（trim / 全角→半角 / 空白圧縮 / ゼロ幅除去）
    │   │      ・CSV 行生成
    │   ├─ preprocess.py
    │   │      画像前処理（回転補正、バイラテラル、二値化、アップスケールなど）。
    │   ├─ worker.py
    │   │      QThread によるバックグラウンド OCR 実行。
    │   │      UI をブロックしない進捗通知・ログ通知を担当。
    │   └─ engines/
    │        ├─ __init__.py
    │        │      OCR_IMPL に応じて OCR エンジンを切り替える拡張ポイント。
    │        └─ paddle.py
    │               現行の PaddleOCR エンジン実装の本体。
    │               1ROI → テキスト抽出のシンプル API を提供。
    │
    ├─ presets/
    │   ├─ __init__.py
    │   ├─ models.py
    │   │      ROI（矩形）・Preset（ROI 集合＋レイアウト）のデータモデル。
    │   │      JSON 化可能で UI / OCR の橋渡しを行う。
    │   ├─ store.py
    │   │      プリセットの保存・読み込み・複製・削除・リネーム。
    │   │      保存は tmp → replace で安全に実行。
    │   └─ postprocess.py
    │          テキスト後処理ルール（電話番号抽出・単位削除など）を定義。
    │
    └─ ui/
        ├─ __init__.py
        ├─ mainveiw.py
        │      メイン UI ロジック本体。
        │      画像プレビュー、ROI 編集、OCR 実行ボタンなど画面操作の中心。
        │      root 側 mainveiw.py と名前が共通だが、こちらは UI クラス定義側。
        ├─ preset.py
        │      プリセット編集画面（ROI 追加・削除・順序変更）。
        └─ （必要に応じてここに UI コンポーネントが増える構造）


---

## ▶ 初回起動時 

- `DEV_MODE` が `True` ならプロジェクト直下に `appdata.json` / `presets/` が作成されます。
- `DEV_MODE = False` にすると OS 標準の AppData 配下に保存される想定です。

---

## 💡 ポイント

- PaddleOCR を活かしつつ、  
  独自の **前処理 → OCR → 正規化 → レイアウト → CSV** パイプラインを構築
- ROI とレイアウトをプリセット化し、  
  「同じ帳票を大量処理」する現場に最適化
- QThread によるノンブロッキングの OCR ワーカー
- AppData / presets / window state / datastore の分離で堅牢な設計
- JSON ベースのプリセット管理で、OCR フローを柔軟にカスタム可能


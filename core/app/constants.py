# -*- coding: utf-8 -*-

# ===== アプリ識別（表示名やAppData名に使用） =====
APP_NAME = "FormXtract"
APP_VERSION = "0.2.0"
ORG_NAME = "tky-tky-tky"

# ===== モード／保存先 =====
# True: プロジェクト直下に保存（開発向け）
# False: OS標準のAppData配下に保存（配布向け）
DEV_MODE = True

# パッケージに旧形式のプリセットが同梱されている場合に
# 初回起動時のみ root/presets へコピーするかどうか
MIGRATE_BUILTIN_PRESETS = True

# ===== UI 既定 =====
CSV_APPEND_DEFAULT = True
ALLOW_DUPLICATE_DROPS = False
ROI_MIN_W = 5
ROI_MIN_H = 5
ZOOM_STEP_RATIO = 1.15
UNDO_STACK_LIMIT = 200

# ===== ファイル／CSV =====
CSV_BOM_UTF8 = True
CSV_NEWLINE = ""
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"]

# ===== OCR =====
OCR_IMPL = "paddle"                 # 将来 "tesseract" 等を想定
PADDLE_LANG = "japan"
PADDLE_USE_ANGLE_CLS = True
PREPROCESS_BILATERAL = True
PREPROCESS_BINARIZE = False
UPSCALE_FACTOR = 1.0

# ===== ポストプロセス制御 =====
# 全体の強度（参照用ラベル。実際の挙動は個別フラグと列別設定で決まる）
POSTPROCESS_LEVEL = "safe"          # "none" | "safe" | "aggressive"

# 全列に対する安全処理（Trueで有効）
PP_TRIM = True
PP_COMPRESS_SPACES = True
PP_ASCII_DIGIT_ZEN2HAN = True       # ASCIIと数字のみ全角→半角（カナは触らない）
PP_REMOVE_ZERO_WIDTH = True

# 列ごとの追加ルール（0始まりの列番号）
# 値はルール名のリスト（postprocess.py 側の関数に対応）
PP_BY_COL = {
    # 例: 0: ["phone_digits"],
    # 例: 2: ["money_number"],
    # 例: 3: ["date_std"],
}

# ===== ワーカー／ログ =====
ALLOW_INTERRUPT = True
LOG_VERBOSE = True

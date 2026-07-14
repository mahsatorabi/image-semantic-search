# AI Image Indexer

ابزار خط فرمان برای **توصیف و ایندکس کردن عکس‌های سیستم** با مدل‌های رایگان Cloudflare Workers AI — بدون کپی کردن خود فایل‌ها. فقط **مسیر فایل + توضیح + embedding** در یک دیتابیس SQLite محلی ذخیره می‌شود.

## چه کار می‌کند؟

1. **اسکن** — پوشه‌های رایج عکس (Pictures، Downloads، Desktop و ...) را پیدا می‌کند
2. **توصیف با AI** — هر عکس را با مدل vision در Cloudflare توصیف می‌کند (caption، tags، متن OCR)
3. **ذخیره محلی** — مسیر فایل و متادیتا در `~/.ai-image-indexer/index.db` (بدون ذخیره خود عکس)
4. **جستجو** — با زبان طبیعی سرچ کنید و مسیر عکس‌های مرتبط را بگیرید

هر بار که `run` بزنید، عکس‌های جدید یا تغییرکرده دوباره پردازش می‌شوند؛ بقیه skip می‌شوند.

## پیش‌نیاز

- Python 3.10+
- حساب رایگان Cloudflare با Workers AI

### گرفتن API Key

1. برو به [Cloudflare Dashboard](https://dash.cloudflare.com)
2. **Workers AI** → **Use REST API**
3. `Account ID` و `API Token` را کپی کن

## نصب از GitHub

```bash
git clone https://github.com/mahsatorabi/image-semantic-search.git
cd image-semantic-search

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -e .
```

## تنظیمات

### روش ۱ — setup خودکار (پیشنهادی)

```bash
image-indexer setup
```

این دستور:
- صفحه **Workers AI** در Cloudflare را در مرورگر باز می‌کند
- از شما `Account ID` و `API Token` می‌گیرد
- اتصال را تست می‌کند و فایل `.env` می‌سازد

اگر Node.js/npm دارید:

```bash
image-indexer setup --login
```

(با `wrangler login` از مرورگر OAuth می‌گیرد)

### روش ۲ — دستی

فایل `.env` بساز (یا از `.env.example` کپی کن):

```env
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

اختیاری:

```env
# مسیرهای سفارشی (با کاما جدا)
AI_IMAGE_INDEXER_SCAN_PATHS=D:\Photos,E:\Backup\Images

# محل دیتابیس
AI_IMAGE_INDEXER_DB_PATH=~/.ai-image-indexer/index.db
```

## استفاده

### ایندکس کردن همه عکس‌های سیستم

```bash
image-indexer run
```

### ایندکس یک پوشه خاص

```bash
image-indexer scan "D:\MyPhotos"
```

### جستجو

```bash
image-indexer search "گربه روی مبل"
image-indexer search "sunset beach" -n 5
image-indexer search "invoice receipt" --json
```

### آمار و خروجی

```bash
image-indexer stats
image-indexer export -o my-index.json
image-indexer export -o my-index.csv --format csv
```

## معماری

```
عکس‌های سیستم (فقط خواندن)
        ↓
   Scanner (مسیر + hash)
        ↓
 Cloudflare Workers AI  ←  caption / tags / OCR / embedding
        ↓
 SQLite (~/.ai-image-indexer/index.db)
   • filepath (نه خود فایل)
   • caption, tags, ocr_text
   • embedding vector
        ↓
   Semantic Search (cosine similarity)
        ↓
   مسیر عکس‌های پیدا شده
```

## مدل‌های پیش‌فرض (رایگان در Cloudflare)

| کار | مدل |
|-----|-----|
| Vision (توصیف عکس) | `@cf/unum/uform-gen2-qwen-500m` |
| Embedding (جستجو) | `@cf/google/embeddinggemma-300m` |

## توسعه

```bash
pip install -e ".[dev]"
pytest
```

## لایسنس

MIT

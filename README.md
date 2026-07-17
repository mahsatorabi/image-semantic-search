# AI Image Indexer

A command-line tool for **describing and indexing your system images** using free Cloudflare Workers AI models — without copying the actual files. Only **file paths + captions + embeddings** are stored in a local SQLite database.

## What Does It Do?

1. **Scan** — Finds common image folders (Pictures, Downloads, Desktop, etc.)
2. **AI Description** — Describes each image using Cloudflare's vision model (caption, tags, OCR text)
3. **Local Storage** — Stores file paths and metadata in `~/.ai-image-indexer/index.db` (never stores the images themselves)
4. **Search** — Search by natural language and get back the paths of relevant images

Each time you run `run`, new or changed images are re-processed; the rest are skipped.

## Prerequisites

- Python 3.10+
- A free Cloudflare account with Workers AI enabled

### Getting Your API Key

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **Workers AI** → **Use REST API**
3. Copy your `Account ID` and create an API Token

## Installation

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

## Setup

### Option 1 — Automatic Setup (Recommended)

```bash
image-indexer setup
```

This command:
- Opens the **Workers AI** page in Cloudflare's dashboard
- Asks for your `Account ID` and `API Token`
- Tests the connection and creates a `.env` file

If you have Node.js/npm installed:

```bash
image-indexer setup --login
```

(This uses `wrangler login` for browser-based OAuth authentication)

### Option 2 — Manual Setup

Create a `.env` file (or copy from `.env.example`):

```env
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

Optional:

```env
# Custom scan paths (comma-separated)
AI_IMAGE_INDEXER_SCAN_PATHS=D:\Photos,E:\Backup\Images

# Database location
AI_IMAGE_INDEXER_DB_PATH=~/.ai-image-indexer/index.db
```

## Usage

### Index All System Images

```bash
image-indexer run
```

### Index a Specific Folder

```bash
image-indexer scan "D:\MyPhotos"
```

### Change Which Folders Are Indexed

Edit your `.env` file and set custom scan paths:

```env
AI_IMAGE_INDEXER_SCAN_PATHS=D:\Photos,E:\Backup\Images,C:\Users\you\Pictures
```

Then re-index with `image-indexer run`.

If no `AI_IMAGE_INDEXER_SCAN_PATHS` is set, it automatically scans default system folders (Pictures, Downloads, Desktop).

To start fresh with only specific folders, delete the database first:

```bash
rm ~/.ai-image-indexer/index.db      # Linux/macOS
del %USERPROFILE%\.ai-image-indexer\index.db   # Windows

image-indexer scan "D:\MyPhotos"
```

### Search

```bash
# Basic search (only shows results with similarity >= 0.25)
image-indexer search "cat on sofa"

# Show more results
image-indexer search "sunset beach" -n 5

# Lower the threshold to include less relevant results
image-indexer search "invoice receipt" --threshold 0.1

# Output as JSON
image-indexer search "robot" --json
```

### Stats, List, and Export

```bash
image-indexer stats
image-indexer list
image-indexer export -o my-index.json
image-indexer export -o my-index.csv --format csv
```

## Architecture

```
System images (read-only)
        ↓
   Scanner (path + hash)
        ↓
 Cloudflare Workers AI  ←  caption / tags / OCR / embedding
        ↓
 SQLite (~/.ai-image-indexer/index.db)
   • filepath (not the image itself)
   • caption, tags, ocr_text
   • embedding vector
        ↓
 Semantic Search (cosine similarity + threshold filtering)
        ↓
   Paths of matching images
```

## Default Models (Free on Cloudflare)

| Task | Model |
|------|-------|
| Vision (image description) | `@cf/unum/uform-gen2-qwen-500m` |
| Embedding (search) | `@cf/google/embeddinggemma-300m` |

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT

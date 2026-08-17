# Ive's Library

A static website for Ive's book library — 455 books across 13 collections, built from a BookBuddy "sorted by tag" PDF export.

Open `index.html` in a browser (or serve the folder) — there is no build step for the site itself.

```
index.html        the page
css/styles.css    design (dark candlelit-library theme, 3D book cards, shelves, dialog)
js/app.js         renders everything from data/books.js; search, filters, scroll reveals, book dialog + YouTube embeds
data/books.js     window.LIBRARY = { meta, collections, books[] }   (generated — don't hand-edit)
covers/           {id}.jpg high-res covers (Amazon image CDN by ISBN/ASIN, ~420px tall) + covers/big/{id}.jpg for the dialog; cover_NNN.jpg = 2× upscaled BookBuddy scan fallback
tools/            the pipeline that generated data/books.js (see below)
```

## Local preview

```bash
python3 -m http.server 4620 --directory ~/ives-library
```
then open http://localhost:4620

## Publishing

Any static host works — the folder is self-contained (≈13 MB, mostly cover images):

- **Netlify Drop**: drag the `ives-library` folder onto https://app.netlify.com/drop → instant URL.
- **GitHub Pages**: push this folder to a repo, Settings → Pages → deploy from `main` / root.
- **Vercel / Cloudflare Pages**: import the repo, no build command, output dir `.`.

## Regenerating when the library changes

1. In BookBuddy, export the library as PDF, sorted by tag ("BookBuddy by tag.pdf").
2. `cd tools` and run, with a Python 3.11+ venv that has `pymupdf` and `Pillow`:
   ```bash
   python parse_pdf.py data "/path/to/BookBuddy by tag.pdf"   # → data/books_parsed.json + data/covers_pdf/
   python enrich_google.py                                    # Google Books synopses + 300px covers (no API key; resumable)
   python build_data.py                                       # → ../data/books.js
   ```
3. High-res covers (run after `build_data.py` once, then again at the end):
   ```bash
   python fetch_covers.py      # Amazon image CDN by ISBN-10/ASIN (500px) → data/covers_hq/, data/covers_hq.json; leftovers listed in data/covers_missing.txt
   python make_covers.py       # trims padding, writes ../covers/{id}.jpg (shelf) + ../covers/big/{id}.jpg (modal), data/covers_final.json
   python build_data.py        # re-run so books.js points at the new covers
   ```
   For leftovers (no ISBN, or no image for that ISBN), put ASINs found by hand/research into `data/asin_overrides.json` (`{"book_id": ["ASIN", ...]}`) and re-run `fetch_covers.py`; or drop any image straight into `data/covers_hq/{id}.jpg` and add `{"source":"research-url","file":"{id}.jpg"}` to `data/covers_hq.json`. `gen_cover.py <id>` makes an elegant typographic cover for a book with no image anywhere. Books with no source at all fall back to the 2×-upscaled BookBuddy scan (`covers/cover_NNN.jpg`). Current state: 421/434 high-res (305 by ISBN, 113 by research), 13 keep Ive's own photos, 1 generated.
4. Books that Google has no synopsis for need a hand-written note in `data/summaries.json` (`{"book_id", "summary", "confidence"}`); `data/overrides.json` patches any field of a book by id; `data/videos.json` maps `book_id` → YouTube `video_id`.

## Data notes

- Collections are Ive's own BookBuddy tags (display names in `tools/build_data.py`, `COLLECTIONS`).
- A book tagged in several collections appears on each shelf but is one record; identical entries within one tag are shown once with a "×2 copies" badge.
- Summaries are either the publisher's description (Google Books) or a "shelf note written for Ive's Library"; the dialog says which.

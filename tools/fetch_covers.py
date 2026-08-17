"""Fetch high-res covers for every unique book. Sources, in order:
   1. Amazon by ISBN-10/ASIN  (images-na.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg, ~500px tall)
   2. Google Books zoom=2 (300px) already downloaded in out/covers_google
Records results in out/covers_hq.json; images in out/covers_hq/{book_id}.jpg
Extra ASINs/ISBNs found by research (out/asin_overrides.json: {book_id: [asin, ...]}) are tried first.
"""
import json, os, io, time, urllib.request, concurrent.futures, threading, sys
from PIL import Image

OUT = 'data'
HQ = os.path.join(OUT, 'covers_hq'); os.makedirs(HQ, exist_ok=True)
STATE_P = os.path.join(OUT, 'covers_hq.json')
lib = json.load(open(os.path.join(OUT, 'library_merged.json')))
books = lib['books']
state = json.load(open(STATE_P)) if os.path.exists(STATE_P) else {}
overrides = json.load(open(os.path.join(OUT, 'asin_overrides.json'))) if os.path.exists(os.path.join(OUT, 'asin_overrides.json')) else {}
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
lock = threading.Lock()
retry_all = '--retry' in sys.argv

def isbn13_to_10(i):
    i = ''.join(ch for ch in i if ch.isdigit())
    if len(i) == 10: return i
    if len(i) != 13 or not i.startswith('978'): return None
    core = i[3:12]; s = sum(int(d) * (10 - k) for k, d in enumerate(core)); c = (11 - s % 11) % 11
    return core + ('X' if c == 10 else str(c))

def fetch(url, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read(), r.status
        except urllib.error.HTTPError as e:
            if e.code in (429, 503): time.sleep(3 * (a + 1)); continue
            return None, e.code
        except Exception:
            time.sleep(1.5)
    return None, 0

def valid_image(data):
    if not data or len(data) < 2500: return None
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception:
        return None
    w, h = im.size
    if w < 180 or h < 220: return None
    return im

def try_amazon(asin):
    data, st = fetch('https://images-na.ssl-images-amazon.com/images/P/%s.01.LZZZZZZZ.jpg' % asin)
    im = valid_image(data)
    return (im, data) if im else (None, None)

def process(b):
    bid = str(b['id'])
    rec = state.get(bid, {})
    if rec.get('source') and not retry_all: return
    cands = []
    for a in overrides.get(bid, []): cands.append(('amazon-research', a))
    a10 = isbn13_to_10(b['isbn']) if b.get('isbn') else None
    if a10: cands.append(('amazon-isbn', a10))
    result = None
    for src, asin in cands:
        im, data = try_amazon(asin)
        if im:
            fn = '%s.jpg' % bid
            open(os.path.join(HQ, fn), 'wb').write(data)
            result = {'source': src, 'asin': asin, 'file': fn, 'w': im.size[0], 'h': im.size[1]}
            break
        time.sleep(0.2)
    if not result and b.get('coverBig'):
        # fall back to the 300px Google cover
        src_path = os.path.join(OUT, 'covers_google', os.path.basename(b['coverBig']))
        if os.path.exists(src_path):
            im = Image.open(src_path)
            result = {'source': 'google-300', 'file': None, 'google': src_path, 'w': im.size[0], 'h': im.size[1]}
    with lock:
        state[bid] = result or {'source': None, 'tried': [c[1] for c in cands]}
        process.n += 1
        if process.n % 25 == 0:
            print('  %d done, hq so far: %d' % (process.n, sum(1 for v in state.values() if v.get('source'))))
            json.dump(state, open(STATE_P, 'w'), indent=1)
process.n = 0

todo = [b for b in books if retry_all or not state.get(str(b['id']), {}).get('source')]
print('books', len(books), 'to process', len(todo))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    list(ex.map(process, todo))
json.dump(state, open(STATE_P, 'w'), indent=1)
srcs = {}
for v in state.values(): srcs[v.get('source')] = srcs.get(v.get('source'), 0) + 1
print('DONE sources:', srcs)
missing = [b for b in books if not state.get(str(b['id']), {}).get('source')]
print('missing', len(missing))
with open(os.path.join(OUT, 'covers_missing.txt'), 'w') as f:
    for b in missing:
        f.write('- id %d — "%s"%s — %s%s%s%s\n' % (b['id'], b['title'], (' : ' + b['subtitle']) if b['subtitle'] else '', b['author'] or 'author unknown', (' — ' + b['publisher']) if b['publisher'] else '', (' (%s)' % b['year']) if b['year'] else '', (' — ISBN ' + b['isbn']) if b['isbn'] else ' — no ISBN'))
print('wrote', os.path.join(OUT, 'covers_missing.txt'))

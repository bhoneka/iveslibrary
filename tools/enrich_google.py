"""Enrich parsed books with Google Books volume IDs, synopses, and larger covers (no API key)."""
import json, os, re, sys, time, html, urllib.request, urllib.parse, concurrent.futures, threading

BOOKS = 'data/books_parsed.json'
STATE = 'data/enrich_google.json'
COVER_DIR = 'data/covers_google'
os.makedirs(COVER_DIR, exist_ok=True)
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
lock = threading.Lock()

books = json.load(open(BOOKS))
state = json.load(open(STATE)) if os.path.exists(STATE) else {}

def fetch(url, binary=False, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9,es;q=0.8'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                ctype = r.headers.get('Content-Type', '')
                return (data if binary else data.decode('utf-8', 'replace')), ctype, r.status
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            return None, '', e.code
        except Exception as e:
            last = e
            time.sleep(2)
    print('  fetch failed', url[:80], last)
    return None, '', 0

def save_state():
    with lock:
        json.dump(state, open(STATE, 'w'), ensure_ascii=False, indent=1)

# ---- step 1: ISBN -> volume id (batched)
isbns = sorted({b['isbn'] for b in books if b['isbn']})
need = [i for i in isbns if i not in state or 'vid' not in state[i]]
print('isbns', len(isbns), 'need lookup', len(need))
for i in range(0, len(need), 20):
    chunk = need[i:i+20]
    keys = ','.join('ISBN:' + x for x in chunk)
    body, ctype, st = fetch('https://books.google.com/books?bibkeys=%s&jscmd=viewapi&callback=x' % keys)
    if not body:
        print('batch failed', i); continue
    m = re.match(r'^\s*x\((.*)\);?\s*$', body, re.S)
    data = json.loads(m.group(1)) if m else {}
    for isbn in chunk:
        rec = data.get('ISBN:' + isbn)
        st_rec = state.setdefault(isbn, {})
        if rec and 'info_url' in rec:
            vm = re.search(r'[?&]id=([^&]+)', rec['info_url'])
            st_rec['vid'] = vm.group(1) if vm else None
            st_rec['thumb'] = rec.get('thumbnail_url')
        else:
            st_rec['vid'] = None
    save_state()
    time.sleep(0.4)
print('with vid:', sum(1 for i in isbns if state.get(i, {}).get('vid')))

# ---- step 2: per volume: synopsis + larger cover
def strip_html(s):
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</p>\s*<p[^>]*>', '\n\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

def process(isbn):
    rec = state[isbn]
    vid = rec.get('vid')
    if not vid or rec.get('done'):
        return
    page, ctype, st = fetch('https://books.google.com/books?id=%s&hl=en' % vid)
    desc = ''
    if page:
        m = re.search(r'<div id="synopsistext"[^>]*>(.*?)</div>\s*(?:<div|<table|<a|<script)', page, re.S)
        if m:
            desc = strip_html(m.group(1))
        if not desc:
            m = re.search(r'<meta name="description" content="([^"]*)"', page)
            if m:
                desc = html.unescape(m.group(1)).strip()
        # page count / published date as backup metadata
        pm = re.search(r'(\d+)\s+pages', page)
        rec['gb_pages'] = int(pm.group(1)) if pm else None
        # categories/subject
        sm = re.search(r'<a[^>]*href="[^"]*subject:[^"]*"[^>]*>([^<]+)</a>', page)
        rec['gb_subject'] = html.unescape(sm.group(1)) if sm else None
    rec['desc'] = desc
    # try larger cover: zoom=2 (300px)
    for zoom in (2,):
        img, ctype, st = fetch('https://books.google.com/books/content?id=%s&printsec=frontcover&img=1&zoom=%d' % (vid, zoom), binary=True)
        if img and 'jpeg' in ctype and len(img) > 4000:
            fn = '%s.jpg' % isbn
            open(os.path.join(COVER_DIR, fn), 'wb').write(img)
            rec['cover_big'] = fn
            break
    rec['done'] = True
    with lock:
        process.count += 1
        if process.count % 10 == 0:
            print('  processed', process.count, 'desc:', sum(1 for v in state.values() if v.get('desc')), 'big covers:', sum(1 for v in state.values() if v.get('cover_big')))
            json.dump(state, open(STATE, 'w'), ensure_ascii=False, indent=1)
    time.sleep(0.3)
process.count = 0

todo = [i for i in isbns if state.get(i, {}).get('vid') and not state[i].get('done')]
print('volumes to process', len(todo))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    list(ex.map(process, todo))
save_state()
print('DONE. desc:', sum(1 for v in state.values() if v.get('desc')), 'big covers:', sum(1 for v in state.values() if v.get('cover_big')), 'of', len(isbns))

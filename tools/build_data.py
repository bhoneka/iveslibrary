"""Merge parsed PDF data + Google synopses + agent summaries + videos into ~/ives-library/data/books.js"""
import json, os, re, collections, unicodedata

SCRATCH = os.path.dirname(os.path.abspath(__file__))  # the tools/ folder
SITE = os.path.dirname(SCRATCH)  # the site root
books = json.load(open(os.path.join(SCRATCH, 'data/books_parsed.json')))
google = json.load(open(os.path.join(SCRATCH, 'data/enrich_google.json')))
summaries = {}
p = os.path.join(SCRATCH, 'data/summaries.json')
if os.path.exists(p):
    for row in json.load(open(p)):
        summaries[int(row['book_id'])] = row
videos = {}
p = os.path.join(SCRATCH, 'data/videos.json')
if os.path.exists(p):
    for row in json.load(open(p)):
        videos[int(row['book_id'])] = row
overrides = {}
p = os.path.join(SCRATCH, 'data/overrides.json')
if os.path.exists(p):
    overrides = {int(k): v for k, v in json.load(open(p)).items()}
covers_final = {}
p = os.path.join(SCRATCH, 'data/covers_final.json')
if os.path.exists(p):
    covers_final = {int(k): v for k, v in json.load(open(p)).items()}

# ---- collections (display order is thematic; keys are stable slugs)
COLLECTIONS = [
    ('Catechism',            'catechism',   'Catechism',              'The foundations — Bibles, catechisms, Scripture study and the teaching of the Church.'),
    ('Apologetics',          'apologetics', 'Apologetics',            'Explaining and defending the faith with reason, Scripture and charity.'),
    ('Saints And Popes',     'saints',      'Saints & Popes',         'Lives, writings and wisdom of the saints — and the popes who have shepherded the Church.'),
    ('Mary',                 'mary',        'Mary',                   'Our Lady — her titles, her apparitions, the Rosary, and consecration to Jesus through Mary.'),
    ('Prayer',               'prayer',      'Prayer',                 'Retreats, meditations, devotions and guides to a deeper interior life.'),
    ('Catholic Authors',     'authors',     'Catholic Authors',       'Memoirs, essays, history and witness from Catholic writers past and present.'),
    ('TOB',                  'tob',         'Theology of the Body',   'St. John Paul II’s vision of love, the body, marriage and family — and how to live it.'),
    ('OPUS DEI',             'opusdei',     'Opus Dei',               'St. Josemaría Escrivá, Blessed Álvaro del Portillo, and finding God in ordinary work.'),
    ('End Times/Conspiracy', 'endtimes',    'End Times & Conspiracy', 'Prophecy, warnings, and the Church in a turbulent age.'),
    ('Self Help',            'selfhelp',    'Self-Help',              'Virtue, character, friendship, happiness and the art of living well.'),
    ('Estrangement',         'estrangement','Estrangement',           'Healing, boundaries and hope for wounded family relationships.'),
    ('Childrens Books',      'children',    'Children’s Books',       'Stories, virtues and picture books for little ones — en inglés y en español.'),
    ('Untagged',             'unsorted',    'New Arrivals',           'Recently added and still waiting for a shelf.'),
]
tag2key = {t: k for t, k, _, _ in COLLECTIONS}

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
    return s

def title_case_fix(t):
    # BookBuddy scanned titles are sometimes ALL Title Case ("El Santo De Cada Dia") — leave as-is; only trim
    return re.sub(r'\s+', ' ', t).strip()

def tidy_text(s):
    s = s or ''
    # "life.Here it is" -> "life. Here it is" (only after a lowercase letter/closing paren, so U.S.A. stays intact)
    s = re.sub(r'([a-záéíóúñ\)][.!?])([A-ZÁÉÍÓÚÑ¿¡"“])', r'\1 \2', s)
    s = re.sub(r'([a-záéíóúñ]),([A-Za-záéíóúñ])', r'\1, \2', s)
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def clean_author(a):
    a = re.sub(r'\s+', ' ', a or '').strip()
    a = re.sub(r'\s*\((?:santo|santa|saint|cardenal|beato|of the holy face|s\.j\.?|catholic priest)\.?\)', '', a, flags=re.I)
    return a.strip(' ,')

# ---- merge duplicates
merged = []       # list of book dicts
index = {}        # key -> merged book
order_counter = 0
for b in books:
    key = (norm(b['title']), norm(b['author']), b['isbn'])
    ckey = tag2key.get(b['tag'], 'unsorted')
    if key in index:
        m = index[key]
        if ckey in m['tags']:
            m['copies'] += 1
        else:
            m['tags'].append(ckey)
        m['source_ids'].append(b['id'])
        continue
    m = {
        'id': b['id'],
        'source_ids': [b['id']],
        'title': title_case_fix(b['title']),
        'subtitle': re.sub(r'\s+', ' ', b['subtitle']).strip(),
        'author': clean_author(b['author']),
        'publisher': b['publisher'],
        'pubDate': b['pub_date'],
        'year': b['year'],
        'pages': b['pages'],
        'language': b['language'],
        'genre': b['genre'],
        'isbn': b['isbn'],
        'tags': [ckey],
        'copies': 1,
        'cover': 'covers/' + b['cover_pdf'],
        'coverBig': None,
        'coverW': b['cover_w'] * 2, 'coverH': b['cover_h'] * 2,
    }
    g = google.get(b['isbn']) if b['isbn'] else None
    if g:
        if g.get('cover_big'):
            m['coverBig'] = 'covers/big/' + g['cover_big']
        if g.get('desc'):
            m['summary'] = tidy_text(g['desc'])
            m['summarySource'] = 'publisher'
        if g.get('vid'):
            m['googleId'] = g['vid']
        if not m['pages'] and g.get('gb_pages'):
            m['pages'] = g['gb_pages']
    index[key] = m
    merged.append(m)

# summaries from agents (apply to all merged books sharing the source id, and to dupes by title/author)
by_source = {}
for m in merged:
    for sid in m['source_ids']:
        by_source[sid] = m
for bid, row in summaries.items():
    m = by_source.get(bid)
    if m and not m.get('summary'):
        m['summary'] = row['summary'].strip()
        m['summarySource'] = 'written'
        m['summaryConfidence'] = row.get('confidence', 'medium')
# fill summaries across same-title books (e.g. two editions) that still lack one
by_title = collections.defaultdict(list)
for m in merged:
    by_title[(norm(m['title']), norm(m['author']))].append(m)
for grp in by_title.values():
    src = next((x for x in grp if x.get('summary')), None)
    if src:
        for x in grp:
            if not x.get('summary'):
                x['summary'] = src['summary']; x['summarySource'] = src['summarySource']

for bid, row in videos.items():
    m = by_source.get(bid)
    if m:
        m['video'] = {'id': row['video_id'], 'title': row.get('video_title', ''), 'channel': row.get('channel', '')}

for bid, ov in overrides.items():
    m = by_source.get(bid)
    if m:
        m.update(ov)

# high-res covers (Amazon CDN by ISBN/ASIN, Google 300px) — keyed by merged book id
for m in merged:
    cf = covers_final.get(m['id'])
    if cf:
        m['cover'] = cf['cover']; m['coverBig'] = cf['coverBig']
        m['coverW'] = cf['w']; m['coverH'] = cf['h']
        m['coverSource'] = cf['source']
    else:
        m['coverSource'] = 'bookbuddy-scan'

# ---- language of summary (for display font/lang attr)
SPANISH_HINTS = re.compile(r'\b(el|la|los|las|de|del|y|para|con|un|una|santo|santa|dios|iglesia|oración|vida|historia|niños|virgen|que|por|su|sus|como|más|este|esta)\b', re.I)
ENGLISH_HINTS = re.compile(r'\b(the|of|and|for|to|with|your|his|her|their|is|are|this|that|book)\b', re.I)
def looks_spanish(s):
    s = s or ''
    return len(SPANISH_HINTS.findall(s)) > len(ENGLISH_HINTS.findall(s))

for m in merged:
    if m.get('summary'):
        m['summaryLang'] = 'es' if looks_spanish(m['summary']) else 'en'

# infer language when missing: from the summary's language (agents wrote Spanish notes for Spanish books;
# publisher blurbs are in the book's language), falling back to title heuristics
for m in merged:
    if not m['language']:
        text = m['title'] + ' ' + m['subtitle']
        if m.get('summaryLang'):
            m['language'] = 'Spanish' if m['summaryLang'] == 'es' else 'English'
        else:
            m['language'] = 'Spanish' if len(SPANISH_HINTS.findall(text)) >= 2 else ('English' if ENGLISH_HINTS.search(text) else '')
        m['languageInferred'] = True

# ---- collections with counts (entries = per-tag listing count, matches BookBuddy's 455)
cols = []
for tag, key, name, blurb in COLLECTIONS:
    items = [m for m in merged if key in m['tags']]
    entries = sum(m['copies'] if len(m['tags']) == 1 else 1 for m in items)
    # copies belong to a single tag in the source; count entries as source_ids in this tag
    entries = sum(1 for b in books if tag2key.get(b['tag'], 'unsorted') == key)
    cols.append({'key': key, 'name': name, 'blurb': blurb, 'count': entries, 'uniqueCount': len(items)})

# ---- stats
total_entries = len(books)
unique_titles = len(merged)
langs = collections.Counter(m['language'] for m in merged if m['language'])
pages = sum((m['pages'] or 0) * m['copies'] for m in merged)
authors = collections.Counter()
for m in merged:
    for a in re.split(r',| and ', m['author']):
        a = a.strip()
        if a and len(a) > 3:
            authors[a] += 1
top_authors = [{'name': a, 'count': c} for a, c in authors.most_common(8)]
years = [m['year'] for m in merged if m['year']]

meta = {
    'title': "Ive's Library",
    'totalEntries': total_entries,
    'uniqueTitles': unique_titles,
    'collections': len([c for c in cols if c['count']]),
    'languages': dict(langs),
    'pages': pages,
    'withSummary': sum(1 for m in merged if m.get('summary')),
    'withVideo': sum(1 for m in merged if m.get('video')),
    'topAuthors': top_authors,
    'oldestYear': min(years) if years else None,
    'newestYear': max(years) if years else None,
    'catalogued': 'August 2026',
}

# strip helper fields
for m in merged:
    m.pop('source_ids', None)

out = {'meta': meta, 'collections': cols, 'books': merged}
os.makedirs(os.path.join(SITE, 'data'), exist_ok=True)
with open(os.path.join(SITE, 'data', 'books.js'), 'w') as f:
    f.write('window.LIBRARY = ')
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    f.write(';\n')
json.dump(out, open(os.path.join(SCRATCH, 'data', 'library_merged.json'), 'w'), ensure_ascii=False, indent=1)
print('books merged:', unique_titles, 'entries:', total_entries)
print('collections:', [(c['name'], c['count']) for c in cols])
print('summaries:', meta['withSummary'], 'videos:', meta['withVideo'], 'big covers:', sum(1 for m in merged if m['coverBig']))
print('multi-tag:', sum(1 for m in merged if len(m['tags']) > 1), 'multi-copy:', sum(1 for m in merged if m['copies'] > 1))
print('languages:', langs, 'pages:', pages)
print('top authors:', top_authors)

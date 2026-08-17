import pymupdf, json, os, re, sys

PDF = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser('~/Downloads/BookBuddy by tag.pdf')
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else 'data'
COVER_DIR = os.path.join(OUT_DIR, 'covers_pdf')
os.makedirs(COVER_DIR, exist_ok=True)

doc = pymupdf.open(PDF)
books = []
current_tag = None
cur = None

def finish():
    global cur
    if cur is not None:
        books.append(cur)
        cur = None

def parse_kv(line_text):
    # "Genre: Religion    Number of Pages: 208    Language: English    ISBN: 978..."
    out = {}
    parts = re.split(r'\s{2,}', line_text.strip())
    for p in parts:
        if ':' in p:
            k, v = p.split(':', 1)
            out[k.strip()] = v.strip()
    return out

for pn in range(len(doc)):
    page = doc[pn]
    images = []
    for info in page.get_image_info(xrefs=True):
        images.append({'xref': info['xref'], 'y0': info['bbox'][1], 'y1': info['bbox'][3], 'x0': info['bbox'][0]})
    # gather lines: list of (y, x, size, font, text)
    lines = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            spans = l['spans']
            if not spans:
                continue
            text = ''.join(s['text'] for s in spans)
            if not text.strip():
                continue
            s0 = spans[0]
            lines.append({'y': l['bbox'][1], 'x': l['bbox'][0], 'size': s0['size'], 'font': s0['font'], 'text': text, 'spans': spans})
    lines.sort(key=lambda r: (round(r['y'], 1), r['x']))

    for ln in lines:
        size, font, text, x, y = ln['size'], ln['font'], ln['text'], ln['x'], ln['y']
        if pn == 0 and (abs(size - 22) < 0.5 or (abs(size - 10) < 0.5 and 'summaries removed' in text)):
            continue  # doc title/subtitle
        if abs(size - 16) < 0.5 and 'Bold' in font and x < 60:
            finish()
            current_tag = text.strip()
            continue
        if abs(size - 12) < 0.5 and 'BoldOblique' in font:
            # title line — new book unless previous line was also a title (wrapped)
            if cur is not None and cur.get('_last') == 'title' and not cur.get('_has_more'):
                cur['title'] += ' ' + text.strip()
            else:
                finish()
                cur = {'title': text.strip(), 'subtitle': '', 'author': '', 'publisher_raw': '',
                       'genre': '', 'pages': None, 'language': '', 'isbn': '', 'status': '', 'date_added': '',
                       'tag': current_tag, 'page': pn + 1, '_title_y': y, '_last': 'title'}
            continue
        if cur is None:
            print('WARN orphan line p%d: %r' % (pn + 1, text))
            continue
        if abs(size - 9.5) < 0.3 and font == 'Helvetica-Bold':
            cur['subtitle'] = (cur['subtitle'] + ' ' + text.strip()).strip()
            cur['_last'] = 'subtitle'; cur['_has_more'] = True
            continue
        if abs(size - 9.5) < 0.3 and font.startswith('Times'):
            cur['author'] = (cur['author'] + ' ' + text.strip()).strip()
            cur['_last'] = 'author'; cur['_has_more'] = True
            continue
        if abs(size - 8.5) < 0.3:
            stripped = text.strip()
            if stripped.startswith('Genre:') or stripped.startswith('Number of Pages:') or stripped.startswith('Language:') or stripped.startswith('ISBN:'):
                kv = parse_kv(text)
                cur['genre'] = kv.get('Genre', cur['genre'])
                if kv.get('Number of Pages'):
                    try: cur['pages'] = int(kv['Number of Pages'])
                    except: pass
                cur['language'] = kv.get('Language', cur['language'])
                cur['isbn'] = kv.get('ISBN', cur['isbn'])
                cur['_last'] = 'meta'; cur['_has_more'] = True
            elif stripped.startswith('Reading Status:') or stripped.startswith('Date Added:') or stripped.startswith('Tags:'):
                kv = parse_kv(text)
                cur['status'] = kv.get('Reading Status', '')
                cur['date_added'] = kv.get('Date Added', '')
                tags = kv.get('Tags', '')
                if tags and tags != current_tag:
                    print('NOTE tag mismatch p%d %r: %r vs section %r' % (pn + 1, cur['title'], tags, current_tag))
                cur['tags_raw'] = tags
                cur['_last'] = 'status'; cur['_has_more'] = True
            else:
                # publisher line (or continuation)
                if cur['_last'] in ('publisher',):
                    cur['publisher_raw'] += ' ' + stripped
                else:
                    cur['publisher_raw'] = stripped
                cur['_last'] = 'publisher'; cur['_has_more'] = True
            continue
        print('WARN unclassified p%d size=%.1f font=%s: %r' % (pn + 1, size, font, text))

    # map images to books on this page
    page_books = [b for b in books if b['page'] == pn + 1] + ([cur] if cur is not None and cur['page'] == pn + 1 else [])
    for b in page_books:
        best = None
        for im in images:
            d = abs(im['y0'] - b['_title_y'])
            if best is None or d < best[0]:
                best = (d, im)
        if best and best[0] < 12:
            b['_xref'] = best[1]['xref']
            b['_img_dist'] = best[0]
        else:
            print('WARN no image for p%d %r (best dist %s)' % (pn + 1, b['title'], best[0] if best else None))
    used = [b.get('_xref') for b in page_books]
    for im in images:
        if im['xref'] not in used:
            print('WARN unused image on p%d at y=%.0f' % (pn + 1, im['y0']))

finish()
print('parsed', len(books), 'books')

# extract images and clean up
for i, b in enumerate(books):
    b['id'] = i + 1
    xref = b.pop('_xref', None)
    if xref:
        pix = pymupdf.Pixmap(doc, xref)
        if pix.n - pix.alpha >= 4:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        fn = 'cover_%03d.jpg' % (i + 1)
        pix.save(os.path.join(COVER_DIR, fn), jpg_quality=92)
        b['cover_pdf'] = fn
        b['cover_w'] = pix.width; b['cover_h'] = pix.height
    for k in list(b.keys()):
        if k.startswith('_'):
            del b[k]
    # split publisher / date
    m = re.match(r'^(.*?)\s*\(([^()]*)\)\s*$', b['publisher_raw'])
    if m:
        b['publisher'] = m.group(1).strip()
        b['pub_date'] = m.group(2).strip()
    else:
        b['publisher'] = b['publisher_raw']
        b['pub_date'] = ''
    ym = re.search(r'(\d{4})', b['pub_date'])
    b['year'] = int(ym.group(1)) if ym else None
    del b['publisher_raw']

json.dump(books, open(os.path.join(OUT_DIR, 'books_parsed.json'), 'w'), ensure_ascii=False, indent=1)
print('wrote', os.path.join(OUT_DIR, 'books_parsed.json'))

"""Turn out/covers_hq/*.jpg (+ google 300px fallbacks) into site assets:
   covers/{id}.jpg       shelf size (max height 420)
   covers/big/{id}.jpg   modal size (native, max height 800)
Auto-trims uniform white/black borders (Amazon pads some covers), flags small results.
Writes out/covers_final.json  {book_id: {cover, coverBig, w, h, source, small}}"""
import json, os, sys
from PIL import Image, ImageChops, ImageOps

OUT = 'data'
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
state = json.load(open(os.path.join(OUT, 'covers_hq.json')))
lib = json.load(open(os.path.join(OUT, 'library_merged.json')))
books = {str(b['id']): b for b in lib['books']}
os.makedirs(os.path.join(SITE, 'covers', 'big'), exist_ok=True)

def trim_borders(im, thresh=238, frac=0.985):
    """Trim rows/cols that are almost entirely near-white (or near-black)."""
    g = im.convert('L')
    w, h = g.size
    px = g.load()
    def row_uniform(y, white):
        cnt = 0
        for x in range(w):
            v = px[x, y]
            if (white and v >= thresh) or ((not white) and v <= 255 - thresh): cnt += 1
        return cnt / w >= frac
    def col_uniform(x, white):
        cnt = 0
        for y in range(h):
            v = px[x, y]
            if (white and v >= thresh) or ((not white) and v <= 255 - thresh): cnt += 1
        return cnt / h >= frac
    best = None
    for white in (True, False):
        top, bottom, left, right = 0, h, 0, w
        while top < bottom - 20 and row_uniform(top, white): top += 1
        while bottom > top + 20 and row_uniform(bottom - 1, white): bottom -= 1
        while left < right - 20 and col_uniform(left, white): left += 1
        while right > left + 20 and col_uniform(right - 1, white): right -= 1
        area = (right - left) * (bottom - top)
        if best is None or area < best[0]:
            best = (area, (left, top, right, bottom))
    box = best[1]
    if box == (0, 0, w, h): return im
    # add a hairline back so we don't cut into the art
    l, t, r, b = box
    return im.crop((max(0, l - 1), max(0, t - 1), min(w, r + 1), min(h, b + 1)))

final = {}
n_small = 0
for bid, rec in state.items():
    src = rec.get('source')
    if not src: continue
    if src == 'google-300':
        path = rec['google']
    else:
        path = os.path.join(OUT, 'covers_hq', rec['file'])
    im = Image.open(path).convert('RGB')
    im = trim_borders(im)
    w, h = im.size
    small = h < 240
    if small:
        n_small += 1
        # prefer google 300 if this book has one and it's taller
        b = books[bid]
        if b.get('coverBig'):
            gp = os.path.join(OUT, 'covers_google', os.path.basename(b['coverBig']))
            if os.path.exists(gp):
                gim = trim_borders(Image.open(gp).convert('RGB'))
                if gim.size[1] > h:
                    im = gim; w, h = im.size; src = 'google-300'; small = h < 240
    # shelf size
    shelf = im if h <= 420 else im.resize((round(w * 420 / h), 420), Image.LANCZOS)
    big = im if h <= 800 else im.resize((round(w * 800 / h), 800), Image.LANCZOS)
    shelf.save(os.path.join(SITE, 'covers', '%s.jpg' % bid), quality=84, optimize=True, progressive=True)
    big.save(os.path.join(SITE, 'covers', 'big', '%s.jpg' % bid), quality=86, optimize=True, progressive=True)
    final[bid] = {'cover': 'covers/%s.jpg' % bid, 'coverBig': 'covers/big/%s.jpg' % bid, 'w': shelf.size[0], 'h': shelf.size[1], 'bigW': big.size[0], 'bigH': big.size[1], 'source': src, 'small': small, 'asin': rec.get('asin')}
json.dump(final, open(os.path.join(OUT, 'covers_final.json'), 'w'), indent=1)
print('final covers', len(final), 'small(<240px after trim):', n_small)
print('small ids:', [ (bid, v['h']) for bid, v in final.items() if v['small']])

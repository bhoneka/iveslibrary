"""Generate an elegant typographic cover (cloth-bound hardcover look) for books with no usable image."""
import json, sys, os, textwrap, hashlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

lib = json.load(open('data/library_merged.json')); books = {str(b['id']): b for b in lib['books']}
PALETTES = [((72, 20, 24), (214, 177, 105)), ((22, 38, 60), (222, 190, 120)), ((30, 52, 40), (220, 186, 112)),
            ((60, 34, 22), (230, 200, 130)), ((44, 28, 60), (218, 184, 118))]
FONT_TITLE = '/System/Library/Fonts/Supplemental/Hoefler Text.ttc'
FONT_AUTH = '/System/Library/Fonts/Supplemental/Baskerville.ttc'

def make(bid, out_path, W=600, H=900):
    b = books[bid]
    idx = int(hashlib.md5(bid.encode()).hexdigest(), 16) % len(PALETTES)
    bg, gold = PALETTES[idx]
    im = Image.new('RGB', (W, H), bg)
    # cloth texture: subtle noise
    rng = np.random.default_rng(int(bid))
    noise = rng.normal(0, 6, (H, W, 1)).astype(np.int16)
    a = np.clip(np.asarray(im).astype(np.int16) + noise, 0, 255).astype(np.uint8)
    im = Image.fromarray(a)
    # vignette + spine shadow
    vig = Image.new('L', (W, H), 0); vd = ImageDraw.Draw(vig)
    vd.ellipse((-W * 0.3, -H * 0.2, W * 1.3, H * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new('RGB', (W, H), tuple(int(c * 0.55) for c in bg))
    im = Image.composite(im, dark, vig)
    spine = Image.new('L', (W, H), 0); sd = ImageDraw.Draw(spine); sd.rectangle((0, 0, 26, H), fill=140)
    spine = spine.filter(ImageFilter.GaussianBlur(14))
    im = Image.composite(Image.new('RGB', (W, H), tuple(int(c * 0.6) for c in bg)), im, spine)
    d = ImageDraw.Draw(im)
    # gilt frame
    m = 42
    d.rectangle((m, m, W - m, H - m), outline=gold, width=2)
    d.rectangle((m + 10, m + 10, W - m - 10, H - m - 10), outline=gold, width=1)
    # title
    title = b['title']
    size = 64 if len(title) < 22 else 54 if len(title) < 40 else 44
    f = ImageFont.truetype(FONT_TITLE, size)
    lines = textwrap.wrap(title, width=int(W * 0.72 / (size * 0.48)))
    while len(lines) > 6:
        size -= 4; f = ImageFont.truetype(FONT_TITLE, size); lines = textwrap.wrap(title, width=int(W * 0.72 / (size * 0.48)))
    lh = int(size * 1.18); total = lh * len(lines)
    y = int(H * 0.36) - total // 2
    for ln in lines:
        w = d.textlength(ln, font=f); d.text(((W - w) / 2, y), ln, font=f, fill=gold); y += lh
    # ornament
    y += 18
    d.line((W * 0.34, y, W * 0.66, y), fill=gold, width=1)
    d.regular_polygon((W / 2, y, 7), 4, rotation=45, fill=gold)
    y += 34
    # subtitle
    if b.get('subtitle'):
        fs = ImageFont.truetype(FONT_AUTH, 26)
        for ln in textwrap.wrap(b['subtitle'], width=34)[:3]:
            w = d.textlength(ln, font=fs); d.text(((W - w) / 2, y), ln, font=fs, fill=tuple(min(255, int(c * 0.9)) for c in gold)); y += 34
    # author (bottom)
    if b.get('author'):
        fa = ImageFont.truetype(FONT_AUTH, 30)
        lines = textwrap.wrap(b['author'], width=30)[:2]
        yy = int(H * 0.80)
        for ln in lines:
            w = d.textlength(ln, font=fa); d.text(((W - w) / 2, yy), ln, font=fa, fill=gold); yy += 38
    im.save(out_path, quality=90)

if __name__ == '__main__':
    for bid in sys.argv[1:]:
        out = 'data/covers_hq/%s.jpg' % bid
        make(bid, out); print('generated', out)

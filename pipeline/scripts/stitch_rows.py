"""Stacks equally wide PNGs top to bottom: stitch_rows.py OUT.png ROW1.png ROW2.png ..."""
import sys

from PIL import Image

import re

def _natural(p):  # row2 before row10 (plain sorted() puts row10 first)
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', p)]


if len(sys.argv) < 3:
    sys.exit('usage: stitch_rows.py OUT.png ROW1.png [ROW2.png ...]')
out, rows = sys.argv[1], sorted(sys.argv[2:], key=_natural)
ims = [Image.open(p).convert('RGB') for p in rows]
w = max(i.width for i in ims)
sheet = Image.new('RGB', (w, sum(i.height for i in ims)), (222, 232, 242))
y = 0
for im in ims:
    sheet.paste(im, (0, y))
    y += im.height
sheet.save(out)
print('wrote', out, sheet.size)

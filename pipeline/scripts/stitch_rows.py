"""Stacks equally wide PNGs top to bottom: stitch_rows.py OUT.png ROW1.png ROW2.png ..."""
import sys

from PIL import Image

out, rows = sys.argv[1], sorted(sys.argv[2:])
ims = [Image.open(p).convert('RGB') for p in rows]
w = max(i.width for i in ims)
sheet = Image.new('RGB', (w, sum(i.height for i in ims)), (222, 232, 242))
y = 0
for im in ims:
    sheet.paste(im, (0, y))
    y += im.height
sheet.save(out)
print('wrote', out, sheet.size)

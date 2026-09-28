"""Pair a Godot-rendered 3D model contact sheet (--scene=model_sheet) with upstream's own
sprites, cell by cell: [upstream sprite x2 | 3D render].

  python3 pipeline/scripts/compose_model_sheet.py SHEET3D.png COLS CELL SPRITES_DIR VIEW OUT.png \
      [--ids A,B,C | --manifest godot/assets/models/pokemon/manifest.json] [--out-cols N] [--chunk N]

SPRITES_DIR comes from pipeline/scripts/bake_monsprites.js (<ID>_front.png / <ID>_back.png).
With --chunk N, writes OUT_000.png, OUT_001.png ... of N cells each instead of one image.
"""
import json
import os
import sys

from PIL import Image, ImageDraw


def main():
    a = sys.argv[1:]
    sheet_path, cols, cell, sprites, view, out = a[0], int(a[1]), int(a[2]), a[3], a[4], a[5]
    opts = a[6:]
    ids = None
    if '--ids' in opts:
        ids = opts[opts.index('--ids') + 1].split(',')
    elif '--manifest' in opts:
        ids = json.load(open(opts[opts.index('--manifest') + 1]))['generated']
    out_cols = int(opts[opts.index('--out-cols') + 1]) if '--out-cols' in opts else 8
    chunk = int(opts[opts.index('--chunk') + 1]) if '--chunk' in opts else 0
    sheet = Image.open(sheet_path).convert('RGBA')
    n = len(ids)
    sp = cell * 4 // 5
    cw = sp + cell
    bg = (222, 232, 242, 255)

    def cell_img(i, name):
        im = Image.new('RGBA', (cw, cell), bg)
        f = os.path.join(sprites, '%s_%s.png' % (name, view))
        if os.path.exists(f):
            s = Image.open(f).convert('RGBA').resize((sp, sp), Image.NEAREST)
            im.alpha_composite(s, (0, (cell - sp) // 2))
        x, y = (i % cols) * cell, (i // cols) * cell
        im.alpha_composite(sheet.crop((x, y, x + cell, y + cell)), (sp, 0))
        d = ImageDraw.Draw(im)
        d.line([(sp - 1, 4), (sp - 1, cell - 4)], fill=(190, 200, 215, 255))
        return im

    groups = [list(range(n))] if not chunk else [list(range(k, min(n, k + chunk))) for k in range(0, n, chunk)]
    for gi, idxs in enumerate(groups):
        rows = (len(idxs) + out_cols - 1) // out_cols
        W = Image.new('RGBA', (out_cols * cw, rows * cell), bg)
        for j, i in enumerate(idxs):
            W.alpha_composite(cell_img(i, ids[i]), ((j % out_cols) * cw, (j // out_cols) * cell))
        path = out if not chunk else out.replace('.png', '_%03d.png' % gi)
        W.convert('RGB').save(path, optimize=True)
        print('wrote', path)


if __name__ == '__main__':
    main()

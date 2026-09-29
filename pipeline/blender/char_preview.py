"""Tiny numpy z-buffer preview of Parts (debug only; the truth is the Godot render).

  from char_preview import preview
  preview(parts, atlas, '/tmp/x.png', views=('front','side','back'))
"""
import numpy as np
from PIL import Image

import char_geo as G


def part_colors(atlas, part, ao=None):
    c = atlas.cells[part.cell]
    if c.kind == 'detail':
        arr = c.fn()
        col = np.tile(arr.reshape(-1, 3).mean(0), (len(part.V), 1))
        if part.uv is not None:
            h, w = arr.shape[:2]
            ix = np.clip((part.uv[:, 0] * (w - 1)).round().astype(int), 0, w - 1)
            iy = np.clip(((1 - part.uv[:, 1]) * (h - 1)).round().astype(int), 0, h - 1)
            col = arr[iy, ix]
        return col
    a = np.ones(len(part.V)) if ao is None else ao
    A = a.reshape(-1, 1)
    Gg = part.g.reshape(-1, 1)
    return c.fn(A, Gg).reshape(-1, 3)


def render_view(items, size=520, yaw=0.0, pitch=8.0, light=(-0.45, -0.6, 0.65), bg=(0.87, 0.91, 0.95)):
    """items: list of (V, F, colors(n,3), normals(n,3))."""
    import math
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    Ry = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])           # yaw about Z
    Rp = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])             # pitch about X
    R = Rp @ Ry
    allv = np.vstack([it[0] for it in items]) @ R.T
    lo, hi = allv.min(0), allv.max(0)
    span = max(hi[0] - lo[0], hi[2] - lo[2])
    scale = size * 0.92 / span
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    W = Hh = size
    zbuf = np.full((Hh, W), -1e9)
    img = np.tile(np.array(bg)[None, None, :], (Hh, W, 1))
    L = np.array(light)
    L = L / np.linalg.norm(L)
    Lr = R @ L
    for V, F, col, N in items:
        P = V @ R.T
        Nn = N @ R.T
        # camera looks along +Y (front of the figure is -Y): depth = -y (nearer = smaller y)
        sx = (P[:, 0] - cx) * scale + W / 2
        sz = Hh / 2 - (P[:, 2] - cz) * scale
        dep = -P[:, 1]
        lam = np.clip(Nn @ (-Lr * np.array([1, -1, 1])), -1, 1)
        for f in F:
            a, b, c = f
            x0, x1, x2 = sx[a], sx[b], sx[c]
            y0, y1, y2 = sz[a], sz[b], sz[c]
            area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if area >= 0:    # back face (screen-space winding)
                continue
            xmin, xmax = int(max(0, np.floor(min(x0, x1, x2)))), int(min(W - 1, np.ceil(max(x0, x1, x2))))
            ymin, ymax = int(max(0, np.floor(min(y0, y1, y2)))), int(min(Hh - 1, np.ceil(max(y0, y1, y2))))
            if xmax < xmin or ymax < ymin:
                continue
            xs = np.arange(xmin, xmax + 1) + 0.5
            ys = np.arange(ymin, ymax + 1) + 0.5
            X, Y = np.meshgrid(xs, ys)
            w0 = ((x1 - X) * (y2 - Y) - (x2 - X) * (y1 - Y)) / area
            w1 = ((x2 - X) * (y0 - Y) - (x0 - X) * (y2 - Y)) / area
            w2 = 1 - w0 - w1
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not m.any():
                continue
            d = w0 * dep[a] + w1 * dep[b] + w2 * dep[c]
            zb = zbuf[ymin:ymax + 1, xmin:xmax + 1]
            m &= d > zb
            if not m.any():
                continue
            colr = (w0[..., None] * col[a] + w1[..., None] * col[b] + w2[..., None] * col[c])
            lm = w0 * lam[a] + w1 * lam[b] + w2 * lam[c]
            # cel steps like the toon shader
            band = np.where(lm > 0.62, 1.12, np.where(lm > 0.32, 1.0, np.where(lm > 0.08, 0.86, 0.72)))
            sub = img[ymin:ymax + 1, xmin:xmax + 1]
            sub[m] = np.clip(colr[m] * band[m][:, None], 0, 1)
            zb[m] = d[m]
    return img


def preview(parts, atlas, path, views=(0, 90, 180), size=460, ao_map=None):
    items = []
    for p in parts:
        if len(p.V) == 0:
            continue
        N = G.vertex_normals(p.V, p.F)
        ao = None if ao_map is None else ao_map.get(id(p))
        items.append((p.V, p.F, part_colors(atlas, p, ao), N))
    tiles = [render_view(items, size, yaw=v) for v in views]
    out = np.hstack(tiles)
    Image.fromarray((out * 255).astype(np.uint8)).save(path)

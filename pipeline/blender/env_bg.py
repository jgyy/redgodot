"""Richer pixel painting for the 3D battle stages (numpy; no bpy).  gen_battlebg.py projects a 320x180 "screen" texture
onto every plane, so anything painted here is pixel art from the battle camera - but it is painted in *world space*:
floors are evaluated on the ground plane (perspective-correct tiles, planks, slabs, blades of grass whose size follows
their distance), walls on the back-wall plane (panels, banners, strata).  Upstream's own painters stay the base layer
(so palette, horizon and composition keep parity); these functions overlay or replace their detail.

`G` is a small camera object supplied by gen_battlebg: G.floor_coords() -> (X, D, valid) per screen pixel,
G.wall_coords(depth) -> (X, Y), G.to_px(pt), G.px_scale(depth).
"""
import math

import numpy as np

import upstream_px as U

W, H = 320, 180


def _rgb(c):
    return np.array(U.hexc(c) if isinstance(c, str) else c, dtype=np.float32)


def hnoise(seed, *idx):
    """Cheap deterministic float in 0..1 from ints (numpy friendly)."""
    h = np.uint64(seed * 2654435761 % (1 << 32))
    for i in idx:
        h = (h ^ (np.asarray(i, dtype=np.int64).astype(np.uint64) + np.uint64(0x9E3779B9) + (h << np.uint64(6)) + (h >> np.uint64(2)))) & np.uint64(0xFFFFFFFF)
        h = (h * np.uint64(2246822519)) & np.uint64(0xFFFFFFFF)
        h ^= h >> np.uint64(15)
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(1 << 24)


def vnoise(x, y, seed=1):
    """Smooth value noise on float arrays (0..1)."""
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hnoise(seed, x0, y0), hnoise(seed, x0 + 1, y0)
    c, d = hnoise(seed, x0, y0 + 1), hnoise(seed, x0 + 1, y0 + 1)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(x, y, seed=1, octaves=3):
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        out = out + vnoise(x * (2 ** o), y * (2 ** o), seed + o * 13) * amp
        tot += amp
        amp *= 0.5
    return out / tot


def to_surf(s, img, valid=None):
    """Write an (H,W,3) float 0..255 image into Surf s where valid."""
    a = np.clip(img, 0, 255).astype(np.uint8)
    if valid is None:
        s.a[:, :, 0:3] = a
        s.a[:, :, 3] = 255
    else:
        s.a[valid, 0:3] = a[valid]
        s.a[valid, 3] = 255


def surf_rgb(s):
    return s.a[:, :, 0:3].astype(np.float32)


# ---------------------------------------------------------------- scatter helpers (screen-space strokes at world positions)
class Scatter:
    def __init__(self, G, s, seed):
        self.G, self.s = G, s
        self.rs = np.random.RandomState(seed)

    def points(self, n, x_span=13.0, d_near=1.3, d_far=12.0, y_min_px=0):
        """n random ground points (X, D) biased toward the camera (uniform in screen-area, roughly)."""
        rs = self.rs
        out = []
        for _ in range(n):
            u = rs.rand()
            d = d_near + (d_far - d_near) * u ** 1.5
            x = (rs.rand() * 2 - 1) * x_span * (0.35 + d * 0.11)
            px, py = self.G.to_px(np.array([x, 0.0, -d]))
            if 0 <= px < W and y_min_px <= py < H:
                out.append((x, d, px, py))
        return out

    def put(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.s.a[y, x, 0:3] = c
            self.s.a[y, x, 3] = 255

    def blade(self, px, py, h, c, tip=None, lean=0):
        for i in range(int(h)):
            col = c if (i < h - 1 or tip is None) else tip
            self.put(px + lean * (i / max(1, h - 1)) * 0.9, py - i, col)

    def disc(self, px, py, rx, ry, c, hi=None, lo=None):
        for yy in range(int(-ry) - 1, int(ry) + 2):
            for xx in range(int(-rx) - 1, int(rx) + 2):
                e = (xx / max(rx, 0.5)) ** 2 + (yy / max(ry, 0.5)) ** 2
                if e <= 1.0:
                    col = c
                    if hi is not None and xx + yy < -(rx + ry) * 0.2:
                        col = hi
                    elif lo is not None and xx + yy > (rx + ry) * 0.25:
                        col = lo
                    self.put(px + xx, py + yy, col)

    def line(self, x0, y0, x1, y1, c):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / max(1, n)
            self.put(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, c)


def px_per_m(G, d):
    return 1.0 / G.px_scale(d)


# ---------------------------------------------------------------- ground overlays
def grass_blades(G, s, base_cols, seed=1, n=5200, flowers=True, litter=None):
    """Blades, clover and tiny flowers sprinkled over a grass ground in world space."""
    sc = Scatter(G, s, seed)
    cA, cB, cC = [_rgb(c) for c in base_cols]
    dark = np.clip(cA * 0.78, 0, 255)
    light = np.clip(cC * 1.03 + 12, 0, 255)
    tip = np.clip(cC * 1.12 + 26, 0, 255)
    for x, d, px, py in sc.points(n, d_near=1.2, d_far=12.2, y_min_px=60):
        h = max(1, min(6, round(0.17 * px_per_m(G, d))))
        r = sc.rs.rand()
        lean = sc.rs.randint(-1, 2)
        if r < 0.5:
            sc.blade(px, py, h, light, tip, lean)
        elif r < 0.85:
            sc.blade(px, py, h, dark, None, lean)
        else:
            sc.blade(px, py, max(1, h - 1), cB, tip, lean)
    if flowers:
        cols = [(255, 250, 240), (255, 226, 96), (255, 170, 200), (200, 220, 255)]
        for x, d, px, py in sc.points(150, d_near=1.6, d_far=11.0, y_min_px=70):
            k = sc.rs.randint(0, 4)
            r = max(1, round(0.045 * px_per_m(G, d)))
            c = cols[k]
            if r >= 2:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    sc.put(px + dx * (r - 1), py + dy * (r - 1), c)
                sc.put(px, py, (255, 200, 60))
                sc.blade(px, py + 1, max(1, r), dark)
            else:
                sc.put(px, py, c)
    if litter:
        lc = [_rgb(c) for c in litter]
        for x, d, px, py in sc.points(420, d_near=1.2, d_far=11.0, y_min_px=70):
            sc.put(px, py, lc[sc.rs.randint(0, len(lc))])
            if px_per_m(G, d) > 12:
                sc.put(px + 1, py, lc[sc.rs.randint(0, len(lc))])


def pebbles(G, s, cols, seed=2, n=260, dmax=11.0):
    """Rounded stones with a lit upper-left and a shadow lower-right; cols = (dark, mid, light, contact-shadow)."""
    sc = Scatter(G, s, seed)
    dk, md, lt, sh = [_rgb(c) for c in cols]
    for x, d, px, py in sc.points(n, d_near=1.2, d_far=dmax, y_min_px=70):
        w = max(1.0, 0.16 * px_per_m(G, d) * (0.4 + sc.rs.rand()))
        h = max(1.0, w * 0.55)
        sc.disc(px + 1, py + 1, w, h * 0.8, sh)
        sc.disc(px, py, w, h, md, lt, dk)


def cracks(G, s, col, seed=3, n=18, dmax=10.0):
    sc = Scatter(G, s, seed)
    c = _rgb(col)
    for x, d, px, py in sc.points(n, d_near=1.4, d_far=dmax, y_min_px=76):
        ppm = px_per_m(G, d)
        cx, cy = px, py
        ang = sc.rs.rand() * math.pi
        for _ in range(sc.rs.randint(3, 8)):
            ang += (sc.rs.rand() - 0.5) * 1.2
            L = (0.25 + sc.rs.rand() * 0.4) * ppm
            nx, ny = cx + math.cos(ang) * L, cy + math.sin(ang) * L * 0.42
            sc.line(cx, cy, nx, ny, c)
            cx, cy = nx, ny


def sparkles(G, s, col, seed=4, n=70, y_min_px=70):
    sc = Scatter(G, s, seed)
    c = _rgb(col)
    for x, d, px, py in sc.points(n, d_near=1.5, d_far=12.0, y_min_px=y_min_px):
        sc.put(px, py, c)
        if sc.rs.rand() < 0.4:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                sc.put(px + dx, py + dy, c * 0.75 + 60)


# ---------------------------------------------------------------- perspective floors (replace the base)
def _shade_lin(img, k):
    return np.clip(img * k[..., None], 0, 255)


def floor_tiles(G, s, y0, cA, cB, grout, tile=0.95, seed=5, gloss=True, ring=None):
    """Polished floor tiles: checker of cA/cB, grout lines, speckle, a soft window-light sheen and a reflection band."""
    X, D, valid = G.floor_coords()
    valid = valid & (np.arange(H)[:, None] >= y0)
    a, b, g = _rgb(cA), _rgb(cB), _rgb(grout)
    u, v = X / tile, D / tile
    iu, iv = np.floor(u), np.floor(v)
    check = ((iu + iv) % 2).astype(np.float32)
    img = a[None, None, :] * (1 - check[..., None]) + b[None, None, :] * check[..., None]
    n = hnoise(seed, iu, iv)
    img = img * (0.95 + 0.1 * n[..., None])
    fu, fv = u - iu, v - iv
    # grout: thin lines; a bevel highlight on the tile's near/left edges
    line_w = 0.03 + 0.012 * D / 6.0
    gl = ((fu < line_w) | (fv < line_w * 1.4)) & valid
    img[gl] = g
    hl = ((fu > line_w) & (fu < line_w * 2.6) & (fv > line_w)) | ((fv > line_w * 1.4) & (fv < line_w * 3.2))
    img = np.where(hl[..., None] & ~gl[..., None], img * 1.07, img)
    if gloss:
        sheen = np.exp(-((X - 1.2) / 3.4) ** 2) * (0.9 - np.clip(D / 14.0, 0, 0.8))
        img = img + sheen[..., None] * 9.0
    if ring is not None:                       # a painted circle around the arena
        cx, cz, r1, r2, rc = ring
        dd = np.sqrt((X - cx) ** 2 + ((D - cz) * 1.0) ** 2)
        band = (dd > r1) & (dd < r2)
        img = np.where(band[..., None], _rgb(rc)[None, None, :], img)
    to_surf(s, img, valid)


def floor_planks(G, s, y0, cols, grain, seed=6, plank=0.32, run_along='z'):
    """Wooden planks running away from the camera, with butt joints, grain, knots and a worn centre."""
    X, D, valid = G.floor_coords()
    valid = valid & (np.arange(H)[:, None] >= y0)
    c0, c1, c2 = [_rgb(c) for c in cols]
    gr = _rgb(grain)
    u = X / plank
    iu = np.floor(u)
    fu = u - iu
    # butt joints every ~2.2 m, staggered by plank
    off = hnoise(seed, iu) * 2.2
    seg = np.floor((D + off) / 2.2)
    tone = hnoise(seed + 1, iu, seg)
    img = c0[None, None, :] * (1 - tone[..., None]) + c1[None, None, :] * tone[..., None]
    graint = fbm(X * 9.0, D * 0.55, seed + 2, 3)
    img = img * (0.9 + 0.2 * graint[..., None])
    img = np.where((graint > 0.72)[..., None], img * 0.88, img)
    seam = (fu < 0.05)
    img = np.where(seam[..., None], gr[None, None, :], img)
    fd = (D + off) / 2.2 - seg
    joint = fd < 0.012 + 0.002 * D
    img = np.where(joint[..., None], gr[None, None, :] * 0.9, img)
    lit = (fu > 0.06) & (fu < 0.16)
    img = np.where(lit[..., None] & ~seam[..., None], np.minimum(img * 1.06 + 4, 255), img)
    wear = np.exp(-(X / 4.5) ** 2) * 0.09
    img = img * (1 + wear[..., None])
    to_surf(s, img, valid)


def floor_slabs(G, s, y0, cols, joint, seed=7, size=1.25, glow=None):
    """Large stone slabs with worn edges, cracks, and optional glowing moss/rune light."""
    X, D, valid = G.floor_coords()
    valid = valid & (np.arange(H)[:, None] >= y0)
    c0, c1, c2 = [_rgb(c) for c in cols]
    j = _rgb(joint)
    u, v = X / size, D / size
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    tone = hnoise(seed, iu, iv)
    img = c0[None, None, :] * (1 - tone[..., None]) + c1[None, None, :] * tone[..., None]
    mott = fbm(X * 2.4, D * 2.4, seed + 3, 4)
    img = img * (0.86 + 0.3 * mott[..., None])
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    lw = 0.035 + 0.004 * D
    img = np.where((edge < lw)[..., None], j[None, None, :], img)
    img = np.where(((edge > lw) & (edge < lw * 2.4) & (fu < 0.5) & (fv < 0.5))[..., None], np.minimum(img * 1.08, 255), img)
    # cracks: thin ridged noise
    rid = np.abs(fbm(X * 1.6 + iu * 0.3, D * 1.6, seed + 9, 3) - 0.5)
    img = np.where((rid < 0.008 + 0.0008 * D)[..., None], j[None, None, :] * 0.85, img)
    if glow is not None:
        gc = _rgb(glow)
        gn = np.clip((fbm(X * 0.9, D * 0.9, seed + 5, 3) - 0.62) * 5, 0, 1) * 0.55
        img = img * (1 - gn[..., None]) + gc[None, None, :] * gn[..., None]
    to_surf(s, img, valid)


def floor_grate(G, s, y0, cols, hazard=('#e8c020', '#1a1a1c'), seed=8, plate=1.6):
    """Industrial floor plates: bolted steel plates, diamond tread, oil stains and hazard stripes."""
    X, D, valid = G.floor_coords()
    valid = valid & (np.arange(H)[:, None] >= y0)
    c0, c1, c2 = [_rgb(c) for c in cols]
    u, v = X / plate, D / plate
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    tone = hnoise(seed, iu, iv)
    img = c0[None, None, :] * (1 - tone[..., None]) + c1[None, None, :] * tone[..., None]
    # diamond tread
    tread = ((np.floor(X * 9) + np.floor(D * 9)) % 2).astype(np.float32)
    img = img * (0.94 + 0.08 * tread[..., None])
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    img = np.where((edge < 0.03)[..., None], c0[None, None, :] * 0.45, img)
    img = np.where(((edge > 0.03) & (edge < 0.07))[..., None], np.minimum(c2[None, None, :] * 0.9, 255), img)
    for (bx, by) in ((0.1, 0.12), (0.9, 0.12), (0.1, 0.88), (0.9, 0.88)):
        d2 = (fu - bx) ** 2 + (fv - by) ** 2
        img = np.where((d2 < 0.0009)[..., None], np.minimum(c2[None, None, :] * 1.1, 255), img)
    oil = np.clip((fbm(X * 0.7, D * 0.7, seed + 4, 3) - 0.66) * 6, 0, 1) * 0.5
    img = img * (1 - oil[..., None]) + np.array([12, 14, 24], np.float32)[None, None, :] * oil[..., None]
    hz = (np.abs(X) < 9) & (D > 6.4) & (D < 6.95)
    stripe = (np.floor((X + D) * 2.2) % 2 == 0)
    img = np.where((hz & stripe)[..., None], _rgb(hazard[0])[None, None, :] * 0.9, np.where(hz[..., None], _rgb(hazard[1])[None, None, :], img))
    to_surf(s, img, valid)


def floor_marble(G, s, y0, base, vein, seed=9, tile=1.7, ring=None):
    """Elite-four hall: dark polished marble with veins, gold inlay lines and a reflection sheen."""
    X, D, valid = G.floor_coords()
    valid = valid & (np.arange(H)[:, None] >= y0)
    b, vn = _rgb(base), _rgb(vein)
    u, v = X / tile, D / tile
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    tone = hnoise(seed, iu, iv)
    img = b[None, None, :] * (0.85 + 0.3 * tone[..., None])
    rid = np.abs(fbm(X * 0.9 + iu, D * 0.9 + iv, seed + 1, 4) - 0.5)
    veins = np.clip(1 - rid * 22, 0, 1) * 0.45
    img = img * (1 - veins[..., None]) + vn[None, None, :] * veins[..., None]
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    img = np.where((edge < 0.02)[..., None], b[None, None, :] * 0.4, img)
    img = np.where(((edge > 0.02) & (edge < 0.05))[..., None], np.array([214, 178, 92], np.float32)[None, None, :] * 0.8, img)
    sheen = np.exp(-((X - 0.5) / 3.0) ** 2) * (0.8 - np.clip(D / 16.0, 0, 0.7))
    img = img + sheen[..., None] * 14.0
    if ring is not None:
        cx, cz, r1, r2, rc = ring
        dd = np.sqrt((X - cx) ** 2 + (D - cz) ** 2)
        img = np.where(((dd > r1) & (dd < r2))[..., None], _rgb(rc)[None, None, :], img)
    to_surf(s, img, valid)


def sea_crests(G, s, y0, hi, mid, foam, seed=10, t=0.0):
    """World-space wave crests: long foam-tipped swells receding to the horizon, plus glints."""
    X, D, valid = G.floor_coords()
    valid = valid & (np.arange(H)[:, None] >= y0)
    img = surf_rgb(s)
    wave = np.sin(D * 2.1 + np.sin(X * 0.45 + D * 0.3) * 1.6 + np.sin(D * 0.6) * 2.0)
    wave2 = np.sin(D * 3.7 - X * 0.3 + 1.7)
    crest = (wave > 0.86) & valid
    img = np.where(crest[..., None], _rgb(hi)[None, None, :], img)
    mid_m = (wave > 0.66) & (wave <= 0.86) & valid
    img = np.where(mid_m[..., None], img * 0.6 + _rgb(mid)[None, None, :] * 0.4, img)
    foam_m = (wave > 0.93) & (wave2 > 0.55) & valid
    img = np.where(foam_m[..., None], _rgb(foam)[None, None, :], img)
    trough = (wave < -0.8) & valid
    img = np.where(trough[..., None], img * 0.88, img)
    to_surf(s, img, valid)


def sand_ripples(G, s, y0, y1, seed=11):
    """Wind ripples on the beach in world space + wet sand near the water line."""
    X, D, valid = G.floor_coords()
    rows = (np.arange(H)[:, None] >= y0) & (np.arange(H)[:, None] < y1)
    valid = valid & rows
    img = surf_rgb(s)
    rip = np.sin(D * 5.5 + np.sin(X * 0.9) * 1.4 + fbm(X * 0.4, D * 0.4, seed, 2) * 4.0)
    img = np.where(((rip > 0.82) & valid)[..., None], img * 0.93, img)
    img = np.where(((rip < -0.92) & valid)[..., None], np.minimum(img * 1.05 + 4, 255), img)
    to_surf(s, img, valid)


# ---------------------------------------------------------------- wall paintings (plane at depth)
def wall_panels(G, s, depth, top_col, wain_col, trim_col, stripe_col, seed=12, wain_h=1.35):
    """Interior wall: wainscot panels, chair rail, striped wallpaper, crown moulding and pilasters."""
    X, Y = G.wall_coords(depth)
    img = np.zeros((H, W, 3), np.float32)
    t, w, tr, st = _rgb(top_col), _rgb(wain_col), _rgb(trim_col), _rgb(stripe_col)
    upper = Y > wain_h
    # wallpaper stripes
    su = (np.floor(X / 0.38) % 2).astype(np.float32)
    paper = t[None, None, :] * (1 - 0.06 * su[..., None]) + st[None, None, :] * 0.06 * su[..., None]
    paper = paper * (0.97 + 0.06 * fbm(X * 1.5, Y * 1.5, seed, 3)[..., None])
    # wainscot: raised panels
    pu, pv = X / 1.5, (Y - 0.1) / (wain_h - 0.3)
    fu, fv = pu - np.floor(pu), pv - np.floor(pv)
    inset = (fu > 0.12) & (fu < 0.88) & (pv > 0.06) & (pv < 0.94)
    wain = w[None, None, :] * (0.94 + 0.08 * fbm(X * 2, Y * 2, seed + 1, 2)[..., None])
    inner_edge = inset & ((fu < 0.16) | (fu > 0.84) | (pv < 0.12) | (pv > 0.88))
    wain = np.where(inset[..., None], wain * 1.06, wain * 0.9)
    wain = np.where(inner_edge[..., None], wain * 0.86, wain)
    img = np.where(upper[..., None], paper, wain)
    rail = (np.abs(Y - wain_h) < 0.085)
    img = np.where(rail[..., None], tr[None, None, :] * 1.05, img)
    rail_sh = (Y > wain_h - 0.15) & (Y < wain_h - 0.085)
    img = np.where(rail_sh[..., None], img * 0.82, img)
    crown = (Y > 3.7) & (Y < 3.95)
    img = np.where(crown[..., None], tr[None, None, :] * (1.0 - 0.15 * (Y[..., None] - 3.7) * 4), img)
    pil = np.abs(((X + 2.2) % 6.0) - 3.0) < 0.28
    img = np.where((pil & (Y > 0.05) & (Y < 3.9))[..., None], np.where(((X + 2.2) % 6.0 < 3.0)[..., None], tr[None, None, :] * 1.08, tr[None, None, :] * 0.78), img)
    base = (Y < 0.14)
    img = np.where(base[..., None], tr[None, None, :] * 0.75, img)
    to_surf(s, img)
    return X, Y


def wall_banners(G, s, depth, cols, gold=(232, 190, 92), seed=13):
    """Draw hanging cloth banners with a ring emblem over an already painted wall (gym / elite)."""
    X, Y = G.wall_coords(depth)
    img = surf_rgb(s)
    c0, c1 = _rgb(cols[0]), _rgb(cols[1])
    g = np.array(gold, np.float32)
    for k in range(-3, 4):
        cx = k * 4.4
        inb = (np.abs(X - cx) < 0.7) & (Y > 0.9) & (Y < 3.7)
        # swallow-tail bottom
        tail = (Y < 1.25) & (np.abs(X - cx) < (Y - 0.9) * 2.0)
        inb = inb & ~tail
        shade = 1 - 0.18 * ((X - cx) / 0.7 > 0.55).astype(np.float32)
        cloth = c0[None, None, :] * shade[..., None] * (0.96 + 0.08 * fbm(X * 8, Y * 3, seed + k, 2)[..., None])
        img = np.where(inb[..., None], cloth, img)
        edge = inb & ((np.abs(X - cx) > 0.62) | (Y > 3.6))
        img = np.where(edge[..., None], g[None, None, :] * 0.85, img)
        dd = np.sqrt((X - cx) ** 2 + (Y - 2.5) ** 2)
        ring = inb & (dd > 0.30) & (dd < 0.40)
        img = np.where(ring[..., None], c1[None, None, :] * 1.1, img)
        dot = inb & (dd < 0.16)
        img = np.where(dot[..., None], g[None, None, :], img)
        rod = (np.abs(Y - 3.78) < 0.05) & (np.abs(X - cx) < 0.82)
        img = np.where(rod[..., None], g[None, None, :] * 0.7, img)
    to_surf(s, img)


def wall_stone_arches(G, s, depth, stone, mortar, glow, seed=14):
    """Tower wall: ashlar blocks with arched slit windows glowing violet and hanging mist."""
    X, Y = G.wall_coords(depth)
    st, mt, gl = _rgb(stone), _rgb(mortar), _rgb(glow)
    course = 0.55
    row = np.floor((Y + 0.2) / course)
    off = (row % 2) * 0.7
    bu = np.floor((X + off) / 1.4)
    fu = (X + off) / 1.4 - bu
    fv = (Y + 0.2) / course - row
    tone = hnoise(seed, bu, row)
    img = st[None, None, :] * (0.82 + 0.34 * tone[..., None]) * (0.92 + 0.16 * fbm(X * 3, Y * 3, seed + 1, 3)[..., None])
    line = (fv < 0.07) | (fu < 0.03)
    img = np.where(line[..., None], mt[None, None, :], img)
    img = np.where(((fv > 0.07) & (fv < 0.16) & ~line)[..., None], img * 1.07, img)
    for k in range(-3, 4):
        cx = k * 4.6 + 1.0
        inarch = (np.abs(X - cx) < 0.5) & (Y > 1.6) & (Y < 3.6 + 0.0) & ((Y < 3.0) | (((X - cx) / 0.5) ** 2 + ((Y - 3.0) / 0.6) ** 2 < 1))
        img = np.where(inarch[..., None], gl[None, None, :] * (0.55 + 0.45 * np.clip((Y - 1.6) / 2.0, 0, 1))[..., None], img)
        frame = (np.abs(X - cx) < 0.62) & (Y > 1.5) & (Y < 3.7) & ~inarch & ((Y < 3.0) | (((X - cx) / 0.62) ** 2 + ((Y - 3.0) / 0.72) ** 2 < 1))
        img = np.where(frame[..., None], st[None, None, :] * 1.18, img)
    to_surf(s, img)


def wall_industrial(G, s, depth, plate, seam, lamp, seed=15):
    """Power plant wall: riveted steel panels, cable trays, vents and blinking-lamp studs."""
    X, Y = G.wall_coords(depth)
    p, sm, lp = _rgb(plate), _rgb(seam), _rgb(lamp)
    pu, pv = X / 2.0, Y / 1.4
    iu, iv = np.floor(pu), np.floor(pv)
    fu, fv = pu - iu, pv - iv
    tone = hnoise(seed, iu, iv)
    img = p[None, None, :] * (0.86 + 0.24 * tone[..., None]) * (0.95 + 0.1 * fbm(X * 4, Y * 4, seed + 1, 3)[..., None])
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    img = np.where((edge < 0.018)[..., None], sm[None, None, :], img)
    img = np.where(((edge > 0.018) & (edge < 0.05) & (fu < 0.5))[..., None], np.minimum(img * 1.14, 255), img)
    for (bx, by) in ((0.08, 0.1), (0.92, 0.1), (0.08, 0.9), (0.92, 0.9)):
        d2 = (fu - bx) ** 2 + (fv - by) ** 2
        img = np.where((d2 < 0.0011)[..., None], np.minimum(p[None, None, :] * 1.5 + 20, 255), img)
    vent = (np.abs(((X + 3.0) % 9.0) - 4.5) < 1.0) & (Y > 1.6) & (Y < 2.5)
    slats = (np.floor(Y / 0.11) % 2 == 0)
    img = np.where((vent & slats)[..., None], sm[None, None, :] * 0.5, np.where(vent[..., None], img * 0.7, img))
    tray = (Y > 3.15) & (Y < 3.45)
    img = np.where(tray[..., None], sm[None, None, :] * 0.8, img)
    cab = tray & ((Y - 3.15) % 0.1 < 0.05)
    img = np.where(cab[..., None], np.array([170, 90, 60], np.float32)[None, None, :], img)
    for k in range(-5, 6):
        lx = k * 2.0 + 1.0
        lamp_m = ((X - lx) ** 2 + (Y - 2.9) ** 2) < 0.012
        on = hnoise(seed + 5, k) > 0.45
        img = np.where(lamp_m[..., None], (lp if on else lp * 0.3)[None, None, :], img)
    to_surf(s, img)


def wall_wallpaper(G, s, depth, base, pattern, wood, seed=16):
    """Haunted mansion wall: damask wallpaper over dark wood wainscoting with picture frames."""
    X, Y = G.wall_coords(depth)
    b, p, w = _rgb(base), _rgb(pattern), _rgb(wood)
    wain_h = 1.45
    u, v = X / 0.9, Y / 0.9
    fu, fv = u - np.floor(u), v - np.floor(v)
    damask = (np.abs(fu - 0.5) + np.abs(fv - 0.5) * 0.9 < 0.32) & (np.abs(fu - 0.5) + np.abs(fv - 0.5) * 0.9 > 0.2)
    dots = ((fu - 0.5) ** 2 + (fv - 0.5) ** 2) < 0.01
    paper = b[None, None, :] * (0.92 + 0.14 * fbm(X * 1.2, Y * 1.2, seed, 4)[..., None])
    paper = np.where((damask | dots)[..., None], paper * 0.78 + p[None, None, :] * 0.22, paper)
    pu, pv = X / 1.1, Y / wain_h
    gu = pu - np.floor(pu)
    wain = w[None, None, :] * (0.88 + 0.2 * fbm(X * 6, Y * 0.8, seed + 2, 3)[..., None])
    wain = np.where(((gu > 0.08) & (gu < 0.92) & (pv > 0.1) & (pv < 0.9))[..., None], wain * 1.12, wain * 0.85)
    img = np.where((Y > wain_h)[..., None], paper, wain)
    rail = np.abs(Y - wain_h) < 0.07
    img = np.where(rail[..., None], w[None, None, :] * 1.28, img)
    for k in range(-3, 4):
        cx = k * 3.9 + 0.5
        fr = (np.abs(X - cx) < 0.62) & (np.abs(Y - 2.7) < 0.82)
        img = np.where(fr[..., None], np.array([196, 150, 76], np.float32)[None, None, :] * (0.7 + 0.3 * hnoise(seed + 9, k)), img)
        inner = (np.abs(X - cx) < 0.5) & (np.abs(Y - 2.7) < 0.7)
        pic = 0.35 + 0.4 * fbm(X * 4 + k * 3.0, Y * 4, seed + 11 + k, 3)
        col = np.array([54, 44, 60], np.float32)[None, None, :] * pic[..., None] + np.array([30, 20, 20], np.float32)[None, None, :]
        img = np.where(inner[..., None], col, img)
    sconce = ((np.abs(((X + 2.0) % 3.9) - 1.95) < 0.09) & (Y > 2.4) & (Y < 2.9))
    to_surf(s, img)


def wall_strata(G, s, depth, hi, seed=20):
    """Overlay on a cave/ice back wall: sedimentary strata, mineral veins and glints in world space."""
    X, Y = G.wall_coords(depth)
    img = surf_rgb(s)
    h = _rgb(hi)
    warp = fbm(X * 0.7, Y * 0.7, seed, 3) * 2.2
    band = np.sin((Y * 2.3 + warp) * 2.2)
    img = np.where((band > 0.82)[..., None], np.minimum(img * 1.12 + 5, 255), img)
    img = np.where((band < -0.86)[..., None], img * 0.86, img)
    vein = np.abs(fbm(X * 0.5 + 3.0, Y * 0.5, seed + 3, 4) - 0.5)
    img = np.where((vein < 0.012)[..., None], img * 0.55 + h[None, None, :] * 0.45, img)
    xs = np.arange(W)[None, :].repeat(H, 0)
    ys = np.arange(H)[:, None].repeat(W, 1)
    glint = hnoise(seed + 9, xs, ys) > 0.9965
    img = np.where(glint[..., None] & (ys[..., None] < 132), h[None, None, :], img)
    to_surf(s, img)


def puddles(G, s, dark, light, seed=7, n=7):
    sc = Scatter(G, s, seed)
    dk, lt = _rgb(dark), _rgb(light)
    for x, d, px, py in sc.points(n, d_near=2.0, d_far=10.5, y_min_px=78):
        rx = (0.5 + sc.rs.rand() * 0.9) * px_per_m(G, d)
        sc.disc(px, py, rx, rx * 0.25, dk)
        sc.disc(px - rx * 0.15, py - 0.5, rx * 0.55, max(0.6, rx * 0.09), lt)


def shore_foam(G, s, y0, y1):
    """Foam line where the sea meets the beach."""
    img = surf_rgb(s)
    ys = np.arange(H)[:, None].repeat(W, 1)
    xs = np.arange(W)[None, :].repeat(H, 0)
    edge = y0 + 3 + (np.sin(xs * 0.13) * 1.5 + np.sin(xs * 0.41 + 2) * 0.8).astype(np.int64)
    band = (ys >= edge - 2) & (ys <= edge)
    foam = np.array([248, 252, 255], np.float32)
    dots = hnoise(3, xs, ys) > 0.35
    img = np.where((band & dots)[..., None], foam[None, None, :], img)
    wet = (ys > edge) & (ys < edge + 5)
    img = np.where(wet[..., None], img * 0.93, img)
    to_surf(s, img)


# ---------------------------------------------------------------- battle platforms
def platform_top(size, cols, kind, base_kind, seed=1):
    """Top of a battle platform (unit disc, v>0 = front): upstream's painter + world-detail overlays."""
    s = U.paint_platform_top(size, cols, base_kind)
    img = s.a[:, :, 0:3].astype(np.float32)
    ys, xs = np.mgrid[0:size, 0:size]
    dx = (xs + 0.5) / (size / 2) - 1
    dy = (ys + 0.5) / (size / 2) - 1
    d = dx * dx + dy * dy
    inside = d <= 1.0
    core = d < 0.62
    rs = np.random.RandomState(seed)
    c = [np.array(x, np.float32) for x in cols]

    def put(mask, colour, k=1.0):
        nonlocal img
        img = np.where(mask[..., None], img * (1 - k) + np.asarray(colour, np.float32)[None, None, :] * k, img)

    if kind in ('grass', 'forest'):
        for _ in range(int(size * size * 0.06)):
            x, y = rs.randint(0, size), rs.randint(0, size)
            if d[y, x] < 0.7:
                col = c[3] if rs.rand() < 0.55 else c[0]
                for i in range(rs.randint(2, 4)):
                    if y - i >= 0:
                        img[y - i, x] = col * (0.95 + 0.1 * i / 3.0)
        for _ in range(9):
            x, y = rs.randint(0, size), rs.randint(0, size)
            if d[y, x] < 0.6:
                for dx_, dy_ in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    img[y + dy_, x + dx_] = (255, 250, 240)
                img[y, x] = (255, 214, 80)
        put(d > 0.84, c[3] * 1.05, 0.0)
    elif kind in ('rock', 'mountain'):
        n = fbm(dx * 3.2, dy * 3.2, seed, 4)
        put(core & (n > 0.62), c[1], 0.55)
        put(core & (n < 0.3), c[3], 0.35)
        for _ in range(3):
            x, y = rs.randint(0, size), rs.randint(0, size)
            ang = rs.rand() * 6.28
            for i in range(rs.randint(10, 26)):
                x += int(round(math.cos(ang) * 1.2))
                y += int(round(math.sin(ang) * 1.2))
                ang += (rs.rand() - 0.5) * 0.9
                if 0 <= x < size and 0 <= y < size and d[y, x] < 0.8:
                    img[y, x] = c[0] * 0.7
    elif kind == 'water':
        for r_ in (0.28, 0.5, 0.7, 0.86):
            ring = np.abs(np.sqrt(d) - r_) < 0.018
            put(ring & inside, (230, 246, 255), 0.75)
        put(d > 0.92, (240, 250, 255), 0.6)
        put(core & (fbm(dx * 5, dy * 5, seed, 3) > 0.7), c[3], 0.4)
    elif kind in ('floor', 'metal', 'tower', 'wood'):
        if kind == 'wood':
            plank = np.floor((dx + 1) * 5.0)
            fu = (dx + 1) * 5.0 - plank
            put(core & (fu < 0.07), c[0] * 0.8, 0.9)
            put(core & (hnoise(seed, plank.astype(np.int64)) > 0.5) & (fu > 0.15) & (fu < 0.9), c[3], 0.10)
            for k in range(3):
                jy = int(size * (0.25 + 0.25 * k + 0.08 * hnoise(seed, k)))
                put(core & (np.abs(ys - jy) < 1), c[0] * 0.75, 0.8)
        elif kind == 'metal':
            gx, gy = np.abs(((dx + 1) * 3.0) % 1.0 - 0.5), np.abs(((dy + 1) * 3.0) % 1.0 - 0.5)
            put(core & ((gx > 0.47) | (gy > 0.47)), c[0] * 0.7, 0.9)
            for a_ in range(8):
                bx, by = math.cos(a_ * math.pi / 4) * 0.78, math.sin(a_ * math.pi / 4) * 0.78
                put(((dx - bx) ** 2 + (dy - by) ** 2) < 0.0016, c[3], 1.0)
            put((np.abs(np.sqrt(d) - 0.9) < 0.03) & inside & (((np.floor((np.arctan2(dy, dx) + 3.15) * 4)) % 2) == 0), (232, 192, 32), 0.9)
        elif kind == 'tower':
            put(np.abs(np.sqrt(d) - 0.62) < 0.02, (150, 110, 230), 0.9)
            put(np.abs(np.sqrt(d) - 0.36) < 0.014, (150, 110, 230), 0.8)
            for k in range(6):
                a_ = k * math.pi / 3
                put((np.abs(dx * math.cos(a_) + dy * math.sin(a_)) < 0.012) & (d < 0.4) & core, (150, 110, 230), 0.7)
            put(core & (fbm(dx * 4, dy * 4, seed, 3) > 0.66), c[3], 0.35)
        else:
            gx, gy = np.abs(((dx + 1) * 2.5) % 1.0 - 0.5), np.abs(((dy + 1) * 2.5) % 1.0 - 0.5)
            put(core & ((gx > 0.485) | (gy > 0.485)), c[0], 0.9)
            put(core & (((np.floor((dx + 1) * 2.5) + np.floor((dy + 1) * 2.5)) % 2) == 0), c[3], 0.08)
            sheen = np.exp(-((dx + dy * 0.6 + 0.35) / 0.28) ** 2) * 0.12
            img = img + sheen[..., None] * 60 * core[..., None]
    elif kind == 'ice':
        for _ in range(7):
            x, y = size // 2 + rs.randint(-8, 8), size // 2 + rs.randint(-8, 8)
            ang = rs.rand() * 6.28
            for i in range(rs.randint(18, 44)):
                x += int(round(math.cos(ang) * 1.1))
                y += int(round(math.sin(ang) * 1.1))
                ang += (rs.rand() - 0.5) * 0.7
                if 0 <= x < size and 0 <= y < size and d[y, x] < 0.85:
                    img[y, x] = (250, 254, 255)
                    if y + 1 < size:
                        img[y + 1, x] = c[1]
    elif kind == 'sand':
        rip = np.sin((dy * 9.0 + np.sin(dx * 3.0) * 0.8 + fbm(dx * 2, dy * 2, seed, 2) * 2.0) * 2.0)
        put(core & (rip > 0.85), c[3], 0.5)
        put(core & (rip < -0.9), c[1], 0.5)
        for _ in range(5):
            x, y = rs.randint(0, size), rs.randint(0, size)
            if d[y, x] < 0.6:
                img[y, x] = (255, 236, 220)
                img[y, min(size - 1, x + 1)] = (240, 200, 180)
    a = np.clip(img, 0, 255).astype(np.uint8)
    s.a[:, :, 0:3] = a
    return s


def platform_side(kind, cols, w=256, h=24, seed=2):
    """The rim of a platform, painted flat (u around the circumference, v = top -> bottom)."""
    s = U.Surf(w, h)
    rs = np.random.RandomState(seed)
    c = [np.array(x, np.float32) for x in cols]
    ys, xs = np.mgrid[0:h, 0:w]
    v = ys / (h - 1.0)
    base = c[0] * (1.0 - 0.35 * v[..., None]) + c[1] * 0.0
    if kind in ('grass', 'forest'):
        soil = np.array([88, 64, 44], np.float32)
        img = soil[None, None, :] * (0.7 + 0.5 * fbm(xs * 0.08, ys * 0.2, seed, 3)[..., None]) * (1.0 - 0.4 * v[..., None])
        fringe = (ys < 4 + (np.sin(xs * 0.5) * 1.5 + hnoise(seed, xs) * 2.5).astype(np.int64))
        img = np.where(fringe[..., None], c[1] * (0.9 + 0.3 * hnoise(seed + 1, xs, ys)[..., None]), img)
        for _ in range(60):
            x, y = rs.randint(0, w), rs.randint(6, h)
            img[y, x] = (60, 44, 30)
    elif kind in ('rock', 'mountain', 'tower'):
        band = np.sin((ys + fbm(xs * 0.05, ys * 0.2, seed, 3) * 8.0) * 0.9)
        img = c[1][None, None, :] * (0.85 + 0.25 * fbm(xs * 0.06, ys * 0.25, seed + 3, 3)[..., None]) * (1.0 - 0.45 * v[..., None])
        img = np.where((band > 0.75)[..., None], img * 0.72, img)
        cr = (np.abs(fbm(xs * 0.05, ys * 0.1, seed + 5, 3) - 0.5) < 0.012)
        img = np.where(cr[..., None], c[0] * 0.6, img)
    elif kind == 'wood':
        pl = (xs // 16)
        img = c[1][None, None, :] * (0.85 + 0.3 * hnoise(seed, pl)[..., None]) * (1.0 - 0.35 * v[..., None])
        img = np.where(((xs % 16) < 1)[..., None], c[0] * 0.5, img)
        img = np.where(((ys > 3) & (ys < 5) & ((xs % 16) == 8))[..., None], c[3][None, None, :], img)
    elif kind in ('floor', 'metal'):
        img = c[1][None, None, :] * (1.0 - 0.4 * v[..., None])
        img = np.where(((xs % 32) < 1)[..., None], c[0] * 0.6, img)
        img = np.where((ys < 2)[..., None], c[3], img)
        img = np.where((ys > h - 3)[..., None], c[0] * 0.6, img)
        if kind == 'metal':
            img = np.where(((((xs + ys) // 6) % 2 == 0) & (ys > 8) & (ys < h - 6))[..., None], np.array([232, 192, 32], np.float32)[None, None, :] * 0.85, img)
    elif kind == 'ice':
        img = c[1][None, None, :] * (1.0 - 0.3 * v[..., None]) + c[3][None, None, :] * 0.25 * (fbm(xs * 0.07, ys * 0.15, seed, 3)[..., None])
        icicle = ys > (h * 0.55 + (np.abs(np.sin(xs * 0.35)) * h * 0.4))
        img = np.where(icicle[..., None], np.array([0, 0, 0], np.float32), img)
    elif kind == 'water':
        img = c[1][None, None, :] * (1.0 - 0.25 * v[..., None])
        img = np.where((ys < 3)[..., None], np.array([240, 250, 255], np.float32), img)
    else:   # sand
        img = c[1][None, None, :] * (0.9 + 0.2 * hnoise(seed, xs, ys)[..., None]) * (1.0 - 0.35 * v[..., None])
        img = np.where((ys < 2)[..., None], c[3], img)
    s.a[:, :, 0:3] = np.clip(img, 0, 255).astype(np.uint8)
    s.a[:, :, 3] = 255
    if kind == 'ice':
        # icicle cut-outs stay opaque dark-blue so the skirt stays a closed surface
        m = (s.a[:, :, 0:3].sum(axis=2) == 0)
        s.a[m, 0:3] = np.array([60, 110, 150], np.uint8)
    return s

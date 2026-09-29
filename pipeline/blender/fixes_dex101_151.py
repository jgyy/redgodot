"""Hand-tuned per-species fixes for Pokedex #101-151.  Register with @fix('NAME'); see species_fixes.py for the API.

Most species here are *rebuilt* from a hand-made part list (`new(d, pal)` then `put(d, group, depth, parts...)`)
so the model is the real Pokemon seen from a front / three-quarter view rather than an extruded 2D sprite.
Sprite space: 64x64, x right, y DOWN (ground ~60), depth `cd` < 0 toward the viewer; the `body` group is the depth anchor (0).
"""
import math

from species_fixes import *  # noqa: F401,F403  (fix, E, Cap, Poly, Stroke, Spot, add, drop, mod, thick, scale, shift, dup, claws ...)


# ============================================================================ tiny part DSL
def new(d, pal):
    d['parts'] = []
    d['pal'] = dict(pal)
    return d


def e(x, y, rx, ry, c, rd=None, dd=0.0, rot=0, **kw):
    p = {'t': 'e', 'x': x, 'y': y, 'rx': rx, 'ry': ry, 'c': c}
    if rd is not None:
        p['rd'] = rd
    if dd:
        p['d'] = dd
    if rot:
        p['rot'] = rot
    p.update(kw)
    return p


def cap(x1, y1, x2, y2, r1, r2, c, d1=0.0, d2=0.0, dd=0.0, **kw):
    p = {'t': 'c', 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'r1': r1, 'r2': r2, 'c': c}
    if d1:
        p['d1'] = d1
    if d2:
        p['d2'] = d2
    if dd:
        p['d'] = dd
    p.update(kw)
    return p


def stroke(pts, w, c, w2=None, d1=0.0, d2=0.0, dd=0.0, **kw):
    p = {'t': 'l', 'pts': list(pts), 'w': w, 'c': c}
    if w2 is not None:
        p['w2'] = w2
    if d1:
        p['d1'] = d1
    if d2:
        p['d2'] = d2
    if dd:
        p['d'] = dd
    p.update(kw)
    return p


def plate(pts, c, T=None, dd=0.0, **kw):
    p = {'t': 'p', 'pts': list(pts), 'c': c}
    if T is not None:
        p['T'] = T
    if dd:
        p['d'] = dd
    p.update(kw)
    return p


def put(d, g, cd, *ps, z=None):
    """Add parts to group `g` whose depth (toward the viewer = negative) is forced to `cd`."""
    zz = round(-cd * 0.5, 3) if z is None else z
    for p in ps:
        if p['t'] == 'e':
            p.setdefault('solid', True)         # never fold a bulge into a texture decal of the group under it
        p['g'] = g
        p['cd'] = cd
        p['z'] = zz
        d['parts'].append(p)


def spot(g, x, y, rx, ry, c, **kw):
    """Paint an ellipse onto group g (texture only).  frontOnly=True keeps it off the back."""
    p = {'t': 'spot', 'x': x, 'y': y, 'rx': rx, 'ry': ry, 'c': c, 'on': g}
    p.update(kw)
    d_ = kw.get('_d')
    return p


def band(g, pts, w, c, **kw):
    p = {'t': 'stripe', 'pts': list(pts), 'w': w, 'c': c, 'on': g}
    p.update(kw)
    return p


def eye(x, y, s=2.4, **kw):
    p = {'t': 'eye', 'x': x, 'y': y, 's': s}
    p.update(kw)
    return p


def mouth(x, y, w=2, style='smile', **kw):
    p = {'t': 'mouth', 'x': x, 'y': y, 'w': w, 'style': style}
    p.update(kw)
    return p


def paint(d, *ps):
    d['parts'].extend(ps)


def curve(pts, per=4, closed=True):
    """Catmull-Rom resampling of a flat [x, y, ...] list (closed by default): smooth silhouettes for fins, wings, leaves."""
    P = [(pts[i], pts[i + 1]) for i in range(0, len(pts) - 1, 2)]
    n = len(P)
    out = []
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = P[(i - 1) % n], P[i], P[(i + 1) % n], P[(i + 2) % n]
        if not closed:
            p0 = P[max(i - 1, 0)]
            p3 = P[min(i + 2, n - 1)]
        for s in range(per):
            t = s / float(per)
            t2, t3 = t * t, t * t * t
            out += [round(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3), 3) for k in (0, 1)]
    if not closed:
        out += [P[-1][0], P[-1][1]]
    return out


def smooth_plate(pts, c, T=None, per=4, **kw):
    return plate(curve(pts, per), c, T=T, **kw)


def toes(d, g, cd, x, y, n=3, gap=2.4, r=1.0, c='#f4efe0', dd=-3.0, spread=0.0, zoff=0.0):
    """A row of little toe / claw balls at the front of a foot centred on (x, y)."""
    ps = []
    for i in range(n):
        f = i - (n - 1) / 2.0
        ps.append(e(x + f * gap, y + abs(f) * spread, r, r * 1.05, c, rd=r * 1.1, dd=dd))
    put(d, g, cd, *ps)


def claw_tips(d, g, cd, x, y, n, gap, length, r, c='#f4efe0', dd=-2.0, dirx=0.0, diry=1.0):
    ps = []
    for i in range(n):
        f = i - (n - 1) / 2.0
        ps.append(cap(x + f * gap, y, x + f * gap * 1.25 + dirx * length, y + diry * length, r, 0.35, c, dd=dd,
                      d1=-f * 0.3, d2=-f * 0.9))
    put(d, g, cd, *ps)


# ============================================================================ #101 - #110
@fix('ELECTRODE')
def electrode(d, look):
    # sphere with a dark seam; angry eyes are on the white half.  A real black outline ring around the seam.
    for p in d['parts']:
        if p.get('g') == 'ball':
            p['rd'] = 19
            p['solid'] = True


@fix('EXEGGCUTE')
def exeggcute(d, look):
    new(d, {'egg': '#f4d2c8', 'crack': '#b8706c', 'eggd': '#e9b8b0'})
    # six eggs in a heap: three in front (bottom), two in the middle, one on top; faces toward the viewer
    eggs = [
        ('e1', 20, 51, -3.0, 'a'), ('e2', 33, 53, -7.5, 'b'), ('e3', 46, 51, -3.0, 'c'),
        ('e4', 26.5, 40, -1.0, 'd'), ('e5', 40, 40, -1.0, 'e'), ('e6', 33, 29.5, 1.0, 'f'),
    ]
    for g, x, y, cd, k in eggs:
        put(d, g, cd, e(x, y, 7.2, 8.2, 'egg', rd=7.2))
    paint(d,
          band('e2', [29, 46.5, 31, 44.8, 33, 46.5, 35, 44.8, 37, 46.5], 0.9, 'crack'),
          band('e4', [22, 35.5, 24, 33.8, 26, 35.5, 28, 33.8, 30, 35.5], 0.9, 'crack'),
          band('e6', [29, 24, 31, 22.3, 33, 24, 35, 22.3, 37, 24], 0.9, 'crack'),
          band('e3', [42, 46, 44, 44.3, 46, 46, 48, 44.3, 50, 46], 0.9, 'crack'),
          # faces (the six differ: smile, sleepy, sad, cheeky, shocked, grin)
          eye(17.3, 50.5, 1.7, sclera=False), eye(22.8, 50.5, 1.7, sclera=False), mouth(20, 55, 1.6, 'open'),
          eye(30.3, 52.5, 1.6, style='happy'), eye(36, 52.5, 1.6, style='happy'), mouth(33, 56.5, 1.6, 'smile'),
          eye(43.3, 50.5, 1.7, sclera=False), eye(48.8, 50.5, 1.7, sclera=False), mouth(46, 54.5, 1.6, 'frown'),
          eye(23.7, 39.5, 1.7, sclera=False), eye(29.3, 39.5, 1.7, sclera=False), mouth(26.5, 43.5, 1.2, 'line'),
          eye(37.3, 39.5, 1.6, style='closed'), eye(42.8, 39.5, 1.6, style='closed'), mouth(40, 44, 1.6, 'smile'),
          eye(30.3, 29, 1.7, sclera=False), eye(35.8, 29, 1.7, sclera=False), mouth(33, 33.5, 1.6, 'open'))


@fix('EXEGGUTOR')
def exeggutor(d, look):
    pal = {'trunk': '#c8a46a', 'trunkd': '#9a7040', 'head': '#f8e070', 'headd': '#e8b840', 'leaf': '#58a848',
           'leafd': '#3a7c34', 'claw': '#f4eedc', 'base': '#b89058'}
    new(d, pal)
    put(d, 'body', 0, e(32, 51, 11.0, 8.0, 'trunk', rd=8.6), e(32, 37, 7.0, 15, 'trunk', rd=6.4))
    paint(d, band('body', [27.5, 42, 32, 37.5, 36.5, 42, 32, 46.5, 27.5, 42], 1.3, 'trunkd', frontOnly=True),
          band('body', [27, 52, 31.5, 47.5, 36, 52, 31.5, 56.5, 27, 52], 1.2, 'trunkd', frontOnly=True),
          band('body', [32, 51, 36.5, 46.5, 41, 51, 36.5, 55.5, 32, 51], 1.2, 'trunkd', frontOnly=True),
          band('body', [27.5, 30, 32, 26, 36.5, 30], 1.0, 'trunkd', frontOnly=True))
    for s, sx in (('L', -1), ('R', 1)):
        x = 32 + sx * 7.5
        put(d, 'leg' + s, 0.5, cap(x, 53, x + sx * 1.5, 58.4, 5.2, 4.6, 'trunk'))
        put(d, 'foot' + s, -1.0, e(x + sx * 1.6, 59.2, 6.2, 2.8, 'base', dd=-1.5))
        toes(d, 'foot' + s, -1.0, x + sx * 1.6, 60.4, 3, 3.6, 1.2, 'claw', dd=-6.0)
        put(d, 'arm' + s, -0.8, cap(32 + sx * 6.6, 34, 32 + sx * 14.5, 44.5, 3.6, 3.0, 'trunk', d1=-1, d2=-3))
        put(d, 'hand' + s, -1.4, e(32 + sx * 15.5, 46.3, 3.6, 3.5, 'trunk', rd=3.4, dd=-3))
    put(d, 'tail', 5, stroke([38, 58, 45, 59, 50, 55], 4.8, 'trunk', w2=1.6, d1=3, d2=9))
    heads = (('headM', 32, 13.5, -2.5, 8.8), ('headL', 18.5, 24.5, -1.8, 8.0), ('headR', 45.5, 24.5, -1.8, 8.0))
    for g, x, y, cd, r in heads:
        put(d, g, cd, e(x, y, r, r * 1.03, 'head', rd=r * 0.95))
        put(d, 'stalk' + g[-1], -0.8, cap(32 + (x - 32) * 0.25, 30, x, y + 4.5, 3.6, 4.0, 'trunk', d1=0, d2=-1))
    fronds = [
        ((29, 10), (17, 1), (3, 9), 9.0), ((35, 10), (47, 0), (61, 9), 9.0),
        ((25, 19), (10, 12), (1, 24), 8.0), ((39, 19), (54, 11), (63, 24), 8.0),
        ((32, 8), (32, 0), (35, -1), 7.0),
    ]
    for i, (a, b, c, w) in enumerate(fronds):
        put(d, 'frond%d' % i, 3.0 if i < 4 else 5.0,
            stroke([a[0], a[1], b[0], b[1], c[0], c[1]], w, 'leaf', w2=1.6, d2=2))
    paint(d,
          eye(15.6, 23.4, 2.4, iris='#603010'), eye(21.6, 23.4, 2.4, iris='#603010'), mouth(18.6, 29.2, 1.7, 'open'),
          eye(42.4, 23.4, 2.4, style='sad', iris='#603010', flip=True), eye(48.4, 23.4, 2.4, style='sad', iris='#603010'),
          mouth(45.4, 29.8, 1.9, 'frown'),
          eye(28.6, 12.6, 2.0, style='happy'), eye(35.6, 12.6, 2.0, style='happy'), mouth(32.1, 18.2, 2.4, 'smile'))


# ============================================================================ #106 - #110
@fix('HITMONLEE')
def hitmonlee(d, look):
    pal = {'sk': '#b5825a', 'skd': '#8d6238', 'cr': '#eedcb0', 'crd': '#c8a86c', 'yel': '#f0c848', 'dark': '#241a1a',
           'claw': '#f4ecd0'}
    new(d, pal)
    put(d, 'body', 0, e(32, 24.5, 11.4, 13.8, 'sk', rd=9.6), e(32, 36.5, 8.4, 5.6, 'sk', rd=7.2))
    paint(d, spot('body', 26.6, 20.4, 3.9, 2.4, 'dark', rot=20, frontOnly=True),
          spot('body', 37.4, 20.4, 3.9, 2.4, 'dark', rot=-20, frontOnly=True),
          eye(26.8, 20.6, 1.7, style='angry', flip=True, iris='#e8b830'), eye(37.2, 20.6, 1.7, style='angry', iris='#e8b830'),
          band('body', [26, 31, 32, 33, 38, 31], 1.0, 'skd', frontOnly=True),
          band('body', [27, 35.5, 32, 37.5, 37, 35.5], 1.0, 'skd', frontOnly=True))
    for s, sx in (('L', -1), ('R', 1)):
        ax, ay = 32 + sx * 10.2, 25.5
        put(d, 'arm' + s, -0.5, cap(ax, ay, ax + sx * 5.0, ay + 12, 2.7, 2.3, 'cr', d1=-0.5, d2=-3))
        paint(d, band('arm' + s, [ax + sx * 1.4 - 3, ay + 4, ax + sx * 1.4 + 3, ay + 4], 0.9, 'crd'),
              band('arm' + s, [ax + sx * 3.2 - 2.8, ay + 8, ax + sx * 3.2 + 2.8, ay + 8], 0.9, 'crd'))
        hx, hy = ax + sx * 5.8, ay + 14
        put(d, 'hand' + s, -1.6, e(hx, hy, 3.0, 2.8, 'cr', rd=2.8, dd=-3),
            cap(hx - 1.6, hy + 1.4, hx - 2.0, hy + 5.2, 1.2, 0.8, 'cr', dd=-3), cap(hx, hy + 1.6, hx, hy + 5.6, 1.25, 0.8, 'cr', dd=-3.4),
            cap(hx + 1.6, hy + 1.4, hx + 2.0, hy + 5.2, 1.2, 0.8, 'cr', dd=-3))
        x = 32 + sx * 5.4
        put(d, 'leg' + s, 0, cap(x, 38, x + sx * 1.4, 48.5, 4.0, 3.4, 'cr'), cap(x + sx * 1.4, 48.5, x + sx * 0.6, 57.5, 3.4, 2.8, 'cr'))
        paint(d, band('leg' + s, [x + sx * 0.6 - 4.4, 42.5, x + sx * 0.6 + 4.4, 42.5], 1.0, 'crd'),
              band('leg' + s, [x + sx * 1.2 - 4.4, 46.5, x + sx * 1.2 + 4.4, 46.5], 1.0, 'crd'),
              band('leg' + s, [x + sx * 1.4 - 4.4, 50.5, x + sx * 1.4 + 4.4, 50.5], 1.0, 'crd'),
              band('leg' + s, [x + sx * 1.1 - 3.8, 54, x + sx * 1.1 + 3.8, 54], 1.0, 'crd'),
              spot('leg' + s, x + sx * 0.7, 56.3, 1.6, 1.6, 'yel', frontOnly=True))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.7, 59.3, 5.4, 2.8, 'cr', dd=-1.6))
        toes(d, 'foot' + s, -1.0, x + sx * 0.7, 60.6, 3, 3.4, 1.25, 'claw', dd=-5.8)


@fix('HITMONCHAN')
def hitmonchan(d, look):
    pal = {'sk': '#c99a6e', 'skd': '#a07448', 'shorts': '#8f78bc', 'shortsd': '#6a5494', 'glove': '#e23a34',
           'cuff': '#f4f0e8', 'dark': '#2a2020', 'crest': '#b98a5e', 'pad': '#b98a5e'}
    new(d, pal)
    put(d, 'body', 0, e(32, 28.5, 9.4, 9.8, 'sk', rd=7.2), e(32, 39, 7.8, 5.2, 'sk', rd=6.2))
    paint(d, band('body', [26, 26, 32, 28, 38, 26], 1.0, 'skd', frontOnly=True),
          band('body', [27, 31, 32, 33, 37, 31], 0.9, 'skd', frontOnly=True))
    put(d, 'shorts', -0.8, e(32, 43.5, 9.0, 5.6, 'shorts', rd=7.2),
        plate([23, 44, 41, 44, 42.5, 52, 38, 50, 35, 53, 32, 50.5, 29, 53, 26, 50, 21.5, 52], 'shorts', T=6.4))
    paint(d, band('shorts', [26, 46, 25.5, 51], 0.8, 'shortsd'), band('shorts', [32, 46, 32, 51], 0.8, 'shortsd'),
          band('shorts', [38, 46, 38.5, 51], 0.8, 'shortsd'))
    crown = []
    for i in (-2, -1, 0, 1, 2):
        crown.append(cap(32 + i * 3.7, 9.0 + abs(i) * 1.0, 32 + i * 4.3, 3.4 + abs(i) * 1.7, 2.1, 1.3, 'crest', d1=0.5, d2=0.5))
    put(d, 'head', -1.2, e(32, 15, 8.8, 8.6, 'sk', rd=7.8), e(32, 19.6, 4.0, 2.6, 'sk', rd=3.4, dd=-4.8), *crown)
    paint(d, eye(28.3, 14.6, 2.1, style='angry', sclera=False, flip=True), eye(35.7, 14.6, 2.1, style='angry', sclera=False),
          band('head', [25.6, 11.4, 30.2, 12.8], 1.0, 'dark', frontOnly=True), band('head', [38.4, 11.4, 33.8, 12.8], 1.0, 'dark', frontOnly=True),
          mouth(32, 21.2, 2.3, 'line'))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'pad' + s, -0.6, e(32 + sx * 10.2, 22.6, 4.6, 3.6, 'pad', rd=4.2, dd=-0.5))
        put(d, 'arm' + s, -0.5, cap(32 + sx * 8.8, 24, 32 + sx * 13, 30.5, 3.0, 2.8, 'sk', d1=-1, d2=-3.5))
        put(d, 'glove' + s, -2.0, e(32 + sx * 14, 33, 5.2, 5.0, 'glove', rd=4.9, dd=-5.0),
            e(32 + sx * 12.8, 28.2, 3.3, 1.7, 'cuff', rd=3.0, dd=-3.6, rot=-sx * 20))
        x = 32 + sx * 5.6
        put(d, 'leg' + s, 0, cap(x, 46, x + sx * 0.6, 57.6, 4.0, 3.3, 'sk'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.7, 59.0, 5.6, 3.0, 'shorts', dd=-1.8),
            e(x + sx * 0.7, 57.2, 4.0, 1.8, 'shortsd', rd=3.6, dd=-0.5))


@fix('LICKITUNG')
def lickitung(d, look):
    pal = {'pk': '#f0a0b0', 'pkd': '#d8788c', 'cr': '#f8e0c0', 'tongue': '#e8607c', 'dark': '#2a2030'}
    new(d, pal)
    put(d, 'body', 0, e(32, 45, 13.5, 12.5, 'pk', rd=10.5), e(32, 53, 14.5, 7.5, 'pk', rd=11))
    paint(d, spot('body', 32, 47, 9.6, 9.6, 'cr', frontOnly=True),
          band('body', [25.5, 44, 28, 42, 30.5, 44, 33, 42, 35.5, 44, 38, 42, 40.5, 44], 0.9, 'pkd', frontOnly=True),
          band('body', [26, 50, 28.5, 48, 31, 50, 33.5, 48, 36, 50, 38.5, 48, 41, 50], 0.9, 'pkd', frontOnly=True))
    put(d, 'head', -1.8, e(32, 23.5, 11.6, 10.4, 'pk', rd=10.2), e(32, 29.4, 8.2, 4.6, 'pk', rd=5.8, dd=-5.4),
        cap(32, 15, 33.5, 7.8, 3.0, 0.7, 'pk', d1=0, d2=0))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ear' + s, -1.4, e(32 + sx * 11, 19.5, 2.4, 3.0, 'pk', rd=1.8, rot=sx * 20))
        put(d, 'arm' + s, -0.5, cap(32 + sx * 12, 38, 32 + sx * 18.5, 46, 3.4, 3.0, 'pk', d1=-1, d2=-3))
        put(d, 'hand' + s, -1.5, e(32 + sx * 19.2, 47.5, 3.4, 3.2, 'pk', rd=3.2, dd=-3))
        x = 32 + sx * 8
        put(d, 'leg' + s, 0.3, cap(x, 54, x + sx * 0.4, 58, 4.8, 4.4, 'pk'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.6, 59.2, 6.0, 2.7, 'pk', dd=-2.0))
        toes(d, 'foot' + s, -1.0, x + sx * 0.6, 60.5, 3, 3.5, 1.1, 'cr', dd=-6.0)
    put(d, 'tongue', -6.5, stroke([32, 31.4, 33.5, 38, 36, 46, 33, 52, 38, 56.5], 5.4, 'tongue', w2=3.2, d1=-2, d2=-4))
    put(d, 'tail', 4, stroke([40, 57, 47, 58, 51, 53, 52, 48], 3.0, 'pk', w2=1.8, d1=3, d2=9))
    paint(d, eye(25.6, 21.4, 2.2, iris='#402828'), eye(38.4, 21.4, 2.2, iris='#402828'),
          spot('head', 32, 29.6, 6.2, 2.4, 'dark', frontOnly=True), spot('head', 32, 30.5, 3.6, 1.4, 'tongue', frontOnly=True),
          spot('head', 32, 19.6, 0.6, 0.6, 'pkd', frontOnly=True))


def _bone_mon(d, look, mar):
    pal = {'br': '#b47c44' if not mar else '#a06c38', 'brd': '#8a5a30', 'cr': '#f0d8a4', 'sk': '#f2ead8',
           'skd': '#c8b898', 'sock': '#4a3a34', 'bone': '#f4ecd8', 'claw': '#f8f0e0'}
    new(d, pal)
    if not mar:
        bh, bw, hy, hs, legtop = 10.5, 9.6, 30.5, 1.0, 53
        put(d, 'body', 0, e(32, 46, bw, bh, 'br', rd=8.4), e(32, 53.5, 9, 6.6, 'br', rd=8.4))
        paint(d, spot('body', 32, 47.5, 6.2, 7.5, 'cr', frontOnly=True))
    else:
        bh, bw, hy, hs, legtop = 12.5, 11.4, 22.5, 0.9, 45
        put(d, 'body', 0, e(32, 37.5, bw, bh, 'br', rd=9.2), e(32, 46, 10.6, 7.6, 'br', rd=8.8))
        paint(d, spot('body', 32, 38.5, 7.2, 9.0, 'cr', frontOnly=True))
        paint(d, band('body', [25.5, 34, 29, 35.4, 32, 35.6, 35, 35.4, 38.5, 34], 0.8, 'brd', frontOnly=True))
    fr = 8.6 * hs                  # face half-width
    put(d, 'head', -2.5,
        e(32, hy, fr + 0.6, 7.8 * hs, 'br', rd=8.2 * hs), e(32, hy + 5 * hs, 5.0 * hs, 3.4 * hs, 'br', rd=4.4 * hs, dd=-4.6 * hs),
        e(32, hy - 4.4 * hs, 10.4 * hs, 9.6 * hs, 'sk', rd=9.0 * hs, dd=-1.0),
        e(32, hy + 0.2 * hs, 6.6 * hs, 2.4 * hs, 'sk', rd=6.0 * hs, dd=-3.4 * hs))
    ex, ey = 3.9 * hs, hy - 3.4 * hs
    paint(d, spot('head', 32 - ex, ey, 3.5 * hs, 3.9 * hs, 'sock', frontOnly=True),
          spot('head', 32 + ex, ey, 3.5 * hs, 3.9 * hs, 'sock', frontOnly=True),
          spot('head', 32, hy + 4.6 * hs, 1.5, 1.1, 'sock', frontOnly=True),
          eye(32 - ex, ey, 2.1 * hs + 0.1, sclera=False), eye(32 + ex, ey, 2.1 * hs + 0.1, sclera=False),
          mouth(32, hy + 7.8 * hs, 2.2, 'frown' if not mar else 'line'))
    for s, sx in (('L', -1), ('R', 1)):
        hx = 32 + sx * 6.2 * hs
        put(d, 'horn' + s, -1.5, cap(hx, hy - 11 * hs, hx + sx * (3.6 if not mar else 5.0), hy - (20.5 if not mar else 21.5) * hs,
                                     3.0, 0.7, 'sk', d1=1, d2=1))
    top = 41.5 if not mar else 31.5
    put(d, 'armR', -1.0, cap(32 + bw - 0.6, top, 32 + bw + 5.5, top + 8.5, 3.2 if not mar else 3.9, 2.8 if not mar else 3.3, 'br', d1=-1, d2=-2))
    put(d, 'handR', -2.5, e(32 + bw + 6.1, top + 10.0, 3.3, 3.1, 'br', rd=3.1))
    ax = 32 - bw
    hyb = top + 6.6
    if not mar:
        put(d, 'armL', -1.0, cap(ax + 0.6, top, 17.5, top + 7, 3.1, 2.7, 'br', d1=-1, d2=-3))
        top_b = 28
        put(d, 'handL', -3.5, e(17, hyb + 0.4, 3.4, 3.2, 'br', rd=3.2),
            cap(11.5, 60, 20.5, top_b, 1.8, 1.8, 'bone'),
            e(10.2, 59.6, 2.7, 2.7, 'bone', rd=2.7), e(13.8, 61.0, 2.7, 2.7, 'bone', rd=2.7),
            e(19.3, top_b - 1.5, 2.7, 2.7, 'bone', rd=2.7), e(22.6, top_b + 0.5, 2.7, 2.7, 'bone', rd=2.7))
    else:
        put(d, 'armL', -1.0, cap(ax + 0.6, top, 15.5, top + 4, 3.9, 3.3, 'br', d1=-1, d2=-3))
        top_b = 5
        put(d, 'handL', -3.5, e(14.5, top + 5, 3.7, 3.5, 'br', rd=3.4),
            cap(9.0, 58, 17.5, top_b, 2.0, 2.0, 'bone'),
            e(7.6, 58.2, 3.0, 3.0, 'bone', rd=3.0), e(11.4, 60.2, 3.0, 3.0, 'bone', rd=3.0),
            e(16.2, top_b - 1.8, 3.0, 3.0, 'bone', rd=3.0), e(19.8, top_b + 0.8, 3.0, 3.0, 'bone', rd=3.0))
    for s, sx in (('L', -1), ('R', 1)):
        x = 32 + sx * (6.2 if not mar else 7.0)
        put(d, 'leg' + s, 0.5, cap(x, legtop, x + sx * 0.3, 58, 4.4 if not mar else 4.8, 3.8 if not mar else 4.0, 'br'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.4, 59.2, 5.6, 2.5, 'br', dd=-1.8))
        toes(d, 'foot' + s, -1.0, x + sx * 0.4, 60.6, 3, 3.1, 1.0, 'claw', dd=-5.2)
    if not mar:
        put(d, 'tail', 3.5, stroke([38, 55, 44.5, 58, 51, 54.5], 5.0, 'br', w2=1.4, d1=2, d2=8))
    else:
        put(d, 'tail', 3.5, stroke([39, 51, 47, 57, 55, 55, 58.5, 48], 5.2, 'br', w2=1.2, d1=2, d2=9))


@fix('CUBONE')
def cubone(d, look):
    _bone_mon(d, look, False)


@fix('MAROWAK')
def marowak(d, look):
    _bone_mon(d, look, True)


def _craters(d, pts, main, rim, hole, cd=-2.0, r=4.4):
    """Little smoking volcano-like craters on a gas ball: pts = [(x, y, outward_dx, outward_dy)]."""
    for i, (x, y, ox, oy) in enumerate(pts):
        n = math.hypot(ox, oy) or 1.0
        ox, oy = ox / n, oy / n
        tx, ty = x + ox * 3.6, y + oy * 3.6
        put(d, 'crater%d' % i, cd, cap(x - ox * 2.0, y - oy * 2.0, tx, ty, r, r * 0.86, main),
            e(tx, ty, r * 0.9, r * 0.9, rim, rd=1.4, dd=-0.5 + (0 if oy > -0.4 else -0.6), solid=True))
        paint(d, spot('crater%d' % i, tx, ty, r * 0.62, r * 0.62, hole))


def _skull(d, g, x, y, s, bone, dark):
    paint(d, band(g, [x - 5.6 * s, y + 4.6 * s, x + 5.6 * s, y + 8.2 * s], 1.9 * s, bone, frontOnly=True),
          band(g, [x + 5.6 * s, y + 4.6 * s, x - 5.6 * s, y + 8.2 * s], 1.9 * s, bone, frontOnly=True),
          spot(g, x, y, 4.8 * s, 4.2 * s, bone, frontOnly=True),
          spot(g, x - 1.8 * s, y - 0.4 * s, 1.15 * s, 1.35 * s, dark, frontOnly=True),
          spot(g, x + 1.8 * s, y - 0.4 * s, 1.15 * s, 1.35 * s, dark, frontOnly=True),
          spot(g, x, y + 2.0 * s, 0.6 * s, 0.9 * s, dark, frontOnly=True))


@fix('KOFFING')
def koffing(d, look):
    pal = {'pu': '#9a7ec6', 'pud': '#7c5eac', 'rim': '#c0a8e0', 'hole': '#2e1c4c', 'bone': '#f6f0dc', 'dark': '#2a2036'}
    new(d, pal)
    put(d, 'body', 0, e(32, 35, 21.5, 21.5, 'pu', rd=21, solid=True))
    _craters(d, [(16.5, 19.5, -1, -1), (46.5, 15.5, 0.55, -1), (56, 40, 1, -0.1), (12, 46, -1, 0.5)], 'pud', 'rim', 'hole')
    _skull(d, 'body', 31, 44.6, 1.2, 'bone', 'dark')
    paint(d, eye(24.2, 29.5, 4.4, style='angry', flip=True, iris='#4a3a7c'), eye(39.4, 28.6, 3.6, style='angry', iris='#4a3a7c'),
          mouth(31.5, 35.6, 5.4, 'fang'))


@fix('WEEZING')
def weezing(d, look):
    pal = {'pu': '#9a7ec6', 'pud': '#7c5eac', 'rim': '#c0a8e0', 'hole': '#2e1c4c', 'bone': '#f6f0dc', 'dark': '#2a2036'}
    new(d, pal)
    put(d, 'body', 0, e(23.5, 30, 17.5, 17.5, 'pu', rd=16.5, solid=True))
    put(d, 'headB', -2.5, e(46, 46, 12.5, 12.5, 'pu', rd=12, solid=True))
    put(d, 'link', -1.0, cap(31, 36, 40, 42, 7.0, 6.4, 'pu'))
    _craters(d, [(9, 14, -1, -1), (28, 10.5, 0.2, -1), (5, 36, -1, 0.3), (57, 38, 1, -0.5), (58, 54, 1, 0.5), (40, 58, 0.2, 1)],
             'pud', 'rim', 'hole')
    _skull(d, 'body', 24, 40.4, 1.05, 'bone', 'dark')
    paint(d, eye(17.5, 25.6, 3.9, style='angry', flip=True, iris='#4a3a7c'), eye(29.5, 25, 3.2, style='angry', iris='#4a3a7c'),
          mouth(23.5, 32.2, 4.4, 'fang'),
          eye(41.5, 43.4, 3.0, style='angry', flip=True, iris='#4a3a7c'), eye(51, 43.2, 2.6, style='angry', iris='#4a3a7c'),
          mouth(46.3, 50.5, 3.4, 'fang'))


@fix('RHYHORN')
def rhyhorn(d, look):
    pal = {'gr': '#a6a8bc', 'grd': '#7c7e96', 'bel': '#d8d2bc', 'horn': '#efe8d4', 'hornd': '#c8bfa4', 'dark': '#2a2830'}
    new(d, pal)
    put(d, 'body', 0, e(32, 37.5, 14.6, 12.6, 'gr', rd=20, dd=10), e(32, 39.5, 13.8, 11.8, 'gr', rd=11, dd=26))
    paint(d, spot('body', 32, 49, 7.5, 4.0, 'bel', frontOnly=True))
    for i, dz in enumerate((3, 10, 17, 24, 30)):
        put(d, 'spike%d' % i, 0.5, cap(32, 27.4, 32, 19.5 - (i in (1, 2)) * 1.5, 4.0, 0.9, 'grd', d1=dz, d2=dz + 1.2),
            cap(24.5, 29.2, 22.5, 22.4, 2.8, 0.7, 'grd', d1=dz + 1.5, d2=dz + 2), cap(39.5, 29.2, 41.5, 22.4, 2.8, 0.7, 'grd', d1=dz + 1.5, d2=dz + 2))
    put(d, 'head', -12, e(32, 40.5, 11.0, 10.0, 'gr', rd=10.4), e(32, 44.6, 7.6, 5.4, 'gr', rd=6.0, dd=-6.2),
        cap(32, 42.4, 32, 31.5, 4.4, 0.8, 'horn', d1=-10, d2=-22), e(19.6, 33.5, 2.8, 3.4, 'gr', rd=2.0, rot=-20), e(44.4, 33.5, 2.8, 3.4, 'gr', rd=2.0, rot=20))
    paint(d, eye(25.8, 37.6, 2.0, style='angry', flip=True), eye(38.2, 37.6, 2.0, style='angry'),
          spot('head', 29.8, 45.4, 0.8, 0.6, 'dark', frontOnly=True), spot('head', 34.2, 45.4, 0.8, 0.6, 'dark', frontOnly=True),
          band('head', [27, 48.4, 32, 49.6, 37, 48.4], 0.9, 'dark', frontOnly=True))
    for nm, x, dz in (('legFL', 21.5, -5), ('legFR', 42.5, -5), ('legBL', 21, 24), ('legBR', 43, 24)):
        put(d, nm, dz * 0.1, cap(x, 44, x, 57.8, 6.2, 5.4, 'gr', dd=dz),
            e(x - 2.8, 59.3, 2.0, 1.5, 'horn', rd=1.8, dd=dz - 4.6), e(x, 59.5, 2.0, 1.5, 'horn', rd=1.8, dd=dz - 5.0),
            e(x + 2.8, 59.3, 2.0, 1.5, 'horn', rd=1.8, dd=dz - 4.6))
    put(d, 'tail', 6, stroke([32, 41, 32, 46, 32, 51, 32, 55], 4.2, 'gr', w2=1.6, d1=34, d2=43))


@fix('RHYDON')
def rhydon(d, look):
    pal = {'gr': '#a6a8b8', 'grd': '#7c7e94', 'bel': '#e2dcc4', 'beld': '#b8b096', 'horn': '#efe8d4', 'hornd': '#c8bfa4',
           'dark': '#2a2830', 'claw': '#f2ecd8'}
    new(d, pal)
    put(d, 'body', 0, e(32, 38, 14.6, 15, 'gr', rd=12), e(32, 49.5, 13.4, 8.6, 'gr', rd=11.2))
    paint(d, spot('body', 32, 40, 9.2, 12.4, 'bel', frontOnly=True),
          *[band('body', [24, 31 + 3.6 * k, 32, 32.4 + 3.6 * k, 40, 31 + 3.6 * k], 0.9, 'beld', frontOnly=True) for k in range(5)])
    put(d, 'head', -2.2, e(32, 19.5, 10.2, 9.2, 'gr', rd=9.4), e(32, 24, 7.0, 5.2, 'gr', rd=6.0, dd=-6.0),
        cap(32, 23.6, 32, 8.5, 4.0, 0.9, 'horn', d1=-9, d2=-16))
    paint(d, eye(26.2, 17.4, 2.0, style='angry', flip=True), eye(37.8, 17.4, 2.0, style='angry'),
          spot('head', 30, 24.6, 0.8, 0.6, 'dark', frontOnly=True), spot('head', 34, 24.6, 0.8, 0.6, 'dark', frontOnly=True),
          band('head', [28, 28.4, 32, 29.4, 36, 28.4], 0.9, 'dark', frontOnly=True))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'frill' + s, -0.5, cap(32 + sx * 8.6, 15.5, 32 + sx * 13, 8, 3.0, 0.7, 'gr', d1=2, d2=2),
            cap(32 + sx * 10, 19, 32 + sx * 15.6, 14, 2.6, 0.6, 'gr', d1=2, d2=2))
        put(d, 'arm' + s, -0.8, cap(32 + sx * 13, 30, 32 + sx * 17.5, 42, 4.6, 4.0, 'gr', d1=-1, d2=-4))
        put(d, 'hand' + s, -1.6, e(32 + sx * 18.2, 44, 4.0, 3.8, 'gr', rd=3.8, dd=-4))
        claw_tips(d, 'hand' + s, -1.6, 32 + sx * 18.2, 46.5, 3, 2.3, 2.4, 0.8, 'claw', dd=-4, dirx=sx * 0.2)
        x = 32 + sx * 7.8
        put(d, 'leg' + s, 0.4, cap(x, 50, x + sx * 1.4, 57.6, 5.6, 4.9, 'gr'))
        put(d, 'foot' + s, -1.0, e(x + sx * 1.6, 59.2, 6.4, 2.9, 'gr', dd=-2.0))
        claw_tips(d, 'foot' + s, -1.0, x + sx * 1.6, 60.2, 3, 3.6, 1.6, 1.0, 'claw', dd=-7.0, diry=0.4)
    for i, (y, sz) in enumerate(((23, 3.4), (30, 4.0), (38, 4.4), (46, 4.0))):
        put(d, 'spike%d' % i, 7, cap(32, y, 32, y - 6.4 - sz * 0.6, sz, 0.8, 'grd', d1=0, d2=6))
    put(d, 'tail', 8, stroke([32, 52, 36, 57, 31, 59.5], 9.5, 'gr', w2=2.2, d1=6, d2=26))


@fix('CHANSEY')
def chansey(d, look):
    pal = {'pk': '#f8b4c4', 'pkd': '#e88ca4', 'cr': '#fbeed8', 'crd': '#e8d2b0', 'egg': '#fffdf8', 'dark': '#2a2030'}
    new(d, pal)
    put(d, 'body', 0, e(32, 41, 17.5, 16.5, 'pk', rd=13.5), e(32, 27, 12.6, 11.2, 'pk', rd=10.8))
    paint(d, spot('body', 32, 48.6, 10.6, 8.6, 'cr', frontOnly=True), band('body', [22.6, 50, 26, 53, 32, 54.8, 38, 53, 41.4, 50], 0.9, 'crd', frontOnly=True))
    put(d, 'egg', -13.5, e(32, 45.6, 5.4, 6.6, 'egg', rd=4.8))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'tuft' + s, -1.0, cap(32 + sx * 11, 23, 32 + sx * 18.6, 16.5, 3.4, 0.9, 'pk', d1=1.5, d2=1.5),
            cap(32 + sx * 11.4, 29, 32 + sx * 19.6, 31, 3.2, 0.9, 'pk', d1=1.5, d2=1.5))
        put(d, 'arm' + s, -1.0, cap(32 + sx * 15, 40, 32 + sx * 19.5, 48, 3.4, 3.0, 'pk', d1=-1, d2=-3))
        put(d, 'hand' + s, -2.0, e(32 + sx * 20.2, 49.6, 3.3, 3.1, 'pk', rd=3.0, dd=-3))
        x = 32 + sx * 9.2
        put(d, 'leg' + s, 0.4, cap(x, 54, x + sx * 0.5, 58.2, 5.2, 4.8, 'pk'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.8, 59.3, 6.4, 2.7, 'pk', dd=-2.4))
    put(d, 'tail', 6, stroke([39, 55, 46, 57, 49, 53], 5.0, 'pk', w2=2.0, d1=5, d2=12))
    put(d, 'curl', -1.4, e(32, 15.6, 3.0, 3.4, 'pk', rd=2.6, dd=-3))
    paint(d, eye(26.8, 26.2, 2.3, sclera=False), eye(37.2, 26.2, 2.3, sclera=False), mouth(32, 31.6, 2.0, 'smile'),
          spot('body', 24.6, 30.6, 2.3, 1.5, 'pkd', frontOnly=True), spot('body', 39.4, 30.6, 2.3, 1.5, 'pkd', frontOnly=True))


@fix('TANGELA')
def tangela(d, look):
    pal = {'bl': '#3c62b8', 'bld': '#284694', 'bll': '#6a92dc', 'red': '#e05858', 'dark': '#14142a'}
    new(d, pal)
    c = (32, 31.5)
    put(d, 'body', 0, e(c[0], c[1], 15.0, 15.0, 'bl', rd=14.0))
    A = [[(-85, 12), (-75, 36), (-50, 56), (-15, 66), (25, 60), (58, 42), (82, 16)],
         [(-88, -12), (-78, -36), (-52, -52), (-22, -62), (14, -60), (46, -48), (78, -30)],
         [(-62, 66), (-60, 34), (-66, 0), (-58, -36), (-46, -62)],
         [(62, 66), (66, 34), (60, 2), (64, -34), (50, -60)],
         [(-28, 72), (-8, 48), (-38, 38), (-56, 14)],
         [(30, 72), (18, 46), (48, 32), (58, 8)],
         [(-46, -30), (-24, -56), (4, -42), (24, -62)],
         [(38, -28), (56, -46), (34, -56)],
         [(100, 20), (140, 46), (180, 54), (220, 44), (262, 22)],
         [(104, -22), (146, -46), (190, -52), (232, -42), (258, -14)],
         [(150, 66), (158, 30), (150, -10), (160, -50)],
         [(210, 66), (206, 28), (214, -14), (204, -50)]]
    ps_a, ps_b = [], []
    for i, r in enumerate(A):
        (ps_a if i % 2 == 0 else ps_b).extend(_rope(r, c, 16.6, 5.0, 'bll' if i % 3 else 'bld', w2=4.6, step=14.0))
    put(d, 'coilA', 0, *ps_a)
    put(d, 'coilB', 0, *ps_b)
    tend = [
        [(19, 20), (11, 14), (7, 6), (12, 2)], [(46, 17), (53, 11), (52, 4)], [(15.5, 34), (7, 33.5), (3, 39)],
        [(49, 36), (58, 34), (60, 27)], [(22, 45), (16, 51), (9, 50)], [(41, 46), (48, 52), (55, 50)],
        [(29, 16), (28, 8), (34, 2.5)],
    ]
    for i, pts in enumerate(tend):
        flat = [q for p in pts for q in p]
        put(d, 'vine%d' % i, -1.0 - i % 2, stroke(flat, 4.6, 'bl' if i % 2 else 'bld', w2=1.8, d1=-8, d2=-8 - (i % 3) * 2))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'foot' + s, 1.0, e(32 + sx * 7.2, 57.6, 5.6, 3.2, 'red', rd=4.4, dd=-1))
    paint(d, spot('body', 32, 32.6, 10.6, 5.0, 'dark', frontOnly=True),
          eye(27.2, 32.4, 3.0, iris='#2a2a48'), eye(36.8, 32.4, 3.0, iris='#2a2a48'))


@fix('KANGASKHAN')
def kangaskhan(d, look):
    pal = {'br': '#b48a58', 'brd': '#8a6238', 'cr': '#ecdcb4', 'crd': '#c8b088', 'plate': '#2e2630', 'baby': '#c8a4dc',
           'babyd': '#a880c0', 'claw': '#f4ecd8', 'dark': '#2a2030', 'red': '#d03838'}
    new(d, pal)
    put(d, 'body', 0, e(32, 39.5, 14.4, 17, 'br', rd=12), e(32, 51, 13, 8, 'br', rd=11.4))
    paint(d, spot('body', 32, 43.5, 9.6, 12.6, 'cr', frontOnly=True))
    paint(d, spot('body', 32, 48.5, 9.4, 7.4, 'crd', frontOnly=True), band('body', [23.4, 47, 26, 53, 32, 55.4, 38, 53, 40.6, 47], 1.0, 'brd', frontOnly=True))
    put(d, 'baby', -11.6, e(32, 43.2, 6.4, 5.8, 'baby', rd=5.4), e(26.4, 38.4, 2.3, 3.2, 'baby', rd=1.5, rot=-22), e(37.6, 38.4, 2.3, 3.2, 'baby', rd=1.5, rot=22))
    paint(d, eye(29.4, 42.6, 1.5, sclera=False), eye(34.6, 42.6, 1.5, sclera=False), mouth(32, 46, 1.4, 'smile'))
    put(d, 'head', -2.2, e(32, 15.6, 10.2, 9.2, 'br', rd=9.2), e(32, 20.2, 6.0, 4.6, 'br', rd=5.4, dd=-6.0),
        e(32, 7.6, 7.8, 2.6, 'plate', rd=6.6, dd=0.5))
    paint(d, eye(27.2, 15.6, 1.6, iris='#c82828', wide=1.5), eye(36.8, 15.6, 1.6, iris='#c82828', wide=1.5),
          spot('head', 30.6, 21.4, 0.7, 0.55, 'dark', frontOnly=True), spot('head', 33.4, 21.4, 0.7, 0.55, 'dark', frontOnly=True),
          mouth(32, 23.4, 2.2, 'smile'))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ear' + s, -1.6, e(32 + sx * 9.8, 10.2, 3.4, 6.0, 'cr', rd=2.0, rot=sx * 22))
        put(d, 'epaulet' + s, -0.8, e(32 + sx * 13, 26.6, 4.4, 3.6, 'plate', rd=3.6, dd=0.5))
        put(d, 'arm' + s, -0.8, cap(32 + sx * 13, 29, 32 + sx * 16.5, 41, 3.8, 3.2, 'br', d1=-1, d2=-4))
        put(d, 'hand' + s, -1.6, e(32 + sx * 17.2, 42.6, 3.4, 3.2, 'br', rd=3.2, dd=-4))
        claw_tips(d, 'hand' + s, -1.6, 32 + sx * 17.2, 44.6, 3, 2.1, 2.4, 0.75, 'claw', dd=-4)
        x = 32 + sx * 8.2
        put(d, 'leg' + s, 0.4, cap(x, 52, x + sx * 0.6, 57.8, 6.0, 5.2, 'br'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.8, 59.2, 6.8, 2.9, 'br', dd=-2.4))
        claw_tips(d, 'foot' + s, -1.0, x + sx * 0.8, 60.2, 3, 3.6, 1.6, 1.0, 'claw', dd=-8.0, diry=0.4)
    for i, (y, sz) in enumerate(((26, 2.8), (32, 3.2), (38, 3.4), (44, 3.2))):
        put(d, 'spike%d' % i, 7, cap(32, y, 32, y - 5.4, sz, 0.7, 'plate', d1=0, d2=4))
    put(d, 'tail', 8, stroke([34, 51, 38, 57, 34, 60], 12.5, 'br', w2=3.0, d1=6, d2=28))


@fix('HORSEA')
def horsea(d, look):
    _seahorse(d, False)


def star_pts(cx, cy, ro, ri, rot=0.0, n=5):
    pts = []
    for i in range(2 * n):
        a = math.radians(rot - 90 + i * 180.0 / n)
        r = ro if i % 2 == 0 else ri
        pts += [round(cx + r * math.cos(a), 3), round(cy + r * math.sin(a), 3)]
    return pts


@fix('STARYU')
def staryu(d, look):
    pal = {'st': '#d9a55a', 'std': '#b4803c', 'gold': '#f2c94a', 'red': '#e63a4c', 'shine': '#ffe6e6'}
    new(d, pal)
    put(d, 'body', 0, plate(star_pts(32, 34.5, 27, 11.2), 'st', T=4.6))
    put(d, 'ring', -3.5, e(32, 34.5, 9.6, 9.6, 'gold', rd=4.2))
    put(d, 'core', -6.5, e(32, 34.5, 6.4, 6.4, 'red', rd=5.6), solid=True) if False else \
        put(d, 'core', -6.5, e(32, 34.5, 6.4, 6.4, 'red', rd=5.6, solid=True))
    paint(d, spot('core', 30.2, 32.6, 1.5, 1.3, 'shine', frontOnly=True))


@fix('STARMIE')
def starmie(d, look):
    pal = {'st': '#a084cc', 'std': '#7e62aa', 'gold': '#f2c94a', 'red': '#e63a4c', 'shine': '#ffe6e6'}
    new(d, pal)
    put(d, 'body', 0, plate(star_pts(32, 34.5, 28, 11.6, 36), 'std', T=4.2))
    put(d, 'front', -4.2, plate(star_pts(32, 34.5, 27, 11.4, 0), 'st', T=4.4))
    put(d, 'ring', -8.6, e(32, 34.5, 10.6, 10.6, 'gold', rd=4.4))
    put(d, 'core', -11.6, e(32, 34.5, 7.4, 7.4, 'red', rd=6.4, solid=True))
    paint(d, spot('core', 29.8, 32.2, 1.7, 1.5, 'shine', frontOnly=True))


def _fish_eyes(d, x, y, r, cdx, white='eye', dark='dark', pr=None):
    pr = pr or r * 0.56
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'eye' + s, cdx * sx, e(x, y, r, r * 1.05, white, rd=r * 0.9, solid=True))
        put(d, 'pupil' + s, cdx * sx + sx * r * 0.42, e(x - 0.5, y + 0.2, pr, pr * 1.08, dark, rd=pr * 0.9, solid=True))


@fix('GOLDEEN')
def goldeen(d, look):
    pal = {'wh': '#f8f4ec', 'whd': '#e2d8c8', 'or': '#f27c3a', 'ord': '#d05c24', 'fin': '#fdf0e4', 'eye': '#ffffff',
           'dark': '#20203a', 'lip': '#f0a0b0'}
    new(d, pal)
    put(d, 'body', 0, e(31, 33.5, 17.5, 11.6, 'wh', rd=8.6), e(19, 33.5, 8.4, 8.6, 'wh', rd=7.4))
    paint(d, spot('body', 33, 25, 11, 4.8, 'or'), spot('body', 26, 26.5, 5, 3, 'or'), spot('body', 46, 33, 4, 5, 'or'))
    put(d, 'horn', 0.5, cap(17, 26.5, 12.5, 12, 3.2, 0.7, 'wh'), cap(17, 26.5, 13.4, 17.4, 3.2, 3.0, 'or'))
    _fish_eyes(d, 16.8, 31, 3.0, 5.8)
    put(d, 'lips', -2.5, e(10.6, 35.6, 2.6, 2.2, 'lip', rd=2.2, dd=-0.5))
    put(d, 'tail', 0.5, smooth_plate([44, 33, 49, 24, 55, 15, 62, 9, 61, 18, 64, 27, 60, 34, 64, 42, 61, 51, 55, 56, 52, 48, 47, 40], 'fin', T=1.2),
        stroke([45, 34, 52, 24, 60, 14], 2.0, 'or'), stroke([46, 37, 55, 41, 62, 40], 1.8, 'or'), stroke([45, 40, 50, 48, 54, 54], 1.8, 'or'))
    put(d, 'dorsal', 0.5, smooth_plate([26, 25, 29, 16, 34, 8, 41, 4, 43, 12, 40, 20, 38, 25], 'fin', T=1.0), stroke([32, 22, 36, 9], 1.6, 'or'))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'pect' + s, sx * 7.0, smooth_plate([26, 36, 22, 41, 17, 48, 22, 51, 28, 48, 33, 42], 'fin', T=0.9))
    put(d, 'pelv', 0.3, smooth_plate([31, 43, 33, 50, 39, 56, 42, 50, 39, 44], 'fin', T=0.9))


@fix('SEAKING')
def seaking(d, look):
    pal = {'wh': '#f8f4ec', 'or': '#f26a30', 'ord': '#c8461c', 'fin': '#fde6d6', 'eye': '#ffffff', 'dark': '#20203a',
           'lip': '#f0a0b0', 'spot': '#3c2e4c', 'horn': '#f6f0e4'}
    new(d, pal)
    put(d, 'body', 0, e(31, 32, 19, 13.2, 'or', rd=9.6), e(18.5, 33, 8.6, 9.4, 'or', rd=8.2))
    paint(d, spot('body', 32, 41.5, 17.5, 6.4, 'wh', frontOnly=True), spot('body', 22, 41, 7, 5, 'wh', frontOnly=True),
          spot('body', 30, 27, 2.0, 2.0, 'spot'), spot('body', 38, 30, 2.4, 2.4, 'spot'), spot('body', 26, 33, 1.7, 1.7, 'spot'))
    put(d, 'horn', 0.5, cap(17, 25, 11, 6.5, 3.6, 0.8, 'horn'))
    _fish_eyes(d, 16, 31, 3.3, 6.4, pr=1.9)
    put(d, 'lips', -2.5, e(10.2, 36.2, 3.0, 2.6, 'lip', rd=2.4, dd=-0.5))
    put(d, 'tail', 0.5, smooth_plate([47, 32, 52, 22, 57, 13, 64, 6, 62, 17, 65, 27, 62, 35, 65, 44, 62, 53, 56, 58, 53, 49, 49, 40], 'fin', T=1.3),
        stroke([48, 33, 56, 20, 62, 10], 2.2, 'or'), stroke([48, 37, 57, 41, 63, 38], 2.0, 'or'), stroke([48, 41, 53, 50, 56, 56], 2.0, 'or'))
    put(d, 'dorsal', 0.5, smooth_plate([25, 21, 28, 12, 32, 4, 40, 1, 44, 8, 43, 15, 41, 20], 'fin', T=1.1), stroke([30, 19, 34, 5], 1.8, 'or'), stroke([36, 19, 40, 4], 1.8, 'or'))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'pect' + s, sx * 8.0, smooth_plate([26, 37, 22, 43, 17, 51, 23, 54, 30, 50, 35, 43], 'fin', T=1.0))
    put(d, 'pelv', 0.3, smooth_plate([30, 44, 32, 52, 39, 58, 44, 52, 40, 45], 'fin', T=1.0))


def _seahorse(d, big):
    if big:
        pal = {'bl': '#4a92d2', 'bld': '#3670b0', 'cr': '#f0e6b8', 'crd': '#c8b880', 'fin': '#f6ecc4', 'fin2': '#e0d094', 'eye': '#fbfbfb',
               'dark': '#20203a', 'red': '#c83040', 'pupil': '#d8384c'}
    else:
        pal = {'bl': '#5aa4e2', 'bld': '#3e84c8', 'cr': '#f0e6b8', 'crd': '#c8b880', 'fin': '#f4eed6', 'fin2': '#e0d094', 'eye': '#fbfbfb',
               'dark': '#20203a', 'red': '#c83040', 'pupil': '#20203a'}
    new(d, pal)
    k = 1.25 if big else 1.0
    body_pts = [38, 27, 41, 33, 41.5, 40, 39, 47, 40.5, 53, 46, 57.5, 51, 54, 49, 49]
    put(d, 'body', 0, stroke(body_pts, 13 * k, 'bl', w2=3.2, d1=-1, d2=1.5))
    paint(d, *[band('body', [33 + 0.3 * j, 30 + 4.6 * j, 45 - 0.3 * j, 30 + 4.6 * j], 1.0, 'crd', frontOnly=True) for j in range(0, 4)])
    put(d, 'belly', -4.4 * k, stroke([36.5, 29, 37.5, 36, 36.5, 43, 37.6, 50], 8.5 * k, 'cr', w2=5.0), z=0.2)
    paint(d, *[band('belly', [32.4 + 0.2 * j, 31 + 4.6 * j, 41.5 - 0.2 * j, 31 + 4.6 * j], 0.9, 'crd', frontOnly=True) for j in range(0, 4)])
    hr = 9.4 * k
    hy = 20.0
    hrd = hr * 0.94
    put(d, 'head', -3, e(35, hy, hr, hr * 0.94, 'bl', rd=hrd),
        cap(33.5, 23, 30.5, 26.0 if big else 25.2, 3.5, 3.0, 'bl', d1=-6, d2=-16 if big else -15),
        e(30.2, 26.2 if big else 25.4, 3.3, 2.7, 'cr', rd=2.6, dd=-16.4 if big else -15.4))
    paint(d, spot('head', 30.2, 26.2 if big else 25.4, 1.4, 1.0, 'dark', frontOnly=True))
    er = 3.0 * k
    for s, sx in (('L', -1), ('R', 1)):
        off, ey = 5.6 * k, hy - 1.6
        surf = hrd * math.sqrt(max(0.05, 1 - (off / hr) ** 2 - (1.6 / (hr * 0.94)) ** 2))
        ecd = -3 - surf + er * 0.55
        put(d, 'eye' + s, ecd, e(35 + sx * off, ey, er, er * 1.04, 'eye', rd=er * 0.92))
        put(d, 'pupil' + s, ecd - er * 0.5, e(35 + sx * (off + er * 0.42), ey + 0.2, er * 0.6, er * 0.66, 'pupil', rd=er * 0.5))
    n = 5 if big else 4
    for i in range(n):
        y = 14 + i * (23.0 / n) * 1.0
        x = 41.5 + (0 if i else 1)
        L = (10 if big else 8) - i * 0.4
        put(d, 'dfin%d' % i, 2.5, cap(x, y, x + L, y - (6.5 if i == 0 else 2.5), 3.4 if big else 3.0, 0.7, 'fin', d1=1, d2=1),
            cap(x, y + 2, x + L - 1, y + (2.5 if big else 2.0), 2.6, 0.6, 'fin2', d1=1, d2=1))
    put(d, 'finL', -3, smooth_plate([40, 35, 45, 33, 49, 37, 46, 42, 41, 40], 'fin', T=0.8))
    put(d, 'finR', 4.5, smooth_plate([40, 35, 45, 33, 49, 37, 46, 42, 41, 40], 'fin', T=0.8))
    if big:
        for i, (x, y, tx, ty) in enumerate(((28, 13, 22, 4), (27.5, 17, 20, 11), (28.5, 22, 20, 21))):
            put(d, 'cfin%d' % i, 1.0, cap(x, y, tx, ty, 3.0, 0.7, 'fin2', d1=4, d2=5))


@fix('SEADRA')
def seadra(d, look):
    _seahorse(d, True)


@fix('MR_MIME')
def mr_mime(d, look):
    pal = {'skin': '#fbdcd0', 'wh': '#f8f4f2', 'whd': '#e0d8dc', 'pk': '#ee6478', 'bl': '#4a7cd0', 'bld': '#3660b0', 'dark': '#20203a',
           'eye': '#ffffff'}
    new(d, pal)
    put(d, 'body', 0, e(32, 34, 9.6, 11.6, 'wh', rd=7.8), e(32, 43.5, 8.2, 5.0, 'wh', rd=6.4))
    paint(d, spot('body', 32, 37.5, 4.2, 4.4, 'pk', frontOnly=True), spot('body', 23.8, 27.6, 3.1, 3.1, 'pk'), spot('body', 40.2, 27.6, 3.1, 3.1, 'pk'))
    put(d, 'head', -1.6, e(32, 15.5, 10.4, 9.6, 'skin', rd=9.0))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ear' + s, -1.0, cap(32 + sx * 6.8, 8.6, 32 + sx * 12.2, 0.8, 4.6, 1.2, 'bl', d1=0.5, d2=0.5),
            e(32 + sx * 8, 8.2, 4.2, 3.6, 'bl', rd=3.2))
        put(d, 'arm' + s, -0.5, cap(32 + sx * 9.4, 28, 32 + sx * 15.5, 38.5, 3.0, 2.6, 'wh', d1=-1, d2=-3))
        put(d, 'hand' + s, -1.4, e(32 + sx * 16.4, 40.6, 3.8, 3.7, 'wh', rd=3.4, dd=-3),
            cap(32 + sx * 15, 42.8, 32 + sx * 14.4, 46.8, 1.3, 0.9, 'wh', dd=-3), cap(32 + sx * 16.8, 43.4, 32 + sx * 17.2, 47.4, 1.3, 0.9, 'wh', dd=-3),
            cap(32 + sx * 18.6, 42.6, 32 + sx * 20.4, 45.6, 1.2, 0.9, 'wh', dd=-3))
        x = 32 + sx * 4.6
        put(d, 'leg' + s, 0.2, cap(x, 46, x + sx * 0.8, 57, 2.9, 2.6, 'wh'))
        paint(d, spot('leg' + s, x + sx * 0.4, 51.5, 2.5, 2.5, 'pk'))
        put(d, 'foot' + s, -1.0, e(x + sx * 1.6, 59, 5.4, 2.7, 'bl', dd=-2.2), cap(x + sx * 5, 58.5, x + sx * 8.6, 55.6, 1.9, 1.1, 'bl', dd=-2.2))
    paint(d, spot('head', 25.2, 19.6, 2.6, 2.6, 'pk', frontOnly=True), spot('head', 38.8, 19.6, 2.6, 2.6, 'pk', frontOnly=True),
          eye(28, 14.2, 3.1, iris='#2a2a48'), eye(36, 14.2, 3.1, iris='#2a2a48'), mouth(32, 22.2, 2.6, 'smile'))


@fix('SCYTHER')
def scyther(d, look):
    pal = {'gr': '#86c058', 'grd': '#5c9038', 'bel': '#eef0c8', 'blade': '#e8eeee', 'blade2': '#a8bac4', 'wing': '#dcecee',
           'wing2': '#b4ccd4', 'dark': '#20203a'}
    new(d, pal)
    put(d, 'body', 0, e(32, 32, 7.8, 10, 'gr', rd=6.4), e(32, 42, 6.0, 4.8, 'gr', rd=5.2),
        cap(32, 40, 32, 47, 4.8, 2.6, 'gr', d1=2, d2=14))
    paint(d, spot('body', 32, 32.5, 4.6, 8.0, 'bel', frontOnly=True),
          *[band('body', [28.2, 27.6 + 3.3 * j, 35.8, 27.6 + 3.3 * j], 0.8, 'grd', frontOnly=True) for j in range(4)])
    put(d, 'neck', -0.4, cap(32, 18.5, 32, 24.5, 3.0, 3.6, 'gr'))
    put(d, 'head', -1.6, e(32, 13, 8.2, 7.4, 'gr', rd=7.0), e(32, 17.6, 4.4, 3.0, 'gr', rd=3.8, dd=-4.6),
        cap(32, 8.6, 32, -1.0, 4.2, 0.8, 'gr', d1=-1.5, d2=-3))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'cheek' + s, -1.2, cap(32 + sx * 6.6, 15, 32 + sx * 10.4, 21.4, 2.1, 0.9, 'gr', dd=-2))
    paint(d, eye(27.8, 12.6, 2.8, style='angry', flip=True, iris='#c8283c'), eye(36.2, 12.6, 2.8, style='angry', iris='#c8283c'),
          mouth(32, 20.0, 1.8, 'line'))
    blade = [10.6, 30, 15.8, 32.6, 20.2, 40, 21.6, 50, 18.6, 58, 15.6, 61.5, 15.6, 52, 15.2, 44, 12.8, 37, 9.8, 33]
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'arm' + s, -0.5, cap(32 + sx * 7.2, 25.5, 32 + sx * 11.6, 33, 2.8, 2.4, 'gr', d1=-1, d2=-3))
        pts = curve(blade, 3)
        pts = [(32 + sx * v) if i % 2 == 0 else v for i, v in enumerate(pts)]
        put(d, 'blade' + s, -3.2, plate(pts, 'blade', T=1.7),
            stroke([32 + sx * 12.3, 35, 32 + sx * 13.8, 43, 32 + sx * 14, 52], 1.3, 'blade2'))
        put(d, 'wing' + s, 4.5, plate([32 + sx * 6, 24, 32 + sx * 24, 6, 32 + sx * 30, 14, 32 + sx * 25, 28, 32 + sx * 9, 33], 'wing', T=0.9),
            plate([32 + sx * 7, 33, 32 + sx * 22, 30, 32 + sx * 27, 41, 32 + sx * 12, 40], 'wing2', T=0.8, dd=0.5))
        x = 32 + sx * 5
        put(d, 'leg' + s, 0, cap(x, 42, x + sx * 2.2, 50, 2.9, 2.5, 'gr'), cap(x + sx * 2.2, 50, x + sx * 0.8, 58.4, 2.5, 2.0, 'gr'))
        put(d, 'foot' + s, -0.8, e(x + sx * 0.9, 59.4, 3.8, 1.8, 'gr', dd=-2), toes_claw(x + sx * 0.9, 60.4, 'gr'))


def toes_claw(x, y, c):
    return cap(x, y - 0.4, x, y + 1.0, 1.1, 0.6, c, dd=-5)


@fix('JYNX')
def jynx(d, look):
    pal = {'hair': '#f6da50', 'haird': '#d6a828', 'face': '#4a2c70', 'lip': '#f0508c', 'lipd': '#c83070',
           'dress': '#dc3c3c', 'dressd': '#a82828', 'skin': '#7050a8', 'bel': '#f6d8d8', 'dark': '#20203a'}
    new(d, pal)
    put(d, 'body', 0, e(32, 42, 10.2, 12.6, 'dress', rd=8.2), e(32, 52.5, 13.8, 6.8, 'dress', rd=10.4))
    paint(d, band('body', [26, 46, 25.4, 58], 1.0, 'dressd', frontOnly=True), band('body', [32, 46, 32, 59], 1.0, 'dressd', frontOnly=True),
          band('body', [38, 46, 38.6, 58], 1.0, 'dressd', frontOnly=True), spot('body', 32, 31.4, 6.4, 2.4, 'bel', frontOnly=True))
    put(d, 'hairBk', 3.6, e(32, 30, 10.2, 24, 'hair', rd=5.4), e(32, 12.5, 12.0, 9.6, 'hair', rd=8.6, dd=-0.6))
    put(d, 'head', -1.6, e(32, 21, 9.4, 9.0, 'face', rd=8.4))
    put(d, 'lips', -7.6, e(32, 26.2, 6.2, 3.2, 'lip', rd=3.4), e(32, 24.6, 4.8, 1.6, 'lipd', rd=2.8, dd=-0.5))
    put(d, 'bangs', -6.6, e(32, 13.6, 11.0, 5.0, 'hair', rd=6.4), cap(24.4, 13, 25.6, 19.4, 2.4, 1.1, 'hair', dd=-1),
        cap(39.6, 13, 38.4, 19.4, 2.4, 1.1, 'hair', dd=-1), cap(32, 14, 32, 17.4, 2.8, 1.2, 'hair', dd=-1))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'lock' + s, -0.4, cap(32 + sx * 10.6, 17, 32 + sx * 11.4, 47, 3.1, 2.4, 'hair', d1=-2, d2=-2))
        put(d, 'arm' + s, -2.2, cap(32 + sx * 10.4, 33, 32 + sx * 15, 45.5, 2.9, 2.4, 'skin', d1=-1, d2=-4))
        put(d, 'hand' + s, -3.0, e(32 + sx * 15.8, 47.4, 2.8, 2.8, 'skin', rd=2.6, dd=-4), cap(32 + sx * 15, 49, 32 + sx * 14.6, 52.2, 1.2, 0.8, 'skin', dd=-4),
            cap(32 + sx * 17, 49, 32 + sx * 17.8, 52.2, 1.2, 0.8, 'skin', dd=-4))
        put(d, 'foot' + s, -1.0, e(32 + sx * 6, 59.4, 5.2, 2.4, 'skin', dd=-4))
    paint(d, eye(28, 20.2, 2.5, style='sleepy', iris='#38a070'), eye(36, 20.2, 2.5, style='sleepy', iris='#38a070'),
          band('head', [24.6, 18, 29.6, 18.6], 0.8, 'dark', frontOnly=True), band('head', [39.4, 18, 34.4, 18.6], 0.8, 'dark', frontOnly=True))


def _sph(c, R, lon, lat):
    la, lo = math.radians(lat), math.radians(lon)
    return c[0] + R * math.cos(la) * math.sin(lo), c[1] - R * math.sin(la), -R * math.cos(la) * math.cos(lo)


def _rope(pts, c, R, w, col, w2=None, step=22.0):
    """A rope hugging a sphere: strokes between points interpolated on lon/lat, depth following the sphere."""
    out = []
    for (lo0, la0), (lo1, la1) in zip(pts, pts[1:]):
        n = max(1, int(max(abs(lo1 - lo0), abs(la1 - la0)) / step + 0.999))
        for k in range(n):
            a = _sph(c, R, lo0 + (lo1 - lo0) * k / n, la0 + (la1 - la0) * k / n)
            b = _sph(c, R, lo0 + (lo1 - lo0) * (k + 1) / n, la0 + (la1 - la0) * (k + 1) / n)
            out.append(stroke([a[0], a[1], b[0], b[1]], w, col, w2=w2, d1=a[2], d2=b[2]))
    return out


@fix('ELECTABUZZ')
def electabuzz(d, look):
    pal = {'yl': '#f8d43c', 'yld': '#d8a820', 'blk': '#26202c', 'wh': '#ffffff', 'dark': '#26202c', 'bel': '#fbe88a'}
    new(d, pal)
    put(d, 'body', 0, e(32, 32, 11.8, 12.6, 'yl', rd=9.4), e(32, 44, 9.4, 6.0, 'yl', rd=7.6))
    paint(d, band('body', [22.5, 25.5, 27.5, 28.5, 24.5, 31.5, 30.5, 33.8, 27.5, 36.5, 34, 38.5], 2.0, 'blk', frontOnly=True),
          band('body', [41.5, 25.5, 36.5, 28.5, 39.5, 31.5, 33.5, 33.8], 2.0, 'blk', frontOnly=True),
          band('body', [26, 41.5, 32, 44, 38, 41.5], 1.6, 'blk'))
    put(d, 'head', -1.4, e(32, 13, 9.0, 8.2, 'yl', rd=8.2), e(32, 18.2, 5.2, 3.6, 'yl', rd=4.2, dd=-5.6))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'horn' + s, -1.0, stroke([32 + sx * 4.4, 7.4, 32 + sx * 6.6, 1.6, 32 + sx * 5.4, -3.4], 3.2, 'yl', w2=2.0, d1=0, d2=0),
            stroke([32 + sx * 5.5, -1.0, 32 + sx * 5.2, -4.2], 2.3, 'blk', d1=0, d2=0))
        put(d, 'arm' + s, -0.6, cap(32 + sx * 10.4, 24, 32 + sx * 15.4, 36.5, 4.6, 3.8, 'yl', d1=-1, d2=-4))
        paint(d, band('arm' + s, [32 + sx * 12.6 - 4, 30, 32 + sx * 12.6 + 4, 30], 1.6, 'blk'),
              band('arm' + s, [32 + sx * 14 - 4, 34, 32 + sx * 14 + 4, 34], 1.6, 'blk'))
        put(d, 'hand' + s, -1.8, e(32 + sx * 16.2, 39.2, 3.9, 3.7, 'yl', rd=3.6, dd=-4))
        x = 32 + sx * 6.4
        put(d, 'leg' + s, 0.2, cap(x, 44, x + sx * 0.6, 57.6, 5.4, 4.4, 'yl'))
        paint(d, band('leg' + s, [x - 5, 48, x + 5, 48], 1.5, 'blk'), band('leg' + s, [x - 4.6, 53.6, x + 4.6, 53.6], 1.3, 'blk'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.7, 59.2, 5.8, 2.8, 'yl', dd=-2.0))
        toes(d, 'foot' + s, -1.0, x + sx * 0.7, 60.5, 3, 3.4, 1.1, 'yl', dd=-6.2)
    put(d, 'tail', 4, stroke([37, 49, 43, 55, 50, 53, 55, 46], 3.8, 'yl', w2=2.0, d1=4, d2=16),
        stroke([53, 50, 55.2, 46], 2.4, 'blk', d1=15, d2=16))
    paint(d, eye(27.6, 12.4, 2.8, style='angry', flip=True), eye(36.4, 12.4, 2.8, style='angry'),
          band('head', [27, 6.6, 29.5, 8.4, 32, 6.6, 34.5, 8.4, 37, 6.6], 1.2, 'blk', frontOnly=True),
          mouth(32, 20.6, 2.6, 'fang'))


@fix('MAGMAR')
def magmar(d, look):
    pal = {'or': '#f6a232', 'orl': '#f8c058', 'red': '#e6481c', 'yel': '#f9dc78', 'bill': '#f4cc50', 'dark': '#3a2820'}
    new(d, pal)
    put(d, 'body', 0, e(32, 33.5, 11.8, 12.6, 'or', rd=9.8), e(32, 45, 10.0, 6.6, 'or', rd=8.4))
    paint(d, spot('body', 32, 36.5, 7.6, 9.4, 'yel', frontOnly=True),
          band('body', [26, 31, 29, 33, 32, 31, 35, 33, 38, 31], 1.2, 'red', frontOnly=True),
          band('body', [26, 37, 29, 39, 32, 37, 35, 39, 38, 37], 1.2, 'red', frontOnly=True),
          band('body', [27, 43, 30, 44.6, 32, 43, 34, 44.6, 37, 43], 1.2, 'red', frontOnly=True))
    put(d, 'head', -1.4, e(32, 15, 8.8, 8.2, 'or', rd=8.2), e(32, 19.6, 5.8, 3.2, 'bill', rd=4.2, dd=-6.4), e(32, 18.2, 4.6, 1.6, 'bill', rd=3.4, dd=-6.8))
    for i, (x, ty, tx) in enumerate(((25.2, 3, 21.4), (28.6, 0, 26.6), (32, -3.4, 32), (35.4, 0, 37.4), (38.8, 3, 42.6))):
        put(d, 'flame%d' % i, -0.8, cap(x, 9.4, tx, ty, 3.0, 0.7, 'red', d1=0, d2=0), cap(x, 9.0, x + (tx - x) * 0.5, ty + 4.8, 1.6, 0.5, 'yel', d1=-1, d2=-1))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'arm' + s, -0.6, cap(32 + sx * 10.6, 24.5, 32 + sx * 15.6, 36, 4.4, 3.6, 'red', d1=-1, d2=-4))
        put(d, 'hand' + s, -1.8, e(32 + sx * 16.4, 38.6, 3.9, 3.7, 'or', rd=3.6, dd=-4))
        put(d, 'spark' + s, 2.0, cap(32 + sx * 13, 30, 32 + sx * 21, 24, 3.2, 0.7, 'red', d1=2, d2=3), cap(32 + sx * 13, 32, 32 + sx * 20, 30, 2.6, 0.6, 'red', d1=2, d2=3))
        x = 32 + sx * 6.4
        put(d, 'leg' + s, 0.2, cap(x, 45, x + sx * 0.6, 57.6, 5.4, 4.6, 'or'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.7, 59.2, 5.8, 2.8, 'or', dd=-2.0))
        toes(d, 'foot' + s, -1.0, x + sx * 0.7, 60.5, 3, 3.4, 1.1, 'yel', dd=-6.2)
    put(d, 'tail', 4, stroke([37, 50, 43, 56, 50, 54, 54, 47], 5.4, 'or', w2=3.0, d1=4, d2=15))
    put(d, 'tailflame', 6, cap(54, 47.4, 57.4, 36, 4.8, 0.9, 'red', d1=15, d2=16), cap(54, 46.8, 55.6, 40.4, 2.6, 0.6, 'yel', d1=14, d2=14),
        cap(53, 47.6, 49, 40, 3.4, 0.8, 'red', d1=15, d2=16))
    paint(d, eye(28.2, 13.8, 2.4, style='angry', flip=True, iris='#d02820'), eye(35.8, 13.8, 2.4, style='angry', iris='#d02820'),
          spot('head', 30.4, 19.8, 0.5, 0.5, 'dark', frontOnly=True), spot('head', 33.6, 19.8, 0.5, 0.5, 'dark', frontOnly=True))


@fix('PINSIR')
def pinsir(d, look):
    pal = {'br': '#a87848', 'brd': '#7c5430', 'tan': '#dcc8a0', 'tand': '#b09868', 'horn': '#ece4d4', 'hornd': '#c0b498',
           'dark': '#2a2020'}
    new(d, pal)
    put(d, 'body', 0, e(32, 33, 10.8, 12.2, 'br', rd=8.8), e(32, 45, 8.0, 5.6, 'br', rd=6.8))
    paint(d, spot('body', 32, 35, 6.6, 9.8, 'tan', frontOnly=True),
          *[band('body', [26.4, 28 + 3.4 * j, 32, 29.2 + 3.4 * j, 37.6, 28 + 3.4 * j], 0.9, 'tand', frontOnly=True) for j in range(4)])
    put(d, 'head', -1.4, e(32, 15, 8.4, 7.8, 'br', rd=7.8), e(32, 19.6, 4.4, 3.0, 'br', rd=3.8, dd=-4.8))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'horn' + s, -1.0, stroke([32 + sx * 6.4, 12, 32 + sx * 13.2, 10.6, 32 + sx * 16, 4, 32 + sx * 12, -2.2], 6.6, 'horn', w2=1.1, d1=-1, d2=-3),
            cap(32 + sx * 14.8, 9.4, 32 + sx * 11.2, 9.0, 1.8, 0.4, 'horn', d1=-3, d2=-3), cap(32 + sx * 15.6, 5.6, 32 + sx * 12.0, 6.0, 1.7, 0.4, 'horn', d1=-3, d2=-3),
            cap(32 + sx * 13.8, 1.4, 32 + sx * 10.6, 2.6, 1.5, 0.4, 'horn', d1=-3, d2=-3), cap(32 + sx * 7.4, 13.4, 32 + sx * 10.4, 13.2, 2.2, 0.6, 'horn', d1=-2, d2=-2))
        put(d, 'shoulder' + s, -0.4, cap(32 + sx * 10, 25, 32 + sx * 18, 18.6, 4.6, 0.8, 'brd', d1=0, d2=0), cap(32 + sx * 10.6, 28, 32 + sx * 19.6, 26.4, 3.8, 0.8, 'brd', d1=0, d2=0))
        put(d, 'arm' + s, -0.6, cap(32 + sx * 9.8, 27.5, 32 + sx * 13.8, 40, 3.2, 2.6, 'br', d1=-1, d2=-4))
        put(d, 'hand' + s, -1.8, e(32 + sx * 14.4, 41.4, 3.0, 2.8, 'br', rd=2.8, dd=-4))
        claw_tips(d, 'hand' + s, -1.8, 32 + sx * 14.4, 43.0, 3, 1.9, 2.6, 0.7, 'horn', dd=-4)
        x = 32 + sx * 5.6
        put(d, 'leg' + s, 0.2, cap(x, 43, x + sx * 2.4, 50.4, 4.8, 3.8, 'br'), cap(x + sx * 2.4, 50.4, x + sx * 0.8, 58.2, 3.8, 3.0, 'br'),
            cap(x + sx * 4, 47.4, x + sx * 6.8, 44.4, 2.4, 0.6, 'brd', d1=-1, d2=-1))
        put(d, 'foot' + s, -1.0, e(x + sx * 1.0, 59.3, 5.0, 2.5, 'br', dd=-2.0))
        claw_tips(d, 'foot' + s, -1.0, x + sx * 1.0, 60.3, 2, 3.6, 2.2, 1.0, 'horn', dd=-6.4, diry=0.4)
    paint(d, eye(28.2, 14.2, 2.2, style='angry', flip=True, iris='#20182a'), eye(35.8, 14.2, 2.2, style='angry', iris='#20182a'),
          spot('head', 30.8, 20.2, 0.5, 0.5, 'dark', frontOnly=True), spot('head', 33.2, 20.2, 0.5, 0.5, 'dark', frontOnly=True), mouth(32, 22.4, 2.2, 'line'))


@fix('TAUROS')
def tauros(d, look):
    pal = {'br': '#c49858', 'brd': '#7c5a3a', 'tan': '#e6cba2', 'horn': '#f0e8d8', 'horn2': '#8c7c6c', 'hoof': '#463c4c', 'dark': '#2a2028'}
    new(d, pal)
    put(d, 'body', 0, e(32, 36.5, 14, 12.6, 'br', rd=20, dd=10), e(32, 38.5, 13.6, 12.0, 'br', rd=11.5, dd=26), e(32, 29.5, 12.4, 7.6, 'br', rd=11, dd=3))
    paint(d, spot('body', 32, 47.5, 7.5, 3.6, 'tan', frontOnly=True))
    put(d, 'mane', -7.5, e(32, 30, 13.4, 10.8, 'brd', rd=10.6))
    tufts = []
    for a in (200, 235, 270, 305, 340, 20, 160):
        ar = math.radians(a)
        tufts.append(cap(32 + 10 * math.cos(ar), 30 + 8.4 * math.sin(ar), 32 + 15.8 * math.cos(ar), 30 + 13.6 * math.sin(ar), 4.2, 0.8, 'brd', d1=0, d2=0))
    put(d, 'tufts', -7.5, *tufts)
    put(d, 'head', -13, e(32, 37.5, 9.8, 9.2, 'br', rd=9.6), e(32, 43.2, 6.8, 4.8, 'tan', rd=5.6, dd=-6.2),
        e(22.2, 32.4, 3.2, 2.0, 'br', rd=1.6, rot=-25), e(41.8, 32.4, 3.2, 2.0, 'br', rd=1.6, rot=25))
    paint(d, eye(26.8, 35.4, 2.3, style='angry', flip=True, iris='#3a2418'), eye(37.2, 35.4, 2.3, style='angry', iris='#3a2418'),
          spot('head', 29.6, 43.6, 0.9, 0.7, 'dark', frontOnly=True), spot('head', 34.4, 43.6, 0.9, 0.7, 'dark', frontOnly=True),
          mouth(32, 46.4, 2.4, 'line'))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'horn' + s, -13, stroke([32 + sx * 8, 33, 32 + sx * 15.4, 31.4, 32 + sx * 19.6, 24, 32 + sx * 16.4, 15.8], 6.4, 'horn', w2=1.2, d1=-1, d2=-2),
            stroke([32 + sx * 19.6, 24, 32 + sx * 16.4, 15.8], 3.0, 'horn2', w2=1.2, d1=-1.5, d2=-2))
    for nm, x, dz in (('legFL', 22.5, -5), ('legFR', 41.5, -5), ('legBL', 22, 24), ('legBR', 42, 24)):
        put(d, nm, dz * 0.1, cap(x, 44, x, 57.6, 5.6, 4.9, 'br', dd=dz), e(x, 59.5, 4.2, 2.4, 'hoof', rd=3.8, dd=dz - 0.8))
    for nm, (ex, ey) in (('tailA', (22, 17)), ('tailB', (32, 14)), ('tailC', (42, 17))):
        put(d, nm, 6, stroke([32, 32, 32 + (ex - 32) * 0.5, 22, ex, ey + 3], 3.0, 'br', w2=2.4, d1=36, d2=38),
            e(ex, ey, 3.6, 3.6, 'brd', rd=3.4, dd=38))


@fix('MAGIKARP')
def magikarp(d, look):
    pal = {'red': '#f0602c', 'redd': '#c8401c', 'cr': '#f8e2b4', 'crd': '#d8b880', 'eye': '#ffffff', 'dark': '#2a1a20', 'whisk': '#f6dc9c'}
    new(d, pal)
    put(d, 'body', 0, e(32, 36, 15.4, 12.2, 'red', rd=9.6), e(19.5, 38, 9.4, 9.6, 'red', rd=8.6))
    paint(d, spot('body', 32, 45.8, 13, 4.2, 'cr', frontOnly=False))
    sc = []
    for r, (y, xs) in enumerate(((30, (26, 32, 38, 44)), (35, (23, 29, 35, 41, 47)), (40, (26, 32, 38, 44)))):
        for x in xs:
            sc.append(band('body', [x - 2.4, y - 0.8, x, y + 1.8, x + 2.4, y - 0.8], 0.8, 'redd'))
    paint(d, *sc)
    put(d, 'lips', -3.5, e(9.2, 40.4, 4.2, 3.6, 'cr', rd=3.6, dd=-0.5), e(9.6, 43.4, 3.6, 2.2, 'cr', rd=2.6, dd=-0.5))
    paint(d, spot('lips', 8.2, 41.6, 1.7, 1.2, 'dark', frontOnly=True))
    _fish_eyes(d, 17, 34, 3.5, 6.4, pr=2.0)
    put(d, 'tail', 0.5, smooth_plate([46, 37, 51, 30, 57, 22, 63, 18, 62, 28, 64, 37, 60, 46, 56, 54, 51, 47], 'cr', T=1.3),
        stroke([47, 38, 55, 30, 62, 20], 1.4, 'crd'), stroke([47, 38, 57, 40, 63, 37], 1.3, 'crd'), stroke([47, 39, 53, 46, 57, 53], 1.3, 'crd'))
    put(d, 'dorsal', 0.5, plate([23, 26, 25, 17, 29, 23, 31, 13, 35, 22, 39, 15, 41, 26], 'cr', T=1.6))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'pect' + s, sx * 7.2, smooth_plate([26, 41, 22, 46, 20, 53, 26, 52, 31, 47], 'cr', T=0.9))
        put(d, 'whisk' + s, sx * 3.0, stroke([12.6, 37.6, 6, 33.4, 3.4, 26, 5, 20], 2.0, 'whisk', w2=0.9, d1=0, d2=sx * 4),
            stroke([12.4, 39.6, 5.4, 44.4, 4.6, 52], 1.8, 'whisk', w2=0.9, d1=0, d2=sx * 4))
    put(d, 'pelv', 0.3, smooth_plate([35, 46, 37, 53, 43, 55, 44, 49], 'cr', T=0.9))


@fix('GYARADOS')
def gyarados(d, look):
    pal = {'bl': '#3a86c6', 'bld': '#2a64a4', 'bll': '#68a8dc', 'cr': '#f0e4b4', 'crd': '#c8b880', 'fin': '#d4e4f0', 'fang': '#fbf6e8',
           'mouth': '#a02840', 'eye': '#ffffff', 'dark': '#20203a', 'wh': '#f4f4f4', 'crest': '#e8dca0'}
    new(d, pal)
    path = [30, 27, 27, 35, 27.5, 44, 32, 52.5, 41, 57, 49.5, 52.5, 53, 42, 52, 31, 55.5, 21]
    put(d, 'body', 0, stroke(path, 18, 'bl', w2=4.6))
    put(d, 'belly', -7.0, stroke([27.4, 30, 25.6, 36, 26, 44, 30.6, 52, 39, 57.6, 47, 53], 9.4, 'cr', w2=4.2), z=0.2)
    paint(d, *[band('belly', [x0, y0, x1, y1], 1.0, 'crd', frontOnly=True) for x0, y0, x1, y1 in
               ((19.5, 33, 31, 34.5), (19.4, 39, 31, 40), (21, 45, 32.6, 46), (25, 50.4, 35.6, 51.6), (32, 54.4, 41, 56))])
    put(d, 'head', -4, e(30, 13.5, 13.4, 10.8, 'bl', rd=11.6), e(30, 20.2, 10.4, 5.4, 'bl', rd=7.8, dd=-9.6),
        e(30, 28.4, 8.6, 4.0, 'cr', rd=5.6, dd=-6.4))
    paint(d, spot('head', 30, 25.0, 7.0, 3.0, 'mouth', frontOnly=True),
          eye(22.6, 12.0, 3.3, style='angry', flip=True, iris='#d02030'), eye(37.4, 12.0, 3.3, style='angry', iris='#d02030'),
          spot('head', 26.6, 19.0, 0.9, 0.7, 'dark', frontOnly=True), spot('head', 33.4, 19.0, 0.9, 0.7, 'dark', frontOnly=True))
    put(d, 'fangs', -15.5, cap(24.6, 22.8, 24.4, 30, 2.2, 0.4, 'fang'), cap(35.4, 22.8, 35.6, 30, 2.2, 0.4, 'fang'),
        cap(27.6, 28.6, 27.4, 24, 1.6, 0.4, 'fang', dd=-1.5), cap(32.4, 28.6, 32.6, 24, 1.6, 0.4, 'fang', dd=-1.5))
    for i, (x, tx, ty) in enumerate(((24, 19, -3), (30, 30, -7), (36, 41, -3))):
        put(d, 'crest%d' % i, -1.5, cap(x, 5.5, tx, ty, 4.4, 0.8, 'bld', d1=0, d2=0))
    for s, sx in (('L', -1), ('R', 1)):
        pts = curve([sx * 11, 12, sx * 17, 8, sx * 23, 10, sx * 22, 17, sx * 16, 21, sx * 12, 19], 3)
        pts = [(30 + v) if i % 2 == 0 else v for i, v in enumerate(pts)]
        put(d, 'gill' + s, 1.0, plate(pts, 'fin', T=1.4))
        put(d, 'whisk' + s, -7.0, stroke([30 + sx * 9.6, 25, 30 + sx * 14, 31, 30 + sx * 13.4, 40], 2.4, 'wh', w2=1.0, d1=-2, d2=-2))
    put(d, 'tailfin', 0.5, smooth_plate([55.5, 23, 51, 14, 49, 5, 55, 8, 60, 3, 61, 12, 60, 21, 58, 28], 'bll', T=1.4))
    put(d, 'sidefin', 1.5, smooth_plate([50, 46, 58, 48, 60, 56, 52, 55], 'fin', T=1.0), smooth_plate([26, 47, 19, 50, 18, 57, 25, 54], 'fin', T=1.0))


@fix('LAPRAS')
def lapras(d, look):
    pal = {'bl': '#58a4de', 'bld': '#3c80bc', 'cr': '#f0ead0', 'crd': '#c8c0a0', 'shl': '#9aa2bc', 'shld': '#7880a0', 'spike': '#ece6d0',
           'eye': '#ffffff', 'dark': '#20203a'}
    new(d, pal)
    put(d, 'body', 0, e(34, 46, 18.4, 10.6, 'bl', rd=13.4), e(50, 47, 8, 6, 'bl', rd=8.4))
    paint(d, spot('body', 30, 53, 13, 3.6, 'cr', frontOnly=True))
    put(d, 'shell', 4.0, e(38, 36, 15.8, 12.4, 'shl', rd=13.4, dd=2))
    for i, (x, y, tx, ty) in enumerate(((31, 27, 28, 20), (38, 25, 38, 17), (45, 27, 48, 20), (50, 33, 57, 29), (30, 34, 23, 32), (47, 41, 54, 43))):
        put(d, 'spike%d' % i, 3.0, cap(x, y, tx, ty, 3.6, 0.8, 'spike', d1=2, d2=2))
    paint(d, spot('shell', 36, 31, 3, 2.4, 'shld'), spot('shell', 44, 36, 3, 2.4, 'shld'), spot('shell', 32, 40, 3, 2.4, 'shld'))
    put(d, 'neck', -1.5, stroke([24, 42, 18.5, 31, 20.5, 21], 10.5, 'bl', w2=8.2, d1=-1, d2=-2))
    put(d, 'throat', -6.0, stroke([21.2, 39, 16.2, 31, 18.4, 22], 5.6, 'cr', w2=4.4, d1=-1, d2=-1), z=0.2)
    put(d, 'head', -3.5, e(21, 14.6, 9.0, 7.8, 'bl', rd=8.2), e(20.5, 20, 6.2, 3.6, 'bl', rd=5.0, dd=-6.0),
        cap(21, 8.4, 19.6, -1.4, 3.0, 0.6, 'spike'), e(30, 12.2, 2.2, 3.2, 'bl', rd=1.6, rot=20), e(12, 12.2, 2.2, 3.2, 'bl', rd=1.6, rot=-20))
    paint(d, eye(16.4, 14, 3.1, iris='#382860'), eye(25.6, 14, 3.1, iris='#382860'), mouth(20.8, 21.4, 2.6, 'smile'))
    put(d, 'flipperFL', -11.5, smooth_plate([20, 50, 13, 47.5, 6, 51, 3.5, 57, 10, 60, 18, 57], 'bl', T=2.0))
    put(d, 'flipperFR', 10.0, smooth_plate([24, 54, 18, 52, 12, 56, 12, 61, 20, 61], 'bl', T=1.8))
    put(d, 'flipperBL', -11.5, smooth_plate([44, 54, 52, 52.5, 58, 56.5, 56, 61, 47, 61], 'bl', T=2.0))
    put(d, 'flipperBR', 11.0, smooth_plate([52, 54, 58, 53, 62, 57, 58, 61, 51, 60], 'bl', T=1.8))
    put(d, 'tail', 6, stroke([54, 46, 60, 48, 63, 43], 7.0, 'bl', w2=2.4, d1=4, d2=6))


@fix('DITTO')
def ditto(d, look):
    pal = {'pu': '#b48ede', 'pud': '#9270c0', 'shine': '#e8d8f8', 'dark': '#3a2a54'}
    new(d, pal)
    put(d, 'body', 0, e(32, 51, 23.6, 9.2, 'pu', rd=17.4), e(21.5, 42.5, 10, 8, 'pu', rd=10), e(39, 41, 11.4, 9.4, 'pu', rd=11),
        e(30.5, 45, 12, 7, 'pu', rd=12))
    put(d, 'blobL', -2.0, e(8.5, 54, 5.6, 4.6, 'pu', rd=5.2), e(56, 53, 6, 4.8, 'pu', rd=5.4))
    paint(d, eye(25, 50.4, 2.1, sclera=False), eye(39, 50.4, 2.1, sclera=False), mouth(32, 55.6, 4.0, 'line'),
          spot('body', 30.5, 33.6, 1.2, 1.2, 'shine', frontOnly=True))


def _cones(g, cx, cy, ang0, ang1, n, r0, r1, base_r, c, ry=None, d1=0.0, d2=0.0, tip=0.7):
    """A fan of tapered cones radiating from (cx, cy) (fur / spines / ruff)."""
    ry = ry or r0
    out = []
    for i in range(n):
        a = math.radians(ang0 + (ang1 - ang0) * (i / max(n - 1, 1)))
        ca, sa = math.cos(a), math.sin(a)
        out.append(cap(cx + r0 * ca, cy + ry * sa * (r0 / r0), cx + r1 * ca, cy + (r1 / r0) * ry * sa, base_r, tip, c, d1=d1, d2=d2))
    return out


def _eeveelution(d, kind):
    K = {
        'eevee': dict(br='#c08850', cr='#f2dcb4', tip='#6a4224', ear='#c08850', eye='#503020'),
        'vaporeon': dict(br='#6cb0e4', cr='#f2f6fc', tip='#3a70b8', ear='#3e78bc', eye='#302858'),
        'jolteon': dict(br='#f8d838', cr='#f8f4e2', tip='#c8a820', ear='#f8d838', eye='#28202c'),
        'flareon': dict(br='#f07a2c', cr='#f8dfa2', tip='#d05a18', ear='#f07a2c', eye='#3a2020'),
    }[kind]
    pal = dict(br=K['br'], cr=K['cr'], tip=K['tip'], ear=K['ear'], dark='#2a2028', fin2='#3a70b8', fin3='#dceaf8')
    new(d, pal)
    slim = kind == 'jolteon'
    bw = 8.8 if slim else 10.4
    put(d, 'body', 0, e(32, 44.5, bw, 8.8 if slim else 9.2, 'br', rd=12.5, dd=10), e(32, 45.2, bw + 0.4, 9.0, 'br', rd=8.4, dd=20))
    paint(d, spot('body', 32, 51.5, 5.4, 2.6, 'cr', frontOnly=True) if kind == 'eevee' else spot('body', 32, 51, 4, 2, 'br'))
    # neck ruff
    if kind == 'jolteon':
        put(d, 'ruff', -6.5, e(32, 40.8, 9.4, 5.4, 'cr', rd=8), *_cones('r', 32, 40.5, 150, 30, 9, 8.4, 14.6, 3.2, 'cr'))
    elif kind == 'vaporeon':
        put(d, 'ruff', -6.5, e(32, 40.8, 9.6, 5.4, 'cr', rd=8), *_cones('r', 32, 40, 165, 15, 9, 8.6, 14.2, 3.4, 'cr'))
    elif kind == 'flareon':
        put(d, 'ruff', -6.5, e(32, 40.6, 11.2, 6.6, 'cr', rd=9), *_cones('r', 32, 40, 165, 15, 9, 10.4, 15.8, 4.2, 'cr'))
    else:
        put(d, 'ruff', -6.5, e(32, 40.8, 10.0, 5.6, 'cr', rd=8.4), *_cones('r', 32, 40, 160, 20, 9, 9.0, 14.0, 3.6, 'cr'))
    hr = 9.0 if kind != 'jolteon' else 8.6
    put(d, 'head', -8, e(32, 30.5, hr + 0.8, hr - 0.4, 'br', rd=hr), e(32, 35.4, 4.4, 3.0, 'br', rd=3.4, dd=-7))
    paint(d, spot('head', 32, 34.6, 1.0, 0.7, 'dark', frontOnly=True),
          eye(27.2, 29.6, 3.2, sclera=False), eye(36.8, 29.6, 3.2, sclera=False),
          band('head', [29.6, 38.6, 32, 39.6, 34.4, 38.6], 0.8, 'dark', frontOnly=True))
    if kind == 'jolteon':
        for s, sx in (('L', -1), ('R', 1)):
            put(d, 'cheek' + s, -7, cap(32 + sx * 8, 35, 32 + sx * 14.5, 38, 3.2, 0.7, 'br'), cap(32 + sx * 7, 38, 32 + sx * 12.5, 43, 2.8, 0.7, 'br'))
    for s, sx in (('L', -1), ('R', 1)):
        ex = 32 + sx * 8.4
        if kind == 'eevee':
            put(d, 'ear' + s, -6, e(32 + sx * 8.2, 19, 4.4, 9.8, 'ear', rd=2.6, rot=sx * 14))
            paint(d, spot('ear' + s, 32 + sx * 6.6, 20.4, 1.9, 6.0, 'cr', rot=sx * 14, frontOnly=True), spot('ear' + s, 32 + sx * 11.4, 10.4, 2.6, 2.6, 'tip'))
        elif kind == 'jolteon':
            put(d, 'ear' + s, -6, cap(ex - sx * 1.2, 25, 32 + sx * 12.6, 3.2, 4.8, 0.8, 'ear'))
        elif kind == 'flareon':
            put(d, 'ear' + s, -6, cap(ex - sx * 0.6, 24, 32 + sx * 11.4, 8.4, 5.0, 1.4, 'ear'))
            paint(d, spot('ear' + s, 32 + sx * 9.2, 17, 1.8, 4.6, 'cr', rot=sx * 22, frontOnly=True))
        else:   # vaporeon: big blue fin ears with a pale stripe
            pts = curve([sx * 5, 25, sx * 8, 17, sx * 11, 9, sx * 15, 2, sx * 19, 7, sx * 21, 14, sx * 18.5, 20, sx * 12, 26], 3)
            pts = [(32 + v) if i % 2 == 0 else v for i, v in enumerate(pts)]
            put(d, 'ear' + s, -6, plate(pts, 'ear', T=2.0))
            paint(d, band('ear' + s, [32 + sx * 9, 23, 32 + sx * 12.6, 14, 32 + sx * 15.6, 7], 1.8, 'fin3', frontOnly=True),
                  band('ear' + s, [32 + sx * 13.6, 22, 32 + sx * 16.6, 15, 32 + sx * 18.4, 10], 1.3, 'fin3', frontOnly=True))
    # legs
    thin = 2.7 if slim else 3.5
    for nm, x, cdl in (('legFL', 25.5, -4), ('legFR', 38.5, -4), ('legBL', 25, 15), ('legBR', 39, 15)):
        put(d, nm, cdl * 0.1, cap(x, 47.5, x, 57.4, thin + 0.4, thin, 'br', dd=cdl), e(x, 58.7, thin + 0.7, 1.9, 'br', rd=thin + 0.7, dd=cdl - 1.4))
    # tail
    if kind == 'eevee':
        put(d, 'tail', 8, stroke([32, 46, 35.5, 39, 34, 31], 8.5, 'br', w2=9.4, d1=21, d2=25), e(34, 29.6, 5.6, 6.4, 'cr', rd=5.2, dd=25.5))
    elif kind == 'flareon':
        put(d, 'tail', 8, stroke([32, 46, 35, 38, 34.5, 29], 10.5, 'br', w2=12.4, d1=21, d2=26), e(34.5, 26.4, 7.6, 8.2, 'cr', rd=7.0, dd=26.5),
            *_cones('t', 34.5, 28, 200, 340, 6, 7.0, 11.4, 3.6, 'cr', d1=26, d2=26))
    elif kind == 'jolteon':
        put(d, 'tail', 8, stroke([32, 46, 33, 40, 33, 34], 6.5, 'br', w2=5.2, d1=21, d2=25),
            *[cap(33, 36, 33 + dx, 36 - h, 4.2, 0.7, 'br', d1=25, d2=25) for dx, h in ((-6, 9), (-2, 12), (2, 12), (6, 9))])
    else:
        put(d, 'tail', 8, stroke([32, 46, 37, 39, 41, 30, 38, 22], 8.2, 'br', w2=4.4, d1=21, d2=27),
            smooth_plate([38, 24, 32, 16, 34, 7, 39, 12, 43, 5, 45, 14, 42, 24], 'fin2', T=1.4, dd=27), stroke([38.5, 22, 39, 10], 1.4, 'fin3', d1=27, d2=27))
    # back ridge
    if kind == 'jolteon':
        put(d, 'spikes', 2, *[cap(32 + sx, 35.5, 32 + sx * 1.6, 27 - (k % 2) * 2, 4.4, 0.8, 'br', d1=dz, d2=dz + 1.5)
                             for k, dz in enumerate((0, 6, 12, 18, 24)) for sx in (-4.0, 4.0)] +
            [cap(32, 34.4, 32, 24.4, 4.6, 0.8, 'br', d1=dz, d2=dz + 1.5) for dz in (3, 9, 15, 21)])
    elif kind == 'vaporeon':
        put(d, 'ridge', 2, *[cap(32, 35.6, 32, 28.6, 3.4, 0.7, 'fin3', d1=dz, d2=dz + 2.4) for dz in (2, 7, 12, 17, 22)])
    elif kind == 'flareon':
        put(d, 'crest', -8, *[cap(32 + dx, 22.6, 32 + dx * 1.3, 13.4 + abs(dx) * 0.5, 3.6, 0.8, 'cr') for dx in (-3.6, 0, 3.6)])


@fix('EEVEE')
def eevee(d, look):
    _eeveelution(d, 'eevee')


@fix('VAPOREON')
def vaporeon(d, look):
    _eeveelution(d, 'vaporeon')


@fix('JOLTEON')
def jolteon(d, look):
    _eeveelution(d, 'jolteon')


@fix('FLAREON')
def flareon(d, look):
    _eeveelution(d, 'flareon')


@fix('PORYGON')
def porygon(d, look):
    pal = {'pk': '#f0808e', 'pkd': '#d05a6c', 'bl': '#44a6de', 'bll': '#7cc6f0', 'bld': '#2c80b8', 'eye': '#ffffff', 'dark': '#20203a'}
    new(d, pal)
    put(d, 'body', 0, plate([16, 34, 32, 30, 48, 34, 50, 47, 32, 51, 14, 47], 'pk', T=8.0, round=0.5))
    put(d, 'back', 10, plate([15, 30, 32, 26, 49, 30, 50, 42, 32, 44, 14, 42], 'bl', T=8.0))
    put(d, 'tail', 12, plate([42, 28, 56, 14, 60, 20, 49, 36], 'bl', T=3.6, dd=12), plate([50, 22, 58, 12, 60, 16, 55, 24], 'bll', T=3.0, dd=14))
    put(d, 'head', -6, plate([20, 14, 32, 8, 44, 14, 44, 27, 32, 32, 20, 27], 'pk', T=9.0), plate([21, 14, 32, 8, 43, 14, 32, 18], 'bll', T=9.0, dd=0.2))
    put(d, 'beak', -8, cap(32, 24, 32, 26, 7.4, 3.6, 'bl', d1=-9, d2=-22), cap(32, 24, 32, 26, 6.6, 6.0, 'bld', d1=-9, d2=-10))
    for s, sx in (('L', -1), ('R', 1)):
        x = 32 + sx * 6.8
        put(d, 'leg' + s, 2, plate([x - 3.4, 47, x + 3.4, 47, x + 3.0, 58, x - 3.0, 58], 'pk', T=3.6))
        put(d, 'foot' + s, 0, e(x + sx * 0.4, 59.2, 4.6, 2.2, 'pkd', rd=3.6, dd=-2.5))
    paint(d, eye(26.6, 19.6, 3.4, iris='#2848a0'), eye(37.4, 19.6, 3.4, iris='#2848a0'))


def _spiral(cx, cy, r0, r1, turns, n=64, a0=0.0):
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        a = a0 + t * turns * 2 * math.pi
        r = r0 + (r1 - r0) * t
        pts += [round(cx + r * math.cos(a), 3), round(cy + r * math.sin(a), 3)]
    return pts


def _ammonite(d, big):
    pal = {'bl': '#72b4e4' if not big else '#78a8d8', 'bld': '#4e8cc0', 'sh': '#ecdca8', 'shd': '#c0a468', 'spk': '#f2e6b8', 'eye': '#ffe066',
           'dark': '#20203a', 'beak': '#f4ecd0'}
    new(d, pal)
    S = 1.25 if big else 1.0
    sx0, sy0 = (40, 30) if not big else (40, 27)
    put(d, 'shell', 6.0, e(sx0, sy0, 15 * S, 15.6 * S, 'sh', rd=9.5, dd=2), e(sx0 + 6 * S, sy0 + 6 * S, 8.6 * S, 8.4 * S, 'sh', rd=8, dd=1))
    paint(d, band('shell', _spiral(sx0 + 1.5, sy0 + 1.5, 1.4, 12.6 * S, 2.4, 80), 1.3, 'shd'),
          band('shell', _spiral(sx0 + 1.5, sy0 + 1.5, 1.4, 12.6 * S, 2.4, 80, a0=0.2), 0.6, 'shd'))
    nsp = 7 if big else 5
    for i in range(nsp):
        a = math.radians(-80 + i * (200.0 / (nsp - 1)))
        rr = 14.5 * S
        x, y = sx0 + rr * math.cos(a), sy0 + rr * math.sin(a)
        L = (8.5 if big else 5.0)
        put(d, 'spike%d' % i, 6.5, cap(x, y, x + L * math.cos(a), y + L * math.sin(a), 3.4 if big else 2.8, 0.7, 'spk', d1=2, d2=2))
    by = 42.5 if not big else 39.5
    put(d, 'body', 0, e(24, by, 9.6 * S, 8.6 * S, 'bl', rd=9.0 * S), e(28, by - 2, 8, 8, 'bl', rd=8.4, dd=4))
    put(d, 'head', -3, e(24, by + 0.5, 9.2 * S, 7.8 * S, 'bl', rd=8.4 * S))
    er = 3.6 if big else 3.4
    for s, sx in (('L', -1), ('R', 1)):
        off = 5.0 * S
        surf = 8.4 * S * math.sqrt(max(0.05, 1 - (off / (9.2 * S)) ** 2 - 0.05))
        ecd = -3 - surf + er * 0.55
        put(d, 'eye' + s, ecd, e(24 + sx * off, by - 1.8, er, er * 1.08, 'eye', rd=er * 0.9))
        put(d, 'pupil' + s, ecd - 1.5, e(24 + sx * off - sx * 0.2, by - 1.4, er * 0.55, er * 0.62, 'dark', rd=er * 0.5))
    if big:
        put(d, 'beak', -6, cap(21.4, by + 5, 21, by + 10.5, 1.9, 0.4, 'beak', d1=-9, d2=-10), cap(26.6, by + 5, 27, by + 10.5, 1.9, 0.4, 'beak', d1=-9, d2=-10))
    nt = 9 if big else 8
    for i in range(nt):
        f = (i - (nt - 1) / 2.0)
        x0 = 24 + f * 2.5 * S
        L = 12.5 if big else 8.5
        x1 = x0 + f * (3.6 if big else 3.0)
        put(d, 'tent%d' % i, -1.0 - abs(f) * 0.5,
            stroke([x0, by + 5, (x0 + x1) / 2, by + 5 + L * 0.55, x1 + (1.8 if f > 0 else -1.8), 59.4], 4.8 if big else 4.4, 'bl', w2=1.8,
                   d1=-2 - abs(f) * 0.6, d2=-6 + f * 0.9))


@fix('OMANYTE')
def omanyte(d, look):
    _ammonite(d, False)


@fix('OMASTAR')
def omastar(d, look):
    _ammonite(d, True)


@fix('KABUTO')
def kabuto(d, look):
    pal = {'br': '#b47c3c', 'brd': '#845424', 'brl': '#cc9450', 'tan': '#e6c890', 'dark': '#26202a', 'red': '#ff4a32'}
    new(d, pal)
    put(d, 'body', 0, e(32, 44, 19.4, 11.8, 'br', rd=15.5, dd=2), e(32, 49.6, 19.6, 4.4, 'brd', rd=15.6, dd=2))
    paint(d, band('body', [32, 33, 32, 50], 1.3, 'brd', frontOnly=False), band('body', [16.5, 47, 23, 41, 32, 38.2, 41, 41, 47.5, 47], 1.1, 'brd', frontOnly=True),
          band('body', [19, 44, 26, 38, 32, 36.5], 0.7, 'brd'), band('body', [45, 44, 38, 38, 32, 36.5], 0.7, 'brd'))
    put(d, 'face', -11, e(32, 50.2, 10.8, 4.6, 'dark', rd=6.4, dd=-2))
    paint(d, eye(27.6, 49.8, 2.4, style='angry', sclera=False, flip=True, iris='#ff4a32'), eye(36.4, 49.8, 2.4, style='angry', sclera=False, iris='#ff4a32'))
    for i, (x, dz) in enumerate(((20, -4), (44, -4), (23, 10), (41, 10))):
        put(d, 'leg%d' % i, 0.5, cap(x, 53, x + (x - 32) * 0.12, 58.8, 3.2, 2.5, 'tan', dd=dz), e(x + (x - 32) * 0.14, 59.6, 2.9, 1.3, 'tan', rd=2.4, dd=dz - 1.2))
    put(d, 'tail', 3, stroke([32, 52, 32, 56, 32, 58], 3.0, 'brd', w2=1.4, d1=14, d2=22))


@fix('KABUTOPS')
def kabutops(d, look):
    pal = {'br': '#b0803e', 'brd': '#7c5228', 'brl': '#cc9452', 'tan': '#eccf98', 'tand': '#c8a468', 'dark': '#241e26', 'blade': '#eef0f2',
           'blade2': '#a8b6c4', 'red': '#ff4a32'}
    new(d, pal)
    put(d, 'body', 0, e(32, 34, 9.6, 12.4, 'br', rd=8.2), e(32, 46, 8.4, 6.2, 'br', rd=7.4))
    paint(d, spot('body', 32, 36, 5.4, 9.6, 'tan', frontOnly=True),
          *[band('body', [27.4, 29 + 3.3 * j, 32, 30.2 + 3.3 * j, 36.6, 29 + 3.3 * j], 0.8, 'tand', frontOnly=True) for j in range(4)])
    put(d, 'head', -1.6, e(32, 14.6, 8.2, 7.6, 'br', rd=7.6), cap(32, 10, 32, -1.4, 6.0, 0.9, 'br', d1=-1, d2=-2),
        e(32, 17.2, 6.0, 3.8, 'dark', rd=4.4, dd=-4.4))
    paint(d, eye(28.4, 15.4, 2.1, style='angry', sclera=False, flip=True, iris='#ff4a32'), eye(35.6, 15.4, 2.1, style='angry', sclera=False, iris='#ff4a32'))
    blade = [8.4, 27, 13, 27.6, 17.4, 33, 19.6, 41, 18.6, 50, 16, 57, 14, 60.5, 14.6, 52, 14.4, 44, 12.8, 37, 9.4, 32]
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'arm' + s, -0.5, cap(32 + sx * 8.4, 24, 32 + sx * 11.6, 32, 3.2, 2.8, 'br', d1=-1, d2=-3))
        pts = curve(blade, 3)
        pts = [(32 + sx * v) if i % 2 == 0 else v for i, v in enumerate(pts)]
        put(d, 'blade' + s, -3.2, plate(pts, 'blade', T=1.8), stroke([32 + sx * 13.6, 34, 32 + sx * 15.6, 43, 32 + sx * 15.4, 52], 1.4, 'blade2'))
        for k in range(4):
            put(d, 'spike%s%d' % (s, k), 4, cap(32 + sx * (7 + 0.6 * k), 22 + 5.2 * k, 32 + sx * (14 + 0.6 * k), 17 + 5.4 * k - k * 0.6, 3.2 - k * 0.2, 0.7, 'brd', d1=6, d2=6)) if k in (0, 2) else None
        x = 32 + sx * 6.4
        put(d, 'leg' + s, 0.2, cap(x, 44, x + sx * 1.2, 51, 4.8, 4.0, 'br'), cap(x + sx * 1.2, 51, x + sx * 0.4, 58, 4.0, 3.1, 'br'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.6, 59.3, 5.2, 2.5, 'br', dd=-2.2))
        toes(d, 'foot' + s, -1.0, x + sx * 0.6, 60.4, 3, 3.2, 1.1, 'tan', dd=-6.4)
    put(d, 'tail', 4, stroke([33, 50, 37, 57, 33, 60], 8.0, 'br', w2=2.6, d1=5, d2=24))


@fix('AERODACTYL')
def aerodactyl(d, look):
    pal = {'gr': '#b2a6cc', 'grd': '#8a7cae', 'bel': '#d2c8e4', 'mem': '#8c76b8', 'memd': '#6e5a9c', 'tooth': '#f8f4ec', 'dark': '#2a2034', 'red': '#c02838'}
    new(d, pal)
    put(d, 'body', 0, e(32, 38.5, 9.8, 11.4, 'gr', rd=8.4), e(32, 49, 8.4, 5.0, 'gr', rd=7.2))
    paint(d, spot('body', 32, 40, 5.6, 8.6, 'bel', frontOnly=True))
    put(d, 'neck', -0.6, cap(32, 22, 32, 28, 4.2, 5.0, 'gr'))
    put(d, 'head', -2.5, e(32, 16.6, 8.0, 7.2, 'gr', rd=7.4), cap(32, 19.5, 32, 21.5, 5.0, 3.9, 'gr', d1=-4, d2=-18),
        cap(32, 23.3, 32, 24.3, 3.8, 3.0, 'gr', d1=-4, d2=-15))
    paint(d, eye(27.4, 15.4, 2.6, style='angry', flip=True, iris='#c02838'), eye(36.6, 15.4, 2.6, style='angry', iris='#c02838'),
          band('head', [30.8, 22.4, 33.2, 22.4], 0.8, 'dark', frontOnly=True))
    put(d, 'teeth', -6, *[cap(32 + sx * 3.4, 22.4, 32 + sx * 3.4, 25.6, 1.2, 0.3, 'tooth', dd=dz) for dz in (-8, -11.5, -15) for sx in (-1, 1)],
        *[cap(32 + sx * 2.8, 25.2, 32 + sx * 2.8, 22.6, 1.0, 0.3, 'tooth', dd=dz - 0.5) for dz in (-9.5, -13) for sx in (-1, 1)])
    for i, (bx, tx, ty, dz) in enumerate(((27.6, 22, 3.8, 3), (32, 32, 1.4, 4), (36.4, 42, 3.8, 3))):
        put(d, 'crest%d' % i, 1.5, cap(bx, 11.6, tx, ty, 3.4, 0.7, 'grd', d1=dz, d2=dz + 4))
    wing = [7, -3, 13, -11, 21, -19, 30, -25, 29, -15, 31, -10, 27, -4, 28, 4, 21, 0, 17, 9, 12, 2, 8, 6]
    for s, sx in (('L', -1), ('R', 1)):
        pts = curve(wing, 3)
        pts = [(32 + sx * v) if i % 2 == 0 else v + 30 for i, v in enumerate(pts)]
        put(d, 'wing' + s, 3.5, plate(pts, 'mem', T=1.1),
            stroke([32 + sx * 7, 27, 32 + sx * 15, 18, 32 + sx * 23, 10, 32 + sx * 30, 5], 3.2, 'gr', w2=1.6, d1=-0.5, d2=-0.5),
            stroke([32 + sx * 23, 10, 32 + sx * 28, 26], 1.4, 'memd', d1=-0.5, d2=-0.5), stroke([32 + sx * 23, 10, 32 + sx * 21, 30], 1.4, 'memd', d1=-0.5, d2=-0.5))
        x = 32 + sx * 5.8
        put(d, 'leg' + s, 0.2, cap(x, 46, x + sx * 1.0, 52.5, 4.6, 3.6, 'gr'), cap(x + sx * 1.0, 52.5, x + sx * 0.4, 58.2, 3.6, 2.8, 'gr'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.6, 59.3, 4.6, 2.3, 'gr', dd=-2.0))
        claw_tips(d, 'foot' + s, -1.0, x + sx * 0.6, 60.3, 3, 2.8, 1.6, 0.9, 'tooth', dd=-5.6, diry=0.4)
    put(d, 'tail', 6, stroke([32, 50, 32, 56, 32, 51, 32, 45], 5.4, 'gr', w2=2.0, d1=8, d2=32),
        smooth_plate([32, 36, 36, 45, 32, 53, 28, 45], 'grd', T=1.4, dd=33))


@fix('SNORLAX')
def snorlax(d, look):
    pal = {'tl': '#2f6a78', 'tld': '#22505e', 'cr': '#f2e4c2', 'crd': '#d8c49a', 'pad': '#a87e56', 'claw': '#f8f2e0', 'dark': '#20203a'}
    new(d, pal)
    put(d, 'body', 0, e(32, 41, 22.4, 19.2, 'tl', rd=17.4), e(32, 52, 21, 8.6, 'tl', rd=16))
    paint(d, spot('body', 32, 44, 15.4, 13.6, 'cr', frontOnly=True))
    put(d, 'head', -4, e(32, 18.5, 14.0, 11.6, 'tl', rd=11.6))
    put(d, 'face', -12.6, e(32, 23.4, 10.8, 8.0, 'cr', rd=6.4))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ear' + s, -3, cap(32 + sx * 10.4, 10.4, 32 + sx * 12.8, 1.4, 4.6, 0.9, 'tl', d1=0, d2=0))
        put(d, 'arm' + s, -1.6, cap(32 + sx * 19.5, 34, 32 + sx * 23.4, 49, 7.4, 6.6, 'tl', d1=-2, d2=-5))
        put(d, 'hand' + s, -3.5, e(32 + sx * 23.8, 51.4, 5.2, 4.8, 'cr', rd=4.8, dd=-4))
        claw_tips(d, 'hand' + s, -3.5, 32 + sx * 23.8, 54, 3, 2.9, 2.6, 0.9, 'claw', dd=-4)
        put(d, 'foot' + s, -9, e(32 + sx * 12.6, 55.6, 8.2, 5.2, 'cr', rd=6.0, dd=-4), e(32 + sx * 12.6, 55.8, 4.6, 3.0, 'pad', rd=1.4, dd=-8.6))
        claw_tips(d, 'foot' + s, -9, 32 + sx * 12.6, 57.6, 3, 4.0, 2.6, 1.0, 'claw', dd=-5.4, diry=0.3)
    paint(d, eye(26.6, 21.8, 2.6, style='closed'), eye(37.4, 21.8, 2.6, style='closed'),
          spot('face', 30.4, 25.6, 0.7, 0.6, 'dark', frontOnly=True), spot('face', 33.6, 25.6, 0.7, 0.6, 'dark', frontOnly=True),
          mouth(32, 28.4, 4.6, 'smile'),
          spot('face', 27.4, 29.6, 1.0, 1.3, 'claw', frontOnly=True), spot('face', 36.6, 29.6, 1.0, 1.3, 'claw', frontOnly=True))
    put(d, 'tail', 8, stroke([38, 54, 44, 55, 48, 51], 6.0, 'tl', w2=2.6, d1=10, d2=16))


def _bird(d, kind):
    if kind == 'ARTICUNO':
        pal = dict(main='#8fcdf0', light='#d4eefa', dark='#4a7cc8', wing='#a4d8f6', tip='#5c8ed4', beak='#8c94a6', leg='#7c86a0', eye='#e03050',
                   crest='#4a7cc8')
    elif kind == 'ZAPDOS':
        pal = dict(main='#f8d030', light='#fbe888', dark='#c8a018', wing='#f8d030', tip='#26202a', beak='#f0a838', leg='#f0a038', eye='#26202a',
                   crest='#f8d030')
    else:
        pal = dict(main='#f8c23a', light='#fbe888', dark='#e0601c', wing='#f26a1e', tip='#f9c83a', beak='#e8a050', leg='#e0964a', eye='#26202a',
                   crest='#f26a1e')
    pal.update(dark_='#26202a', red='#e03050')
    new(d, pal)
    put(d, 'body', 0, e(32, 38.4, 9.8, 12.4, 'main', rd=8.6), e(32, 49, 7.6, 5.2, 'main', rd=6.6))
    paint(d, spot('body', 32, 40, 5.8, 9.2, 'light', frontOnly=True))
    put(d, 'neck', -0.8, cap(32, 22, 32, 30, 4.6, 6.2, 'main'))
    put(d, 'head', -2.2, e(32, 16, 6.8, 6.4, 'main', rd=6.4), cap(32, 17.6, 32, 19.4, 3.2, 1.0, 'beak', d1=-4.5, d2=-15.5))
    paint(d, eye(28.4, 14.8, 2.4, iris=pal['eye'], sclera=(kind != 'ZAPDOS')), eye(35.6, 14.8, 2.4, iris=pal['eye'], sclera=(kind != 'ZAPDOS')))
    # crest
    if kind == 'ARTICUNO':
        for i, (bx, tx, ty) in enumerate(((29, 24, 1), (32, 32, -3), (35, 40, 1))):
            put(d, 'crest%d' % i, -1.0, cap(bx, 11, tx, ty, 3.4, 0.8, 'crest', d1=1, d2=3))
        wing = [(6, -3), (14, -11), (22, -19), (29, -25), (28, -16), (31, -12), (27, -6), (29, 0), (24, 3), (25, 9), (18, 8), (14, 12), (9, 8), (5, 4)]
        inner = [(8, -2), (15, -9), (22, -16), (24, -10), (21, -4), (22, 2), (16, 3), (10, 3)]
    elif kind == 'ZAPDOS':
        for i, (bx, tx, ty) in enumerate(((27, 21, 3), (29.5, 26, -3), (32, 32, -5), (34.5, 38, -3), (37, 43, 3))):
            put(d, 'crest%d' % i, -1.0, cap(bx, 11, tx, ty, 3.0, 0.7, 'crest', d1=1, d2=3))
        wing = [(6, -2), (12, -9), (18, -18), (24, -27), (23, -17), (31, -20), (26, -10), (34, -8), (26, -3), (32, 4), (22, 4), (24, 12), (14, 7), (10, 12), (6, 6)]
        inner = [(8, -1), (13, -7), (18, -14), (24, -19), (22, -9), (26, -3), (18, 0), (11, 3)]
    else:
        for i, (bx, tx, ty) in enumerate(((28, 23, 2), (32, 32, -5), (36, 41, 2))):
            put(d, 'crest%d' % i, -1.0, cap(bx, 11, tx, ty, 3.6, 0.7, 'crest', d1=1, d2=3), cap(bx, 10.6, (bx + tx) / 2, 4.5 + i % 2, 2.0, 0.5, 'tip', d1=0, d2=1))
        wing = [(6, -3), (13, -10), (19, -19), (25, -27), (26, -17), (32, -17), (28, -9), (33, -3), (27, 1), (29, 9), (22, 7), (20, 15), (14, 9), (9, 13), (5, 5)]
        inner = [(8, -2), (14, -8), (20, -14), (24, -9), (28, -3), (22, 3), (14, 6), (9, 4)]
    for s, sx in (('L', -1), ('R', 1)):
        pts = curve([v for p in wing for v in (32 + sx * p[0], 30 + p[1])], 3)
        ptsi = curve([v for p in inner for v in (32 + sx * p[0], 30 + p[1])], 3)
        put(d, 'wing' + s, 3.6, plate(pts, 'wing', T=1.4), plate(ptsi, 'tip' if kind != 'ARTICUNO' else 'light', T=1.5, dd=-0.4))
        if kind == 'ZAPDOS':
            paint(d, band('wing' + s, [32 + sx * 12, 22, 32 + sx * 27, 8], 1.8, 'dark_'), band('wing' + s, [32 + sx * 14, 28, 32 + sx * 30, 14], 1.6, 'dark_'))
        x = 32 + sx * 5
        put(d, 'leg' + s, 0.4, cap(x, 48, x + sx * 0.4, 57.4, 2.3, 1.9, 'leg'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.4, 59.3, 3.4, 1.4, 'leg', dd=-3), cap(x, 59.5, x, 60.2, 1.0, 0.6, 'leg', dd=-8))
        toes(d, 'foot' + s, -1.0, x + sx * 0.4, 60.3, 3, 2.6, 0.9, 'leg', dd=-6.0)
    if kind == 'ARTICUNO':
        put(d, 'tailA', 6, stroke([31, 44, 29, 52, 27, 58, 25, 61], 6.4, 'dark', w2=1.8, d1=8, d2=26))
        put(d, 'tailB', 6, stroke([33, 44, 35, 52, 37, 58, 39, 61], 6.4, 'main', w2=1.8, d1=8, d2=26))
    elif kind == 'ZAPDOS':
        put(d, 'tail', 6, *[cap(32 + dx, 46, 32 + dx * 1.6, 56 + h, 3.6, 0.7, 'main', d1=8, d2=24) for dx, h in ((-4, 3), (0, 4), (4, 3))])
    else:
        put(d, 'tailA', 6, stroke([30, 46, 27, 54, 26, 60], 6.8, 'wing', w2=1.6, d1=8, d2=26), stroke([30, 47, 28, 53, 27.4, 57], 3.0, 'tip', d1=8.5, d2=25))
        put(d, 'tailB', 6, stroke([34, 46, 37, 54, 38, 60], 6.8, 'wing', w2=1.6, d1=8, d2=26), stroke([34, 47, 36, 53, 36.6, 57], 3.0, 'tip', d1=8.5, d2=25))


@fix('ARTICUNO')
def articuno(d, look):
    _bird(d, 'ARTICUNO')


@fix('ZAPDOS')
def zapdos(d, look):
    _bird(d, 'ZAPDOS')


@fix('MOLTRES')
def moltres(d, look):
    _bird(d, 'MOLTRES')


def _serpent(d, dragonair):
    pal = {'bl': '#5a94e0' if not dragonair else '#6ea0e2', 'bld': '#4074c0', 'wh': '#f4f4fb', 'whd': '#d4d8ea', 'fin': '#f6f6fc', 'orb': '#3a6ee0',
           'eye': '#ffffff', 'dark': '#20203a', 'horn': '#f6f6fc'}
    new(d, pal)
    if not dragonair:
        path = [31, 25, 30, 33, 36, 40, 41, 47, 35, 54, 25, 54, 20, 58, 12, 55]
        w, w2 = 9.0, 2.6
    else:
        path = [31, 26, 29, 33, 34, 39, 42, 44, 40, 51, 31, 55, 22, 52, 18, 57, 24, 60, 33, 59]
        w, w2 = 10.0, 3.0
    put(d, 'body', 0, stroke(path, w, 'bl', w2=w2, d1=-1, d2=1))
    put(d, 'belly', -4.0, stroke(path[:12] if not dragonair else path[:14], w * 0.55, 'wh', w2=w2 * 0.6, d1=-1, d2=-1), z=0.2)
    hr = 8.6 if not dragonair else 8.2
    put(d, 'head', -3, e(31, 16.5, hr, hr * 0.92, 'bl', rd=hr * 0.92), e(31, 21.4, 4.4, 3.0, 'bl', rd=3.6, dd=-6.4))
    paint(d, mouth(31, 22.8, 2.2, 'smile'), spot('head', 29.8, 21.0, 0.5, 0.4, 'dark', frontOnly=True), spot('head', 32.2, 21.0, 0.5, 0.4, 'dark', frontOnly=True))
    er = 3.3
    for s, sx in (('L', -1), ('R', 1)):
        off = 5.0
        surf = hr * 0.92 * math.sqrt(max(0.05, 1 - (off / hr) ** 2 - 0.02))
        ecd = -3 - surf + er * 0.5
        put(d, 'eye' + s, ecd, e(31 + sx * off, 14.6, er, er * 1.08, 'eye', rd=er * 0.9))
        put(d, 'pupil' + s, ecd - 1.3, e(31 + sx * off - sx * 0.1, 14.9, er * 0.56, er * 0.62, 'dark', rd=er * 0.5))
        pts = curve([sx * 6, 14, sx * 11, 10, sx * 15, 5, sx * 14, 13, sx * 10.5, 17], 3)
        pts = [(31 + v) if i % 2 == 0 else v for i, v in enumerate(pts)]
        put(d, 'fin' + s, -1.0, plate(pts, 'fin', T=1.1))
    if dragonair:
        put(d, 'horn', -4, cap(31, 9.4, 31, -1.2, 3.4, 0.6, 'horn', d1=-1, d2=-2))
        put(d, 'orbN', -9, e(31, 30, 4.0, 4.0, 'orb', rd=3.8, dd=-2.5))
        put(d, 'orbT1', -1, e(23, 51.5, 3.6, 3.6, 'orb', rd=3.4, dd=-3))
        put(d, 'orbT2', -1, e(19.6, 57.5, 3.3, 3.3, 'orb', rd=3.1, dd=-3))
    else:
        put(d, 'bump', -3, e(31, 9.4, 2.4, 2.0, 'wh', rd=2.0, dd=-1))


@fix('DRATINI')
def dratini(d, look):
    _serpent(d, False)


@fix('DRAGONAIR')
def dragonair(d, look):
    _serpent(d, True)


@fix('DRAGONITE')
def dragonite(d, look):
    pal = {'or': '#f6a850', 'ord': '#d88434', 'cr': '#f8e2b0', 'crd': '#dcb878', 'wing': '#56a898', 'wingd': '#3c8878', 'claw': '#f4ecd6', 'dark': '#20203a',
           'eye': '#ffffff'}
    new(d, pal)
    put(d, 'body', 0, e(32, 38.5, 13.0, 14.4, 'or', rd=10.4), e(32, 50, 11.4, 7.6, 'or', rd=9.4))
    paint(d, spot('body', 32, 41, 8.6, 11.4, 'cr', frontOnly=True),
          *[band('body', [24.2, 33 + 3.4 * j, 32, 34.4 + 3.4 * j, 39.8, 33 + 3.4 * j], 0.9, 'crd', frontOnly=True) for j in range(5)])
    put(d, 'head', -3, e(32, 16, 9.8, 8.8, 'or', rd=8.8), e(32, 21, 6.6, 4.4, 'or', rd=5.4, dd=-6.4))
    paint(d, eye(27, 14.6, 3.2, iris='#382828'), eye(37, 14.6, 3.2, iris='#382828'), mouth(32, 24.4, 2.8, 'smile'),
          spot('head', 30, 20.4, 0.6, 0.5, 'dark', frontOnly=True), spot('head', 34, 20.4, 0.6, 0.5, 'dark', frontOnly=True))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ant' + s, -2, stroke([32 + sx * 4.4, 9.4, 32 + sx * 7.8, 3, 32 + sx * 6.6, -1.4, 32 + sx * 9.4, -3.6], 2.6, 'or', w2=1.6, d1=0, d2=0))
        put(d, 'earbump' + s, -2, cap(32 + sx * 9, 11.4, 32 + sx * 11.4, 7.2, 2.6, 0.8, 'or'))
        put(d, 'arm' + s, -1.0, cap(32 + sx * 12.6, 30, 32 + sx * 16.6, 43, 4.2, 3.5, 'or', d1=-1, d2=-5))
        put(d, 'hand' + s, -3.0, e(32 + sx * 17.2, 45, 3.8, 3.5, 'or', rd=3.5, dd=-5))
        claw_tips(d, 'hand' + s, -3.0, 32 + sx * 17.2, 47.2, 3, 2.3, 2.6, 0.8, 'claw', dd=-5)
        x = 32 + sx * 8.4
        put(d, 'leg' + s, 0.3, cap(x, 51, x + sx * 0.8, 57.8, 5.6, 4.8, 'or'))
        put(d, 'foot' + s, -1.0, e(x + sx * 1.0, 59.2, 6.4, 2.8, 'or', dd=-2.4))
        claw_tips(d, 'foot' + s, -1.0, x + sx * 1.0, 60.2, 3, 3.6, 1.6, 0.95, 'claw', dd=-7.4, diry=0.4)
        wing = [7, -2, 13, -9, 19, -17, 24, -22, 22, -13, 25, -8, 20, -3, 21, 3, 14, 1, 10, 6]
        pts = curve(wing, 3)
        pts = [(32 + sx * v) if i % 2 == 0 else v + 30 for i, v in enumerate(pts)]
        put(d, 'wing' + s, 4.5, plate(pts, 'wing', T=1.3))
    put(d, 'tail', 6, stroke([36, 52, 41, 58, 36, 60.4, 34, 56], 11, 'or', w2=3.0, d1=6, d2=26))


@fix('MEWTWO')
def mewtwo(d, look):
    pal = {'gr': '#d2c8de', 'grd': '#b0a2c4', 'pu': '#9866b6', 'pud': '#7a4a9a', 'eye': '#ffffff', 'dark': '#2a1e3a'}
    new(d, pal)
    put(d, 'body', 0, e(32, 33, 9.6, 11.4, 'gr', rd=7.6), e(32, 44.4, 8.2, 6.6, 'gr', rd=7))
    paint(d, spot('body', 32, 42.6, 6.4, 5.2, 'pu', frontOnly=True), spot('body', 32, 30, 4.4, 3.4, 'grd', frontOnly=True))
    put(d, 'neck', -0.6, cap(32, 21, 32, 25, 3.4, 4.6, 'gr'))
    put(d, 'head', -1.8, e(32, 14, 7.8, 8.6, 'gr', rd=7.4), e(32, 19, 4.4, 3.2, 'gr', rd=3.6, dd=-4.4))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ear' + s, -1.4, cap(32 + sx * 4.6, 8.2, 32 + sx * 6.6, -2.2, 3.4, 0.7, 'gr', d1=0, d2=0))
        put(d, 'arm' + s, -0.6, cap(32 + sx * 9.6, 26, 32 + sx * 15.8, 35, 3.6, 3.0, 'gr', d1=-1, d2=-4),
            cap(32 + sx * 15.8, 35, 32 + sx * 17.6, 43, 3.0, 2.5, 'gr', d1=-4, d2=-6))
        put(d, 'hand' + s, -2.6, e(32 + sx * 17.9, 44.6, 2.9, 2.6, 'gr', rd=2.6, dd=-6),
            cap(32 + sx * 16.6, 46, 32 + sx * 16, 51, 1.3, 0.8, 'gr', dd=-6), cap(32 + sx * 18.2, 46.4, 32 + sx * 18.6, 51.4, 1.3, 0.8, 'gr', dd=-6),
            cap(32 + sx * 19.6, 45.2, 32 + sx * 21.4, 49.2, 1.2, 0.8, 'gr', dd=-6))
        x = 32 + sx * 6.4
        put(d, 'leg' + s, 0.3, cap(x, 45, x + sx * 1.6, 51.6, 5.4, 4.2, 'gr'), cap(x + sx * 1.6, 51.6, x + sx * 0.6, 58, 4.0, 3.0, 'gr'))
        put(d, 'foot' + s, -1.0, e(x + sx * 0.8, 59.4, 4.8, 2.3, 'gr', dd=-2.4))
        toes(d, 'foot' + s, -1.0, x + sx * 0.8, 60.5, 3, 3.0, 1.15, 'gr', dd=-6.0)
    put(d, 'tube', 5, stroke([32, 20, 32, 28, 32, 36], 4.0, 'pu', d1=6, d2=7), e(32, 21, 3.0, 2.0, 'pud', rd=2.6, dd=6))
    put(d, 'tail', 7, stroke([37, 49, 45, 55, 52, 51, 55, 41], 6.4, 'gr', w2=4.8, d1=6, d2=24), e(55.4, 39.6, 4.6, 5.6, 'pu', rd=4.6, dd=25))
    paint(d, eye(28.2, 13.4, 2.0, style='angry', flip=True, iris='#7a3ac0'), eye(35.8, 13.4, 2.0, style='angry', iris='#7a3ac0'), mouth(32, 22.0, 1.8, 'line'))


@fix('MEW')
def mew(d, look):
    pal = {'pk': '#f8b4d0', 'pkd': '#f090b8', 'pkl': '#fcdbe8', 'eye': '#ffffff', 'dark': '#20203a'}
    new(d, pal)
    put(d, 'body', 0, e(32, 36, 8.2, 9.6, 'pk', rd=7.4), e(32, 44, 7.2, 5.2, 'pk', rd=6.6))
    paint(d, spot('body', 32, 40, 4.6, 5.8, 'pkl', frontOnly=True))
    put(d, 'head', -1.8, e(32, 19, 11.6, 10.4, 'pk', rd=10.2))
    for s, sx in (('L', -1), ('R', 1)):
        put(d, 'ear' + s, -1.4, cap(32 + sx * 6.8, 10.6, 32 + sx * 9.2, 1.6, 4.2, 0.8, 'pk', d1=0, d2=0))
        put(d, 'arm' + s, -0.6, cap(32 + sx * 7.2, 32, 32 + sx * 12.6, 39, 2.5, 2.1, 'pk', d1=-1, d2=-3), e(32 + sx * 13.4, 40.2, 2.2, 2.0, 'pk', rd=2.0, dd=-3))
        x = 32 + sx * 4.8
        put(d, 'leg' + s, 0.2, cap(x, 44, x + sx * 1.4, 50, 3.6, 3.0, 'pk'))
        put(d, 'foot' + s, -1.2, e(x + sx * 2, 52.4, 4.8, 2.6, 'pk', dd=-2.6), *[e(x + sx * 2 + (k - 1) * 2.0, 53.4, 1.0, 1.0, 'pkd', rd=1.0, dd=-6.2) for k in range(3)])
    put(d, 'tail', 5, stroke([36, 45, 42, 51, 50, 51, 55, 45, 56, 38], 3.4, 'pk', w2=2.0, d1=4, d2=12), e(56, 35.6, 3.6, 4.6, 'pk', rd=3.6, dd=13))
    paint(d, eye(26.2, 19.4, 4.0, iris='#3a80e8'), eye(37.8, 19.4, 4.0, iris='#3a80e8'), mouth(32, 26.6, 2.4, 'smile'),
          spot('head', 32, 22.2, 0.5, 0.4, 'pkd', frontOnly=True))

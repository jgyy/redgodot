"""Per-species patches of upstream's 2D sprite definitions (pipeline/extracted/mons.json).

The sprite parts are a great starting point (proportions, palette, markings all line up with the
2D game) but a sprite only has to look right from one side.  Where the 3D model built from it is
anatomically off, unappealing, or missing something a Pokemon is known for -- looked up in
pipeline/data/species_looks.json's `features` -- the fix below edits the part list before it is
turned into geometry: add a missing limb / ear / horn, thicken a paper-thin neck, reshape an ear,
give a serpent a proper head, etc.

Part vocabulary (sprite space: 64x64, x right, y DOWN, ground ~ y 60), same as upstream:
  {'t':'e','x','y','rx','ry','rot','c','g','z'}                       ellipsoid
  {'t':'c','x1','y1','x2','y2','r1','r2','c','g','z'}                 tapered capsule (limb)
  {'t':'l','pts':[x,y,...],'w','w2','c','g','z'}                      round stroke (tail, tentacle)
  {'t':'p','pts':[x,y,...],'c','g','z'}                               bevelled plate (ear, wing, spike)
  spots / stripes / eyes / mouths ('on': group) paint the texture only.
Extensions understood by monparts.py:  d/d1/d2 (depth offsets), rd (ellipsoid depth radius), T (plate
half-thickness), cd (force the group's depth).

Every fix is a small function `fix(d, look)` editing the definition `d` in place.
"""
import copy
import math

FIXES = {}


def fix(*names):
    def deco(fn):
        for n in names:
            FIXES[n] = fn
        return fn
    return deco


def apply(name, defn, look):
    d = copy.deepcopy(defn)
    fn = FIXES.get(name)
    if fn is not None:
        fn(d, look or {})
    pal = (look or {}).get('pal')
    if pal:
        d.setdefault('pal', {}).update(pal)
    return d


# ----------------------------------------------------------------------------- helpers
def parts(d, g):
    return [p for p in d['parts'] if p.get('g') == g]


def on(d, g):
    return [p for p in d['parts'] if p.get('on') == g]


def add(d, p, at=None):
    if at is None:
        d['parts'].append(p)
    else:
        d['parts'].insert(at, p)
    return p


def drop(d, g):
    d['parts'] = [p for p in d['parts'] if p.get('g') != g and p.get('on') != g]


def mod(d, g, **kw):
    for p in parts(d, g):
        p.update(kw)


def E(g, x, y, rx, ry, c, z=0, rot=0, **kw):
    p = {'t': 'e', 'x': x, 'y': y, 'rx': rx, 'ry': ry, 'c': c, 'g': g, 'z': z}
    if rot:
        p['rot'] = rot
    p.update(kw)
    return p


def Cap(g, x1, y1, x2, y2, r1, r2, c, z=0, **kw):
    p = {'t': 'c', 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'r1': r1, 'r2': r2, 'c': c, 'g': g, 'z': z}
    p.update(kw)
    return p


def Poly(g, pts, c, z=0, **kw):
    p = {'t': 'p', 'pts': list(pts), 'c': c, 'g': g, 'z': z}
    p.update(kw)
    return p


def Stroke(g, pts, w, c, z=0, w2=None, **kw):
    p = {'t': 'l', 'pts': list(pts), 'w': w, 'c': c, 'g': g, 'z': z}
    if w2 is not None:
        p['w2'] = w2
    p.update(kw)
    return p


def Spot(on_g, x, y, rx, ry, c, **kw):
    p = {'t': 'spot', 'x': x, 'y': y, 'rx': rx, 'ry': ry, 'c': c, 'on': on_g}
    p.update(kw)
    return p


def _pts_map(pts, fn):
    out = []
    for i in range(0, len(pts) - 1, 2):
        x, y = fn(pts[i], pts[i + 1])
        out += [x, y]
    return out


def transform(d, g, fn, rs=1.0):
    """Apply point map `fn(x, y) -> (x, y)` to every part of group g (radii scaled by rs)."""
    for p in parts(d, g) + on(d, g):
        t = p['t']
        if t in ('e', 'spot'):
            p['x'], p['y'] = fn(p['x'], p['y'])
            p['rx'] = p.get('rx', 2) * rs
            p['ry'] = p.get('ry', p.get('rx', 2)) * rs
        elif t == 'c':
            p['x1'], p['y1'] = fn(p['x1'], p['y1'])
            p['x2'], p['y2'] = fn(p['x2'], p['y2'])
            p['r1'] = p.get('r1', 2) * rs
            if p.get('r2') is not None:
                p['r2'] = p['r2'] * rs
        elif 'pts' in p:
            p['pts'] = _pts_map(p['pts'], fn)
            if t in ('l', 'stripe'):
                p['w'] = p.get('w', 2) * rs
                if p.get('w2') is not None:
                    p['w2'] = p['w2'] * rs
        elif t in ('eye', 'mouth', 'shine'):
            p['x'], p['y'] = fn(p['x'], p['y'])


def shift(d, g, dx=0.0, dy=0.0):
    transform(d, g, lambda x, y: (x + dx, y + dy))


def scale(d, g, s=1.0, sx=None, sy=None, about=None):
    """Scale group g by s (or sx, sy) about a point (default: its bbox centre)."""
    ps = parts(d, g)
    if about is None:
        xs, ys = _bbox_pts(ps)
        about = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    ax, ay = about
    fx = s if sx is None else sx
    fy = s if sy is None else sy
    transform(d, g, lambda x, y: (ax + (x - ax) * fx, ay + (y - ay) * fy), rs=(fx + fy) / 2)


def _bbox_pts(ps):
    xs, ys = [], []
    for p in ps:
        t = p['t']
        if t in ('e', 'spot'):
            xs += [p['x'] - p['rx'], p['x'] + p['rx']]
            ys += [p['y'] - p['ry'], p['y'] + p['ry']]
        elif t == 'c':
            xs += [p['x1'], p['x2']]
            ys += [p['y1'], p['y2']]
        elif 'pts' in p:
            xs += p['pts'][0::2]
            ys += p['pts'][1::2]
    return xs or [0], ys or [0]


def thick(d, g, f):
    """Multiply the cross-section of tubes / strokes / plates in group g (capsule radii, stroke widths)."""
    for p in parts(d, g):
        if p['t'] == 'c':
            p['r1'] = p.get('r1', 2) * f
            if p.get('r2') is not None:
                p['r2'] = p['r2'] * f
        elif p['t'] == 'l':
            p['w'] = p.get('w', 2) * f
            if p.get('w2') is not None:
                p['w2'] = p['w2'] * f
        elif p['t'] == 'p':
            p['T'] = p.get('T', 0) and p['T'] * f or 0
            if not p['T']:
                del p['T']
        elif p['t'] == 'e':
            p['rd'] = p.get('rd', 0) and p['rd'] * f or 0
            if not p['rd']:
                del p['rd']


def dup(d, g, new, dx=0.0, dy=0.0, dz=0.0, mirror_about=None):
    """Copy group g as `new` (e.g. the far-side limb), offset in x/y and paint depth; optionally mirror x."""
    out = []
    for p in parts(d, g) + on(d, g):
        q = copy.deepcopy(p)
        if q.get('g') == g:
            q['g'] = new
        if q.get('on') == g:
            q['on'] = new
        out.append(q)
    for q in out:
        tmp = {'parts': [q]}
        if mirror_about is not None:
            m = mirror_about
            fn = lambda x, y, m=m: (2 * m - x + dx, y + dy)  # noqa: E731
        else:
            fn = lambda x, y: (x + dx, y + dy)  # noqa: E731
        _apply_pt(q, fn)
        if 'z' in q or dz:
            q['z'] = q.get('z', 0) + dz
    for q in out:
        d['parts'].append(q)
    return out


def _apply_pt(p, fn):
    t = p['t']
    if t in ('e', 'spot', 'eye', 'mouth', 'shine'):
        p['x'], p['y'] = fn(p['x'], p['y'])
        if 'rot' in p:
            pass
    elif t == 'c':
        p['x1'], p['y1'] = fn(p['x1'], p['y1'])
        p['x2'], p['y2'] = fn(p['x2'], p['y2'])
    elif 'pts' in p:
        p['pts'] = _pts_map(p['pts'], fn)


def set_color(d, g, c):
    for p in parts(d, g):
        p['c'] = c

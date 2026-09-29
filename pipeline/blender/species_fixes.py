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
    look = look or {}
    _generic(d, look)
    fn = FIXES.get(name)
    if fn is not None:
        fn(d, look)
    pal = (look or {}).get('pal')
    if pal:
        d.setdefault('pal', {}).update(pal)
    return d


def _generic(d, look):
    """Rules driven by the researched body plan (species_looks.json `shape`) before the per-species fix runs."""
    shape = look.get('shape')
    if shape == 'bird':                       # spindly stick legs read badly in 3D
        for g in {p.get('g') for p in d['parts'] if p.get('g')}:
            if g.lower().startswith('leg'):
                thick(d, g, 1.35)


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


# ============================================================================ fixes
@fix('SQUIRTLE', 'WARTORTLE', 'BLASTOISE')
def turtles(d, look):
    """The sprite shows the plastron head-on with the shell behind; in 3D the shell must sit on the BACK
    (flatter, pushed away from the viewer) and the belly is a proper torso, not a ball of shell."""
    for p in parts(d, 'shell'):
        p['rd'] = 0.66 * p['rx']
        p['d'] = 0.28 * p['rx']


@fix('WEEDLE')
def weedle(d, look):
    # the three pairs of little feet floated below the body: make them part of the segment above them
    for f, s in (('f1', 's3'), ('f2', 's4'), ('f3', 's2')):
        for p in parts(d, f):
            p['g'] = s
            p['y'] -= 2.0
            p['rx'], p['ry'] = 2.0, 2.2


@fix('KABUTO')
def kabuto(d, look):
    # legs were four hairlines detached from the shell: thicker, and merged with the shell group
    for g in ('l1', 'l2', 'l3', 'l4'):
        for p in parts(d, g):
            p['g'] = 'shell'
            p['w'] = 3.2
            p['w2'] = 2.2
            p['z'] = -0.5


@fix('POLIWAG')
def poliwag(d, look):
    # the flat five-sided fin looked like a paper flag: a curled, tapering tail
    drop(d, 'tail')
    add(d, Stroke('tail', [42, 50, 49, 47, 55, 43, 58, 40, 57, 37], 7.5, 'fin', z=-2, w2=2.2))


@fix('STARYU')
def staryu(d, look):
    for p in parts(d, 'star'):
        p['T'] = 3.6


@fix('STARMIE')
def starmie(d, look):
    for g, T in (('back', 3.4), ('front', 3.6), ('ring', 4.2)):
        for p in parts(d, g):
            p['T'] = T


@fix('EEVEE', 'FLAREON', 'JOLTEON', 'VAPOREON')
def eeveelutions(d, look):
    # the neck ruff / frill is fluff, not a flat sheet
    for g in ('collar', 'frill', 'mane'):
        for p in parts(d, g):
            if p['t'] == 'p':
                p['T'] = 3.0


@fix('GYARADOS')
def gyarados(d, look):
    # give the open mouth a real interior so it is not see-through from the side
    add(d, E('mouthin', 12, 25, 8.5, 4.8, 'mouth', z=1.6, rd=5.0))


@fix('CHARIZARD')
def charizard(d, look):
    for p in parts(d, 'body'):
        if p['t'] == 'c':                      # the neck
            p['r1'] = 7.6
            p['r2'] = 5.6
    scale(d, 'head', 1.14, about=(22, 16))
    for g in ('wingL', 'wingR'):
        for p in parts(d, g):
            p['T'] = 2.0
    charmander_line(d, look)


@fix('BLASTOISE')
def blastoise(d, look):
    turtles(d, look)
    scale(d, 'head', 1.14, about=(23, 30))
    for g in ('armF', 'armB'):
        thick(d, g, 1.15)
    for g in ('canL', 'canR'):
        thick(d, g, 1.18)


@fix('HITMONLEE')
def hitmonlee(d, look):
    # the sprite has no head shape (the eyes sit on the torso): add one and lift the face onto it
    for g in ('eyeL', 'eyeLi', 'eyeR', 'eyeRi'):
        shift(d, g, 0, -4.5)
    for p in d['parts']:
        if p['t'] == 'eye':
            p['y'] -= 4.5
    add(d, E('head', 37.5, 14.5, 9.6, 8.6, 'body', z=2))


@fix('JYNX')
def jynx(d, look):
    # a tall paper slab of hair -> a proper mane: a thick back mass, two long side locks, a fringe cap
    drop(d, 'hairBk')
    drop(d, 'bangs')
    add(d, E('hairBk', 32, 33, 13.5, 24.5, 'hair', z=-3, rd=6.0), at=0)
    add(d, Cap('lockL', 21, 17, 15.5, 52, 4.6, 3.6, 'hair', z=1.6))
    add(d, Cap('lockR', 43, 17, 48.5, 52, 4.6, 3.6, 'hair', z=1.6))
    add(d, E('bangs', 31, 11.8, 11.6, 6.2, 'hair', z=2.6, rd=8.5))
    add(d, Spot('bangs', 36, 10, 1.0, 5.0, 'hairD'))


def _recentre_face(d, dx, features_only=True, groups=()):
    """The sprite shows a 3/4 turn; the battle camera sees the front, so slide the face toward the
    middle of the body (eyes, mouth, listed face groups)."""
    for p in d['parts']:
        if p['t'] in ('eye', 'mouth', 'shine'):
            p['x'] += dx
    for g in groups:
        shift(d, g, dx, 0)


@fix('JIGGLYPUFF')
def jigglypuff(d, look):
    for p in d['parts']:
        if p['t'] == 'eye':
            p['x'] = 27.6 if p['x'] < 30 else 38.0
            p['look'] = [-0.25, 0]
        elif p['t'] == 'mouth':
            p['x'] = 32.9
    shift(d, 'curl', 5.2, 0)
    scale(d, 'curl', 1.25, about=(30, 33))


@fix('WIGGLYTUFF')
def wigglytuff(d, look):
    for p in d['parts']:
        if p['t'] == 'eye':
            p['x'] = 28.0 if p['x'] < 27 else 37.8
            p['look'] = [-0.25, 0]
        elif p['t'] == 'mouth':
            p['x'] = 32.9


@fix('EEVEE')
def eevee(d, look):
    eeveelutions(d, look)
    # tall, pointed, leaf-shaped ears instead of two slanted bars
    for p in parts(d, 'earF'):
        if p['t'] == 'p':
            p['pts'] = [15.5, 29, 12.6, 18, 9.0, 6.2, 15.5, 11.2, 21.5, 16.5, 27.5, 24]
    for p in parts(d, 'earB'):
        if p['t'] == 'p':
            p['pts'] = [27, 25, 30.5, 14, 37.5, 4.6, 39.5, 12.5, 37.6, 20.5, 35.5, 27.5]


def claws(d, groups, n=3, length=2.6, r=0.95, color='#f4efe0', z=None):
    """Small tapered claws / toes fanned out from the tip of each limb group's last capsule."""
    for g in groups:
        caps = [p for p in parts(d, g) if p['t'] == 'c']
        if not caps:
            continue
        c = caps[-1]
        x1, y1, x2, y2 = c['x1'], c['y1'], c['x2'], c['y2']
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        px, py = -uy, ux
        rr = c.get('r2') if c.get('r2') is not None else c.get('r1', 2)
        for i in range(n):
            f = (i - (n - 1) / 2.0)
            sx = x2 + px * f * rr * 0.55 - ux * 0.4
            sy = y2 + py * f * rr * 0.55 - uy * 0.4
            ex = x2 + px * f * rr * 0.9 + ux * length
            ey = y2 + py * f * rr * 0.9 + uy * length
            add(d, Cap(g, sx, sy, ex, ey, r, 0.35, color, z=c.get('z', 0) + 0.01, d1=f * 0.5, d2=f * 1.3))


@fix('CHARMANDER', 'CHARMELEON')
def charmander_line(d, look):
    claws(d, [g for g in ('armF', 'armB', 'legL', 'legR') if parts(d, g)], n=3, length=2.4, r=0.85)


@fix('BULBASAUR', 'IVYSAUR', 'VENUSAUR')
def bulbasaur_line(d, look):
    claws(d, [g for g in ('legF', 'legF2', 'legB', 'legB2') if parts(d, g)], n=3, length=2.0, r=0.8)


@fix('DRAGONITE')
def dragonite(d, look):
    claws(d, [g for g in ('armF', 'legF', 'legB') if parts(d, g)], n=3, length=2.4, r=0.85)


@fix('NINETALES')
def ninetales(d, look):
    for i in range(9):
        thick(d, 'nt%d' % i, 1.35)


@fix('VULPIX')
def vulpix(d, look):
    for i in range(1, 7):
        thick(d, 't%d' % i, 1.3)


@fix('GENGAR')
def gengar(d, look):
    # squat spiky ball -> a ball with proper legs and feet, and hands that grip
    for g in ('legF', 'legB'):
        thick(d, g, 1.1)
        c = [p for p in parts(d, g) if p['t'] == 'c'][0]
        add(d, E(g, c['x2'] - 0.5, 58.2, 5.8, 2.6, 'body', z=c.get('z', 0)))
    thick(d, 'armF', 1.25)
    thick(d, 'armB', 1.25)
    claws(d, ['armF'], n=3, length=2.2, r=0.9, color='#8a70bc')


@fix('ALAKAZAM', 'KADABRA')
def alakazam(d, look):
    # the long moustache is cream-white and fluffy, not two sticks of fur
    for g in ('must', 'must2'):
        for p in parts(d, g):
            p['c'] = '#f6efdc'
            p['w'] = 3.8
            p['w2'] = 2.0


@fix('SHELLDER')
def shellder(d, look):
    # the dark face is a real bulge (not a decal on the shell) with proper big eyes
    for p in parts(d, 'body'):
        p['solid'] = True
        p['rd'] = 5.2
        p['rx'], p['ry'] = 9.5, 6.6
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 2.7
            p['sclera'] = True
            p['style'] = 'round'
            p['iris'] = '#3aa0c0'
            p['x'] += 0.5
            p['y'] += 0.3

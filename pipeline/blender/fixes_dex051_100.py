"""Hand-tuned per-species fixes for Pokedex #051-100.  Register with @fix('NAME'); see species_fixes.py for the API."""
import math

from species_fixes import *  # noqa: F401,F403  (fix, E, Cap, Poly, Stroke, Spot, add, drop, mod, thick, scale, shift, dup, claws ...)


# ============================================================================ helpers (this module)
def Eye(x, y, s=2.4, style=None, iris=None, look=None, flip=False, sclera=None, wide=None, **kw):
    p = {'t': 'eye', 'x': x, 'y': y, 's': s}
    if style:
        p['style'] = style
    if iris:
        p['iris'] = iris
    if look is not None:
        p['look'] = look
    if flip:
        p['flip'] = True
    if sclera is not None:
        p['sclera'] = sclera
    if wide is not None:
        p['wide'] = wide
    p.update(kw)
    return p


def Mouth(x, y, w=2.5, style='smile', c=None, **kw):
    p = {'t': 'mouth', 'x': x, 'y': y, 'w': w, 'style': style}
    if c:
        p['c'] = c
    p.update(kw)
    return p


def Ink(pts, w=0.9, c='#1b1a2e', z=9, **kw):
    """A painted (texture-only) face line."""
    p = {'t': 'l', 'pts': list(pts), 'w': w, 'c': c, 'flat': True, 'line': False, 'face': True, 'z': z,
         'g': kw.pop('g', 'ink')}
    p.update(kw)
    return p


def keep_features(d):
    return [p for p in d['parts'] if p['t'] in ('eye', 'mouth', 'shine')]


def SolidE(g, x, y, rx, ry, c, z=0, rd=None, **kw):
    """Ellipsoid that keeps its volume (never flattened into a decal on the group under it)."""
    kw['solid'] = True
    if rd is not None:
        kw['rd'] = rd
    return E(g, x, y, rx, ry, c, z=z, **kw)


def Hand(g, x, y, r, c, ang, n=3, spread=70.0, fl=0.95, fr=0.30, z=0, tip=None, pad=None, **kw):
    """A palm (ellipsoid) with `n` finger/claw capsules fanned around direction `ang` (degrees, sprite space,
    0 = +x, 90 = down)."""
    out = [SolidE(g, x, y, r, r * 0.92, c, z=z, **kw)]
    for i in range(n):
        f = 0.0 if n == 1 else (i / (n - 1.0) - 0.5)
        a = math.radians(ang + spread * f)
        sx, sy = x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.55
        ex, ey = x + math.cos(a) * r * (1.0 + fl), y + math.sin(a) * r * (1.0 + fl)
        out.append(Cap(g, sx, sy, ex, ey, r * fr, r * fr * 0.72, tip or c, z=z + 0.01, d1=f * r * 0.5, d2=f * r * 0.9))
    return out


def Foot(g, x, y, rx, ry, c, dirx=-1, n=3, tl=0.8, tr=0.24, z=0, tip=None, **kw):
    """Foot ellipsoid with `n` toes pointing along dirx (+-1)."""
    out = [SolidE(g, x, y, rx, ry, c, z=z, **kw)]
    for i in range(n):
        f = 0.0 if n == 1 else (i / (n - 1.0) - 0.5)
        sx, sy = x + dirx * rx * 0.55, y + f * ry * 1.0 + ry * 0.1
        ex, ey = x + dirx * rx * (1.0 + tl * 0.5), y + f * ry * 1.5 + ry * 0.25
        out.append(Cap(g, sx, sy, ex, ey, ry * tr * 2.0, ry * tr * 1.5, tip or c, z=z + 0.01, d1=f * ry * 0.6, d2=f * ry * 1.3))
    return out


def Tufts(g, base, c, z=0.0, n=5, length=6.0, width=2.6, dirv=(0, -1), **kw):
    """Row of pointed fur tufts along a polyline `base` [(x, y) ...] pointing along dirv (unit-ish)."""
    out = []
    m = len(base)
    for i in range(n):
        t = i / (n - 1.0) if n > 1 else 0.5
        k = t * (m - 1)
        j = min(int(k), m - 2)
        u = k - j
        x = base[j][0] + (base[j + 1][0] - base[j][0]) * u
        y = base[j][1] + (base[j + 1][1] - base[j][1]) * u
        L = length * (0.8 + 0.4 * ((i * 7) % 5) / 4.0)
        tx, ty = dirv
        px, py = -ty, tx
        out.append(Poly(g, [x - px * width, y - py * width, x + tx * L + px * 0.3, y + ty * L + py * 0.3,
                            x + px * width, y + py * width], c, z=z + 0.01 * i, **kw))
    return out


def _pop_ellipsoid(d, g, which=-1):
    es = [p for p in d['parts'] if p.get('g') == g and p['t'] == 'e']
    if not es:
        return None
    e = es[which]
    d['parts'].remove(e)
    return e


def retoe(d, g, dirx=-1, n=3, grow=1.0, tl=0.8, tr=0.24, tip=None, name=None):
    """Replace the foot ellipsoid of group g with a foot + toes."""
    e = _pop_ellipsoid(d, g)
    if e is None:
        return
    d['parts'] += Foot(name or g, e['x'], e['y'], e['rx'] * grow, e['ry'] * grow, e['c'], dirx=dirx, n=n, tl=tl, tr=tr,
                       z=e.get('z', 0), tip=tip)


def refinger(d, g, ang, n=3, spread=70.0, grow=1.0, fl=0.95, fr=0.30, tip=None, name=None):
    """Replace the hand / fist ellipsoid of group g with a palm + fingers fanned around `ang`."""
    e = _pop_ellipsoid(d, g)
    if e is None:
        return
    r = (e['rx'] + e['ry']) * 0.5 * grow
    d['parts'] += Hand(name or g, e['x'], e['y'], r, e['c'], ang, n=n, spread=spread, fl=fl, fr=fr,
                       z=e.get('z', 0), tip=tip)


def recolor(d, g, c, only=None):
    for p in parts(d, g):
        if only is None or p.get('c') == only:
            p['c'] = c


def Flame(g, x, y, ang, L, w, c, z=0.0, curl=0.25, thick_=None, **kw):
    """One teardrop flame tongue rooted at (x, y), pointing along `ang` degrees (0 = +x, -90 = up), length L,
    base half-width w, tip curling sideways by `curl` * L."""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    loc = [(0, -w), (0.32 * L, -w * 0.95), (0.7 * L, -w * 0.45 + curl * L * 0.35), (L, curl * L),
           (0.72 * L, w * 0.45 + curl * L * 0.3), (0.3 * L, w * 0.95), (0, w)]
    pts = []
    for u, v in loc:
        pts += [x + ux * u + vx * v, y + uy * u + vy * v]
    return Poly(g, pts, c, z=z, T=(thick_ if thick_ is not None else max(1.0, w * 0.6)), **kw)


def FlameCluster(g, base, angs, L, w, c, z=0.0, curl=0.25, jitter=0.25, **kw):
    """Flame tongues rooted at successive `base` points with directions `angs` (lists of equal length)."""
    out = []
    for i, ((x, y), a) in enumerate(zip(base, angs)):
        k = 1.0 + jitter * (((i * 5) % 3) - 1)
        cu = curl * (1 if i % 2 == 0 else -0.6)
        out.append(Flame(g, x, y, a, L * k, w * (0.85 + 0.3 * (i % 2)), c, z=z + 0.01 * i, curl=cu, **kw))
    return out


# ============================================================================ #51 DUGTRIO
@fix('DUGTRIO')
def dugtrio(d, look):
    d['pal'].update({'body': '#b57843', 'nose': '#f2809a', 'dirt': '#8a6440', 'rock': '#a8988a'})
    P = []
    heads = [('dL', 16.5, 30, 52, 8.4), ('body', 33, 20, 52, 8.8), ('dR', 49.5, 30, 52, 8.4)]
    for n, x, ytop, ybot, r in heads:
        P.append(Cap(n, x, ytop + r, x, ybot, r, r * 0.98, 'body', z=0.5 if n != 'body' else 0,
                     cd=-1.5))
    for n, x, ytop, ybot, r in heads:
        ny = ytop + r * 1.7
        P.append(SolidE('n' + n[-1].upper(), x, ny, 4.3, 3.3, 'nose', z=1, rd=3.6, gloss=True, face=True))
    P += [E('dirt', 33, 55.5, 27, 5.2, 'dirt', z=2, rd=8.5), E('dirt', 12, 55, 8, 4, 'dirt', z=2.2),
          E('dirt', 55, 55, 8, 4, 'dirt', z=2.2), E('dirt', 33, 53.6, 20, 3.6, 'dirt', z=2.3, rd=9),
          E('rk1', 6, 58, 2.4, 1.8, 'rock', z=2.5), E('rk2', 60, 58, 2, 1.6, 'rock', z=2.5)]
    for n, x, ytop, ybot, r in heads:
        ny = ytop + r * 1.7
        P.append(Eye(x - 4.3, ny - 6.2, 2.0, sclera=False, look=[0, 0]))
        P.append(Eye(x + 4.3, ny - 6.2, 2.0, sclera=False, look=[0, 0]))
    d['parts'] = P


# ============================================================================ #56-57 MANKEY / PRIMEAPE
@fix('MANKEY')
def mankey(d, look):
    d['pal'].update({'body': '#f0e2c4', 'brown': '#a0744c', 'nose': '#f7b9b0', 'inner': '#eab8a4', 'fur2': '#d8c49e'})
    P = []
    P += [Stroke('tail', [42, 53, 47, 54, 52, 50, 53.5, 44, 51, 39.5], 2.6, 'body', z=-3, w2=1.7),
          E('tail', 50.5, 38.8, 2.5, 2.3, 'brown', z=-3)]
    # far arm (raised fist), far leg
    P += [Cap('armB', 41, 43, 46.5, 41, 2.6, 2.3, 'body', z=-2), Cap('armB', 46.5, 41, 48.5, 35.5, 2.3, 2.3, 'body', z=-2)]
    P += Hand('fistB', 48.8, 33.2, 3.2, 'brown', -80, n=3, spread=60, z=-1.9)
    P += [Cap('legB', 40, 52, 42, 56.5, 3.0, 2.6, 'body', z=-2)]
    P += Foot('footB', 43.5, 58.4, 4.4, 2.1, 'brown', dirx=-1, z=-1.9)
    # torso
    P += [E('body', 36, 46.5, 9.4, 9.8, 'body')]
    # near leg, near arm
    P += [Cap('legF', 32, 52, 29, 56.5, 3.4, 2.8, 'body', z=1.5)]
    P += Foot('footF', 27.6, 58.5, 4.8, 2.3, 'brown', dirx=-1, z=1.6)
    P += [Cap('armF', 30.5, 43, 24.5, 47.5, 2.9, 2.5, 'body', z=2), Cap('armF', 24.5, 47.5, 20, 43.5, 2.5, 2.6, 'body', z=2)]
    P += Hand('fist', 18, 41.7, 3.4, 'brown', 200, n=3, spread=60, z=2.2)
    # head + face
    P += [E('head', 28, 32.5, 11.2, 10, 'body', z=3)]
    P += [Poly('earF', [19.5, 27.5, 16.5, 19.5, 25.5, 24], 'body', z=3.2, T=2.0),
          Poly('earB', [35, 24, 40.5, 19, 38.5, 30], 'body', z=2.6, T=2.0)]
    P += [Poly('earFi', [20.7, 26, 18.2, 21, 24, 24.2], 'inner', z=3.25, T=1.2)]
    P += Tufts('tuft', [(23.5, 23.5), (29, 21.5), (34.5, 24)], 'body', z=3.1, n=3, length=3.8, width=2.6, T=1.8)
    P += [SolidE('nose', 20.2, 37.8, 4.9, 3.7, 'nose', z=3.5, rd=3.3, face=True)]
    P += [E('nost', 18.6, 37.8, 0.8, 1.05, '#6a3a38', z=3.6, face=True, line=False, flat=True),
          E('nost', 21.8, 37.8, 0.8, 1.05, '#6a3a38', z=3.6, face=True, line=False, flat=True)]
    P += [Eye(23.6, 31.6, 2.5, 'angry', iris='#c03030', look=[-1, 0.2]),
          Eye(31.6, 31.2, 2.5, 'angry', iris='#c03030', look=[-1, 0.2], flip=True),
          Mouth(24.0, 43.4, 2.4, 'smile')]
    d['parts'] = P


@fix('PRIMEAPE')
def primeape(d, look):
    d['pal'].update({'body': '#f0e2c4', 'brown': '#9c6e46', 'nose': '#f4a8a0', 'cuff': '#a4a8ba', 'inner': '#eab8a4',
                     'fur2': '#d8c49e'})
    P = []
    # far side
    P += [Cap('armB', 43, 35, 50, 30.5, 3.9, 3.4, 'body', z=-2), Cap('armB', 50, 30.5, 52.5, 23, 3.4, 3.3, 'body', z=-2),
          Cap('cuffB', 51.6, 26.6, 52.3, 24.8, 4.0, 4.0, 'cuff', z=-1.9)]
    P += Hand('fistB', 53, 20.3, 4.6, 'brown', -85, n=3, spread=60, z=-1.8)
    P += [Cap('legB', 41, 49, 44, 55, 4.4, 3.8, 'body', z=-2), Cap('cuffB2', 44.2, 55, 44.4, 56.3, 4.1, 4.1, 'cuff', z=-1.9)]
    P += Foot('footB', 45.6, 58.6, 5.4, 2.4, 'brown', dirx=-1, z=-1.8)
    # torso: broad chest, narrow waist
    P += [E('body', 36, 41.5, 12.6, 13.8, 'body')]
    # near leg, arm
    P += [Cap('legF', 31, 49, 27, 55, 4.8, 3.9, 'body', z=1.5), Cap('cuffF2', 26.8, 55.2, 26.4, 56.4, 4.2, 4.2, 'cuff', z=1.55)]
    P += Foot('footF', 23.6, 58.6, 6.0, 2.6, 'brown', dirx=-1, z=1.6)
    P += [Cap('armF', 28, 33, 20, 39, 4.3, 3.7, 'body', z=2), Cap('armF', 20, 39, 14.5, 35, 3.7, 3.7, 'body', z=2),
          Cap('cuffF', 16.6, 36.6, 15.2, 35.6, 4.2, 4.2, 'cuff', z=2.1)]
    P += Hand('fist', 12, 33.2, 4.8, 'brown', 205, n=3, spread=60, z=2.2)
    # head
    P += [E('head', 27, 25, 11.8, 10.4, 'body', z=3)]
    P += [Poly('earF', [17.8, 21, 14.5, 12.5, 24, 16], 'body', z=3.2, T=2.2),
          Poly('earB', [35, 16, 41, 11.5, 38, 24], 'body', z=2.6, T=2.2),
          Poly('earFi', [18.9, 19.2, 16.6, 14.6, 22, 16.6], 'inner', z=3.25, T=1.2)]
    P += Tufts('tuft', [(21, 17), (27.5, 14.6), (34, 17.5)], 'body', z=3.1, n=3, length=4.4, width=2.8, T=1.8)
    # spiky fur ring round the neck / shoulders
    P += [SolidE('nose', 19.5, 31.0, 5.2, 3.9, 'nose', z=3.5, rd=3.4, face=True)]
    P += [E('nost', 17.8, 31.0, 0.85, 1.1, '#6a3a38', z=3.6, face=True, line=False, flat=True),
          E('nost', 21.3, 31.0, 0.85, 1.1, '#6a3a38', z=3.6, face=True, line=False, flat=True)]
    P += [Eye(21.6, 24.3, 2.7, 'angry', iris='#c83030', look=[-1, 0.2]),
          Eye(30.4, 23.9, 2.7, 'angry', iris='#c83030', look=[-1, 0.2], flip=True),
          Mouth(23.5, 36.6, 3.0, 'smile')]
    d['parts'] = P


# ============================================================================ #52-53 MEOWTH / PERSIAN
@fix('MEOWTH')
def meowth(d, look):
    d['pal'].update({'brown': '#8a5a34', 'body': '#f4e4b0'})
    for p in d['parts']:
        if p.get('g') in ('earB', 'earF'):
            if p['c'] == 'body':
                p['c'] = 'brown'
                p['T'] = 2.4
            elif p['c'] == 'inner':
                p['c'] = '#f2b8a8'
                p['T'] = 1.4
    mod(d, 'tail', w=3.0, w2=2.4)
    scale(d, 'head', 1.08, about=(27.7, 32.4))
    retoe(d, 'legF', dirx=-1, n=3, tip='#f0e0b0')
    retoe(d, 'legB', dirx=-1, n=3, tip='#f0e0b0')
    add(d, Cap('armF', 22.5, 47.9, 20.8, 49.6, 1.6, 1.6, 'body', z=2))
    for a, (x, y) in (('armF', (20.4, 49.9)), ('armB', (42.0, 48.4))):
        d['parts'] += Hand(a, x, y, 1.9, 'body', 120 if a == 'armF' else 60, n=3, spread=60, fl=0.7, z=2 if a == 'armF' else -1)
    # nose (pink triangle) so the face reads from the front
    add(d, SolidE('nose', 19.4, 33.5, 1.4, 1.1, '#e88a90', z=4, rd=1.4, face=True))


@fix('PERSIAN')
def persian(d, look):
    d['pal'].update({'inner': '#3a3242', 'body': '#f4e6bc', 'paw': '#ecd8a4'})
    for p in d['parts']:
        if p.get('g') in ('earB', 'earF'):
            if p['c'] == 'body':
                p['c'] = 'inner'
                p['T'] = 2.4
            elif p['c'] == 'inner':
                p['c'] = '#f0b8a8'
                p['T'] = 1.4
    mod(d, 'tail', w=3.8, w2=2.6)
    for g in ('legF1', 'legF2'):
        retoe(d, g, dirx=-1, n=3, tip='#f4e6bc')
    for g in ('legB1', 'legB2'):
        c = [p for p in parts(d, g) if p['t'] == 'c'][-1]
        d['parts'] += Foot(g, c['x2'] - 0.6, 58.4, 3.3, 1.7, 'paw', dirx=-1, z=c.get('z', 0))
    mod(d, 'gem', solid=True, rd=2.4)
    scale(d, 'head', 1.06, about=(19.9, 29.6))
    # the neck: thicker so the head does not look stuck on
    thick(d, 'neck', 1.12)


# ============================================================================ #54-55 PSYDUCK / GOLDUCK
@fix('PSYDUCK')
def psyduck(d, look):
    d['pal'].update({'body': '#f8d850'})
    retoe(d, 'footL', dirx=-1, n=3, tl=0.6, tr=0.28)
    retoe(d, 'footR', dirx=-1, n=3, tl=0.6, tr=0.28)
    d['parts'] += Hand('armF', 25.6, 35.4, 2.7, 'body', -110, n=3, spread=50, fl=0.8, z=3)
    d['parts'] += Hand('armB', 41.6, 33.2, 2.5, 'body', -80, n=3, spread=50, fl=0.8, z=-1)
    mod(d, 'tail', solid=True)
    scale(d, 'head', 1.06, about=(31.1, 31.5))
    # beak nostrils
    add(d, E('nost', 15.5, 33.6, 0.7, 0.55, '#c8b070', z=3, face=True, flat=True, line=False))


@fix('GOLDUCK')
def golduck(d, look):
    mod(d, 'gem', solid=True, rd=2.6)
    for g in ('handF', 'handB'):
        mod(d, g, T=1.5)
    for g in ('footF', 'footB'):
        mod(d, g, T=1.6)
    mod(d, 'tail', T=2.2)
    mod(d, 'crest', T=2.0)
    thick(d, 'legF', 1.1)
    thick(d, 'legB', 1.1)


# ============================================================================ #58-59 GROWLITHE / ARCANINE
@fix('GROWLITHE')
def growlithe(d, look):
    scale(d, 'head', 1.12, about=(20, 37))
    mod(d, 'earF', T=2.8)
    mod(d, 'earB', T=2.8)
    for p in parts(d, 'tuft'):
        p['pts'] = [18.5, 30.5, 22, 27, 26.5, 29.5, 31, 28, 34.5, 33, 33.5, 39.5, 30, 43, 25.5, 42, 21, 38.5]
        p['T'] = 3.4
        p['z'] = 1.9
    thick(d, 'tail', 1.15)
    for g, (x, y) in (('legF1', (29.4, 58.3)), ('legF2', (46.6, 58.3)), ('legB1', (27.4, 58.3)), ('legB2', (44.4, 58.3))):
        z = parts(d, g)[0].get('z', 0)
        d['parts'] += Foot(g, x, y, 3.1, 1.6, 'body', dirx=-1, n=3, tl=0.6, tip='cream', z=z)
    mod(d, 'nose', solid=True, rd=1.6, rx=1.9, ry=1.6)
    add(d, E('chestF', 24, 47, 5.2, 5.6, 'cream', z=0.6, solid=True, rd=4.0))
    d['parts'] += Tufts('chestF', [(21, 43), (23, 47), (26, 51)], 'cream', z=0.7, n=3, length=3.6, width=2.0, dirv=(-1, 0.4), T=1.4)


@fix('ARCANINE')
def arcanine(d, look):
    for g in ('legF1', 'legF2', 'legB1', 'legB2'):
        retoe(d, g, dirx=-1, n=3, tl=0.7, tip='cream')
    mod(d, 'mane', T=3.0)
    mod(d, 'tuft', T=2.6)
    for g in ('fluffF1', 'fluffF2'):
        mod(d, g, T=1.8)
    mod(d, 'earF', T=2.6)
    mod(d, 'earB', T=2.6)
    scale(d, 'head', 1.08, about=(16, 22))
    mod(d, 'nose', solid=True, rd=1.8, rx=1.9, ry=1.6)
    thick(d, 'tail', 1.15)
    scale(d, 'mane', 1.18, about=(24, 33))
    for g in ('legF1', 'legF2', 'legB1', 'legB2'):
        thick(d, g, 1.12)


# ============================================================================ #60-62 POLIWAG line
@fix('POLIWAG')
def poliwag(d, look):
    drop(d, 'tail')
    add(d, Stroke('tail', [40, 47, 47, 45, 54, 42, 58, 38, 57, 33.5], 8.0, 'fin', z=-2, w2=2.4), at=0)
    retoe(d, 'footL', dirx=-1, n=3, tl=0.55, tr=0.3)
    retoe(d, 'footR', dirx=-1, n=3, tl=0.55, tr=0.3)
    mod(d, 'lip', solid=True, rd=2.0)
    scale(d, 'body', 1.0)


@fix('POLIWHIRL')
def poliwhirl(d, look):
    retoe(d, 'legF', dirx=-1, n=3, tl=0.55, tr=0.25)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.55, tr=0.25)
    d['parts'] += [Mouth(29.5, 31.5, 6.5, 'smile')]
    thick(d, 'armF', 1.15)
    thick(d, 'armB', 1.15)


@fix('POLIWRATH')
def poliwrath(d, look):
    retoe(d, 'legF', dirx=-1, n=3, tl=0.55, tr=0.25)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.55, tr=0.25)
    d['parts'] += [Mouth(28.5, 32.5, 7.5, 'smile')]
    d['parts'] += [Ink([21.5, 21.6, 24.5, 22.6], w=1.0, g='brow'), Ink([34.5, 21.2, 37.5, 22.2], w=1.0, g='brow')]
    thick(d, 'armF', 1.1)


# ============================================================================ #63-65 ABRA line
@fix('ABRA')
def abra(d, look):
    d['pal'].update({'fur': '#e6bd4a', 'armor': '#8f5c30'})
    mod(d, 'earB', T=2.4)
    for p in d['parts']:
        if p.get('g') == 'head' and p['t'] == 'p':
            p['T'] = 2.4
    # ears taller
    for p in d['parts']:
        if p.get('g') == 'earB':
            p['pts'] = [34, 27.5, 40.5, 10.5, 41.5, 31.5]
        if p.get('g') == 'head' and p['t'] == 'p':
            p['pts'] = [22.5, 29.5, 14.5, 10.5, 29.7, 25.5]
    retoe(d, 'legF', dirx=-1, n=3, tl=0.6, tr=0.24)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.6, tr=0.24)
    refinger(d, 'armF', 150, n=3, spread=60, fl=0.7)
    thick(d, 'tail', 1.1)
    add(d, E('snout', 20.5, 36.0, 3.6, 2.8, 'fur', z=4.2, solid=True, rd=2.6))
    add(d, E('nose', 18.6, 35.4, 1.1, 0.9, '#3a2a2a', z=4.3, face=True))


def _psychic_hands(d, hands, ang):
    for g, a in hands:
        if parts(d, g):
            refinger(d, g, a, n=3, spread=55, fl=0.7)


def _spoon_bowl(d, g):
    for p in parts(d, g):
        if p['t'] == 'e':
            p['rd'] = 0.9
            p['rx'] = 3.0
            p['ry'] = 4.2


@fix('KADABRA')
def kadabra(d, look):
    alakazam(d, look)
    d['pal'].update({'fur': '#eec04a', 'armor': '#8f5c30'})
    _psychic_hands(d, (('armF', 190), ('armB', 20)), 0)
    _spoon_bowl(d, 'spoon')
    retoe(d, 'legF', dirx=-1, n=3, tl=0.6, tr=0.22)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.6, tr=0.22)
    mod(d, 'earB', T=2.4)
    for p in d['parts']:
        if p.get('g') == 'head' and p['t'] == 'p':
            p['T'] = 2.4
    mod(d, 'star', T=1.2)
    thick(d, 'tail', 1.12)


@fix('ALAKAZAM')
def alakazam_fix(d, look):
    alakazam(d, look)
    d['pal'].update({'fur': '#e8bc48', 'armor': '#8f5c30'})
    _psychic_hands(d, (('armF', 190), ('armB', 20)), 0)
    _spoon_bowl(d, 'spoon')
    _spoon_bowl(d, 'spoonB')
    retoe(d, 'legF', dirx=-1, n=2, tl=0.6, tr=0.3)
    retoe(d, 'legB', dirx=-1, n=2, tl=0.6, tr=0.3)
    mod(d, 'earB', T=2.4)
    for p in d['parts']:
        if p.get('g') == 'head' and p['t'] == 'p':
            p['T'] = 2.4
    # cream neck ruff
    add(d, E('ruff', 33, 22.5, 8.2, 3.2, '#f6efdc', z=6.5, solid=True, rd=5.2))
    thick(d, 'must', 1.2)
    thick(d, 'must2', 1.2)


# ============================================================================ #66-68 MACHOP line
def _fists(d, spec, n=3, fr=0.3):
    for g, ang in spec:
        refinger(d, g, ang, n=n, spread=55, fl=0.7, fr=fr)


@fix('MACHOP')
def machop(d, look):
    d['pal'].update({'skin': '#94a8c8', 'lip': '#f0dcc4', 'belt': '#2c2c3c', 'buckle': '#e8c040'})
    _fists(d, (('fist', 205), ('fistB', -80)))
    retoe(d, 'legF', dirx=-1, n=3, tl=0.6, tr=0.26)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.6, tr=0.26)
    thick(d, 'armF', 1.12)
    thick(d, 'armB', 1.12)
    thick(d, 'legF', 1.08)
    thick(d, 'legB', 1.08)
    for g in ('crest', 'crest2', 'crest3'):
        recolor(d, g, '#b8907c')
    add(d, E('ear', 21.8, 31, 2.0, 2.6, 'skin', z=1.8, solid=True, rd=1.6))
    add(d, E('ear', 39.5, 30.2, 2.0, 2.6, 'skin', z=1.8, solid=True, rd=1.6))
    mod(d, 'crest', T=1.8)
    scale(d, 'head', 1.06, about=(30, 32))


def _muscle_body(d, y=45.0):
    """Championship belt: a black waist band with a gold buckle (replaces the ragged sprite briefs)."""
    d['pal'].update({'brief': '#2c2c3c', 'buckle': '#ecc23c'})
    for g in ('brief', 'belt', 'buckle'):
        drop(d, g)
    d['parts'] += [SolidE('belt', 35, y, 10.9, 4.0, 'brief', z=0.7, rd=9.2),
                   SolidE('buckle', 29.4, y + 0.3, 3.5, 3.3, 'buckle', z=0.8, rd=1.9)]


@fix('MACHOKE')
def machoke(d, look):
    d['pal'].update({'skin': '#a8a4c8', 'vein': '#d0505a', 'belt': '#3c3c54', 'buckle': '#e8c040'})
    _muscle_body(d)
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 2.3
    _fists(d, (('fist', 170), ('fistB', 10)), n=3, fr=0.32)
    retoe(d, 'legF', dirx=-1, n=3, tl=0.6, tr=0.24)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.6, tr=0.24)
    # pecs / delts read as muscle
    d['parts'] += [E('body', 29.5, 31.5, 6.0, 5.0, 'skin', z=0.2), E('body', 40.5, 31.5, 6.0, 5.0, 'skin', z=0.2)]
    for g in ('armF', 'armB'):
        thick(d, g, 1.1)
    for g in ('legF', 'legB'):
        thick(d, g, 1.08)
    add(d, E('ear', 22, 19.8, 1.9, 2.5, 'skin', z=1.8, solid=True, rd=1.6))
    add(d, E('ear', 38.5, 19.2, 1.9, 2.5, 'skin', z=1.8, solid=True, rd=1.6))


@fix('MACHAMP')
def machamp(d, look):
    d['pal'].update({'skin': '#90a4c2', 'belt': '#e8c040'})
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 2.0
    _muscle_body(d)
    _fists(d, (('fistFT', -95), ('fistBT', -85), ('fistFL', 180), ('fistBL', 0)), n=3, fr=0.32)
    retoe(d, 'legF', dirx=-1, n=3, tl=0.6, tr=0.24)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.6, tr=0.24)
    d['parts'] += [E('body', 29, 30.5, 6.5, 5.5, 'skin', z=0.2), E('body', 41.5, 30.5, 6.5, 5.5, 'skin', z=0.2)]
    for g in ('armFT', 'armFL', 'armBT', 'armBL'):
        thick(d, g, 1.1)
    add(d, E('ear', 23.3, 19.5, 1.8, 2.4, 'skin', z=7.2, solid=True, rd=1.5))
    add(d, E('ear', 39.3, 18.8, 1.8, 2.4, 'skin', z=7.2, solid=True, rd=1.5))


# ============================================================================ #69-71 BELLSPROUT line
@fix('BELLSPROUT')
def bellsprout(d, look):
    d['pal'].update({'head': '#f4e878', 'stem': '#7cb84c', 'leaf': '#5cac42'})
    # leaf "arms" sprout right under the bell, drooping, and are real leaves (thick, pointed, with a midrib)
    drop(d, 'leafF')
    drop(d, 'leafB')
    add(d, Poly('leafF', [31.4, 37.5, 26, 33.5, 15, 34.5, 10.5, 41, 21, 41, 28.5, 42.5], 'leaf', z=1, T=1.7))
    add(d, Poly('leafB', [31.6, 37, 37, 33, 47, 34, 51.5, 41, 41, 41, 34, 42], 'leaf', z=-1, T=1.7))
    # thicker stem + root feet
    thick(d, 'stem', 1.25)
    thick(d, 'root', 1.4)
    thick(d, 'root2', 1.4)
    # bigger bell with a flared, pink-rimmed opening
    scale(d, 'head', 1.12, about=(30, 24))
    mod(d, 'lip', solid=True, rd=3.2, rx=4.4, ry=3.4)
    add(d, E('lip', 26.8, 27.6, 5.5, 4.2, 'lip', rot=-35, z=2.6, solid=True, rd=4.0))
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 1.9


@fix('WEEPINBELL')
def weepinbell(d, look):
    d['pal'].update({'body': '#f0d95c', 'lip': '#f08fa0'})
    mod(d, 'lip', solid=True, rd=5.5, rx=11.5, ry=6.8)
    for g in ('leafF', 'leafB'):
        mod(d, g, T=1.8)
    thick(d, 'stem', 1.2)
    # vine tip leaf
    add(d, Poly('stem', [42.5, 13.5, 47, 9.5, 51.5, 12, 47.5, 16], 'leaf', z=-1, T=1.2))
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 2.4


@fix('VICTREEBEL')
def victreebel(d, look):
    d['pal'].update({'body': '#cad85c', 'lip': '#ec8aa0'})
    mod(d, 'lip', solid=True, rd=7.5, rx=13.5, ry=8.0)
    for g in ('tooth', 'tooth2'):
        mod(d, g, T=1.4)
    for g in ('leafF', 'leafB', 'vleaf'):
        mod(d, g, T=1.9)
    thick(d, 'vine', 1.2)
    scale(d, 'body', 1.0)
    for p in parts(d, 'body'):
        if p['t'] == 'e' and p['ry'] == 16:
            p['ry'] = 17.5
            p['rx'] = 13.2


# ============================================================================ #72-73 TENTACOOL / TENTACRUEL
@fix('TENTACOOL')
def tentacool(d, look):
    d['pal'].update({'dome': '#9fd2f4', 'body': '#3568bc', 'orb': '#e83446', 'tent': '#7fa8e0'})
    P = [
        Stroke('tentB', [36.5, 43, 40.5, 49, 37.5, 54.5, 41.5, 59.5], 3.2, 'tent', z=-1.5, w2=1.5),
        Stroke('tentB2', [33.5, 43.5, 34, 49.5, 36.5, 55], 2.4, 'tent', z=-1.6, w2=1.2),
        E('body', 32, 40.6, 13, 5.2, 'body', rd=10.5),
        E('dome', 32, 29.5, 15, 11.6, 'dome', z=1, gloss=True),
        E('orbF', 24.0, 25.4, 4.2, 3.9, 'orb', z=2, gloss=True, face=True),
        E('orbB', 40.4, 24.8, 4.0, 3.7, 'orb', z=2, gloss=True, face=True),
        SolidE('orbC', 32, 43.2, 2.0, 1.7, 'orb', z=2, gloss=True, rd=1.6),
        Stroke('tentF', [27.5, 43.8, 23.5, 49.5, 27, 55, 22, 59.5], 3.4, 'tent', z=2, w2=1.5),
        Stroke('tentF2', [30.5, 44.3, 30, 50, 27.5, 55.5], 2.4, 'tent', z=2.1, w2=1.2),
        Eye(26.4, 40.6, 2.1, iris='#d02838', look=[0, 0]), Eye(37.6, 40.6, 2.1, iris='#d02838', look=[0, 0]),
    ]
    d['parts'] = P


@fix('TENTACRUEL')
def tentacruel(d, look):
    d['pal'].update({'dome': '#86c4f2'})
    for g in ('orbB', 'orbF', 'orbC'):
        mod(d, g, solid=True)
    mod(d, 'orbF', rd=4.4)
    mod(d, 'orbB', rd=4.0)
    for g in ('t1', 't2', 't3', 't4', 't5'):
        thick(d, g, 1.25)
    d['parts'] += [Stroke('t6', [35, 42, 39, 50, 36, 56, 41, 61], 2.6, 'tent', z=-1, w2=1.2),
                   Stroke('t7', [22, 42, 14, 50, 15, 57, 9, 61], 2.8, 'tent', z=2, w2=1.3),
                   Stroke('t8', [31, 43, 33, 51, 29, 57], 2.4, 'tent', z=1, w2=1.2)]
    mod(d, 'beak', T=1.8)


# ============================================================================ #74-76 GEODUDE line
@fix('GEODUDE')
def geodude(d, look):
    _fists(d, (('fistF', 200), ('fistB', -20)), n=3, fr=0.42)
    mod(d, 'browL', T=2.6)
    mod(d, 'browR', T=2.6)
    thick(d, 'armF', 1.08)
    thick(d, 'armB', 1.08)


@fix('GRAVELER')
def graveler(d, look):
    _fists(d, (('fistFT', -100), ('fistBT', -80), ('fistFL', 180), ('fistBL', 0)), n=3, fr=0.42)
    mod(d, 'brow', r1=2.4, r2=2.4)
    for g in ('armFT', 'armFL', 'armBT', 'armBL'):
        thick(d, g, 1.1)
    for g in ('legF', 'legB'):
        retoe(d, g, dirx=-1, n=3, tl=0.4, tr=0.3)


@fix('GOLEM')
def golem(d, look):
    d['parts'] = [p for p in d['parts'] if p['t'] not in ('eye', 'mouth', 'shine')]
    drop(d, 'head')
    drop(d, 'hole')
    d['parts'] += [SolidE('head', 17.6, 39.0, 10.8, 9.8, 'skin', z=3, rd=8.8, cd=-10),
                   SolidE('head', 10.6, 42.4, 6.2, 5.0, 'skin', z=3, rd=5.0),
                   Poly('tusk', [8.4, 44.6, 7.2, 48.6, 10.6, 45.6], '#f4ecd8', z=3.2, T=1.1),
                   Poly('tusk', [15.4, 45.4, 15.8, 49.4, 17.6, 45.4], '#f4ecd8', z=3.2, T=1.1),
                   Eye(14.4, 36.6, 2.6, 'angry', iris='#c03028', look=[-1, 0]),
                   Eye(22.4, 36.2, 2.6, 'angry', iris='#c03028', look=[-1, 0], flip=True),
                   Mouth(13.0, 43.4, 3.0, 'line')]
    retoe(d, 'legF', dirx=-1, n=3, tl=0.5, tr=0.3)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.5, tr=0.3)
    refinger(d, 'armF', 190, n=3, spread=50, fl=0.6, fr=0.35)
    refinger(d, 'armB', 10, n=3, spread=50, fl=0.6, fr=0.35)
    thick(d, 'armF', 1.1)
    thick(d, 'armB', 1.1)


# ============================================================================ #77-78 PONYTA / RAPIDASH
def _flame_pair(d, name_o, name_i, base, angs, L, w, zo, name_r=None, zr=None):
    d['parts'] += FlameCluster(name_o, base, angs, L, w, 'f2', z=zo, curl=0.28)
    d['parts'] += FlameCluster(name_i, base, [a + 4 for a in angs], L * 0.72, w * 0.6, 'f1', z=zo + 0.3, curl=0.28)


@fix('PONYTA')
def ponyta(d, look):
    d['pal'].update({'hoof': '#cbbfa6', 'coat': '#fbf1d6', 'f1': '#fbe25a', 'f2': '#f58a2a', 'f3': '#e63a20'})
    for g in ('tailO', 'tailI', 'maneO', 'maneI', 'fore'):
        drop(d, g)
    _flame_pair(d, 'tailO', 'tailI', [(45.5, 40), (45, 38), (44.4, 36.2), (43.6, 34.8), (46, 42)],
                [10, -22, -52, -84, 34], 13.5, 3.4, -2)
    mane_b = [(27, 23.4), (29.4, 26.2), (31.4, 29.0), (33.2, 31.8), (35.0, 34.6)]
    _flame_pair(d, 'maneO', 'maneI', mane_b, [-108, -82, -62, -50, -38], 11.5, 3.0, 1.5)
    d['parts'] += FlameCluster('fore', [(24.3, 22.7), (22.6, 23.6)], [-118, -150], 7.0, 2.1, 'f3', z=3.5, curl=0.3)
    # bright inner tail base
    for g in ('legFR', 'legBR', 'legFL', 'legBL'):
        thick(d, g, 1.12)
    mod(d, 'ear', T=1.9)
    mod(d, 'head', solid=True)
    add(d, E('nost', 15.6, 30.6, 0.55, 0.45, '#5a4a48', z=3.4, face=True, flat=True, line=False))
    scale(d, 'head', 1.08, about=(22, 29))


@fix('RAPIDASH')
def rapidash(d, look):
    d['pal'].update({'hoof': '#cbbfa6', 'coat': '#fbf1d6', 'f1': '#fbe25a', 'f2': '#f58a2a', 'f3': '#e63a20',
                     'horn': '#e8e8f0'})
    for g in ('tailO', 'tailI', 'maneO', 'maneI', 'fore', 'fl1', 'fl2', 'fl3', 'fl4', 'horn'):
        drop(d, g)
    _flame_pair(d, 'tailO', 'tailI', [(51, 34), (52, 37), (50.5, 32), (52, 40.5), (49.6, 30.5)],
                [-18, 8, -46, 30, -74], 19.0, 4.0, -2)
    _flame_pair(d, 'maneO', 'maneI', [(27.6, 13.4), (29.6, 17.6), (31.6, 22.4), (34.4, 27.6), (37.4, 31.6)],
                [-100, -78, -62, -46, -34], 14.5, 3.6, 1.5)
    d['parts'] += FlameCluster('fore', [(21.6, 10.4), (19.6, 11.2)], [-112, -144], 8.5, 2.5, 'f3', z=3.5, curl=0.3)
    for i, (x, y, z) in enumerate(((50.6, 53.2, -0.9), (34.4, 53.2, -0.9), (45, 53.6, 1.1), (25.8, 53.6, 1.1))):
        d['parts'] += FlameCluster('fl%d' % (i + 1), [(x - 1.6, y), (x, y), (x + 1.6, y)], [-140, -100, -60], 6.0, 1.7,
                                   'f2', z=z, curl=0.2)
    d['parts'].append(Cap('horn', 17.6, 10.8, 10.4, 1.4, 2.2, 0.4, 'horn', z=3.6, gloss=True))
    for g in ('legFR', 'legBR', 'legFL', 'legBL'):
        thick(d, g, 1.1)
    mod(d, 'ear', T=1.9)
    add(d, E('nost', 11.6, 22.2, 0.6, 0.5, '#5a4a48', z=3.4, face=True, flat=True, line=False))


# ============================================================================ #79-80 SLOWPOKE / SLOWBRO
@fix('SLOWPOKE')
def slowpoke(d, look):
    d['pal'].update({'skin': '#f4a4b8', 'muz': '#fae8cc', 'tip': '#fbf6f2'})
    thick(d, 'tail', 1.1)
    # snout: a real bulge, cream, with nostrils
    for p in parts(d, 'head'):
        if p['ry'] == 4.6:
            p['rx'], p['ry'] = 7.8, 5.0
    add(d, SolidE('muzzle', 15.2, 45.4, 6.2, 4.4, 'muz', z=1.5, rd=4.4))
    add(d, E('nost', 11.4, 43.8, 0.6, 0.8, '#b06a70', z=1.7, face=True, flat=True, line=False))
    add(d, E('nost', 12.6, 43.4, 0.6, 0.8, '#b06a70', z=1.7, face=True, flat=True, line=False))
    for g, dirx in (('legF', -1), ('legF2', -1), ('legB', -1)):
        c = [p for p in parts(d, g) if p['t'] == 'c'][-1]
        d['parts'] += Foot(g, c['x2'] - 0.3, 58.6, 3.6, 1.7, 'muz', dirx=-1, n=3, tl=0.5, z=c.get('z', 0))
    mod(d, 'earF', solid=True, rd=2.2)
    mod(d, 'earB', solid=True, rd=2.2)
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 3.0


def _slowbro_shell(d):
    for g in ('shellder', 'spk1', 'spk2', 'spk3'):
        drop(d, g)
    d['pal'].update({'shell': '#9a86c6', 'sp': '#6a5aa0', 'spike': '#f2eef6', 'mouthin': '#4a2a58'})
    cx, cy = 51, 46
    d['parts'] += [
        E('shellder', cx, cy - 3.6, 10.6, 7.2, 'shell', rot=8, z=-2.0, rd=8.5),
        E('shellder', cx + 0.6, cy + 4.6, 9.8, 5.6, 'shell', rot=8, z=-2.1, rd=8.0),
        Stroke('shellder', [cx - 8, cy - 8, cx - 2, cy - 9.8, cx + 6, cy - 9.2, cx + 12, cy - 4], 1.0, 'sp', z=-1.9,
               backOnly=False),
    ]
    for i, (x0, x1) in enumerate(((cx - 6, cx - 6.5), (cx - 1.5, cx - 1.5), (cx + 3.5, cx + 4.5), (cx + 8, cx + 9.5))):
        d['parts'].append(Stroke('shellder', [x0, cy - 9.6, x1, cy + 1.5], 1.0, 'sp', z=-1.9))
    # spikes: real cones
    d['parts'] += [Cap('spk1', cx - 4, cy - 8.5, cx - 6, cy - 16, 2.4, 0.3, 'spike', z=-2.2),
                   Cap('spk2', cx + 5, cy - 8.8, cx + 9.5, cy - 15, 2.4, 0.3, 'spike', z=-2.2),
                   Cap('spk3', cx + 10.5, cy - 2.5, cx + 17.5, cy - 5.5, 2.4, 0.3, 'spike', z=-2.2),
                   Cap('spk4', cx + 10.5, cy + 6, cx + 16.5, cy + 10.5, 2.2, 0.3, 'spike', z=-2.2)]


@fix('SLOWBRO')
def slowbro(d, look):
    d['pal'].update({'skin': '#f4a4b8', 'muz': '#fae8cc'})
    _slowbro_shell(d)
    mod(d, 'earF', solid=True, rd=2.2)
    mod(d, 'earB', solid=True, rd=2.2)
    retoe(d, 'legF', dirx=-1, n=3, tl=0.5, tr=0.3, tip='#fae8cc')
    retoe(d, 'legB', dirx=-1, n=3, tl=0.5, tr=0.3, tip='#fae8cc')
    add(d, SolidE('muzzle', 20.6, 28.6, 5.6, 4.0, 'muz', z=3.6, rd=3.8))
    d['parts'] += Hand('armF', 18, 44.8, 2.6, 'skin', 170, n=3, spread=50, fl=0.6, z=2)
    d['parts'] += Hand('armB', 45.5, 42.6, 2.4, 'skin', 20, n=3, spread=50, fl=0.6, z=-1)
    thick(d, 'armF', 1.1)
    thick(d, 'armB', 1.1)
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 3.0


# ============================================================================ #81-82 MAGNEMITE / MAGNETON
def _mag_unit(sfx, cx, cy, r, z, top_screw=True, bot_screws=True, eye_look=(-0.55, 0)):
    P = []
    w = 0.44 * r
    h = 0.56 * r
    for side, (c_top, c_bot) in (('L', ('blu', 'red')), ('R', ('red', 'blu'))):
        s = -1 if side == 'L' else 1
        xi = cx + s * 1.08 * r
        xo = cx + s * 1.98 * r
        xc = cx + s * 1.46 * r
        P.append(Stroke('mag' + side + sfx, [xo, cy - h, xc, cy - h, xi, cy - h * 0.6, xi, cy + h * 0.6, xc, cy + h, xo, cy + h],
                        w, 'steel', z=z - 0.2))
        for yy, cc in ((cy - h, c_top), (cy + h, c_bot)):
            P.append(Cap('tip' + side + sfx, cx + s * 2.34 * r, yy, cx + s * 1.86 * r, yy, 0.25 * r, 0.25 * r, cc, z=z - 0.1))
    P.append(E('ball' + sfx if sfx else 'ball', cx, cy, r, r, 'steel', z=z, gloss=True))
    P.append(Eye(cx - 0.12 * r, cy, 0.42 * r, look=list(eye_look)))
    sw = 0.14 * r
    if top_screw:
        P.append(Cap('scT' + sfx, cx, cy - 0.85 * r, cx, cy - 1.33 * r, sw, sw, 'screw', z=z - 0.4))
        P.append(E('scT' + sfx, cx, cy - 1.4 * r, 0.36 * r, 0.17 * r, 'screw', z=z - 0.4, solid=True, rd=0.36 * r))
    if bot_screws:
        for side in ('L', 'R'):
            s = -1 if side == 'L' else 1
            P.append(Cap('sc' + side + sfx, cx + s * 0.52 * r, cy + 0.85 * r, cx + s * 0.78 * r, cy + 1.32 * r, sw, sw, 'screw', z=z - 0.4))
            P.append(E('sc' + side + sfx, cx + s * 0.84 * r, cy + 1.4 * r, 0.32 * r, 0.16 * r, 'screw', z=z - 0.4, rot=-s * 25,
                       solid=True, rd=0.32 * r))
    return P


@fix('MAGNEMITE')
def magnemite(d, look):
    d['pal'].update({'steel': '#bcc4d0', 'screw': '#8e96a4'})
    d['parts'] = _mag_unit('', 32, 36, 9.6, 0)


@fix('MAGNETON')
def magneton(d, look):
    d['pal'].update({'steel': '#bcc4d0', 'screw': '#8e96a4'})
    P = []
    P += _mag_unit('a', 32, 21.5, 8.0, 0, top_screw=True, bot_screws=False)
    P += _mag_unit('b', 24, 36, 8.0, 0.2, top_screw=False, bot_screws=True)
    P += _mag_unit('c', 40, 36, 8.0, 0.4, top_screw=False, bot_screws=True)
    d['parts'] = P


# ============================================================================ #83-85 FARFETCHD / DODUO / DODRIO
@fix('FARFETCHD')
def farfetchd(d, look):
    d['pal'].update({'beak': '#f4b840'})
    # the leek is held UP in the near wing, in front of the body
    drop(d, 'leekW')
    drop(d, 'leekG')
    d['parts'] += [Cap('leekW', 39.5, 43, 46.5, 24, 1.9, 1.7, 'leekW', z=2.6),
                   Cap('leekG', 46.5, 24, 52.5, 10, 1.7, 1.5, 'leekG', z=2.6),
                   Poly('leekG', [52.5, 13, 47.5, 4, 53, 8, 55, 1.5, 56.5, 9.5, 61, 6, 55.5, 15], 'leekG', z=2.6, T=1.3)]
    mod(d, 'beak', solid=True, rd=2.6, ry=3.0)
    mod(d, 'wing', solid=True)
    mod(d, 'tail', T=2.0)
    for g in ('legF', 'legB'):
        thick(d, g, 1.15)
        retoe(d, g, dirx=-1, n=3, tl=0.5, tr=0.24, tip='beak')
    add(d, E('brow', 21.6, 22, 5.6, 1.6, 'brow', z=3.6, rot=-8, face=True, flat=True, line=False))


@fix('DODUO')
def doduo(d, look):
    d['pal'].update({'beak': '#f0cf9c', 'leg': '#e2bc8a'})
    for g in ('neckF', 'neckB'):
        thick(d, g, 1.2)
    for g in ('beakF', 'beakB'):
        mod(d, g, T=2.1)
    for g in ('legF', 'legB'):
        thick(d, g, 1.35)
    d['parts'] += [Poly('crestF', [17, 14, 15, 8, 20, 12.5, 23.5, 9.5, 22.5, 14.5], 'dk', z=2.2, T=1.2),
                   Poly('crestB', [38, 8.5, 36.5, 3.5, 41, 7, 44, 4.5, 43.5, 9], 'dk', z=-0.3, T=1.2),
                   Poly('tailD', [45, 38, 53, 34, 52, 40, 55, 44, 46, 44], 'dk', z=-2, T=1.8)]


@fix('DODRIO')
def dodrio(d, look):
    d['pal'].update({'beak': '#f0cf9c', 'leg': '#e2bc8a'})
    for g in ('neck1', 'neck2', 'neck3'):
        thick(d, g, 1.25)
    for g in ('beak1', 'beak2', 'beak3'):
        mod(d, g, T=2.2)
    for g in ('crest1', 'crest2', 'crest3'):
        mod(d, g, T=1.4)
    for g in ('legF', 'legB'):
        thick(d, g, 1.3)
    mod(d, 'tail', T=2.2)


# ============================================================================ #86-87 SEEL / DEWGONG
@fix('SEEL')
def seel(d, look):
    drop(d, 'tongue')
    drop(d, 'horn')
    d['parts'] += [Cap('horn', 21.6, 26.5, 20.2, 15.2, 2.6, 0.4, 'horn', z=1.5),
                   SolidE('nose', 9.8, 37.4, 2.0, 1.6, '#2c2834', z=3, rd=1.7, gloss=True)]
    for g in ('finB', 'finF', 'tail'):
        mod(d, g, T=2.2)
    thick(d, 'body', 1.0)
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 1.9
    add(d, Ink([9.6, 42.2, 12.5, 43.4, 15.2, 42.2], w=0.8, g='smile'))


@fix('DEWGONG')
def dewgong(d, look):
    drop(d, 'horn')
    d['parts'] += [Cap('horn', 18.4, 14.5, 14.6, 1.8, 2.8, 0.4, 'horn', z=1.5),
                   SolidE('nose', 6.4, 24.4, 2.0, 1.6, '#2c2834', z=3, rd=1.7, gloss=True)]
    for g in ('finB', 'finF', 'tail'):
        mod(d, g, T=2.4)
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 1.9


# ============================================================================ #88-89 GRIMER / MUK
def _drips(d, spec, g='body'):
    for x, y, L, r in spec:
        d['parts'].append(Cap(g, x, y, x, y + L, r, r * 0.55, 'goo', z=0.4))
        d['parts'].append(E(g, x, y + L + 0.6, r * 0.75, r * 0.85, 'goo', z=0.4))


@fix('GRIMER')
def grimer(d, look):
    d['pal'].update({'goo': '#a878c0', 'mouth': '#3a2040'})
    _drips(d, [(20.5, 46, 6.5, 2.0), (39.5, 47, 5.5, 2.2), (30.5, 52, 5.0, 1.6)])
    _drips(d, [(12.5, 33.5, 6, 1.9)], g='armF')
    _drips(d, [(49, 32, 5, 2.0)], g='armB')
    # lumpy crown
    d['parts'] += [E('body', 28, 29.6, 4.0, 3.4, 'goo', z=0.2), E('body', 36, 32, 3.4, 3.0, 'goo', z=0.2)]
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 2.6
    mod(d, 'mouth', solid=False)


@fix('MUK')
def muk(d, look):
    d['pal'].update({'goo': '#a070bc'})
    _drips(d, [(15, 46, 8, 2.6), (43, 48, 7, 2.8), (31, 55, 4.5, 2.0), (52, 51, 5, 2.2)])
    _drips(d, [(9, 22, 8, 2.4)], g='armF')
    _drips(d, [(54.5, 22, 7, 2.6)], g='armB')
    d['parts'] += [E('body', 25, 21.5, 5.0, 4.2, 'goo', z=0.2), E('body', 38, 22.5, 4.4, 3.8, 'goo', z=0.2),
                   E('body', 31.5, 19.5, 3.6, 3.2, 'goo', z=0.2)]
    for p in d['parts']:
        if p['t'] == 'eye':
            p['s'] = 3.0


# ============================================================================ #90-91 SHELLDER / CLOYSTER
def cone_spikes(d, g, center, base_scale=0.5, color=None, z=None, inset=2.5):
    """Turn flat triangular spike plates of group g into round cones rooted slightly inside the shell."""
    cx, cy = center
    new = []
    for p in list(parts(d, g)):
        if p['t'] != 'p' or len(p['pts']) != 6:
            continue
        P = [(p['pts'][i], p['pts'][i + 1]) for i in range(0, 6, 2)]
        tip = max(P, key=lambda q: math.hypot(q[0] - cx, q[1] - cy))
        o = [q for q in P if q is not tip]
        bx, by = (o[0][0] + o[1][0]) / 2, (o[0][1] + o[1][1]) / 2
        rad = math.hypot(o[0][0] - o[1][0], o[0][1] - o[1][1]) / 2 * base_scale * 2
        L = math.hypot(tip[0] - bx, tip[1] - by) or 1
        ux, uy = (tip[0] - bx) / L, (tip[1] - by) / L
        d['parts'].remove(p)
        new.append(Cap(g, bx - ux * inset, by - uy * inset, tip[0], tip[1], max(1.2, rad), 0.3, color or p['c'],
                       z=p.get('z', 0) if z is None else z))
    d['parts'] += new


@fix('SHELLDER')
def shellder(d, look):
    d['pal'].update({'shell': '#8a68c0', 'ridge': '#5c3c90', 'body': '#2c2638', 'tongue': '#f0708c'})
    P = [E('shellB', 36, 52, 15.5, 7, 'shell', rd=10.5),
         E('shellT', 41, 33.5, 15.2, 10.4, 'shell', z=1, rot=-16, rd=11.5),
         SolidE('body', 24.5, 44.8, 11.4, 8.0, 'body', z=1.5, rd=7.4, cd=-3)]
    for pts, g in (([22, 44, 30, 30], 'shellT'), ([29, 46, 36, 29], 'shellT'), ([37, 47, 42, 30], 'shellT'),
                   ([44, 46, 48, 33], 'shellT'), ([25, 54, 28, 50], 'shellB'), ([34, 56, 35, 51], 'shellB'),
                   ([43, 55, 42, 51], 'shellB')):
        P.append({'t': 'stripe', 'pts': pts, 'w': 1.3, 'c': 'ridge', 'on': g})
    P += [Stroke('tongue', [19.5, 49.4, 14.5, 52, 11, 51.5, 8.5, 55.5], 4.4, 'tongue', z=2, w2=2.8),
          Eye(20.4, 43.4, 3.1, iris='#3aa4c8', look=[-1, 0.1]),
          Eye(29.6, 43.4, 3.1, iris='#3aa4c8', look=[-1, 0.1])]
    d['parts'] = P


@fix('CLOYSTER')
def cloyster(d, look):
    cone_spikes(d, 'spk', (35, 37), base_scale=0.55, inset=3.0)
    d['pal'].update({'shell': '#7c6cae', 'spike': '#e6e0f2'})
    mod(d, 'horn', T=2.2)
    for g in ('eyeL', 'eyeR', 'eyeLi', 'eyeRi'):
        pass
    mod(d, 'shell', solid=True)


# ============================================================================ #92-94 GASTLY / HAUNTER / GENGAR
@fix('GASTLY')
def gastly(d, look):
    for p in parts(d, 'gas'):
        if p['t'] == 'l':
            p['w'] = p.get('w', 8) * 1.25
    mod(d, 'ball', solid=True)


@fix('HAUNTER')
def haunter(d, look):
    for p in parts(d, 'body'):
        if p['t'] == 'p':
            p['T'] = 2.6
    for g in ('handL', 'handR'):
        for p in parts(d, g):
            if p['t'] == 'p':
                p['T'] = 1.5
            elif p['t'] == 'e':
                p['solid'] = True
                p['rx'] *= 1.15
                p['ry'] *= 1.15
    mod(d, 'tongue', r1=3.4, r2=2.6)


@fix('GENGAR')
def gengar_fix(d, look):
    gengar(d, look)
    for p in parts(d, 'body'):
        if p['t'] == 'p':
            p['T'] = 2.8
    # toes on the feet
    for g in ('legF', 'legB'):
        es = [p for p in parts(d, g) if p['t'] == 'e']
        if es:
            e = es[-1]
            for i in range(3):
                f = i - 1
                d['parts'].append(Cap(g, e['x'] - 3.4, e['y'] + f * 1.4, e['x'] - 6.4, e['y'] + f * 1.9, 1.5, 0.9, 'body',
                                      z=e.get('z', 0) + 0.01, d1=f * 1.0, d2=f * 2.0))
    # fingers
    for p in list(parts(d, 'armF')):
        if p['t'] == 'p':
            d['parts'].remove(p)
    d['parts'] += Hand('armF', 9.8, 46.2, 2.9, 'body', 165, n=3, spread=60, fl=0.7, z=2.1)
    d['parts'] += Hand('armB', 55, 44.5, 2.7, 'body', 20, n=3, spread=60, fl=0.7, z=-1)
    mod(d, 'tail', r1=3.6, r2=1.2)


# ============================================================================ #95 ONIX
@fix('ONIX')
def onix(d, look):
    d['pal'].update({'rock': '#b8b8c2', 'crest': '#a0a0b0'})
    mod(d, 'crest', T=2.4)
    d['parts'] += [Cap('crest', 22.5, 16, 15.5, 8.5, 3.0, 0.4, 'crest', z=5.6), Cap('crest', 28, 14.5, 23, 6.2, 3.0, 0.4, 'crest', z=5.6),
                   Cap('crest', 33, 14, 30.5, 5.5, 2.6, 0.4, 'crest', z=5.6)]
    # bumpier boulders
    for i in (2, 3, 4, 5, 6):
        pass
    d['parts'] += [E('s2', 27.5, 26.5, 3.2, 3.0, 'rock', z=4.1), E('s3', 44.5, 36.5, 3.4, 3.2, 'rock', z=2.1),
                   E('s4', 21.5, 46, 3.6, 3.4, 'rock', z=3.1)]
    mod(d, 'head', solid=True)
    d['parts'].append(Ink([4.5, 28.6, 9.5, 29.4, 16, 28.4], w=0.9, c='#4a4a58', g='mouthline'))


# ============================================================================ #96-97 DROWZEE / HYPNO
@fix('DROWZEE')
def drowzee(d, look):
    d['pal'].update({'fur': '#f2cc48', 'brown': '#8e5c32'})
    refinger(d, 'handF', 185, n=3, spread=55, fl=0.6, fr=0.36)
    for p in d['parts']:
        if p.get('g') == 'handF' and p['t'] == 'c' and p['r1'] < 1.5:
            d['parts'].remove(p)
    retoe(d, 'legF', dirx=-1, n=3, tl=0.5, tr=0.26)
    retoe(d, 'legB', dirx=-1, n=3, tl=0.5, tr=0.26)
    mod(d, 'head', T=2.4) if False else None
    for p in d['parts']:
        if p.get('g') == 'head' and p['t'] == 'p':
            p['T'] = 2.2
    thick(d, 'nose', 1.15)
    # the brown lower body reads as trousers with a hem
    d['parts'].append(SolidE('nosetip', 13.6, 40.4, 3.7, 3.2, 'brown', z=3.2, rd=3.3))


@fix('HYPNO')
def hypno(d, look):
    d['pal'].update({'fur': '#f2cc48'})
    for p in d['parts']:
        if p.get('g') == 'head' and p['t'] == 'p':
            p['T'] = 2.2
        if p.get('g') == 'ruff' and p['t'] == 'p':
            p['T'] = 2.4
    mod(d, 'ruff', solid=True)
    d['parts'] += Hand('armF', 14.2, 42.2, 2.9, 'fur', 185, n=3, spread=55, fl=0.6, z=4.2)
    retoe(d, 'legF', dirx=-1, n=3, tl=0.5, tr=0.26) if any(p['t'] == 'e' for p in parts(d, 'legF')) else None
    for g in ('legF', 'legB'):
        c = [p for p in parts(d, g) if p['t'] == 'c'][-1]
        d['parts'] += Foot(g, c['x2'] - 1.2, 57.6, 5.2, 2.4, 'brown' if False else 'fur', dirx=-1, n=3, tl=0.5, tr=0.26,
                           z=c.get('z', 0))
    thick(d, 'nose', 1.15)


# ============================================================================ #98-100 KRABBY / KINGLER / VOLTORB
def _crab_common(d, claws, legs, T=2.6):
    for g in claws:
        for p in parts(d, g):
            if p['t'] == 'p':
                p['T'] = T
            elif p['t'] == 'e':
                p['solid'] = True
                p['rd'] = min(p['rx'], p['ry']) * 0.9
    for g in legs:
        thick(d, g, 1.3)
    for g in ('stalk', 'stalk2'):
        thick(d, g, 1.2)


@fix('KRABBY')
def krabby(d, look):
    d['pal'].update({'shell': '#e85a38'})
    _crab_common(d, ('clawF', 'clawB'), ('legF1', 'legF2', 'legB1', 'legB2', 'armF', 'armB'))
    d['parts'] += [Cap('legF3', 22, 49, 15, 54, 1.8, 1.3, 'shell', z=1), Cap('legB3', 46, 50, 53, 56, 1.8, 1.3, 'shell', z=-2)]
    # eyes sit on short stalks as black beads
    d['parts'] += [SolidE('stalk', 27, 33, 2.2, 2.2, '#1b1a2e', z=-0.9, rd=2.2),
                   SolidE('stalk2', 38, 33, 2.2, 2.2, '#1b1a2e', z=-0.9, rd=2.2)]
    d['parts'] = [p for p in d['parts'] if p['t'] != 'eye']


@fix('KINGLER')
def kingler(d, look):
    d['pal'].update({'shell': '#e25a3a'})
    _crab_common(d, ('clawF', 'clawB'), ('legF1', 'legF2', 'legB1', 'legB2', 'armF', 'armB'), T=3.4)
    for p in parts(d, 'body'):
        if p['t'] == 'p':
            p['T'] = 2.6
    d['parts'] += [Cap('legF3', 28, 50, 21, 56, 2.0, 1.4, 'shell', z=1), Cap('legB3', 52, 51, 58, 57, 2.0, 1.4, 'shell', z=-2)]
    d['parts'] += [SolidE('stalk', 32, 29.5, 2.4, 2.4, '#1b1a2e', z=-1.4, rd=2.4),
                   SolidE('stalk2', 41, 29.5, 2.4, 2.4, '#1b1a2e', z=-1.4, rd=2.4)]
    d['parts'] = [p for p in d['parts'] if p['t'] != 'eye']


@fix('VOLTORB')
def voltorb(d, look):
    d['pal'].update({'red': '#ea3a3a', 'white': '#f6f6f6'})
    mod(d, 'ball', rd=13.5)
    for p in d['parts']:
        if p['t'] == 'stripe':
            p['w'] = 2.4
            p['c'] = '#2a1820'


# --- END OF FIXES ---

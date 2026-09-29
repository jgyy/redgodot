"""Hand-tuned per-species fixes for Pokedex #001-050.  Register with @fix('NAME'); see species_fixes.py for the API.

Most species here are re-built as *front-facing* 3D characters (the battle camera turns them ~28 degrees toward
screen-left, so a symmetric front-facing body reads as a natural 3/4 view): explicit group depths (`cd`),
real hands / feet with toes, shells, ears, tails and flames modelled as volumes instead of the sprite's flat
silhouettes.  Sprite space: x right, y DOWN, ground ~ y 60; depth d < 0 is toward the viewer.
"""
import math

from species_fixes import *  # noqa: F401,F403  (fix, E, Cap, Poly, Stroke, Spot, add, drop, mod, thick, scale, shift, dup, claws ...)
import species_fixes as _SF

CLAW = '#f6f0dc'


# ============================================================================ helpers
def _tame(c, top=0xe8):
    """Near-white palette colours blow out under the cel shader's brightest ramp step (and its top-light gradient):
    keep the brightest channel <= `top` so creams and whites stay cream / white-ish instead of pure white."""
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    m = max(r, g, b)
    if m > top:
        k = top / float(m)
        r, g, b = int(r * k), int(g * k), int(b * k)
    return '#%02x%02x%02x' % (r, g, b)


def keep_features(d):
    """The face features (eyes, mouths, shines) of the definition, for a rebuild."""
    return [p for p in d['parts'] if p['t'] in ('eye', 'mouth', 'shine')]


def rebuild(d, parts, pal=None, features=None):
    """Replace the whole part list (keeping, unless `features` is given, the sprite's eyes / mouths)."""
    feats = keep_features(d) if features is None else features
    for p in list(parts) + list(feats):
        c = p.get('c')
        if isinstance(c, str) and len(c) == 7 and c[0] == '#':
            p['c'] = _tame(c)
    for p in parts:               # ellipsoid groups hidden inside others would otherwise be flattened into decals
        if p['t'] == 'e' and not p.get('face') and not p.get('frontOnly'):
            p.setdefault('solid', True)
    d['parts'] = list(parts) + list(feats)
    if pal:
        d.setdefault('pal', {}).update(pal)


def Eye(x, y, s=3.0, iris='#303030', look=(0, 0), **kw):
    p = {'t': 'eye', 'x': x, 'y': y, 's': s, 'iris': iris, 'look': list(look)}
    p.update(kw)
    return p


def Mouth(x, y, w=3, style='smile', **kw):
    p = {'t': 'mouth', 'x': x, 'y': y, 'w': w, 'style': style}
    p.update(kw)
    return p


def Stripe(on_g, pts, w, c, **kw):
    p = {'t': 'stripe', 'pts': list(pts), 'w': w, 'c': c, 'on': on_g}
    p.update(kw)
    return p


def toes(g, x, y, n=3, spread=2.7, r=1.5, dz=-6.0, c='skin', claw=CLAW, z=0.0, cd=None, rz=None):
    """A row of round toes (with tiny claws) for a front-facing foot: toes sit forward (toward the viewer)."""
    out = []
    for i in range(n):
        f = i - (n - 1) / 2.0
        tx = x + f * spread
        ty = y - abs(f) * 0.15
        out.append(E(g, tx, ty, r, r * 0.92, c, z=z, rd=rz or r * 1.15, d=dz - abs(f) * 0.3))
        if claw:
            out.append(Cap(g, tx, ty + 0.1, tx, ty + 0.35, r * 0.62, r * 0.2, claw, z=z + 0.02,
                           d1=dz - r * 0.6 - abs(f) * 0.3, d2=dz - r * 1.9 - abs(f) * 0.3))
    return out


def foot(g, x, y, c, w=5.0, ln=5.6, n=3, dz=-2.0, toe_r=1.5, spread=None, z=0.0, claw=CLAW):
    """Flat front-facing foot: a wide low pad plus `n` toes at the front edge.  (x, y) = ground contact centre."""
    spread = spread or (2 * w / (n + 0.6))
    out = [E(g, x, y - 1.7, w, 2.4, c, z=z, rd=ln, d=dz)]
    out += toes(g, x, y - 1.35, n=n, spread=spread, r=toe_r, dz=dz - ln * 0.72, c=c, claw=claw, z=z)
    return out


def hand(g, x, y, c, r=2.8, n=3, ang=0.0, fl=2.4, fr=0.95, dz=-1.5, z=0.0, claw=CLAW, spread=1.35):
    """Mitten hand at (x, y) with `n` short fingers pointing down (rotated by ang degrees) and slightly forward."""
    out = [E(g, x, y, r, r * 0.95, c, z=z, rd=r, d=dz)]
    a = math.radians(ang)
    ux, uy = math.sin(a), math.cos(a)
    px, py = uy, -ux
    for i in range(n):
        f = i - (n - 1) / 2.0
        sx, sy = x + px * f * spread * 0.9, y + py * f * spread * 0.9
        ex, ey = sx + ux * fl + px * f * 0.35, sy + uy * fl + py * f * 0.35
        out.append(Cap(g, sx, sy, ex, ey, fr, fr * 0.72, c, z=z + 0.01, d1=dz - 0.6, d2=dz - 1.0))
        if claw:
            out.append(Cap(g, ex, ey, ex + ux * 0.9, ey + uy * 0.9, fr * 0.55, 0.2, claw, z=z + 0.02,
                           d1=dz - 1.0, d2=dz - 1.2))
    return out


def scutes(g, cx, cy, rx, ry, c='#6a4220', w=1.2, back=True):
    """Hexagonal shell pattern (back layer only): a central hex, spokes to the rim and a border ring."""
    out = []
    hx, hy = rx * 0.42, ry * 0.36
    hexp = []
    for k in range(7):
        a = math.radians(60 * k + 30)
        hexp += [cx + hx * math.cos(a), cy + hy * math.sin(a) * 1.1]
    kw = {'backOnly': True} if back else {}
    out.append(Stripe(g, hexp, w, c, **kw))
    for k in range(6):
        a = math.radians(60 * k + 30)
        out.append(Stripe(g, [cx + hx * math.cos(a), cy + hy * 1.1 * math.sin(a),
                              cx + rx * 0.9 * math.cos(a), cy + ry * 0.9 * math.sin(a)], w, c, **kw))
    ring = []
    for k in range(25):
        a = math.radians(360.0 * k / 24)
        ring += [cx + rx * 0.9 * math.cos(a), cy + ry * 0.9 * math.sin(a)]
    out.append(Stripe(g, ring, w * 1.1, c, **kw))
    return out


def flame(g, x, y, h=12.0, r=4.2, c_out='#ff7a1c', c_in='#ffe24a', z=0.0, lean=0.0, tongues=True, dz=0.0):
    """A 3D tail flame: a swaying teardrop with two side licks and a bright yellow core.  (x, y) = base centre."""
    out = [Cap(g, x, y, x + lean * 0.4, y - h * 0.5, r, r * 0.86, c_out, z=z, d1=dz, d2=dz),
           Cap(g, x + lean * 0.4, y - h * 0.5, x + lean * 1.2, y - h, r * 0.86, 0.3, c_out, z=z, d1=dz, d2=dz)]
    if tongues:
        out.append(Cap(g, x - r * 0.4, y - h * 0.32, x - r * 1.35 + lean * 0.5, y - h * 0.78, r * 0.5, 0.25, c_out,
                       z=z + 0.05, d1=dz, d2=dz))
        out.append(Cap(g, x + r * 0.4, y - h * 0.32, x + r * 1.35 + lean * 0.5, y - h * 0.68, r * 0.5, 0.25, c_out,
                       z=z + 0.05, d1=dz, d2=dz))
    out.append(Cap(g, x, y - h * 0.02, x + lean * 0.35, y - h * 0.46, r * 0.68, r * 0.3, c_in, z=z + 0.3,
                   d1=dz - 2.2, d2=dz - 1.6))
    return out


# ============================================================================ starters: the turtles
def _turtle(d, look, size, sh_c='#b4763a', sh_dark='#6a4220', skin='#78c0e8', rimc='#f4ecd0', plasc='#f0dc9c'):
    """size: dict of proportions.  Front-facing upright turtle: belly + plastron in front, shell behind."""
    s = size
    bx, by = 32.0, s['by']
    parts = []
    # far-side arm, tail, shell (behind the body)
    parts.append(Stroke('tail', s['tail'], s['tail_w'], skin, z=-4, w2=s['tail_w2'], cd=8.0))
    parts.append(E('shell', bx, by - 1.0, s['shell_rx'], s['shell_ry'], sh_c, z=-2, rd=s['shell_rd'], d=0, cd=s['shell_cd'],
                   bz=3, solid=True))
    parts += scutes('shell', bx, by - 1.0, s['shell_rx'], s['shell_ry'], c=sh_dark)
    ring = []
    for k in range(29):
        a = math.radians(360.0 * k / 28)
        ring += [bx + s['shell_rx'] * 0.93 * math.cos(a), by - 1.0 + s['shell_ry'] * 0.93 * math.sin(a)]
    parts.append(Stripe('shell', ring, 2.4, rimc))
    parts.append(E('body', bx, by, s['bx'], s['by_r'], skin, z=0, rd=s['b_rd']))
    parts.append(E('plas', bx, by + 1.0, s['bx'] * 0.78, s['by_r'] * 0.8, plasc, face=True))
    for k in range(3):
        yy = by - s['by_r'] * 0.35 + k * s['by_r'] * 0.36
        parts.append(Stripe('plas', [bx - s['bx'] * 0.72, yy, bx, yy + 0.5, bx + s['bx'] * 0.72, yy], 0.9, '#b89860'))
    parts.append(Stripe('plas', [bx, by - s['by_r'] * 0.7, bx, by + s['by_r'] * 0.8], 0.9, '#b89860'))
    # legs with feet (wide feet, 3 toes)
    for side, g in ((-1, 'legL'), (1, 'legR')):
        lx = bx + side * s['leg_dx']
        ly = s['leg_y']
        parts.append(Cap(g, lx, ly, lx + side * 0.6, 55.5, s['leg_r'], s['leg_r'] * 0.9, skin, z=2, cd=s['leg_cd']))
        parts += foot(g, lx + side * 0.7, 60.0, skin, w=s['foot_w'], ln=s['foot_l'], dz=-1.0, toe_r=s['toe_r'], z=2.2)
    # arms with hands
    for side, g in ((-1, 'armL'), (1, 'armR')):
        sx = bx + side * (s['bx'] - 1.0)
        hx = bx + side * (s['bx'] + s['arm_out'])
        parts.append(Cap(g, sx, s['arm_y'], hx, s['arm_y'] + s['arm_l'], s['arm_r'], s['arm_r'] * 0.86, skin, z=3, cd=s['arm_cd']))
        parts += hand(g, hx + side * 0.2, s['arm_y'] + s['arm_l'] + 1.0, skin, r=s['arm_r'] * 0.95, ang=-side * 8, dz=0, z=3.1,
                      fl=2.3, fr=0.9)
    # head
    parts.append(E('head', bx, s['hy'], s['hrx'], s['hry'], skin, z=4, rd=s['hrd'], cd=s['head_cd']))
    return parts


@fix('SQUIRTLE')
def squirtle(d, look):
    size = dict(by=44.0, bx=12.0, by_r=13.4, b_rd=9.4, shell_rx=15.2, shell_ry=15.0, shell_rd=8.5, shell_cd=6.5,
                rim_rx=12.6, rim_ry=13.0, rim_rd=6.5, rim_cd=3.0,
                tail=[36, 53, 43, 55, 49.5, 51, 50, 45, 46.5, 42.5], tail_w=6.0, tail_w2=2.2,
                leg_dx=6.4, leg_y=52.5, leg_r=4.7, foot_w=4.6, foot_l=4.8, toe_r=1.45, leg_cd=0.0,
                arm_y=36.5, arm_l=6.0, arm_out=3.0, arm_r=3.0, arm_cd=-3.0,
                hy=22.0, hrx=11.6, hry=10.4, hrd=9.6, head_cd=-2.0)
    parts = _turtle(d, look, size)
    feats = [Eye(26.0, 22.6, 3.9, '#a84030', look=(0, 0.05)), Eye(38.0, 22.6, 3.9, '#a84030', look=(0, 0.05)),
             Mouth(32.0, 28.2, 2.4, 'smile')]
    rebuild(d, parts, features=feats)


def _cannon(g, x0, y0, d0, x1, y1, d1, r, c='#b8bcc8', dark='#666c7e'):
    """A shoulder cannon: silver barrel, dark mouth band, mount collar."""
    fx = lambda t: (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, d0 + (d1 - d0) * t)  # noqa: E731
    a, b, e = fx(0.0), fx(0.9), fx(1.0)
    return [Cap(g, a[0], a[1], b[0], b[1], r * 1.05, r, c, z=5, d1=a[2], d2=b[2], gloss=True),
            Cap(g, b[0], b[1], e[0], e[1], r * 1.14, r * 1.14, dark, z=5.1, d1=b[2], d2=e[2]),
            Cap(g, e[0], e[1], e[0], e[1] - 0.2, r * 0.75, r * 0.7, '#20222c', z=5.2, d1=e[2] - 0.2, d2=e[2] - 1.0)]


@fix('WARTORTLE')
def wartortle(d, look):
    size = dict(by=43.5, bx=12.6, by_r=13.8, b_rd=9.6, shell_rx=16.0, shell_ry=15.4, shell_rd=9.0, shell_cd=7.0,
                tail=[38, 52, 45, 54, 51, 49, 51, 42, 49, 37], tail_w=8.0, tail_w2=6.0,
                leg_dx=6.8, leg_y=52.5, leg_r=5.0, foot_w=5.0, foot_l=5.2, toe_r=1.5, leg_cd=0.0,
                arm_y=36.0, arm_l=6.6, arm_out=3.6, arm_r=3.2, arm_cd=-3.0,
                hy=21.5, hrx=11.4, hry=10.2, hrd=9.6, head_cd=-2.0)
    parts = _turtle(d, look, size, sh_c='#a86c3c', sh_dark='#5e3a1c', skin='#8aa4e8', rimc='#f4ecd0', plasc='#f0d890')
    fl, fld = '#e4eaf8', '#a4acdc'
    # fluffy white tail: bushy stroke with a feathery tip
    parts = [p for p in parts if p.get('g') != 'tail']
    parts.append(Stroke('tail', [37, 51, 44, 53, 50.5, 49, 51.5, 42, 49.5, 36.5], 9.0, fl, z=-4, w2=6.5, cd=8.0))
    parts.append(Stripe('tail', [39, 55, 46, 54, 52, 48, 53, 41], 1.0, fld))
    parts.append(Poly('tail', [47, 40, 46.5, 30, 50, 34, 52, 27, 54.5, 35, 57, 33, 55.5, 41], fl, z=-4, T=2.6, cd=8.0))
    parts.append(Stripe('tail', [50.5, 39, 51, 33], 0.9, fld))
    # furry fin ears
    for side, g in ((-1, 'earL'), (1, 'earR')):
        x0 = 32 + side * 9.6
        pts = [x0 - side * 1.6, 23.5, x0 + side * 4.5, 19.5, x0 + side * 8.0, 14.0, x0 + side * 5.2, 13.6,
               x0 + side * 11.0, 8.0, x0 + side * 6.0, 8.4, x0 + side * 9.2, 0.5, x0 + side * 3.0, 7.6,
               x0 - side * 0.3, 14.5]
        parts.append(Poly(g, pts, fl, z=1, T=3.2, cd=-1.0))
    feats = [Eye(26.6, 22.6, 3.4, '#6a3828', look=(0, 0.05), style='angry'),
             Eye(37.4, 22.6, 3.4, '#6a3828', look=(0, 0.05), style='angry', flip=True),
             Mouth(32.0, 28.4, 2.8, 'smile')]
    rebuild(d, parts, features=feats)


@fix('BLASTOISE')
def blastoise(d, look):
    size = dict(by=41.5, bx=14.4, by_r=15.6, b_rd=11.0, shell_rx=18.6, shell_ry=17.6, shell_rd=10.0, shell_cd=8.5,
                tail=[38, 56, 44, 57.5, 47, 54], tail_w=6.5, tail_w2=4.0,
                leg_dx=8.2, leg_y=52.0, leg_r=6.4, foot_w=6.2, foot_l=6.2, toe_r=1.8, leg_cd=0.0,
                arm_y=35.0, arm_l=7.0, arm_out=4.4, arm_r=4.4, arm_cd=-4.0,
                hy=20.0, hrx=10.2, hry=9.0, hrd=8.8, head_cd=-3.0)
    parts = _turtle(d, look, size, sh_c='#8a5a30', sh_dark='#4e3018', skin='#6890d8', rimc='#f2e8c4', plasc='#e8d890')
    # two shoulder cannons bursting out of the shell, pointing forward-outward
    for side, g in ((-1, 'canL'), (1, 'canR')):
        parts += _cannon(g, 32 + side * 9.0, 26.0, 9.0, 32 + side * 17.0, 20.0, -8.0, 3.6)
        parts.append(E(g + 'mt', 32 + side * 10.0, 27.0, 5.2, 4.2, '#6a4826', z=4, rd=5.0, cd=6.0))
    # ears: small pointed
    for side, g in ((-1, 'earL'), (1, 'earR')):
        x0 = 32 + side * 7.4
        parts.append(Poly(g, [x0 - side * 2, 14.5, x0 + side * 0.5, 7.6, x0 + side * 3.6, 14.2], '#6890d8', z=1, T=1.8, cd=-3.0))
    feats = [Eye(27.6, 21.6, 3.0, '#6a3828', look=(0, 0.05), style='angry'),
             Eye(36.4, 21.6, 3.0, '#6a3828', look=(0, 0.05), style='angry', flip=True),
             Mouth(32.0, 27.4, 3.4, 'smile')]
    rebuild(d, parts, features=feats)


# ============================================================================ generic builders
def limbs_biped(skin, bx=32.0, leg_dx=6.0, leg_y=52.0, leg_r=4.4, foot_w=4.4, foot_l=4.6, toe_r=1.4, n_toe=3,
                arm_sx=22.0, arm_y=36.0, arm_dx=-3.0, arm_l=8.0, arm_r=2.8, hand_r=2.5, n_fing=3, fl=2.4,
                arm_cd=-3.0, leg_cd=0.0, claw=CLAW, gnd=60.0, arm_ang=8):
    """Two legs with feet+toes and two arms with hands+fingers, front facing.  Groups legL/legR/armL/armR."""
    out = []
    for side, g in ((-1, 'legL'), (1, 'legR')):
        lx = bx + side * leg_dx
        out.append(Cap(g, lx, leg_y, lx + side * 0.6, gnd - 4.5, leg_r, leg_r * 0.9, skin, z=2, cd=leg_cd))
        out += foot(g, lx + side * 0.9, gnd, skin, w=foot_w, ln=foot_l, n=n_toe, dz=-1.0, toe_r=toe_r, z=2.2, claw=claw)
    for side, g in ((-1, 'armL'), (1, 'armR')):
        sx = bx + side * (bx - arm_sx) if False else bx + side * abs(arm_sx - bx)
        hx = sx + side * (-arm_dx)
        hy = arm_y + arm_l
        out.append(Cap(g, sx, arm_y, hx, hy, arm_r, arm_r * 0.85, skin, z=3, cd=arm_cd))
        out += hand(g, hx + side * 0.3, hy + 0.8, skin, r=hand_r, n=n_fing, ang=-side * arm_ang, dz=0, z=3.1, fl=fl,
                    fr=0.85, claw=claw)
    return out


def batwing(g, side, S, W, tips, membrane, bone, back, cd=5.0, z=-1.0, bone_r=1.7, T=1.1, scallop=0.32):
    """Bat-style wing in the sprite plane: leading-edge arm S->W, fingers W->tips, scalloped membrane between them
    and back to the body point `back`.  `side` only names things; the geometry is given in absolute coords."""
    out = []
    poly = [S[0], S[1], W[0], W[1]]
    for i, t in enumerate(tips):
        poly += [t[0], t[1]]
        if i + 1 < len(tips):
            n = tips[i + 1]
            mx, my = (t[0] + n[0]) / 2.0, (t[1] + n[1]) / 2.0
            poly += [mx + (W[0] - mx) * scallop, my + (W[1] - my) * scallop]
    poly += [back[0], back[1]]
    out.append(Poly(g, poly, membrane, z=z, T=T, cd=cd))
    out.append(Cap(g, S[0], S[1], W[0], W[1], bone_r * 1.25, bone_r, bone, z=z + 0.5, cd=cd))
    for i, t in enumerate(tips):
        r = bone_r * (0.75 if i else 0.85)
        out.append(Cap(g, W[0], W[1], t[0], t[1], r, r * 0.35, bone, z=z + 0.5, cd=cd))
    return out


@fix('CHARMANDER')
def charmander(d, look):
    sk, bel = '#f08430', '#f8e09a'
    parts = []
    parts.append(Stroke('tail', [36, 54, 44, 56, 51, 52, 53.5, 45, 53.5, 39], 6.6, sk, z=-4, w2=3.4, cd=7.0))
    parts += flame('fl', 53.5, 40.5, h=15.0, r=4.6, z=-3.5, lean=1.4)
    parts.append(E('body', 32, 43.5, 9.8, 12.2, sk, z=0, rd=8.4))
    parts.append(E('belly', 32, 46, 6.6, 9.2, bel, face=True))
    for k in range(4):
        parts.append(Stripe('belly', [26.5, 40 + k * 3.4, 32, 41 + k * 3.4, 37.5, 40 + k * 3.4], 0.7, '#e2c078'))
    parts += limbs_biped(sk, leg_dx=5.6, leg_y=52.5, leg_r=4.5, foot_w=4.2, foot_l=4.6, toe_r=1.35,
                         arm_sx=23.0, arm_y=36.5, arm_dx=-1.5, arm_l=7.0, arm_r=2.6, hand_r=2.3, fl=2.4)
    parts.append(E('head', 32, 22.5, 11.4, 10.0, sk, z=4, rd=9.4, cd=-2.0))
    parts.append(E('head', 32, 27.6, 6.4, 4.8, sk, z=4, rd=6.6, d=-4.6))
    parts.append(Spot('head', 30.0, 26.2, 0.55, 0.45, '#8a3a18', face=True))
    parts.append(Spot('head', 34.0, 26.2, 0.55, 0.45, '#8a3a18', face=True))
    feats = [Eye(26.8, 21.4, 3.4, '#304888', look=(0, 0.05)), Eye(37.2, 21.4, 3.4, '#304888', look=(0, 0.05)),
             Mouth(32.0, 30.4, 3.2, 'smile')]
    rebuild(d, parts, pal={'skin': sk, 'belly': bel}, features=feats)


@fix('CHARMELEON')
def charmeleon(d, look):
    sk, bel = '#e4503a', '#f6dc98'
    parts = []
    parts.append(Stroke('tail', [36, 53, 45, 56, 53, 52, 56, 44, 55.5, 36], 7.2, sk, z=-4, w2=3.4, cd=7.0))
    parts += flame('fl', 55.5, 38.0, h=16.0, r=4.8, z=-3.5, lean=1.0)
    parts.append(E('body', 32, 42.5, 9.8, 13.0, sk, z=0, rd=8.6))
    parts.append(E('belly', 32, 45, 6.4, 10.4, bel, face=True))
    for k in range(4):
        parts.append(Stripe('belly', [26.8, 38 + k * 3.8, 32, 39 + k * 3.8, 37.2, 38 + k * 3.8], 0.7, '#dcb872'))
    parts += limbs_biped(sk, leg_dx=5.8, leg_y=52.0, leg_r=4.5, foot_w=4.4, foot_l=4.8, toe_r=1.4,
                         arm_sx=22.6, arm_y=35.5, arm_dx=-1.8, arm_l=8.0, arm_r=2.6, hand_r=2.3, fl=3.0)
    parts.append(E('head', 32, 20.5, 10.4, 9.0, sk, z=4, rd=8.8, cd=-2.0))
    parts.append(E('head', 32, 25.4, 5.8, 5.2, sk, z=4, rd=7.6, d=-5.4))
    # the horn sweeping back from the head, and cheek ridges
    parts.append(Cap('horn', 32, 13.5, 32, 8.0, 3.4, 2.0, sk, z=5, d1=2.5, d2=6.5, cd=0.0))
    parts.append(Cap('horn', 32, 8.0, 32, 2.5, 2.0, 0.4, '#f4d8b0', z=5.1, d1=6.5, d2=11.5, cd=0.0))
    parts.append(Spot('head', 30.2, 24.4, 0.5, 0.4, '#7a2a14', face=True))
    parts.append(Spot('head', 33.8, 24.4, 0.5, 0.4, '#7a2a14', face=True))
    feats = [Eye(27.6, 19.6, 3.0, '#3a86c0', look=(0, 0.05), style='angry'),
             Eye(36.4, 19.6, 3.0, '#3a86c0', look=(0, 0.05), style='angry', flip=True),
             Mouth(32.0, 28.4, 3.4, 'line')]
    rebuild(d, parts, pal={'skin': sk, 'belly': bel}, features=feats)


@fix('CHARIZARD')
def charizard(d, look):
    sk, bel = '#f08030', '#f6d890'
    mem, bone = '#3ea6a4', '#e46c26'
    parts = []
    # wings (behind the body)
    for side, g, sgn in ((-1, 'wingL', -1), (1, 'wingR', 1)):
        m = lambda x: 32 + sgn * (x - 32) * -1 if False else 32 + sgn * x  # noqa: E731
        S, W = (m(7), 33), (m(19), 17)
        tips = [(m(30), -5), (m(34), 12), (m(27), 28)]
        parts += batwing(g, side, S, W, tips, mem, bone, back=(m(10), 42), cd=6.5, z=-6, bone_r=2.1, T=1.4)
    parts.append(Stroke('tail', [37, 51, 45, 55.5, 53, 53.5, 57, 46, 56.5, 38], 7.4, sk, z=-4, w2=3.6, cd=5.0))
    parts += flame('fl', 56.5, 40.0, h=16.0, r=4.8, z=-3.5, lean=0.8)
    parts.append(E('body', 32, 39.5, 12.2, 15.8, sk, z=0, rd=10.4))
    parts.append(E('belly', 32, 42, 8.2, 13.2, bel, face=True))
    for k in range(6):
        parts.append(Stripe('belly', [25.6, 31 + k * 3.6, 32, 32 + k * 3.6, 38.4, 31 + k * 3.6], 0.7, '#dcb872'))
    # neck + head
    parts.append(Cap('neck', 32, 31, 32, 21.5, 7.0, 5.8, sk, z=3, cd=-1.5))
    parts += limbs_biped(sk, leg_dx=7.4, leg_y=50.0, leg_r=6.2, foot_w=6.0, foot_l=6.6, toe_r=1.8,
                         arm_sx=20.0, arm_y=33.0, arm_dx=-1.4, arm_l=8.5, arm_r=3.0, hand_r=2.7, fl=3.0)
    parts.append(E('head', 32, 16.5, 9.6, 8.2, sk, z=4, rd=8.6, cd=-2.5))
    parts.append(E('head', 32, 21.0, 6.0, 4.9, sk, z=4, rd=7.6, d=-6.2))
    for side, g in ((-1, 'hornL'), (1, 'hornR')):
        parts.append(Cap(g, 32 + side * 4.6, 11.6, 32 + side * 6.6, 7.0, 2.0, 0.9, sk, z=5, d1=3.5, d2=5.5, cd=0.0))
        parts.append(Cap(g, 32 + side * 6.6, 7.0, 32 + side * 8.4, 2.2, 1.0, 0.25, '#f4d8b0', z=5.1, d1=5.5, d2=8.0, cd=0.0))
    parts.append(Spot('head', 30.4, 19.6, 0.5, 0.45, '#6a2a10', face=True))
    parts.append(Spot('head', 33.6, 19.6, 0.5, 0.45, '#6a2a10', face=True))
    feats = [Eye(27.8, 15.6, 2.9, '#3aa6b0', look=(0, 0.05), style='angry'),
             Eye(36.2, 15.6, 2.9, '#3aa6b0', look=(0, 0.05), style='angry', flip=True),
             Mouth(32.0, 23.2, 3.0, 'line')]
    rebuild(d, parts, pal={'skin': sk, 'belly': bel}, features=feats)


def sidefoot(d, g, dirx=-1, n=3, w=4.6, h=2.3, toe_r=1.25, c=None, gnd=60.0, claw=CLAW, dx=0.0, z=None):
    """Add a foot with `n` toes (fanned in depth) to the lowest capsule of limb group g, for side-facing species."""
    caps = [p for p in parts(d, g) if p['t'] == 'c']
    if not caps:
        return
    cp = max(caps, key=lambda p: max(p['y1'], p['y2']))
    x = cp['x2'] if cp['y2'] >= cp['y1'] else cp['x1']
    x += dx
    c = c or cp['c']
    zz = cp.get('z', 0) if z is None else z
    add(d, E(g, x + dirx * 0.9, gnd - h * 0.9, w, h, c, z=zz, rd=w * 0.78))
    for i in range(n):
        f = i - (n - 1) / 2.0
        tx = x + dirx * (w * 0.95 + 0.3 - abs(f) * 0.35)
        add(d, E(g, tx, gnd - toe_r * 0.9, toe_r * 1.05, toe_r * 0.95, c, z=zz, rd=toe_r * 1.1, d=f * toe_r * 2.0))
        add(d, Cap(g, tx + dirx * 0.3, gnd - toe_r * 0.8, tx + dirx * 1.3, gnd - toe_r * 0.5, toe_r * 0.55, 0.2, claw,
                   z=zz + 0.02, d1=f * toe_r * 2.0, d2=f * toe_r * 2.3))


# ============================================================================ birds
def feather(g, x, y, ang, L, w, c, z=0.0, T=1.4, **kw):
    """A leaf-shaped feather plate from (x, y) in direction `ang` (deg; 0 = straight down, + toward +x)."""
    a = math.radians(ang)
    dx, dy = math.sin(a), math.cos(a)
    px, py = dy, -dx
    pts = [x - px * w * 0.35, y - py * w * 0.35,
           x + dx * L * 0.35 - px * w * 0.5, y + dy * L * 0.35 - py * w * 0.5,
           x + dx * L * 0.78 - px * w * 0.55, y + dy * L * 0.78 - py * w * 0.55,
           x + dx * L, y + dy * L,
           x + dx * L * 0.78 + px * w * 0.55, y + dy * L * 0.78 + py * w * 0.55,
           x + dx * L * 0.35 + px * w * 0.5, y + dy * L * 0.35 + py * w * 0.5,
           x + px * w * 0.35, y + py * w * 0.35]
    return Poly(g, pts, c, z=z, T=T, **kw)


def blade(g, x, y, rx, ln, c, dback=14.0, z=0.0, ry=0.9, **kw):
    """A flat horizontal feather / fin extending straight back in depth from the body (front-facing designs)."""
    return E(g, x, y, rx, ry, c, z=z, rd=ln * 0.5, d=dback + ln * 0.5, solid=True, **kw)


def bird_legs(bx, top, gnd, c, dx=4.6, r=1.8, toe_r=1.05, ln=3.4, n=3, w=2.6):
    out = []
    for side, g in ((-1, 'legL'), (1, 'legR')):
        lx = bx + side * dx
        out.append(Cap(g, lx, top, lx, gnd - 2.2, r, r * 0.82, c, z=2, cd=-1.0))
        out += foot(g, lx, gnd, c, w=w, ln=ln, n=n, dz=-1.0, toe_r=toe_r, z=2.2, claw=None)
    return out


def _bird(d, look, P):
    """Front-facing round bird: body, cream belly, head with face mask, beak, crest, folded wings, tail blades."""
    bx = 32.0
    parts = []
    br, bel = P['brown'], P['cream']
    by, brx, bry = P['by'], P['brx'], P['bry']
    # tail blades (behind)
    for i, (tx, ty, tl) in enumerate(P['tail']):
        parts.append(blade('tail', tx, ty, P.get('tail_w', 1.9), tl, P['tail_cols'][i % len(P['tail_cols'])],
                           dback=P.get('tail_back', 8.0), z=-4, ry=1.0, cd=0.0))
    parts.append(E('body', bx, by, brx, bry, br, z=0, rd=P['brd']))
    parts.append(E('belly', bx, by + P.get('belly_dy', 3.5), brx * 0.72, bry * 0.72, bel, face=True))
    hy, hrx, hry = P['hy'], P['hrx'], P['hry']
    parts.append(E('head', bx, hy, hrx, hry, P.get('head_c', br), z=4, rd=P['hrd'], cd=-1.5))
    if P.get('neck'):
        parts.append(Cap('neck', bx, hy + 2, bx, by - bry * 0.6, P['neck'][0], P['neck'][1], br, z=3, cd=-1.0))
    parts.append(E('mask', bx, hy + P.get('mask_dy', 2.6), hrx * 0.74, hry * 0.58, P['mask_c'], z=4.5, face=True))
    # beak: upper + lower, pointing at the viewer
    bl = P['beak_len']
    parts.append(Cap('beak', bx, hy + 3.2, bx, hy + 3.5, P['beak_r'], P['beak_r'] * 0.3, P['beak_c'], z=6,
                     d1=-P['hrd'] * 0.85, d2=-P['hrd'] * 0.85 - bl, cd=0.0))
    parts.append(Cap('beak', bx, hy + 4.8, bx, hy + 4.9, P['beak_r'] * 0.7, P['beak_r'] * 0.2, P['beak_c2'], z=6,
                     d1=-P['hrd'] * 0.8, d2=-P['hrd'] * 0.8 - bl * 0.7, cd=0.0))
    # crest / head feathers
    parts += P['crest'](hy, hrx, hry)
    # wings
    parts += P['wings'](bx, by, brx, bry)
    # legs
    parts += bird_legs(bx, by + bry * 0.55, 60.0, P['leg_c'], dx=P['leg_dx'], r=P.get('leg_r', 1.8),
                       toe_r=P.get('toe_r', 1.05), ln=P.get('foot_l', 3.4), w=P.get('foot_w', 2.6))
    ex = P['eye_dx']
    ey = hy + P.get('eye_dy', -0.6)
    feats = [Eye(bx - ex, ey, P['eye_s'], '#202030', look=(0, 0), sclera=False, **P.get('eye_kw', {})),
             Eye(bx + ex, ey, P['eye_s'], '#202030', look=(0, 0), sclera=False, **P.get('eye_kw', {}))]
    rebuild(d, parts, features=feats)


def _folded_wing(bx, by, brx, bry, c, tipc, length=9.5, thick=3.0, cdz=3.0, tip_n=3):
    out = []
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        wx = bx + side * (brx - 0.4)
        out.append(E(g, wx, by - 1.0, thick, length, c, z=2, rd=length * 0.78, d=cdz, rot=side * 10, cd=0.0))
        for i in range(tip_n):
            f = i - (tip_n - 1) / 2.0
            out.append(Cap(g, wx + side * 0.3 + f * 0.2, by + length * 0.4, wx + side * (1.2 + abs(f) * 0.4),
                           by + length * 1.02, thick * 0.55, thick * 0.2, tipc, z=2.1, d1=cdz + 2 + f * 2.2,
                           d2=cdz + 6.5 + f * 2.6, cd=0.0))
    return out


@fix('PIDGEY')
def pidgey(d, look):
    br, cr = '#b98a4e', '#f0e0bc'
    dark = '#8e5e30'

    def crest(hy, hrx, hry):
        return [Cap('crest', 32, hy - hry + 1.5, 30.6, hy - hry - 2.4, 1.6, 0.4, dark, z=6, d1=1.5, d2=3.0, cd=0.0),
                Cap('crest', 32, hy - hry + 1.5, 33.4, hy - hry - 2.0, 1.6, 0.4, dark, z=6, d1=1.5, d2=3.0, cd=0.0),
                Cap('crest', 32, hy - hry + 1.0, 32, hy - hry - 3.2, 1.8, 0.4, br, z=6, d1=2.0, d2=4.0, cd=0.0)]

    P = dict(brown=br, cream=cr, by=41.5, brx=12.2, bry=12.6, brd=10.8, hy=23.5, hrx=9.8, hry=8.8, hrd=9.0,
             mask_c=cr, beak_len=4.6, beak_r=2.7, beak_c='#f0a468', beak_c2='#d88a68', crest=crest,
             wings=lambda bx, by, brx, bry: _folded_wing(bx, by, brx, bry, dark, '#6e4520', length=9.5, thick=2.5),
             leg_c='#e8a090', leg_dx=4.6, eye_dx=4.4, eye_s=2.3, eye_kw=dict(wide=0.85),
             tail=[(28.5, 48, 13.0), (32, 49, 15.0), (35.5, 48, 13.0)], tail_cols=['#8e5e30', '#a87440', '#8e5e30'],
             tail_w=2.8, tail_back=7.0)
    _bird(d, look, P)


@fix('PIDGEOTTO')
def pidgeotto(d, look):
    br, cr = '#b47c44', '#f3e2bc'
    dark = '#8a5a2c'
    red, yel = '#e24a34', '#f8c83a'

    def crest(hy, hrx, hry):
        out = []
        # a swept-back plume of red and yellow feathers
        for i, (ang, L, c) in enumerate([(-8, 11.5, red), (10, 10.5, red), (2, 12.5, yel)]):
            out.append(Cap('crest', 32 + ang * 0.15, hy - hry + 2.0, 32 + ang * 0.5, hy - hry - L * 0.7, 1.9, 0.5, c, z=6,
                           d1=2.0, d2=2.0 + L * 0.9, cd=0.0))
        return out

    P = dict(brown=br, cream=cr, by=40.5, brx=12.0, bry=13.6, brd=10.4, hy=21.5, hrx=9.4, hry=8.6, hrd=8.6,
             mask_c=cr, beak_len=5.6, beak_r=2.6, beak_c='#ee9c60', beak_c2='#d08462', crest=crest,
             wings=lambda bx, by, brx, bry: _folded_wing(bx, by, brx, bry, dark, '#6a4220', length=11.5, thick=2.6),
             leg_c='#e6a094', leg_dx=4.8, eye_dx=4.4, eye_s=2.3, eye_kw=dict(wide=0.85),
             tail=[(28.5, 47, 17), (32, 48, 20), (35.5, 47, 17)], tail_cols=[red, yel, red], tail_w=2.8, tail_back=7.0,
             neck=(6.0, 5.2))
    _bird(d, look, P)


@fix('SPEAROW')
def spearow(d, look):
    br, cr = '#a86a3c', '#f2dcb4'
    rust = '#c8603a'

    def crest(hy, hrx, hry):
        out = []
        for i, (dx, L) in enumerate([(-4.4, 5.0), (0, 6.6), (4.4, 5.0)]):
            out.append(Cap('crest', 32 + dx * 0.7, hy - hry + 1.5, 32 + dx * 1.1, hy - hry - L, 1.7, 0.35, rust, z=6,
                           d1=1.0, d2=2.5, cd=0.0))
        return out

    P = dict(brown=br, cream=cr, by=42.0, brx=11.2, bry=12.0, brd=10.0, hy=24.0, hrx=9.6, hry=8.6, hrd=8.8,
             mask_c=cr, beak_len=6.6, beak_r=2.6, beak_c='#f4b8a0', beak_c2='#dca090', crest=crest,
             wings=lambda bx, by, brx, bry: _folded_wing(bx, by, brx, bry, rust, '#7a3a20', length=10.0, thick=2.5),
             leg_c='#e6a898', leg_dx=4.4, eye_dx=4.4, eye_s=2.3, eye_kw=dict(wide=0.85, style='angry'),
             tail=[(28.5, 47, 13), (32, 48, 15), (35.5, 47, 13)], tail_cols=['#7a4a28', rust, '#7a4a28'], tail_w=2.8,
             tail_back=7.0)
    _bird(d, look, P)


def crest_sweep(cols, hy, hry, back=16.0, rise=3.0, w=(3.4, 0.9), spread=(-2.6, 0.0, 2.6), lens=(1.0, 1.15, 1.0),
                start=1.0, group='crest'):
    """A plume swept back from the top of the head: strokes rising a little while running backwards in depth."""
    out = []
    for i, c in enumerate(cols):
        sx = 32 + spread[i % len(spread)]
        L = back * lens[i % len(lens)]
        out.append(Stroke(group, [sx, hy - hry + 2.2, sx + spread[i % len(spread)] * 0.35, hy - hry - rise * 0.6,
                                  sx + spread[i % len(spread)] * 0.6, hy - hry - rise], w[0], c, z=6, w2=w[1],
                          d1=start, d2=start + L, cd=0.0))
    return out


def _fan_wing(g, side, sx, sy, angs, lens, w, c, tipc, z=-1.0, cd=4.0, T=1.5):
    """Spread wing: feathers fanned from the shoulder in the sprite plane.  Angles are for the +x side (0 = down)."""
    out = []
    for i, (a, L) in enumerate(zip(angs, lens)):
        aa = a * side
        out.append(feather(g, sx, sy, aa, L, w, c if i % 2 == 0 else tipc, z=z + i * 0.05, T=T, cd=cd))
    out.append(E(g, sx + side * 2.0, sy - 0.5, 4.2, 3.4, c, z=z + 1, rd=3.2, cd=cd))
    return out


@fix('PIDGEOTTO')
def pidgeotto2(d, look):
    pidgeotto(d, look)
    parts_ = [p for p in d['parts'] if p.get('g') != 'crest']
    d['parts'] = parts_
    red, yel = '#e24a34', '#f8c83a'
    for p in crest_sweep([red, yel, red], 21.5, 8.6, back=15.0, rise=4.0):
        d['parts'].insert(0, p)


@fix('PIDGEOT')
def pidgeot(d, look):
    br, cr = '#b47c46', '#f2e4c2'
    dark = '#84562c'
    red, yel = '#e24a34', '#f8c83a'
    # spread, raised wings (feather fans)
    wings = []
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        wings += _fan_wing(g, side, 32 + side * 9.0, 32.0, [96, 112, 128, 144, 158],
                           [24.0, 26.5, 26.0, 23.0, 18.0], 7.0, br, dark, z=-2, cd=5.0, T=1.8)
    P = dict(brown=br, cream=cr, by=40.0, brx=11.8, bry=14.2, brd=10.6, hy=20.5, hrx=9.0, hry=8.4, hrd=8.4,
             mask_c=cr, beak_len=5.6, beak_r=2.5, beak_c='#ee9c60', beak_c2='#d08462',
             crest=lambda hy, hrx, hry: crest_sweep([red, yel, red, yel], hy, hry, back=22.0, rise=6.0,
                                                    spread=(-3.0, -1.0, 1.0, 3.0), lens=(1.0, 1.1, 1.1, 1.0), w=(3.4, 1.0)),
             wings=lambda bx, by, brx, bry: wings,
             leg_c='#e6a094', leg_dx=4.8, eye_dx=4.2, eye_s=2.2, eye_kw=dict(wide=0.85),
             tail=[(27.5, 46, 22), (30, 47, 25), (32, 48, 27), (34, 47, 25), (36.5, 46, 22)],
             tail_cols=[red, yel, red, yel, red], tail_w=2.3, tail_back=7.0, neck=(6.4, 5.4))
    _bird(d, look, P)


@fix('FEAROW')
def fearow(d, look):
    br, cr = '#a86e40', '#ecd8b0'
    rust, dark = '#c65e3c', '#7a4a28'
    wings = []
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        wings += _fan_wing(g, side, 32 + side * 8.6, 33.0, [100, 116, 132, 148],
                           [22.0, 24.0, 22.0, 18.0], 6.4, rust, dark, z=-2, cd=5.0, T=1.7)

    def crest(hy, hrx, hry):
        out = []
        for i, (dx, L) in enumerate([(-3.2, 6.5), (0, 8.5), (3.2, 6.5)]):
            out.append(Cap('crest', 32 + dx * 0.6, hy - hry + 2.0, 32 + dx * 1.2, hy - hry - L, 1.9, 0.35, '#d83a28', z=6,
                           d1=2.0, d2=5.0 + i, cd=0.0))
        return out

    P = dict(brown=br, cream=cr, by=42.0, brx=10.6, bry=13.2, brd=9.4, hy=21.0, hrx=7.8, hry=7.4, hrd=7.4,
             mask_c=cr, beak_len=10.5, beak_r=2.2, beak_c='#f0b8a4', beak_c2='#d8a090', crest=crest,
             wings=lambda bx, by, brx, bry: wings,
             leg_c='#e6a898', leg_dx=4.4, eye_dx=3.7, eye_s=2.1, eye_kw=dict(wide=0.85, style='angry'),
             tail=[(28.5, 47, 15), (32, 48, 17), (35.5, 47, 15)], tail_cols=[dark, rust, dark], tail_w=2.5,
             tail_back=7.0, neck=(5.4, 4.4), belly_dy=1.0)
    _bird(d, look, P)


# ============================================================================ Pikachu line
def bolt(g, x, y, s, c, base_c=None, tilt=0.0, T=2.6, cd=6.0, z=-2.0):
    """A chunky lightning-bolt plate (tail tip); (x, y) = the bottom tip, s = scale (~1 px per unit), tilt in degrees."""
    pts0 = [(6, 0), (13, 0), (9.5, 9.5), (15, 9.5), (2, 27), (5.5, 14.5), (0, 14.5)]
    a = math.radians(tilt)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for (px, py) in pts0:
        ux, uy = (px - 2) * s, (py - 27) * s
        pts += [x + ux * ca - uy * sa, y + ux * sa + uy * ca]
    return Poly(g, pts, c, z=z, T=T, cd=cd)


@fix('PIKACHU')
def pikachu(d, look):
    fur, tip, cheek, brown = '#f8d030', '#2a2430', '#e84838', '#a86830'
    parts = []
    # tail: brown stem + big zig-zag bolt (behind the body, to the right)
    parts.append(Cap('tail', 40.0, 54.0, 44.0, 45.5, 2.8, 2.3, brown, z=-4, cd=6.0))
    parts.append(bolt('tail', 45.0, 45.5, 0.95, fur, tilt=8, T=2.8, cd=6.0, z=-4))
    parts.append(E('body', 32, 46.5, 10.6, 12.0, fur, z=0, rd=9.4))
    parts.append(E('belly', 32, 48, 6.6, 8.4, '#fbe680', face=True))
    parts.append(Stripe('body', [24.5, 41.5, 32, 42.6, 39.5, 41.5], 2.0, brown, backOnly=True))
    parts.append(Stripe('body', [24.0, 47.0, 32, 48.2, 40.0, 47.0], 2.0, brown, backOnly=True))
    parts += limbs_biped(fur, leg_dx=5.4, leg_y=54.5, leg_r=3.6, foot_w=4.4, foot_l=4.8, toe_r=1.25,
                         arm_sx=22.5, arm_y=39.5, arm_dx=-1.6, arm_l=5.6, arm_r=2.4, hand_r=2.1, n_fing=3, fl=1.9,
                         claw=None)
    # ears: long, black-tipped, standing off the head
    for side, g in ((-1, 'earL'), (1, 'earR')):
        x0 = 32 + side * 6.0
        pts = [x0 - side * 3.0, 22, x0 - side * 0.2, 15, x0 + side * 4.4, 5.0, x0 + side * 9.4, -1.0,
               x0 + side * 12.2, 1.2, x0 + side * 9.0, 8.0, x0 + side * 7.0, 17, x0 + side * 4.0, 23]
        parts.append(Poly(g, pts, fur, z=1, T=2.3, cd=1.0))
        parts.append(Poly(g, [x0 + side * 4.4, 3.0, x0 + side * 9.4, -1.0, x0 + side * 12.2, 1.2, x0 + side * 9.8, 6.2],
                          tip, z=1.1, T=2.3, cd=1.0))
    parts.append(E('head', 32, 28.0, 12.6, 10.6, fur, z=4, rd=10.0, cd=-1.0))
    parts.append(E('cheekL', 22.6, 32.0, 3.5, 3.0, cheek, z=4.6, rd=2.6, d=-6.5, cd=-1.0))
    parts.append(E('cheekR', 41.4, 32.0, 3.5, 3.0, cheek, z=4.6, rd=2.6, d=-6.5, cd=-1.0))
    parts.append(Spot('head', 32.0, 29.6, 0.7, 0.5, '#3a2a2a', face=True))
    feats = [Eye(26.4, 26.2, 3.3, '#202030', look=(0, 0), sclera=False),
             Eye(37.6, 26.2, 3.3, '#202030', look=(0, 0), sclera=False),
             Mouth(32.0, 32.4, 2.2, 'smile')]
    rebuild(d, parts, features=feats)


@fix('RAICHU')
def raichu(d, look):
    fur, belly, brown, ein = '#ee9632', '#f8e2a8', '#8e5228', '#f8d860'
    parts = []
    # long thin tail with a bolt tip, curling out behind
    parts.append(Stroke('tail', [38, 55, 46, 58, 54, 55, 56, 47, 54.5, 41], 2.6, '#302830', z=-5, w2=2.0, cd=6.0))
    parts.append(bolt('tail', 53.5, 41.5, 0.85, '#f4c430', tilt=-6, T=2.4, cd=6.0, z=-4.9))
    parts.append(E('body', 32, 46.0, 11.4, 12.4, fur, z=0, rd=10.0))
    parts.append(E('belly', 32, 48.0, 7.6, 9.4, belly, face=True))
    parts.append(Stripe('body', [23.5, 42.0, 32, 43.2, 40.5, 42.0], 2.0, brown, backOnly=True))
    parts.append(Stripe('body', [23.0, 47.5, 32, 48.7, 41.0, 47.5], 2.0, brown, backOnly=True))
    parts += limbs_biped(fur, leg_dx=5.8, leg_y=54.5, leg_r=3.9, foot_w=4.8, foot_l=5.2, toe_r=1.3,
                         arm_sx=21.5, arm_y=39.0, arm_dx=-1.8, arm_l=6.0, arm_r=2.6, hand_r=2.3, n_fing=3, fl=2.0,
                         claw=None)
    # big ears: brown outside, yellow inside, curling out at the tips
    for side, g in ((-1, 'earL'), (1, 'earR')):
        x0 = 32 + side * 7.5
        outer = [x0 - side * 3.5, 24, x0 - side * 1.5, 14, x0 + side * 2.0, 6, x0 + side * 7.0, 2.0, x0 + side * 12.5, 3.0,
                 x0 + side * 14.5, 6.0, x0 + side * 11.0, 5.8, x0 + side * 12.0, 11, x0 + side * 9.0, 19, x0 + side * 5.0, 24.5]
        parts.append(Poly(g, outer, brown, z=1, T=2.5, cd=0.5))
        inner = [x0 - side * 0.5, 22.5, x0 + side * 0.5, 14, x0 + side * 3.6, 8.6, x0 + side * 7.5, 6.4, x0 + side * 9.5, 10.5,
                 x0 + side * 7.5, 17.5, x0 + side * 4.0, 22.5]
        parts.append(Poly(g, inner, ein, z=1.2, T=2.5, cd=0.5, face=True))
    parts.append(E('head', 32, 29.5, 12.8, 10.6, fur, z=4, rd=10.2, cd=-1.0))
    parts.append(E('cheekL', 21.6, 33.6, 3.6, 3.0, '#f8e040', z=4.6, rd=2.6, d=-6.5, cd=-1.0))
    parts.append(E('cheekR', 42.4, 33.6, 3.6, 3.0, '#f8e040', z=4.6, rd=2.6, d=-6.5, cd=-1.0))
    parts.append(Spot('head', 32.0, 31.6, 0.7, 0.5, '#3a2a2a', face=True))
    feats = [Eye(26.2, 27.8, 3.0, '#202030', look=(0, 0), sclera=False, wide=0.8),
             Eye(37.8, 27.8, 3.0, '#202030', look=(0, 0), sclera=False, wide=0.8),
             Mouth(32.0, 33.6, 2.6, 'open')]
    rebuild(d, parts, features=feats)


# ============================================================================ pink fairies
def cone(g, x0, y0, x1, y1, r0, r1, c, tipc=None, tip_frac=0.22, z=1.0, d0=0.0, d1=0.0, **kw):
    """A pointed ear / horn: round cone from (x0,y0) to (x1,y1); optional coloured tip."""
    out = []
    if tipc:
        mx, my = x0 + (x1 - x0) * (1 - tip_frac), y0 + (y1 - y0) * (1 - tip_frac)
        rm = r0 + (r1 - r0) * (1 - tip_frac)
        dm = d0 + (d1 - d0) * (1 - tip_frac)
        out.append(Cap(g, x0, y0, mx, my, r0, rm, c, z=z, d1=d0, d2=dm, **kw))
        out.append(Cap(g, mx, my, x1, y1, rm, r1, tipc, z=z + 0.05, d1=dm, d2=d1, **kw))
    else:
        out.append(Cap(g, x0, y0, x1, y1, r0, r1, c, z=z, d1=d0, d2=d1, **kw))
    return out


def head_curl(g, x, y, c, w=3.0, s=1.0, d=-7.0, cd=-1.0, z=6.0):
    """The curl of hair on the forehead of Clefairy / Jigglypuff, standing out of the head."""
    pts = [x + 2.0 * s, y + 2.5 * s, x + 0.2 * s, y - 0.8 * s, x + 3.0 * s, y - 3.4 * s, x + 6.4 * s, y - 2.6 * s,
           x + 6.8 * s, y + 0.4 * s, x + 4.4 * s, y + 0.8 * s]
    return Stroke(g, pts, w, c, z=z, w2=w * 0.5, d1=d, d2=d - 1.5, cd=cd)


@fix('CLEFAIRY')
def clefairy(d, look):
    body, dark, light = '#f8b4c4', '#6c4438', '#fbdce6'
    parts = []
    parts.append(Stroke('tail', [39, 55.5, 46, 57, 51, 52.5, 49, 47.5, 45, 49], 3.4, body, z=-5, w2=2.2, cd=6.0))
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        parts.append(Poly(g, [m(41), 43, m(43.5), 34, m(51), 31, m(49.5), 37, m(53), 40, m(47), 44, m(43), 47],
                          '#fbe2ea', z=-3, T=1.3, cd=5.0))
        parts.append(Stripe(g, [m(43), 42, m(49), 36], 0.8, '#e8b0c0'))
    parts.append(E('body', 32, 46.5, 11.4, 11.2, body, z=0, rd=10.0))
    parts.append(E('belly', 32, 48.5, 7.4, 8.0, light, face=True))
    parts += limbs_biped(body, leg_dx=5.0, leg_y=54.5, leg_r=3.8, foot_w=4.4, foot_l=4.8, toe_r=1.3, n_toe=3,
                         arm_sx=21.5, arm_y=40.0, arm_dx=-3.2, arm_l=5.0, arm_r=2.4, hand_r=2.1, n_fing=3, fl=1.7,
                         claw=None, arm_ang=20)
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 6.4, 25.0, 32 + side * 12.4, 9.0, 5.0, 1.2, body, tipc=dark, z=1, cd=-0.5)
        parts.append(Spot(g, 32 + side * 8.4, 20.0, 1.6, 3.6, '#f8c8d6', face=True))
    parts.append(E('head', 32, 30.5, 12.8, 10.8, body, z=4, rd=10.6, cd=-1.0))
    parts.append(head_curl('curl', 28.5, 22.0, '#e5809c', w=3.0, s=1.0))
    parts.append(Spot('head', 21.5, 35.0, 2.2, 1.5, '#f47e9c', face=True))
    parts.append(Spot('head', 42.5, 35.0, 2.2, 1.5, '#f47e9c', face=True))
    feats = [Eye(26.6, 31.0, 2.7, '#202030', look=(0, 0), sclera=False, wide=0.8),
             Eye(37.4, 31.0, 2.7, '#202030', look=(0, 0), sclera=False, wide=0.8),
             Mouth(32.0, 35.6, 1.8, 'smile')]
    rebuild(d, parts, features=feats)


@fix('CLEFABLE')
def clefable(d, look):
    body, dark, light = '#f8b4c4', '#6c4438', '#fbdce6'
    parts = []
    parts.append(Stroke('tail', [39, 56.0, 46, 58, 52, 53, 50, 46.5, 45.5, 48.5], 4.2, body, z=-5, w2=2.6, cd=6.0))
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        parts.append(Poly(g, [m(41), 44, m(43), 33, m(46), 25, m(50), 20.5, m(52), 27, m(55), 30, m(52), 36, m(56), 40,
                              m(50), 45, m(44), 48], '#fbe2ea', z=-3, T=1.5, cd=5.0))
        parts.append(Stripe(g, [m(43), 42, m(48), 30, m(51), 23], 0.9, '#e8b0c0'))
        parts.append(Stripe(g, [m(44), 45, m(52), 38], 0.9, '#e8b0c0'))
    parts.append(E('body', 32, 45.0, 11.2, 13.4, body, z=0, rd=9.8))
    parts.append(E('belly', 32, 47.5, 7.2, 9.6, light, face=True))
    parts += limbs_biped(body, leg_dx=5.0, leg_y=53.5, leg_r=3.7, foot_w=4.2, foot_l=4.8, toe_r=1.25, n_toe=3,
                         arm_sx=21.5, arm_y=37.0, arm_dx=-3.2, arm_l=7.0, arm_r=2.4, hand_r=2.2, n_fing=3, fl=1.9,
                         claw=None, arm_ang=20)
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 6.6, 22.0, 32 + side * 12.6, 3.5, 5.0, 1.2, body, tipc=dark, z=1, cd=-0.5)
        parts.append(Spot(g, 32 + side * 8.6, 15.0, 1.7, 4.4, '#f8c8d6', face=True))
    parts.append(E('head', 32, 27.5, 11.8, 10.0, body, z=4, rd=10.0, cd=-1.0))
    parts.append(head_curl('curl', 28.5, 19.5, '#e5809c', w=3.2, s=1.1))
    feats = [Eye(27.4, 28.0, 2.9, '#202030', look=(0, 0), sclera=False, wide=0.8),
             Eye(36.6, 28.0, 2.9, '#202030', look=(0, 0), sclera=False, wide=0.8),
             Mouth(32.0, 32.4, 1.8, 'smile')]
    rebuild(d, parts, features=feats)


@fix('JIGGLYPUFF')
def jigglypuff(d, look):
    body, light, dark = '#f8bccc', '#fde2ea', '#3a2a3a'
    parts = []
    parts.append(E('body', 32, 42.5, 16.2, 15.6, body, z=0, rd=15.0))
    parts.append(E('belly', 32, 50.0, 10.5, 8.0, light, face=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 10.0, 30.0, 32 + side * 14.4, 16.0, 6.2, 1.6, body, z=1, cd=-2.0)
        parts.append(Spot(g, 32 + side * 11.6, 25.0, 2.4, 4.0, dark, face=True))
    for side, g in ((-1, 'armL'), (1, 'armR')):
        parts.append(Cap(g, 32 + side * 14.5, 44.0, 32 + side * 19.5, 48.5, 3.0, 2.5, body, z=3, cd=-4.0))
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(E(g, 32 + side * 7.2, 57.2, 5.6, 3.0, body, z=2, rd=6.0, d=-2.5, cd=0.0))
        parts += toes(g, 32 + side * 7.2, 58.4, n=3, spread=2.6, r=1.4, dz=-7.5, c=body, claw=None, z=2.1, cd=0.0)
    parts.append(head_curl('curl', 26.5, 27.0, '#ee8fac', w=3.6, s=1.5, d=-13.0, cd=-2.0))
    feats = [Eye(25.4, 40.5, 4.6, '#2aa4c8', look=(0, 0.05), wide=0.95),
             Eye(38.6, 40.5, 4.6, '#2aa4c8', look=(0, 0.05), wide=0.95),
             Mouth(32.0, 48.5, 1.8, 'smile')]
    rebuild(d, parts, features=feats)


@fix('WIGGLYTUFF')
def wigglytuff(d, look):
    body, light, ein = '#f8bcd0', '#fdeef2', '#e8d0b0'
    parts = []
    parts.append(Stroke('tail', [40, 56, 47, 55, 51, 48, 48, 42, 43, 44.5, 45, 49], 6.2, body, z=-5, w2=4.0, cd=7.0))
    parts.append(E('body', 32, 43.0, 14.4, 16.6, body, z=0, rd=12.6))
    parts.append(E('belly', 32, 46.5, 10.4, 12.0, light, face=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 8.6, 22.0, 32 + side * 14.0, 2.5, 6.0, 1.8, body, z=1, cd=-2.0)
        parts.append(Spot(g, 32 + side * 10.6, 13.0, 2.2, 6.0, ein, face=True))
    for side, g in ((-1, 'armL'), (1, 'armR')):
        parts.append(Cap(g, 32 + side * 13.5, 42.0, 32 + side * 17.0, 46.5, 3.6, 3.0, body, z=3, cd=-3.5))
        parts += toes(g, 32 + side * 17.2, 47.6, n=3, spread=1.9, r=1.2, dz=-4.5, c=body, claw=None, z=3.1, cd=0.0)
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(E(g, 32 + side * 7.0, 57.4, 5.4, 3.0, body, z=2, rd=6.0, d=-2.5, cd=0.0))
        parts += toes(g, 32 + side * 7.0, 58.6, n=3, spread=2.5, r=1.3, dz=-7.5, c=body, claw=None, z=2.1, cd=0.0)
    # the big fluffy forelock
    parts.append(E('tuft', 32, 23.5, 9.5, 5.2, body, z=6, rd=7.5, d=-4.0, cd=-2.0))
    parts.append(head_curl('curl', 27.0, 24.0, '#f09ab4', w=3.4, s=1.4, d=-13.0, cd=-2.0))
    feats = [Eye(26.0, 34.5, 4.0, '#38a8d0', look=(0, 0.05), wide=0.85),
             Eye(38.0, 34.5, 4.0, '#38a8d0', look=(0, 0.05), wide=0.85),
             Mouth(32.0, 42.0, 1.6, 'smile')]
    rebuild(d, parts, features=feats)


# ============================================================================ rats
def whiskers(g, x, y, c='#f0ecdc', n=2, ln=8.0, spread=2.4, dx=-1, z=7.0, d=-2.0, cd=0.0, w=0.9):
    out = []
    for i in range(n):
        f = i - (n - 1) / 2.0
        out.append(Stroke(g, [x, y + f * 0.8, x + dx * ln * 0.5, y + f * spread * 0.9 - 0.6, x + dx * ln, y + f * spread * 1.6],
                          w, c, z=z, w2=w * 0.6, d1=d, d2=d + 1.0, cd=cd))
    return out


@fix('RATTATA')
def rattata(d, look):
    fur, belly, ein, tooth = '#a070b8', '#f0e0b8', '#e8a8c0', '#f4f0e4'
    parts = []
    parts.append(Stroke('tail', [34, 52, 41, 58.5, 49, 55, 52, 46, 48.5, 41], 3.0, '#b088c0', z=-6, w2=1.6,
                        d1=12.0, d2=16.0, cd=0.0))
    parts.append(E('body', 32, 49.5, 9.0, 8.4, fur, z=0, rd=11.5, d=3.0, cd=0.0))
    parts.append(E('belly', 32, 55.0, 6.4, 3.2, belly, z=0.5, face=True))
    # four short legs
    for side, g in ((-1, 'legFL'), (1, 'legFR')):
        parts.append(Cap(g, 32 + side * 5.6, 54.0, 32 + side * 5.8, 58.0, 2.5, 2.1, fur, z=2, cd=-4.5))
        parts.append(E(g, 32 + side * 6.0, 58.6, 3.0, 1.5, belly, z=2.1, rd=3.6, d=-1.0, cd=-4.5))
    for side, g in ((-1, 'legBL'), (1, 'legBR')):
        parts.append(Cap(g, 32 + side * 6.2, 52.5, 32 + side * 6.4, 58.0, 3.4, 2.4, fur, z=2, cd=8.0))
        parts.append(E(g, 32 + side * 6.4, 58.6, 3.2, 1.5, belly, z=2.1, rd=4.2, d=-1.0, cd=8.0))
    # head
    parts.append(E('head', 32, 42.0, 9.4, 8.2, fur, z=4, rd=8.4, cd=-8.5))
    parts.append(E('head', 32, 45.2, 5.0, 3.8, belly, z=4, rd=5.4, d=-4.0, cd=-8.5, frontOnly=True))
    parts.append(E('nose', 32, 43.6, 1.5, 1.2, '#e86888', z=6, rd=1.4, d=-9.0, cd=-8.5, solid=True))
    for side in (-1, 1):
        parts.append(E('tooth', 32 + side * 0.9, 48.6, 0.95, 1.8, tooth, z=6, rd=0.7, d=-8.6, cd=-8.5, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts.append(E(g, 32 + side * 7.4, 34.4, 4.8, 5.8, fur, z=1, rd=1.9, rot=side * 12, d=2.0, cd=-8.5))
        parts.append(Spot(g, 32 + side * 7.2, 34.8, 2.8, 3.8, ein, rot=side * 12, face=True))
    parts += whiskers('whL', 29.4, 45.6, dx=-1, ln=8.5)
    parts += whiskers('whR', 34.6, 45.6, dx=1, ln=8.5)
    for p in parts:
        if p.get('g') in ('whL', 'whR'):
            p['cd'] = -8.5
    feats = [Eye(27.6, 39.6, 2.6, '#c02848', look=(0, 0)), Eye(36.4, 39.6, 2.6, '#c02848', look=(0, 0))]
    rebuild(d, parts, features=feats)


@fix('RATICATE')
def raticate(d, look):
    fur, belly, ein, tooth = '#c89058', '#f4e4c0', '#f0c8a0', '#f4f0e4'
    parts = []
    parts.append(Stroke('tail', [36, 54, 45, 58.5, 53, 53, 55, 44, 51, 38], 3.4, '#d8a878', z=-6, w2=1.8,
                        d1=10.0, d2=15.0, cd=0.0))
    parts.append(E('body', 32, 45.5, 11.4, 12.4, fur, z=0, rd=10.6))
    parts.append(E('belly', 32, 48.0, 7.4, 9.4, belly, face=True))
    parts += limbs_biped(fur, leg_dx=6.2, leg_y=54.0, leg_r=4.2, foot_w=5.0, foot_l=5.6, toe_r=1.3,
                         arm_sx=21.4, arm_y=38.5, arm_dx=-2.5, arm_l=6.5, arm_r=2.7, hand_r=2.3, fl=2.0, claw=CLAW,
                         arm_ang=14)
    # head with a long muzzle, two big front teeth, big ears
    parts.append(E('head', 32, 28.0, 11.6, 9.8, fur, z=4, rd=9.4, cd=-1.5))
    parts.append(E('head', 32, 32.6, 6.2, 5.0, belly, z=4, rd=6.6, d=-5.8, cd=-1.5, frontOnly=True))
    parts.append(E('nose', 32, 30.4, 1.9, 1.5, '#8a4a30', z=6, rd=1.8, d=-12.0, cd=-1.5, solid=True))
    for side in (-1, 1):
        parts.append(E('tooth', 32 + side * 1.2, 37.4, 1.3, 2.7, tooth, z=6, rd=0.9, d=-10.8, cd=-1.5, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts.append(E(g, 32 + side * 8.6, 19.0, 4.6, 5.4, fur, z=1, rd=2.0, rot=side * 22, d=1.0, cd=-1.5))
        parts.append(Spot(g, 32 + side * 8.4, 19.4, 2.6, 3.4, ein, rot=side * 22, face=True))
    parts += whiskers('whL', 28.0, 33.2, dx=-1, ln=10.0, n=3, spread=2.6)
    parts += whiskers('whR', 36.0, 33.2, dx=1, ln=10.0, n=3, spread=2.6)
    for p in parts:
        if p.get('g') in ('whL', 'whR'):
            p['cd'] = -1.5
            p['d1'] = -10.0
            p['d2'] = -9.0
    feats = [Eye(26.6, 25.6, 2.6, '#302020', look=(0, 0), style='angry'),
             Eye(37.4, 25.6, 2.6, '#302020', look=(0, 0), style='angry', flip=True)]
    rebuild(d, parts, features=feats)


# ============================================================================ Nidoran family (quadrupeds) + queen / king
def _spines(g, xs, ys_base, ys_tip, depths, r, c, tip=None, z=-1.0, cd=0.0):
    out = []
    for x, yb, yt, dd in zip(xs, ys_base, ys_tip, depths):
        out.append(Cap(g, x, yb, x, yt, r, 0.3, c, z=z, d1=dd, d2=dd, cd=cd))
    return out


def _nquad(d, P):
    """Front-facing four-legged Nido: body running away from the viewer, head in front, tall ears, back quills."""
    body, spot, ein, spike = P['body'], P['spot'], P['earIn'], P['spike']
    parts = []
    by, brx, bry, blen = P['by'], P['brx'], P['bry'], P['blen']
    parts.append(Cap('tail', 32, by - 1.0, 34.5, by - 6.0, 2.4, 0.7, body, z=-6, d1=blen * 0.95 + 3, d2=blen * 0.95 + 7, cd=0.0))
    parts.append(E('body', 32, by, brx, bry, body, z=0, rd=blen, d=4.0, cd=0.0))
    for (sx, sy, sd) in P['spots']:
        parts.append(Spot('body', sx, sy, 2.0, 1.6, spot))
    parts += _spines('quill', P['q_x'], [by - bry + 1.8] * len(P['q_d']), [by - bry - P['q_h']] * len(P['q_d']),
                     P['q_d'], P['q_r'], spike, cd=0.0)
    for side, g in ((-1, 'legFL'), (1, 'legFR')):
        parts.append(Cap(g, 32 + side * 5.2, by + 3.0, 32 + side * 5.4, 58.0, P['leg_r'], P['leg_r'] * 0.85, body, z=2, cd=-4.5))
        parts.append(E(g, 32 + side * 5.6, 58.6, 3.2, 1.6, body, z=2.1, rd=3.8, d=-1.2, cd=-4.5))
    for side, g in ((-1, 'legBL'), (1, 'legBR')):
        parts.append(Cap(g, 32 + side * 6.0, by + 1.5, 32 + side * 6.2, 58.0, P['leg_r'] * 1.15, P['leg_r'] * 0.9, body, z=2, cd=8.5))
        parts.append(E(g, 32 + side * 6.2, 58.6, 3.4, 1.6, body, z=2.1, rd=4.0, d=-1.2, cd=8.5))
    hy, hrx, hry = P['hy'], P['hrx'], P['hry']
    parts.append(E('head', 32, hy, hrx, hry, body, z=4, rd=hry + 0.4, cd=-8.0))
    parts.append(E('head', 32, hy + hry * 0.4, hrx * 0.52, hry * 0.44, body, z=4, rd=hrx * 0.6, d=-4.2, cd=-8.0))
    parts.append(E('nose', 32, hy + hry * 0.18, 1.5, 1.2, P['nose_c'], z=6, rd=1.3, d=-hrx * 0.98, cd=-8.0, solid=True))
    for side in (-1, 1):
        parts.append(Cap('fang', 32 + side * 1.9, hy + hry * 0.72, 32 + side * 1.9, hy + hry * 0.72 + 2.0, 0.8, 0.2, P['tooth_c'],
                         z=7, d1=-hrx * 0.7, d2=-hrx * 0.7 - 0.6, cd=-8.0))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts.append(E(g, 32 + side * P['ear_dx'], hy - hry * 0.78 - P['ear_ry'] * 0.55, P['ear_rx'], P['ear_ry'], body, z=1,
                       rd=2.0, rot=side * P['ear_rot'], d=3.0, cd=-8.0))
        parts.append(Spot(g, 32 + side * (P['ear_dx'] - 0.3), hy - hry * 0.78 - P['ear_ry'] * 0.5, P['ear_rx'] * 0.58,
                          P['ear_ry'] * 0.68, ein, rot=side * P['ear_rot'], face=True))
    if P.get('horn'):
        hl = P['horn']
        parts.append(Cap('horn', 32, hy - hry * 0.7, 32, hy - hry * 0.7 - hl, 2.3, 0.35, P['horn_c'], z=7,
                         d1=-hrx * 0.6, d2=-hrx * 0.6 - hl * 0.45, cd=-8.0))
    ex = P['eye_dx']
    feats = [Eye(32 - ex, hy - hry * 0.18, P['eye_s'], P['iris'], look=(0, 0), style=P.get('eye_style', 'round'), wide=0.85),
             Eye(32 + ex, hy - hry * 0.18, P['eye_s'], P['iris'], look=(0, 0), style=P.get('eye_style', 'round'), wide=0.85,
                 **({'flip': True} if P.get('eye_style') else {}))]
    rebuild(d, parts, features=feats)


@fix('NIDORAN_F')
def nidoran_f(d, look):
    _nquad(d, dict(body='#8cb2e6', spot='#5a7cc0', earIn='#c8daf4', spike='#dce6f6', nose_c='#3a4a78', tooth_c='#f4f0e4',
                   by=49.5, brx=8.4, bry=7.6, blen=10.5, spots=[(28, 47, 0), (37, 49, 0), (33, 45, 0)],
                   q_x=[32, 32, 32, 32], q_d=[-1.0, 4.0, 9.0, 13.5], q_h=4.6, q_r=1.5, leg_r=2.6,
                   hy=41.0, hrx=9.2, hry=8.0, ear_dx=7.4, ear_rx=5.4, ear_ry=8.4, ear_rot=14,
                   eye_dx=4.4, eye_s=2.6, iris='#c82838'))


@fix('NIDORINA')
def nidorina(d, look):
    _nquad(d, dict(body='#84a8dc', spot='#4a68b0', earIn='#c0d2ee', spike='#e4ecf8', nose_c='#3a4a78', tooth_c='#f4f0e4',
                   by=48.5, brx=9.8, bry=8.8, blen=12.0, spots=[(27, 46, 0), (37, 49, 0), (34, 43, 0), (29, 51, 0)],
                   q_x=[32, 32, 32, 32, 32], q_d=[-2.0, 3.0, 8.0, 13.0, 17.5], q_h=6.2, q_r=1.8, leg_r=3.0,
                   hy=39.5, hrx=9.8, hry=8.6, ear_dx=7.4, ear_rx=5.2, ear_ry=7.4, ear_rot=16,
                   eye_dx=4.6, eye_s=2.6, iris='#c82838', eye_style='angry'))


@fix('NIDORAN_M')
def nidoran_m(d, look):
    _nquad(d, dict(body='#b47cc8', spot='#7a4a98', earIn='#dcb8e8', spike='#e8d8f0', nose_c='#4a2a58', tooth_c='#f4f0e4',
                   by=49.5, brx=8.6, bry=7.8, blen=10.5, spots=[(28, 47, 0), (37, 49, 0), (33, 45, 0)],
                   q_x=[32, 32, 32, 32], q_d=[-1.0, 4.0, 9.0, 13.5], q_h=4.0, q_r=1.4, leg_r=2.7,
                   hy=41.0, hrx=9.4, hry=8.0, ear_dx=7.6, ear_rx=5.6, ear_ry=8.8, ear_rot=12, horn=6.5, horn_c='#ede0f2',
                   eye_dx=4.4, eye_s=2.6, iris='#c82838'))


@fix('NIDORINO')
def nidorino(d, look):
    _nquad(d, dict(body='#a870c0', spot='#6a3e90', earIn='#d8b0e6', spike='#e4d0ee', nose_c='#4a2a58', tooth_c='#f4f0e4',
                   by=48.5, brx=10.0, bry=9.0, blen=12.0, spots=[(27, 46, 0), (37, 49, 0), (34, 43, 0), (29, 51, 0)],
                   q_x=[32, 32, 32, 32, 32], q_d=[-2.0, 3.0, 8.0, 13.0, 17.5], q_h=6.0, q_r=1.8, leg_r=3.1,
                   hy=39.5, hrx=10.0, hry=8.8, ear_dx=7.8, ear_rx=5.4, ear_ry=8.0, ear_rot=16, horn=9.0, horn_c='#ede0f2',
                   eye_dx=4.7, eye_s=2.6, iris='#c82838', eye_style='angry'))


def _nbiped(d, P):
    """Nidoqueen / Nidoking: bulky upright body, cream belly, ears + horn, back quills, heavy tail."""
    body, bel, spike = P['body'], P['belly'], P['spike']
    parts = []
    parts.append(Stroke('tail', [38, 55, 46, 58, 53, 55, 57, 50], P['tail_w'], body, z=-6, w2=2.0, d1=6, d2=14, cd=0.0))
    parts.append(E('body', 32, P['by'], P['brx'], P['bry'], body, z=0, rd=P['brd']))
    parts.append(E('belly', 32, P['by'] + 2.5, P['brx'] * 0.68, P['bry'] * 0.78, bel, face=True))
    for k in range(P['bands']):
        yy = P['by'] - P['bry'] * 0.35 + k * P['bry'] * 0.42
        parts.append(Stripe('belly', [32 - P['brx'] * 0.6, yy, 32, yy + 1.0, 32 + P['brx'] * 0.6, yy], 0.7, P['band_c']))
    parts += _spines('quill', P['q_x'], P['q_yb'], P['q_yt'], P['q_d'], P['q_r'], spike, cd=0.0, z=-1.0)
    parts += limbs_biped(body, leg_dx=P['leg_dx'], leg_y=51.5, leg_r=P['leg_r'], foot_w=P['foot_w'], foot_l=P['foot_l'],
                         toe_r=P['toe_r'], arm_sx=32 - (P['brx'] + 0.5), arm_y=P['arm_y'], arm_dx=-2.0, arm_l=P['arm_l'],
                         arm_r=P['arm_r'], hand_r=P['arm_r'] * 0.9, fl=2.6, claw=CLAW, arm_ang=12)
    hy = P['hy']
    parts.append(E('head', 32, hy, P['hrx'], P['hry'], body, z=4, rd=P['hry'] + 0.8, cd=-2.0))
    parts.append(E('head', 32, hy + P['hry'] * 0.42, P['hrx'] * 0.56, P['hry'] * 0.5, body, z=4, rd=P['hrx'] * 0.7, d=-5.0, cd=-2.0))
    parts.append(E('nose', 32, hy + P['hry'] * 0.2, 1.6, 1.3, P['nose_c'], z=6, rd=1.4, d=-P['hrx'] * 1.05, cd=-2.0, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * P['ear_dx'], hy - P['hry'] * 0.4, 32 + side * (P['ear_dx'] + 3.4),
                      hy - P['hry'] - P['ear_h'], 4.4, 1.0, body, z=1, cd=-2.0)
    for side in (-1, 1):
        parts.append(Cap('fang', 32 + side * 2.1, hy + P['hry'] * 0.78, 32 + side * 2.1, hy + P['hry'] * 0.78 + 2.2, 0.85, 0.2,
                         '#f4f0e4', z=7, d1=-P['hrx'] * 0.75, d2=-P['hrx'] * 0.75 - 0.7, cd=-2.0))
    if P.get('horn'):
        hl = P['horn']
        parts.append(Cap('horn', 32, hy - P['hry'] * 0.55, 32, hy - P['hry'] * 0.55 - hl, 3.2, 0.4, '#efe6f4', z=7,
                         d1=-P['hrx'] * 0.75, d2=-P['hrx'] * 0.75 - hl * 0.4, cd=-2.0))
    ex = P['eye_dx']
    feats = [Eye(32 - ex, hy - P['hry'] * 0.2, 2.6, '#c82838', look=(0, 0), style='angry', wide=0.9),
             Eye(32 + ex, hy - P['hry'] * 0.2, 2.6, '#c82838', look=(0, 0), style='angry', wide=0.9, flip=True)]
    rebuild(d, parts, features=feats)


@fix('NIDOQUEEN')
def nidoqueen(d, look):
    _nbiped(d, dict(body='#70a0d8', belly='#f0e6c8', band_c='#d8c9a0', spike='#e6eef8', nose_c='#3a4a78',
                    by=41.5, brx=12.4, bry=14.6, brd=10.6, bands=5, tail_w=6.8,
                    q_x=[24.0, 28.0, 32.0, 36.0, 40.0, 21.5, 42.5], q_yb=[24, 21, 20, 21, 24, 32, 32],
                    q_yt=[17.5, 15.0, 14.0, 15.0, 17.5, 26, 26], q_d=[7, 8, 9, 8, 7, 8, 8], q_r=2.4,
                    leg_dx=6.8, leg_r=5.4, foot_w=5.6, foot_l=6.0, toe_r=1.6, arm_y=34.0, arm_l=8.0, arm_r=3.1,
                    hy=21.5, hrx=12.0, hry=10.2, ear_dx=8.0, ear_h=3.0, eye_dx=5.2))


@fix('NIDOKING')
def nidoking(d, look):
    _nbiped(d, dict(body='#9a6cbc', belly='#eadcc4', band_c='#cdbc98', spike='#e8d8f0', nose_c='#3a2048',
                    by=41.0, brx=13.0, bry=15.0, brd=11.0, bands=5, tail_w=8.0, horn=9.5,
                    q_x=[24.0, 28.0, 32.0, 36.0, 40.0, 21.5, 42.5], q_yb=[24, 21, 20, 21, 24, 32, 32],
                    q_yt=[17.0, 14.5, 13.5, 14.5, 17.0, 26, 26], q_d=[7, 8, 9, 8, 7, 8, 8], q_r=2.6,
                    leg_dx=7.2, leg_r=5.8, foot_w=6.0, foot_l=6.4, toe_r=1.7, arm_y=34.0, arm_l=8.5, arm_r=3.4,
                    hy=21.0, hrx=12.4, hry=10.4, ear_dx=8.2, ear_h=2.4, eye_dx=5.4))


# ============================================================================ Sandshrew line
def big_claws(g, x, y, n=3, ln=3.4, r=1.15, spread=1.7, c='#f4f0e2', dz=-2.5, z=3.2, ang=0.0):
    out = []
    a = math.radians(ang)
    ux, uy = math.sin(a), math.cos(a)
    px, py = uy, -ux
    for i in range(n):
        f = i - (n - 1) / 2.0
        sx, sy = x + px * f * spread, y + py * f * spread
        out.append(Cap(g, sx, sy, sx + ux * ln + px * f * 0.5, sy + uy * ln + py * f * 0.5, r, 0.2, c, z=z,
                       d1=dz - abs(f) * 0.2, d2=dz - 1.2 - abs(f) * 0.2, cd=0.0))
    return out


@fix('SANDSHREW')
def sandshrew(d, look):
    body, belly, brick, claw = '#e8cc6a', '#f8eec6', '#b48c2c', '#f4f0e2'
    parts = []
    parts.append(Cap('tail', 36, 54.5, 46, 58.5, 3.6, 1.2, body, z=-6, d1=5.0, d2=10.0, cd=0.0))
    parts.append(E('body', 32, 45.5, 11.4, 12.2, body, z=0, rd=10.2))
    parts.append(E('belly', 32, 48.0, 7.6, 9.4, belly, face=True))
    # the shell-like bands of the back / sides
    for k, yy in enumerate((38.5, 44.5, 50.5)):
        parts.append(Stripe('body', [21.5, yy, 32, yy + 1.4, 42.5, yy], 1.3, brick, backOnly=True))
        parts.append(Stripe('body', [21.0, yy + 0.2, 23.5, yy + 0.8], 1.3, brick))
        parts.append(Stripe('body', [41.0, yy + 0.8, 43.0, yy + 0.2], 1.3, brick))
    parts.append(Stripe('body', [32, 33, 32, 57], 1.3, brick, backOnly=True))
    parts += limbs_biped(body, leg_dx=5.6, leg_y=53.5, leg_r=4.0, foot_w=4.6, foot_l=5.0, toe_r=1.3,
                         arm_sx=21.2, arm_y=39.5, arm_dx=-3.0, arm_l=6.5, arm_r=2.8, hand_r=2.4, n_fing=0, fl=0,
                         claw=CLAW, arm_ang=14)
    for side, g in ((-1, 'armL'), (1, 'armR')):
        hx = 32 + side * (11.2 + 3.0)
        parts += big_claws(g, hx, 47.2, n=3, ln=3.6, r=1.25, spread=1.9, dz=-2.0, ang=-side * 14)
    parts.append(E('head', 32, 28.5, 11.0, 9.6, body, z=4, rd=9.4, cd=-1.5))
    parts.append(E('head', 32, 33.0, 5.8, 4.8, belly, z=4, rd=6.2, d=-5.2, cd=-1.5, frontOnly=True))
    parts.append(E('nose', 32, 31.6, 1.6, 1.3, '#3a3040', z=6, rd=1.4, d=-10.6, cd=-1.5, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 6.6, 22.0, 32 + side * 9.4, 13.5, 3.6, 0.9, body, z=1, cd=-1.5)
    feats = [Eye(27.0, 27.0, 2.5, '#202030', look=(0, 0), sclera=False, style='angry'),
             Eye(37.0, 27.0, 2.5, '#202030', look=(0, 0), sclera=False, style='angry', flip=True),
             Mouth(32.0, 36.0, 1.8, 'smile')]
    rebuild(d, parts, features=feats)


@fix('SANDSLASH')
def sandslash(d, look):
    body, belly, spine, spineL, claw = '#e6c05a', '#f6ebc0', '#94602c', '#bd8446', '#f4f0e2'
    parts = []
    parts.append(Cap('tail', 36, 55.5, 47, 59, 4.0, 1.2, body, z=-6, d1=5.0, d2=11.0, cd=0.0))
    # a great fan of spines behind the body
    fan = [(-19, 34, 0), (-16, 24, 1), (-10, 16, 2), (-3, 12, 3), (5, 12, 3), (12, 16, 2), (18, 24, 1), (21, 34, 0),
           (-20, 44, 0), (22, 44, 0)]
    for i, (dx, yt, kk) in enumerate(fan):
        x0 = 32 + dx * 0.55
        y0 = 32 + abs(dx) * 0.25 if yt < 40 else 40 + i
        col = spine if i % 2 == 0 else spineL
        parts.append(Cap('quill', x0, y0, 32 + dx * 1.05, yt - 2, 3.3, 0.9, col, z=-5 - kk * 0.1,
                         d1=7.0, d2=9.5 + kk, cd=0.0))
    parts.append(E('body', 32, 44.5, 12.4, 13.4, body, z=0, rd=10.8))
    parts.append(E('belly', 32, 47.5, 8.2, 10.4, belly, face=True))
    for k in range(3):
        yy = 39 + k * 5
        parts.append(Stripe('belly', [26.5, yy, 32, yy + 1.2, 37.5, yy], 0.8, '#d2b878'))
    parts += limbs_biped(body, leg_dx=6.2, leg_y=53.0, leg_r=4.6, foot_w=5.0, foot_l=5.6, toe_r=1.4,
                         arm_sx=20.2, arm_y=38.0, arm_dx=-3.0, arm_l=7.6, arm_r=3.2, hand_r=2.7, n_fing=0, fl=0,
                         claw=CLAW, arm_ang=16)
    for side, g in ((-1, 'armL'), (1, 'armR')):
        hx = 32 + side * (12.2 + 3.0)
        parts += big_claws(g, hx, 47.4, n=3, ln=4.2, r=1.4, spread=2.1, dz=-2.0, ang=-side * 16)
    parts.append(E('head', 32, 26.5, 11.4, 9.6, body, z=4, rd=9.4, cd=-1.5))
    parts.append(E('head', 32, 31.2, 5.6, 4.8, belly, z=4, rd=6.6, d=-5.6, cd=-1.5, frontOnly=True))
    parts.append(E('nose', 32, 29.6, 1.7, 1.4, '#3a3040', z=6, rd=1.5, d=-11.4, cd=-1.5, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 6.8, 20.0, 32 + side * 9.6, 11.0, 3.8, 1.0, body, z=1, cd=-1.5)
    feats = [Eye(27.0, 25.0, 2.5, '#202030', look=(0, 0), sclera=False, style='angry'),
             Eye(37.0, 25.0, 2.5, '#202030', look=(0, 0), sclera=False, style='angry', flip=True),
             Mouth(32.0, 34.0, 2.0, 'smile')]
    rebuild(d, parts, features=feats)


def hint(look, chains=None, roles=None):
    """Rig hints for this species (the look dict is the one gen_pokemon later reads `chains` / `roles` from)."""
    if look is None:
        return
    if chains:
        look.setdefault('chains', {}).update(chains)
    if roles:
        look.setdefault('roles', {}).update(roles)


# ============================================================================ serpents
def ring(g, cx, cy, cz, R, r, c, n=16, z=0.0, a0=0.0, a1=360.0, ry=None, **kw):
    """A torus-like coil made of overlapping spheres, lying flat (x-depth plane) at height cy."""
    out = []
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / float(n if a1 - a0 >= 360 else n - 1))
        out.append(E(g, cx + R * math.cos(a), cy, r, ry or r, c, z=z, rd=r, d=cz + R * math.sin(a), solid=True, **kw))
    return out


@fix('EKANS')
def ekans(d, look):
    body, band, belly = '#a070c0', '#f0d050', '#f4e4a8'
    parts = []
    # coiled body: two stacked rings (anchor group), front arc lighter underneath
    parts += ring('body', 32, 55.0, 4.0, 10.5, 4.7, body, n=18, z=0)
    parts += ring('body', 32, 48.5, 3.0, 8.0, 4.3, body, n=16, z=0.1)
    parts += ring('body', 32, 43.0, 2.0, 4.0, 4.0, body, n=8, z=0.2)
    for yy in (52.5, 57.0):
        parts.append(Stripe('body', [27, yy, 32, yy + 1.0, 37, yy], 1.3, belly, face=True))
    # tail with a yellow rattle-like tip poking out behind the coil
    parts.append(Stroke('tail', [40, 56, 47, 55, 52, 50, 53, 44], 5.0, body, z=-4, w2=2.0, d1=6.0, d2=9.0, cd=0.0))
    parts.append(E('tail', 53.5, 42.0, 2.4, 3.6, band, z=-3.9, rd=2.4, d=9.5, solid=True, cd=0.0))
    parts.append(Stripe('tail', [50.5, 42, 56.5, 42], 0.7, '#b89020'))
    # rising neck (S curve) with a pale throat and a yellow collar
    parts.append(Stroke('neck', [33, 48, 30, 41, 32, 34, 33.5, 28], 8.4, body, z=1, w2=7.0, d1=-5.0, d2=-7.0, cd=0.0))
    parts.append(Stripe('neck', [33, 47, 31.5, 41, 33, 34.5], 3.6, belly, face=True))
    parts.append(Stripe('neck', [28.5, 30.5, 38.5, 30.5], 2.4, band, face=True))
    parts.append(E('head', 33.5, 23.0, 6.8, 5.6, body, z=3, rd=6.0, cd=-7.5))
    parts.append(E('head', 33.5, 26.0, 4.2, 3.4, body, z=3, rd=4.6, d=-4.4, cd=-7.5))
    parts.append(Spot('head', 33.5, 27.6, 3.0, 1.4, belly, face=True))
    feats = [Eye(29.6, 21.6, 1.9, '#e8c030', look=(0, 0), style='angry', wide=1.0),
             Eye(37.4, 21.6, 1.9, '#e8c030', look=(0, 0), style='angry', wide=1.0, flip=True),
             Mouth(33.5, 28.6, 2.0, 'tongue')]
    rebuild(d, parts, features=feats)
    hint(look, chains={'body': 1, 'neck': 3, 'tail': 4})


@fix('ARBOK')
def arbok(d, look):
    body, belly, red, yel, blk = '#8a5cac', '#f0dc98', '#d83838', '#f0d040', '#282030'
    parts = []
    parts += ring('body', 32, 55.5, 4.0, 13.0, 5.4, body, n=22, z=0)
    parts += ring('body', 32, 48.0, 3.0, 10.0, 5.0, body, n=18, z=0.1)
    parts += ring('body', 32, 41.5, 2.0, 6.0, 4.8, body, n=10, z=0.2)
    for yy in (53.0, 59.0):
        parts.append(Stripe('body', [26, yy, 32, yy + 1.0, 38, yy], 1.5, belly, face=True))
    parts.append(Stroke('tail', [42, 57, 50, 56, 56, 50, 57, 42], 6.4, body, z=-4, w2=1.5, d1=7.0, d2=10.0, cd=0.0))
    parts.append(Stroke('neck', [32, 44, 31, 36, 32, 28], 11.5, body, z=1, w2=10.0, d1=-4.0, d2=-6.0, cd=0.0))
    # the wide hood with its fierce face pattern
    parts.append(E('hood', 32, 24.0, 14.6, 15.0, body, z=2, rd=4.6, d=-1.0, cd=-6.0, solid=True))
    parts.append(Spot('hood', 32, 31.5, 5.6, 6.2, red, face=True))
    parts.append(Spot('hood', 24.5, 22.5, 3.4, 2.4, yel, face=True))
    parts.append(Spot('hood', 39.5, 22.5, 3.4, 2.4, yel, face=True))
    parts.append(Stripe('hood', [20.5, 21, 25.5, 16.5, 30.5, 20.5], 1.7, blk, face=True))
    parts.append(Stripe('hood', [43.5, 21, 38.5, 16.5, 33.5, 20.5], 1.7, blk, face=True))
    parts.append(Stripe('hood', [22, 35.5, 26.5, 40.5, 32, 42, 37.5, 40.5, 42, 35.5], 1.9, blk, face=True))
    parts.append(Stripe('hood', [25.5, 32.5, 28.5, 36.5], 2.6, yel, face=True))
    parts.append(Stripe('hood', [38.5, 32.5, 35.5, 36.5], 2.6, yel, face=True))
    parts.append(Spot('hood', 32, 13.0, 1.4, 1.4, red, face=True))
    parts.append(E('head', 32, 10.5, 9.0, 7.0, body, z=4, rd=7.4, cd=-8.5))
    parts.append(E('head', 32, 14.2, 5.8, 4.2, body, z=4, rd=5.6, d=-5.4, cd=-8.5))
    parts.append(Spot('head', 32, 15.6, 3.4, 1.4, belly, face=True))
    for side in (-1, 1):
        parts.append(Cap('fang', 32 + side * 2.3, 15.4, 32 + side * 2.3, 18.0, 0.9, 0.2, '#f4f0e2', z=7, d1=-9.0, d2=-9.4, cd=-8.5))
    feats = [Eye(27.6, 9.4, 2.4, '#e8c030', look=(0, 0), style='angry', wide=1.0),
             Eye(36.4, 9.4, 2.4, '#e8c030', look=(0, 0), style='angry', wide=1.0, flip=True)]
    rebuild(d, parts, features=feats)
    hint(look, chains={'body': 1, 'neck': 3, 'tail': 4})


# ============================================================================ foxes
def tail_fan(names, base, angles, L, w0, w1, c, tipc=None, curl=0.0, depth=(12.0, 14.0), z=-4.0, wave=0.0, tip_r=2.6):
    """A fan of tails behind the body: each one leaves `base` at `ang` degrees from vertical, curling by `curl`."""
    out = []
    for i, (nm, ang) in enumerate(zip(names, angles)):
        a = math.radians(ang)
        sgn = 1.0 if ang >= 0 else -1.0
        mx, my = base[0] + L * 0.5 * math.sin(a), base[1] - L * 0.5 * math.cos(a)
        a2 = a - math.radians(curl) * sgn + math.radians(wave) * (1 if i % 2 else -1)
        tx, ty = mx + L * 0.5 * math.sin(a2), my - L * 0.5 * math.cos(a2)
        out.append(Stroke(nm, [base[0], base[1], mx, my, tx, ty], w0, c, z=z - i * 0.05, w2=w1, d1=depth[0], d2=depth[1],
                          cd=0.0))
        if tipc:
            out.append(Spot(nm, tx, ty, tip_r, tip_r, tipc))
    return out


def _fox_legs(body, paw, by, leg_r=2.7, front=4.5, back=8.5, gnd=58.6, top_f=None):
    out = []
    for side, g in ((-1, 'legFL'), (1, 'legFR')):
        out.append(Cap(g, 32 + side * 4.8, top_f or by + 3.0, 32 + side * 5.0, gnd - 0.6, leg_r, leg_r * 0.82, body, z=2, cd=-front))
        out.append(E(g, 32 + side * 5.2, gnd, 3.0, 1.6, paw, z=2.1, rd=3.8, d=-1.2, cd=-front))
    for side, g in ((-1, 'legBL'), (1, 'legBR')):
        out.append(Cap(g, 32 + side * 5.6, by + 1.5, 32 + side * 5.8, gnd - 0.6, leg_r * 1.2, leg_r * 0.85, body, z=2, cd=back))
        out.append(E(g, 32 + side * 5.8, gnd, 3.2, 1.6, paw, z=2.1, rd=4.0, d=-1.2, cd=back))
    return out


@fix('VULPIX')
def vulpix(d, look):
    body, tail, curl, paw, inner = '#cc5c34', '#e87838', '#f4a050', '#f0d4a4', '#6a3020'
    parts = []
    parts += tail_fan(['t1', 't2', 't3', 't4', 't5', 't6'], (32, 47.0), [-104, -64, -24, 24, 64, 104], 23.0, 8.0, 3.4, tail,
                      tipc=curl, curl=100, depth=(10.0, 13.0), tip_r=2.8)
    parts.append(E('body', 32, 49.0, 8.8, 7.4, body, z=0, rd=10.0, d=4.0, cd=0.0))
    parts.append(E('chest', 32, 47.5, 4.8, 4.6, paw, z=0.5, rd=5.0, d=-5.0, cd=0.0, frontOnly=True))
    parts += _fox_legs(body, paw, 49.0)
    hy = 39.5
    parts.append(E('head', 32, hy, 9.4, 7.8, body, z=4, rd=8.0, cd=-8.5))
    parts.append(E('head', 32, hy + 3.6, 3.9, 3.2, body, z=4, rd=5.2, d=-6.0, cd=-8.5))
    parts.append(E('nose', 32, hy + 2.6, 1.3, 1.1, '#2a1a18', z=6, rd=1.2, d=-11.6, cd=-8.5, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 6.2, hy - 4.0, 32 + side * 10.2, hy - 17.5, 4.8, 0.8, body, z=1, cd=-8.5)
        parts.append(Spot(g, 32 + side * 7.6, hy - 8.5, 1.6, 3.6, inner, face=True))
    # curly forelock on the forehead
    parts.append(head_curl('tuft', 27.5, hy - 8.0, curl, w=3.4, s=1.05, d=-8.5, cd=-8.5))
    feats = [Eye(27.4, hy - 0.8, 2.7, '#7a4020', look=(0, 0), sclera=False), Eye(36.6, hy - 0.8, 2.7, '#7a4020', look=(0, 0), sclera=False)]
    rebuild(d, parts, features=feats)


@fix('NINETALES')
def ninetales(d, look):
    body, tip, mane, paw, inner = '#f2e2a4', '#ee9a44', '#fbf3d0', '#e4c888', '#c89858'
    parts = []
    names = ['nt%d' % i for i in range(9)]
    parts += tail_fan(names, (32, 44.0), [-92, -70, -48, -26, 0, 26, 48, 70, 92], 26.0, 8.0, 3.0, body, tipc=tip,
                      curl=-10, depth=(11.0, 13.0), wave=14, tip_r=3.0)
    parts.append(E('body', 32, 46.0, 8.8, 7.8, body, z=0, rd=11.0, d=4.0, cd=0.0))
    parts += _fox_legs(body, paw, 46.0, leg_r=2.8, gnd=58.6, top_f=48.0)
    # long neck with a fluffy mane
    parts.append(Cap('neck', 32, 44.0, 32, 33.0, 6.0, 4.8, body, z=3, d1=-4.0, d2=-7.0, cd=0.0))
    parts.append(E('mane', 32, 39.0, 7.4, 6.4, mane, z=3.5, rd=6.0, d=-9.0, cd=0.0, frontOnly=True))
    hy = 30.5
    parts.append(E('head', 32, hy, 8.4, 7.2, body, z=4, rd=7.4, cd=-8.5))
    parts.append(E('head', 32, hy + 3.8, 3.7, 3.2, body, z=4, rd=5.4, d=-6.2, cd=-8.5))
    parts.append(E('nose', 32, hy + 3.0, 1.3, 1.1, '#1b1a2e', z=6, rd=1.2, d=-12.0, cd=-8.5, solid=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 5.6, hy - 3.8, 32 + side * 9.4, hy - 15.5, 4.4, 0.8, body, z=1, cd=-8.5)
        parts.append(Spot(g, 32 + side * 6.8, hy - 8.5, 1.5, 3.4, inner, face=True))
    # swept-back crest and cheek tufts
    for i, (dx, L) in enumerate([(-3.0, 9.0), (0.0, 11.0), (3.0, 9.0)]):
        parts.append(Cap('crest', 32 + dx, hy - 6.0, 32 + dx * 1.6, hy - 6.0 - L * 0.6, 2.6, 0.5, mane, z=6, d1=-5.0,
                         d2=-2.0 + L * 0.5, cd=-8.5))
    for side, g in ((-1, 'cheekL'), (1, 'cheekR')):
        parts.append(Cap(g, 32 + side * 6.4, hy + 2.5, 32 + side * 11.0, hy + 6.0, 2.6, 0.4, mane, z=6, d1=-4.0, d2=-2.0, cd=-8.5))
    feats = [Eye(27.6, hy - 0.4, 2.5, '#c82828', look=(0, 0), style='angry'),
             Eye(36.4, hy - 0.4, 2.5, '#c82828', look=(0, 0), style='angry', flip=True)]
    rebuild(d, parts, features=feats)


# ============================================================================ bats
@fix('ZUBAT')
def zubat(d, look):
    body, mem, inner = '#5a9ad8', '#a872c8', '#9a5ab8'
    parts = []
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        parts += batwing(g, side, (m(37), 32), (m(46), 20), [(m(62), 8), (m(63), 22), (m(56), 34)], mem, body,
                         back=(m(39), 40), cd=4.0, z=-3, bone_r=1.5, T=1.0, scallop=0.34)
    parts.append(E('body', 32, 34.0, 8.6, 9.0, body, z=0, rd=8.0))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 5.0, 28.0, 32 + side * 9.4, 10.0, 4.4, 1.0, body, z=1, cd=-1.0)
        parts.append(Spot(g, 32 + side * 6.4, 20.5, 1.7, 4.8, inner, face=True))
    parts.append(E('mouth', 32, 38.0, 4.6, 3.4, '#7a1c2c', z=1.5, face=True))
    for side in (-1, 1):
        parts.append(Cap('fang', 32 + side * 2.6, 37.0, 32 + side * 2.6, 40.6, 1.0, 0.2, '#f4f0e2', z=7, d1=-7.4, d2=-7.8, cd=0.0))
    # spindly legs with little clawed feet
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(Cap(g, 32 + side * 3.0, 41.0, 32 + side * 3.6, 53.5, 1.7, 1.5, body, z=2, cd=-1.0))
        parts += foot(g, 32 + side * 3.8, 57.0, body, w=2.0, ln=2.6, n=3, dz=-1.0, toe_r=0.8, z=2.2, claw=CLAW)
    rebuild(d, parts, features=[])


@fix('GOLBAT')
def golbat(d, look):
    body, mem, inner = '#5a9ad8', '#a872c8', '#9a5ab8'
    parts = []
    for side, g in ((-1, 'wingL'), (1, 'wingR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        parts += batwing(g, side, (m(41), 30), (m(51), 15), [(m(66), 2), (m(68), 20), (m(60), 38)], mem, body,
                         back=(m(43), 44), cd=6.0, z=-3, bone_r=1.8, T=1.2, scallop=0.34)
    parts.append(E('body', 32, 35.0, 12.6, 12.4, body, z=0, rd=11.0))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * 7.0, 26.0, 32 + side * 11.4, 9.0, 4.6, 1.0, body, z=1, cd=-1.0)
        parts.append(Spot(g, 32 + side * 8.4, 19.0, 1.7, 4.4, inner, face=True))
    parts.append(E('mouth', 32, 40.5, 8.8, 7.4, '#7a1c2c', z=1.5, face=True))
    parts.append(Spot('mouth', 32, 45.0, 6.2, 2.8, '#e0607a', face=True))
    for x, y, L in ((24.5, 36.0, 4.0), (39.5, 36.0, 4.0), (28.5, 47.2, 3.4), (35.5, 47.2, 3.4)):
        parts.append(Cap('fang', x, y, x, y + (L if y < 40 else -L), 1.3, 0.25, '#f4f0e2', z=7, d1=-10.4, d2=-10.8, cd=0.0))
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(Cap(g, 32 + side * 5.0, 45.0, 32 + side * 5.6, 54.0, 2.4, 2.0, body, z=2, cd=-1.0))
        parts += foot(g, 32 + side * 5.8, 58.0, body, w=2.8, ln=3.2, n=3, dz=-1.0, toe_r=1.0, z=2.2, claw=CLAW)
    feats = [Eye(26.5, 32.0, 2.1, '#c03040', look=(0, 0), style='angry', wide=1.0),
             Eye(37.5, 32.0, 2.1, '#c03040', look=(0, 0), style='angry', wide=1.0, flip=True)]
    rebuild(d, parts, features=feats)


# ============================================================================ Oddish line
def leaf_plate(g, x, y, ang, L, w, c, vein, z=-1.0, T=1.5, cd=0.0, bend=0.0, d0=0.0):
    """A broad pointed leaf from its base (x, y), pointing `ang` degrees from straight up (+ = right), midrib painted on."""
    a = math.radians(ang)
    dx, dy = math.sin(a), -math.cos(a)
    px, py = -dy, dx
    def pt(t, s):
        return (x + dx * L * t + px * w * s + px * bend * t * t * L, y + dy * L * t + py * w * s + py * bend * t * t * L)
    prof = [(0.0, 0.0), (0.25, 0.75), (0.55, 1.0), (0.82, 0.62), (1.0, 0.0), (0.82, -0.62), (0.55, -1.0), (0.25, -0.75)]
    pts = []
    for t, s in prof:
        pts += list(pt(t, s * 0.5))
    out = [Poly(g, pts, c, z=z, T=T, cd=cd)]
    p0, p1 = pt(0.06, 0), pt(0.92, 0)
    out.append(Stripe(g, [p0[0], p0[1], p1[0], p1[1]], 0.9, vein))
    return out


def petals(g, cx, cy, cz, R, n, rx, ry, rd, c, dot=None, tilt=0.35, z=0.0, a0=0.0, dot_c=None, cd=0.0):
    """A ring of flattened petals tilted toward the viewer (front petals lower)."""
    out = []
    for i in range(n):
        a = math.radians(a0 + 360.0 * i / n)
        px = cx + R * math.cos(a)
        pz = cz + R * math.sin(a)
        py = cy - tilt * R * math.sin(a)
        out.append(E(g, px, py, rx, ry, c, z=z, rd=rd, d=pz, solid=True, cd=cd))
    return out


@fix('ODDISH')
def oddish(d, look):
    body, leaf, vein, foot = '#4a6cb0', '#4fae44', '#36782e', '#3c5898'
    parts = []
    # five leaves fanned out of the top
    for ang, L, w, dd in ((-64, 15.0, 9.0, 1.0), (-32, 19.0, 9.0, 3.0), (0, 20.0, 9.5, 5.0), (32, 19.0, 9.0, 3.0), (64, 15.0, 9.0, 1.0)):
        parts += leaf_plate('lf%d' % (int(ang) + 64), 32 + ang * 0.10, 35.0, ang, L, w, leaf, vein, z=-1, T=1.6, cd=dd, bend=0.05 * (1 if ang >= 0 else -1))
    parts.append(E('body', 32, 45.0, 13.4, 12.8, body, z=0, rd=12.0))
    for side, g in ((-1, 'footL'), (1, 'footR')):
        parts.append(E(g, 32 + side * 6.4, 57.4, 4.6, 2.6, foot, z=2, rd=5.4, d=-3.0, cd=-2.0))
        parts += toes(g, 32 + side * 6.4, 58.2, n=3, spread=2.4, r=1.25, dz=-8.0, c=foot, claw=None, z=2.1, cd=-2.0)
    feats = [Eye(26.4, 44.6, 2.7, '#c02830', look=(0, 0), sclera=True, wide=0.9),
             Eye(37.6, 44.6, 2.7, '#c02830', look=(0, 0), sclera=True, wide=0.9),
             Mouth(32.0, 50.2, 1.7, 'smile')]
    rebuild(d, parts, features=feats)


def _plant_body(body, foot, by=45.5, brx=12.0, bry=11.4, arms=True, arm_l=7.0):
    parts = [E('body', 32, by, brx, bry, body, z=0, rd=brx - 0.6)]
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(Cap(g, 32 + side * 6.0, by + bry * 0.55, 32 + side * 6.2, 55.5, 3.6, 3.2, body, z=2, cd=-1.0))
        parts.append(E(g, 32 + side * 6.4, 58.0, 4.8, 2.6, foot, z=2.1, rd=5.4, d=-2.5, cd=-1.0))
        parts += toes(g, 32 + side * 6.4, 58.8, n=3, spread=2.5, r=1.25, dz=-7.5, c=foot, claw=None, z=2.2, cd=-1.0)
    if arms:
        for side, g in ((-1, 'armL'), (1, 'armR')):
            parts.append(Cap(g, 32 + side * (brx - 1.0), by - 3.0, 32 + side * (brx + 3.6), by - 3.0 + arm_l, 2.9, 2.5, body, z=3, cd=-3.0))
            parts += hand(g, 32 + side * (brx + 3.8), by - 3.0 + arm_l + 0.8, body, r=2.3, n=3, ang=-side * 8, fl=1.7, fr=0.8, claw=None, z=3.1)
    return parts


@fix('GLOOM')
def gloom(d, look):
    body, foot, petal, dot, leaf = '#4a6cb0', '#3c5898', '#c4503c', '#eeb878', '#5cb048'
    parts = _plant_body(body, foot, by=46.5, brx=12.6, bry=11.6)
    # the big red drooping flower on its head
    parts += petals('flower', 32, 29.5, 0.0, 10.5, 5, 8.2, 4.4, 8.2, petal, tilt=0.36, z=1, a0=-90)
    parts.append(E('flower', 32, 29.5, 8.0, 5.0, '#a03c30', z=1.2, rd=8.0, solid=True))
    parts.append(E('ctr', 32, 27.0, 4.6, 3.4, '#8a3028', z=2, rd=4.6, d=-1.5, solid=True))
    for x, y in ((21.5, 31.5), (43, 31.5), (27, 36.0), (37.5, 36.0), (32, 22.0), (26, 26.0), (38.5, 26.0)):
        parts.append(Spot('flower', x, y, 1.9, 1.5, dot))
    for side, g in ((-1, 'lfL'), (1, 'lfR')):
        parts += leaf_plate(g, 32 + side * 7.0, 39.0, side * 78, 11.0, 6.0, leaf, '#36782e', z=0.1, T=1.3, cd=-1.0)
    parts.append(Cap('drool', 28.0, 50.5, 28.0, 55.0, 1.0, 1.7, '#f4e27a', z=6, d1=-10.5, d2=-10.8, cd=0.0))
    feats = [Eye(26.0, 43.4, 2.7, '#c02830', look=(0, 0), style='sleepy'),
             Eye(38.0, 43.4, 2.7, '#c02830', look=(0, 0), style='sleepy'),
             Mouth(30.0, 48.8, 2.4, 'open')]
    rebuild(d, parts, features=feats)


@fix('VILEPLUME')
def vileplume(d, look):
    body, foot, petal, dot = '#4a6cb0', '#3c5898', '#e04a3c', '#fad0c4'
    parts = _plant_body(body, foot, by=46.5, brx=10.6, bry=10.4, arm_l=6.5)
    # a huge rafflesia bloom: ring of big spotted petals around a purple centre
    parts += petals('flower', 32, 26.5, 0.0, 14.0, 6, 11.0, 4.8, 10.0, petal, tilt=0.42, z=1, a0=-90)
    parts.append(E('flower', 32, 27.0, 12.0, 6.4, '#c0382e', z=1.2, rd=11.0, solid=True))
    parts.append(E('ctr', 32, 24.0, 8.6, 5.6, '#5a3a78', z=2, rd=8.6, d=-2.0, solid=True))
    for x, y in ((26, 22), (34, 20), (38, 25), (28, 27), (33, 26), (31, 23)):
        parts.append(Spot('ctr', x, y, 1.2, 0.9, '#e8c8f0'))
    for x, y in ((14, 29), (50, 29), (20, 36), (44, 36), (32, 37), (13, 24), (51, 24), (24, 17), (40, 17), (32, 13.5)):
        parts.append(Spot('flower', x, y, 2.3, 1.7, dot))
    feats = [Eye(27.0, 43.0, 2.7, '#c02830', look=(0, 0), style='angry'),
             Eye(37.0, 43.0, 2.7, '#c02830', look=(0, 0), style='angry', flip=True),
             Mouth(32.0, 49.0, 1.6, 'smile')]
    rebuild(d, parts, features=feats)


# ============================================================================ Diglett, Paras line, Venonat line
def _inset(pts, k):
    """Shrink a flat [x, y, ...] polygon toward its centroid by factor k (0..1 kept)."""
    xs, ys = pts[0::2], pts[1::2]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    out = []
    for x, y in zip(xs, ys):
        out += [cx + (x - cx) * k, cy + (y - cy) * k]
    return out


def bordered_wing(g, pts, border, fill, vein=None, veins=(), z=-3.0, T=1.1, cd=5.0, k=0.8):
    """A wing plate with a dark border: outer plate in `border`, inner polygon painted on it in `fill`."""
    out = [Poly(g, pts, border, z=z, T=T, cd=cd)]
    inner = {'t': 'p', 'pts': _inset(pts, k), 'c': fill, 'on': g}
    out.append(inner)
    for vp in veins:
        out.append(Stripe(g, vp, 0.8, vein or border))
    return out


@fix('DIGLETT')
def diglett(d, look):
    body, nose, dirt, rock = '#b0703e', '#f07a92', '#8a6440', '#a8988a'
    parts = []
    parts.append(E('body', 32, 42.0, 9.6, 14.0, body, z=0, rd=9.4))
    # ring of loose earth around the base
    for i in range(12):
        a = 2 * math.pi * i / 12
        parts.append(E('dirt', 32 + 14.5 * math.cos(a), 56.6 - 0.6 * math.sin(a), 5.0, 3.6, dirt, z=1, rd=5.2,
                       d=13.0 * math.sin(a), solid=True, cd=0.0))
    parts.append(E('dirt', 32, 57.5, 15.0, 3.6, dirt, z=1, rd=14.0, solid=True, cd=0.0))
    for x, y, dd, r in ((17.5, 58.5, -6, 2.2), (46.5, 58.8, -3, 2.0), (39.0, 60.0, -12, 1.6)):
        parts.append(E('rk', x, y, r, r * 0.75, rock, z=1.5, rd=r, d=dd, solid=True, cd=0.0))
    parts.append(E('nose', 32, 46.5, 4.6, 4.0, nose, z=3, rd=4.2, d=-9.6, cd=0.0, solid=True))
    feats = [Eye(27.6, 38.0, 2.3, '#101018', look=(0, 0), sclera=False), Eye(36.4, 38.0, 2.3, '#101018', look=(0, 0), sclera=False)]
    rebuild(d, parts, features=feats)


def _crab_legs(body, n=3, x0=8.0, y0=54.0, dx=2.4, ln=5.0, r=1.7, cd=1.0, bside=None):
    out = []
    for side, gs in ((-1, 'L'), (1, 'R')):
        for i in range(n):
            g = 'leg%s%d' % (gs, i)
            x = 32 + side * (x0 + i * dx)
            dd = -4.0 + i * 5.0
            out.append(Cap(g, x, y0 - 1.0, x + side * 2.4, y0 + ln, r, r * 0.6, body, z=2, cd=dd))
    return out


@fix('PARAS')
def paras(d, look):
    body, cap, dot, claw, eye = '#f0903c', '#e44a30', '#fad870', '#faeac8', '#f8eed6'
    parts = []
    parts += _crab_legs(body, n=3, x0=7.5, y0=53.5, dx=3.0, ln=5.0, r=1.9)
    parts.append(E('body', 32, 47.5, 12.4, 8.6, body, z=0, rd=10.5, d=2.0, cd=0.0))
    parts.append(Stripe('body', [24, 41, 25, 55], 1.0, '#c86828', backOnly=True))
    parts.append(Stripe('body', [40, 41, 39, 55], 1.0, '#c86828', backOnly=True))
    # head + big round eyes
    parts.append(E('head', 32, 48.0, 9.0, 7.4, body, z=4, rd=7.8, cd=-8.5))
    # two mushrooms growing from the back
    parts.append(Cap('stemA', 25.5, 42.0, 25.0, 34.0, 3.0, 2.6, '#f4dcb0', z=1, d1=3.0, d2=3.0, cd=0.0))
    parts.append(E('capA', 25.0, 33.0, 9.0, 5.8, cap, z=2, rd=8.6, d=3.0, rot=-6, cd=0.0, solid=True))
    parts.append(Cap('stemB', 40.5, 42.0, 41.0, 33.0, 3.2, 2.8, '#f4dcb0', z=1, d1=4.0, d2=4.0, cd=0.0))
    parts.append(E('capB', 41.0, 31.5, 10.6, 6.8, cap, z=2, rd=10.0, d=4.0, rot=6, cd=0.0, solid=True))
    for x, y in ((22, 30), (28, 32), (25, 35), (38, 28), (45, 30), (42, 34), (48, 33)):
        parts.append(Spot('capA' if x < 32 else 'capB', x, y, 1.7, 1.3, dot))
    # claws
    for side, g in ((-1, 'armL'), (1, 'armR')):
        parts.append(Cap(g, 32 + side * 11.0, 49.0, 32 + side * 15.2, 54.5, 3.2, 2.8, body, z=3, cd=-6.0))
        parts.append(E(g, 32 + side * 15.6, 56.2, 4.4, 3.8, claw, z=3.1, rd=3.6, d=-1.5, cd=-6.0, solid=True))
        parts.append(Cap(g, 32 + side * 14.2, 58.0, 32 + side * 12.6, 60.4, 1.3, 0.3, claw, z=3.2, d1=-2.0, d2=-3.0, cd=-6.0))
        parts.append(Cap(g, 32 + side * 17.0, 58.4, 32 + side * 17.8, 61.0, 1.3, 0.3, claw, z=3.2, d1=-2.0, d2=-3.0, cd=-6.0))
    feats = [Eye(27.0, 47.0, 3.4, '#f0e2b8', look=(0, 0), sclera=True, wide=0.85),
             Eye(37.0, 47.0, 3.4, '#f0e2b8', look=(0, 0), sclera=True, wide=0.85)]
    rebuild(d, parts, features=feats)


@fix('PARASECT')
def parasect(d, look):
    body, cap, dot, claw, eye = '#ec8a3a', '#e05432', '#fad880', '#faeac8', '#f8f4e8'
    parts = []
    parts += _crab_legs(body, n=3, x0=8.0, y0=52.0, dx=3.2, ln=6.5, r=2.0)
    parts.append(E('body', 32, 46.0, 11.2, 8.0, body, z=0, rd=10.0, d=2.0, cd=0.0))
    parts.append(E('head', 32, 47.0, 8.0, 6.6, body, z=4, rd=7.4, cd=-8.0))
    # the giant mushroom on its back
    parts.append(E('cap', 32, 28.0, 25.0, 14.5, cap, z=2, rd=19.0, d=2.0, cd=0.0, solid=True))
    parts.append(E('gills', 32, 38.5, 21.0, 4.0, '#f4c890', z=2.2, rd=16.0, d=1.0, cd=0.0, frontOnly=True))
    for x, y in ((14, 24), (24, 15), (33, 12), (43, 15), (52, 22), (20, 32), (32, 24), (44, 30), (54, 32), (10, 32), (28, 33)):
        parts.append(Spot('cap', x, y, 3.0 if y < 26 else 2.4, 2.3 if y < 26 else 1.8, dot))
    for side, g in ((-1, 'armL'), (1, 'armR')):
        parts.append(Cap(g, 32 + side * 10.0, 48.0, 32 + side * 15.6, 55.0, 3.4, 3.0, body, z=3, cd=-6.0))
        parts.append(E(g, 32 + side * 16.2, 57.0, 4.8, 4.0, claw, z=3.1, rd=4.0, d=-1.5, cd=-6.0, solid=True))
        parts.append(Cap(g, 32 + side * 14.6, 59.2, 32 + side * 13.0, 62.0, 1.4, 0.3, claw, z=3.2, d1=-2.0, d2=-3.0, cd=-6.0))
        parts.append(Cap(g, 32 + side * 18.0, 59.6, 32 + side * 18.8, 62.4, 1.4, 0.3, claw, z=3.2, d1=-2.0, d2=-3.0, cd=-6.0))
    feats = [Eye(28.0, 46.0, 3.0, '#f0e6c4', look=(0, 0), sclera=True, wide=0.9),
             Eye(36.0, 46.0, 3.0, '#f0e6c4', look=(0, 0), sclera=True, wide=0.9)]
    rebuild(d, parts, features=feats)


@fix('VENONAT')
def venonat(d, look):
    body, fur, eye, eyel, mand, foot = '#8a5cb8', '#7a4ca8', '#e8404a', '#ff9a9a', '#eeeaea', '#6a4090'
    parts = []
    parts.append(E('body', 32, 42.0, 13.4, 13.2, body, z=0, rd=12.4))
    # fuzzy tufts around the silhouette
    for i in range(14):
        a = math.radians(-180 + 360.0 * i / 14)
        sx, sy = 32 + 12.8 * math.cos(a), 42 + 12.6 * math.sin(a)
        if sy > 50:
            continue
        parts.append(Cap('fuzz', sx, sy, 32 + 16.4 * math.cos(a), 42 + 16.2 * math.sin(a), 2.0, 0.3, fur, z=-1,
                         d1=0.0, d2=0.0, cd=0.0))
    for side, g in ((-1, 'eyeL'), (1, 'eyeR')):
        parts.append(E(g, 32 + side * 7.4, 39.0, 5.8, 6.4, eye, z=3, rd=5.0, d=-8.6, cd=0.0, solid=True))
        parts.append(Spot(g, 32 + side * 8.6, 36.6, 2.0, 2.2, eyel, face=True))
        parts.append(Spot(g, 32 + side * 5.6, 41.4, 1.0, 1.0, '#a01828', face=True))
    for side, g in ((-1, 'antL'), (1, 'antR')):
        parts.append(Stroke(g, [32 + side * 4.0, 31.5, 32 + side * 6.4, 25.0, 32 + side * 9.5, 21.0], 1.5, fur, z=2, w2=1.1,
                            d1=-6.0, d2=-3.0, cd=0.0))
        parts.append(E(g, 32 + side * 9.8, 20.4, 1.9, 1.9, body, z=2, rd=1.9, d=-3.0, cd=0.0, solid=True))
    for side in (-1, 1):
        parts.append(Cap('mand', 32 + side * 2.2, 49.0, 32 + side * 2.8, 53.6, 1.2, 0.3, mand, z=6, d1=-11.5, d2=-11.8, cd=0.0))
    for side, g in ((-1, 'footL'), (1, 'footR')):
        parts.append(E(g, 32 + side * 6.6, 57.2, 4.6, 2.6, foot, z=2, rd=5.4, d=-3.0, cd=-1.0))
        parts += toes(g, 32 + side * 6.6, 58.0, n=3, spread=2.4, r=1.2, dz=-8.0, c=foot, claw=None, z=2.1, cd=-1.0)
    rebuild(d, parts, features=[Mouth(32.0, 49.0, 1.5, 'smile')])


@fix('VENOMOTH')
def venomoth(d, look):
    body, wing, vein, spot, eye, eyel, leg = '#9a72c4', '#c6aae6', '#a888d0', '#7c58ac', '#4a8ad4', '#a8d4ff', '#e8dcf4'
    parts = []
    for side, gu, gl in ((-1, 'wingUL', 'wingLL'), (1, 'wingUR', 'wingLR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        up = [m(37), 30, m(43), 13, m(53), 3, m(62), 6, m(64), 16, m(58), 26, m(47), 33]
        parts.append(Poly(gu, up, wing, z=-3, T=1.1, cd=5.0))
        parts.append(Spot(gu, m(58), 10, 3.4, 2.7, spot))
        parts.append(Spot(gu, m(51), 8, 1.8, 1.4, spot))
        parts.append(Spot(gu, m(59), 19, 1.8, 1.4, spot))
        parts.append(Stripe(gu, [m(38), 29, m(50), 13, m(59), 8], 0.8, vein))
        lo = [m(37), 38, m(49), 34, m(58), 39, m(57), 48, m(48), 51, m(40), 45]
        parts.append(Poly(gl, lo, wing, z=-3.2, T=1.1, cd=5.0))
        parts.append(Spot(gl, m(52), 42, 2.6, 2.1, spot))
        parts.append(Stripe(gl, [m(39), 40, m(52), 44], 0.8, vein))
    parts.append(E('abd', 32, 47.0, 5.8, 9.6, body, z=-0.5, rd=5.4, d=2.0, cd=0.0))
    for yy in (43.5, 47.5, 51.5):
        parts.append(Stripe('abd', [26.5, yy, 32, yy + 1.0, 37.5, yy], 1.0, '#7a54a4'))
    parts.append(E('thx', 32, 34.0, 7.0, 7.0, body, z=0, rd=6.6))
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(Cap(g, 32 + side * 2.4, 39.0, 32 + side * 4.4, 46.0, 1.3, 1.0, leg, z=1, cd=-2.5))
    parts.append(E('head', 32, 24.5, 7.6, 6.9, body, z=2, rd=7.0, cd=-2.0))
    for side, g in ((-1, 'eyeL'), (1, 'eyeR')):
        parts.append(E(g, 32 + side * 4.8, 24.0, 3.8, 4.4, eye, z=3, rd=3.2, d=-5.0, cd=-2.0, solid=True))
        parts.append(Spot(g, 32 + side * 5.6, 22.4, 1.3, 1.6, eyel, face=True))
    for side, g in ((-1, 'antL'), (1, 'antR')):
        parts.append(Stroke(g, [32 + side * 3.0, 19.5, 32 + side * 5.6, 12.0, 32 + side * 10.5, 6.0], 1.5, body, z=2, w2=1.0,
                            d1=-2.0, d2=-1.0, cd=0.0))
    parts.append(Poly('mand', [30.4, 29.0, 32, 32.6, 33.6, 29.0], leg, z=6, T=0.8, cd=-8.0, face=True))
    rebuild(d, parts, features=[])


@fix('BUTTERFREE')
def butterfree(d, look):
    body, eye, wing, wk, limb = '#50508c', '#e03858', '#f2f2f4', '#262636', '#88c8e8'
    parts = []
    for side, gu, gl in ((-1, 'wingUL', 'wingLL'), (1, 'wingUR', 'wingLR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        up = [m(37), 29, m(45), 12, m(56), 4, m(64), 8, m(63), 20, m(55), 29, m(45), 33]
        parts += bordered_wing(gu, up, wk, wing, veins=[[m(39), 28, m(52), 13], [m(41), 30, m(59), 19]], z=-3, cd=5.0)
        lo = [m(37), 38, m(50), 35, m(58), 41, m(56), 50, m(46), 52, m(39), 45]
        parts += bordered_wing(gl, lo, wk, wing, veins=[[m(40), 40, m(53), 44]], z=-3.2, cd=5.0)
    parts.append(E('abd', 32, 44.0, 5.6, 8.0, body, z=-0.5, rd=5.2, d=1.5, cd=0.0))
    parts.append(E('body', 32, 36.5, 6.8, 8.6, body, z=0, rd=6.2))
    for side, g in ((-1, 'armL'), (1, 'armR')):
        parts.append(Cap(g, 32 + side * 4.6, 38.0, 32 + side * 8.6, 42.0, 1.9, 1.6, limb, z=3, cd=-4.0))
        parts.append(E(g, 32 + side * 9.0, 42.8, 1.9, 1.6, limb, z=3.1, rd=1.7, d=-1.0, cd=-4.0, solid=True))
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(Cap(g, 32 + side * 2.6, 47.0, 32 + side * 3.2, 54.0, 1.9, 1.6, limb, z=1, cd=-1.0))
        parts.append(E(g, 32 + side * 3.6, 55.0, 2.4, 1.4, limb, z=1.1, rd=2.6, d=-1.5, cd=-1.0, solid=True))
    parts.append(E('head', 32, 25.5, 8.2, 7.4, body, z=2, rd=7.4, cd=-2.0))
    for side, g in ((-1, 'eyeL'), (1, 'eyeR')):
        parts.append(E(g, 32 + side * 5.0, 24.5, 4.4, 5.0, eye, z=3, rd=3.6, d=-5.2, cd=-2.0, solid=True))
        parts.append(Spot(g, 32 + side * 6.0, 22.6, 1.5, 1.8, '#ff8aa0', face=True))
    for side, g in ((-1, 'antL'), (1, 'antR')):
        parts.append(Stroke(g, [32 + side * 3.2, 20.0, 32 + side * 5.0, 12.5, 32 + side * 10.0, 7.0], 1.4, wk, z=2, w2=1.0,
                            d1=-2.0, d2=-1.0, cd=0.0))
    parts.append(Poly('mand', [30.6, 30.0, 32, 33.4, 33.4, 30.0], '#f0f0f0', z=6, T=0.8, cd=-9.0, face=True))
    rebuild(d, parts, features=[])


# ============================================================================ Caterpie / Weedle / Kakuna / Beedrill
def _grub(d, look, P):
    """Front-facing caterpillar: big head towards the viewer, body segments trailing away to the back-right."""
    body, belly = P['body'], P['belly']
    parts = []
    segs = P['segs']                      # (x, y, r, depth)
    for i, (x, y, r, dd) in enumerate(reversed(segs)):
        k = len(segs) - i
        parts.append(E('s%d' % k, x, y, r, r * 0.95, body, z=-k, rd=r, d=dd, cd=0.0, solid=True))
        parts.append(Spot('s%d' % k, x, y + r * 0.72, r * 0.55, r * 0.28, belly))
        if P.get('ring'):
            parts.append(Spot('s%d' % k, x - r * 0.15, y - r * 0.1, r * 0.34, r * 0.34, P['ring']))
        # tiny feet under each segment
        parts.append(E('f%d' % k, x, y + r * 0.95, r * 0.55, 1.2, P['foot'], z=-k + 0.1, rd=r * 0.5, d=dd, cd=0.0, solid=True))
    tx, ty, tr, td = segs[-1]
    parts += P['tail'](tx, ty, tr, td)
    hx, hy, hr = P['head']
    parts.append(E('head', hx, hy, hr, hr * 0.95, body, z=4, rd=hr * 0.95, cd=-hr * 0.7))
    parts += P['extras'](hx, hy, hr)
    rebuild(d, parts, features=P['feats'](hx, hy, hr))


@fix('CATERPIE')
def caterpie(d, look):
    def tail(tx, ty, tr, td):
        return [Cap('s0', tx, ty, tx + 3.0, ty - 1.5, tr * 0.7, 0.6, '#80c850', z=-6, d1=td + 1.0, d2=td + 6.0, cd=0.0)]

    def extras(hx, hy, hr):
        out = []
        # the red Y-shaped antenna
        out.append(Cap('ant', hx, hy - hr + 1.2, hx, hy - hr - 5.5, 1.4, 1.1, '#e84830', z=6, d1=-2.0, d2=-2.0, cd=0.0))
        out.append(Cap('ant', hx, hy - hr - 5.2, hx - 3.6, hy - hr - 10.0, 1.3, 0.8, '#e84830', z=6, d1=-2.0, d2=-2.0, cd=0.0))
        out.append(Cap('ant', hx, hy - hr - 5.2, hx + 3.6, hy - hr - 10.0, 1.3, 0.8, '#e84830', z=6, d1=-2.0, d2=-2.0, cd=0.0))
        out.append(Spot('head', hx, hy + hr * 0.62, hr * 0.35, hr * 0.18, '#f8e890', face=True))
        return out

    def feats(hx, hy, hr):
        return [Eye(hx - hr * 0.48, hy - 0.5, 3.5, '#202030', look=(0, 0), sclera=True, wide=0.9),
                Eye(hx + hr * 0.48, hy - 0.5, 3.5, '#202030', look=(0, 0), sclera=True, wide=0.9),
                Mouth(hx, hy + hr * 0.55, 1.4, 'smile')]

    _grub(d, look, dict(body='#80c850', belly='#f8e890', ring='#f4f0b0', foot='#f4e090',
                        segs=[(33.5, 51.0, 7.6, 4.0), (36.0, 53.2, 7.0, 10.5), (38.6, 55.0, 6.2, 16.5), (41.0, 56.2, 5.2, 21.5),
                              (43.0, 56.8, 4.2, 25.5)],
                        head=(32.0, 44.0, 9.2), tail=tail, extras=extras, feats=feats))


@fix('WEEDLE')
def weedle(d, look):
    def tail(tx, ty, tr, td):
        return [Cap('sting', tx, ty, tx + 3.0, ty - 5.5, tr * 0.9, 0.3, '#ece4d4', z=-6, d1=td + 1.0, d2=td + 5.0, cd=0.0)]

    def extras(hx, hy, hr):
        out = [E('nose', hx, hy + hr * 0.3, 3.2, 3.0, '#f07c78', z=6, rd=3.0, d=-hr * 0.95 - 1.5, cd=0.0, solid=True)]
        out.append(Cap('horn', hx, hy - hr + 1.0, hx + 0.6, hy - hr - 9.5, 2.4, 0.3, '#ece4d4', z=6, d1=-2.0, d2=-2.5, cd=0.0))
        return out

    def feats(hx, hy, hr):
        return [Eye(hx - hr * 0.5, hy - 1.4, 2.4, '#101018', look=(0, 0), sclera=False),
                Eye(hx + hr * 0.5, hy - 1.4, 2.4, '#101018', look=(0, 0), sclera=False)]

    _grub(d, look, dict(body='#d8a038', belly='#e8c060', foot='#e87070', ring=None,
                        segs=[(33.5, 51.5, 7.0, 4.0), (36.0, 53.4, 6.6, 10.5), (38.4, 55.0, 5.8, 16.0), (40.6, 56.2, 5.0, 21.0)],
                        head=(32.0, 44.5, 8.8), tail=tail, extras=extras, feats=feats))


@fix('KAKUNA')
def kakuna(d, look):
    shell, line, dark = '#e6c63e', '#a88a22', '#c8a830'
    parts = []
    parts.append(E('seg4', 32, 58.0, 3.4, 3.0, shell, z=-4, rd=3.2, cd=0.0, solid=True))
    parts.append(E('seg3', 32, 54.0, 5.8, 4.4, shell, z=-3, rd=5.4, cd=0.0, solid=True))
    parts.append(E('seg2', 32, 48.5, 8.0, 5.6, shell, z=-2, rd=7.4, cd=0.0, solid=True))
    parts.append(E('seg1', 32, 42.0, 9.6, 6.6, shell, z=-1, rd=8.8, cd=0.0, solid=True))
    for g, yy, w in (('seg2', 45.5, 6.6), ('seg3', 51.2, 5.0), ('seg4', 56.2, 3.0)):
        parts.append(Stripe(g, [32 - w, yy, 32, yy + 1.0, 32 + w, yy], 0.9, line))
    parts.append(E('head', 32, 28.5, 10.8, 13.0, shell, z=2, rd=10.0, cd=-0.5, solid=True))
    parts.append(Cap('head', 32, 20.0, 32, 13.0, 4.0, 0.6, shell, z=2.1, d1=1.0, d2=2.0, cd=-0.5))
    parts.append(Stripe('head', [32, 15, 32, 26], 1.0, line, backOnly=True))
    parts.append(Stripe('head', [26.5, 33.5, 32, 34.8, 37.5, 33.5], 1.0, line, face=True))
    for side, g in ((-1, 'armL'), (1, 'armR')):
        parts.append(Cap(g, 32 + side * 9.0, 44.0, 32 + side * 14.6, 49.5, 2.6, 0.4, dark, z=3, d1=-3.0, d2=-3.5, cd=-3.0))
    feats = [Eye(27.2, 31.0, 2.9, '#101018', look=(0, 0), sclera=False, style='angry'),
             Eye(36.8, 31.0, 2.9, '#101018', look=(0, 0), sclera=False, style='angry', flip=True)]
    rebuild(d, parts, features=feats)
    hint(look, chains={'seg1': 1, 'seg2': 1, 'seg3': 1})


@fix('BEEDRILL')
def beedrill(d, look):
    yel, blk, sting, eye, wing = '#f0c830', '#302838', '#eceaf0', '#e02838', '#d4eaf8'
    parts = []
    for side, gu, gl in ((-1, 'wingUL', 'wingLL'), (1, 'wingUR', 'wingLR')):
        m = lambda x: 32 + side * (x - 32)  # noqa: E731
        parts.append(Poly(gu, [m(38), 27, m(43), 10, m(52), 1, m(59), 4, m(58), 14, m(50), 24, m(43), 30], wing, z=-4, T=0.9, cd=6.0))
        parts.append(Stripe(gu, [m(39), 26, m(48), 12, m(56), 4], 0.7, '#98b8d0'))
        parts.append(Poly(gl, [m(38), 32, m(50), 27, m(60), 29, m(57), 36, m(47), 38, m(40), 36], wing, z=-4.2, T=0.9, cd=6.0))
        parts.append(Stripe(gl, [m(40), 33, m(52), 30], 0.7, '#98b8d0'))
    parts.append(E('abd', 32, 45.0, 8.6, 11.2, yel, z=-1, rd=8.4, d=4.0, cd=0.0))
    for yy in (41.0, 47.0):
        parts.append(Stripe('abd', [22.5, yy - 1.0, 32, yy + 1.6, 41.5, yy - 1.0], 2.6, blk))
    parts.append(Cap('st3', 32, 54.0, 32, 60.5, 3.2, 0.4, sting, z=-2, d1=8.0, d2=16.0, cd=0.0))
    parts.append(E('thx', 32, 32.0, 6.6, 7.2, blk, z=0, rd=6.4))
    for side, ga, gs in ((-1, 'armL', 'lanceL'), (1, 'armR', 'lanceR')):
        parts.append(Cap(ga, 32 + side * 5.0, 30.0, 32 + side * 10.5, 36.0, 2.2, 1.9, yel, z=3, cd=-2.0))
        parts.append(Cap(gs, 32 + side * 10.5, 36.0, 32 + side * 13.0, 46.5, 3.4, 0.4, sting, z=3.1, d1=-3.0, d2=-9.5, cd=-2.0))
    for side, g in ((-1, 'legL'), (1, 'legR')):
        parts.append(Cap(g, 32 + side * 2.0, 38.0, 32 + side * 3.2, 46.0, 1.3, 1.0, blk, z=1, cd=-3.0))
    parts.append(E('head', 32, 20.5, 7.8, 7.2, yel, z=2, rd=7.2, cd=-2.0))
    for side, g in ((-1, 'eyeL'), (1, 'eyeR')):
        parts.append(E(g, 32 + side * 4.8, 20.0, 3.6, 4.4, eye, z=3, rd=3.2, d=-5.2, cd=-2.0, solid=True))
        parts.append(Spot(g, 32 + side * 5.6, 18.4, 1.2, 1.5, '#ff8a98', face=True))
    for side, g in ((-1, 'antL'), (1, 'antR')):
        parts.append(Stroke(g, [32 + side * 3.0, 14.5, 32 + side * 4.6, 8.0, 32 + side * 8.0, 3.0], 1.4, blk, z=2, w2=1.0,
                            d1=-2.0, d2=-1.0, cd=0.0))
    parts.append(Mouth(32.0, 25.4, 1.0, 'line'))
    rebuild(d, parts, features=[Mouth(32.0, 25.6, 1.2, 'line')])


# ============================================================================ Bulbasaur line (front-facing quadrupeds)
def _toad_legs(skin, by, spread_f=7.0, spread_b=8.0, leg_r=4.2, foot_w=4.4, foot_l=5.0, toe_r=1.4, df=-6.0, db=12.0,
               claw=CLAW, top_f=None):
    out = []
    for side, g in ((-1, 'legFL'), (1, 'legFR')):
        x = 32 + side * spread_f
        out.append(Cap(g, x, top_f or by + 1.0, x + side * 0.4, 56.0, leg_r, leg_r * 0.92, skin, z=2, cd=df))
        out += foot(g, x + side * 0.6, 60.0, skin, w=foot_w, ln=foot_l, n=3, dz=-1.0, toe_r=toe_r, z=2.2, claw=claw)
    for side, g in ((-1, 'legBL'), (1, 'legBR')):
        x = 32 + side * spread_b
        out.append(Cap(g, x, by - 1.0, x + side * 0.4, 56.0, leg_r * 1.15, leg_r * 1.0, skin, z=2, cd=db))
        out += foot(g, x + side * 0.6, 60.0, skin, w=foot_w * 1.05, ln=foot_l, n=3, dz=-1.0, toe_r=toe_r, z=2.2, claw=claw)
    return out


def _toad_head(skin, spot, hy, hrx, hry, eye_dx, eye_y, eye_s, cd=-10.0, ear_h=5.2, ear_dx=8.0):
    parts = [E('head', 32, hy, hrx, hry, skin, z=4, rd=hry + 1.2, cd=cd)]
    parts.append(E('head', 32, hy + hry * 0.42, hrx * 0.7, hry * 0.58, skin, z=4, rd=hry * 0.9, d=-4.4, cd=cd, frontOnly=True))
    for side, g in ((-1, 'earL'), (1, 'earR')):
        parts += cone(g, 32 + side * ear_dx, hy - hry * 0.55, 32 + side * (ear_dx + 2.2), hy - hry - ear_h, 4.8, 0.9, skin, z=1, cd=cd)
    parts.append(Spot('head', 32 - hrx * 0.62, hy - hry * 0.78, 2.4, 1.6, spot))
    parts.append(Spot('head', 32 + hrx * 0.55, hy - hry * 0.85, 1.9, 1.3, spot))
    parts.append(Spot('head', 32 - 1.4, hy + hry * 0.35, 0.55, 0.45, '#2a4a40', face=True))
    parts.append(Spot('head', 32 + 1.4, hy + hry * 0.35, 0.55, 0.45, '#2a4a40', face=True))
    feats = [Eye(32 - eye_dx, eye_y, eye_s, '#d03040', look=(0, 0), style='angry', wide=1.05),
             Eye(32 + eye_dx, eye_y, eye_s, '#d03040', look=(0, 0), style='angry', wide=1.05, flip=True)]
    return parts, feats


@fix('BULBASAUR')
def bulbasaur(d, look):
    skin, spot, bulb, bulbd = '#72c8a8', '#3f8f76', '#5aa848', '#3a7a38'
    parts = []
    parts.append(E('body', 32, 47.5, 11.4, 9.4, skin, z=0, rd=13.0, d=5.0, cd=0.0))
    for x, y in ((25.5, 44.0), (38.5, 46.5), (33.0, 51.5), (29.0, 49.5)):
        parts.append(Spot('body', x, y, 2.6, 2.0, spot))
    parts += _toad_legs(skin, 47.5, spread_f=7.0, spread_b=8.4, leg_r=4.3)
    # the bulb: a big green onion with a pointed sprout and ribs
    parts.append(E('bulb', 32, 34.5, 12.4, 12.0, bulb, z=1, rd=12.4, d=7.5, cd=0.0, gloss=True, solid=True))
    parts.append(Cap('bulb', 32, 25.0, 32, 18.5, 3.4, 0.5, bulbd, z=1.1, d1=7.5, d2=7.5, cd=0.0))
    for x0, x1 in ((23.5, 26.0), (32, 32), (40.5, 38.0)):
        parts.append(Stripe('bulb', [x0, 28.0, (x0 + x1) / 2 + (0 if x0 == 32 else 0.4 * (x1 - x0)), 36.0, x1, 45.5], 1.4, bulbd))
    hp, feats = _toad_head(skin, spot, 42.5, 12.6, 8.8, 5.8, 41.2, 3.0)
    parts += hp
    feats.append(Mouth(32.0, 47.6, 3.6, 'open'))
    rebuild(d, parts, features=feats)


@fix('IVYSAUR')
def ivysaur(d, look):
    skin, spot, bulb, bulbd = '#68bcb0', '#3c8a80', '#4aac48', '#2e7c34'
    bud, budd, trunk = '#f482a2', '#c44874', '#9a6a3c'
    parts = []
    parts.append(E('body', 32, 47.0, 12.2, 9.8, skin, z=0, rd=13.6, d=5.0, cd=0.0))
    for x, y in ((24.5, 44.0), (39.5, 46.5), (33.0, 51.5), (28.0, 49.5)):
        parts.append(Spot('body', x, y, 2.8, 2.1, spot))
    parts += _toad_legs(skin, 47.0, spread_f=7.4, spread_b=8.8, leg_r=4.7, foot_w=4.8, foot_l=5.3, toe_r=1.5)
    parts.append(E('bulb', 32, 37.0, 10.0, 8.0, bulb, z=1, rd=10.0, d=7.0, cd=0.0, solid=True))
    parts.append(Cap('trunk', 32, 37.0, 32, 26.0, 3.6, 3.0, trunk, z=1.5, d1=7.0, d2=7.0, cd=0.0))
    # the budding flower
    parts.append(E('bud', 32, 21.0, 6.6, 9.0, bud, z=2, rd=6.6, d=7.0, cd=0.0, gloss=True, solid=True))
    parts.append(Cap('bud', 32, 13.0, 32, 8.0, 3.2, 0.5, bud, z=2.1, d1=7.0, d2=7.0, cd=0.0))
    for x0, x1 in ((26.5, 28.0), (32, 32), (37.5, 36.0)):
        parts.append(Stripe('bud', [x0, 12.0, (x0 + x1) / 2, 20.0, x1, 29.0], 1.1, budd))
    for side, g in ((-1, 'lfL'), (1, 'lfR')):
        parts += leaf_plate(g, 32 + side * 3.0, 33.0, side * 66, 19.0, 9.0, '#4aac48', bulbd, z=0.5, T=1.5, cd=6.0)
    hp, feats = _toad_head(skin, spot, 42.0, 13.0, 9.0, 6.0, 40.6, 3.0, ear_h=5.8)
    parts += hp
    feats.append(Mouth(32.0, 47.2, 3.4, 'open'))
    rebuild(d, parts, features=feats)


@fix('VENUSAUR')
def venusaur(d, look):
    skin, spot = '#5eb0a4', '#387c74'
    petal, petald, center, leaf, leafd, trunk = '#f07888', '#d05068', '#f4d870', '#44a44c', '#2a6c34', '#8a5a30'
    parts = []
    parts.append(E('body', 32, 45.5, 15.8, 11.8, skin, z=0, rd=15.5, d=5.0, cd=0.0))
    for x, y in ((21.0, 42.0), (43.0, 45.0), (33.0, 52.0), (26.0, 49.0), (39.0, 50.0)):
        parts.append(Spot('body', x, y, 3.0, 2.3, spot))
    parts += _toad_legs(skin, 45.5, spread_f=9.6, spread_b=10.8, leg_r=6.0, foot_w=5.8, foot_l=6.2, toe_r=1.8, df=-7.0, db=13.5)
    # trunk + big flower
    parts.append(Cap('trunk', 32, 36.0, 32, 24.0, 5.4, 4.6, trunk, z=1.5, d1=7.0, d2=7.0, cd=0.0))
    parts += petals('flower', 32, 18.5, 7.0, 12.5, 5, 10.0, 4.4, 9.0, petal, tilt=0.5, z=2, a0=-90)
    parts.append(E('flower', 32, 19.0, 9.0, 5.4, petald, z=2.1, rd=9.0, d=7.0, solid=True))
    parts.append(E('ctr', 32, 17.0, 6.0, 4.0, center, z=3, rd=6.0, d=5.0, solid=True))
    for x, y in ((18.0, 22.0), (46.0, 22.0), (24.0, 30.0), (40.0, 30.0), (32, 12.0)):
        parts.append(Spot('flower', x, y, 2.0, 1.5, '#fae0e6'))
    for side, g in ((-1, 'lfL'), (1, 'lfR')):
        parts += leaf_plate(g, 32 + side * 6.0, 36.0, side * 74, 22.0, 10.0, leaf, leafd, z=0.5, T=1.6, cd=6.0)
    hp, feats = _toad_head(skin, spot, 41.5, 14.4, 9.6, 6.6, 39.6, 3.0, cd=-11.0, ear_h=5.0, ear_dx=9.0)
    parts += hp
    feats.append(Mouth(32.0, 47.0, 3.8, 'fang'))
    rebuild(d, parts, features=feats)
    look['view'] = 'front'

"""Hair styles: a thick shell hugging the skull (hairline shaped per style) plus lofted locks,
spikes, tails and buns.  All parts are rigid to the head unless they belong to a secondary
hair bone chain (ponytail, pigtails, long back hair)."""
import math

import numpy as np

import char_geo as G


def _interp(az, table):
    xs = [t[0] for t in table]
    ys = [t[1] for t in table]
    a = ((np.asarray(az, float) + 180.0) % 360.0) - 180.0
    return np.interp(np.abs(a), xs, ys)


def dirs_from(az, th):
    a, t = np.radians(az), np.radians(th)
    return np.stack([np.sin(t) * np.sin(a), -np.sin(t) * np.cos(a), np.cos(t)], -1)


def shell(ctx, name, bot, top=None, az_range=(-180, 180), nu=32, nv=10, thick=0.5, volume=0.0,
          ridges=14, ridge_amp=0.10, cell='hair', wrap=True, lip=0.22, offset=0.5, rim_top=True, seed=1):
    """Thick hair cap.  bot/top: tables [(|az|, theta_deg)] of the lower / upper edge (top None =>
    covers the crown pole).  Returns a Part."""
    H = ctx.head
    if wrap:
        az = np.linspace(az_range[0], az_range[1], nu, endpoint=False)
    else:
        az = np.linspace(az_range[0], az_range[1], nu)
    tb = _interp(az, bot) if not callable(bot) else bot(az)
    tt = np.zeros_like(az) if top is None else (_interp(az, top) if not callable(top) else top(az))
    v = np.linspace(0, 1, nv)
    TH = tt[:, None] + (tb - tt)[:, None] * v[None, :]
    AZ = np.repeat(az[:, None], nv, 1)
    d = dirs_from(AZ, TH)
    P = H.pt(d)
    # crown swirl: ridges radiate from the top
    rid = 1.0 + ridge_amp * np.sin(np.radians(AZ) * ridges + 1.3 * np.sin(np.radians(AZ) * 3)) * G.smoothstep(0.05, 0.4, v)[None, :]
    body = lip + (thick - lip) * G.smoothstep(1.0, 0.72, v)
    if top is not None:
        body = np.minimum(body, lip + (thick - lip) * G.smoothstep(0.0, 0.28, v))
    crown = volume * np.exp(-((TH / 38.0) ** 2))
    th = (body + crown) * rid
    if not wrap:
        uu = np.linspace(0, 1, nu)
        env = 0.3 + 0.7 * G.smoothstep(0.0, 0.22, uu) * G.smoothstep(1.0, 0.78, uu)
        th = th * env[:, None]
    g = np.tile(v[None, :], (nu, 1)).reshape(-1)
    p = G.solid_surface(P, 0.0, cell=cell, name=name, wrap_u=wrap, g=g, thick_fn=lambda _P: th, offset=offset,
                        outward_from=H.c, inner='rim')
    return p


def lock(ctx, pts_azel, widths, thick, off, name='lock', cell='hair', seg=8, taper_tip=0.9, ref=(1, 0, 0)):
    """Flat tapered lock hugging the head: points as (az, el, offset) triples."""
    H = ctx.head
    a = np.asarray(pts_azel, float)
    path = H.surf(a[:, 0], a[:, 1], a[:, 2])
    path = G.catmull(path, 9)
    t = np.linspace(0, 1, 9)
    w = np.interp(t, np.linspace(0, 1, len(widths)), widths)
    th = np.interp(t, np.linspace(0, 1, len(thick)), thick) if hasattr(thick, '__len__') else np.full(9, thick)
    p = G.loft(path, np.stack([w, th], 1), seg=seg, cell=cell, name=name, caps=(0.6, taper_tip), ref=ref)
    p.g = np.clip(1 - (p.V[:, 2] - path[:, 2].min()) / max(np.ptp(path[:, 2]), 1e-3), 0, 1) * 0.5 + 0.5
    return p


def spike(ctx, az, el, length, width, tilt=(0, 0, 0), off=-0.1, name='spike', bend=(0, 0, 0), cell='hair', seg=6, thin=0.55):
    """Blade-shaped spike growing out of the skull at (az, el): wide across the head's tangent,
    thin front-to-back, curving by `bend`.  tilt is added to the outward normal."""
    H = ctx.head
    base = H.surf(az, el, off)
    n = H.normal(az, el)
    d = G.nrm(n + np.asarray(tilt, float))
    k = 5
    t = np.linspace(0, 1, k)
    path = base[None, :] + d[None, :] * (t * length)[:, None] + np.asarray(bend, float)[None, :] * (t ** 2 * length)[:, None]
    taper = (1 - t) ** 0.85
    rx = width * 0.5 * taper + 0.04
    ry = width * 0.5 * thin * taper + 0.04
    a = math.radians(az)
    ref = (math.cos(a), math.sin(a), 0.0)
    p = G.loft(path, np.stack([rx, ry], 1), seg=seg, cell=cell, name=name, caps=(0.0, 0.0), ref=ref)
    p.g = np.clip(G.smoothstep(0, length, np.linalg.norm(p.V - base, axis=1)), 0, 1) * 0.6 + 0.3
    return p


def tail(ctx, pts, radii, name='tail', cell='hair', seg=8, bones=None, hw=0.8):
    """Free-hanging tapered tube (ponytail / pigtail / curtain lock).  Weights: rigid head at the
    root blending down a chain of secondary bones (pts are also the bone joints)."""
    path = G.catmull(np.asarray(pts, float), 10)
    t = np.linspace(0, 1, 10)
    r = np.interp(t, np.linspace(0, 1, len(radii)), radii)
    p = G.loft(path, np.stack([r, r], 1), seg=seg, cell=cell, name=name, caps=(0.5, 0.4), ref=(1, 0, 0))
    p.g = np.clip(np.linalg.norm(p.V - path[0], axis=1) / max(np.linalg.norm(path[-1] - path[0]), 1e-3), 0, 1)
    return p


# ----------------------------------------------------------------------------- styles
def add_chain_bones(ctx, prefix, pts, parent='head'):
    """Secondary bone chain along pts; returns bone names."""
    names = []
    par = parent
    for i in range(len(pts) - 1):
        nm = '%s%d' % (prefix, i + 1)
        ctx.extra_bones.append((nm, par, tuple(pts[i]), tuple(pts[i + 1])))
        names.append(nm)
        par = nm
    return names


def weight_chain(part, pts, names, root_bone='head', hw=0.7):
    """Blend head -> chain bones along pts (the part follows the chain from its root)."""
    bones = [root_bone] + names
    joints = [np.asarray(pts[0])] + [np.asarray(p) for p in pts]
    # segment 0 of the chain is head (fixed root): bones = [head, n1, n2, ...] on points [p0-ε, p0, p1, ...]
    P = [np.asarray(pts[0]) + np.array([0, 0, 1.0])] + [np.asarray(p) for p in pts]
    G.add_weights(part, G.chain_weights(part.V, P, bones, hw))
    return part


def build_hair(ctx, hair):
    """hair: dict(style=..., color role, ...)."""
    st = hair.get('style', 'short')
    color = ctx.col(hair.get('color'), 'hair')
    ctx.ramp('hair', 'hair', color)
    fn = STYLES.get(st)
    if fn is None:
        raise KeyError('hair style %s' % st)
    fn(ctx, hair)


def _bangs_(ctx, n=5, az_span=32, el0=44, el1=17, sweep=10, wid=1.15, off=(0.8, 0.58, 0.40), asym=0.0, thick=0.38, seed=2, lens=None, side=1):
    """Swept fringe: a few broad overlapping locks that start in the crown and fall across the forehead."""
    rng = np.random.default_rng(seed)
    lens = lens or (1.0, 0.72, 0.92, 0.6, 0.85)
    for i in range(n):
        f = (i + 0.5) / n
        az = -az_span + 2 * az_span * f + asym * 8
        ln = lens[i % len(lens)]
        e1 = el0 - (el0 - el1) * ln
        sw = sweep * side * (0.6 + 0.6 * (f if side > 0 else 1 - f)) * (0.85 + 0.3 * rng.random())
        w = wid * (0.9 + 0.2 * rng.random())
        p = lock(ctx, [(az, el0 + 8, off[0]), (az + sw * 0.35, (el0 + e1) / 2 + 3, off[1]), (az + sw, e1, off[2])],
                 [w, w * 1.05, w * 0.3], [thick, thick, thick * 0.5], 0, name='bang', seg=8, taper_tip=0.9)
        ctx.add(p, 'head')


def hairline(kind='short', part=0.0, drop=5.0, back=126):
    """Lower hairline (theta from the top, degrees) as a function of signed azimuth: high forehead with a
    soft swoop lower on the side the fringe falls to, ears free, nape covered."""
    tab = {'short': [(0, 58), (30, 60), (55, 66), (75, 72), (90, 80), (105, 98), (140, back - 4), (180, back)],
           'long': [(0, 58), (30, 60), (55, 68), (75, 84), (90, 108), (105, 122), (140, 130), (180, 132)],
           'bob': [(0, 58), (30, 60), (55, 68), (75, 88), (90, 112), (105, 124), (140, 130), (180, 132)]}[kind]
    xs = [t[0] for t in tab]
    ys = [t[1] for t in tab]

    def f(az):
        az = np.asarray(az, float)
        th = np.interp(np.abs(az), xs, ys)
        sw = drop * np.exp(-(((az - part * 20.0) / 24.0) ** 2))
        return th + sw
    return f


SHORT_BOT = None
LONG_BOT = None
CAP_BOT = [(0, 62), (25, 64), (50, 70), (72, 80), (88, 90), (105, 100), (140, 108), (180, 112)]


def style_short(ctx, h):
    bot = h.get('bot') or hairline('short', h.get('part', 0.5), h.get('drop', 5.0))
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.62), volume=h.get('volume', 0.3), ridges=h.get('ridges', 12))
    ctx.add(p, 'head')
    if h.get('bangs', True):
        _bangs(ctx, n=h.get('bang_n', 5), az_span=h.get('bang_span', 32), el1=h.get('bang_el', 17), sweep=h.get('sweep', 10),
               asym=h.get('part', 0.0), seed=h.get('seed', 2), side=(1 if h.get('part', 0.5) >= 0 else -1))
    if h.get('tuft'):
        ctx.add(spike(ctx, 0, 62, 2.0, 1.2, tilt=(0, -0.5, 0.6), bend=(0, -0.3, 0.3)), 'head')
    _extras(ctx, h)


def style_spiky(ctx, h):
    """Spiky hair: shell + clumps of curved blades.  h: len, spike_w, sweep_back (crown blades lean back),
    up (lower blades rise), rows [(theta_from_top, count, length_scale, outward)], fringe (front blades)."""
    bot = h.get('bot') or hairline('short', 0.0, 0.0)
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.6), volume=h.get('volume', 0.25), ridges=10)
    ctx.add(p, 'head')
    if ctx.cover:
        _extras(ctx, h)
        return
    rng = np.random.default_rng(h.get('seed', 5))
    L = h.get('len', 4.6)
    W = h.get('spike_w', 3.2)
    back = h.get('sweep_back', 0.45)
    up = h.get('up', 0.55)
    rows = h.get('rows') or [(88, 7, 0.80, 1.0), (62, 7, 1.0, 0.8), (38, 6, 1.05, 0.55), (14, 4, 0.85, 0.2)]
    for r_i, (th, n, ls, outw) in enumerate(rows):
        for i in range(n):
            az = -180 + 360 * (i + 0.5 * (r_i % 2)) / n + rng.uniform(-6, 6)
            el = 90 - th
            if abs(az) < 30 and th > 60:
                continue                      # keep the forehead clear
            jit = 0.8 + 0.4 * rng.random()
            a = math.radians(az)
            radial = np.array([math.sin(a), -math.cos(a), 0.0]) * outw
            tilt = radial * 0.4 + np.array([0, back, up + 0.35 * (1 - outw)])
            bend = np.array([0, back * 0.35, 0.35 + 0.2 * (1 - outw)])
            ctx.add(spike(ctx, az, el, L * ls * jit, W * (0.85 + 0.3 * rng.random()), tilt=tilt, bend=bend), 'head')
    # forehead fringe: short blades falling over the brow
    for i, az in enumerate(h.get('fringe_az', (-22, -5, 12, 27))):
        ln = (3.4, 4.0, 3.6, 3.0)[i % 4] * h.get('fringe_len', 1.0)
        sgn = 1 if az >= 0 else -1
        ctx.add(spike(ctx, az, 44, ln, 2.6, tilt=(0.25 * sgn, -0.75, -0.1), bend=(0.1 * sgn, -0.25, -0.5), off=-0.1), 'head')
    _extras(ctx, h)


def style_flat(ctx, h):
    """Military flat-top / crew cut: dense short spikes on a shell (Surge)."""
    style_spiky(ctx, {**h, 'len': h.get('len', 2.4), 'spike_w': h.get('spike_w', 2.2), 'sweep_back': 0.05,
                      'fringe_az': (-26, -9, 9, 26), 'fringe_len': 0.6,
                      'rows': [(84, 9, 0.7, 1.0), (62, 9, 0.9, 0.7), (40, 7, 1.0, 0.45), (18, 5, 1.05, 0.2), (2, 1, 1.1, 0.0)]})


def style_long(ctx, h):
    """Long hair: shell reaching the nape + curtain down the back + side locks + bangs."""
    bot = h.get('bot') or hairline('long', h.get('part', 0.5), h.get('drop', 5.0))
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.62), volume=h.get('volume', 0.25), ridges=12)
    ctx.add(p, 'head')
    if h.get('bangs', True):
        _bangs(ctx, n=h.get('bang_n', 5), az_span=h.get('bang_span', 32), el1=h.get('bang_el', 16), sweep=h.get('sweep', 10),
               asym=h.get('part', 0.0), seed=h.get('seed', 2), side=(1 if h.get('part', 0.5) >= 0 else -1))
    P = ctx.P
    H = ctx.head
    ln = h.get('length', 1.0)
    z_rim = H.c[2] - 2.6
    z_bot = max(P.shoulder - 0.4 - (ln - 1.0) * 4.0, P.chest - 2.2)
    # curtain: grid over azimuth (back half) x height
    nu, nv = 17, 9
    azr = np.linspace(-92, 92, nu)
    s = np.linspace(0, 1, nv)
    AZ = azr[:, None].repeat(nv, 1)
    S = s[None, :].repeat(nu, 0)
    zc = z_rim + (z_bot - z_rim) * S
    flare = h.get('flare', 0.5)
    wave = h.get('wave', 0.3)
    rx = 5.45 + flare * 1.3 * S + wave * np.sin(S * 9 + AZ * 0.08) * 0.35
    ry = 5.0 + flare * 0.5 * S
    end_in = 1.0 - 0.28 * S ** 2 * (1 - h.get('blunt', 0.6))      # taper the width toward the tips
    x = np.sin(np.radians(AZ)) * rx * end_in
    y = np.cos(np.radians(AZ)) * ry * (0.9 - 0.15 * S) * 1.0
    y = np.where(np.abs(AZ) < 89, y, y * 0.6)
    y = y + 0.4
    pts = np.stack([x, y, zc], -1)
    # hem: scalloped
    pts[..., 2] -= (0.5 * np.sin(AZ * 0.35) ** 2 + 0.3 * np.sin(AZ * 0.9)) * S ** 3 * (1.0 if h.get('scallop', True) else 0.0)
    cur = G.solid_surface(pts, 1.0, cell='hair', name='curtain', flip=False, g=(1 - S).reshape(-1) * 0.9, offset=0.0,
                          outward_from=(0, 0.3, z_rim), thick_fn=lambda _P: 0.75 + 0.2 * np.sin(AZ * 0.2))
    b_pts = [(0, 4.4, z_rim + 0.5), (0, 4.9, (z_rim + z_bot) / 2), (0, 5.2, z_bot)]
    names = add_chain_bones(ctx, 'hair_back', b_pts)
    weight_chain(cur, b_pts, names)
    ctx.add(cur, None)
    ctx.anim_hints['hair_back'] = names
    # side locks in front of the ears
    for s_ in (1, -1):
        pl = lock(ctx, [(s_ * 78, 6, 0.55), (s_ * 87, -8, 0.6), (s_ * 90, -26, 0.62), (s_ * 88, -42, 0.5)],
                  [1.25, 1.35, 1.1, 0.25], 0.5, 0, name='sidelock', seg=8)
        ctx.add(pl, 'head')
    _extras(ctx, h)


def style_bob(ctx, h):
    """Chin-length bob (kids / girls)."""
    bot = [(0, 55), (25, 57), (50, 64), (72, 80), (88, 104), (105, 118), (140, 122), (180, 124)]
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.7), volume=h.get('volume', 0.25), ridges=12)
    ctx.add(p, 'head')
    _bangs(ctx, n=6, az_span=32, el1=h.get('bang_el', 13), sweep=h.get('sweep', 6), seed=h.get('seed', 4))
    for s_ in (1, -1):
        ctx.add(lock(ctx, [(s_ * 80, 8, 0.6), (s_ * 90, -10, 0.85), (s_ * 100, -30, 0.95)], [1.5, 1.7, 0.9], 0.6, 0, name='bobside'), 'head')
    _extras(ctx, h)


def style_pony(ctx, h):
    """Short hair + high ponytail (with tie)."""
    bot = h.get('bot') or hairline('short', h.get('part', 0.5), h.get('drop', 5.0))
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.6), volume=h.get('volume', 0.3))
    ctx.add(p, 'head')
    _bangs(ctx, n=5, az_span=30, el1=h.get('bang_el', 15), sweep=h.get('sweep', 6), seed=h.get('seed', 3))
    H = ctx.head
    side = h.get('side', 0)          # -1 / +1 = side ponytail
    ln = h.get('length', 1.0)
    if side == 0:
        b0 = H.surf(180, 36, 0.4)
        pts = [b0, b0 + np.array([0, 1.2, 0.9]), b0 + np.array([0, 3.0, 0.2]), b0 + np.array([0, 3.9, -2.4 * ln]),
               b0 + np.array([0, 3.6, -5.2 * ln]), b0 + np.array([0, 3.9, -7.0 * ln])]
    else:
        b0 = H.surf(side * 118, 22, 0.4)
        pts = [b0, b0 + np.array([side * 1.3, 0.5, 0.8]), b0 + np.array([side * 3.0, 0.7, 0.2]), b0 + np.array([side * 4.3, 0.7, -2.2 * ln]),
               b0 + np.array([side * 4.3, 0.8, -4.6 * ln]), b0 + np.array([side * 4.8, 0.9, -6.2 * ln])]
    ptail = tail(ctx, pts, [0.9, 1.45, 1.7, 1.45, 0.95, 0.15], name='pony')
    names = add_chain_bones(ctx, 'hair_tail', [tuple(q) for q in (pts[0], pts[2], pts[3], pts[5])])
    weight_chain(ptail, [pts[0], pts[2], pts[3], pts[5]], names, hw=0.9)
    ctx.add(ptail, None)
    ctx.anim_hints['hair_tail'] = names
    tie = h.get('tie', 'accent')
    tcell = ctx.ramp('hairtie', 'flat', ctx.col(tie, 'accent'))
    band = G.ellipsoid(pts[0] + (pts[1] - pts[0]) * 0.55, (1.55, 1.45, 0.75), seg=12, rings=6, cell=tcell, name='tie', rot=G.align_z(pts[1] - pts[0]) if False else None)
    band.g[:] = 0.5
    ctx.add(band, 'head')
    _extras(ctx, h)


def style_twin(ctx, h):
    """Two pigtails (Lorelei-style twin tails, little girl)."""
    bot = h.get('bot') or hairline('short', h.get('part', 0.5), h.get('drop', 5.0))
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.6), volume=h.get('volume', 0.3))
    ctx.add(p, 'head')
    _bangs(ctx, n=5, az_span=30, el1=h.get('bang_el', 15), sweep=h.get('sweep', 6), seed=h.get('seed', 3))
    H = ctx.head
    ln = h.get('length', 1.0)
    tcell = ctx.ramp('hairtie', 'flat', ctx.col(h.get('tie', 'accent'), 'accent'))
    for s_ in (1, -1):
        b0 = H.surf(s_ * 105, 28, 0.35)
        pts = [b0, b0 + np.array([s_ * 1.2, 0.3, 0.3]), b0 + np.array([s_ * 3.2, 0.5, -1.4 * ln]), b0 + np.array([s_ * 4.0, 0.8, -4.0 * ln]),
               b0 + np.array([s_ * 3.6, 1.0, -6.4 * ln]), b0 + np.array([s_ * 3.9, 1.0, -8.0 * ln])]
        ptl = tail(ctx, pts, [0.8, 1.35, 1.45, 1.25, 0.8, 0.12], name='pigtail')
        sfx = 'L' if s_ > 0 else 'R'
        names = add_chain_bones(ctx, 'hair_twin%s' % sfx, [tuple(q) for q in (pts[0], pts[2], pts[3], pts[5])])
        weight_chain(ptl, [pts[0], pts[2], pts[3], pts[5]], names, hw=0.9)
        ctx.add(ptl, None)
        ctx.anim_hints.setdefault('hair_twin', []).extend(names)
        band = G.ellipsoid(b0 + np.array([s_ * 0.9, 0.2, 0.15]), (1.05, 1.2, 1.2), seg=10, rings=6, cell=tcell, name='tie')
        band.g[:] = 0.5
        ctx.add(band, 'head')
    _extras(ctx, h)


def style_bun(ctx, h):
    """Hair swept into a bun (top / back)."""
    bot = h.get('bot') or [(0, 55), (25, 57), (50, 63), (72, 74), (88, 86), (105, 100), (140, 110), (180, 114)]
    p = shell(ctx, 'hair', bot, thick=h.get('thick', 0.62), volume=h.get('volume', 0.3), ridges=12)
    ctx.add(p, 'head')
    _bangs(ctx, n=h.get('bang_n', 5), az_span=30, el1=h.get('bang_el', 14), sweep=h.get('sweep', 7), seed=h.get('seed', 6))
    H = ctx.head
    where = h.get('bun', 'top')
    r = h.get('bun_r', 2.6)
    if where == 'top':
        c = H.surf(150, 62, r * 0.5)
    else:
        c = H.surf(180, 34, r * 0.55)
    b = G.ellipsoid(c, (r, r * 0.95, r * 0.9), seg=14, rings=9, cell='hair', name='bun')
    b.g = np.clip((b.V[:, 2] - c[2]) / (2 * r) + 0.55, 0, 1)
    ctx.add(b, 'head')
    if h.get('bun_band'):
        tcell = ctx.ramp('hairtie', 'flat', ctx.col(h['bun_band'], 'accent'))
        base = H.surf(150 if where == 'top' else 180, 60 if where == 'top' else 30, 0.6)
        bd = G.ellipsoid((base + c) / 2, (r * 0.85, r * 0.8, r * 0.35), seg=12, rings=6, cell=tcell, name='bunband')
        bd.g[:] = 0.5
        ctx.add(bd, 'head')
    _extras(ctx, h)


def torus(center, R, r, rot=None, seg=16, ring=8, cell='hair', name='torus'):
    th = np.linspace(0, 2 * math.pi, ring, endpoint=False)
    prof = [(R + r * math.cos(t), r * math.sin(t)) for t in th]
    prof = prof + [prof[0]]
    p = G.lathe(prof, seg=seg, cell=cell, name=name, close=False)
    if rot is not None:
        p.V = p.V @ np.asarray(rot).T
    p.V = p.V + np.asarray(center, float)
    p.F = G.orient_outward(p.V, p.F)
    return p


def style_loops(ctx, h):
    """Nurse Joy: short hair with two big looped side buns."""
    bot = h.get('bot') or hairline('short', h.get('part', 0.5), h.get('drop', 5.0))
    p = shell(ctx, 'hair', bot, top=h.get('top'), thick=h.get('thick', 0.6), volume=h.get('volume', 0.3))
    ctx.add(p, 'head')
    _bangs(ctx, n=5, az_span=30, el1=h.get('bang_el', 15), sweep=h.get('sweep', 7), seed=h.get('seed', 3))
    Hh = ctx.head
    for s_ in (1, -1):
        c = Hh.surf(s_ * 104, 26, 0.0) + np.array([s_ * 2.0, 0.4, -0.2])
        lp = torus(c, 2.0, 1.15, rot=G.rot_y(90) @ G.rot_z(0), seg=18, ring=8, name='loop')
        lp.g = np.clip((lp.V[:, 2] - c[2]) / 6.0 + 0.5, 0, 1)
        ctx.add(lp, 'head')
        core = G.ellipsoid(c + np.array([s_ * 0.3, 0, 0]), (0.8, 1.9, 1.9), seg=10, rings=6, cell='hair', name='loopcore')
        core.g[:] = 0.4
        ctx.add(core, 'head')
    _extras(ctx, h)


def style_bald(ctx, h):
    """Bald on top with a fringe of hair round the sides / back (horseshoe from ear to ear)."""
    top = [(0, 88), (60, 88), (95, 82), (130, 84), (180, 84)]
    bot = [(0, 100), (60, 100), (95, 106), (130, 116), (180, 120)]
    p = shell(ctx, 'hair', bot, top=top, az_range=(68, 292), nu=24, nv=6, wrap=False, thick=h.get('thick', 0.62), volume=0.0,
              ridges=16, lip=0.3, ridge_amp=0.14)
    ctx.add(p, 'head')
    _extras(ctx, h)


def style_bald_full(ctx, h):
    """Completely bald (shine handled by the toon shader)."""
    _extras(ctx, h)


def style_tuft(ctx, h):
    """Balding top with a small comb-over tuft (balding_guy) over a horseshoe."""
    style_bald(ctx, h)
    for i, az in enumerate((-18, 0, 18)):
        ctx.add(spike(ctx, az, 62, 2.4, 1.0, tilt=(0.1 * (az / 18), -0.2, 0.0), bend=(0.2 * np.sign(az) if az else 0.1, -0.2, -0.2)), 'head')


def style_long_pony(ctx, h):
    """Bruno: black spiky hair pulled back into a long thick ponytail."""
    style_spiky(ctx, {**h, 'len': h.get('len', 2.2), 'rows': [(76, 9, 0.7, 1.0), (52, 8, 0.9, 0.6), (26, 5, 0.9, 0.3)], 'fringe_len': 0.8})
    H = ctx.head
    b0 = H.surf(180, 30, 0.4)
    pts = [b0, b0 + np.array([0, 2.0, -0.6]), b0 + np.array([0, 3.2, -3.2]), b0 + np.array([0, 3.4, -6.0]), b0 + np.array([0, 3.0, -9.0])]
    ptail = tail(ctx, pts, [1.0, 1.7, 1.75, 1.3, 0.2], name='pony')
    names = add_chain_bones(ctx, 'hair_tail', [tuple(q) for q in (pts[0], pts[2], pts[3], pts[4])])
    weight_chain(ptail, [pts[0], pts[2], pts[3], pts[4]], names, hw=0.9)
    ctx.add(ptail, None)
    ctx.anim_hints['hair_tail'] = names


def style_mohawk(ctx, h):
    """Rocker: tall punk spikes on top."""
    style_spiky(ctx, {**h, 'len': h.get('len', 5.6), 'spike_w': 2.4, 'sweep_back': 0.25,
                      'rows': [(80, 8, 0.5, 1.0), (58, 8, 0.85, 0.7), (36, 6, 1.1, 0.45), (14, 4, 1.25, 0.15)], 'fringe_len': 1.1})


def style_none(ctx, h):
    _extras(ctx, h)


def _bangs(ctx, *a, **k):
    if ctx.cover:
        return
    _bangs_(ctx, *a, **k)


def _extras(ctx, h):
    """Side burns / eyebrow tufts etc. requested by the look."""
    H = ctx.head
    if h.get('sideburns'):
        for s_ in (1, -1):
            sb = lock(ctx, [(s_ * 80, 0, 0.35), (s_ * 84, -14, 0.36), (s_ * 80, -24, 0.32)], [0.9, 1.0, 0.6], 0.3, 0, name='sideburn')
            ctx.add(sb, 'head')


STYLES = {'loops': style_loops, 'short': style_short, 'spiky': style_spiky, 'flat': style_flat, 'long': style_long, 'bob': style_bob,
          'pony': style_pony, 'twin': style_twin, 'bun': style_bun, 'bald': style_bald, 'bald_full': style_bald_full,
          'tuft': style_tuft, 'long_pony': style_long_pony, 'mohawk': style_mohawk, 'none': style_none}

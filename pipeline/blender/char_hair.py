"""Hair: a scalp cap shell (cut from the head so it hugs the skull) plus soft tapered locks.

* cap     - the head surface above a hairline curve, pushed out by the hair thickness (no floating, no gaps).
* locks   - flattened tapered tubes that start inside the cap and follow the head surface before they lift off
            (fringes, side parts, tufts); tips are rounded, never cones.
* sheets  - long hair falls as a curtain that drapes over the back / shoulders using the body field, so it never
            passes through them.
* tails / buns / loops - gathered hair with a tie; tails and curtains carry secondary bones for follow-through.
"""
import math

import numpy as np

import char_geo as G
import char_shell as SH
import char_outfit as O


# ----------------------------------------------------------------------------- head reference
class HeadRef:
    def __init__(self, ctx):
        self.ctx = ctx
        P = ctx.P
        self.P = P
        self.u = P.head_h / 3.3
        self.hc = np.array([0.0, 0.18 * self.u, P.chin + 1.85 * self.u])
        self.B = ctx.body

    def dirv(self, az, el):
        a, e = np.radians(np.asarray(az, float)), np.radians(np.asarray(el, float))
        return np.stack([np.sin(a) * np.cos(e), -np.cos(a) * np.cos(e), np.sin(e)], -1)

    def skin(self, az, el):
        """Skin point seen from the skull centre along (azimuth, elevation) degrees; az 0 = front, + toward +X."""
        from mathutils import Vector
        az, el = np.broadcast_arrays(np.asarray(az, float), np.asarray(el, float))
        d = self.dirv(az, el).reshape(-1, 3)
        out = np.zeros_like(d)
        for i, dv in enumerate(d):
            hit = self.B.tree.ray_cast(Vector(self.hc.tolist()), Vector(dv.tolist()), 9.0)
            out[i] = np.array(hit[0][:]) if hit[0] is not None else self.hc + dv * 1.3 * self.u
        return out.reshape(az.shape + (3,))

    def normal(self, pts):
        import char_sdf as S
        return S.field_normals(self.B.field, np.asarray(pts).reshape(-1, 3)).reshape(np.asarray(pts).shape)

    def hairline_z(self, az, kind='short', recede=0.0):
        """World height of the hairline at azimuth az (deg, 0 = front)."""
        u, chin = self.u, self.P.chin
        a = np.abs(np.asarray(az, float))
        if kind == 'long':
            zs = [2.72, 2.55, 2.1, 1.55, 0.75, 0.2]
        else:
            zs = [2.72, 2.55, 2.12, 1.86, 1.25, 0.95]
        zs = np.array(zs) - np.array([0.0, 0.25, 0.4, 0.15, 0, 0]) * recede
        z = chin + np.interp(a, [0, 42, 72, 98, 140, 180], zs) * u
        # a natural hairline is never a ruler line: temples recede, a little irregularity
        z = z + 0.05 * u * np.sin(np.radians(np.asarray(az, float)) * 5.0 + 1.0) + 0.10 * u * np.exp(-((a - 46) / 16.0) ** 2)
        return z


def _col_jitter(n, amp, seed):
    return np.random.default_rng(seed).uniform(-amp, amp, n)


# ----------------------------------------------------------------------------- clumps sculpted into the scalp
def bump_centres(ctx, HR, n, height, up, back, seed, jitter=0.3, front_clear=True):
    """n clump centres spread over the top and back of the skull: (centres (n,3), dirs (n,3), heights (n,))."""
    rng = np.random.default_rng(seed)
    k = np.arange(n) + 0.5
    ph = (k * 2.399963) % (2 * math.pi)                      # golden-angle spiral over the hemisphere
    el = np.degrees(np.arcsin(1 - (1 - math.sin(math.radians(14))) * (k / n) ** 0.85 * 1.0 - 0.0))
    el = 14 + 74 * (1 - (k / n) ** 0.9)
    az = np.degrees(ph) - 180
    az = az + rng.uniform(-8, 8, n)
    el = el + rng.uniform(-5, 5, n)
    keep = ~((np.abs(az) < 34) & (el < 50)) if front_clear else np.ones(n, bool)
    az, el = az[keep], np.clip(el[keep], 10, 88)
    pts = HR.skin(az, el)
    nn = HR.normal(pts)
    d = nn * 0.5 + np.array([0.0, back, up]) + rng.normal(0, jitter, (len(az), 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    hs = height * (0.7 + 0.5 * rng.random(len(az)))
    return pts, d, hs


def bump_offsets(V, centres, dirs, heights, radius=0.6):
    """Displacement of every vertex by the clump it belongs to (cone-like falloff, the tallest overlapping clump wins so neighbouring
    clumps keep their own peak and a crease between them)."""
    d = np.linalg.norm(V[:, None, :] - centres[None, :, :], axis=2)
    w = np.clip(1.0 - d / radius, 0.0, 1.0) ** 1.3
    score = w * heights[None, :]
    j = score.argmax(1)
    idx = np.arange(len(V))
    disp = dirs[j] * score[idx, j][:, None]
    # a little of the runner-up keeps the valleys from being razor sharp
    score2 = score.copy()
    score2[idx, j] = 0
    j2 = score2.argmax(1)
    disp += 0.35 * dirs[j2] * score2[idx, j2][:, None]
    return disp


# ----------------------------------------------------------------------------- scalp cap
def scalp_cap(ctx, HR, thick=0.14, kind='short', recede=0.0, volume=0.0, top_rim=None, name='hair_cap', flat_top=None,
              cell='hair', keep=None, seed=0, bumps=None):
    B, P = ctx.body, ctx.P
    V = B.V
    rel = V - HR.hc
    az = np.degrees(np.arctan2(rel[:, 0], -rel[:, 1]))
    zh = HR.hairline_z(az, kind, recede)
    cut = V[:, 2] - zh
    cut = np.minimum(cut, B.headw - 0.5)
    if top_rim is not None:
        cut = np.minimum(cut, top_rim(az) - V[:, 2])
    if keep is not None:
        cut = np.minimum(cut, keep(az, V))
    el = np.degrees(np.arctan2(rel[:, 2], np.hypot(rel[:, 0], rel[:, 1])))
    crown = np.clip(np.sin(np.radians(np.clip(el, 0, 90))), 0, 1)
    th = thick * (0.8 + 0.25 * crown) + volume * crown ** 2 * (1.0 - np.clip(np.abs(az) / 180.0, 0, 1) * 0.3)
    th = th + 0.02 * SH._noise(V * 2.2, seed)
    streak = 0.06 * np.sin(np.radians(az) * 9.0 + 3.0 * SH._noise(V, seed + 5)) * (0.4 + 0.6 * crown)     # broad clumps of strands
    g = 0.3 + 0.5 * (1.0 - crown) + _col_jitter(len(V), 0.03, seed + 1) + streak
    if flat_top is not None:
        # military flat top: extra height that is then clamped to a plane
        th = th + flat_top['extra'] * crown ** 1.5
    ov = None
    if bumps is not None:
        ov = bump_offsets(V, *bumps)
        g = g + 0.16 * np.clip(np.linalg.norm(ov, axis=1) / max(bumps[2].max(), 1e-6), 0, 1)          # tips of the clumps catch the light
    p = SH.shell_from_body(ctx, cut, th, cell, name, g=g, rim=0.02, cover=False, offset_vec=ov)
    if p is not None:
        p.ao_gain = 0.45
    if p is not None and flat_top is not None:
        top = HR.P.head_top + flat_top['plateau']
        p.V[:, 2] = np.minimum(p.V[:, 2], top)
    return p


# ----------------------------------------------------------------------------- locks
def lock_path(HR, az0, el0, az1, el1, n=8, off0=0.06, off1=0.06, lift=0.0, lift_pow=2.0):
    """Path from (az0, el0) to (az1, el1) hugging the head, `off` above the skin (interpolated) plus a lift profile."""
    t = np.linspace(0, 1, n)
    az = az0 + (az1 - az0) * t
    el = el0 + (el1 - el0) * t
    sk = HR.skin(az, el)
    nn = HR.normal(sk)
    off = off0 + (off1 - off0) * t + lift * t ** lift_pow
    return sk + nn * off[:, None], nn


def tapered(ctx, path, width, thick, name, cell='hair', seg=6, tip=0.18, g0=0.35, g1=0.85, ref=None, root_bury=0.0):
    """Flattened tapered tube along `path` with a rounded tip (width across, thick along the surface normal)."""
    path = np.asarray(path, float)
    n = len(path)
    t = np.linspace(0, 1, n)
    prof = np.sqrt(np.clip(1 - t ** 3.0, 0, 1))
    prof = tip + (1 - tip) * prof
    w = width * 0.5 * prof
    h = thick * 0.5 * prof
    ref = ref if ref is not None else (0, 0, 1)
    p = G.loft(path, np.stack([h, w], 1), seg=seg, cell=cell, name=name, caps=(0.0 if root_bury else None, 0.9), ref=ref)
    p.g = np.clip(g0 + (g1 - g0) * np.clip(G.smoothstep(0, 1, np.linalg.norm(p.V - path[0], axis=1) / max(np.linalg.norm(path[-1] - path[0]), 1e-3)), 0, 1), 0, 1)
    return p


def add_lock(ctx, HR, az0, el0, az1, el1, width, thick, name='lock', n=7, lift=0.0, off=0.05, seg=6, tip=0.2, g0=0.5, g1=0.85, jit=0.0):
    path, nn = lock_path(HR, az0, el0, az1, el1, n=n, off0=off, off1=off + 0.02, lift=lift)
    # bury the root a little inside the cap
    path[0] = path[0] - nn[0] * 0.03 - nn[0] * 0.0
    p = tapered(ctx, path, width, thick, name, seg=seg, tip=tip, g0=g0 + jit, g1=g1 + jit, ref=nn[0])
    p.ao_gain = 0.35
    ctx.add(p, 'head')
    return p


def add_tuft(ctx, HR, az, el, length, width, direction, name='tuft', curl=0.25, thick=None, off=0.05, g0=0.3, g1=0.75):
    """Soft tuft: rises from the scalp along `direction` (unit vector, biased by the local normal), rounded tip."""
    sk = HR.skin(az, el)
    nn = HR.normal(sk)
    d = direction / np.linalg.norm(direction)
    n = 6
    pts = [sk - nn * 0.0]
    cur = sk + nn * off
    pts.append(cur)
    for k in range(1, n):
        s = k / (n - 1)
        dv = nn * (1 - s) * 0.85 + d * (0.35 + 0.65 * s)
        dv = dv / np.linalg.norm(dv)
        dv = dv + np.array([0, 0, -1.0]) * curl * s * s * 0.6            # tips droop a little
        dv = dv / np.linalg.norm(dv)
        cur = cur + dv * length / (n - 1)
        pts.append(cur)
    pts = np.array(pts)
    p = tapered(ctx, pts, width, thick or width * 0.62, name, seg=6, tip=0.34, g0=g0, g1=g1, ref=nn)
    p.ao_gain = 0.35
    ctx.add(p, 'head')
    return p


# ----------------------------------------------------------------------------- curtains and tails
def add_bones(ctx, prefix, pts, parent='head'):
    names = []
    par = parent
    for i in range(len(pts) - 1):
        nm = '%s%d' % (prefix, i + 1)
        ctx.extra_bones.append((nm, par, tuple(map(float, pts[i])), tuple(map(float, pts[i + 1]))))
        names.append(nm)
        par = nm
    return names


def chain_weights(part, pts, names, root='head', hw=0.7, start_below=None):
    bones = [root] + names
    P = [np.asarray(pts[0]) + np.array([0, 0, 1.0])] + [np.asarray(p) for p in pts]
    G.add_weights(part, G.chain_weights(part.V, P, bones, hw))
    return part


def hair_curtain(ctx, HR, length, az_span=(-118, 118), n_cols=15, n_rows=11, thick=0.13, name='hair_back', cell='hair', seed=0,
                 bones=True, front_len=None, layer=0.0):
    """Long hair draped down the back: columns start on the scalp, follow the skull to the nape and fall with gravity
    outside the body (field-based clearance)."""
    P, B = ctx.P, ctx.body
    u = HR.u
    azs = 180.0 + np.linspace(az_span[0], az_span[1], n_cols)          # columns around the back of the head (az 180 = behind)
    cols = []
    rng = np.random.default_rng(seed)
    z_nape = P.chin + 0.7 * u
    z_end0 = z_nape - length
    for a in azs:
        aa = abs(a - 180.0)                                            # angular distance from straight behind
        # rows: head surface part, then the drop
        el_top = 62 - 25 * min(aa / 100.0, 1.0)
        ns = 5
        els = np.linspace(el_top, -32, ns)
        head_part = HR.skin(np.full(ns, a), els)
        nn = HR.normal(head_part)
        head_part = head_part + nn * (thick * 0.6 + 0.05 + layer)
        z_last = head_part[-1, 2]
        end = z_end0 + (0.4 * u) * (1 - np.cos(np.radians(min(aa, 160)))) * 0.5 - 0.35 * rng.random() * u * (1 if front_len is None else 0)
        if front_len is not None and aa < 80:
            end = z_nape - front_len
        zs = np.linspace(z_last, end, n_rows - ns + 1)[1:]
        dirv = np.array([math.sin(math.radians(a)), -math.cos(math.radians(a))])
        ang = np.array([math.radians(a)])
        rows = list(head_part)
        prev_r = np.linalg.norm(head_part[-1][:2] - np.array([0.0, 0.1]))
        for z in zs:
            r_env = float(O.envelope_radii(ctx, z, ang, margin=0.0, cy=0.1)[0])
            r = max(r_env, prev_r * 0.985) + thick + 0.3 + layer
            prev_r = r
            rows.append(np.array([dirv[0] * r, 0.1 + dirv[1] * r, z]))
        cols.append(np.array(rows))
    Pg = np.array(cols)                # (n_cols, n_rows, 3)
    g = np.tile(np.linspace(0.3, 0.9, Pg.shape[1])[None, :], (Pg.shape[0], 1)) + _col_jitter(Pg.shape[0], 0.05, seed)[:, None]
    p = G.solid_surface(Pg, thick, cell=cell, name=name, g=g, offset=0.5, outward_from=(0, 0.1, P.chin), inner='full')
    ctx.add(p, 'head')
    if bones:
        mid = Pg[Pg.shape[0] // 2]
        pts = mid[max(Pg.shape[1] - 6, 0)::2]
        pts = np.vstack([pts[:1] + np.array([0, 0, 0.0]), pts])
        pts = pts[:5]
        names = add_bones(ctx, 'hair_back', pts)
        chain_weights(p, pts, names, root='head', hw=0.9)
        ctx.anim_hints.setdefault('hair_back', []).extend(names)
    return p


def hair_tail(ctx, HR, root_az, root_el, length, radius, name='hair_tail', sideways=0.0, back=0.5, drop=1.0, cell='hair', tie=None,
              bones=True, curl=0.0, seed=0, prefix='hair_tail'):
    """Ponytail / pigtail: tube from a point on the skull, out and down, tapered, with a tie ring at its root."""
    P = ctx.P
    u = HR.u
    sk = HR.skin(root_az, root_el)
    nn = HR.normal(sk)
    n = 8
    pts = [sk + nn * 0.01, sk + nn * 0.05]
    cur = sk + nn * 0.05
    d0 = nn * 0.5 + np.array([sideways, back, -0.1])
    d0 /= np.linalg.norm(d0)
    step = length / (n - 1)
    dvec = d0
    for k in range(1, n):
        s = k / (n - 1)
        g_ = np.array([0, 0, -1.0]) * (0.35 + 1.8 * s ** 1.1) * drop
        dvec = dvec * (1 - 0.3 * s) + g_ * (0.3 * s + 0.3)
        dvec = dvec / np.linalg.norm(dvec)
        cur = cur + dvec * step
        pts.append(cur)
    pts = np.array(pts)
    path = G.catmull(pts, 12)
    t = np.linspace(0, 1, len(path))
    r = radius * (0.72 + 0.55 * np.sin(np.pi * np.clip(t * 1.05, 0, 1)) ** 0.8) * (1 - 0.65 * t ** 2.2)
    r[0] = radius * 0.75
    p = G.loft(path, np.stack([r, r * 0.92], 1), seg=8, cell=cell, name=name, caps=(0.4, 0.55), ref=(1, 0, 0))
    p.g = np.clip(G.smoothstep(0, 1, np.linalg.norm(p.V - path[0], axis=1) / max(np.linalg.norm(path[-1] - path[0]), 1e-3)) * 0.6 + 0.3, 0, 1)
    ctx.add(p, 'head')
    if bones:
        jp = pts[1:][::2][:5]
        if len(jp) >= 2:
            names = add_bones(ctx, prefix, jp)
            chain_weights(p, jp, names, root='head', hw=0.55)
            ctx.anim_hints.setdefault('hair_tail' if 'twin' not in prefix else 'hair_twin', []).extend(names)
    if tie:
        tc = ctx.ramp('hairtie', 'flat', ctx.col(tie))
        ring = torus(pts[2], path[3] - path[2], radius * 0.95, radius * 0.24, cell=tc, name='tie')
        ctx.add(ring, 'head')
    return p, pts


def torus(center, axis, R, r, seg=14, ring=6, cell='hair', name='torus'):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    a = np.cross(axis, [0, 0, 1.0])
    if np.linalg.norm(a) < 1e-3:
        a = np.cross(axis, [1.0, 0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(axis, a)
    th = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    ph = np.linspace(0, 2 * math.pi, ring, endpoint=False)
    TH, PH = np.meshgrid(th, ph, indexing='ij')
    rad = R + r * np.cos(PH)
    Pt = (np.asarray(center)[None, None, :] + rad[..., None] * (np.cos(TH)[..., None] * a + np.sin(TH)[..., None] * b) + (r * np.sin(PH))[..., None] * axis)
    F = G.grid_tris(seg, ring, wrap_u=True, wrap_v=True)
    p = G.Part(name, Pt.reshape(-1, 3), F, cell, g=np.full(seg * ring, 0.5))
    if (np.cross(p.V[p.F[:, 1]] - p.V[p.F[:, 0]], p.V[p.F[:, 2]] - p.V[p.F[:, 0]]) * (p.V[p.F[:, 0]] - np.asarray(center))).sum() < 0:
        p.F = p.F[:, ::-1].copy()
    return p


def hair_bun(ctx, HR, az, el, radius, name='bun', cell='hair', band=None, squash=0.85):
    sk = HR.skin(az, el)
    nn = HR.normal(sk)
    c = sk + nn * (radius * 0.72)
    p = ellipsoid_part(c, (radius, radius * squash, radius * 0.9), name=name, cell=cell, seg=14, rings=9)
    p.g = np.clip(0.3 + 0.5 * (p.V[:, 2] - c[2]) / radius * -0.5 + 0.4, 0, 1)
    ctx.add(p, 'head')
    if band:
        bc = ctx.ramp('hairtie', 'flat', ctx.col(band))
        ctx.add(torus(c - nn * radius * 0.45, nn, radius * 0.72, radius * 0.16, cell=bc, name='bun_band'), 'head')
    return p


def ellipsoid_part(c, r, seg=14, rings=9, name='ell', cell='hair'):
    th = np.linspace(0, math.pi, rings + 1)
    ph = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    PH, TH = np.meshgrid(ph, th, indexing='ij')
    Pt = np.asarray(c) + np.stack([r[0] * np.sin(TH) * np.cos(PH), r[1] * np.sin(TH) * np.sin(PH), r[2] * np.cos(TH)], -1)
    return _grid_out(Pt, name, cell, c)


def _grid_out(Pt, name, cell, centre):
    nu, nv = Pt.shape[:2]
    F = G.grid_tris(nu, nv, wrap_u=True)
    V = Pt.reshape(-1, 3)
    a, b, c_ = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    ok = np.linalg.norm(np.cross(b - a, c_ - a), axis=1) > 1e-8
    F = F[ok]
    p = G.Part(name, V, F, cell, g=np.full(len(V), 0.5))
    a, b, c_ = p.V[p.F[:, 0]], p.V[p.F[:, 1]], p.V[p.F[:, 2]]
    if (np.cross(b - a, c_ - a) * ((a + b + c_) / 3 - np.asarray(centre))).sum() < 0:
        p.F = p.F[:, ::-1].copy()
    return p


# ----------------------------------------------------------------------------- styles
def _th(h, default=0.14):
    return h.get('thick', 0.55) / 0.55 * default


def style_bald(ctx, HR, h):
    """Bald; with `sides` a thin band of hair round the ears and the back of the head (old men)."""
    if h.get('sides'):
        p = scalp_cap(ctx, HR, thick=0.11, kind='short', name='hair_sides',
                      keep=lambda az, V: np.minimum(np.abs(az) - 62.0, (HR.P.chin + 2.1 * HR.u) - V[:, 2]))
        if p is not None:
            ctx.add(p, 'head')


def _add_cap(ctx, HR, h, **kw):
    top_rim = getattr(ctx, 'hat_rim', None) if ctx.cover else None
    p = scalp_cap(ctx, HR, top_rim=top_rim, **kw)
    if p is not None:
        ctx.add(p, 'head')
    return p


def style_short(ctx, HR, h):
    """Short cut with a side part: cap + a sweep of fringe locks falling from the parting."""
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), volume=h.get('volume', 0.08), kind='short', recede=h.get('recede', 0.0), seed=h.get('seed', 1))
    if ctx.cover:
        return
    part = h.get('part', 0.4)
    side = 1 if part >= 0 else -1
    n = h.get('bang_n', 4)
    rng = np.random.default_rng(h.get('seed', 2))
    u = HR.u
    # locks combed from the parting line over the forehead
    for i in range(n):
        f = (i + 0.5) / n
        az0 = side * (-30 + 70 * f) * (1.0 if abs(part) > 0.05 else 0.0) + (0 if abs(part) > 0.05 else (f - 0.5) * 70)
        az0 = (f - 0.5) * 64
        el0 = 47 + 4 * math.sin(f * 3)
        az1 = az0 + side * (14 + 10 * (1 - f)) * (0.4 + abs(part))
        el1 = 29 - 4 * f + rng.uniform(-2, 2)
        add_lock(ctx, HR, az0, el0, az1, el1, width=0.58 * u, thick=0.16 * u, name='fringe', n=6, lift=0.05, off=0.09, jit=rng.uniform(-0.05, 0.05))
    # sideburn / temple locks
    for sd in (1, -1):
        add_lock(ctx, HR, sd * 75, 36, sd * 84, 6, width=0.5 * u, thick=0.14 * u, name='temple', n=5, off=0.08)


def style_spiky(ctx, HR, h, flat=False):
    """Tousled swept-up hair: the scalp cap is sculpted into overlapping soft clumps that rise and sweep back (no cones), a few short
    tufts break the silhouette and a fringe falls over the brow."""
    u = HR.u
    rng = np.random.default_rng(h.get('seed', 5))
    ln = h.get('len', 3.8)
    height = (0.42 + 0.11 * (ln - 2.5)) * u
    back = h.get('sweep_back', 0.45)
    up = h.get('up', 0.55) + 0.5
    n = h.get('clumps', 46)
    bumps = None
    if not ctx.cover:
        cen, dirs, hs = bump_centres(ctx, HR, n, height, up, back, h.get('seed', 5))
        bumps = (cen, dirs, hs, 0.5 * u)
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), volume=h.get('volume', 0.04), kind='short', seed=h.get('seed', 3), bumps=bumps)
    if ctx.cover:
        return
    # a few short tufts on the outline
    L = height * 1.05
    for i in range(10):
        az = -180 + 360 * (i + 0.5) / 10 + rng.uniform(-10, 10)
        if abs(az) < 40:
            continue
        el = 30 + rng.uniform(0, 30)
        a = math.radians(az)
        d = np.array([math.sin(a) * 0.7, -math.cos(a) * 0.7 + back * 0.5, up * 0.9])
        add_tuft(ctx, HR, az, el, L * (0.8 + 0.4 * rng.random()), 0.5 * u, d, name='tuft', curl=0.25, g0=0.32, g1=0.8)
    # forehead fringe: short soft locks falling over the brow
    for i, az in enumerate(h.get('fringe_az', (-24, -7, 10, 26))):
        sgn = 1 if az >= 0 else -1
        add_lock(ctx, HR, az, 50, az + sgn * 10, 33 - 2 * i % 3, width=0.5 * u, thick=0.15 * u, name='fringe', n=6, lift=0.1, off=0.09)
    for sd in (1, -1):
        add_lock(ctx, HR, sd * 76, 36, sd * 84, 8, width=0.5 * u, thick=0.14 * u, name='temple', n=5, off=0.08)


def style_flat(ctx, HR, h):
    """Flat top (Surge): short crew cut that ends in a flat plateau."""
    u = HR.u
    _add_cap(ctx, HR, h, thick=0.14, volume=0.0, kind='short', flat_top={'extra': 0.42, 'plateau': 0.28}, seed=4)


def style_mohawk(ctx, HR, h):
    u = HR.u
    p = _add_cap(ctx, HR, h, thick=0.1, kind='short', recede=1.0, seed=6,
                 name='hair_cap')
    L = (0.55 + 0.13 * (h.get('len', 3.9) - 2.5)) * u
    # ridge of upright tufts from the forehead over the crown to the nape
    for i, el in enumerate(np.linspace(70, 5, 9)):
        az = 0 if i < 4 else 180
        e_ = el if i < 4 else 20 + i * 6
        e_ = 66 - i * 4 if i < 5 else 78 - (i - 4) * 14
        az = 0 if i < 5 else 180
        add_tuft(ctx, HR, az, e_, L * (1.05 - 0.06 * abs(i - 3)), 0.55 * u, np.array([0, 0.4 if az == 180 else -0.35, 1.0]), name='mohawk', g0=0.3, g1=0.8)


def style_long(ctx, HR, h):
    """Long hair: cap, a curtain down the back, side locks in front of the shoulders and a parted fringe."""
    u = HR.u
    P = ctx.P
    ln = h.get('length', 1.0)
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), volume=h.get('volume', 0.05), kind='long', seed=h.get('seed', 7))
    if ctx.cover:
        return
    length = (3.6 + 4.6 * ln) * u
    hair_curtain(ctx, HR, length, thick=0.16, seed=h.get('seed', 7))
    part = h.get('part', 0.0)
    side = 1 if part >= 0 else -1
    n = h.get('bang_n', 5)
    rng = np.random.default_rng(3)
    for i in range(n):
        f = (i + 0.5) / n
        az0 = (f - 0.5) * 70
        az1 = az0 + side * 14 * (0.5 + abs(part)) + (f - 0.5) * 30
        add_lock(ctx, HR, az0, 46, az1, 30 - 3 * abs(f - 0.5) * 4, width=0.6 * u, thick=0.16 * u, name='fringe', n=6, lift=0.05, off=0.09)
    # front side locks drape over the shoulders on both sides of the face
    for sd in (1, -1):
        drape_lock(ctx, HR, sd, length * 0.75, wave=h.get('wave', 0.2))


def drape_lock(ctx, HR, sd, length, wave=0.2, name='side_lock'):
    """A lock in front of the shoulder: starts behind the temple, follows the jaw, falls onto the chest side."""
    P, B = ctx.P, ctx.body
    u = HR.u
    pts = []
    for k, (az, el, off) in enumerate(((sd * 82, 42, 0.1), (sd * 88, 12, 0.12), (sd * 92, -18, 0.14))):
        sk = HR.skin(az, el)
        pts.append(sk + HR.normal(sk) * off)
    z0 = pts[-1][2]
    for z in np.linspace(z0 - 0.6, z0 - length, 5):
        ang = np.array([math.radians(sd * 62)])
        r = float(O.envelope_radii(ctx, z, ang, cy=-0.1)[0]) + 0.6
        pts.append(np.array([math.sin(ang[0]) * r, -0.1 - math.cos(ang[0]) * r, z]))
    path = G.catmull(np.array(pts), 14)
    t = np.linspace(0, 1, len(path))
    w = (0.55 + 0.12 * np.sin(t * 6) * wave) * u * (1 - 0.6 * t ** 3)
    p = G.loft(path, np.stack([w * 0.5, 0.075 * np.ones_like(w) * u * 1.4], 1), seg=6, cell='hair', name=name, caps=(None, 0.9), ref=(0, 1, 0))
    p.g = np.clip(0.35 + 0.5 * t.repeat(1)[0] * 0 + G.smoothstep(0, 1, (p.V[:, 2] - z0) / (-length)) * 0.5, 0, 1)
    ctx.add(p, 'head')


def style_pony(ctx, HR, h):
    u = HR.u
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), volume=h.get('volume', 0.05), kind='short', seed=h.get('seed', 8))
    if ctx.cover:
        return
    ln = h.get('length', 1.0)
    side = h.get('side', 0)
    style_fringe(ctx, HR, h)
    if side:
        hair_tail(ctx, HR, side * 118, 42, (2.4 + 2.6 * ln) * u, 0.62 * u, sideways=side * 0.7, back=0.1, drop=1.0, tie=h.get('tie', 'accent'))
    else:
        hair_tail(ctx, HR, 180, 34, (2.6 + 3.6 * ln) * u, 0.7 * u, sideways=0.0, back=0.9, drop=1.0, tie=h.get('tie', 'accent'))


def style_fringe(ctx, HR, h, n=None):
    u = HR.u
    part = h.get('part', 0.3)
    side = 1 if part >= 0 else -1
    n = n or h.get('bang_n', 4)
    for i in range(n):
        f = (i + 0.5) / n
        az0 = (f - 0.5) * 60
        az1 = az0 + side * 12
        add_lock(ctx, HR, az0, 47, az1, 30, width=0.55 * u, thick=0.15 * u, name='fringe', n=6, lift=0.05, off=0.09)
    for sd in (1, -1):
        add_lock(ctx, HR, sd * 76, 36, sd * 84, 8, width=0.5 * u, thick=0.14 * u, name='temple', n=5, off=0.08)


def style_twin(ctx, HR, h):
    u = HR.u
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), kind='short', seed=9)
    if ctx.cover:
        return
    style_fringe(ctx, HR, h, n=5)
    ln = h.get('length', 1.0)
    for sd in (1, -1):
        hair_tail(ctx, HR, sd * 100, 34, (2.2 + 2.0 * ln) * u, 0.58 * u, sideways=sd * 0.9, back=0.05, drop=1.1, tie=h.get('tie', 'accent'),
                  name='twin_tail', prefix='hair_twin%s' % ('L' if sd > 0 else 'R'))


def style_bun(ctx, HR, h):
    u = HR.u
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), volume=h.get('volume', 0.05), kind='short', seed=h.get('seed', 10))
    if ctx.cover:
        return
    style_fringe(ctx, HR, h, n=h.get('bang_n', 4))
    r = h.get('bun_r', 2.5) * 0.3 * u
    if h.get('bun', 'top') == 'top':
        hair_bun(ctx, HR, 180, 62, r, band=h.get('bun_band') or h.get('tie'))
    else:
        hair_bun(ctx, HR, 180, 24, r, band=h.get('bun_band') or h.get('tie'))


def style_loops(ctx, HR, h):
    """Nurse Joy: two side loops."""
    u = HR.u
    _add_cap(ctx, HR, h, thick=_th(h, 0.15), volume=0.08, kind='short', seed=11)
    style_fringe(ctx, HR, h, n=5)
    for sd in (1, -1):
        sk = HR.skin(sd * 98, 24)
        nn = HR.normal(sk)
        c = sk + nn * 0.72 * u
        ctx.add(torus(c, np.array([sd * 0.3, 0.9, 0.0]) + nn * 0.1, 0.6 * u, 0.3 * u, seg=18, ring=8, name='loop'), 'head')


def style_tuft(ctx, HR, h):
    """Balding comb-over: hair only round the sides plus a few strands across the top."""
    u = HR.u
    p = scalp_cap(ctx, HR, thick=0.1, kind='short', name='hair_sides',
                  keep=lambda az, V: np.minimum(np.abs(az) - 58.0, (HR.P.chin + 2.15 * HR.u) - V[:, 2]))
    if p is not None:
        ctx.add(p, 'head')
    for i in range(4):
        f = i / 3
        add_lock(ctx, HR, 60 - 100 * f * 0, 62 - 3 * i, -70 + 6 * i * 0, 66 - 3 * i, width=0.22 * u, thick=0.06 * u, name='strand', n=8, off=0.06)


def style_long_pony(ctx, HR, h):
    """Bruno: long spiky hair gathered in a ponytail."""
    u = HR.u
    _add_cap(ctx, HR, h, thick=0.14, kind='short', seed=12)
    style_fringe(ctx, HR, dict(h, part=0.0), n=4)
    hair_tail(ctx, HR, 180, 30, 5.2 * u, 0.75 * u, back=1.0, drop=1.0, tie='#c8c8d0')


STYLES = {'short': style_short, 'spiky': style_spiky, 'flat': style_flat, 'mohawk': style_mohawk, 'long': style_long, 'pony': style_pony,
          'twin': style_twin, 'bun': style_bun, 'loops': style_loops, 'bald': style_bald, 'tuft': style_tuft, 'long_pony': style_long_pony,
          'none': lambda ctx, HR, h: None}


def build_hair(ctx, hair):
    st = hair.get('style', 'short')
    color = ctx.col(hair.get('color'), 'hair')
    ctx.ramp('hair', 'hair', color)
    HR = HeadRef(ctx)
    ctx.headref = HR
    fn = STYLES[st]
    fn(ctx, HR, hair)

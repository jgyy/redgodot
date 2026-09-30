"""Clothing as offset shells of the body (see char_shell.py), driven by character_looks.json.

Every garment is cut from the body mesh with smooth scalar fields (weights, heights, limb parameters), so hems,
cuffs, sleeve seams and necklines are exact level lines and the cloth sits a controlled distance above the skin
everywhere.  Free-hanging cloth (skirts, dresses, long coats, robes) is a radial loft around the body envelope.
"""
import math

import numpy as np

import char_geo as G
import char_mesh as M
import char_paint as PT
import char_sdf as S
import char_shell as SH

# fabric thickness above the skin (rows; 1 row = 6.25 cm at the nominal scale)
T_THIN, T_SHIRT, T_JACKET, T_COAT, T_PANTS, T_JEANS, T_GLOVE, T_SHOE = 0.07, 0.115, 0.14, 0.17, 0.08, 0.09, 0.055, 0.11


def cloth_cell(ctx, name, spec, default='shirt', **kw):
    stripes = kw.pop('stripes', None)
    if stripes:
        stripes = [(a, b, ctx.col(c)) for a, b, c in stripes]
    hem = kw.pop('hem', None)
    return ctx.ramp(name, 'cloth', ctx.col(spec, default), stripes=stripes, hem=ctx.col(hem) if hem else None, **kw)


def smooth_step(a, b, x):
    return G.smoothstep(a, b, x)


def map_z(P, old):
    """Heights in character_looks.json were authored on the old chibi rig (ankle 1.4, hip 6.7, waist 8.2, chest 9.7, shoulder 11);
    map them onto the realistic body's landmarks."""
    return float(np.interp(old, [0.0, 1.4, 3.9, 6.7, 8.2, 9.7, 11.0, 12.5], [0.0, P.ankle, P.knee, P.hip, P.waist, P.chest, P.shoulder, P.neck_base + 1.0]))


def fold_noise(B, amp, seed, mask=None):
    """Soft cloth wrinkles: low-frequency noise on the body positions, stronger where `mask` (0..1) is high."""
    n = SH._noise(B.V * 1.7, seed)
    if mask is not None:
        n = n * mask
    return amp * n


# ----------------------------------------------------------------------------- neckline / collar helpers
def neck_hole(ctx, depth=0.0, wide=1.0, front_only=False):
    """>0 outside the neck opening of a garment (crew: a small ellipse round the neck; V: extended down the chest)."""
    B, P = ctx.body, ctx.P
    x, y, z = B.V[:, 0], B.V[:, 1], B.V[:, 2]
    zc = P.neck_base + 0.55 * P.s - depth * 0.5
    rz = 0.7 * P.s + depth * 0.5
    rx = 1.35 * P.ls * wide
    ry = 1.6 * P.ls
    v = (x / rx) ** 2 + ((y - 0.1) / ry) ** 2 + ((z - zc) / rz) ** 2 - 1.0
    if front_only:
        v = np.where(y > 0.1, 1.0, v)
    return v * 0.6


def neck_z(ctx, kind):
    P = ctx.P
    return P.neck_base + {'crew': 0.45, 'polo': 0.5, 'high': 1.15, 'none': 0.2}.get(kind, 0.45) * P.s


# ----------------------------------------------------------------------------- tops
def top_fields(ctx):
    B = ctx.body
    torso = B.trunk
    arm = {sd: B.arm[sd] for sd in (1, -1)}
    return torso, arm


def torso_weight(ctx):
    """Trunk weight plus the top of the thighs above the crotch: hips and hip sides belong to the body of a shirt / coat even though
    the skin weights hand them to the thighs."""
    B, P = ctx.body, ctx.P
    z = B.V[:, 2]
    thighs = B.w.get('thigh_L', 0) + B.w.get('thigh_R', 0)
    return np.maximum(B.trunk, thighs * smooth_step(P.crotch - 1.0, P.crotch + 0.5, z))


def torso_cut(ctx, hem_z, neck, open_front=None):
    """Torso garment region: torso side of the shoulder seam, above the hem, below the neck."""
    B = ctx.body
    torso = torso_weight(ctx)
    arm_max = np.maximum(B.arm[1], B.arm[-1])
    c = np.minimum.reduce([torso - arm_max, torso - 0.3, B.V[:, 2] - hem_z, neck])
    if open_front is not None:
        c = np.minimum(c, open_front)
    return c


def sleeve_cut(ctx, sd, end_t, neck=None):
    B = ctx.body
    c = np.minimum.reduce([B.arm[sd] - B.trunk, B.arm[sd] - 0.3, end_t - B.arm_t[sd]])
    return c


def open_front_cut(ctx, w0, w1, z_lo, z_hi):
    """Front opening (V of a coat / jacket): keep |x| >= w(z) on the front, everything on the back."""
    B = ctx.body
    z = B.V[:, 2]
    t = np.clip((z - z_lo) / max(z_hi - z_lo, 1e-6), 0, 1)
    w = w0 + (w1 - w0) * t
    return np.maximum(np.abs(B.V[:, 0]) - w, (B.V[:, 1] - 0.15) * 3.0)


def thickness_field(ctx, base, hem_z=None, loose=0.0, loose_from=None, loose_to=None):
    B, P = ctx.body, ctx.P
    z = B.V[:, 2]
    t = np.full(len(z), float(base))
    if loose and hem_z is not None:
        top = P.chest if loose_from is None else loose_from
        k = smooth_step(top, hem_z, z)
        t = t + loose * k * (0.5 + 0.5 * np.clip(-B.N[:, 1] * 1.0 + 0.4, 0, 1))
    return t


def build_top(ctx, t):
    typ = t.get('type', 'shirt')
    fn = TOPS.get(typ, top_shirt)
    fn(ctx, t)


def top_g(ctx, hem_z, top_z):
    z = ctx.body.V[:, 2]
    return np.clip((z - hem_z) / max(top_z - hem_z, 1e-6), 0, 1)


def _trim_cell(ctx, t, key='trim', default='accent'):
    return cloth_cell(ctx, 'trim_' + key, t.get(key, default) if t.get(key) not in (None, True, False) else default, default)


def top_shirt(ctx, t, thick=T_SHIRT, long_default=False):
    P, B = ctx.P, ctx.body
    sleeves = t.get('sleeves', 'short')
    hem_z = t.get('hem_z')
    hem_z = P.hip - 0.3 * P.s if hem_z is None else max(map_z(P, hem_z), P.crotch + 0.5 * P.s)
    neck_kind = t.get('collar', 'crew')
    depth = t.get('v', 0.0)
    neck = neck_hole(ctx, depth=depth)
    body_col = t.get('color')
    stripes = t.get('stripes')
    hem = t.get('hem')
    cell = cloth_cell(ctx, 'top', body_col, 'shirt', stripes=stripes)
    sleeve_col = t.get('sleeve_color')
    scell = cloth_cell(ctx, 'sleeve', sleeve_col, 'shirt') if sleeve_col else cell
    th = thickness_field(ctx, thick, hem_z, loose=t.get('loose', 0.04), loose_from=P.chest)
    th = th + fold_noise(B, 0.012, 3, smooth_step(P.chest, P.waist, B.V[:, 2]))
    g = top_g(ctx, hem_z, P.neck_base)
    ctop = torso_cut(ctx, hem_z, neck)
    cut_sleeve = {}
    if sleeves != 'none':
        end = {'short': 0.29, 'three': 0.47, 'long': 0.66}[sleeves] if sleeves in ('short', 'three', 'long') else 0.66
        for sd in (1, -1):
            cut_sleeve[sd] = sleeve_cut(ctx, sd, end)
    if sleeve_col:
        p = SH.shell_from_body(ctx, ctop, th, cell, 'top', g=g)
        ctx.add(p)
        for sd, c in cut_sleeve.items():
            th_s = np.full(len(th), thick + 0.005)
            ps = SH.shell_from_body(ctx, c, th_s, scell, 'sleeve%s' % ('L' if sd > 0 else 'R'), g=B.arm_t[sd])
            ctx.add(ps)
    else:
        allc = ctop
        for sd, c in cut_sleeve.items():
            allc = np.maximum(allc, c)
        p = SH.shell_from_body(ctx, allc, th, cell, 'top', g=g)
        ctx.add(p)
    # hem / cuff trim bands
    if t.get('hem_band') or t.get('hem'):
        tc = cloth_cell(ctx, 'trim_hem', t.get('hem') if isinstance(t.get('hem'), str) else 'accent', 'accent')
        c = np.minimum(ctop, hem_z + 0.55 - B.V[:, 2])
        ctx.add(SH.shell_from_body(ctx, c, th + 0.028, tc, 'hemband', g=g, cover=False))
    if t.get('cuff') and sleeves != 'none':
        cc = cloth_cell(ctx, 'trim_cuff', t['cuff'] if isinstance(t['cuff'], str) else 'accent', 'accent')
        end = {'short': 0.29, 'three': 0.47, 'long': 0.66}[sleeves]
        for sd in (1, -1):
            c = np.minimum(cut_sleeve[sd], B.arm_t[sd] - (end - 0.06))
            ctx.add(SH.shell_from_body(ctx, c, np.full(len(th), thick + 0.03), cc, 'cuff', g=B.arm_t[sd], cover=False))
    collar(ctx, t, thick, neck_kind, cell)
    return p


def collar(ctx, t, thick, kind, cell):
    """Neck band / polo collar / high turtleneck round the neck."""
    if kind == 'none':
        return
    P, B = ctx.P, ctx.body
    z = B.V[:, 2]
    ccol = t.get('collar_color', 'shirt')
    cc = cloth_cell(ctx, 'collar', ccol, 'shirt')
    top = neck_z(ctx, kind)
    neckw = B.w.get('neck', np.zeros(len(z)))
    reg = neckw - 0.35
    c = np.minimum.reduce([reg, top - z, z - (P.neck_base - 0.25 * P.s)])
    th = np.full(len(z), thick + (0.05 if kind in ('polo', 'high') else 0.035))
    g = np.clip((z - (P.neck_base - 0.25)) / max(top - (P.neck_base - 0.25), 0.1), 0, 1)
    if kind == 'polo':
        # front placket opening between two flaps
        c = np.minimum(c, np.where(B.V[:, 1] < 0.2, np.abs(B.V[:, 0]) - 0.22, 1.0))
    ctx.add(SH.shell_from_body(ctx, c, th, cc, 'collar', g=g, cover=False))


def top_jacket(ctx, t):
    p = top_shirt(ctx, dict(t, loose=t.get('loose', 0.07)), thick=T_JACKET)
    add_front_line(ctx, t, T_JACKET)
    return p


def add_front_line(ctx, t, thick):
    """Zip / button placket down the centre front as a raised strip on top of the garment."""
    if not (t.get('zip') or t.get('buttons')):
        return
    import char_face as FC
    P, B = ctx.P, ctx.body
    z0 = P.lift + (t.get('hem_z') or (P.hip / P.s - 0.3)) * P.s if t.get('hem_z') else P.hip - 0.3
    z1 = P.neck_base + 0.35
    zs = np.linspace(z0, z1, 14)
    pts = np.stack([np.zeros(14), np.full(14, -3.0), zs], 1)
    pts, nrm = FC.lift_to_skin(ctx, pts, 0.03, layer=True)
    col = t.get('zip_color') or ('#c8c8d0' if t.get('zip') else 'accent')
    cell = ctx.ramp('zip', 'metal' if t.get('zip') else 'cloth', ctx.col(col))
    ctx.add(FC.ribbon(pts, nrm, 0.09 if t.get('zip') else 0.22, cell, 'placket', bone='chest', sag=0.2))
    if t.get('buttons'):
        bc = ctx.ramp('button', 'metal', ctx.col(t.get('button_color', '#c8c8d0')))
        for zb in np.linspace(z0 + 0.5, z1 - 0.4, 4):
            p, n = FC.lift_to_skin(ctx, np.array([[0.0, -3.0, zb]]), 0.045, layer=True)
            ctx.add(stud(p[0], n[0], 0.1, bc, 'button'))


def stud(pos, nrm, r, cell, name, h=0.5):
    """Tiny dome (button / rivet) sitting on a surface."""
    seg, rings = 8, 3
    n = np.asarray(nrm, float)
    n = n / np.linalg.norm(n)
    a = np.cross(n, [0, 0, 1.0])
    if np.linalg.norm(a) < 1e-3:
        a = np.cross(n, [1.0, 0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    V = [pos + n * r * h]
    for k in range(1, rings + 1):
        th = k / rings * (math.pi / 2)
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            V.append(pos + (a * math.cos(ph) + b * math.sin(ph)) * r * math.sin(th) + n * r * h * math.cos(th))
    V = np.array(V)
    F = [(0, 1 + j, 1 + (j + 1) % seg) for j in range(seg)]
    for k in range(rings - 1):
        for j in range(seg):
            a0, a1 = 1 + k * seg + j, 1 + k * seg + (j + 1) % seg
            b0, b1 = 1 + (k + 1) * seg + j, 1 + (k + 1) * seg + (j + 1) % seg
            F += [(a0, b0, b1), (a0, b1, a1)]
    p = G.Part(name, V, np.array(F, np.int64), cell, g=np.full(len(V), 0.6))
    v0, v1, v2 = p.V[p.F[:, 0]], p.V[p.F[:, 1]], p.V[p.F[:, 2]]
    if (np.cross(v1 - v0, v2 - v0) @ n).sum() < 0:
        p.F = p.F[:, ::-1].copy()
    p.set_bone('chest')
    return p


def top_bare(ctx, t):
    return None


# ----------------------------------------------------------------------------- long garments (coat, robe, dress skirt)
LEG_TRUNK_TAGS = ('trunk', 'thigh_L', 'shin_L', 'thigh_R', 'shin_R', 'foot_L', 'foot_R')


def envelope_radii(ctx, z, ang, margin=0.0, cx=0.0, cy=0.1):
    """Outermost extent of the trunk + legs (arms excluded: cloth must not wrap round the hands) from (cx, cy) along each
    angle at height z, from the anatomy field."""
    B = ctx.body
    r = np.arange(0.2, 6.5, 0.08)
    A, R = np.meshgrid(ang, r, indexing='ij')
    pts = np.stack([cx + R * np.sin(A), cy - R * np.cos(A), np.full(A.shape, z)], -1).reshape(-1, 3)
    d = np.full(len(pts), 9.0)
    for tag in LEG_TRUNK_TAGS:
        d = np.minimum(d, B.field.tag_dist(pts, tag))
    d = d.reshape(A.shape)
    inside = d < 0.0
    out = np.zeros(len(ang))
    for i in range(len(ang)):
        idx = np.where(inside[i])[0]
        out[i] = r[idx.max()] if len(idx) else 0.0
    return out + margin


def hanging_cloth(ctx, z_top, z_bot, cell, name, thick=0.12, flare=0.35, flare_pow=1.4, sway=0.0, seg=36, n_z=9, g_span=None,
                  min_rx=0.0, min_ry=0.0, open_front=None, top_thick=None, swing=0.5):
    """Skirt / coat tail / robe: a loft of rings that encloses the legs, with the hem flared out by `flare`.

    swing: extra depth (front/back) per row below the hip so the legs can swing without poking through."""
    P, B = ctx.P, ctx.body
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    zs = np.linspace(z_top, z_bot, n_z)
    rows = []
    hipz = P.hip
    for k, z in enumerate(zs):
        frac = k / (n_z - 1)
        r = envelope_hull(ctx, z, seg)
        ex = min_rx + (thick + flare * frac ** flare_pow * P.ls * 2.2)
        drop = max(hipz - z, 0.0)
        ey = thick + flare * frac ** flare_pow * P.ls * 1.6 + swing * drop * 0.5
        x = (r + 0.0) * np.sin(ang)
        y = -(r) * np.cos(ang)
        x = x + np.sign(np.sin(ang)) * np.abs(np.sin(ang)) ** 1.0 * ex
        y = y - np.cos(ang) * np.abs(np.cos(ang)) ** 1.0 * ey
        rows.append(np.stack([x, y + 0.1, np.full(seg, z)], 1))
    V = np.concatenate(rows)
    F = []
    for i in range(n_z - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            c, d = (i + 1) * seg + j, (i + 1) * seg + (j + 1) % seg
            F += [(a, c, d), (a, d, b)]
    F = np.array(F, np.int64)
    g0, g1 = (1.0, 0.0) if g_span is None else g_span
    g = np.repeat(np.linspace(g0, g1, n_z), seg)
    p = G.Part(name, V, F, cell, g=g)
    # outward winding
    cen = np.array([0, 0.1, z_top])
    v0, v1, v2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    fc = (v0 + v1 + v2) / 3 - np.array([0, 0.1, (z_top + z_bot) / 2])
    fc[:, 2] = 0
    if (fn * fc).sum() < 0:
        p.F = p.F[:, ::-1].copy()
    skirt_weights(ctx, p, z_top, z_bot)
    p.hang = True
    return p


def envelope_hull(ctx, z, seg, over=4):
    """Body extent at each of `seg` angles, sampled `over`x finer and max-pooled so lobes between two samples (glutes, thighs) are
    enclosed by the polygon, then convexified across the gap between the legs."""
    fine = np.linspace(0, 2 * math.pi, seg * over, endpoint=False)
    r = envelope_radii(ctx, z, fine)
    pooled = r.copy()
    for s in range(-over, over + 1):
        pooled = np.maximum(pooled, np.roll(r, s))
    out = pooled[::over]
    rs = _circ_smooth(out, 4)
    return np.maximum(out, rs * 0.97)


def _circ_smooth(a, k):
    out = np.zeros_like(a)
    for s in range(-k, k + 1):
        out += np.roll(a, s)
    return out / (2 * k + 1)


def skirt_weights(ctx, part, z_top, z_bot, leg_max=0.6):
    """Hips at the waist, sliding toward the nearer thigh (front / back keep more hips weight) further down."""
    P = ctx.P
    z = part.V[:, 2]
    drop = np.clip((P.hip - z) / max(P.hip - z_bot, 1e-6), 0, 1)
    x = part.V[:, 0]
    side = np.clip(x / (P.hip_x * 1.4), -1, 1)
    wl = np.clip(0.5 + 0.5 * side, 0, 1)
    k = leg_max * drop ** 0.8
    w = {'hips': 1.0 - k, 'thigh_L': k * wl, 'thigh_R': k * (1 - wl)}
    # inside the torso range the cloth rides the trunk
    up = np.clip((z - (P.hip - 0.2)) / 1.4, 0, 1)
    w['spine'] = up * (w['hips'])
    w['hips'] = w['hips'] * (1 - up)
    part.w = {b: np.asarray(v, float) for b, v in w.items()}
    return part


def top_dress(ctx, t):
    """Bodice (shell) + flared skirt (hanging cloth)."""
    P = ctx.P
    tt = dict(t)
    tt['hem_z'] = None
    bodice_hem = P.waist - 0.5 * P.s + (t.get('bodice_lo') or 0.0)
    B = ctx.body
    top_shirt(ctx, dict(tt, hem_z=None, type='shirt'), thick=T_SHIRT)
    # remove the shirt's own hem by building the dress top as a waist-length shell then the skirt takes over
    sk_col = t.get('skirt_color') or t.get('color')
    cell = cloth_cell(ctx, 'skirt', sk_col, 'shirt', hem=t.get('hem'))
    hem_len = t.get('skirt_len', 0.58)                           # fraction of the leg (hip -> ankle) the skirt covers
    z_bot = P.hip - hem_len * (P.hip - P.ankle)
    ctx.add(hanging_cloth(ctx, P.hip + 0.6 * P.s, z_bot, cell, 'skirt', thick=0.16, flare=t.get('flare', 0.55) + 0.2, min_rx=0.0, swing=0.85))
    if t.get('apron'):
        apron(ctx, t['apron'], z_bot)


def apron(ctx, a, z_hem):
    """Front panel worn over a dress: cast onto the dress parts so it follows the bodice and the flared skirt."""
    import char_face as FC
    P, B = ctx.P, ctx.body
    cell = cloth_cell(ctx, 'apron', a.get('color'), 'accent')
    z0 = z_hem + 0.45
    z1 = P.chest + 0.45
    nz, nx = 30, 21
    zs = np.linspace(z0, z1, nz)
    half = np.interp(zs, [z0, P.hip, P.waist, z1], [2.0, 1.9, 1.5, 1.2]) * P.ls
    xs = np.linspace(-1, 1, nx)
    pts = np.zeros((nx, nz, 3))
    for i, xx in enumerate(xs):
        for j, zz in enumerate(zs):
            pts[i, j] = (xx * half[j], -3.0, zz)
    under = [p for p in ctx.parts if p.name in ('top', 'skirt')]
    lifted, nrm = FC.lift_to_parts(ctx, pts.reshape(-1, 3), under, 0.06)
    g = np.tile(np.linspace(0, 1, nz)[None, :], (nx, 1))
    part = FC.grid_part(lifted.reshape(nx, nz, 3), cell, 'apron', g=g, out_from=(0, 3, P.chest))
    skirt_weights(ctx, part, z0, z1)
    ctx.add(part)


def top_coat(ctx, t):
    """Long coat / lab coat: torso shell with a front opening, sleeves, lapels, and hanging tails."""
    P, B = ctx.P, ctx.body
    ccol = t.get('color', 'coat')
    cell = cloth_cell(ctx, 'top', ccol, 'coat')
    under_col = t.get('under_color', 'shirt')
    op = t.get('open', 15)
    hem_len = t.get('coat_len', 0.55)
    z_hem = P.hip - hem_len * (P.hip - P.ankle)
    # under shirt
    ucell = cloth_cell(ctx, 'under', under_col if isinstance(under_col, str) else 'shirt', 'shirt')
    top_shirt(ctx, dict(t, type='shirt', color=under_col, sleeves='none', collar='crew', hem_z=None), thick=T_THIN)
    # coat torso with opening
    of = open_front_cut(ctx, 0.5, 1.5, P.waist - 1.5, P.neck_base)
    neck = neck_hole(ctx, depth=0.0, wide=1.15)
    hem_top = P.hip - 0.6 * P.s
    th = np.full(len(B.V), T_COAT) + fold_noise(B, 0.015, 5, smooth_step(P.chest, P.waist, B.V[:, 2]))
    g = top_g(ctx, hem_top, P.neck_base)
    ctop = torso_cut(ctx, hem_top, neck, open_front=of)
    parts = []
    for sd in (1, -1):
        c = sleeve_cut(ctx, sd, 0.68)
        ctop = np.maximum(ctop, c)
    ctx.add(SH.shell_from_body(ctx, ctop, th, cell, 'coat', g=g))
    # tails below the hip: hanging cloth split at the front opening
    tail = hanging_cloth(ctx, hem_top + 0.6, z_hem, cell, 'coat_tail', thick=T_COAT + 0.02, flare=t.get('flare', 0.25), swing=0.55)
    ctx.add(_open_front_hang(ctx, tail))
    # lapels
    lap = cloth_cell(ctx, 'lapel', t.get('lapel_color') or ccol, 'coat')
    of2 = open_front_cut(ctx, 0.5, 1.5, P.waist - 1.5, P.neck_base)
    band = np.minimum.reduce([of, 0.75 - (np.abs(B.V[:, 0]) - (0.5 + (1.0) * np.clip((B.V[:, 2] - (P.waist - 1.5)) / (P.neck_base - P.waist + 1.5), 0, 1))),
                              B.V[:, 2] - (P.chest - 1.2), (B.V[:, 2] - P.chest) * -1 + 4.0, -B.V[:, 1] + 0.2])
    ctx.add(SH.shell_from_body(ctx, band, np.full(len(B.V), T_COAT + 0.045), lap, 'lapel', g=g, cover=False))
    if t.get('pockets'):
        pockets(ctx, z_hem, T_COAT)
    return


def _open_front_hang(ctx, part):
    """Cut a slit down the centre front of a hanging garment (coat tails)."""
    x, y = part.V[:, 0], part.V[:, 1]
    val = np.maximum(np.abs(x) - 0.55, (y + 0.1) * 3.0)          # keep the sides and the back, slit the front
    V2, F2, at, src = SH.clip_mesh(part.V, part.F, val, {'g': part.g, **{'w_' + b: a for b, a in part.w.items()}})
    p = G.Part(part.name, V2, F2, part.cell, g=at['g'])
    p.w = {k[2:]: v for k, v in at.items() if k.startswith('w_')}
    p.hang = True
    return p


def pockets(ctx, z_hem, thick):
    import char_face as FC
    P = ctx.P
    cell = ctx.ramp('pocket', 'cloth', ctx.shade(ctx.col('coat'), -0.06))
    for sd in (1, -1):
        zc = P.hip - 0.2
        pts = np.array([[sd * (1.6 + dx), -3.0, zc + dz] for dx, dz in ((-0.6, 0.5), (0.6, 0.5), (0.6, -0.5), (-0.6, -0.5))])
        # small rectangular flap as a plate on the coat
        lifted, nrm = FC.lift_to_skin(ctx, np.array([[sd * 1.9 + a, -3.0, zc + b] for a in np.linspace(-0.55, 0.55, 5) for b in np.linspace(-0.45, 0.45, 4)]), 0.045, layer=True)
        part = FC.grid_part(lifted.reshape(5, 4, 3), cell, 'pocket', bone='hips', out_from=(0, 3, zc))
        ctx.add(part)


def top_robe(ctx, t):
    """Floor-length robe with wide sleeves."""
    P, B = ctx.P, ctx.body
    cell = cloth_cell(ctx, 'top', t.get('color'), 'shirt', stripes=t.get('stripes'), hem=t.get('hem'))
    hem_top = P.hip - 0.8 * P.s
    of = open_front_cut(ctx, 0.35, 1.0, P.chest - 2.0, P.neck_base + 0.2) if t.get('open') else None
    neck = neck_hole(ctx, depth=t.get('v', 1.2), wide=1.1)
    th = np.full(len(B.V), T_JACKET)
    ctop = torso_cut(ctx, hem_top, neck, open_front=of)
    for sd in (1, -1):
        ctop = np.maximum(ctop, sleeve_cut(ctx, sd, 0.5))
    ctx.add(SH.shell_from_body(ctx, ctop, th, cell, 'robe', g=top_g(ctx, hem_top, P.neck_base)))
    ctx.add(hanging_cloth(ctx, hem_top + 0.2, P.lift + 0.6, cell, 'robe_skirt', thick=0.14, flare=t.get('flare', 0.5), swing=0.6, g_span=(1.0, 0.0)))
    # wide sleeve cuffs (hanging)
    for sd in (1, -1):
        j = P.joints(sd)
        e = j['wrist']
        cuff = ctx.ramp('sleeve_hem', 'cloth', ctx.col(t.get('cuff_color') or 'accent'))
        band = np.minimum(B.arm[sd] - B.trunk, 0.5 - B.arm_t[sd] + 0.06)
        ctx.add(SH.shell_from_body(ctx, np.minimum(band, B.arm_t[sd] - 0.4), np.full(len(B.V), T_JACKET + 0.05), cuff, 'sleeve_cuff', g=B.arm_t[sd], cover=False))
    if t.get('sash'):
        sash(ctx, t['sash'], P.waist)


def sash(ctx, col, z, h=0.9, thick=0.05, name='sash'):
    B, P = ctx.body, ctx.P
    cell = cloth_cell(ctx, 'sash', col if isinstance(col, str) else 'accent', 'accent')
    z_ = B.V[:, 2]
    c = np.minimum(np.minimum(B.trunk - 0.4, (h / 2) - np.abs(z_ - z)), 1.0)
    th = np.full(len(z_), T_JACKET + thick)
    ctx.add(SH.shell_from_body(ctx, c, th, cell, name, g=np.clip((z_ - (z - h / 2)) / h, 0, 1), cover=False))


TOPS = {'shirt': top_shirt, 'jacket': top_jacket, 'coat': top_coat, 'dress': top_dress, 'robe': top_robe, 'bare': top_bare}


# ----------------------------------------------------------------------------- legs
def build_legs(ctx, l):
    P, B = ctx.P, ctx.body
    typ = l.get('type', 'pants')
    if typ in ('none',):
        return
    cell = cloth_cell(ctx, 'pants', l.get('color'), 'pants', stripes=l.get('stripes'))
    z = B.V[:, 2]
    legw = {sd: B.leg[sd] for sd in (1, -1)}
    hips_w = B.w.get('hips', np.zeros(len(z)))
    waist_top = P.waist - 0.15 * P.s
    if typ in ('pants', 'baggy', 'gi', 'shorts', 'trunks'):
        loose = {'pants': 0.0, 'baggy': 0.09, 'gi': 0.12, 'shorts': 0.03, 'trunks': -0.02}[typ]
        z_end = {'pants': P.lift + 1.15, 'baggy': P.lift + 0.9, 'gi': P.lift + 2.3, 'shorts': P.hip - 3.4 * P.s, 'trunks': P.hip - 1.7 * P.s}[typ]
        z_end = l.get('z_end', z_end)
        th = np.full(len(z), (T_JEANS if typ == 'pants' else T_PANTS) + max(loose, 0.0)) + loose * 0.0
        # legs get looser toward the ankle for baggy / gi
        if typ in ('baggy', 'gi'):
            th = th + 0.05 * smooth_step(P.knee + 1.0, z_end, z)
        th = th + fold_noise(B, 0.01, 11, smooth_step(P.knee + 1.0, P.knee - 1.0, z) + smooth_step(P.hip, P.hip - 1.5, z) * 0.5)
        # the pants are everything below the waistband that belongs to the pelvis or a leg (the fused crotch belongs to neither leg alone)
        lower = legw[1] + legw[-1] + B.trunk
        cut = np.minimum.reduce([lower - 0.5, z - z_end, waist_top - z, z - (P.crotch - 1.4) if typ in ('shorts', 'trunks') else z - z_end])
        cut = np.minimum(cut, 0.6 - np.maximum(B.arm[1], B.arm[-1]))
        g = np.clip((z - z_end) / max(waist_top - z_end, 1e-6), 0, 1)
        ctx.add(SH.shell_from_body(ctx, cut, th, cell, 'pants', g=g))
        if l.get('cuff'):
            cc = cloth_cell(ctx, 'legcuff', l['cuff'], 'accent')
            for sd in (1, -1):
                c = np.minimum(legw[sd] - 0.5, np.minimum(z - z_end, z_end + 0.55 - z))
                ctx.add(SH.shell_from_body(ctx, c, th + 0.03, cc, 'legcuff', g=g, cover=False))
        if typ in ('shorts', 'trunks') and l.get('socks'):
            sc = cloth_cell(ctx, 'sock', l['socks'], 'accent')
            for sd in (1, -1):
                c = np.minimum.reduce([legw[sd] - 0.5, P.knee - 0.6 - z, z - (P.lift + 0.9)])
                ctx.add(SH.shell_from_body(ctx, c, np.full(len(z), 0.07), sc, 'sock', g=g))
        if l.get('waistband', ctx.look.get('top', {}).get('type') in ('bare', None)):
            waistband(ctx, cell, th, waist_top)
    elif typ == 'skirt':
        pass      # the dress builder owns the skirt


def waistband(ctx, cell, th, waist_top):
    B, P = ctx.body, ctx.P
    z = B.V[:, 2]
    c = np.minimum.reduce([B.w.get('hips', 0) + B.w.get('spine', 0) * 0.3 - 0.28, waist_top - z, z - (waist_top - 0.35)])
    ctx.add(SH.shell_from_body(ctx, c, th + 0.02, cell, 'waistband', g=np.full(len(z), 0.9), cover=False))


# ----------------------------------------------------------------------------- shoes and gloves
def build_shoes(ctx, sh):
    P, B = ctx.P, ctx.body
    typ = sh.get('type', 'sneaker')
    if typ == 'barefoot':
        return
    z = B.V[:, 2]
    up = ctx.ramp('shoe', 'flat', ctx.col(sh.get('color'), 'shoes'))
    sole_col = sh.get('sole') or ('#f2f2f2' if typ == 'sneaker' else ctx.shade(ctx.col(sh.get('color'), 'shoes'), -0.45))
    sole = ctx.ramp('sole', 'flat', ctx.col(sole_col))
    top_z = {'sneaker': P.ankle + 0.55, 'flat': P.ankle + 0.25, 'loafer': P.ankle + 0.3, 'heel': P.ankle + 0.35, 'boot': P.ankle + 2.6 * P.s,
             'sandal': P.ankle + 0.1}.get(typ, P.ankle + 0.5)
    for sd in (1, -1):
        fw = B.foot[sd]
        nz = B.Ns[:, 2]
        sole_amt = np.clip((-nz - 0.15) * 1.6, 0, 1)
        th_up = np.full(len(z), T_SHOE if typ != 'boot' else T_SHOE + 0.02)
        thick = th_up + sole_amt * (P.lift + 0.02)
        if typ == 'heel':
            thick = thick + sole_amt * np.clip((B.V[:, 1] - 0.3) * 0.5, 0, 0.6)
        reg = np.maximum(fw - 0.42, np.minimum(B.leg[sd] - 0.5, 0.6) * 0 - 1.0)
        cut = np.minimum(reg, top_z - z)
        if typ == 'boot':
            cut = np.maximum(cut, np.minimum(B.leg[sd] - 0.5, top_z - z))
        # upper
        cut_up = np.minimum(cut, -0.0 + (0.22 - (-nz)) * 1.0 + 0.0)      # not on the sole side
        cut_up = np.minimum(cut, sole_amt * -1.0 + 0.5 * 0 + (nz + 0.15) * 2.0 + 0.0 * 0)
        ctx.add(SH.shell_from_body(ctx, cut, thick, up, 'shoe', g=np.clip((z - P.lift) / max(top_z - P.lift, 1e-6), 0, 1)))
    # sole band: a separate ring of sole colour along the bottom edge
    for sd in (1, -1):
        fw = B.foot[sd]
        nz = B.Ns[:, 2]
        c = np.minimum.reduce([fw - 0.42, (P.lift + 0.55) - z])
        th = np.full(len(z), T_SHOE + 0.03) + np.clip((-nz - 0.15) * 1.6, 0, 1) * (P.lift + 0.02)
        ctx.add(SH.shell_from_body(ctx, c, th, sole, 'sole', g=np.full(len(z), 0.5), cover=False))
    if typ == 'boot' and sh.get('cuff'):
        cc = cloth_cell(ctx, 'bootcuff', sh['cuff'], 'accent')
        for sd in (1, -1):
            c = np.minimum.reduce([B.leg[sd] - 0.5, top_z - z, z - (top_z - 0.5)])
            ctx.add(SH.shell_from_body(ctx, c, np.full(len(z), T_SHOE + 0.07), cc, 'bootcuff', g=np.full(len(z), 0.5), cover=False))


def build_hands(ctx, g):
    if not g:
        return
    B, P = ctx.body, ctx.P
    cell = cloth_cell(ctx, 'glove', g.get('color'), 'accent')
    fingers = g.get('fingerless', False)
    for sd in (1, -1):
        c = np.minimum(B.hand[sd] - 0.45, 1.0)
        th = np.full(len(B.V), T_GLOVE)
        ctx.add(SH.shell_from_body(ctx, c, th, cell, 'glove', g=np.full(len(B.V), 0.5)))
        if g.get('cuff'):
            cc = cloth_cell(ctx, 'glovecuff', g['cuff'], 'accent')
            c2 = np.minimum.reduce([B.arm[sd] - 0.5, B.arm_t[sd] - 0.52, 0.66 - B.arm_t[sd]])
            ctx.add(SH.shell_from_body(ctx, c2, np.full(len(B.V), T_JACKET + 0.02), cc, 'glovecuff', g=B.arm_t[sd], cover=False))

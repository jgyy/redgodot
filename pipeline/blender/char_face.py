"""Face details laid on the sculpted head: painted eyes with rotating eyelids, brows, lips and the mouth line.

Everything is a thin patch or ribbon lifted onto the exact skin (the body field), so it follows the sculpted
socket / brow ridge / lips and never floats.  Blink = the lid cap rotating about the eyeball (bone eye_L / eye_R),
talking = the lips scaling about bone `mouth`.
"""
import math

import numpy as np

import char_anat as AN
import char_eye as EY
import char_geo as G
import char_mesh as M
import char_paint as PT
import char_sdf as S

LIFT = 0.03          # patch height above the skin (rows)
BLINK_DEG = 82.0     # lid rotation from open to closed


# ----------------------------------------------------------------------------- helpers
def grid_part(Pg, cell, name, g=None, uv=None, bone=None, out_from=None):
    """(nu, nv, 3) point grid -> Part (degenerate triangles dropped, wound away from out_from or by majority)."""
    nu, nv = Pg.shape[:2]
    V = Pg.reshape(-1, 3)
    F = G.grid_tris(nu, nv)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    F = F[area > 1e-7]
    if out_from is not None:
        a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
        fn = np.cross(b - a, c - a)
        cen = (a + b + c) / 3 - np.asarray(out_from)
        if (fn * cen).sum() < 0:
            F = F[:, ::-1]
    p = G.Part(name, V, F, cell, g=np.zeros(len(V)) + 0.5 if g is None else np.asarray(g, float).reshape(-1))
    if uv is not None:
        p.uv = np.asarray(uv, float).reshape(-1, 2)
    if bone:
        p.set_bone(bone)
    return p


def lift_to_skin(ctx, pts, off=LIFT, layer=False):
    """Cast each point along +Y onto the body mesh (front of the face), then raise it by `off` along the field normal.
    Ray casting is robust inside grooves (lip line, nostril) where a gradient descent would wander."""
    from mathutils import Vector
    B = ctx.body
    out = np.array(pts, float)
    for i, p in enumerate(out):
        hit = B.tree.ray_cast(Vector((p[0], -8.0, p[2])), Vector((0, 1, 0)), 16.0)
        if hit[0] is not None:
            out[i] = (hit[0].x, hit[0].y, hit[0].z)
    n = S.field_normals(B.field, out)
    if layer:                       # sit on top of whatever garment covers this spot
        off = off + B.layer_at(out)
        off = off[:, None]
    return out + n * off, n


def lift_to_parts(ctx, pts, parts, off=0.03):
    """Like lift_to_skin, but onto the outer surface of some garment parts (skirt, dress, coat): ray along +Y against their triangles."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    V = np.vstack([p.V for p in parts])
    F = np.vstack([p.F + sum(len(q.V) for q in parts[:i]) for i, p in enumerate(parts)])
    tree = BVHTree.FromPolygons([tuple(map(float, v)) for v in V], [tuple(int(i) for i in f) for f in F], epsilon=0.0)
    out = np.array(pts, float)
    nrm = np.zeros_like(out)
    for i, p in enumerate(out):
        hit = tree.ray_cast(Vector((p[0], -8.0, p[2])), Vector((0, 1, 0)), 16.0)
        if hit[0] is not None:
            out[i] = (hit[0].x, hit[0].y, hit[0].z)
            nrm[i] = (hit[1].x, hit[1].y, hit[1].z)
            if nrm[i][1] > 0:
                nrm[i] = -nrm[i]
    return out + nrm * off, nrm


def ribbon(pts, nrm, width, cell, name, bone='head', g=None, sag=0.3):
    """Strip along a polyline on a surface; width is per-point, nrm the surface normals (already lifted points)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    tan = np.gradient(pts, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
    bi = np.cross(nrm, tan)
    bi /= np.maximum(np.linalg.norm(bi, axis=1, keepdims=True), 1e-9)
    w = np.broadcast_to(np.asarray(width, float), (n,))[:, None] * 0.5
    left = pts + bi * w - nrm * (w * sag)
    right = pts - bi * w - nrm * (w * sag)
    top = pts + nrm * 0.0
    V = np.concatenate([left, top, right])
    F = []
    for i in range(n - 1):
        a0, a1 = i, i + 1
        c0, c1 = n + i, n + i + 1
        r0, r1 = 2 * n + i, 2 * n + i + 1
        F += [(a0, c0, c1), (a0, c1, a1), (c0, r0, r1), (c0, r1, c1)]
    gg = np.tile(np.zeros(n) + 0.5 if g is None else g, 3)
    p = G.Part(name, V, np.array(F, np.int64), cell, g=gg)
    # orient by the surface normal
    a, b, c = V[p.F[:, 0]], V[p.F[:, 1]], V[p.F[:, 2]]
    fn = np.cross(b - a, c - a)
    nn = np.concatenate([nrm, nrm, nrm])[p.F[:, 0]]
    if (fn * nn).sum() < 0:
        p.F = p.F[:, ::-1].copy()
    p.set_bone(bone)
    return p


# ----------------------------------------------------------------------------- eyes
PHI = 68.0      # half azimuth of the visible eye on the dome (deg)
E_SCALE = 38.0  # elevation (deg) per unit of the almond y coordinate


def _dome_pts(e, phi_deg, el_deg, k=1.0):
    """Points on the eyeball ellipsoid at azimuth / elevation (degrees)."""
    C, R = e['c'], e['r']
    ph, el = np.radians(phi_deg), np.radians(el_deg)
    x = R[0] * np.cos(el) * np.sin(ph)
    y = -R[1] * np.cos(el) * np.cos(ph)
    z = R[2] * np.sin(el)
    return C + np.stack([x, y, z], -1) * k


def build_eyes(ctx, face):
    P, B = ctx.P, ctx.body
    style = face.get('eyes', 'round')
    eg = AN.eye_geom(P, face)
    skin = ctx.col('skin')
    iris = face.get('iris') or '#3a2a20'
    dark = face.get('eye_color', '#181420')
    hair_c = ctx.col(face.get('lash_color'), 'hair')
    lashy = bool(face.get('lash')) or style in ('lash', 'lash_white')
    scale = face.get('eye_scale', 1.0)
    skin_cell = ctx.skin_cell
    lash_cell = ctx.ramp('lash', 'flat', dark if not lashy else PT.rgb2hex(PT.hex2rgb(dark) * 0.9))
    closed = style == 'closed'
    for sd in (1, -1):
        e = eg[sd]
        nm = 'eye_%s' % ('L' if sd > 0 else 'R')
        if not closed:
            st = style if style in EY.EYE_STYLES else 'round'
            cell = ctx.detail(nm, EY.detail_eye_real(st, sd, iris=iris, skin=skin, lash=lashy, dark=dark), 72, 44)
            t, top, bot = EY.eye_curves(st, 15)
            q = np.linspace(0, 1, 5)
            Y = bot[:, None] + q[None, :] * (top - bot)[:, None]                 # (nt, nq)
            phi = (t[:, None] * 2 - 1) * PHI * scale + 0 * Y
            if sd < 0:
                phi = phi                                                        # +X order is preserved for both eyes
            el = Y * E_SCALE * scale
            pts = _dome_pts(e, phi, el, 1.05)
            flat, n = lift_to_skin(ctx, pts.reshape(-1, 3), LIFT)
            Pg = flat.reshape(pts.shape)
            uv = np.stack([np.broadcast_to(t[:, None], Y.shape), (Y - EY.EYE_YLO) / (EY.EYE_YHI - EY.EYE_YLO)], -1)
            part = grid_part(Pg, cell, nm, uv=uv, bone='head', out_from=e['c'])
            part.ao_gain = 0.0
            ctx.add(part)
            # eyeliner ribbon along the upper lid line
            ei = np.arange(len(t))
            line_pts = Pg[:, -1, :]
            line_n = n.reshape(pts.shape)[:, -1, :]
            w = (0.03 + 0.03 * (1 - np.abs(t - (1.0 if sd > 0 else 0.0)))) * (1.6 if lashy else 1.0)
            ctx.add(ribbon(line_pts + line_n * 0.01, line_n, w, lash_cell, nm + '_liner', bone='head'))
        # lid cap (skin ramp), rests hidden behind the brow; blink rotates it about the eyeball centre
        rest_el = np.linspace(46.0, 118.0, 6)
        rest_ph = np.linspace(-84, 84, 13)
        PH, EL = np.meshgrid(rest_ph, rest_el, indexing='ij')
        cap = _dome_pts(e, PH, EL, 1.11)
        part = grid_part(cap, skin_cell, nm + '_lid', g=np.full(cap.shape[:2], 0.35), bone=None, out_from=e['c'])
        part.ao_gain = 0.0
        part.ao_const = 0.88
        lower = _dome_pts(e, rest_ph, np.full(len(rest_ph), 46.0), 1.11)
        ln = G.nrm(lower - e['c'])
        lash = ribbon(lower + ln * 0.005, ln, 0.05, lash_cell, nm + '_lash', bone=None, sag=0.0)
        if closed:
            # Brock & co: the lids are shut for good -> bake the closed pose into the geometry
            Rm = _rot_about_x(BLINK_DEG)
            for pp in (part, lash):
                pp.V = (pp.V - e['c']) @ Rm.T + e['c']
                pp.set_bone('head')
        else:
            part.set_bone(nm)
            lash.set_bone(nm)
        ctx.add(part)
        ctx.add(lash)


def _rot_about_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


# ----------------------------------------------------------------------------- brows
BROW_W = {'thin': 0.075, 'normal': 0.105, 'thick': 0.15, 'bushy': 0.21}


def build_brows(ctx, face):
    kind = face.get('brows', 'normal')
    if kind == 'none':
        return
    P = ctx.P
    HS = AN.HeadShape(P, face)
    u = HS.u
    child = P.age == 'child'
    wide = HS.wide
    col = ctx.col(face.get('brow_color'), 'hair')
    cell = ctx.ramp('brow', 'hair', col, gloss=0.05)
    tilt = face.get('brow_tilt', 0.0) * 0.02            # + angry (inner end low), - worried
    bz = HS.z('brow') + 0.12 * u
    n = 12
    for sd in (1, -1):
        s = np.linspace(0, 1, n)
        x = sd * (0.16 + 0.78 * s) * u * wide
        z = bz + 0.07 * u * np.sin(np.pi * s * 0.9) + tilt * u * (s - 0.35) * 3.0 - 0.02 * u * (1 - s)
        y = np.array([HS.front_y(xx, zz - P.chin) for xx, zz in zip(x, z)])
        pts = np.stack([x, y, z], 1)
        pts, nrm = lift_to_skin(ctx, pts, 0.035)
        w = BROW_W[kind] * u * (0.55 + 0.45 * np.sin(np.pi * (1 - s) * 0.5 + 0.2)) * (1.0 if kind != 'bushy' else 1.15)
        w = w * (1.0 - 0.55 * s ** 3) * (0.9 if P.f else 1.0)
        ctx.add(ribbon(pts, nrm, w, cell, 'brow_%s' % ('L' if sd > 0 else 'R'), bone='head', sag=0.5))


# ----------------------------------------------------------------------------- lips
def build_lips(ctx, face):
    P = ctx.P
    HS = AN.HeadShape(P, face)
    u = HS.u
    child = P.age == 'child'
    mouth = face.get('mouth', 'smile')
    skin = ctx.col('skin')
    lipc = face.get('mouth_color')
    if lipc is None:
        base = PT.hex2rgb(skin)
        lipc = PT.rgb2hex(np.clip(base * (np.array([0.93, 0.56, 0.58]) if P.f else np.array([0.86, 0.6, 0.58])), 0, 1))
    cell = ctx.ramp('lip', 'flat', lipc, top=1.06, bottom=0.86)
    lc = PT.rgb2hex(PT.hex2rgb(lipc) * np.array([0.45, 0.35, 0.38]))
    line_cell = ctx.ramp('mouthline', 'flat', lc)
    mz = HS.z('mouth')
    lw = (0.44 if P.f else 0.4) * u
    smile = {'smile': 0.075, 'grin': 0.12, 'flat': 0.0, 'frown': -0.07, 'open': 0.04, 'o': 0.0}.get(mouth, 0.06) * u
    gap = {'open': 0.11, 'o': 0.12}.get(mouth, 0.0) * u
    nx, nz = 17, 4
    xs = np.linspace(-1, 1, nx)
    curve = smile * xs ** 2 - smile * 0.15
    hu = (0.115 if P.f else 0.095) * u
    hl = (0.15 if P.f else 0.12) * u
    if mouth == 'o':
        lw *= 0.55
    edge = (1 - np.abs(xs) ** 1.7) ** 0.7
    cupid = 1 - 0.28 * np.exp(-(xs / 0.16) ** 2)
    zm = mz + curve
    ztop = zm + gap * 0.5 + hu * edge * cupid
    zbot = zm - gap * 0.5 - hl * (1 - np.abs(xs) ** 2.2) ** 0.6
    parts = []
    for name, zlo, zhi, g0 in (('lip_up', zm + gap * 0.5, ztop, 0.05), ('lip_lo', zbot, zm - gap * 0.5, 0.95)):
        q = np.linspace(0, 1, nz)
        Z = zlo[:, None] + q[None, :] * (zhi - zlo)[:, None]
        X = np.broadcast_to((xs * lw)[:, None], Z.shape)
        Y0 = np.vectorize(lambda xx, zz: HS.front_y(xx, zz - P.chin))(X, Z)
        pts = np.stack([X, Y0, Z], -1).reshape(-1, 3)
        pts, nrm = lift_to_skin(ctx, pts, 0.03)
        Pg = pts.reshape(Z.shape + (3,))
        gg = (0.35 + 0.65 * np.broadcast_to(q[None, :], Z.shape)) if name == 'lip_up' else (1.0 - 0.6 * np.broadcast_to(q[None, :], Z.shape))
        part = grid_part(Pg, cell, name, g=gg, bone='mouth', out_from=(0, 3, mz))
        part.ao_gain = 0.55
        parts.append(part)
    ctx.add(parts[0])
    ctx.add(parts[1])
    # dark mouth line between the lips
    y0 = np.array([HS.front_y(xx, zz - P.chin) for xx, zz in zip(xs * lw * 0.97, zm)])
    pts = np.stack([xs * lw * 0.97, y0, zm], 1)
    pts, nrm = lift_to_skin(ctx, pts, 0.035)
    ctx.add(ribbon(pts, nrm, 0.03 * u * (0.6 + 0.4 * edge) + gap * 0.6, line_cell, 'mouthline', bone='mouth', sag=0.0))


def build_face(ctx, face):
    build_eyes(ctx, face)
    build_brows(ctx, face)
    build_lips(ctx, face)

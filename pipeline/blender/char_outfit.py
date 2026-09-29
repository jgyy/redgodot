"""Clothing + body accessories driven by character_looks.json."""
import math

import numpy as np

import char_geo as G
import char_paint as PT
import char_body as B


# ----------------------------------------------------------------------------- helpers
def torso_axis_pt(P, z):
    return np.array([0.0, 0.15 if z < P.chest else 0.0, z])


def plate_on_torso(ctx, z0, z1, a_lo, a_hi, dr=0.06, thick=0.22, cell='top', name='plate', n_z=8, n_a=9, e=2.4,
                   g_fn=None, weights='torso', uv_fn=None):
    """Thin plate hugging the torso between heights z0..z1 and angles a_lo(z)..a_hi(z) (radians,
    0 = front, + toward +X).  Callables of z or scalars."""
    P = ctx.P
    zs = np.linspace(z0, z1, n_z)
    lo = np.array([a_lo(z) if callable(a_lo) else a_lo for z in zs])
    hi = np.array([a_hi(z) if callable(a_hi) else a_hi for z in zs])
    pts = np.zeros((n_a, n_z, 3))
    for j, z in enumerate(zs):
        for i in range(n_a):
            a = lo[j] + (hi[j] - lo[j]) * i / (n_a - 1)
            pts[i, j] = B.torso_pt(P, z, a, dr, e)
    g = np.tile(np.linspace(0, 1, n_z)[None, :], (n_a, 1)).reshape(-1) if g_fn is None else g_fn(pts)
    part = G.solid_surface(pts, thick, cell=cell, name=name, g=g, offset=0.5, outward_from=(0, 0.15, (z0 + z1) / 2), inner='rim')
    if weights == 'torso':
        B.torso_weights(ctx, part)
    return part


def band_ring(ctx, z, height, dr, thick, cell, name='band', rx_extra=0.0, seg=24, weights='torso', y_shift=0.0, e=2.4, ry_mult=1.0):
    """Horizontal band (belt, sash, hem) around the torso at height z."""
    P = ctx.P
    rx = P.torso_rx(z) + dr
    ry = (P.torso_ry(z) + dr) * ry_mult
    zc = z
    prof = [(0.0, zc - height / 2 - thick * 0.3)]
    prof = [(rx - thick, zc - height / 2), (rx, zc - height / 2 + thick * 0.3), (rx + thick * 0.3, zc), (rx, zc + height / 2 - thick * 0.3), (rx - thick, zc + height / 2)]
    # build via loft around an elliptical path
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    pts = []
    for a in ang:
        p = B.torso_pt(P, z, a, dr + thick * 0.15, e)
        pts.append(p)
    pts = np.array(pts)
    part = _ring_loft(pts, height, thick, cell, name)
    if weights == 'torso':
        B.torso_weights(ctx, part)
    return part


def _ring_loft(pts, height, thick, cell, name):
    """Closed loop of centre points -> band with rectangular-ish rounded section."""
    n = len(pts)
    c = pts.mean(0)
    rows = []
    for dz, dr_, gg in ((-height / 2, 0.0, 0.0), (-height / 2 + thick * 0.25, thick * 0.55, 0.2), (0, thick * 0.6, 0.5),
                        (height / 2 - thick * 0.25, thick * 0.55, 0.8), (height / 2, 0.0, 1.0)):
        ring = []
        for p in pts:
            rad = np.array([p[0] - c[0], p[1] - c[1], 0.0])
            rad = G.nrm(rad)
            ring.append(p + rad * dr_ + np.array([0, 0, dz]))
        rows.append(np.array(ring))
    inner = []
    for dz in (-height / 2, height / 2):
        ring = []
        for p in pts:
            rad = G.nrm(np.array([p[0] - c[0], p[1] - c[1], 0.0]))
            ring.append(p - rad * thick * 0.7 + np.array([0, 0, dz]))
        inner.append(np.array(ring))
    grid = np.array(rows + [inner[1], inner[0]])          # (m, n, 3)
    grid = np.transpose(grid, (1, 0, 2))                # (n, m, 3)
    g = np.tile(np.array([0, 0.2, 0.5, 0.8, 1.0, 1.0, 0.0])[None, :], (n, 1)).reshape(-1)
    return G.surface_grid(grid, cell, name, g=g, wrap_u=True, wrap_v=True)


def skirt_weights(ctx, part, z_top, z_bot, max_leg=0.6):
    """Hips at the top, blending toward the thigh of the side the vertex is on (skirt / coat tails follow the legs)."""
    P = ctx.P
    z = part.V[:, 2]
    k = G.smoothstep(z_top, z_bot, z) * max_leg
    L = part.V[:, 0] >= 0
    w = {'hips': 1 - k}
    wl = np.where(L, k, 0.0)
    wr = np.where(~L, k, 0.0)
    w['thigh_L'] = wl
    w['thigh_R'] = wr
    # upper part follows the spine chain
    up = G.chain_weights(part.V, [(0, 0, P.hip + 0.3), (0, 0, P.waist), (0, 0, P.chest), (0, 0, P.neck_base), (0, 0, P.neck_top)],
                         ['hips', 'spine', 'chest', 'neck'], [0.9, 0.9, 0.5])
    m = 1 - k
    part.w = {b: up.get(b, 0) * m for b in up}
    part.w['thigh_L'] = wl
    part.w['thigh_R'] = wr
    return part


# ----------------------------------------------------------------------------- tops
def cloth_cell(ctx, name, spec, default='shirt', **kw):
    stripes = kw.pop('stripes', None)
    if stripes:
        stripes = [(a, b, ctx.col(c)) for a, b, c in stripes]
    hem = kw.pop('hem', None)
    return ctx.ramp(name, 'cloth', ctx.col(spec, default), stripes=stripes, hem=ctx.col(hem) if hem else None, **kw)


def sleeve_cell(ctx, t, cell, default='shirt'):
    """Sleeves get their own plain cell when the body cell carries a hem trim / stripes (arm g runs shoulder->wrist)."""
    if t.get('sleeve_color') or t.get('sleeve_stripes'):
        return cloth_cell(ctx, 'sleeve', t.get('sleeve_color') or t.get('color'), default, stripes=t.get('sleeve_stripes'))
    if t.get('hem') or t.get('stripes'):
        return cloth_cell(ctx, 'sleeve', t.get('color'), default)
    return cell


def sleeves(ctx, cell, upto, dr=0.14, cuff=None, name='sleeve', taper=None, cuff_h=0.5):
    for s in (1, -1):
        sl = B.build_arm(ctx, s, cell, dr=dr, upto=upto, name=name, cap_end=0.0, taper=taper)
        ctx.add(sl)
        if upto < 0.999 or cuff:
            # end cuff ring
            path, sarc = B.arm_path(ctx, s)
            k = int(np.searchsorted(sarc, upto))
            k = min(max(k, 2), len(path) - 1)
            cc = cuff or cell
            ring = _arm_ring(ctx, s, upto, dr + 0.06, cuff_h, cc)
            ctx.add(ring)


def _arm_ring(ctx, side, s_frac, dr, h, cell):
    P = ctx.P
    path, sarc = B.arm_path(ctx, side)
    idx = np.searchsorted(sarc, s_frac)
    idx = min(max(idx, 2), len(path) - 2)
    c = path[idx]
    tang = G.nrm(path[min(idx + 2, len(path) - 1)] - path[max(idx - 2, 0)])
    r = float(B.limb_radius(np.array([sarc[idx]]), [(0, 1.32), (0.15, 1.36), (0.55, 1.18), (0.7, 1.1), (1.0, 0.92)])[0]) * P.bulk + dr
    p0 = c - tang * (h / 2)
    p1 = c + tang * (h / 2)
    path2 = np.array([p0, c, p1])
    ring = G.loft(path2, np.array([[r, r], [r + 0.05, r + 0.05], [r, r]]), seg=12, cell=cell, name='cuff', caps=(0.0, 0.0), ref=(0, 1, 0))
    B.arm_weights(ctx, ring, side)
    ring.g[:] = 0.5
    return ring


def top_shirt(ctx, t):
    P = ctx.P
    cell = cloth_cell(ctx, 'top', t.get('color'), stripes=t.get('stripes'), hem=t.get('hem'))
    if t.get('hem_z') is not None and t['hem_z'] > P.hip + 0.3:
        ctx.add(B.build_torso_shell(ctx, 'skin', dr=-0.05))        # midriff
    ctx.add(B.build_torso_shell(ctx, cell, dr=t.get('dr', 0.0), hem_flare=t.get('flare', 0.12), z_bot=t.get('hem_z')))
    sl = t.get('sleeves', 'short')
    scell = sleeve_cell(ctx, t, cell)
    if sl == 'short':
        sleeves(ctx, scell, 0.36, cuff=ctx.ramp('cuff', 'cloth', ctx.col(t.get('cuff', t.get('sleeve_color') or t.get('color')))) if t.get('cuff') else None)
    elif sl == 'long':
        sleeves(ctx, scell, 0.97, cuff=ctx.ramp('cuff', 'cloth', ctx.col(t.get('cuff'))) if t.get('cuff') else None)
    elif sl == 'three':
        sleeves(ctx, scell, 0.62)
    collar(ctx, t)


def collar(ctx, t):
    P = ctx.P
    c = t.get('collar', 'crew')
    if c == 'none':
        return
    col = ctx.ramp('collar', 'cloth', ctx.col(t.get('collar_color'), 'accent'))
    z = P.neck_base + 0.15
    if c == 'crew':
        prof = [(1.5, z - 0.25), (2.05, z - 0.1), (2.15, z + 0.15), (1.85, z + 0.4), (1.5, z + 0.45)]
        p = G.lathe(prof, seg=20, center=(0, 0.1, 0), scale=(P.sw ** 0.5, 0.95), cell=col, name='collar')
        p.g[:] = 0.5
        B.torso_weights(ctx, p)
        ctx.add(p)
    elif c in ('polo', 'lapel', 'shirt'):
        crew = G.lathe([(1.55, z - 0.1), (2.0, z + 0.05), (2.05, z + 0.55), (1.6, z + 0.75)], seg=20, center=(0, 0.1, 0), scale=(1.0, 0.95), cell=col, name='collar', close=True)
        crew.g[:] = 0.5
        B.torso_weights(ctx, crew)
        ctx.add(crew)
        for s in (1, -1):
            pl = plate_on_torso(ctx, z - 2.0, z + 0.2, lambda zz, s=s: s * 0.10, lambda zz, s=s: s * (0.45 - 0.35 * (zz - (z - 2.0)) / 2.2), dr=0.16, thick=0.2, cell=col,
                                name='lapel', n_z=6, n_a=4)
            ctx.add(pl)
    elif c == 'high':
        p = G.lathe([(1.6, z - 0.5), (2.1, z - 0.3), (2.15, z + 0.5), (1.85, z + 1.1), (1.55, z + 1.15)], seg=20, center=(0, 0.1, 0), cell=col, name='collar')
        p.g[:] = 0.5
        B.torso_weights(ctx, p)
        ctx.add(p)
    elif c == 'v':
        skin = 'skin'
        ctx.add(plate_on_torso(ctx, z - 2.4, z + 0.3, lambda zz: -0.5 * (1 - (zz - (z - 2.4)) / 2.7) ** 0.8 - 0.02,
                               lambda zz: 0.5 * (1 - (zz - (z - 2.4)) / 2.7) ** 0.8 + 0.02, dr=0.1, thick=0.16,
                               cell=t.get('v_cell', 'skin'), name='vneck', n_z=6, n_a=7))
        ring = G.lathe([(1.55, z - 0.1), (2.05, z + 0.05), (2.1, z + 0.4), (1.6, z + 0.55)], seg=20, center=(0, 0.1, 0), cell=col, name='collar')
        ring.g[:] = 0.5
        B.torso_weights(ctx, ring)
        ctx.add(ring)


def top_jacket(ctx, t):
    """Jacket: torso shell + hem/cuff trims + zipper line; sleeves colour may differ (Red's white sleeves)."""
    P = ctx.P
    cell = cloth_cell(ctx, 'top', t.get('color'), stripes=t.get('stripes'), hem=t.get('hem'))
    ctx.add(B.build_torso_shell(ctx, cell, dr=0.18, hem_flare=0.2, z_bot=P.hip - 0.55))
    trim = ctx.ramp('trim', 'cloth', ctx.col(t.get('trim'), 'accent'))
    if t.get('hem_band', True):
        ctx.add(band_ring(ctx, P.hip - 0.4, 0.55, 0.2, 0.3, trim, name='hemband'))
    if t.get('zip', True):
        zc = ctx.ramp('zip', 'metal', '#c0c4cc')
        ctx.add(plate_on_torso(ctx, P.hip - 0.3, P.neck_base, -0.03, 0.03, dr=0.32, thick=0.16, cell=zc, name='zip', n_z=8, n_a=2))
    scell = sleeve_cell(ctx, t, cell)
    sl = t.get('sleeves', 'long')
    up = {'short': 0.36, 'long': 0.97, 'three': 0.62}.get(sl, 0.97)
    sleeves(ctx, scell, up, dr=0.2, cuff=trim if t.get('cuff', True) else None)
    collar(ctx, {**t, 'collar_color': t.get('collar_color', t.get('trim'))})
    inner = t.get('under')
    if inner:
        ic = ctx.ramp('under', 'cloth', ctx.col(inner))
        ctx.add(plate_on_torso(ctx, P.neck_base - 2.6, P.neck_base + 0.05, lambda z: -0.35 * (1 - (z - (P.neck_base - 2.6)) / 2.7) ** 0.7 - 0.02,
                               lambda z: 0.35 * (1 - (z - (P.neck_base - 2.6)) / 2.7) ** 0.7 + 0.02, dr=0.3, thick=0.12, cell=ic, name='under', n_z=7, n_a=6))


def top_coat(ctx, t):
    """Long open coat (lab coat / trench): body shell with open front, lapels, pockets, buttons; undershirt visible."""
    P = ctx.P
    coat = cloth_cell(ctx, 'coat', t.get('color'), 'coat', stripes=t.get('stripes'))
    # undershirt torso
    ucell = cloth_cell(ctx, 'top', t.get('under_color'), 'shirt')
    ctx.add(B.build_torso_shell(ctx, ucell, dr=0.0))
    z_top = P.neck_base + 0.25
    z_hem = P.knee + 0.7 + t.get('hem_lift', 0.0)
    nz, na = 12, 22
    a0 = math.radians(t.get('open', 16))
    angs = np.linspace(a0, 2 * math.pi - a0, na)
    zs = np.linspace(z_hem, z_top, nz)
    grid = np.zeros((na, nz, 3))
    dr = 0.42
    for j, z in enumerate(zs):
        zz = max(z, P.hip - 0.6)
        below = max(0.0, (P.hip - 0.6 - z))
        for i, a in enumerate(angs):
            p = B.torso_pt(P, zz, a, dr + below * 0.16, 2.4)
            p[2] = z
            # flare toward the hem, tails swing slightly wider at the back
            grid[i, j] = p
    g = np.tile(np.linspace(0, 1, nz)[None, :], (na, 1)).reshape(-1)
    cshell = G.solid_surface(grid, 0.5, cell=coat, name='coat', g=g, offset=0.5, outward_from=(0, 0.15, (z_hem + z_top) / 2))
    skirt_weights(ctx, cshell, P.hip - 0.4, z_hem, 0.55)
    ctx.add(cshell)
    # lapels (both sides), wider near the collar
    lap = ctx.ramp('lapel', 'cloth', ctx.col(t.get('lapel_color') or t.get('color'), 'coat'), top=1.1, bottom=0.98)
    z_l0 = P.chest - 1.6
    for s in (1, -1):
        pl = plate_on_torso(ctx, z_l0, P.neck_base + 0.2, lambda z, s=s: s * (a0 - 0.02),
                            lambda z, s=s: s * (a0 + 0.10 + 0.5 * ((z - z_l0) / (P.neck_base + 0.2 - z_l0)) ** 1.2),
                            dr=dr + 0.16, thick=0.25, cell=lap, name='lapel', n_z=8, n_a=4)
        ctx.add(pl)
    # collar band round the back of the neck
    zc = P.neck_base + 0.2
    cb = G.lathe([(1.6, zc - 0.2), (2.35, zc - 0.05), (2.5, zc + 0.35), (2.0, zc + 0.85), (1.7, zc + 0.9)], seg=22, center=(0, 0.15, 0), scale=(1, 1), cell=lap, name='coatcollar')
    cb.g[:] = 0.5
    B.torso_weights(ctx, cb)
    ctx.add(cb)
    # pockets
    if t.get('pockets', True):
        pc = ctx.ramp('pocket', 'cloth', ctx.col(t.get('color'), 'coat'), top=0.98, bottom=0.9)
        for s in (1, -1):
            pk = plate_on_torso(ctx, P.hip - 2.2, P.hip - 0.3, lambda z, s=s: s * 0.5, lambda z, s=s: s * 0.95, dr=dr + 0.18, thick=0.16,
                                cell=pc, name='pocket', n_z=4, n_a=5)
            skirt_weights(ctx, pk, P.hip - 0.4, z_hem, 0.55)
            ctx.add(pk)
    if t.get('buttons', True):
        bc = ctx.ramp('button', 'metal', '#d8d4c8')
        for i in range(3):
            z = P.chest - 0.4 - i * 1.5
            pb = G.ellipsoid(B.torso_pt(P, z, math.radians(a0 * 0 + 8) * 0 + a0 * 0 + 0.0, dr + 0.3), (0.28, 0.16, 0.28), seg=8, rings=5, cell=bc, name='button')
            pb.g[:] = 0.5
            B.torso_weights(ctx, pb)
            ctx.add(pb)
    sleeves(ctx, coat, 0.98, dr=0.34, cuff=lap if t.get('cuffs', True) else None, cuff_h=0.55)


def top_dress(ctx, t):
    P = ctx.P
    cell = cloth_cell(ctx, 'top', t.get('color'), stripes=t.get('stripes'), hem=t.get('hem'))
    ctx.add(B.build_torso_shell(ctx, cell, dr=0.0, z_bot=P.hip + 0.2, hem_flare=0.0))
    z_top = P.hip + 1.4
    hem = t.get('length', P.knee - 0.4)
    prof = [(2.85, z_top), (3.15, z_top - 0.6), (3.6, (z_top + hem) / 2 + 0.7), (4.1, hem + 0.5), (4.4, hem)]
    sk = G.lathe(prof, seg=26, center=(0, 0.1, 0), scale=(P.sw * t.get('flare', 1.0), 0.84), cell=cell, name='skirt',
                 wobble=lambda a, z: 1 + 0.04 * np.sin(a * 9) * G.smoothstep(z_top, hem, z))
    sk.g = np.clip((sk.V[:, 2] - hem) / (z_top - hem), 0, 1)
    skirt_weights(ctx, sk, z_top - 0.5, hem, 0.45)
    ctx.add(sk)
    sl = t.get('sleeves', 'short')
    if sl != 'none':
        sleeves(ctx, sleeve_cell(ctx, t, cell),
                {'short': 0.34, 'long': 0.97, 'three': 0.62, 'puff': 0.30}[sl], dr=0.15 if sl != 'puff' else 0.35)
    collar(ctx, t)
    if t.get('sash'):
        sc = ctx.ramp('sash', 'cloth', ctx.col(t['sash']))
        ctx.add(band_ring(ctx, P.hip + 1.2, 0.9, 0.2, 0.3, sc, name='sash'))
    if t.get('apron'):
        apron(ctx, t['apron'] if isinstance(t['apron'], dict) else {}, z_top, hem)


def apron(ctx, a, z_top, hem):
    P = ctx.P
    cell = ctx.ramp('apron', 'cloth', ctx.col(a.get('color'), 'accent'), top=1.05, bottom=0.97)
    pl = plate_on_torso(ctx, z_top - 0.5, P.chest + 0.8, lambda z: -0.85 + 0.35 * (z - (z_top - 0.5)) / 3, lambda z: 0.85 - 0.35 * (z - (z_top - 0.5)) / 3,
                        dr=0.3, thick=0.18, cell=cell, name='bib', n_z=6, n_a=6)
    ctx.add(pl)
    # skirt part of the apron: front panel of a smaller cone
    prof = [(2.5, z_top), (3.2, z_top - 0.6), (3.8, (z_top + hem) / 2 + 0.6), (4.35, hem + 0.7), (4.6, hem + 0.35)]
    ang = np.linspace(-1.05, 1.05, 11)
    zs = np.linspace(hem + 0.5, z_top, 8)
    grid = np.zeros((11, 8, 3))
    for j, z in enumerate(zs):
        r = np.interp(z, [p[1] for p in prof][::-1], [p[0] for p in prof][::-1])
        for i, a_ in enumerate(ang):
            grid[i, j] = (math.sin(a_) * (r + 0.2) * P.sw, -math.cos(a_) * (r + 0.2) * 0.86 + 0.1, z)
    ap = G.solid_surface(grid, 0.2, cell=cell, name='apron', g=np.tile(np.linspace(0, 1, 8)[None, :], (11, 1)).reshape(-1), offset=0.5,
                         outward_from=(0, 0.1, z_top))
    skirt_weights(ctx, ap, z_top - 0.5, hem, 0.45)
    ctx.add(ap)


def top_bare(ctx, t):
    """Bare chest (Bruno, swimmers): skin torso with pecs / abs suggestion."""
    P = ctx.P
    ctx.add(B.build_torso_shell(ctx, 'skin', dr=0.0))
    if t.get('muscle', False):
        for s in (1, -1):
            pc = G.ellipsoid(B.torso_pt(P, P.chest + 0.5, s * 0.42, 0.05), (1.45, 0.75, 1.0), seg=12, rings=7, cell='skin', name='pec',
                             rot=G.rot_y(-s * 8))
            pc.g[:] = 0.75
            B.torso_weights(ctx, pc)
            ctx.add(pc)
            for k in range(3):
                ab = G.ellipsoid(B.torso_pt(P, P.waist + 0.7 - k * 0.85, s * 0.2, 0.0), (0.85, 0.5, 0.42), seg=10, rings=6, cell='skin', name='ab')
                ab.g[:] = 0.7
                B.torso_weights(ctx, ab)
                ctx.add(ab)


def top_robe(ctx, t):
    """Wide-sleeved robe / kimono: torso wrap + long skirt, obi sash, big sleeves."""
    P = ctx.P
    cell = cloth_cell(ctx, 'top', t.get('color'), stripes=t.get('stripes'), hem=t.get('hem'))
    ctx.add(B.build_torso_shell(ctx, cell, dr=0.22, z_bot=P.hip + 0.2, hem_flare=0.0))
    z_top = P.hip + 1.6
    hem = P.ankle + 0.55
    prof = [(2.8, z_top), (3.3, z_top - 0.8), (3.7, (z_top + hem) / 2), (4.0, hem + 0.6), (4.15, hem)]
    sk = G.lathe(prof, seg=26, center=(0, 0.1, 0), scale=(P.sw, 0.82), cell=cell, name='robeskirt',
                 wobble=lambda a, z: 1 + 0.035 * np.sin(a * 7) * G.smoothstep(z_top, hem, z))
    sk.g = np.clip((sk.V[:, 2] - hem) / (z_top - hem), 0, 1)
    skirt_weights(ctx, sk, z_top - 0.5, hem, 0.35)
    ctx.add(sk)
    # wide sleeves: a fat short sleeve plus a drooping sleeve panel
    sleeves(ctx, cell, 0.62, dr=0.42, cuff=None)
    scell = cloth_cell(ctx, 'sleeve2', t.get('sleeve_color') or t.get('color'))
    for s in (1, -1):
        j = P.joints(s)
        pts = [j['elbow'] + np.array([0, 0.0, 0.5]), j['elbow'] + np.array([s * 0.7, -0.2, -1.2]), j['wrist'] + np.array([s * 1.3, -0.3, -1.0])]
        drape = G.loft(np.array(pts), np.array([[1.2, 1.25], [1.6, 1.45], [1.7, 1.2]]), seg=12, cell=scell, name='sleevedrape', caps=(0.5, 0.4), ref=(1, 0, 0))
        drape.g = np.clip(1 - (drape.V[:, 2] - pts[2][2]) / max(pts[0][2] - pts[2][2], 1e-3), 0, 1)
        B.arm_weights(ctx, drape, s)
        ctx.add(drape)
    # collar (crossed front) + sash
    collar(ctx, {**t, 'collar': t.get('collar', 'polo')})
    if t.get('sash'):
        sc = ctx.ramp('sash', 'cloth', ctx.col(t['sash']))
        ctx.add(band_ring(ctx, P.waist - 0.2, 1.6, 0.3, 0.35, sc, name='obi'))
        bow = G.superellipsoid((0, P.torso_ry(P.waist) + 1.6, P.waist - 0.3), (1.9, 0.8, 1.5), 3.0, seg=14, rings=8, cell=sc, name='obibow')
        bow.g[:] = 0.5
        B.torso_weights(ctx, bow)
        ctx.add(bow)


def top_vest_overlay(ctx, t):
    """Sleeveless vest over the shirt (Brock, fisher, safari): torso shell slightly bigger with open front."""
    P = ctx.P
    vc = cloth_cell(ctx, 'vest', t.get('color'), 'accent')
    a0 = math.radians(t.get('open', 24))
    nz, na = 8, 18
    angs = np.linspace(a0, 2 * math.pi - a0, na)
    zs = np.linspace(P.hip - 0.2, P.shoulder + 0.15, nz)
    grid = np.zeros((na, nz, 3))
    for j, z in enumerate(zs):
        for i, a in enumerate(angs):
            grid[i, j] = B.torso_pt(P, z, a, 0.34, 2.4)
    g = np.tile(np.linspace(0, 1, nz)[None, :], (na, 1)).reshape(-1)
    sh = G.solid_surface(grid, 0.32, cell=vc, name='vest', g=g, offset=0.5, outward_from=(0, 0.15, P.chest), inner='rim')
    B.torso_weights(ctx, sh)
    ctx.add(sh)
    if t.get('pockets', True):
        pc = ctx.ramp('vestpocket', 'cloth', ctx.col(t.get('pocket_color'), t.get('color')), top=0.98, bottom=0.9)
        for s in (1, -1):
            for zc in (P.chest + 0.2, P.waist - 0.9):
                pk = plate_on_torso(ctx, zc - 0.55, zc + 0.55, lambda z, s=s: s * 0.4, lambda z, s=s: s * 0.95, dr=0.5, thick=0.18, cell=pc, name='vpocket', n_z=3, n_a=4)
                ctx.add(pk)


TOPS = {'shirt': top_shirt, 'tshirt': top_shirt, 'jacket': top_jacket, 'coat': top_coat, 'dress': top_dress, 'bare': top_bare,
        'robe': top_robe}


def build_top(ctx, t):
    fn = TOPS[t.get('type', 'shirt')]
    fn(ctx, t)
    if t.get('vest'):
        top_vest_overlay(ctx, t['vest'])


# ----------------------------------------------------------------------------- legs / shoes
def build_legs(ctx, l):
    P = ctx.P
    typ = l.get('type', 'pants')
    cell = cloth_cell(ctx, 'pants', l.get('color'), 'pants', stripes=l.get('stripes')) if typ != 'none' else 'skin'
    if typ in ('pants', 'baggy', 'gi'):
        flare = {'pants': 0.0, 'baggy': 0.28, 'gi': 0.35}[typ]
        for s in (1, -1):
            ctx.add(B.build_leg(ctx, s, cell, dr=l.get('dr', 0.0) + (0.12 if typ != 'pants' else 0.0), flare=flare))
            if l.get('cuff'):
                cc = ctx.ramp('legcuff', 'cloth', ctx.col(l['cuff']))
                path = B.leg_path(ctx, s, 9)
                z = P.ankle + 0.75
                x = path[0, 0]
                r = float(np.interp(z, [P.ankle, P.knee, P.hip], [1.2, 1.4, 1.7])) * P.bulk + 0.1 + flare * 0.5
                ring = G.loft(np.array([[x, 0, z - 0.3], [x, 0, z], [x, 0, z + 0.3]]), np.array([[r, r], [r + 0.06, r + 0.06], [r, r]]), seg=12, cell=cc, name='legcuff', caps=(0, 0), ref=(1, 0, 0))
                ring.g[:] = 0.5
                B.leg_weights(ctx, ring, s)
                ctx.add(ring)
        pelvis(ctx, cell, dr=l.get('dr', 0.0) + (0.12 if typ != 'pants' else 0.0))
    elif typ in ('shorts', 'trunks'):
        skin = 'skin'
        z_bot = P.knee + 2.0 if typ == 'shorts' else P.hip - 2.5
        for s in (1, -1):
            ctx.add(B.build_leg(ctx, s, skin, name='leg'))
            sh = B.build_leg(ctx, s, cell, dr=0.1, z_bot=z_bot, name='shorts')
            ctx.add(sh)
            if l.get('socks'):
                sc = ctx.ramp('sock', 'cloth', ctx.col(l['socks']))
                ctx.add(B.build_leg(ctx, s, sc, dr=0.06, z_top=P.knee - 0.5, z_bot=P.ankle + 0.05, name='sock'))
        pelvis(ctx, cell, dr=0.04)
    elif typ in ('skirt', 'robe', 'none'):
        skin = 'skin'
        for s in (1, -1):
            ctx.add(B.build_leg(ctx, s, skin if typ != 'robe' else cell))
        if typ != 'none':
            pelvis(ctx, 'top' if 'top' in ctx.atlas.cells else cell, dr=0.05)
        else:
            pelvis(ctx, 'skin', dr=0.0)


def pelvis(ctx, cell, dr=0.0):
    P = ctx.P
    zs = np.linspace(P.hip - 1.5, P.hip + 1.0, 6)
    path = np.array([[0, 0.12, z] for z in zs])
    rad = np.array([[P.sw * (2.95 - 0.35 * max(0.0, (z - P.hip) / 1.0) ** 2) + dr, 2.35 - 0.16 * max(0.0, (z - P.hip) / 1.0) ** 2 + dr] for z in zs])
    p = G.loft(path, rad, seg=18, cell=cell, name='pelvis', caps=(0.6, 0.2), e=2.4)
    p.g = np.clip((p.V[:, 2] - (P.hip - 1.5)) / 2.5, 0, 1)
    p.w = {'hips': np.ones(len(p.V))}
    ctx.add(p)


def build_shoes(ctx, sh):
    typ = sh.get('type', 'sneaker')
    cell = ctx.ramp('shoe', 'flat', ctx.col(sh.get('color'), 'shoes')) if typ != 'barefoot' else 'skin'
    sole = ctx.ramp('sole', 'flat', ctx.col(sh.get('sole'), '#f2f2f2') if sh.get('sole') else ('#f2f2f2' if typ == 'sneaker' else ctx.shade(ctx.col(sh.get('color'), 'shoes'), -0.4)))
    acc = ctx.ramp('toecap', 'flat', ctx.col(sh['toe'])) if sh.get('toe') else None
    kind = {'sneaker': 'sneaker', 'boot': 'boot', 'flat': 'sneaker', 'loafer': 'sneaker', 'heel': 'heel', 'barefoot': 'barefoot', 'sandal': 'barefoot', 'geta': 'sneaker'}[typ]
    for s in (1, -1):
        for p in B.shoe_parts(ctx, s, kind, cell, sole, acc):
            ctx.add(p)
    if sh.get('laces', typ == 'sneaker'):
        pass
    if typ == 'boot' and sh.get('cuff'):
        cc = ctx.ramp('bootcuff', 'flat', ctx.col(sh['cuff']))
        P = ctx.P
        for s in (1, -1):
            x = P.joints(s)['ankle'][0]
            ring = G.loft(np.array([[x, 0.05, P.ankle + 1.0], [x, 0.05, P.ankle + 1.5], [x, 0.05, P.ankle + 2.0]]), np.array([[1.38, 1.4], [1.45, 1.47], [1.38, 1.4]]) * P.bulk, seg=12, cell=cc, name='bootcuff', caps=(0, 0), ref=(1, 0, 0))
            ring.g[:] = 0.5
            B.leg_weights(ctx, ring, s)
            ctx.add(ring)


def build_hands(ctx, g):
    """Hands: skin unless gloves are specified."""
    P = ctx.P
    if not g:
        cell = 'skin'
        cuff = None
    else:
        cell = ctx.ramp('glove', 'cloth', ctx.col(g.get('color'), 'accent'))
        cuff = g.get('cuff')
    for s in (1, -1):
        ctx.add(B.build_hand(ctx, s, cell))
        if g and cuff:
            cc = ctx.ramp('glovecuff', 'cloth', ctx.col(cuff))
            ring = _arm_ring(ctx, s, 0.93, 0.08, 0.6, cc)
            ctx.add(ring)


def build_arms_skin(ctx):
    for s in (1, -1):
        ctx.add(B.build_arm(ctx, s, 'skin', name='arm'))

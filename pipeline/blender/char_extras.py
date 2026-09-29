"""Accessories: belts, pokeballs, ties, scarves, capes, backpacks, glasses, facial hair, hats."""
import math

import numpy as np

import char_geo as G
import char_paint as PT
import char_body as B
import char_outfit as O
import char_hair as H


# ----------------------------------------------------------------------------- decals
def torso_decal(ctx, cell, z, a, w, h, dr=0.3, name='decal', e=2.4):
    """Flat picture patch on the torso surface (uv = planar)."""
    P = ctx.P
    nu, nv = 9, 9
    pts = np.zeros((nu, nv, 3))
    uv = np.zeros((nu, nv, 2))
    for i in range(nu):
        for j in range(nv):
            u = i / (nu - 1)
            v = j / (nv - 1)
            zz = z + (v - 0.5) * h
            aa = a + (u - 0.5) * w
            pts[i, j] = B.torso_pt(P, zz, aa, dr, e)
            uv[i, j] = (u, v)
    p = G.surface_grid(pts, cell, name, uv=uv, outward_from=(0, 0.15, z))
    p.ao_gain = 0.0
    B.torso_weights(ctx, p)
    return p


def emblem(ctx, e):
    P = ctx.P
    kind = e.get('type', 'R')
    if kind == 'R':
        cell = ctx.detail('emblem', PT.detail_letter_R(ctx.col(e.get('bg'), '#2a2a34'), ctx.col(e.get('color'), '#e04040')), 32, 32)
    elif kind == 'cross':
        cell = ctx.detail('emblem', PT.detail_cross(ctx.col(e.get('bg'), '#f4f4f8'), ctx.col(e.get('color'), '#e03848')), 32, 32)
    elif kind == 'ball':
        cell = ctx.detail('emblem', PT.detail_pokeball(ctx.col(e.get('bg'), '#d8383a')), 32, 32)
    else:
        cell = ctx.detail('emblem', PT.detail_badge(ctx.col(e.get('bg'), '#e8c84a'), ctx.col(e.get('color'), '#b89020')), 32, 32)
    z = P.chest + e.get('dz', -0.2)
    ctx.add(torso_decal(ctx, cell, z, e.get('a', 0.0), e.get('w', 0.75), e.get('h', 3.0), dr=e.get('dr', 0.32), name='emblem'))


# ----------------------------------------------------------------------------- torso accessories
def belt(ctx, b):
    P = ctx.P
    z = P.hip + b.get('dz', 0.95)
    cell = ctx.ramp('belt', 'cloth', ctx.col(b.get('color'), '#3a2a22'))
    dr = b.get('dr', 0.2)
    ctx.add(O.band_ring(ctx, z, b.get('h', 0.62), dr, 0.24, cell, name='belt'))
    bk = ctx.ramp('buckle', 'metal', ctx.col(b.get('buckle'), '#d8b840'))
    p = G.superellipsoid(B.torso_pt(P, z, 0.0, dr + 0.22), (0.62, 0.16, 0.5), 3.2, seg=12, rings=8, cell=bk, name='buckle')
    p.g[:] = 0.5
    B.torso_weights(ctx, p)
    ctx.add(p)
    n = b.get('balls', 0)
    if n:
        ballcell = ctx.ramp('pball', 'ball', '#e04040')
        btn = ctx.ramp('pbtn', 'flat', '#f4f4f8')
        spots = [0.95, -0.95, 1.25][:n]
        for a in spots:
            c = B.torso_pt(P, z - 0.15, a, dr + 0.7)
            ball(ctx, c, 0.78, ballcell, btn, 'hips')


def ball(ctx, c, r, cell, btn, bone):
    sph = G.ellipsoid(c, (r, r, r), seg=14, rings=10, cell=cell, name='ball')
    sph.g = np.clip((sph.V[:, 2] - c[2]) / (2 * r) + 0.5, 0, 1)
    ctx.add(sph, bone)
    b = G.ellipsoid(c + np.array([0, -r * 0.93, r * 0.02]), (r * 0.26, r * 0.13, r * 0.26), seg=10, rings=6, cell=btn, name='ballbtn')
    b.g[:] = 0.5
    ctx.add(b, bone)


def tie(ctx, t):
    P = ctx.P
    cell = ctx.ramp('tie', 'cloth', ctx.col(t.get('color'), 'accent'))
    z0, z1 = P.chest - 0.9 + t.get('dz', 0.0), P.neck_base - 0.05
    ctx.add(O.plate_on_torso(ctx, z0, z1, lambda z: -0.16 - 0.07 * (z - z0) / (z1 - z0) - 0.05 * (1 - (z - z0) / (z1 - z0)) * 0 - 0.0, lambda z: 0.16 + 0.07 * (z - z0) / (z1 - z0),
                             dr=0.3, thick=0.18, cell=cell, name='tie', n_z=6, n_a=4))
    knot = G.ellipsoid(B.torso_pt(P, z1 - 0.15, 0.0, 0.34), (0.46, 0.3, 0.42), seg=10, rings=6, cell=cell, name='tieknot')
    knot.g[:] = 0.5
    B.torso_weights(ctx, knot)
    ctx.add(knot)


def bowtie(ctx, t):
    P = ctx.P
    cell = ctx.ramp('tie', 'cloth', ctx.col(t.get('color'), 'accent'))
    z = P.neck_base - 0.05
    for s in (1, -1):
        w = G.ellipsoid(B.torso_pt(P, z, s * 0.2, 0.4), (0.7, 0.3, 0.5), seg=10, rings=6, cell=cell, name='bow', rot=G.rot_y(-s * 15))
        w.g[:] = 0.5
        B.torso_weights(ctx, w)
        ctx.add(w)


def scarf(ctx, s):
    P = ctx.P
    cell = ctx.ramp('scarf', 'cloth', ctx.col(s.get('color'), 'accent'), stripes=[(a, b, ctx.col(c)) for a, b, c in s.get('stripes', [])] or None)
    z = P.neck_base + 0.4
    prof = [(1.75, z - 0.55), (2.3, z - 0.35), (2.5, z + 0.05), (2.3, z + 0.55), (1.8, z + 0.75), (1.6, z + 0.6)]
    ring = G.lathe(prof, seg=22, center=(0, 0.05, 0), scale=(1.0, 0.95), cell=cell, name='scarf')
    ring.g[:] = 0.5
    B.torso_weights(ctx, ring)
    ring.w = {'neck': np.ones(len(ring.V)) * 0.5, 'chest': np.ones(len(ring.V)) * 0.5}
    ctx.add(ring)
    if s.get('tail', True):
        pts = [np.array([1.2, 2.6, z - 0.4]), np.array([1.6, 3.4, z - 2.0]), np.array([1.8, 3.6, z - 4.0]), np.array([2.0, 3.4, z - 5.6])]
        names = H.add_chain_bones(ctx, 'scarf', [tuple(p) for p in pts], parent='chest')
        tl = G.loft(np.array(G.catmull(np.array(pts), 9)), np.array([[0.9, 0.35]] * 9) * np.linspace(1, 0.85, 9)[:, None], seg=8, cell=cell, name='scarftail', caps=(0.5, 0.3), ref=(1, 0, 0))
        tl.g = np.clip((tl.V[:, 2] - pts[-1][2]) / (pts[0][2] - pts[-1][2]), 0, 1)
        H.weight_chain(tl, pts, names, root_bone='chest', hw=0.8)
        ctx.add(tl)
        ctx.anim_hints['hair_back'] = ctx.anim_hints.get('hair_back', []) + names


def necklace(ctx, n):
    P = ctx.P
    z = P.neck_base - 0.4
    cell = ctx.ramp('chain', 'metal', ctx.col(n.get('color'), '#d8c060'))
    ang = np.linspace(-1.35, 1.35, 12)
    pts = np.array([B.torso_pt(P, z - 1.3 * (math.cos(a * 0.95)) ** 2 * 0 - 0.9 * (1 - math.cos(a * 0.8)) * 0 - 0.7 * math.sin(abs(a) * 0.35) * 0 - 0.9 * (a / 1.35) ** 2 * -1 * 0, a, 0.08) for a in ang])
    # V-shaped chain: higher at the sides, hanging in the middle
    pts = np.array([B.torso_pt(P, z + 0.9 * (abs(a) / 1.35) ** 1.3 - 0.4, a, 0.12) for a in ang])
    ch = G.loft(pts, np.full((len(pts), 2), 0.11), seg=5, cell=cell, name='chain', caps=(0.5, 0.5), ref=(0, 1, 0))
    ch.g[:] = 0.5
    B.torso_weights(ctx, ch)
    ctx.add(ch)
    pc = ctx.detail('pendant', PT.detail_badge(ctx.col(n.get('pendant_bg'), '#f4f4f8'), ctx.col(n.get('pendant'), '#2a2a3a'), star=False), 24, 24)
    ctx.add(torso_decal(ctx, pc, z - 0.35, 0.0, 0.5, 1.0, dr=0.22, name='pendant'))


def backpack(ctx, b):
    P = ctx.P
    cell = ctx.ramp('bag', 'cloth', ctx.col(b.get('color'), 'bag'), top=1.06, bottom=0.9)
    dark = ctx.ramp('bagd', 'cloth', ctx.shade(ctx.col(b.get('color'), 'bag'), -0.22), top=1.04, bottom=0.92)
    sz = b.get('size', 1.0)
    c = np.array([0, P.torso_ry(P.chest) + 1.6 * sz, P.chest - 0.3])
    body = G.superellipsoid(c, (2.9 * sz * P.sw ** 0.5, 1.7 * sz, 3.0 * sz), 3.4, seg=18, rings=12, cell=cell, name='pack')
    body.g = np.clip((body.V[:, 2] - (c[2] - 3.0 * sz)) / (6.0 * sz), 0, 1)
    ctx.add(body, 'chest')
    flap = G.superellipsoid(c + np.array([0, 0.25, 1.9 * sz]), (2.95 * sz * P.sw ** 0.5, 1.7 * sz, 1.2 * sz), 3.4, seg=16, rings=8, cell=dark, name='packflap')
    flap.g[:] = 0.5
    ctx.add(flap, 'chest')
    if b.get('roll'):
        rl = G.loft(np.array([[-3.0, c[1] + 0.3, c[2] - 3.3], [3.0, c[1] + 0.3, c[2] - 3.3]]), [[0.9, 0.9], [0.9, 0.9]], seg=10, cell=ctx.ramp('roll', 'cloth', ctx.col(b['roll'])), name='roll', ref=(0, 1, 0))
        ctx.add(rl, 'chest')
    for s in (1, -1):
        pts = [np.array([s * 2.1, c[1] - 0.3, P.shoulder + 0.4]), np.array([s * 2.7, -1.1, P.shoulder + 0.35]), np.array([s * 3.05, -2.05, P.chest + 0.6]),
               np.array([s * 2.7, -2.6, P.waist + 0.8]), np.array([s * 2.5, 0.2, P.waist - 0.3])]
        pts = [np.array([s * 2.0, c[1] - 0.2, P.shoulder + 0.2]), np.array([s * 2.5, 0.0, P.shoulder + 0.35]), np.array([s * 2.75, -1.6, P.shoulder - 0.3]),
               np.array([s * 2.55, -2.35, P.chest - 0.6]), np.array([s * 2.35, -2.45, P.waist + 0.2])]
        st = G.loft(G.catmull(np.array(pts), 12), np.array([[0.5, 0.15]] * 12), seg=6, cell=dark, name='strap', caps=(0.5, 0.5), ref=(0, 0, 1))
        st.g[:] = 0.5
        ctx.add(st, 'chest')


def cape(ctx, cp):
    P = ctx.P
    outer = ctx.ramp('cape', 'cloth', ctx.col(cp.get('color'), 'accent'), hem=ctx.col(cp.get('hem')) if cp.get('hem') else None, hem_w=0.06)
    z_top = P.neck_base + 0.1
    z_bot = cp.get('bottom', P.knee - 0.5)
    nu, nv = 15, 10
    us = np.linspace(-1, 1, nu)
    vs = np.linspace(0, 1, nv)
    grid = np.zeros((nu, nv, 3))
    for i, u in enumerate(us):
        for j, v in enumerate(vs):
            z = z_top + (z_bot - z_top) * v
            half = 2.9 + 1.7 * v + 2.6 * v * v
            x = u * half
            y = P.torso_ry(min(max(z, P.hip), P.shoulder)) + 0.9 + 0.6 * v + 0.7 * v * v * (1 - u * u) + 1.4 * (1 - abs(u)) ** 2 * 0
            y += 0.45 * (u * u) * (1 - v)
            grid[i, j] = (x, y, z - 0.5 * (u * u) * v * 0.6)
    g = np.tile((1 - vs)[None, :], (nu, 1)).reshape(-1)
    pts = [(0, 3.0, z_top), (0, 3.6, (z_top + z_bot) / 2), (0, 4.6, z_bot)]
    names = H.add_chain_bones(ctx, 'cape', pts, parent='chest')
    sh = G.solid_surface(grid, 0.34, cell=outer, name='cape', g=g, offset=0.5, outward_from=(0, -20, (z_top + z_bot) / 2) if False else (0, 0.0, (z_top + z_bot) / 2))
    H.weight_chain(sh, pts, names, root_bone='chest', hw=1.0)
    ctx.add(sh)
    ctx.anim_hints['hair_back'] = ctx.anim_hints.get('hair_back', []) + names
    # standing collar
    zc = P.neck_base + 0.3
    col = ctx.ramp('capecollar', 'cloth', ctx.col(cp.get('collar') or cp.get('color'), 'accent'))
    cb = G.lathe([(1.7, zc - 0.5), (2.6, zc - 0.2), (2.9, zc + 0.9), (2.5, zc + 1.8), (2.2, zc + 1.85)], seg=22, center=(0, 0.25, 0), scale=(1.0, 0.95), cell=col, name='capecollar')
    cb.g[:] = 0.5
    B.torso_weights(ctx, cb)
    ctx.add(cb)


def suspenders(ctx, s):
    P = ctx.P
    cell = ctx.ramp('suspenders', 'cloth', ctx.col(s.get('color'), 'accent'))
    for sg in (1, -1):
        pl = O.plate_on_torso(ctx, P.hip + 0.4, P.shoulder + 0.35, sg * 0.50, sg * 0.86, dr=0.3, thick=0.16, cell=cell, name='strap', n_z=9, n_a=3)
        ctx.add(pl)
        if s.get('clip', True):
            cc = ctx.ramp('clip', 'metal', '#d8d8dc')
            b = G.ellipsoid(B.torso_pt(P, P.hip + 0.5, sg * 0.68, 0.36), (0.35, 0.16, 0.3), seg=8, rings=5, cell=cc, name='clip')
            b.g[:] = 0.5
            B.torso_weights(ctx, b)
            ctx.add(b)


def wristbands(ctx, w):
    cell = ctx.ramp('wrist', 'cloth', ctx.col(w.get('color'), '#2a2a2a'))
    for s in (1, -1):
        ctx.add(O._arm_ring(ctx, s, 0.93, 0.12, 0.7, cell))
        if w.get('spikes'):
            pass


def pokedex(ctx, d):
    pass


# ----------------------------------------------------------------------------- face accessories
def _ellipse_pts(az, el, haz, hel, n=14):
    a = np.linspace(0, 2 * math.pi, n + 1)
    return [(az + haz * math.cos(t), el + hel * math.sin(t)) for t in a]


def glasses(ctx, g):
    H_ = ctx.head
    kind = g.get('type', 'round')
    frame = ctx.ramp('frame', 'flat', ctx.col(g.get('color'), '#2a2a3a'))
    eaz = ctx.look.get('face', {}).get('eye_az', 19.0)
    eel = ctx.look.get('face', {}).get('eye_el', -5.0)
    if kind == 'shades':
        lens = ctx.ramp('lens', 'flat', ctx.col(g.get('lens'), '#15151c'))
        for s in (1, -1):
            H.__dict__  # noqa
            B.face_patch(ctx, s * eaz, eel + 0.5, 10.5, 9.0, lens, 'lens', n_rad=3, off=0.55, bone='head')
            B.face_tube(ctx, _ellipse_pts(s * eaz, eel + 0.5, 10.8, 9.3, 16), 0.17, frame, 'rim', off=0.5, seg=5)
        B.face_tube(ctx, [(-eaz + 8.5, eel + 3), (0, eel + 3.5), (eaz - 8.5, eel + 3)], 0.16, frame, 'bridge', off=0.5, seg=5)
    else:
        rx, ry = (10.5, 11.5) if kind == 'round' else (11.0, 9.0)
        for s in (1, -1):
            B.face_tube(ctx, _ellipse_pts(s * eaz, eel + 0.5, rx, ry, 18), 0.21, frame, 'rim', off=0.55, seg=6)
        B.face_tube(ctx, [(-eaz + rx, eel + 3), (0, eel + 3.8), (eaz - rx, eel + 3)], 0.17, frame, 'bridge', off=0.5, seg=5)
    for s in (1, -1):
        B.face_tube(ctx, [(s * (eaz + 10.0), eel + 3.5), (s * 55, eel + 3.5), (s * 84, eel + 1.5)], 0.14, frame, 'temple', off=0.45, seg=5)


def moustache(ctx, m):
    col = ctx.ramp('stache', 'hair', ctx.col(m.get('color'), 'beard'))
    kind = m.get('type', 'normal')
    th = {'thin': 0.32, 'normal': 0.55, 'bushy': 0.8, 'handle': 0.42}[kind]
    ln = {'thin': 9, 'normal': 11, 'bushy': 14, 'handle': 16}[kind]
    for s in (1, -1):
        pts = [(s * 0.5, -25.0), (s * ln * 0.45, -26.0), (s * ln * 0.85, -30.0 - (2 if kind == 'handle' else 0)), (s * ln, -33.0 + (5 if kind == 'handle' else 0))]
        p = B.face_tube(ctx, pts, th, col, 'stache', off=th * 0.45, seg=8, taper=[1.0, 1.0, 0.8, 0.3])
        p.g[:] = 0.5
        p.ao_gain = 0.4


def beard(ctx, b):
    H_ = ctx.head
    col = ctx.ramp('beard', 'hair', ctx.col(b.get('color'), 'beard'))
    kind = b.get('type', 'full')
    nu, nv = 25, 8
    if kind == 'full':
        az = np.linspace(-98, 98, nu)
        top = np.interp(np.abs(az), [0, 20, 40, 65, 85, 98], [-40, -38, -28, -12, 8, 14])
        bot = np.interp(np.abs(az), [0, 30, 60, 90, 98], [-84, -80, -66, -30, -8])
        th = 0.75
    elif kind == 'goatee':
        az = np.linspace(-26, 26, nu)
        top = np.interp(np.abs(az), [0, 14, 26], [-41, -44, -52])
        bot = np.interp(np.abs(az), [0, 14, 26], [-74, -70, -62])
        th = 0.7
    elif kind == 'chin':                  # long white chin beard
        az = np.linspace(-34, 34, nu)
        top = np.interp(np.abs(az), [0, 20, 34], [-40, -42, -52])
        bot = np.interp(np.abs(az), [0, 20, 34], [-84, -80, -68])
        th = 0.8
    else:
        return
    v = np.linspace(0, 1, nv)
    EL = top[:, None] + (bot - top)[:, None] * v[None, :]
    AZ = np.repeat(az[:, None], nv, 1)
    pts = H_.surf(AZ, EL, 0.0)
    full = float(b.get('fullness', 1.0))
    # thin at the sideburn / upper edge, fat under the chin, rolled edge at the bottom
    prof = 0.28 + (th * 1.5 * full - 0.28) * G.smoothstep(0.0, 0.55, v)
    prof = prof * (0.45 + 0.55 * G.smoothstep(1.0, 0.82, v))
    edge_fade = 0.55 + 0.45 * np.clip(np.cos(np.radians(AZ) * 90.0 / max(np.abs(az).max(), 1.0)), 0.0, 1.0) ** 0.5
    body = prof[None, :] * edge_fade * (1 + 0.10 * np.sin(AZ * 0.5))
    p = G.solid_surface(pts, 0.0, cell=col, name='beard', g=(1 - v)[None, :].repeat(nu, 0).reshape(-1) * 0.8 + 0.1, thick_fn=lambda _P: body,
                        offset=0.4, outward_from=H_.c, inner='rim')
    p.ao_gain = 0.4
    ctx.add(p, 'head')
    if kind == 'chin' or b.get('tuft'):
        c0 = H_.surf(0, -82, 0.4)
        pts2 = [c0, c0 + np.array([0, -0.5, -1.4]), c0 + np.array([0, -0.6, -2.8]), c0 + np.array([0, -0.4, -3.9])]
        tl = G.loft(np.array(G.catmull(np.array(pts2), 8)), np.array([[1.2, 0.9], [1.3, 0.95], [0.95, 0.8], [0.15, 0.15]])[np.linspace(0, 3, 8).round().astype(int)], seg=8, cell=col, name='beardtuft', caps=(0.5, 0.3), ref=(1, 0, 0))
        tl.g[:] = 0.3
        ctx.add(tl, 'head')


# ----------------------------------------------------------------------------- hats
CAP_RIM = [(0, 71), (40, 73), (80, 79), (110, 85), (180, 88)]
BEANIE_RIM = [(0, 66), (40, 68), (80, 84), (110, 100), (180, 108)]


def hat_cap(ctx, h):
    P = ctx.P
    H_ = ctx.head
    body = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), 'hat'), top=1.06, bottom=0.94)
    pan = ctx.ramp('hatk', 'cloth', ctx.col(h.get('panel'), 'hatk'), top=1.06, bottom=0.94)
    brimc = ctx.ramp('brim', 'cloth', ctx.col(h.get('brim') or h.get('color'), 'hat'), top=1.05, bottom=0.9)
    thick = 0.85
    rim = h.get('rim') or CAP_RIM
    sh = H.shell(ctx, 'cap', rim, thick=thick, volume=0.5, cell=body, ridges=0, ridge_amp=0.0, lip=thick * 0.9, offset=0.6)
    ctx.add(sh, 'head')
    # front panel
    if pan != body or h.get('panel_seam', True):
        fp = H.shell(ctx, 'panel', lambda az: np.interp(np.abs(az), [0, 45], [rim[0][1] - 0.4, rim[1][1] - 0.4]), az_range=(-46, 46), nu=16, nv=10, thick=thick + 0.12,
                     volume=0.55, cell=pan, ridges=0, ridge_amp=0.0, wrap=False, lip=thick * 0.9, offset=0.6)
        ctx.add(fp, 'head')
    # crown button
    bt = G.ellipsoid(H_.surf(0, 89, thick + 0.75), (0.55, 0.55, 0.42), seg=10, rings=6, cell=pan if pan != body else body, name='hatbutton')
    bt.g[:] = 0.5
    ctx.add(bt, 'head')
    # seams (thin ridges at the panel borders)
    # brim
    length = h.get('brim_len', 3.6)
    width = 58
    nu, nv = 17, 8
    azs = np.linspace(-width, width, nu)
    sv = np.linspace(0, 1, nv)
    grid = np.zeros((nu, nv, 3))
    for i, a in enumerate(azs):
        el0 = 90 - np.interp(abs(a), [c[0] for c in rim], [c[1] for c in rim]) + 2
        base = H_.surf(a, el0, thick + 0.15)
        dirn = G.nrm(np.array([math.sin(math.radians(a)) * 0.75, -math.cos(math.radians(a)), 0.0]))
        ext = length * (0.55 + 0.45 * math.cos(math.radians(a) * 90 / width)) if False else length * (math.cos(math.radians(a) * 1.35)) ** 0.6
        for j, s in enumerate(sv):
            drop = h.get('curve', 0.75) * (a / width) ** 2 * s * 1.2 + 0.25 * s * s
            grid[i, j] = base + dirn * ext * s + np.array([0, 0, -drop + 0.5 * s * (1 - s)])
    bg = np.tile(sv[None, :], (nu, 1)).reshape(-1)
    br = G.solid_surface(grid, 0.34, cell=brimc, name='brim', g=bg, offset=0.5, outward_from=(0, 0, P.head_c[2] - 10))
    ctx.add(br, 'head')
    logo = h.get('logo')
    if logo:
        if logo == 'ball':
            lc = ctx.detail('hatlogo', PT.detail_pokeball(ctx.col(h.get('panel'), 'hatk'), ctx.col(h.get('logo_top'), '#e04040')), 32, 32)
        elif logo == 'R':
            lc = ctx.detail('hatlogo', PT.detail_letter_R(ctx.col(h.get('color'), 'hat'), ctx.col(h.get('logo_color'), '#e04040')), 32, 32)
        elif logo == 'badge':
            lc = ctx.detail('hatlogo', PT.detail_badge(ctx.col(h.get('logo_color'), '#e8c84a'), ctx.col(h.get('logo_edge'), '#a88018')), 32, 32)
        else:
            lc = ctx.detail('hatlogo', PT.detail_cross(ctx.col(h.get('color'), 'hat'), '#f4f4f8'), 32, 32)
        p = B.face_patch(ctx, 0, 28, 17, 17, lc, 'hatlogo', n_rad=4, off=0.05, base=thick + 0.32, bone='head')


def hat_beanie(ctx, h):
    """Knit cap / swim cap: snug shell, ribbed cuff, optional pompom."""
    H_ = ctx.head
    body = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), 'hat'), top=1.06, bottom=0.94, stripes=[(a, b, ctx.col(c)) for a, b, c in h.get('stripes', [])] or None)
    rim = h.get('rim') or BEANIE_RIM
    thick = h.get('thick', 0.9)
    sh = H.shell(ctx, 'beanie', rim, thick=thick, volume=h.get('volume', 0.45), cell=body, ridges=h.get('ridges', 0), ridge_amp=0.06 if h.get('ridges') else 0.0,
                 lip=thick * 0.9, offset=0.6)
    ctx.add(sh, 'head')
    if h.get('cuff', True):
        cuff = ctx.ramp('hatcuff', 'cloth', ctx.col(h.get('cuff_color') or h.get('color'), 'hat'), top=1.08, bottom=0.92)
        az = np.linspace(-180, 180, 40, endpoint=False)
        edge = np.interp(np.abs(az), [c[0] for c in rim], [c[1] for c in rim])
        nv = 4
        v = np.linspace(-0.09, 0.02, nv)
        TH = edge[:, None] + v[None, :] * 100.0 * 0 + np.array([-9, -4, 1, 5])[None, :]
        AZ = az[:, None].repeat(nv, 1)
        P_ = H_.pt(H.dirs_from(AZ, TH))
        cf = G.solid_surface(P_, 0.0, cell=cuff, name='hatcuff', wrap_u=True, g=np.tile(np.linspace(0, 1, nv)[None, :], (40, 1)).reshape(-1),
                             thick_fn=lambda _P: 1.25 + 0 * _P[..., 0], offset=0.5, outward_from=H_.c, inner='rim')
        ctx.add(cf, 'head')
    if h.get('tails'):
        _band_tails(ctx, body, h.get('tail_el', 24))
    if h.get('pompom'):
        pc = ctx.ramp('pompom', 'cloth', ctx.col(h['pompom']))
        pp = G.ellipsoid(H_.surf(0, 88, thick + 1.6), (1.4, 1.4, 1.3), seg=12, rings=8, cell=pc, name='pompom')
        pp.g[:] = 0.5
        ctx.add(pp, 'head')


def _dome(ctx, name, cell, z0, r_base, r_top, h_crown, seg=28, scale=(1.0, 0.96), wob=0.0, flat_top=0.0, bulge=0.0):
    prof = [(0.0, z0 + h_crown)]
    n = 10
    for k in range(1, n + 1):
        a = k / n * math.pi / 2
        r = r_top * math.sin(a) + 0.0
        z = z0 + h_crown * math.cos(a) * (1 - flat_top)
        prof.append((r, z))
    prof.append((r_base, z0 + 0.0))
    prof = prof[::-1]
    p = G.lathe(prof, seg=seg, center=(0, 0.25, 0), scale=scale, cell=cell, name=name)
    return p


def hat_wide(ctx, h):
    """Straw / ranger / bucket hat: dome crown that clears the hair, hat band, wide (drooping) brim."""
    P = ctx.P
    hc = P.head_c[2]
    cell = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), 'hat'), top=1.06, bottom=0.94)
    band = ctx.ramp('hatband', 'cloth', ctx.col(h.get('band'), '#8a3a2a'))
    z0 = hc + h.get('z', 1.5)
    rb = h.get('brim_r', 9.2)
    rc = h.get('crown_r', 6.9)
    crown = h.get('crown', 4.8)
    droop = h.get('droop', 0.5)
    dome = [(rc * math.sin(t) ** 0.85, z0 + 0.5 + (crown - 0.5) * math.cos(t) ** 0.8) for t in np.linspace(0, math.pi / 2, 8)]
    prof = dome + [(rc, z0), (rc + 0.8, z0 - 0.05), (rb - 1.4, z0 - 0.1 - droop * 0.3), (rb, z0 - 0.25 - droop), (rb - 0.25, z0 - 0.6 - droop),
                   (rb - 1.4, z0 - 0.45 - droop * 0.3), (rc + 0.5, z0 - 0.4), (rc - 0.4, z0 - 0.4), (0.0, z0 - 0.4)]
    hat = G.lathe(prof[::-1], seg=30, center=(0, 0.25, 0), scale=(1.0, 0.95), cell=cell, name='hat',
                  wobble=lambda a, z: 1 + h.get('wobble', 0.0) * np.sin(a * 6) * G.smoothstep(z0 - 0.2, z0 - 1.2, z))
    hat.g = np.clip((hat.V[:, 2] - (z0 - 1.5)) / 6.0, 0, 1)
    ctx.add(hat, 'head')
    bd = G.lathe([(rc - 0.1, z0 + 0.1), (rc + 0.3, z0 + 0.25), (rc + 0.32, z0 + 1.15), (rc + 0.1, z0 + 1.5), (rc - 0.25, z0 + 1.5)], seg=30, center=(0, 0.25, 0), scale=(1.0, 0.95),
                 cell=band, name='hatband')
    bd.g[:] = 0.5
    ctx.add(bd, 'head')


def hat_sailor(ctx, h):
    """Sailor cap / captain's cap: flat round white top, band, optional peak and badge."""
    P = ctx.P
    hc = P.head_c[2]
    cell = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), 'hat'), top=1.06, bottom=0.94)
    band = ctx.ramp('hatband', 'cloth', ctx.col(h.get('band'), '#2a2a3a'))
    z0 = hc + 1.9
    rc = 6.95
    top = h.get('top_r', 7.6)
    H_ = h.get('height', 4.7)
    prof = [(0.0, z0 + H_), (top * 0.6, z0 + H_), (top, z0 + H_ - 0.35), (top + 0.1, z0 + H_ - 1.0), (rc + 0.15, z0 + H_ - 2.2), (rc, z0 + 1.0), (rc, z0 - 0.3),
            (rc - 0.5, z0 - 0.35), (0.0, z0 - 0.35)]
    hat = G.lathe(prof[::-1], seg=30, center=(0, 0.25, 0), scale=(1.0, 0.95), cell=cell, name='hat')
    hat.g = np.clip((hat.V[:, 2] - (z0 - 0.3)) / (H_ + 0.3), 0, 1)
    ctx.add(hat, 'head')
    bd = G.lathe([(rc - 0.1, z0 - 0.35), (rc + 0.35, z0 - 0.3), (rc + 0.4, z0 + 0.95), (rc + 0.2, z0 + 1.05), (rc - 0.2, z0 + 1.05)], seg=30, center=(0, 0.25, 0), scale=(1.0, 0.95), cell=band, name='hatband')
    bd.g[:] = 0.5
    ctx.add(bd, 'head')
    if h.get('peak'):
        pk = ctx.ramp('peak', 'cloth', ctx.col(h.get('peak_color'), '#1a1a22'), top=1.1, bottom=0.9)
        nu, nv = 13, 6
        azs = np.linspace(-62, 62, nu)
        sv = np.linspace(0, 1, nv)
        grid = np.zeros((nu, nv, 3))
        for i, a in enumerate(azs):
            base = np.array([math.sin(math.radians(a)) * rc * 0.98, 0.25 - math.cos(math.radians(a)) * rc * 0.93, z0 + 0.2])
            dirn = G.nrm(np.array([math.sin(math.radians(a)) * 0.6, -math.cos(math.radians(a)), 0.0]))
            ext = 3.0 * math.cos(math.radians(a) * 1.3) ** 0.6
            for j, s in enumerate(sv):
                grid[i, j] = base + dirn * ext * s + np.array([0, 0, -0.4 * s - 0.4 * (a / 62) ** 2 * s])
        ctx.add(G.solid_surface(grid, 0.3, cell=pk, name='peak', g=np.tile(sv[None, :], (nu, 1)).reshape(-1), offset=0.5, outward_from=(0, 0, z0 - 8)), 'head')
    if h.get('badge'):
        bc = ctx.detail('hatbadge', PT.detail_badge(ctx.col(h.get('badge_color'), '#e8c84a'), ctx.col(h.get('badge_edge'), '#a88018')), 24, 24)
        nu, nv = 9, 9
        pts = np.zeros((nu, nv, 3))
        uv = np.zeros((nu, nv, 2))
        for i in range(nu):
            for j in range(nv):
                u, v = i / (nu - 1), j / (nv - 1)
                a = math.radians((u - 0.5) * 34)
                pts[i, j] = np.array([math.sin(a) * (rc + 0.5), 0.25 - math.cos(a) * (rc + 0.5) * 0.95, z0 + 0.1 + v * 1.3])
                uv[i, j] = (u, v)
        b = G.surface_grid(pts, bc, 'badge', uv=uv, outward_from=(0, 0.25, z0))
        b.ao_gain = 0
        ctx.add(b, 'head')


def hat_chef(ctx, h):
    P = ctx.P
    hc = P.head_c[2]
    cell = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), '#f4f4f8'), top=1.06, bottom=0.92)
    z0 = hc + 2.6
    rc = 6.9
    prof = [(0.0, z0 + 7.6), (3.0, z0 + 7.5), (5.6, z0 + 6.6), (7.0, z0 + 5.0), (7.6, z0 + 3.6), (7.4, z0 + 2.3), (6.6, z0 + 1.5), (rc, z0 + 0.9), (rc, z0 - 0.3), (rc - 0.5, z0 - 0.35), (0.0, z0 - 0.35)]
    hat = G.lathe(prof[::-1], seg=32, center=(0, 0.3, 0), scale=(1.0, 0.98), cell=cell, name='chefhat',
                  wobble=lambda a, z: 1 + 0.05 * np.sin(a * 7 + z * 0.8) * G.smoothstep(z0 + 1.0, z0 + 4.0, z))
    hat.g = np.clip((hat.V[:, 2] - z0) / 8.0, 0, 1)
    ctx.add(hat, 'head')


def hat_nurse(ctx, h):
    P = ctx.P
    H_ = ctx.head
    cell = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), '#f4f4f8'), top=1.06, bottom=0.94)
    c = H_.surf(0, 58, 0.5)
    cap = G.superellipsoid(c + np.array([0, -0.6, 0.4]), (3.5, 2.5, 1.0), 3.0, seg=18, rings=10, cell=cell, name='nursecap', rot=G.rot_x(-18))
    cap.g = np.clip((cap.V[:, 2] - (c[2] - 1)) / 2.5, 0, 1)
    ctx.add(cap, 'head')
    cc = ctx.detail('nursecross', PT.detail_cross('#f4f4f8', ctx.col(h.get('cross'), '#e03848')), 24, 24)
    nu = nv = 7
    pts = np.zeros((nu, nv, 3))
    uv = np.zeros((nu, nv, 2))
    R_ = G.rot_x(-18)
    for i in range(nu):
        for j in range(nv):
            u, v = i / (nu - 1), j / (nv - 1)
            p = np.array([(u - 0.5) * 2.4, -2.5 * 0.86 - 0.35, 1.0 * 0.4 + (v - 0.5) * 1.5])
            pts[i, j] = p @ R_.T + c + np.array([0, -0.6, 0.4]) + np.array([0, -0.08, 0.0])
            uv[i, j] = (u, v)
    x = G.surface_grid(pts, cc, 'cross', uv=uv, outward_from=c)
    x.ao_gain = 0
    ctx.add(x, 'head')


def _band_tails(ctx, cell, el):
    H_ = ctx.head
    b0 = H_.surf(180, el, 1.0)
    for s in (1, -1):
        pts2 = [b0, b0 + np.array([s * 0.8, 1.2, -0.6]), b0 + np.array([s * 1.6, 2.4, -3.0]), b0 + np.array([s * 2.0, 2.6, -5.6])]
        nm = 'band_%s' % ('L' if s > 0 else 'R')
        names = H.add_chain_bones(ctx, nm, [tuple(p) for p in [pts2[0], pts2[2], pts2[3]]])
        tl = G.loft(G.catmull(np.array(pts2), 9), np.array([[0.85, 0.2], [0.95, 0.2], [0.9, 0.18], [0.85, 0.16], [0.8, 0.16], [0.75, 0.15], [0.7, 0.15], [0.6, 0.14], [0.5, 0.12]]),
                    seg=6, cell=cell, name='bandtail', caps=(0.5, 0.2), ref=(1, 0, 0))
        tl.g = np.clip(1 - (tl.V[:, 2] - pts2[-1][2]) / max(pts2[0][2] - pts2[-1][2], 1e-3), 0, 1) * 0.5 + 0.3
        H.weight_chain(tl, [pts2[0], pts2[2], pts2[3]], names, hw=0.9)
        ctx.add(tl)
        ctx.anim_hints['hair_tail'] = ctx.anim_hints.get('hair_tail', []) + names


def hat_headband(ctx, h):
    """Headband around the forehead with knot + trailing tails (ninja / bandana)."""
    P = ctx.P
    H_ = ctx.head
    cell = ctx.ramp('hat', 'cloth', ctx.col(h.get('color'), 'hat'), top=1.06, bottom=0.94)
    el = h.get('el', 20)
    az = np.linspace(-180, 180, 44, endpoint=False)
    hgt = h.get('h', 12)
    ELS = np.array([el - hgt / 2, el - hgt / 4, el + hgt / 4, el + hgt / 2])
    AZ = az[:, None].repeat(4, 1)
    EL = np.tile(ELS[None, :], (44, 1))
    pts = H_.surf(AZ, EL, 0.0)
    th = np.array([0.5, 1.15, 1.15, 0.5])[None, :].repeat(44, 0) + 0.3
    band = G.solid_surface(pts, 0.0, cell=cell, name='headband', wrap_u=True, g=np.tile(np.linspace(0, 1, 4)[None, :], (44, 1)).reshape(-1),
                           thick_fn=lambda _P: th, offset=0.45, outward_from=H_.c, inner='rim')
    ctx.add(band, 'head')
    if h.get('tails', True):
        _band_tails(ctx, cell, el)
    if h.get('plate'):
        pc = ctx.ramp('plate', 'metal', '#c8ccd8')
        pl = G.superellipsoid(H_.surf(0, el, 1.4), (2.2, 0.3, 1.5), 3.0, seg=14, rings=8, cell=pc, name='plate')
        pl.g[:] = 0.5
        ctx.add(pl, 'head')


HATS = {'cap': hat_cap, 'beanie': hat_beanie, 'wide': hat_wide, 'sailor': hat_sailor, 'chef': hat_chef, 'nurse': hat_nurse, 'headband': hat_headband}


def build_hat(ctx, h):
    HATS[h.get('type', 'cap')](ctx, h)

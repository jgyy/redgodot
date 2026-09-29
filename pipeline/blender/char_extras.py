"""Hats, facial hair, glasses and body accessories (belts, ties, scarves, packs, capes ...)."""
import math

import numpy as np

import char_anat as AN
import char_face as FC
import char_geo as G
import char_hair as H
import char_outfit as O
import char_paint as PT
import char_shell as SH


# ----------------------------------------------------------------------------- head rings
class Rings:
    """Head cross-sections (ellipse round the skull at any height) for building hats that hug it."""

    def __init__(self, ctx, face=None):
        self.ctx = ctx
        self.P = ctx.P
        self.HS = AN.HeadShape(ctx.P, face or ctx.look.get('face', {}))
        self.u = self.HS.u

    def ellipse(self, z, gap=0.0):
        """(cx, cy, rx, ry) of the head at world height z, or None above the skull."""
        HS = self.HS
        r = HS.rows
        zr = z - self.P.chin
        if zr >= r[-1, 0] - 1e-3:
            return None
        hw = float(np.interp(zr, r[:, 0], r[:, 1])) * self.u
        fy = float(np.interp(zr, r[:, 0], r[:, 2])) * self.u
        by = float(np.interp(zr, r[:, 0], r[:, 3])) * self.u
        return 0.0, (fy + by) / 2, hw + gap, (by - fy) / 2 + gap

    def rim_z(self, az, kind):
        u, chin = self.u, self.P.chin
        a = np.abs(np.asarray(az, float))
        tab = {'cap': [2.05, 1.95, 1.82, 1.62, 1.5], 'beanie': [1.88, 1.82, 1.25, 1.0, 0.95], 'band': [1.9, 1.85, 1.82, 1.8, 1.8]}[kind]
        return chin + np.interp(a, [0, 60, 95, 150, 180], tab) * u


def ring_points(cx, cy, rx, ry, z, seg, expo=2.0):
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    s, c = np.sin(ang), np.cos(ang)
    x = cx + rx * np.sign(s) * np.abs(s) ** (2 / expo)
    y = cy - ry * np.sign(c) * np.abs(c) ** (2 / expo)
    return np.stack([x, y, np.full(seg, z)], 1)


def hat_solid(ctx, RG, z0, z1, gap0, gap1, n_z, thick, cell, name, seg=32, rim_fn=None, g=None, bulge=0.0, top_close=True, tilt=0.0):
    """Hat body: rings stacked from z0 to z1 that follow the head plus a gap profile (gap0 -> gap1); rim_fn(az) lowers the front / back edge."""
    zs = np.linspace(z0, z1, n_z)
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    az_deg = np.degrees(ang)
    az_deg = np.where(az_deg > 180, az_deg - 360, az_deg)
    rows = []
    top = RG.P.head_top
    for k, z in enumerate(zs):
        f = k / (n_z - 1)
        gap = gap0 + (gap1 - gap0) * f + bulge * math.sin(math.pi * f)
        el = RG.ellipse(min(z, top - 0.02), gap)
        if el is None:
            el = (0, 0.2, 0.1, 0.1)
        cx, cy, rx, ry = el
        if z > top - 0.05:
            # above the skull: dome closing
            q = (z - (top - 0.05)) / max(z1 - (top - 0.05), 1e-3)
            rx *= max(1 - q * q, 0.02)
            ry *= max(1 - q * q, 0.02)
        pts = ring_points(cx, cy, rx, ry, z, seg)
        if rim_fn is not None:
            low = rim_fn(az_deg) - z0
            pts[:, 2] = pts[:, 2] - np.clip(low * (1 - f) ** 2, -5, 5)
        rows.append(pts)
    Pg = np.array(rows)                                 # (n_z, seg, 3) -> want (seg, n_z)
    Pg = np.transpose(Pg, (1, 0, 2))
    gg = np.tile(np.linspace(0, 1, n_z)[None, :], (seg, 1)) if g is None else g
    p = G.solid_surface(Pg, thick, cell=cell, name=name, wrap_u=True, g=gg, offset=0.5, outward_from=(0, 0.2, z0 - 3), inner='rim')
    return p


# ----------------------------------------------------------------------------- hats
def build_hat(ctx, h):
    fn = HATS[h['type']]
    RG = Rings(ctx)
    ctx.rings = RG
    fn(ctx, RG, h)


def hat_cell(ctx, h, key='color', default='hat', name='hat'):
    return O.cloth_cell(ctx, name, h.get(key), default)


def hat_cap(ctx, RG, h):
    """Baseball-style cap: skull-hugging crown (front panel in its own colour), stitched seams, button, visor."""
    u = RG.u
    P = ctx.P
    cell = hat_cell(ctx, h)
    pcell = O.cloth_cell(ctx, 'hatpanel', h.get('panel'), 'hatk') if h.get('panel') else cell
    z_lo = RG.rim_z(0, 'cap') - 0.05
    ctx.hat_rim = lambda az: RG.rim_z(az, 'cap') + 0.05
    thick = 0.16
    # crown as shell of the head so it follows every bump: cut = above rim(az)
    B = ctx.body
    rel = B.V - ctx.headref.hc if hasattr(ctx, 'headref') else B.V - H.HeadRef(ctx).hc
    az = np.degrees(np.arctan2(rel[:, 0], -rel[:, 1]))
    rim = RG.rim_z(az, 'cap')
    cut = np.minimum(B.V[:, 2] - rim, B.headw - 0.5)
    el = np.degrees(np.arctan2(rel[:, 2], np.hypot(rel[:, 0], rel[:, 1])))
    crown = np.clip(np.sin(np.radians(np.clip(el, 0, 90))), 0, 1)
    th = thick + 0.05 * crown + 0.02 * np.clip(1 - np.abs(az) / 60, 0, 1)
    g = 0.4 + 0.5 * (1 - crown)
    if h.get('panel') and h.get('panel') != 'hat':
        front = 1.0 - np.abs(az) / 52.0                     # front panel = |az| < 52 deg
        p1 = SH.shell_from_body(ctx, np.minimum(cut, front), th, pcell, 'cap_front', g=g, rim=0.02, cover=False)
        p2 = SH.shell_from_body(ctx, np.minimum(cut, -front), th, cell, 'cap_back', g=g, rim=0.02, cover=False)
        for pp in (p1, p2):
            if pp is not None:
                ctx.add(pp, 'head')
    else:
        p = SH.shell_from_body(ctx, cut, th, cell, 'cap', g=g, rim=0.02, cover=False)
        ctx.add(p, 'head')
    # button on top
    top = np.array([0, 0.18 * u, P.head_top + thick + 0.05])
    ctx.add(O.stud(top, np.array([0, 0, 1.0]), 0.16, cell, 'cap_button', h=0.8), 'head')
    # visor
    bl = h.get('brim_len', 3.2) * 0.2
    brim_cell = O.cloth_cell(ctx, 'brim', h.get('brim'), 'hat') if h.get('brim') not in (None, 'hat') else cell
    az_s = np.linspace(-78, 78, 15)
    rs = np.linspace(0, 1, 6)
    z_rim = RG.rim_z(0, 'cap')
    grid = np.zeros((len(az_s), len(rs), 3))
    for i, a in enumerate(az_s):
        zr = RG.rim_z(a, 'cap') - 0.02
        el_ = RG.ellipse(zr, thick + 0.02)
        cx, cy, rx, ry = el_
        ar = math.radians(a)
        base = np.array([cx + rx * math.sin(ar), cy - ry * math.cos(ar), zr])
        outv = np.array([math.sin(ar) * 0.75, -math.cos(ar), 0.0])
        outv = outv / np.linalg.norm(outv)
        wlen = bl * (1.0 - 0.28 * (abs(a) / 78.0) ** 2)
        for j, r_ in enumerate(rs):
            drop = -0.25 * (r_ ** 1.6) * wlen + 0.18 * (r_ ** 3) * wlen * 0 - 0.08 * r_ * wlen
            grid[i, j] = base + outv * (r_ * wlen) + np.array([0, 0, drop + 0.05 * (1 - r_)])
    part = G.solid_surface(grid, 0.07, cell=brim_cell, name='visor', wrap_u=False, g=np.tile(np.linspace(0.3, 0.9, len(rs))[None, :], (len(az_s), 1)),
                           offset=0.5, outward_from=(0, 0.2, z_rim + 3), inner='full')
    ctx.add(part, 'head')
    logo(ctx, RG, h, z_rim)


def logo(ctx, RG, h, z_rim):
    lg = h.get('logo')
    if not lg:
        return
    HR = ctx.headref
    hat_col = ctx.col(h.get('panel') if h.get('panel') not in (None, 'hat') else h.get('color'), 'hat')
    if lg == 'ball':
        painter = PT.detail_pokeball(bg=hat_col, top=ctx.col(h.get('logo_color'), '#e04040') if h.get('logo_color') else '#e04040')
    elif lg == 'R':
        painter = PT.detail_letter_R(bg=hat_col, fg=ctx.col(h.get('logo_color'), '#e04040'))
    elif lg == 'badge':
        painter = PT.detail_badge(bg=ctx.col(h.get('badge_color') or h.get('logo_color'), '#e8c84a'), fg='#b89020')
    else:
        return
    cell = ctx.detail('hatlogo', painter, 32, 32)
    pts = np.zeros((7, 7, 3))
    uv = np.zeros((7, 7, 2))
    zc = RG.rim_z(0, 'cap') + 0.72
    for i, x in enumerate(np.linspace(-0.42, 0.42, 7)):
        for j, z in enumerate(np.linspace(-0.42, 0.42, 7)):
            pts[i, j] = (x, -3.0, zc + z)
            uv[i, j] = (i / 6.0, j / 6.0)
    # cast onto the hat surface (body ray + hat thickness)
    flat, nrm = FC.lift_to_skin(ctx, pts.reshape(-1, 3), 0.235)
    part = FC.grid_part(flat.reshape(7, 7, 3), cell, 'logo', uv=uv, bone='head', out_from=(0, 3, zc))
    part.ao_gain = 0.0
    ctx.add(part)


def hat_beanie(ctx, RG, h):
    """Snug knit cap: covers the crown down to the brow / over the ears, with a folded cuff."""
    P = ctx.P
    cell = hat_cell(ctx, h)
    ctx.hat_rim = lambda az: RG.rim_z(az, 'beanie') + 0.05
    B = ctx.body
    rel = B.V - ctx.headref.hc
    az = np.degrees(np.arctan2(rel[:, 0], -rel[:, 1]))
    rim = RG.rim_z(az, 'beanie')
    cut = np.minimum(B.V[:, 2] - rim, B.headw - 0.5)
    th = np.full(len(B.V), 0.2) + 0.03 * SH._noise(B.V * 2.0, 4)
    p = SH.shell_from_body(ctx, cut, th, cell, 'beanie', g=np.clip((B.V[:, 2] - P.chin) / 3.3, 0, 1), rim=0.02, cover=False)
    ctx.add(p, 'head')
    if h.get('cuff', True):
        cc = O.cloth_cell(ctx, 'beaniecuff', h.get('color'), 'hat')
        c2 = np.minimum(cut, rim + 0.55 - B.V[:, 2])
        q = SH.shell_from_body(ctx, c2, th + 0.06, cc, 'cuff', g=np.full(len(B.V), 0.5), rim=0.02, cover=False)
        if q is not None:
            ctx.add(q, 'head')
    if h.get('tails'):
        pass


def hat_wide(ctx, RG, h):
    """Wide-brimmed hat (fisher / hiker / safari / sun hat): rounded crown, hat band, drooping brim."""
    P = ctx.P
    u = RG.u
    cell = hat_cell(ctx, h)
    z_rim = P.chin + (h.get('z', 1.5) * 0.36 + 1.55) * u
    crown_h = h.get('crown', 5.4) * 0.19 * u
    z_top = P.head_top + crown_h * 0.42
    zs = np.linspace(z_rim, z_top, 9)
    seg = 36
    rows = []
    for k, z in enumerate(zs):
        f = k / (len(zs) - 1)
        el = RG.ellipse(min(z, P.head_top - 0.04), 0.14 + 0.05 * f)
        cx, cy, rx, ry = el
        if z > P.head_top - 0.04:
            q = (z - (P.head_top - 0.04)) / max(z_top - (P.head_top - 0.04), 1e-3)
            k_ = math.sqrt(max(1 - q ** 2, 0.0))
            rx, ry = rx * (0.55 + 0.45 * k_), ry * (0.55 + 0.45 * k_)
        rows.append(ring_points(cx, cy, rx * (1.0 + 0.06 * math.sin(math.pi * f)), ry * (1.0 + 0.06 * math.sin(math.pi * f)), z, seg, expo=2.2))
    Pg = np.transpose(np.array(rows), (1, 0, 2))
    # close the crown with a cap of rings shrinking to the centre
    cap_rows = []
    last = np.array(rows[-1])
    cen = last.mean(0)
    for f in (0.55, 0.25, 0.02):
        cap_rows.append(cen + (last - cen) * f + np.array([0, 0, 0.05 * (1 - f)]))
    Pg = np.concatenate([Pg, np.transpose(np.array(cap_rows), (1, 0, 2))], 1)
    g = np.tile(np.linspace(0.2, 0.9, Pg.shape[1])[None, :], (seg, 1))
    ctx.add(G.solid_surface(Pg, 0.09, cell=cell, name='crown', wrap_u=True, g=g, offset=0.5, outward_from=(0, 0.2, z_rim - 4), inner='rim'), 'head')
    # band
    if h.get('band'):
        bc = O.cloth_cell(ctx, 'hatband', h['band'], 'accent')
        rowsb = []
        for z in np.linspace(z_rim + 0.05, z_rim + 0.5, 4):
            cx, cy, rx, ry = RG.ellipse(z, 0.2)
            rowsb.append(ring_points(cx, cy, rx, ry, z, seg, 2.2))
        Pb = np.transpose(np.array(rowsb), (1, 0, 2))
        ctx.add(G.solid_surface(Pb, 0.05, cell=bc, name='band', wrap_u=True, offset=0.5, outward_from=(0, 0.2, z_rim - 4), inner='rim'), 'head')
    # brim
    brim_out = max((h.get('brim_r', 8.6) - 6.0) * 0.34, 0.5) * u
    droop = h.get('droop', 0.4) * 0.35
    cx, cy, rx, ry = RG.ellipse(z_rim + 0.02, 0.2)
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    rr = np.linspace(0, 1, 6)
    grid = np.zeros((seg, len(rr), 3))
    for i, a in enumerate(ang):
        base = np.array([cx + rx * math.sin(a), cy - ry * math.cos(a), z_rim + 0.02])
        outv = np.array([math.sin(a) * rx, -math.cos(a) * ry, 0.0])
        outv = outv / np.linalg.norm(outv)
        for j, r_ in enumerate(rr):
            grid[i, j] = base + outv * brim_out * r_ - np.array([0, 0, droop * r_ ** 1.8 * brim_out + 0.08 * r_])
    ctx.add(G.solid_surface(grid, 0.08, cell=cell, name='brim', wrap_u=True, g=np.tile(np.linspace(0.3, 0.8, len(rr))[None, :], (seg, 1)), offset=0.5,
                            outward_from=(0, 0.2, z_rim - 4), inner='full'), 'head')


def hat_sailor(ctx, RG, h):
    """Sailor / captain's cap: flat round top, band, optional peak and badge."""
    P = ctx.P
    u = RG.u
    cell = hat_cell(ctx, h)
    z_rim = P.chin + 1.98 * u
    ctx.hat_rim = lambda az: np.full_like(np.asarray(az, float), z_rim + 0.05)
    seg = 32
    zs = np.linspace(z_rim, P.head_top + 0.35, 8)
    rows = []
    for k, z in enumerate(zs):
        f = k / (len(zs) - 1)
        el = RG.ellipse(min(z, P.head_top - 0.04), 0.18 + 0.22 * f)
        cx, cy, rx, ry = el
        rows.append(ring_points(cx, cy, rx * (1 + 0.1 * f), ry * (1 + 0.1 * f), z, seg))
    last = np.array(rows[-1])
    cen = last.mean(0)
    for f in (0.6, 0.25, 0.02):
        rows.append(cen + (last - cen) * f + np.array([0, 0, 0.02]))
    Pg = np.transpose(np.array(rows), (1, 0, 2))
    ctx.add(G.solid_surface(Pg, 0.1, cell=cell, name='sailor', wrap_u=True, g=np.tile(np.linspace(0.2, 0.9, Pg.shape[1])[None, :], (seg, 1)),
                            offset=0.5, outward_from=(0, 0.2, z_rim - 4), inner='rim'), 'head')
    bc = O.cloth_cell(ctx, 'hatband', h.get('band'), 'accent')
    rowsb = []
    for z in np.linspace(z_rim, z_rim + 0.5, 4):
        cx, cy, rx, ry = RG.ellipse(z, 0.2)
        rowsb.append(ring_points(cx, cy, rx, ry, z, seg))
    ctx.add(G.solid_surface(np.transpose(np.array(rowsb), (1, 0, 2)), 0.06, cell=bc, name='band', wrap_u=True, offset=0.5,
                            outward_from=(0, 0.2, z_rim - 4), inner='rim'), 'head')
    if h.get('peak'):
        hat_cap_visor(ctx, RG, z_rim, cell)
    if h.get('badge'):
        lc = ctx.ramp('badge', 'metal', ctx.col(h.get('badge_color'), '#e8c84a'))
        c = np.array([0, RG.ellipse(z_rim + 0.3, 0.3)[1] - RG.ellipse(z_rim + 0.3, 0.3)[3] - 0.03, z_rim + 0.3])
        ctx.add(O.stud(c, np.array([0, -1.0, 0.2]), 0.3, lc, 'badge', h=0.4), 'head')


def hat_cap_visor(ctx, RG, z_rim, cell):
    az_s = np.linspace(-70, 70, 13)
    rs = np.linspace(0, 1, 5)
    grid = np.zeros((len(az_s), len(rs), 3))
    for i, a in enumerate(az_s):
        cx, cy, rx, ry = RG.ellipse(z_rim, 0.2)
        ar = math.radians(a)
        base = np.array([cx + rx * math.sin(ar), cy - ry * math.cos(ar), z_rim])
        outv = np.array([math.sin(ar) * 0.6, -math.cos(ar), 0.0])
        outv /= np.linalg.norm(outv)
        for j, r_ in enumerate(rs):
            grid[i, j] = base + outv * 0.6 * r_ - np.array([0, 0, 0.12 * r_])
    ctx.add(G.solid_surface(grid, 0.06, cell='brim' if 'brim' in ctx.atlas.cells else cell, name='peak', g=np.tile(np.linspace(0.3, 0.9, 5)[None, :], (13, 1)),
                            offset=0.5, outward_from=(0, 0.2, z_rim + 3), inner='full'), 'head')


def hat_chef(ctx, RG, h):
    """Tall puffed chef's hat."""
    P = ctx.P
    u = RG.u
    cell = hat_cell(ctx, h)
    z_rim = P.chin + 2.1 * u
    ctx.hat_rim = lambda az: np.full_like(np.asarray(az, float), z_rim + 0.05)
    seg = 32
    rows = []
    z_top = P.head_top + 2.2 * u
    zs = np.linspace(z_rim, z_top, 12)
    for k, z in enumerate(zs):
        f = k / (len(zs) - 1)
        cx, cy, rx, ry = RG.ellipse(z_rim + 0.1, 0.2)
        puff = 1.0 + 0.45 * math.sin(min(f * 1.4, 1.0) * math.pi * 0.62) ** 1.2
        if f > 0.82:
            puff *= math.sqrt(max(1 - ((f - 0.82) / 0.18) ** 2, 0.0)) * 0.55 + 0.45
        rows.append(ring_points(cx, cy, rx * puff, ry * puff, z, seg))
    last = np.array(rows[-1])
    cen = last.mean(0)
    for f in (0.6, 0.25, 0.02):
        rows.append(cen + (last - cen) * f)
    Pg = np.transpose(np.array(rows), (1, 0, 2))
    ctx.add(G.solid_surface(Pg, 0.09, cell=cell, name='chef', wrap_u=True, g=np.tile(np.linspace(0.2, 0.9, Pg.shape[1])[None, :], (seg, 1)), offset=0.5,
                            outward_from=(0, 0.2, z_rim - 4), inner='rim'), 'head')


def hat_nurse(ctx, RG, h):
    """Small flat nurse's cap pinned on top of the hair, with a cross."""
    P = ctx.P
    u = RG.u
    cell = hat_cell(ctx, h)
    c = np.array([0, 0.05 * u, P.head_top - 0.28])
    body = H.ellipsoid_part(c + np.array([0, -0.55 * u, 0.12]), (0.95 * u, 0.42 * u, 0.2 * u), name='nursecap', cell=cell, seg=20, rings=8)
    ctx.add(body, 'head')
    xc = ctx.detail('cross', PT.detail_cross(bg=ctx.col(h.get('color'), 'accent'), fg=ctx.col(h.get('cross'), '#e03848')), 32, 32)
    pts = np.zeros((5, 5, 3))
    uv = np.zeros((5, 5, 2))
    for i, x in enumerate(np.linspace(-0.3, 0.3, 5)):
        for j, z in enumerate(np.linspace(-0.09, 0.09, 5)):
            pts[i, j] = (x, c[1] - 0.55 * u - 0.36 * u - 0.03, c[2] + 0.14 + z * 0)
            uv[i, j] = (i / 4.0, j / 4.0)
    ctx.add(FC.grid_part(pts, xc, 'nurse_cross', uv=uv, bone='head', out_from=(0, 3, c[2])), 'head')


def hat_headband(ctx, RG, h):
    """Headband round the forehead (Daisy) / ninja band with a metal plate and tails (Koga)."""
    P = ctx.P
    u = RG.u
    cell = hat_cell(ctx, h)
    z = P.chin + 2.0 * u
    hh = h.get('h', 7) * 0.05
    seg = 32
    rows = []
    for zz in np.linspace(z - hh / 2, z + hh / 2, 4):
        cx, cy, rx, ry = RG.ellipse(zz, 0.08)
        rows.append(ring_points(cx, cy, rx, ry, zz, seg))
    Pg = np.transpose(np.array(rows), (1, 0, 2))
    ctx.add(G.solid_surface(Pg, 0.08, cell=cell, name='headband', wrap_u=True, offset=0.5, outward_from=(0, 0.2, z - 4), inner='rim'), 'head')
    if h.get('plate'):
        mc = ctx.ramp('plate', 'metal', '#c8c8d0')
        cx, cy, rx, ry = RG.ellipse(z, 0.12)
        ctx.add(O.stud(np.array([0, cy - ry - 0.02, z]), np.array([0, -1.0, 0]), 0.42, mc, 'plate', h=0.25), 'head')
    if h.get('tails', True) and h.get('type') == 'headband' and h.get('plate') is not None:
        cx, cy, rx, ry = RG.ellipse(z, 0.1)
        base = np.array([0, cy + ry, z])
        pts = np.array([base, base + [0.25, 0.5, -0.4], base + [0.45, 1.2, -1.3], base + [0.7, 1.8, -2.3]])
        for sd in (1, -1):
            pp = pts * np.array([sd, 1, 1])
            path = G.catmull(pp, 8)
            wd = np.linspace(0.16, 0.12, 8)
            p = G.loft(path, np.stack([wd, wd * 0.3], 1), seg=6, cell=cell, name='band_tail', caps=(0.3, 0.3), ref=(1, 0, 0))
            names = H.add_bones(ctx, 'band_%s' % ('L' if sd > 0 else 'R'), pp)
            H.chain_weights(p, pp, names, root='head', hw=0.5)
            ctx.add(p)
            ctx.anim_hints.setdefault('hair_twin', []).extend(names)


HATS = {'cap': hat_cap, 'beanie': hat_beanie, 'wide': hat_wide, 'sailor': hat_sailor, 'chef': hat_chef, 'nurse': hat_nurse, 'headband': hat_headband}


# ----------------------------------------------------------------------------- facial hair / glasses
def moustache(ctx, m):
    HR = ctx.headref
    u = HR.u
    P = ctx.P
    HS = AN.HeadShape(P, ctx.look.get('face', {}))
    col = ctx.ramp('beardc', 'hair', ctx.col(m.get('color'), 'beard'))
    kind = m.get('type', 'normal')
    big = 1.35 if kind == 'bushy' else 1.0
    nz = HS.z('nose') - 0.12 * u
    mz = HS.z('mouth')
    zc = mz + 0.2 * u
    for sd in (1, -1):
        n = 7
        s = np.linspace(0, 1, n)
        x = sd * (0.03 + 0.55 * s) * u
        z = zc + 0.03 * u - 0.32 * u * s ** 1.6 * (1 if kind != 'bushy' else 0.85) + 0.12 * u * math.sin(math.pi * 0.5) * (1 - s) * 0.4
        pts = np.stack([x, np.full(n, -3.0), z], 1)
        pts, nrm = FC.lift_to_skin(ctx, pts, 0.08 * big)
        pts[:, 1] -= 0.04 * big * (1 - s)
        w = 0.24 * u * big * (1 - 0.7 * s ** 2) + 0.03
        p = FC.ribbon(pts, nrm, w, col, 'moustache', bone='head', sag=0.2 + 0.4 * big)
        ctx.add(p)


def beard(ctx, b):
    HR = ctx.headref
    u = HR.u
    P = ctx.P
    B = ctx.body
    HS = AN.HeadShape(P, ctx.look.get('face', {}))
    col = ctx.ramp('beardc', 'hair', ctx.col(b.get('color'), 'beard'))
    kind = b.get('type', 'full')
    V = B.V
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    mz = HS.z('mouth')
    front = np.clip((HR.hc[1] - y) / (0.8 * u) + 0.4, -1, 1)              # >0 on the front half of the head
    if kind == 'full':
        top = mz + 0.25 * u + 0.75 * u * np.clip(np.abs(x) / (0.95 * u), 0, 1) ** 1.6
        cut = np.minimum.reduce([B.headw + B.trunk * 0 - 0.5, top - z, front + 0.1, z - (P.chin - 0.55 * u)])
        th = 0.12 + 0.05 * (1 - np.clip(np.abs(x) / u, 0, 1))
        # sculpt a fuller chin: thickness grows toward the chin tip
        th = th + 0.12 * np.exp(-((z - P.chin - 0.1 * u) / (0.5 * u)) ** 2) * np.clip(front + 0.2, 0, 1)
    elif kind == 'goatee':
        top = mz + 0.02 * u
        cut = np.minimum.reduce([B.headw - 0.5, top - z, 0.42 * u - np.abs(x), front + 0.2, z - (P.chin - 0.35 * u)])
        th = 0.12 + 0.1 * np.exp(-((z - P.chin - 0.05 * u) / (0.4 * u)) ** 2)
    else:                          # 'chin': short beard under the lip, optional pointed tuft
        top = mz - 0.12 * u
        cut = np.minimum.reduce([B.headw - 0.5, top - z, 0.62 * u - np.abs(x), front + 0.2, z - (P.chin - 0.5 * u)])
        th = 0.13 + 0.12 * np.exp(-((z - P.chin - 0.05 * u) / (0.45 * u)) ** 2)
    p = SH.shell_from_body(ctx, cut, th, col, 'beard', g=np.clip(0.3 + 0.6 * (V[:, 2] - P.chin) / (2.0 * u), 0, 1), rim=0.02, cover=False)
    if p is not None:
        ctx.add(p, 'head')
    if b.get('tuft') or kind == 'chin':
        pts = np.array([[0, HS.face_y(0, P.chin + 0.25 * u) - 0.12, P.chin + 0.3 * u], [0, HS.face_y(0, P.chin + 0.25 * u) - 0.2, P.chin - 0.1 * u],
                        [0, HS.face_y(0, P.chin + 0.25 * u) - 0.05, P.chin - 0.5 * u], [0, HS.face_y(0, P.chin + 0.25 * u) + 0.1, P.chin - 0.9 * u]])
        path = G.catmull(pts, 7)
        wd = np.linspace(0.42, 0.06, 7) * u
        tuft = G.loft(path, np.stack([wd, wd * 0.8], 1), seg=6, cell=col, name='beard_tuft', caps=(0.2, 0.9), ref=(1, 0, 0))
        ctx.add(tuft, 'head')


def glasses(ctx, g):
    HS = AN.HeadShape(ctx.P, ctx.look.get('face', {}))
    P = ctx.P
    u = HS.u
    eg = AN.eye_geom(P, ctx.look.get('face', {}), HS)
    col = ctx.ramp('frame', 'flat', ctx.col(g.get('color'), '#2a2a3a'))
    kind = g.get('type', 'round')
    wide = HS.wide
    for sd in (1, -1):
        e = eg[sd]
        ex, ez = e['ex'], e['ez']
        y = HS.face_y(ex, ez) - 0.28 * u
        n = 24
        a = np.linspace(0, 2 * math.pi, n, endpoint=False)
        if kind == 'square':
            rx, rz, ex_ = 0.42 * u, 0.3 * u, 6.0
            cs, sn = np.cos(a), np.sin(a)
            xx = rx * np.sign(cs) * np.abs(cs) ** (2 / ex_)
            zz = rz * np.sign(sn) * np.abs(sn) ** (2 / ex_)
        elif kind == 'shades':
            xx = 0.5 * u * np.cos(a)
            zz = 0.34 * u * np.sin(a) * (0.8 + 0.2 * np.cos(a * 0))
        else:
            xx = 0.44 * u * np.cos(a)
            zz = 0.44 * u * np.sin(a)
        ring = np.stack([ex + xx, np.full(n, y), ez - 0.02 * u + zz], 1)
        # rims sit on the face: cast each point onto the skin, then lift
        ring, nrm = FC.lift_to_skin(ctx, ring, 0.22)
        ring = np.vstack([ring, ring[:1]])
        w = 0.028 * u if kind != 'shades' else 0.05 * u
        path = ring
        p = G.loft(path, np.full((len(path), 2), w), seg=6, cell=col, name='rim', caps=(None, None), ref=(0, 0, 1))
        ctx.add(p, 'head')
        if kind == 'shades':
            lens = ctx.ramp('lens', 'flat', ctx.col(g.get('lens'), '#15151c'))
            ctr = ring[:-1].mean(0)
            pts = np.zeros((n, 3, 3))
            for i in range(n):
                for j, f in enumerate((0.0, 0.5, 1.0)):
                    pts[i, j] = ctr + (ring[i] - ctr) * f + np.array([0, 0.005, 0])
            lp = FC.grid_part(pts, lens, 'lens', bone='head', out_from=ctr + np.array([0, 3, 0]))
            lp.ao_gain = 0.0
            ctx.add(lp)
        # temple arm back to the ear
        ear = np.array([sd * (1.0 * u * wide + 0.08), 0.05 * u, HS.z('ear') + 0.25 * u])
        start = ring[0 if sd > 0 else n // 2]
        outer = ring[n // 2 if sd > 0 else 0]
        arm = np.array([outer, (outer + ear) / 2 + np.array([sd * 0.05, 0.0, 0.0]), ear])
        ctx.add(G.loft(G.catmull(arm, 6), np.full((6, 2), 0.045 * u), seg=6, cell=col, name='temple', caps=(0.3, 0.3), ref=(0, 0, 1)), 'head')
    # bridge
    e = eg[1]
    y = HS.face_y(0, e['ez']) - 0.3 * u
    br = np.array([[0.42 * u, y, e['ez'] + 0.05 * u], [0.0, y - 0.03, e['ez'] + 0.12 * u], [-0.42 * u, y, e['ez'] + 0.05 * u]])
    ctx.add(G.loft(G.catmull(br, 6), np.full((6, 2), 0.045 * u), seg=6, cell=col, name='bridge', caps=(0.3, 0.3), ref=(0, 0, 1)), 'head')


# ----------------------------------------------------------------------------- body extras
def _lift_line(ctx, xs, zs, off):
    """Points on the front of the body, `off` above the garment that covers them."""
    pts = np.stack([xs, np.full(len(xs), -3.0), zs], 1)
    return FC.lift_to_skin(ctx, pts, off, layer=True)


def belt(ctx, b):
    P, B = ctx.P, ctx.body
    col = O.cloth_cell(ctx, 'belt', b.get('color'), 'accent')
    z0 = P.waist - 0.2 + 0.35 * b.get('dz', 0.0)
    h = 0.5 * b.get('h', 1.0)
    z = B.V[:, 2]
    c = np.minimum(B.trunk + B.w.get('hips', 0) * 0.3 - 0.3, h / 2 - np.abs(z - z0))
    top_t = 0.05
    ctx.add(SH.shell_from_body(ctx, c, B.layer + top_t, col, 'belt', g=np.clip((z - (z0 - h / 2)) / h, 0, 1), cover=False))
    bk = ctx.ramp('buckle', 'metal', ctx.col(b.get('buckle'), '#c8c8d0'))
    pts, nrm = _lift_line(ctx, np.array([0.0]), np.array([z0]), top_t + 0.05)
    box = G.box_round(pts[0] + nrm[0] * 0.02, (0.34, 0.06, h * 0.5), r=0.05, cell=bk, name='buckle')
    box.set_bone('spine')
    ctx.add(box)
    balls = b.get('balls', 0)
    for k in range(balls):
        sx = 1 if k % 2 == 0 else -1
        p, n = _lift_line(ctx, np.array([sx * (1.1 + 0.55 * (k // 2))]), np.array([z0 - 0.05]), top_t + 0.1)
        bc = ctx.ramp('ball', 'ball', '#e04040')
        ball = H.ellipsoid_part(p[0], (0.2, 0.2, 0.2), name='ball', cell=bc)
        ctx.add(ball, 'spine')


def emblem(ctx, e):
    P = ctx.P
    kind = e.get('type', 'badge')
    if kind == 'R':
        painter = PT.detail_letter_R(bg=ctx.col(e.get('bg'), 'shirt'), fg=ctx.col(e.get('color'), '#e04040'))
    else:
        painter = PT.detail_badge(bg=ctx.col(e.get('bg'), '#f4f4f8'), fg=ctx.col(e.get('color'), '#e8c84a'))
    cell = ctx.detail('emblem', painter, 32, 32)
    zc = O.map_z(P, 9.7 + e.get('dz', 0.0) + 1.1)
    w = 0.55 * (e.get('h', 3.0) * 0.5 + 0.3)
    nx, nz = 7, 7
    pts = np.zeros((nx, nz, 3))
    uv = np.zeros((nx, nz, 2))
    xoff = e.get('x', 0.0)
    for i, x in enumerate(np.linspace(-w, w, nx)):
        for j, z in enumerate(np.linspace(-w, w, nz)):
            pts[i, j] = (xoff + x, -3.0, zc + z)
            uv[i, j] = (i / (nx - 1), j / (nz - 1))
    flat, nrm = FC.lift_to_skin(ctx, pts.reshape(-1, 3), 0.03, layer=True)
    part = FC.grid_part(flat.reshape(nx, nz, 3), cell, 'emblem', uv=uv, bone='chest', out_from=(0, 3, zc))
    part.ao_gain = 0.0
    ctx.add(part)


def tie(ctx, t):
    P = ctx.P
    col = O.cloth_cell(ctx, 'tie', t.get('color'), 'accent')
    z_top = P.neck_base - 0.15
    z_bot = O.map_z(P, 8.6)
    n = 9
    zs = np.linspace(z_top, z_bot, n)
    w = np.interp(zs, [z_bot, z_top - 0.9, z_top - 0.2, z_top], [0.34, 0.19, 0.24, 0.16])
    pts, nrm = _lift_line(ctx, np.zeros(n), zs, 0.05)
    ctx.add(FC.ribbon(pts, nrm, w * 1.7, col, 'tie', bone='chest', sag=0.3, g=np.linspace(0, 1, n)))
    knot = H.ellipsoid_part(pts[0] + nrm[0] * 0.03, (0.19, 0.14, 0.17), name='knot', cell=col, seg=10, rings=6)
    ctx.add(knot, 'chest')


def bowtie(ctx, t):
    P = ctx.P
    col = O.cloth_cell(ctx, 'bowtie', t.get('color'), 'accent')
    z = P.neck_base - 0.05
    p, n = _lift_line(ctx, np.array([0.0]), np.array([z]), 0.06)
    c = p[0]
    ctx.add(H.ellipsoid_part(c, (0.12, 0.1, 0.1), name='knot', cell=col, seg=8, rings=5), 'chest')
    for sd in (1, -1):
        w = H.ellipsoid_part(c + np.array([sd * 0.3, 0.0, 0.0]), (0.24, 0.07, 0.15), name='bow', cell=col, seg=10, rings=6)
        ctx.add(w, 'chest')


def scarf(ctx, s):
    P, B = ctx.P, ctx.body
    col = O.cloth_cell(ctx, 'scarf', s.get('color'), 'accent')
    z = B.V[:, 2]
    top = P.neck_base + 0.85 * P.s
    neckw = B.w.get('neck', np.zeros(len(z)))
    c = np.minimum.reduce([neckw + B.trunk * (z > P.neck_base - 0.2) - 0.35, top - z, z - (P.neck_base - 0.35)])
    ctx.add(SH.shell_from_body(ctx, c, B.layer + 0.13, col, 'scarf', g=np.clip((z - P.neck_base) / 1.2, 0, 1), cover=False))
    if s.get('tail'):
        # tail hanging from the knot at the front-left, with follow-through bones
        p0 = np.array([0.55, -1.15, P.neck_base - 0.1])
        pts = np.array([p0, p0 + [0.2, -0.2, -0.9], p0 + [0.3, -0.25, -2.0], p0 + [0.3, -0.2, -3.0]])
        path = G.catmull(pts, 9)
        wd = np.linspace(0.42, 0.34, 9)
        p = G.loft(path, np.stack([wd, np.full(9, 0.06)], 1), seg=8, cell=col, name='scarf_tail', caps=(0.3, 0.3), ref=(1, 0, 0), e=4.0)
        names = H.add_bones(ctx, 'scarf', pts, parent='chest')
        H.chain_weights(p, pts, names, root='chest', hw=0.6)
        ctx.add(p)
        ctx.anim_hints.setdefault('hair_back', []).extend([])


def necklace(ctx, n):
    P = ctx.P
    col = ctx.ramp('chain', 'metal', ctx.col(n.get('color'), '#d8c060'))
    seg = 20
    a = np.linspace(-math.radians(75), math.radians(75), seg)
    pts = []
    for ang in a:
        r = 1.0 + 0.0
        x = 1.05 * math.sin(ang)
        zc = P.neck_base - 0.05 - 0.6 * (1 - abs(math.cos(ang)) ** 0.3)
        pts.append((x, -3.0, zc - 0.55 * (math.cos(ang)) * 0.9 - 0.15))
    pts = np.array(pts)
    lifted, nrm = FC.lift_to_skin(ctx, pts, 0.09)
    p = G.loft(lifted, np.full((seg, 2), 0.028), seg=5, cell=col, name='chain', caps=(0.5, 0.5), ref=(0, 1, 0))
    ctx.add(p, 'chest')
    if n.get('pendant'):
        pc = O.cloth_cell(ctx, 'pendant', n.get('pendant'), 'accent')
        c = lifted[seg // 2] + nrm[seg // 2] * 0.03
        disc = H.ellipsoid_part(c + np.array([0, -0.02, -0.25]), (0.22, 0.05, 0.22), name='pendant', cell=pc, seg=14, rings=6)
        ctx.add(disc, 'chest')


def suspenders(ctx, s):
    P = ctx.P
    col = O.cloth_cell(ctx, 'susp', s.get('color'), 'accent')
    for sd in (1, -1):
        zs = np.linspace(O.map_z(P, 7.6), P.shoulder_top + 0.15, 11)
        xs = sd * np.interp(zs, [zs[0], P.chest, zs[-1]], [1.35, 1.35, 1.7])
        pts, nrm = _lift_line(ctx, xs, zs, 0.05)
        ctx.add(FC.ribbon(pts, nrm, 0.34, col, 'suspender', bone='chest', sag=0.2))


def wristbands(ctx, w):
    B = ctx.body
    col = O.cloth_cell(ctx, 'wristband', w.get('color'), 'accent')
    for sd in (1, -1):
        c = np.minimum.reduce([B.arm[sd] - 0.5, B.arm_t[sd] - 0.53, 0.6 - B.arm_t[sd]])
        ctx.add(SH.shell_from_body(ctx, c, B.layer + 0.05, col, 'wristband', g=np.full(len(B.V), 0.5), cover=False))


def backpack(ctx, bk):
    P = ctx.P
    s = bk.get('size', 1.0)
    col = O.cloth_cell(ctx, 'bag', bk.get('color'), 'bag')
    cz = O.map_z(P, 9.3)
    c = np.array([0.0, P.chest * 0 + 1.55 * P.ls + 0.75 * s, cz])
    box = G.box_round(c, (1.65 * P.ls * s, 0.72 * s, 2.0 * P.s * s), r=0.32, cell=col, name='backpack')
    box.set_bone('chest')
    ctx.add(box)
    flap = G.box_round(c + np.array([0, 0.28 * s, 0.9 * s]), (1.5 * P.ls * s, 0.56 * s, 1.0 * P.s * s), r=0.25, cell=col, name='bag_flap')
    flap.set_bone('chest')
    ctx.add(flap)
    for sd in (1, -1):
        zs = np.linspace(P.shoulder_top + 0.1, cz - 1.3, 8)
        xs = np.full(8, sd * 1.35 * P.ls)
        pts, nrm = _lift_line(ctx, xs, zs, 0.05)
        ctx.add(FC.ribbon(pts, nrm, 0.36, col, 'strap', bone='chest', sag=0.15))
    if bk.get('roll'):
        rc = ctx.ramp('roll', 'cloth', ctx.col(bk['roll']))
        ctx.add(H.torus(c + np.array([0, 0.5 * s, -2.1 * s]), np.array([1.0, 0, 0]), 0.55 * s, 0.42 * s, cell=rc, name='roll'), 'chest')


def cape(ctx, cp):
    P, B = ctx.P, ctx.body
    col = O.cloth_cell(ctx, 'cape', cp.get('color'), 'accent', hem=cp.get('hem'))
    z_top = P.shoulder_top - 0.1
    z_bot = P.lift + 2.0
    n_c, n_r = 15, 10
    Pg = np.zeros((n_c, n_r, 3))
    for i, a in enumerate(np.linspace(-1, 1, n_c)):
        for j, f in enumerate(np.linspace(0, 1, n_r)):
            z = z_top + (z_bot - z_top) * f
            x = a * (2.6 * P.ls + 1.8 * f)
            back = float(O.envelope_radii(ctx, z, np.array([math.pi]), cy=0.1)[0])
            y = 0.1 + max(back, 1.6) + 0.22 + 0.35 * f + 0.25 * (a ** 2) * (1 - f)
            Pg[i, j] = (x, y, z)
    g = np.tile(np.linspace(1, 0, n_r)[None, :], (n_c, 1))
    part = G.solid_surface(Pg, 0.08, cell=col, name='cape', g=g, offset=0.5, outward_from=(0, -3, P.chest), inner='full')
    pts = np.array([Pg[n_c // 2, k] for k in (0, 3, 5, 7, 9)])
    names = H.add_bones(ctx, 'cape', pts, parent='chest')
    H.chain_weights(part, pts, names, root='chest', hw=1.0)
    ctx.add(part)
    ctx.anim_hints.setdefault('hair_back', []).extend(names)
    if cp.get('collar'):
        cc = O.cloth_cell(ctx, 'capecollar', cp['collar'], 'accent')
        z = B.V[:, 2]
        neckw = B.w.get('neck', np.zeros(len(z)))
        c = np.minimum.reduce([neckw + B.trunk * (z > P.neck_base - 0.2) - 0.35, P.neck_base + 1.0 - z, z - (P.neck_base - 0.2)])
        ctx.add(SH.shell_from_body(ctx, c, B.layer + 0.06, cc, 'capecollar', g=np.full(len(z), 0.5), cover=False))

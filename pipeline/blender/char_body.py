"""Chibi body: context, head, face features, torso, limbs, hands, shoes."""
import math

import numpy as np

import char_geo as G
import char_paint as PT
from char_rig import Prop, FOOT_LEN_BACK, FOOT_LEN_FRONT

DEFAULT_COL = {'skin': '#f0b88a', 'hair': '#4a3428', 'hat': '#d03a3a', 'shirt': '#4a78c8', 'pants': '#3a4058',
               'shoes': '#2e2e3e', 'accent': '#f8f8f8', 'coat': '#f4f4f8', 'bag': '#c8a040'}


# ----------------------------------------------------------------------------- context
class Ctx:
    def __init__(self, key, cast, look):
        self.key, self.cast, self.look = key, cast, look
        b = look.get('build', {})
        self.P = Prop(sh=b.get('sh', 1.0), sw=b.get('sw', 1.0), hs=b.get('hs', 1.0), bulk=b.get('bulk', 1.0),
                      belly=b.get('belly', 0.0), neck=b.get('neck', 1.0), stoop=b.get('stoop', 0.0))
        self.head = Head(self.P, jaw=b.get('jaw', 0.20), wide=b.get('face_wide', 1.0))
        self.atlas = PT.Atlas(256)
        self.parts = []
        self.extra_bones = []      # (name, parent, head, tail)
        self.anim_hints = {}       # e.g. hair bones for secondary motion
        self.pal = dict(DEFAULT_COL)
        for k in ('skin', 'hair', 'hat', 'shirt', 'pants', 'shoes', 'accent', 'coat'):
            if cast.get(k):
                self.pal[k] = cast[k]
        self.pal['bag'] = cast.get('backpack') or cast.get('bag') or DEFAULT_COL['bag']
        self.pal['hatk'] = cast.get('hatK') or PT.rgb2hex(PT.shade(PT.hex2rgb(self.pal['hat']), 0.45))
        self.pal['beard'] = cast.get('beard') or self.pal['hair']
        for k, v in look.get('colors', {}).items():
            self.pal[k] = v
        self.bones = {}
        self.cover = False        # a snug hat covers the crown (hair shows only below the rim)

    # colours: a role name from the palette or a literal hex
    def col(self, spec, default=None):
        if spec is None:
            spec = default
        if isinstance(spec, str) and spec.startswith('#'):
            return spec
        return self.pal.get(spec, self.pal.get(default, '#888888') if default else '#888888')

    def shade(self, hexc, amt):
        return PT.rgb2hex(PT.shade(PT.hex2rgb(hexc), amt))

    # cells ---------------------------------------------------------------
    def ramp(self, name, style, color, **kw):
        self.atlas.ramp(name, style, color, **kw)
        return name

    def detail(self, name, painter, w=32, h=32):
        self.atlas.detail(name, painter, w, h)
        return name

    def add(self, part, bone=None, cell=None, ao=None):
        if part is None:
            return None
        if bone is not None:
            part.set_bone(bone)
        if cell is not None:
            part.cell = cell
        if ao is not None:
            part.ao_gain = ao
        self.parts.append(part)
        return part


# ----------------------------------------------------------------------------- head surface
class Head:
    """Head = ellipsoid with a tapered jaw.  Points addressed by (azimuth, elevation) degrees:
    az 0 = straight ahead (-Y), positive toward +X (character's left); el 0 = equator."""

    def __init__(self, P, jaw=0.20, wide=1.0):
        self.P, self.jaw, self.wide = P, jaw, wide
        self.c = P.head_c.copy()
        self.r = np.array([P.head_rx * wide, P.head_ry, P.head_rz])

    def pt(self, d):
        d = np.asarray(d, float)
        x = d[..., 0] * self.r[0]
        y = d[..., 1] * self.r[1]
        z = d[..., 2] * self.r[2]
        t = G.smoothstep(0.0, -0.95, d[..., 2])
        x = x * (1 - self.jaw * t)
        y = y * (1 - 0.10 * t) + np.minimum(d[..., 1], 0.0) * 0.32 * t     # chin sits a little forward
        return self.c + np.stack([x, y, z], -1)

    @staticmethod
    def dir(az, el):
        a, e = np.radians(np.asarray(az, float)), np.radians(np.asarray(el, float))
        return np.stack([np.sin(a) * np.cos(e), -np.cos(a) * np.cos(e), np.sin(e)], -1)

    def surf(self, az, el, off=0.0):
        az, el = np.broadcast_arrays(np.asarray(az, float), np.asarray(el, float))
        d = self.dir(az, el)
        p0 = self.pt(d)
        h = 0.6
        pa = self.pt(self.dir(az + h, el)) - self.pt(self.dir(az - h, el))
        pe = self.pt(self.dir(az, el + h)) - self.pt(self.dir(az, el - h))
        n = G.nrm(np.cross(pa, pe))
        # make outward
        n = np.where((np.einsum('...i,...i->...', n, p0 - self.c) < 0)[..., None], -n, n)
        return p0 + n * np.asarray(off)[..., None] if np.ndim(off) else p0 + n * off

    def normal(self, az, el):
        return G.nrm(self.surf(az, el, 1.0) - self.surf(az, el, 0.0))


# ----------------------------------------------------------------------------- head + neck
def build_head(ctx, ear=True, nose='dot'):
    P, H = ctx.P, ctx.head
    skin = ctx.ramp('skin', 'skin', ctx.col('skin'))
    seg, rings = 28, 18
    th = np.linspace(0, math.pi, rings + 1)
    ph = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    PH, TH = np.meshgrid(ph, th, indexing='ij')
    dirs = np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], -1)
    Pt = H.pt(dirs)
    g = 0.5 + 0.5 * dirs[..., 2]
    head = G.surface_grid(Pt, skin, 'head', g=g.reshape(-1), wrap_u=True)
    ctx.add(head, 'head')
    if ear:
        for s in (1, -1):
            e = G.ellipsoid(H.surf(s * 88, -3, -0.35), (0.8, 0.6, 1.15), seg=10, rings=6, cell=skin, name='ear',
                            rot=G.rot_z(-s * 12))
            e.g[:] = 0.6
            ctx.add(e, 'head')
    if nose and nose != 'none':
        sz = {'dot': (0.5, 0.5, 0.42), 'small': (0.6, 0.62, 0.55), 'normal': (0.75, 0.8, 0.7), 'big': (1.0, 1.05, 0.9),
              'pointy': (0.62, 1.0, 0.75)}[nose]
        c = H.surf(0, -14, sz[1] * 0.05)
        n = G.ellipsoid(c, sz, seg=10, rings=6, cell=skin, name='nose')
        n.g[:] = 0.7
        ctx.add(n, 'head')
    # neck
    z0, z1 = P.neck_base - 0.7, P.neck_top + 0.5
    path = np.array([[0, 0.1, z0], [0, 0.1, (z0 + z1) / 2], [0, 0.1, z1]])
    neck = G.loft(path, [[1.75 * P.sw ** 0.5, 1.6], [1.5, 1.4], [1.45, 1.4]], seg=12, cell=skin, name='neck', caps=(0.3, 0.3))
    neck.g[:] = 0.2
    ctx.add(neck)
    bones = ['chest', 'neck', 'head']
    G.add_weights(neck, G.chain_weights(neck.V, [(0, 0, z0 - 0.5), (0, 0, P.neck_base), (0, 0, P.neck_top), (0, 0, P.head_top)],
                                        bones, [0.5, 0.3]))
    return head


# ----------------------------------------------------------------------------- face features
EYES = {
    'round': dict(haz=7.0, hel=11.0, tex='round'),
    'big': dict(haz=8.0, hel=12.5, tex='round'),
    'oval': dict(haz=6.3, hel=9.5, tex='oval'),
    'tall': dict(haz=5.8, hel=11.5, tex='tall'),
    'narrow': dict(haz=7.6, hel=6.2, tex='narrow'),
    'sharp': dict(haz=8.0, hel=7.4, tex='sharp'),
    'sleepy': dict(haz=7.2, hel=9.0, tex='sleepy'),
    'dot': dict(haz=3.3, hel=5.0, tex='dot'),
    'lash': dict(haz=7.8, hel=11.0, tex='round', lash=True),
    'lash_white': dict(haz=8.2, hel=10.0, tex='lash', lash=True),
}


def face_patch(ctx, az, el, haz, hel, cell, name, n_ang=18, n_rad=4, off=0.12, mirror=False, bone='head', flat=1.0, base=0.0):
    """Disc glued to the head surface, uv = planar picture of the disc."""
    H = ctx.head
    rho = np.linspace(0, 1.0, n_rad + 1)
    ang = np.linspace(0, 2 * math.pi, n_ang, endpoint=False)
    A, R = np.meshgrid(ang, rho, indexing='ij')
    azz = az + R * np.cos(A) * haz
    ell = el + R * np.sin(A) * hel
    o = off * (1 - R ** 2) + 0.02 - 0.05 * (R >= 0.999)
    Pt = H.surf(azz, ell, base + o * flat)
    uv = np.stack([0.5 + R * np.cos(A) * 0.5, 0.5 + R * np.sin(A) * 0.5], -1)
    if mirror:
        uv[..., 0] = 1 - uv[..., 0]
    p = G.surface_grid(Pt, cell, name, wrap_u=True, uv=uv, outward_from=H.c)
    p.ao_gain = 0.0
    ctx.add(p, bone)
    return p


def face_tube(ctx, pts_azel, radius, cell, name, off=None, seg=6, bone='head', caps=(0.9, 0.9), taper=None):
    """Tube following (az, el) points on the face."""
    H = ctx.head
    pa = np.asarray(pts_azel, float)
    n = max(len(pa), 6)
    t = np.linspace(0, 1, len(pa))
    tt = np.linspace(0, 1, n)
    az = np.interp(tt, t, pa[:, 0]) if len(pa) < 4 else G.catmull(pa, n)[:, 0]
    el = np.interp(tt, t, pa[:, 1]) if len(pa) < 4 else G.catmull(pa, n)[:, 1]
    r = np.full(n, float(radius)) if taper is None else radius * np.interp(tt, np.linspace(0, 1, len(taper)), taper)
    o = (r * 0.35) if off is None else off
    path = H.surf(az, el, o)
    p = G.loft(path, np.stack([r, r], 1), seg=seg, cell=cell, name=name, caps=caps, ref=(0, 1, 0))
    p.ao_gain = 0.0
    ctx.add(p, bone)
    return p


def build_face(ctx, face):
    """face: dict from looks (eyes, iris, brows, mouth, blush, freckles, ...)."""
    H, P = ctx.head, ctx.P
    style = face.get('eyes', 'round')
    skin = ctx.col('skin')
    hs = P.hs
    eaz = face.get('eye_az', 19.0)
    eel = face.get('eye_el', -5.0)
    dark = face.get('eye_color', '#181420')
    iris = face.get('iris', dark)
    if style == 'closed':
        # Brock: two curved dark slits
        for s in (1, -1):
            cell = ctx.ramp('eyeline', 'flat', face.get('eye_color', '#2a1c14'))
            pts = [(s * (eaz - 6.5), eel - 1.5), (s * (eaz - 2.5), eel - 3.0), (s * (eaz + 3.0), eel - 2.8), (s * (eaz + 7.0), eel - 0.6)]
            face_tube(ctx, pts, 0.17, cell, 'eyeline', bone='eye_L' if s > 0 else 'eye_R', seg=6, taper=[0.6, 1, 1, 0.6])
    else:
        e = EYES[style]
        for s in (1, -1):
            nm = 'eye_%s' % ('L' if s > 0 else 'R')
            cell = ctx.detail(nm, PT.detail_eye(e['tex'], s, iris=iris, skin=skin, lash=face.get('lash', e.get('lash', False)),
                                                dark=dark, lid=face.get('lid')), 48, 48)
            face_patch(ctx, s * eaz, eel, e['haz'] * face.get('eye_scale', 1.0), e['hel'] * face.get('eye_scale', 1.0),
                       cell, nm, bone=nm, off=0.16)
    # brows
    b = face.get('brows', 'normal')
    if b != 'none':
        bcol = ctx.col(face.get('brow_color'), 'hair')
        thick = {'thin': 0.13, 'normal': 0.19, 'thick': 0.3, 'bushy': 0.42}[b]
        cell = ctx.ramp('brow', 'flat', bcol)
        tilt = face.get('brow_tilt', 0.0)        # + = angry (inner ends low), - = worried
        bel = eel + (EYES[style]['hel'] if style in EYES else 6) + face.get('brow_gap', 4.0)
        for s in (1, -1):
            inner, outer = s * (eaz - 7.5), s * (eaz + 7.5)
            pts = [(inner, bel - tilt), (s * eaz, bel + 1.2), (outer, bel + tilt * 0.7 - 0.6)]
            face_tube(ctx, pts, thick, cell, 'brow', seg=6, taper=[0.8, 1.0, 0.7])
    # mouth
    m = face.get('mouth', 'smile')
    mcell = ctx.ramp('mouth', 'flat', face.get('mouth_color', '#7a3038'))
    mel = face.get('mouth_el', -33.0)
    mb = 'mouth'
    if m == 'smile':
        face_tube(ctx, [(-7, mel + 1.5), (-3.5, mel - 0.4), (0, mel - 0.9), (3.5, mel - 0.4), (7, mel + 1.5)], 0.15, mcell, 'mouth', bone=mb, taper=[0.6, 1, 1.1, 1, 0.6])
    elif m == 'grin':
        face_tube(ctx, [(-9, mel + 2.5), (-5, mel - 0.4), (0, mel - 1.5), (5, mel - 0.4), (9, mel + 2.5)], 0.16, mcell, 'mouth', bone=mb, taper=[0.6, 1, 1.1, 1, 0.6])
    elif m == 'flat':
        face_tube(ctx, [(-5, mel), (0, mel - 0.15), (5, mel)], 0.15, mcell, 'mouth', bone=mb, taper=[0.7, 1, 0.7])
    elif m == 'frown':
        face_tube(ctx, [(-6, mel - 1.4), (-3, mel + 0.1), (0, mel + 0.5), (3, mel + 0.1), (6, mel - 1.4)], 0.16, mcell, 'mouth', bone=mb, taper=[0.6, 1, 1.1, 1, 0.6])
    elif m == 'open':
        oc = ctx.detail('mouth_open', PT.detail_mouth_open(), 24, 24)
        face_patch(ctx, 0, mel - 0.5, 5.2, 4.0, oc, 'mouth', n_rad=3, off=0.05, bone=mb)
    elif m == 'o':
        oc = ctx.detail('mouth_o', PT.detail_flat('#5a1c28'), 8, 8)
        face_patch(ctx, 0, mel, 2.6, 3.2, oc, 'mouth', n_rad=2, n_ang=12, off=0.05, bone=mb)
    # cheeks
    if face.get('blush') or face.get('freckles'):
        cc = ctx.detail('cheek', PT.detail_cheek(skin, face.get('blush_color', '#f28a7c'), bool(face.get('freckles')),
                                                    strength=0.6 if face.get('blush') else 0.0), 32, 32)
        for s in (1, -1):
            face_patch(ctx, s * 30, -17, 9.5, 6.2, cc, 'cheek', n_ang=14, n_rad=3, off=0.05)
    # ---- glasses / face accessories are added by the outfit module


# ----------------------------------------------------------------------------- torso / limbs
def torso_pt(P, z, a, dr=0.0, e=2.4):
    """Point on the torso surface at height z, angle a (rad, 0 = front / -Y, + toward +X)."""
    rx, ry = P.torso_rx(z) + dr, P.torso_ry(z) + dr
    s, c = math.sin(a), math.cos(a)
    px = rx * math.copysign(abs(s) ** (2 / e), s)
    py = -ry * math.copysign(abs(c) ** (2 / e), c)
    return np.array([px, py + (0.15 if z < P.chest else 0.0), z])


def build_torso_shell(ctx, cell, dr=0.0, z_bot=None, z_top=None, name='torso', n=10, e=2.4, hem_flare=0.0, seg=18, g_up=True):
    P = ctx.P
    z0 = P.hip - 0.15 if z_bot is None else z_bot
    z1 = P.neck_base + 0.3 if z_top is None else z_top
    zs = np.linspace(z0, z1, n)
    path = np.array([[0, 0.15 if z < P.chest else 0.0, z] for z in zs])
    rad = np.array([[P.torso_rx(z) + dr + hem_flare * max(0, 1 - (z - z0) / 1.2), P.torso_ry(z) + dr + hem_flare * max(0, 1 - (z - z0) / 1.2)] for z in zs])
    t = G.loft(path, rad, seg=seg, cell=cell, name=name, caps=(0.15, 0.6), e=e, ref=(1, 0, 0))
    t.g = np.clip((t.V[:, 2] - z0) / max(z1 - z0, 1e-6), 0, 1)
    torso_weights(ctx, t)
    return t


def torso_weights(ctx, part):
    P = ctx.P
    pts = [(0, 0, P.hip - 1.0), (0, 0, P.waist), (0, 0, P.chest), (0, 0, P.neck_base), (0, 0, P.neck_top)]
    G.add_weights(part, G.chain_weights(part.V, [(0, 0, P.hip + 0.3)] + pts[1:], ['hips', 'spine', 'chest', 'neck'], [0.9, 0.9, 0.5]))
    # the first chain point is the hip bone head; fine
    return part


def arm_path(ctx, side, upto=1.0, n=9):
    """Centre line of the arm (shoulder cap -> wrist), truncated at fraction `upto` of the length."""
    P = ctx.P
    j = P.joints(side)
    pts = [j['shoulder'] + np.array([-side * 0.55, 0.0, 0.4]), j['shoulder'], (j['shoulder'] + j['elbow']) / 2, j['elbow'],
           (j['elbow'] + j['wrist']) / 2, j['wrist']]
    path = G.catmull(pts, 24)
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    s /= s[-1]
    return path, s


def limb_radius(s, table):
    xs = [t[0] for t in table]
    return np.interp(s, xs, [t[1] for t in table])


def arm_weights(ctx, part, side):
    P = ctx.P
    j = P.joints(side)
    sf = '_L' if side > 0 else '_R'
    G.add_weights(part, G.chain_weights(part.V, [j['shoulder'] + np.array([-side * 1.8, 0, 0.6]), j['shoulder'], j['elbow'], j['wrist'], j['hand_tip']],
                                        ['chest', 'upper_arm' + sf, 'forearm' + sf, 'hand' + sf], [1.1, 0.55, 0.4]))
    return part


def build_arm(ctx, side, cell, dr=0.0, upto=1.0, name='arm', cap_end=0.7, seg=10, taper=None, e=2.0, s_from=0.0):
    P = ctx.P
    path, s = arm_path(ctx, side)
    sel = (s <= upto + 1e-6) & (s >= s_from - 1e-6)
    path, s = path[sel], s[sel]
    # resample to ~11 rings, denser around the elbow
    idx = np.unique(np.linspace(0, len(path) - 1, 10).round().astype(int))
    path, s = path[idx], s[idx]
    b = P.bulk
    table = taper or [(0, 1.32), (0.15, 1.36), (0.55, 1.18), (0.7, 1.1), (1.0, 0.92)]
    r = limb_radius(s, table) * b + dr
    p = G.loft(path, np.stack([r, r * 0.97], 1), seg=seg, cell=cell, name=name, caps=(0.9 if s_from <= 0 else 0.0, cap_end if upto >= 1.0 else 0.0), e=e)
    p.g = np.clip(1 - (p.V[:, 2] - P.wrist_z) / (P.shoulder - P.wrist_z), 0, 1)
    arm_weights(ctx, p, side)
    return p


def build_hand(ctx, side, cell, name='hand'):
    P = ctx.P
    j = P.joints(side)
    W = j['wrist']
    sf = '_L' if side > 0 else '_R'
    sc = P.bulk ** 0.5
    parts = []
    # local frame: origin wrist, z down, x across (side), y forward(-)
    def T(p):
        return W + np.array([p[0] * side * 0 + p[0], p[1], p[2]]) * 1.0
    pal = G.ellipsoid(W + np.array([side * 0.1, 0.0, -0.85]), (0.62 * sc, 0.72 * sc, 0.95 * sc), seg=8, rings=5, cell=cell, name='palm')
    pal.g[:] = 0.4
    parts.append(pal)
    for k, y in enumerate((-0.42, 0.0, 0.42)):
        ln = (1.05, 1.15, 1.0)[k]
        pts = [W + np.array([side * 0.05, y * sc, -1.3]), W + np.array([-side * 0.02, y * sc - 0.08, -1.3 - ln * 0.55]),
               W + np.array([-side * 0.22, y * sc - 0.2, -1.3 - ln])]
        f = G.loft(np.array(pts), np.array([[0.27 * sc, 0.27 * sc], [0.25 * sc, 0.25 * sc], [0.21 * sc, 0.21 * sc]]),
                   seg=5, cell=cell, name='finger', caps=(0.9, 0.9), ref=(0, 1, 0))
        f.g[:] = 0.6
        parts.append(f)
    pts = [W + np.array([-side * 0.1, -0.5 * sc, -0.55]), W + np.array([-side * 0.35, -0.85 * sc, -0.95]), W + np.array([-side * 0.5, -0.95 * sc, -1.35])]
    th = G.loft(np.array(pts), np.array([[0.3 * sc, 0.3 * sc], [0.27 * sc, 0.27 * sc], [0.22 * sc, 0.22 * sc]]), seg=5, cell=cell, name='thumb', caps=(0.9, 0.9), ref=(0, 1, 0))
    th.g[:] = 0.6
    parts.append(th)
    m = G.merge_parts(parts, name, cell)
    m.set_bone('hand' + sf)
    return m


def leg_path(ctx, side, n=9):
    P = ctx.P
    j = P.joints(side)
    x = j['hip'][0]
    pts = np.array([[x, 0.0, P.hip + 0.9], [x, 0.0, P.hip], [x, 0.03, (P.hip + P.knee) / 2], [x, 0.05, P.knee], [x, 0.0, (P.knee + P.ankle) / 2], [x, 0.0, P.ankle + 0.15]])
    path = G.catmull(pts, n + 3)
    return path


def leg_weights(ctx, part, side):
    P = ctx.P
    j = P.joints(side)
    sf = '_L' if side > 0 else '_R'
    x = j['hip'][0]
    G.add_weights(part, G.chain_weights(part.V, [(x, 0, P.hip + 1.5), j['hip'], j['knee'], j['ankle'], (x, -1.0, P.ankle - 0.2)],
                                        ['hips', 'thigh' + sf, 'shin' + sf, 'foot' + sf], [0.9, 0.55, 0.35]))
    return part


def build_leg(ctx, side, cell, dr=0.0, z_top=None, z_bot=None, name='leg', flare=0.0, table=None, seg=10):
    P = ctx.P
    path = leg_path(ctx, side, 9)
    zt = path[0, 2] if z_top is None else z_top
    zb = path[-1, 2] if z_bot is None else z_bot
    sel = (path[:, 2] <= zt + 1e-6) & (path[:, 2] >= zb - 1e-6)
    path = path[sel]
    zs = path[:, 2]
    b = P.bulk
    tab = table or [(P.hip + 1.0, 1.58), (P.hip - 0.5, 1.58), (P.knee + 0.4, 1.44), (P.knee - 0.2, 1.33), (P.ankle + 0.6, 1.22), (P.ankle, 1.2)]
    xs = [t[0] for t in tab][::-1]
    ys = [t[1] for t in tab][::-1]
    r = np.interp(zs, xs, ys) * b + dr
    r = r + flare * np.clip((P.ankle + 1.4 - zs) / 1.4, 0, 1)
    p = G.loft(path, np.stack([r, r * 1.02], 1), seg=seg, cell=cell, name=name, caps=(0.15, 0.6), e=2.1)
    p.g = np.clip((p.V[:, 2] - P.ankle) / (P.hip - P.ankle), 0, 1)
    leg_weights(ctx, p, side)
    return p


def shoe_parts(ctx, side, kind, cell, sole_cell, accent_cell=None):
    """Sneaker / boot / flat / barefoot foot.  Returns parts (rigid to foot_x)."""
    P = ctx.P
    j = P.joints(side)
    x = j['ankle'][0]
    sf = '_L' if side > 0 else '_R'
    out = []
    bulk = P.bulk ** 0.5
    if kind == 'barefoot':
        cell_ = cell
        ys = np.array([1.2, 0.3, -1.0, -2.2, -3.1])
        zc = np.array([1.05, 1.15, 0.95, 0.75, 0.62])
        rx = np.array([0.95, 1.15, 1.25, 1.2, 0.95]) * bulk
        rz = np.array([0.85, 1.05, 0.7, 0.55, 0.45])
    else:
        cell_ = cell
        ys = np.array([1.35, 0.55, -0.6, -1.7, -2.6, -3.3])
        zc = np.array([1.2, 1.3, 1.05, 0.85, 0.75, 0.7])
        rx = np.array([1.05, 1.32, 1.45, 1.4, 1.25, 0.9]) * bulk
        rz = np.array([0.8, 1.3, 0.85, 0.65, 0.55, 0.42])
        if kind == 'boot':
            zc = zc + np.array([0.6, 0.9, 0.0, 0, 0, 0])
            rz = rz + np.array([0.65, 0.85, 0.0, 0, 0, 0])
        if kind == 'heel':
            zc = zc + np.array([0.3, 0.2, 0.05, 0, 0, 0])
    path = np.stack([np.full(len(ys), x), ys, zc], 1)
    path = G.catmull(path, 9)
    rx9 = np.interp(np.linspace(0, 1, 9), np.linspace(0, 1, len(rx)), rx)
    rz9 = np.interp(np.linspace(0, 1, 9), np.linspace(0, 1, len(rz)), rz)
    sh = G.loft(path, np.stack([rx9, rz9], 1), seg=12, cell=cell_, name='shoe', caps=(0.8, 1.0), e=2.3, ref=(1, 0, 0))
    sh.g = np.clip((sh.V[:, 2]) / 2.2, 0, 1)
    sh.set_bone('foot' + sf)
    out.append(sh)
    if kind not in ('barefoot',):
        # sole
        sp = np.stack([np.full(7, x), np.linspace(1.4, -3.35, 7), np.full(7, 0.32)], 1)
        sr = np.stack([np.interp(np.linspace(0, 1, 7), [0, 0.25, 0.6, 1], [1.0, 1.4, 1.5, 1.0]) * bulk + 0.03,
                       np.full(7, 0.33)], 1)
        so = G.loft(sp, sr, seg=10, cell=sole_cell, name='sole', caps=(0.8, 0.8), e=2.6, ref=(1, 0, 0))
        so.g[:] = 0.5
        so.set_bone('foot' + sf)
        out.append(so)
        if accent_cell:
            tp = G.ellipsoid((x, -2.6, 0.95), (1.05 * bulk, 0.85, 0.5), seg=10, rings=6, cell=accent_cell, name='toecap')
            tp.g[:] = 0.5
            tp.set_bone('foot' + sf)
            out.append(tp)
    return out

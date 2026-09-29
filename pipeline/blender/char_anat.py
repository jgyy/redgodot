"""Anatomy of the realistic body as a signed-distance field (see char_sdf.py).

build_field(P, face) -> Field.  Every limb, muscle group and facial feature is a primitive combined with a
smooth union so the figure is one continuous surface.  `face` (dict from character_looks.json) tweaks the
nose / jaw / brow / lips.  All numbers are sprite rows; Prop (char_rig.py) supplies the landmarks.
"""
import math

import numpy as np

import char_sdf as S
from char_sdf import RoundCone, Ellipsoid, Box, Stack

NOSE = {'dot': 0.62, 'small': 0.82, 'normal': 1.0, 'big': 1.22, 'pointy': 0.95}


def _v(*a):
    return np.array(a, float)


def _rot_y(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rot_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(x=0, y=0, z=0):
    return _rot_z(z) @ _rot_y(y) @ _rot_x(x)


# ----------------------------------------------------------------------------- torso
def torso(F, P):
    F.cur_tag = 'trunk'
    s, ls, sw, b = P.s, P.ls, P.sw, P.bulk
    f = P.f
    L = P.lift
    belly = P.belly
    m = P.muscle
    # (z, half width, half depth, x offset, y offset)
    rx_hip = (2.42 if f else 2.22) * ls * sw
    rx_waist = (1.85 if f else 2.0) * ls * sw * (1 + belly * 0.18)
    rx_chest = (2.0 if f else 2.3 + 0.35 * m) * ls * sw
    rx_sh = (2.05 if f else 2.45 + 0.3 * m) * ls * sw
    prof = [
        (P.crotch - 0.25 * s, rx_hip * 0.8, 1.4 * ls, 0, 0.12),
        (P.hip - 0.3 * s, rx_hip, 1.62 * ls, 0, 0.13),
        (P.hip + 1.0 * s, rx_hip * 0.98, 1.6 * ls, 0, 0.12),
        (P.waist - 0.4 * s, rx_waist, (1.32 + belly * 0.55) * ls, 0, 0.0 - belly * 0.25),
        (P.waist + 0.8 * s, rx_waist * 1.04, (1.32 + belly * 0.5) * ls, 0, -belly * 0.22),
        (P.chest, rx_chest, (1.5 + belly * 0.2) * ls, 0, 0.05),
        (P.chest + 1.05 * s, rx_chest * 1.03, 1.55 * ls, 0, 0.1),
        (P.shoulder - 0.15 * s, rx_sh, 1.42 * ls, 0, 0.15),
        (P.neck_base + 0.05 * s, 1.45 * ls, 1.05 * ls, 0, 0.2),
    ]
    F.add(Stack('z', prof, cap=0.3), k=0.25)
    # ribcage / back volume, lats
    # pecs / bust
    if f:
        for sd in (1, -1):
            F.add(Ellipsoid(_v(sd * 0.98 * ls, -1.05 * ls, P.chest + 0.2 * s), _v(0.98 * ls, 0.85 * ls, 0.95 * ls * (0.6 + P.bust * 0.5)),
                            euler(x=-12)), k=0.5)
    else:
        for sd in (1, -1):
            F.add(Ellipsoid(_v(sd * 1.05 * ls, -1.0 * ls, P.chest + 0.45 * s), _v(1.05 * ls, 0.62 * ls + 0.12 * m, 0.72 * ls), euler(x=-8)), k=0.45)
    # trapezius slope neck -> shoulder, clavicles
    for sd in (1, -1):
        F.cur_tag = 'clavicle' + ('_L' if sd > 0 else '_R')
        F.add(RoundCone(_v(sd * 0.45, 0.35, P.neck_base + 0.75 * s), _v(sd * (P.shoulder_x - 0.15), 0.1, P.shoulder_top - 0.35 * s), 0.55 * ls, 0.62 * ls), k=0.5)
        F.add(RoundCone(_v(sd * 0.35, -0.9 * ls, P.neck_base - 0.05 * s), _v(sd * (P.shoulder_x - 0.55), -0.55 * ls, P.shoulder_top - 0.55 * s), 0.2 * ls, 0.26 * ls), k=0.25)
    # glutes / hips
    F.cur_tag = 'trunk'
    for sd in (1, -1):
        F.add(Ellipsoid(_v(sd * P.hip_x * 0.92, 0.55 * ls, P.hip - 0.55 * s), _v(1.28 * ls * (1.08 if f else 1.0), 1.25 * ls, 1.35 * s)), k=0.45)


# ----------------------------------------------------------------------------- limbs
def arm(F, P, side, hand=True):
    ls, b, s = P.ls, P.bulk, P.s
    sd = side
    j = P.joints(side)
    sh, el, wr = j['shoulder'], j['elbow'], j['wrist']
    m = P.muscle
    f = P.f
    fs = 0.86 if f else 1.0
    r_up0, r_up1 = 0.7 * ls * b * fs + 0.08 * m, 0.56 * ls * b * fs + 0.05 * m
    sfx = '_L' if sd > 0 else '_R'
    F.cur_tag = 'upper_arm' + sfx
    F.add(RoundCone(sh + _v(0, 0.02, 0.05), el, r_up0, r_up1), k=0.3)
    # deltoid cap
    F.add(Ellipsoid(sh + _v(sd * 0.33 * ls, 0.0, 0.2 * s), _v(0.8 * ls * b * fs + 0.05 * m, 0.8 * ls * b * fs, 1.15 * s * (0.9 + 0.1 * b)), euler(y=-sd * 12)), k=0.4)
    # biceps / triceps mass
    F.add(Ellipsoid(sh + (el - sh) * 0.42 + _v(0, -0.06, 0), _v(0.62 * ls * b * fs + 0.06 * m, 0.66 * ls * b * fs + 0.08 * m, 1.7 * s)), k=0.4)
    F.cur_tag = None
    F.add(Ellipsoid(el, _v(0.52 * ls * b * fs, 0.52 * ls * b * fs, 0.52 * ls * b * fs)), k=0.3)
    F.cur_tag = 'forearm' + sfx
    F.add(RoundCone(el, wr, 0.52 * ls * b * fs, 0.34 * ls * b * fs), k=0.25)
    F.add(Ellipsoid(el + (wr - el) * 0.24 + _v(0, -0.02, 0), _v(0.56 * ls * b * fs, 0.58 * ls * b * fs, 1.25 * s)), k=0.35)
    if hand:
        F.cur_tag = 'hand' + sfx
        hand_prims(F, P, side)


def hand_prims(F, P, side):
    """Relaxed hand: palm + 4 slightly curled fingers + thumb, all on the wrist frame."""
    sd = side
    j = P.joints(side)
    wr = j['wrist']
    d1, d2, d3 = j['arm_dirs']
    z = d3                                              # along the hand, toward the fingertips
    # palm faces the thigh: x_local points forward (-Y) so the thumb sits in front
    fwd = _v(0, -1, 0)
    lat = np.cross(z, fwd)                              # sideways across the palm
    lat /= np.linalg.norm(lat)
    if lat[0] * sd < 0:
        lat = -lat
    fwd2 = np.cross(lat, z)
    fwd2 /= np.linalg.norm(fwd2)
    if fwd2[1] > 0:
        fwd2 = -fwd2
    hs = P.hand_len / 2.35                              # hand size relative to the standard
    hb = math.sqrt(P.bulk)
    bulk_h = 0.5 + 0.5 * P.bulk
    R = np.stack([fwd2, lat, z], 1)
    W = wr
    # palm: broad in `lat`... palm is thin toward the thigh (lat) and wide along fwd
    F.add(Box(W + z * 0.85 * hs + fwd2 * 0.0, _v(0.6 * hs * bulk_h, 0.3 * hs * bulk_h, 0.78 * hs), rnd=0.2 * hs, R=R), k=0.25)
    F.add(Ellipsoid(W + z * 0.2 * hs, _v(0.42 * hs, 0.38 * hs, 0.5 * hs), R), k=0.25)
    # fingers: index nearest the front. curl toward the palm (-lat side is the thigh, so palm faces -lat)
    spec = [(0.5, 1.0, 1.0), (0.17, 1.06, 1.0), (-0.17, 1.0, 0.98), (-0.48, 0.86, 0.95)]      # (offset along fwd, length, radius scale)
    curl_dir = -lat
    for k_, (off, ln, rs) in enumerate(spec):
        base = W + z * 1.55 * hs + fwd2 * off * hs
        r0 = 0.165 * hs * rs * (0.9 + 0.1 * P.bulk)
        segs = [0.55 * ln * hs, 0.36 * ln * hs, 0.3 * ln * hs]
        curls = [14, 24, 20]
        spread = off * 6.0
        cur = base
        dirv = z.copy()
        rr = r0
        # slight fan-out
        dirv = dirv + fwd2 * math.sin(math.radians(spread))
        dirv /= np.linalg.norm(dirv)
        for si, (sl, cu) in enumerate(zip(segs, curls)):
            ang = math.radians(cu)
            dirv = dirv * math.cos(ang) + curl_dir * math.sin(ang)
            dirv /= np.linalg.norm(dirv)
            nxt = cur + dirv * sl
            r1 = rr * (0.9 if si < 2 else 0.8)
            F.add(RoundCone(cur, nxt, rr, r1), k=0.045)
            cur, rr = nxt, r1
    # thumb
    tb = W + z * 0.55 * hs + fwd2 * 0.42 * hs - lat * 0.06 * hs
    t1 = tb + (fwd2 * 0.55 + z * 0.75 - lat * 0.05) / 0.93 * 0.55 * hs
    t2 = t1 + (fwd2 * 0.42 + z * 0.85 - lat * 0.32) / 0.99 * 0.42 * hs
    t3 = t2 + (fwd2 * 0.15 + z * 0.9 - lat * 0.4) / 1.0 * 0.36 * hs
    F.add(RoundCone(tb, t1, 0.24 * hs, 0.2 * hs), k=0.14)
    F.add(RoundCone(t1, t2, 0.2 * hs, 0.17 * hs), k=0.06)
    F.add(RoundCone(t2, t3, 0.17 * hs, 0.145 * hs), k=0.05)


def leg(F, P, side, foot=True):
    ls, b, s = P.ls, P.bulk, P.s
    sd = side
    j = P.joints(side)
    hp, kn, an = j['hip'], j['knee'], j['ankle']
    f = P.f
    m = P.muscle
    fs = 1.04 if f else 1.0
    sfx = '_L' if sd > 0 else '_R'
    F.cur_tag = 'thigh' + sfx
    F.add(RoundCone(hp + _v(0, 0.0, 0.3 * s), kn, 1.22 * ls * b * fs, 0.78 * ls * b), k=0.4)
    # quads / hamstring mass
    F.add(Ellipsoid(hp + (kn - hp) * 0.4 + _v(0, -0.05, 0), _v(1.18 * ls * b * fs + 0.05 * m, 1.22 * ls * b + 0.05 * m, 2.6 * s)), k=0.5)
    F.cur_tag = None
    F.add(Ellipsoid(kn + _v(0, -0.1, 0), _v(0.74 * ls * b, 0.72 * ls * b, 0.7 * ls * b)), k=0.3)
    F.cur_tag = 'shin' + sfx
    F.add(RoundCone(kn, an, 0.72 * ls * b, 0.46 * ls * b), k=0.3)
    # calf
    F.add(Ellipsoid(kn + (an - kn) * 0.3 + _v(0, 0.28 * ls, 0), _v(0.72 * ls * b + 0.03 * m, 0.82 * ls * b, 1.9 * s)), k=0.4)
    if foot:
        F.cur_tag = 'foot' + sfx
        foot_prims(F, P, side)


def foot_prims(F, P, side, barefoot=False):
    ls, b = P.ls, math.sqrt(P.bulk)
    sd = side
    j = P.joints(side)
    an = j['ankle']
    x0 = an[0]
    L = P.lift
    ang = 7.0 * sd                                     # toes point slightly outward
    R = euler(z=-ang)
    fs = 0.5 + 0.5 * P.s
    # heel/arch/ball/toe volume, sole flat at z = lift
    F.add(RoundCone(_v(x0, 0.0, an[2] + 0.05), _v(x0, 0.28, L + 0.55 * fs), 0.5 * ls * b, 0.52 * ls * b), k=0.3)
    prof = [(1.15 * fs, 0.5 * ls * b, 0.5 * fs, 0, L + 0.5 * fs),
            (0.55 * fs, 0.72 * ls * b, 0.62 * fs, 0, L + 0.6 * fs),
            (-0.3 * fs, 0.76 * ls * b, 0.62 * fs, 0, L + 0.6 * fs),
            (-1.4 * fs, 0.84 * ls * b, 0.5 * fs, 0, L + 0.5 * fs),
            (-2.15 * fs, 0.82 * ls * b, 0.4 * fs, 0, L + 0.4 * fs),
            (-2.7 * fs, 0.62 * ls * b, 0.3 * fs, 0, L + 0.32 * fs)]
    st = Stack('y', prof, cap=0.25)
    # rotate about the ankle: wrap prim with a transform
    F.add(_Rotated(st, _v(x0, 0, 0), R), k=0.25)


class _Rotated(S.Prim):
    """Prim evaluated in a frame rotated about a pivot; stack profiles are authored around x = 0 -> shifted to the pivot."""

    def __init__(self, inner, pivot, R):
        self.inner, self.pivot, self.R = inner, np.asarray(pivot, float), np.asarray(R, float)
        c = (inner.lo + inner.hi) / 2
        r = np.linalg.norm(inner.hi - inner.lo) / 2
        cw = self.R @ c + self.pivot
        self.lo, self.hi = cw - r, cw + r

    def d(self, p):
        q = (p - self.pivot) @ self.R
        return self.inner.d(q)


# ----------------------------------------------------------------------------- head
# side-view profile of the head: (height above the chin in head units, half width, front y, back y).  The head is a
# Stack of these sections, so the profile (forehead, nose bridge, lips, chin, jaw) is exactly what is written here.
# Landmark heights follow adult anthropometry: eye line ~ 0.46 of the head height, nose base ~ 0.28, mouth ~ 0.2.
HEAD_PROFILE = [
    (0.00, 0.26, -0.80, 0.05),
    (0.14, 0.38, -1.02, 0.20),
    (0.30, 0.50, -1.14, 0.40),
    (0.50, 0.60, -1.10, 0.56),
    (0.72, 0.70, -1.15, 0.72),
    (0.95, 0.80, -1.08, 0.88),
    (1.25, 0.90, -1.09, 1.00),
    (1.55, 0.98, -1.11, 1.14),
    (1.86, 1.01, -1.20, 1.26),
    (2.15, 1.02, -1.12, 1.34),
    (2.45, 1.02, -1.02, 1.38),
]
# cranium dome: quarter ellipse from the temples up to the top of the skull
for _a in range(1, 11):
    _t = math.radians(_a * 90 / 10.0)
    _c, _s = math.cos(_t), math.sin(_t)
    HEAD_PROFILE.append((2.45 + 0.85 * _s, 1.02 * _c, -1.02 * _c + 0.18 * (1 - _c), 1.38 * _c + 0.18 * (1 - _c)))

# landmark heights (head units above the chin)
FEAT = {'eye': 1.52, 'brow': 1.86, 'nose': 0.86, 'mouth': 0.66, 'ear': 1.38, 'cheek': 1.38, 'chin': 0.22}


class HeadShape:
    """Head sections + a helper to find the face surface, so features are placed relative to it."""

    def __init__(self, P, face):
        self.P = P
        f = P.f
        self.child = P.age == 'child'
        self.u = P.head_h / 3.3
        self.low = 0.88 if self.child else (0.97 if P.age == 'teen' else 1.0)      # features sit lower on a child's head
        jaw = P.jaw * face.get('jaw', 1.0) * (0.92 if f else 1.0)
        wide = face.get('face_wide', 1.0) * 1.06
        self.wide = wide
        rows = []
        for (t, hw, fy, by) in HEAD_PROFILE:
            k = 1.0 + (jaw - 1.0) * (1 - min(t / 1.6, 1.0)) * 0.6 if t < 1.6 else 1.0
            fy2 = fy * (0.95 if self.child and t < 2.4 else 1.0)
            rows.append((self.tz(t), hw * k * wide, fy2, by))
        rows = np.array(rows)
        rows[:, 0] *= self.u
        self.rows = rows

    def tz(self, t):
        """Head-unit height after the child compression of the lower face."""
        lo = 2.3 * self.low
        if t <= 2.3:
            return t * self.low
        return lo + (t - 2.3) * (3.3 - lo) / (3.3 - 2.3)

    def z(self, name):
        """World height of a facial landmark."""
        return self.P.chin + self.tz(FEAT[name]) * self.u

    def sections(self):
        u, chin = self.u, self.P.chin
        pr = []
        for (zz, hw, fy, by) in self.rows:
            cy = (fy + by) / 2 * u
            hb = (by - fy) / 2 * u
            pr.append((chin + zz, hw * u, hb, 0.0, cy))
        return pr

    def front_y(self, x, zr):
        """y of the face surface at lateral x and height zr (rows above the chin)."""
        r = self.rows
        hw = np.interp(zr, r[:, 0], r[:, 1]) * self.u
        fy = np.interp(zr, r[:, 0], r[:, 2]) * self.u
        by = np.interp(zr, r[:, 0], r[:, 3]) * self.u
        cy, hb = (fy + by) / 2, (by - fy) / 2
        q = np.clip(abs(x) / hw, 0, 0.98)
        return cy - hb * math.sqrt(1 - q * q)

    def face_y(self, x, z):
        """y of the face surface at world height z."""
        return self.front_y(x, z - self.P.chin)


def eye_geom(P, face, HS=None):
    """Eyeball dome per side: {'ex', 'y0' (skin plane), 'ez', 'c' centre, 'r' radii}.  Shared with the face patches and the rig."""
    HS = HS or HeadShape(P, face)
    u = HS.u
    wide = HS.wide
    ez = HS.z('eye')
    out = {}
    for sd in (1, -1):
        ex = sd * 0.5 * u * wide
        y0 = HS.face_y(ex, ez)
        out[sd] = {'ex': ex, 'y0': y0, 'ez': ez, 'c': _v(ex, y0 + 0.2 * u, ez), 'r': _v(0.27 * u, 0.2 * u, 0.19 * u)}
    return out


def head(F, P, face):
    HS = HeadShape(P, face)
    u = HS.u
    chin = P.chin
    f = P.f
    wide = HS.wide
    fy = HS.face_y
    F.cur_tag = 'head'
    F.add(Stack('z', HS.sections(), cap=0.03, expo=2.35), k=0.2)
    # neck
    nr = (0.78 if f else 0.92) * P.ls
    F.cur_tag = 'neck'
    F.add(RoundCone(_v(0, 0.14, P.neck_base - 0.25 * P.s), _v(0, 0.08, P.neck_top), nr * 1.08, nr * 0.98), k=0.4)
    F.cur_tag = 'head'
    nose = NOSE[face.get('nose', 'normal')] * (0.94 if f else 1.0)
    # cheekbones and chin
    cz = HS.z('cheek')
    for sd in (1, -1):
        F.add(Ellipsoid(_v(sd * 0.72 * u * wide, fy(0.72 * u * wide, cz) + 0.2 * u, cz), _v(0.34 * u, 0.3 * u, 0.3 * u)), k=0.3)
    chz = HS.z('chin')
    F.add(Ellipsoid(_v(0, fy(0, chz) + 0.14 * u, chz), _v(0.36 * u * P.jaw, 0.22 * u, 0.24 * u)), k=0.2)
    # brow ridge
    bz = HS.z('brow')
    for sd in (1, -1):
        F.add(RoundCone(_v(sd * 0.14 * u, fy(0.14 * u, bz) + 0.06 * u, bz), _v(sd * 0.86 * u, fy(0.86 * u, bz) + 0.09 * u, bz - 0.02 * u),
                        0.11 * u * (0.85 if f else 1.0), 0.09 * u), k=0.15)
    # eye sockets (recess + eyeball dome)
    eg = eye_geom(P, face, HS)
    for sd in (1, -1):
        e = eg[sd]
        ex, y0, ez = e['ex'], e['y0'], e['ez']
        F.sub(Ellipsoid(_v(ex, y0 - 0.03 * u, ez), _v(0.34 * u, 0.12 * u, 0.22 * u)), k=0.1)
        F.add(Ellipsoid(e['c'], e['r']), k=0.03)
        F.add(RoundCone(_v(ex - sd * 0.3 * u, y0 + 0.13 * u, ez + 0.2 * u), _v(ex + sd * 0.3 * u, y0 + 0.1 * u, ez + 0.19 * u), 0.06 * u, 0.055 * u), k=0.05)
        F.add(RoundCone(_v(ex - sd * 0.24 * u, y0 + 0.14 * u, ez - 0.21 * u), _v(ex + sd * 0.26 * u, y0 + 0.11 * u, ez - 0.2 * u), 0.045 * u, 0.04 * u), k=0.05)
    # nose: bridge, tip, wings, nostrils
    ez = HS.z('eye')
    nz = HS.z('nose')
    yb = fy(0, nz)
    yt = yb - 0.30 * u * nose
    F.add(RoundCone(_v(0, fy(0, ez) + 0.03 * u, ez), _v(0, yt + 0.12 * u * nose, nz + 0.2 * u), 0.13 * u * nose, 0.2 * u * nose), k=0.18)
    F.add(Ellipsoid(_v(0, yt + 0.16 * u, nz + 0.1 * u), _v(0.2 * u * nose, 0.2 * u * nose, 0.17 * u * nose)), k=0.12)
    for sd in (1, -1):
        F.add(Ellipsoid(_v(sd * 0.19 * u * nose, yb + 0.08 * u, nz + 0.12 * u), _v(0.14 * u * nose, 0.16 * u * nose, 0.13 * u * nose)), k=0.1)
        F.sub(Ellipsoid(_v(sd * 0.09 * u * nose, yt + 0.14 * u, nz - 0.03 * u), _v(0.05 * u, 0.09 * u, 0.045 * u)), k=0.03)
    # lips
    mz = HS.z('mouth')
    lipw = (0.5 if f else 0.46) * u
    lipf = 1.3 if f else 1.0
    ym = fy(0, mz)
    F.add(RoundCone(_v(-lipw, ym + 0.05 * u, mz + 0.08 * u), _v(lipw, ym + 0.05 * u, mz + 0.08 * u), 0.078 * u * lipf, 0.078 * u * lipf), k=0.1)
    F.add(RoundCone(_v(-lipw * 0.85, ym + 0.08 * u, mz - 0.1 * u), _v(lipw * 0.85, ym + 0.08 * u, mz - 0.1 * u), 0.09 * u * lipf, 0.09 * u * lipf), k=0.1)
    F.sub(RoundCone(_v(-lipw * 1.05, ym - 0.12 * u, mz), _v(lipw * 1.05, ym - 0.12 * u, mz), 0.03 * u, 0.03 * u), k=0.03)
    # ears (solid: thin concave shells break up at this resolution)
    ezr = HS.z('ear')
    for sd in (1, -1):
        c = _v(sd * (1.0 * u * wide + 0.03), 0.27 * u, ezr)
        F.add(Ellipsoid(c, _v(0.15 * u, 0.25 * u, 0.44 * u), euler(z=-sd * 8, y=sd * 10)), k=0.1)


def build_field(P, face=None, barefoot=False):
    face = face or {}
    F = S.Field()
    torso(F, P)
    for sd in (1, -1):
        arm(F, P, sd)
        leg(F, P, sd)
    head(F, P, face)
    return F

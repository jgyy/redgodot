"""Character context + the welded realistic body (see char_anat.py for the shape, char_sdf.py for the maths).

Ctx is what every builder (face, hair, outfit, extras) receives: proportions (P), the palette, the texture atlas,
the list of finished mesh parts and, once build_body() ran, the BodyMesh they all hang off.
"""
import math

import numpy as np

import char_anat as AN
import char_geo as G
import char_mesh as M
import char_paint as PT
import char_sdf as S
import char_skin as SK
from char_rig import Prop

DEFAULT_COL = {'skin': '#f0b88a', 'hair': '#4a3428', 'hat': '#d03a3a', 'shirt': '#4a78c8', 'pants': '#3a4058',
               'shoes': '#2e2e3e', 'accent': '#f8f8f8', 'coat': '#f4f4f8', 'bag': '#c8a040'}

# grid the field is sampled on; every character is < 14 wide and 26 tall in rows
GRID_LO = (-7.5, -4.5, -0.6)
GRID_HI = (7.5, 4.0, 26.5)
VOXEL = 0.05


class Ctx:
    def __init__(self, key, cast, look):
        self.key, self.cast, self.look = key, cast, look
        b = dict(look.get('build', {}))
        shoes = look.get('shoes', {}).get('type', 'sneaker')
        b.setdefault('lift', 0.0 if shoes == 'barefoot' else 0.28)
        self.P = Prop(**{k: v for k, v in b.items() if k in Prop.__init__.__code__.co_varnames})
        self.P.fine_scalp = look.get('hair', {}).get('style') in ('spiky', 'flat', 'mohawk')
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
        self.body = None
        self.cover = False        # a snug hat covers the crown (hair shows only below the rim)
        self.covered = None       # bool per body vertex: hidden under opaque clothing (skin faces there are dropped)
        self.log = None

    # colours: a role name from the palette or a literal hex
    def col(self, spec, default=None):
        if spec is None:
            spec = default
        if isinstance(spec, str) and spec.startswith('#'):
            return spec
        return self.pal.get(spec, self.pal.get(default, '#888888') if default else '#888888')

    def shade(self, hexc, amt):
        return PT.rgb2hex(PT.shade(PT.hex2rgb(hexc), amt))

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


# ----------------------------------------------------------------------------- body
class BodyMesh:
    """The welded body surface with skin weights and per-vertex anatomy scalars."""

    def __init__(self, P, field, V, F, N, w):
        self.P, self.field = P, field
        self.V, self.F, self.N, self.w = V, F, N, w
        self._tree = None
        self._kd = None
        self.layer = np.zeros(len(V))       # thickness of the outermost garment on each vertex (decals / belts sit above it)
        wsum = lambda *names: sum((w[n] for n in names if n in w), np.zeros(len(V)))
        self.arm = {1: wsum('upper_arm_L', 'forearm_L', 'hand_L'), -1: wsum('upper_arm_R', 'forearm_R', 'hand_R')}
        self.leg = {1: wsum('thigh_L', 'shin_L', 'foot_L'), -1: wsum('thigh_R', 'shin_R', 'foot_R')}
        self.hand = {1: wsum('hand_L'), -1: wsum('hand_R')}
        self.foot = {1: wsum('foot_L'), -1: wsum('foot_R')}
        self.trunk = wsum('hips', 'spine', 'chest', 'clavicle_L', 'clavicle_R')
        self.headw = wsum('head', 'neck')
        # smooth vertex normals for offsetting shells (field normals, lightly relaxed so shells do not crinkle)
        self.Ns = M.smooth_attr(N, F, iters=2, lam=0.5)
        self.Ns /= np.maximum(np.linalg.norm(self.Ns, axis=1, keepdims=True), 1e-9)
        # cloth thickness relief where a joint folds (inner elbow, back of the knee): the shell would otherwise poke into the other segment
        self.relief = np.ones(len(V))
        for sd in (1, -1):
            j = P.joints(sd)
            for c, front in ((j['elbow'], -1.0), (j['knee'], 1.0)):
                d = np.linalg.norm(V - c, axis=1)
                inner = np.clip(front * N[:, 1] * 1.6 + 0.2, 0, 1)
                self.relief -= 0.55 * np.exp(-(d / 1.1) ** 2) * inner
        self.relief = np.clip(self.relief, 0.35, 1.0)
        # parameter along each limb (0 at the proximal joint, 1 at the distal end) for the vertices that belong to it
        self.arm_t, self.leg_t = {}, {}
        for sd in (1, -1):
            j = P.joints(sd)
            self.arm_t[sd] = self._param([j['shoulder'], j['elbow'], j['wrist'], j['hand_tip']], V)
            self.leg_t[sd] = self._param([j['hip'], j['knee'], j['ankle']], V)

    @staticmethod
    def _param(pts, V):
        """Arc-length fraction of the closest point on the polyline (0..1, clamped)."""
        pts = [np.asarray(p, float) for p in pts]
        seg = [pts[i + 1] - pts[i] for i in range(len(pts) - 1)]
        ln = np.array([np.linalg.norm(s) for s in seg])
        cum = np.concatenate([[0], np.cumsum(ln)])
        best = np.full(len(V), 1e9)
        out = np.zeros(len(V))
        for i, s in enumerate(seg):
            t = np.clip(((V - pts[i]) @ s) / (s @ s), 0, 1)
            d = np.linalg.norm(V - (pts[i] + t[:, None] * s), axis=1)
            m = d < best
            best[m] = d[m]
            out[m] = (cum[i] + t[m] * ln[i]) / cum[-1]
        return out

    def layer_at(self, pts):
        from scipy.spatial import cKDTree
        if self._kd is None:
            self._kd = cKDTree(self.V)
        return self.layer[self._kd.query(np.asarray(pts, float))[1]]

    @property
    def tree(self):
        if self._tree is None:
            self._tree = M.bvh(self.V, self.F)
        return self._tree

    def faces_of(self, vmask):
        return np.where(vmask[self.F].all(1))[0]

    def signed_distance(self, pts):
        return self.field.eval_points(pts)


def size_fn_for(P, scale=1.0):
    """Wanted mesh cell size at each vertex: fine on the face and hands, coarse on the trunk and legs (the field supplies the
    smooth normals, so flat-looking cells still shade round)."""
    k = P.s ** 0.6

    def fn(V):
        # cluster cell -> mean triangle edge is ~0.5 x cell
        c = np.full(len(V), 0.85 * k)
        hc = np.array([0, 0.2, P.chin + P.head_h * 0.5])
        dh = np.linalg.norm(V - hc, axis=1)
        hr = P.head_h * 0.72
        c = np.minimum(c, 0.27 * k + 0.25 * np.maximum(dh - hr, 0))
        face = (V[:, 1] < 0.1) & (V[:, 2] > P.chin - 0.5 * k) & (dh < hr * 1.15)
        c = np.where(face, np.minimum(c, 0.17 * k), c)
        for sd in (1, -1):
            j = P.joints(sd)
            dw = np.linalg.norm(V - (j['wrist'] * 0.6 + j['hand_tip'] * 0.4), axis=1)
            c = np.minimum(c, 0.16 * k + 0.25 * np.maximum(dw - 1.3, 0))
        if getattr(P, 'fine_scalp', False):          # tousled / spiky hair is sculpted from the scalp: the skull top needs the resolution
            c = np.where((V[:, 2] > P.chin + 2.0 * P.head_h / 3.3) & (dh < hr * 1.3), np.minimum(c, 0.16 * k), c)
        c = np.where((np.abs(V[:, 0]) > P.shoulder_x - 0.5) & (V[:, 2] > P.wrist_z - 0.5) & (V[:, 2] < P.shoulder + 1.0), np.minimum(c, 0.6 * k), c)
        c = np.where(V[:, 2] < P.lift + 2.0 * k, np.minimum(c, 0.4 * k), c)
        return c * scale

    return fn


_BODY_CACHE = {}


def build_body(ctx, scale=1.0, cache=False):
    P = ctx.P
    face = ctx.look.get('face', {})
    key = (repr(sorted((k, round(float(v), 4) if not isinstance(v, str) else v) for k, v in vars(P).items() if isinstance(v, (int, float, str)))),
           repr(sorted((k, v) for k, v in face.items() if k in ('nose', 'jaw', 'face_wide'))), scale)
    if cache and key in _BODY_CACHE:
        body = _BODY_CACHE[key]
        P.eye_c, P.mouth_c = body.P.eye_c, body.P.mouth_c
        ctx.body = body
        ctx.covered = np.zeros(len(body.V), bool)
        ctx.skin_cell = ctx.ramp('skin', 'skin', ctx.col('skin'))
        return body
    field = AN.build_field(P, face)
    eg = AN.eye_geom(P, face)
    P.eye_c = {sd: eg[sd]['c'] for sd in (1, -1)}
    HS = AN.HeadShape(P, face)
    u = HS.u
    mz = HS.z('mouth')
    P.mouth_c = np.array([0.0, HS.face_y(0.0, mz) + 0.1, mz])
    V, F, N = M.make_surface(field, GRID_LO, GRID_HI, VOXEL, size_fn_for(P, scale), log=ctx.log)
    w = SK.body_weights(field, P, V, F)
    ctx.body = BodyMesh(P, field, V, F, N, w)
    ctx.covered = np.zeros(len(V), bool)
    ctx.skin_cell = ctx.ramp('skin', 'skin', ctx.col('skin'))
    if cache:
        _BODY_CACHE[key] = ctx.body
    return ctx.body


def skin_part(ctx, drop_covered=True, name='body', z_range=None):
    """The exposed skin as one Part (faces fully under clothing are dropped).  z_range=(lo, hi) keeps only faces whose centroid
    height is inside it -- the modular player splits the body at the neck this way (both halves share the cut vertices)."""
    B = ctx.body
    keep = np.ones(len(B.F), bool)
    if z_range is not None:
        zc = B.V[B.F][:, :, 2].mean(1)
        keep &= (zc >= z_range[0]) & (zc < z_range[1])
    if drop_covered:
        keep &= ~ctx.covered[B.F].all(1)
    F = B.F[keep]
    used = np.zeros(len(B.V), bool)
    used[F.reshape(-1)] = True
    remap = -np.ones(len(B.V), np.int64)
    remap[used] = np.arange(used.sum())
    p = G.Part(name, B.V[used], remap[F], ctx.skin_cell, g=skin_flush(ctx, B.V[used]))
    p.w = {b: a[used] for b, a in B.w.items()}
    p.N = B.N[used]
    p.src = np.where(used)[0]
    return p


def skin_flush(ctx, V):
    """0..1 warmth of the skin: ears, nose, cheeks, knuckles, elbows and knees are pinker than the rest."""
    P = ctx.P
    g = np.full(len(V), 0.3)
    u = P.head_h / 3.3
    hc = np.array([0, 0.0, P.chin + 1.7 * u])
    front = V[:, 1] < 0.0
    d = np.linalg.norm((V - hc) * [1, 1.0, 1.4], axis=1)
    g = np.where(d < 1.9 * u, 0.55, g)
    for sd in (1, -1):
        for c in (np.array([sd * 0.72 * u, -1.0 * u, P.chin + 1.5 * u]),):
            g += 0.25 * np.exp(-(np.linalg.norm(V - c, axis=1) / (0.5 * u)) ** 2)
        j = P.joints(sd)
        for c in (j['elbow'], j['knee'], j['hand_tip']):
            g += 0.2 * np.exp(-(np.linalg.norm(V - c, axis=1) / 0.5) ** 2)
    return np.clip(g, 0, 1)

"""Geometry kit for the chibi character generator (pure numpy, no bpy).

Everything is a `Part`: an indexed triangle mesh + per-vertex attributes:
  * g      gradient parameter 0..1 that the part's texture cell maps along its V axis
  * uv     optional explicit cell-local uv (0..1) for decal / detail cells (eyes, emblems)
  * w      {bone: per-vertex weight array}  (skin weights, blended later to <= 4 influences)
Parts are built from a handful of parametric-surface primitives (loft along a path with
elliptical sections, lathe, ellipsoid, thickened open surface) which all produce clean quad
grids that are welded and triangulated.

Conventions: Blender space, Z up, the figure faces -Y, +X is the character's LEFT.
"""
import math

import numpy as np


# ----------------------------------------------------------------------------- small maths
def nrm(v, eps=1e-9):
    v = np.asarray(v, float)
    if v.ndim == 1:
        return v / max(np.linalg.norm(v), eps)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), eps)


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def rot_x(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot_euler(x=0.0, y=0.0, z=0.0):
    """Rotation applied X then Y then Z (degrees)."""
    return rot_z(z) @ rot_y(y) @ rot_x(x)


def align_z(direction):
    """Rotation matrix taking +Z onto `direction`."""
    d = nrm(direction)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, d)
    c = float(np.dot(z, d))
    if np.linalg.norm(v) < 1e-8:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


# ----------------------------------------------------------------------------- Part
class Part:
    def __init__(self, name, V, F, cell='skin', g=None, uv=None, w=None, bone=None, tag=''):
        self.name = name
        self.V = np.asarray(V, float).reshape(-1, 3)
        self.F = np.asarray(F, np.int64).reshape(-1, 3)
        n = len(self.V)
        self.cell = cell
        self.g = np.full(n, 0.5) if g is None else np.asarray(g, float)
        self.uv = uv if uv is None else np.asarray(uv, float)
        self.w = {} if w is None else dict(w)
        if bone is not None:
            self.w = {bone: np.ones(n)}
        self.tag = tag
        self.ao_gain = 1.0          # 0 disables baked AO for this part (decals)

    # -- transforms
    def transform(self, M=None, t=None):
        if M is not None:
            self.V = self.V @ np.asarray(M).T
        if t is not None:
            self.V = self.V + np.asarray(t, float)
        return self

    def copy(self, name=None):
        p = Part(name or self.name, self.V.copy(), self.F.copy(), self.cell, self.g.copy(),
                 None if self.uv is None else self.uv.copy(), {k: v.copy() for k, v in self.w.items()}, tag=self.tag)
        p.ao_gain = self.ao_gain
        return p

    def mirror_x(self, name=None):
        p = self.copy(name)
        p.V[:, 0] *= -1
        p.F = p.F[:, ::-1].copy()
        return p

    def set_bone(self, bone):
        self.w = {bone: np.ones(len(self.V))}
        return self

    def set_cell(self, cell):
        self.cell = cell
        return self

    def set_g(self, g):
        self.g = np.broadcast_to(np.asarray(g, float), (len(self.V),)).copy()
        return self


def merge_parts(parts, name, cell=None):
    """Concatenate parts that share a cell (weights merged)."""
    parts = [p for p in parts if p is not None and len(p.V)]
    if not parts:
        return None
    V, F, g, uv = [], [], [], []
    bones = set()
    for p in parts:
        bones |= set(p.w)
    off = 0
    W = {b: [] for b in bones}
    for p in parts:
        V.append(p.V)
        F.append(p.F + off)
        off += len(p.V)
        g.append(p.g)
        if p.uv is not None:
            uv.append(p.uv)
        for b in bones:
            W[b].append(p.w.get(b, np.zeros(len(p.V))))
    out = Part(name, np.vstack(V), np.vstack(F), cell or parts[0].cell, np.concatenate(g),
               np.vstack(uv) if len(uv) == len(parts) else None,
               {b: np.concatenate(v) for b, v in W.items()})
    out.ao_gain = parts[0].ao_gain
    return out


def weld(V, F, extra=(), tol=1e-4):
    """Merge coincident vertices; drop degenerate triangles.  `extra` arrays follow the first
    surviving vertex of each merged group.  Returns V, F, [extra...]."""
    key = np.round(V / tol).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    Vn = V[idx]
    Fn = inv[F]
    ok = (Fn[:, 0] != Fn[:, 1]) & (Fn[:, 1] != Fn[:, 2]) & (Fn[:, 0] != Fn[:, 2])
    Fn = Fn[ok]
    return Vn, Fn, [e[idx] for e in extra]


def orient_outward(V, F):
    """Flip triangle winding if the signed volume is negative (closed surfaces)."""
    v0, v1, v2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    vol = np.einsum('ij,ij->i', v0, np.cross(v1, v2)).sum()
    return F[:, ::-1].copy() if vol < 0 else F


def vertex_normals(V, F):
    v0, v1, v2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)   # area weighted
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return nrm(N)


# ----------------------------------------------------------------------------- grid surfaces
def grid_tris(nu, nv, wrap_u=False, wrap_v=False):
    """Triangles of an (nu x nv) vertex grid indexed iu*nv+iv."""
    iu = np.arange(nu if wrap_u else nu - 1)
    iv = np.arange(nv if wrap_v else nv - 1)
    IU, IV = np.meshgrid(iu, iv, indexing='ij')
    a = IU * nv + IV
    b = ((IU + 1) % nu) * nv + IV
    c = ((IU + 1) % nu) * nv + (IV + 1) % nv
    d = IU * nv + (IV + 1) % nv
    a, b, c, d = (x.reshape(-1) for x in (a, b, c, d))
    return np.vstack([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])


def _finish(name, V, F, cell, g, extra_weld=(), orient=True, tol=1e-4):
    extras = [g] + list(extra_weld)
    V2, F2, ex = weld(V, F, extras, tol)
    if orient:
        F2 = orient_outward(V2, F2)
    p = Part(name, V2, F2, cell, ex[0])
    return p, ex[1:]


def surface_grid(P, cell='skin', name='surf', g=None, wrap_u=False, wrap_v=False, orient=True, uv=None,
                 outward_from=None):
    """A closed/open grid P (nu, nv, 3) -> Part.  uv: optional (nu, nv, 2) explicit cell uv.
    outward_from: point; for OPEN surfaces flips winding so normals face away from it."""
    nu, nv = P.shape[:2]
    F = grid_tris(nu, nv, wrap_u, wrap_v)
    if g is None:
        g = np.tile(np.linspace(0, 1, nv)[None, :], (nu, 1)).reshape(-1)
    extra = [] if uv is None else [np.asarray(uv, float).reshape(-1, 2)]
    p, ex = _finish(name, P.reshape(-1, 3), F, cell, np.asarray(g).reshape(-1), extra, orient=orient and outward_from is None)
    if uv is not None:
        p.uv = ex[0]
    if outward_from is not None:
        v0, v1, v2 = p.V[p.F[:, 0]], p.V[p.F[:, 1]], p.V[p.F[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        cen = (v0 + v1 + v2) / 3.0 - np.asarray(outward_from, float)
        if np.einsum('ij,ij->i', fn, cen).sum() < 0:
            p.F = p.F[:, ::-1].copy()
    return p


def _superellipse(a, e):
    c, s = np.cos(a), np.sin(a)
    if e == 2.0:
        return c, s
    p = 2.0 / e
    return np.sign(c) * np.abs(c) ** p, np.sign(s) * np.abs(s) ** p


def frames_along(P, ref=(1.0, 0.0, 0.0)):
    """Rotation-minimising frames along a polyline: tangents T, normals N, binormals B."""
    P = np.asarray(P, float)
    T = np.gradient(P, axis=0)
    T = nrm(T)
    N = np.zeros_like(T)
    ref = np.asarray(ref, float)
    n = ref - T[0] * np.dot(ref, T[0])
    if np.linalg.norm(n) < 1e-6:
        alt = np.array([0.0, 1.0, 0.0])
        n = alt - T[0] * np.dot(alt, T[0])
    N[0] = nrm(n)
    for i in range(1, len(P)):
        n = N[i - 1] - T[i] * np.dot(N[i - 1], T[i])
        if np.linalg.norm(n) < 1e-6:
            n = ref - T[i] * np.dot(ref, T[i])
        N[i] = nrm(n)
    B = np.cross(T, N)
    return T, N, B


def resample(pts, n):
    """n points evenly spread by arc length along a polyline; returns pts, t (0..1 arc)."""
    pts = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    tt = np.linspace(0, s[-1], n)
    out = np.stack([np.interp(tt, s, pts[:, k]) for k in range(pts.shape[1])], 1)
    return out, tt / max(s[-1], 1e-9)


def catmull(pts, n, closed=False):
    """Smooth curve through pts (centripetal-ish Catmull-Rom), n samples."""
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return resample(pts, n)[0]
    P = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    segs = len(pts) - 1
    out = []
    for i in range(n):
        u = i / (n - 1) * segs
        k = min(int(u), segs - 1)
        t = u - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                          (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)


def loft(path, radii, seg=14, cell='skin', name='loft', ref=(1.0, 0.0, 0.0), caps=(0.9, 0.9),
         e=2.0, mod=None, g=None, path_n=None, twist=0.0, rot=0.0):
    """Sweep an elliptical section along `path` (k,3).  radii: (k,2) or (k,) or scalar pair;
    (rx across the frame normal N, ry across the binormal B).  caps: rounded-end factor per
    end (0 => flat disc, None => open).  e: super-ellipse exponent (scalar or per ring)."""
    path = np.asarray(path, float)
    k = len(path)
    radii = np.asarray(radii, float)
    if radii.ndim == 0:
        radii = np.full((k, 2), float(radii))
    elif radii.ndim == 1 and len(radii) == 2 and k != 2:
        radii = np.tile(radii, (k, 1))
    elif radii.ndim == 1:
        radii = np.stack([radii, radii], 1)
    ee = np.broadcast_to(np.asarray(e, float), (k,))
    T, N, B = frames_along(path, ref)
    rings = []
    gs = []
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    arc = arc / max(arc[-1], 1e-9)
    a = np.linspace(0, 2 * math.pi, seg, endpoint=False) + math.radians(rot)

    def ring(i, scale=1.0, shift=0.0, tw=0.0):
        aa = a + tw
        rx, ry = radii[i]
        cs, sn = _superellipse(aa, ee[i])
        pts = path[i] + T[i] * shift + (N[i][None, :] * (rx * scale * cs)[:, None] +
                                          B[i][None, :] * (ry * scale * sn)[:, None])
        if mod is not None:
            f = mod(i, aa)
            pts = path[i] + T[i] * shift + (pts - path[i] - T[i] * shift) * np.asarray(f)[:, None]
        return pts

    if caps[0] is not None and caps[0] > 0:
        r0 = float(np.mean(radii[0])) * caps[0]
        for ph in (62, 30):
            rings.append(ring(0, math.cos(math.radians(ph)), -r0 * math.sin(math.radians(ph))))
            gs.append(0.0)
    for i in range(k):
        rings.append(ring(i, tw=twist * arc[i]))
        gs.append(arc[i])
    if caps[1] is not None and caps[1] > 0:
        r1 = float(np.mean(radii[-1])) * caps[1]
        for ph in (30, 62):
            rings.append(ring(k - 1, math.cos(math.radians(ph)), r1 * math.sin(math.radians(ph))))
            gs.append(1.0)
    pole0 = pole1 = None
    if caps[0] is not None:
        r0 = float(np.mean(radii[0])) * (caps[0] if caps[0] > 0 else 0.0)
        pole0 = path[0] - T[0] * r0
    if caps[1] is not None:
        r1 = float(np.mean(radii[-1])) * (caps[1] if caps[1] > 0 else 0.0)
        pole1 = path[-1] + T[-1] * r1
    R = np.array(rings)  # (nr, seg, 3)
    nr = len(R)
    verts = [R.reshape(-1, 3)]
    gg = [np.repeat(gs, seg)]
    F = [grid_tris(nr, seg, wrap_u=False, wrap_v=True)]
    base = nr * seg
    if pole0 is not None:
        verts.append(pole0[None, :])
        gg.append([0.0])
        i0 = base
        base += 1
        F.append(np.array([[i0, k2, (k2 + 1) % seg] for k2 in range(seg)]))
    if pole1 is not None:
        verts.append(pole1[None, :])
        gg.append([1.0])
        i1 = base
        last = (nr - 1) * seg
        F.append(np.array([[i1, last + (k2 + 1) % seg, last + k2] for k2 in range(seg)]))
    Vv = np.vstack(verts)
    Ff = np.vstack(F)
    gv = np.concatenate([np.asarray(x, float).reshape(-1) for x in gg])
    if g is not None:
        gfun = g
        gv = np.asarray(gfun(Vv), float) if callable(gfun) else np.asarray(gfun, float)
    p, _ = _finish(name, Vv, Ff, cell, gv)
    return p


def lathe(profile, seg=20, center=(0, 0, 0), scale=(1.0, 1.0), cell='skin', name='lathe', wobble=None,
          g=None, rot=0.0, close=True):
    """Surface of revolution about +Z. profile: [(r, z), ...] bottom -> top (r may be 0 at
    the ends to close).  wobble(a, z) -> radius factor."""
    prof = np.asarray(profile, float)
    a = np.linspace(0, 2 * math.pi, seg, endpoint=False) + math.radians(rot)
    r = prof[:, 0][None, :].repeat(seg, 0)
    z = prof[:, 1][None, :].repeat(seg, 0)
    ca, sa = np.cos(a)[:, None], np.sin(a)[:, None]
    fac = 1.0 if wobble is None else wobble(a[:, None] + 0 * z, z)
    X = r * fac * ca * scale[0] + center[0]
    Y = r * fac * sa * scale[1] + center[1]
    Z = z + center[2]
    P = np.stack([X, Y, Z], -1)
    if close:
        # flat caps if the profile does not end on the axis
        pass
    gv = np.tile(np.linspace(0, 1, len(prof))[None, :], (seg, 1)).reshape(-1) if g is None else g
    nu, nv = P.shape[:2]
    F = grid_tris(nu, nv, wrap_u=True, wrap_v=False)
    V = P.reshape(-1, 3)
    extra = []
    if close:
        for end in (0, nv - 1):
            if prof[end, 0] > 1e-6:
                cpt = np.array([center[0], center[1], prof[end, 1] + center[2]])
                idx = len(V)
                V = np.vstack([V, cpt])
                gv = np.concatenate([np.asarray(gv, float).reshape(-1), [end / max(nv - 1, 1)]])
                ring_i = [iu * nv + end for iu in range(nu)]
                for i in range(nu):
                    j = (i + 1) % nu
                    extra.append([idx, ring_i[j], ring_i[i]] if end == 0 else [idx, ring_i[i], ring_i[j]])
        if extra:
            F = np.vstack([F, np.array(extra)])
    p, _ = _finish(name, V, F, cell, np.asarray(gv, float).reshape(-1))
    return p


def ellipsoid(center, radii, seg=16, rings=10, cell='skin', name='ell', rot=None, g=None, cut=None):
    """UV ellipsoid; rot = 3x3 matrix. cut = (zmin_frac, zmax_frac) trims poles (open)."""
    rx, ry, rz = radii
    th = np.linspace(0, math.pi, rings + 1)
    prof = np.stack([np.sin(th), -np.cos(th)], 1)
    p = lathe(prof * np.array([1.0, 1.0]), seg=seg, cell=cell, name=name)
    V = p.V * np.array([rx, ry, rz])
    if rot is not None:
        V = V @ np.asarray(rot).T
    p.V = V + np.asarray(center, float)
    if g is not None:
        p.g = np.asarray(g(p.V), float) if callable(g) else np.broadcast_to(g, (len(p.V),)).copy()
    return p


def sphere_dir_grid(seg, rings):
    """Direction unit vectors on a sphere as (seg, rings+1, 3); ring 0 = +Z pole."""
    th = np.linspace(0, math.pi, rings + 1)
    ph = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    TH, PH = np.meshgrid(ph, th, indexing='ij')[1], np.meshgrid(ph, th, indexing='ij')[0]
    return np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], -1), TH, PH


def solid_surface(P, thickness, cell='hair', name='sheet', wrap_u=False, flip=False, g=None,
                  offset=0.0, thick_fn=None, outward_from=None, inner='full'):
    """Give an open parametric surface P (nu, nv, 3) real thickness.  Outward direction is set by
    the (u x v) normal (`flip` reverses it) or `outward_from`.  offset shifts the sheet along the
    normal (fraction of thickness: 0.5 puts the inner skin on P).
    inner='full': outer + inner skins + stitched edges (visible from both sides);
    inner='rim' : outer skin + a skirt of edge vertices only (shells that sit on the skull)."""
    P = np.asarray(P, float)
    nu, nv = P.shape[:2]
    du = np.gradient(P, axis=0)
    if wrap_u:
        du = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    dv = np.gradient(P, axis=1)
    Nn = nrm(np.cross(du, dv))
    if outward_from is not None:
        if np.einsum('ijk,ijk->', Nn, P - np.asarray(outward_from, float)) < 0:
            Nn = -Nn
    if flip:
        Nn = -Nn
    th = np.full((nu, nv), float(thickness)) if thick_fn is None else np.asarray(thick_fn(P), float)
    if th.ndim == 0:
        th = np.full((nu, nv), float(th))
    off = offset * th
    outer = P + Nn * (th * 0.5 + off)[..., None]
    inner_p = P - Nn * (th * 0.5 - off)[..., None]
    n1 = nu * nv
    idx = np.arange(n1).reshape(nu, nv)
    if g is None:
        gv = np.tile(np.linspace(0, 1, nv)[None, :], (nu, 1)).reshape(-1)
    else:
        gv = np.asarray(g, float).reshape(-1)
    edges = [idx[:, 0], idx[:, -1]]
    if wrap_u:
        edges = [np.append(e, e[0]) for e in edges]
    else:
        edges += [idx[0, :], idx[-1, :]]
    Fo = grid_tris(nu, nv, wrap_u=wrap_u, wrap_v=False)
    centre = outer.reshape(-1, 3).mean(0)
    if inner == 'rim':
        rim_ids = {}
        Vr = []
        for e in edges:
            for k in e:
                if k not in rim_ids:
                    rim_ids[k] = n1 + len(Vr)
                    Vr.append(inner_p.reshape(-1, 3)[k])
        V = np.vstack([outer.reshape(-1, 3), np.array(Vr)])
        gg = np.concatenate([gv, np.array([gv[k] for k in rim_ids])])
        F = [Fo]
        for e in edges:
            q = []
            for a, b in zip(e[:-1], e[1:]):
                q.append([a, rim_ids[a], rim_ids[b]])
                q.append([a, rim_ids[b], b])
            q = np.array(q)
            # winding: strip normal should point away from the patch centre
            v0, v1, v2 = V[q[:, 0]], V[q[:, 1]], V[q[:, 2]]
            fn = np.cross(v1 - v0, v2 - v0)
            if np.einsum('ij,ij->i', fn, (v0 + v1 + v2) / 3 - centre).sum() < 0:
                q = q[:, ::-1]
            F.append(q)
        Vw, Fw, ex = weld(V, np.vstack(F), [gg], 1e-5)
        if outward_from is not None:
            v0, v1, v2 = Vw[Fw[:, 0]], Vw[Fw[:, 1]], Vw[Fw[:, 2]]
            fn = np.cross(v1 - v0, v2 - v0)
            if np.einsum('ij,ij->i', fn, (v0 + v1 + v2) / 3 - np.asarray(outward_from, float)).sum() < 0:
                Fw = Fw[:, ::-1].copy()
        return Part(name, Vw, Fw, cell, ex[0])
    V = np.vstack([outer.reshape(-1, 3), inner_p.reshape(-1, 3)])
    Fi = Fo[:, ::-1] + n1
    F = [Fo, Fi]
    for e in edges:
        q = []
        for a, b in zip(e[:-1], e[1:]):
            q.append([a, a + n1, b + n1])
            q.append([a, b + n1, b])
        F.append(np.array(q))
    gg = np.concatenate([gv, gv])
    Vw, Fw, ex = weld(V, np.vstack(F), [gg], 1e-5)
    Fw = orient_outward(Vw, Fw)
    return Part(name, Vw, Fw, cell, ex[0])


def box_round(center, half, r=0.3, seg=6, cell='accent', name='box', rot=None):
    """Rounded box via a superellipsoid loft-free construction (lathe-free): use an
    ellipsoid with high exponent, cheap and smooth."""
    return superellipsoid(center, half, 6.0, seg=seg * 3, rings=seg * 2, cell=cell, name=name, rot=rot)


def superellipsoid(center, radii, e=4.0, seg=16, rings=10, cell='accent', name='sup', rot=None, g=None, e2=None):
    """Superellipsoid |x|^e+|y|^e+|z|^e' ... (e=2 ellipsoid, bigger -> boxier)."""
    e2 = e if e2 is None else e2
    th = np.linspace(0, math.pi, rings + 1)
    ph = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    PH, TH = np.meshgrid(ph, th, indexing='ij')
    c, s = np.cos(TH), np.sin(TH)
    cp, sp = np.cos(PH), np.sin(PH)
    pw = lambda x, ex: np.sign(x) * np.abs(x) ** (2.0 / ex)
    X = pw(s, e2) * pw(cp, e)
    Y = pw(s, e2) * pw(sp, e)
    Z = pw(-c, e2)
    P = np.stack([X * radii[0], Y * radii[1], Z * radii[2]], -1)
    if rot is not None:
        P = P @ np.asarray(rot).T
    P = P + np.asarray(center, float)
    p = surface_grid(P, cell, name, g=None if g is None else g(P.reshape(-1, 3)), wrap_u=True)
    return p


# ----------------------------------------------------------------------------- weights
def chain_weights(V, points, bones, halfw):
    """Blend weights of vertices V along a bone chain.
    points: len(bones)+1 joint positions (bone i spans points[i] -> points[i+1]);
    halfw: blend half-width at each internal joint (len(bones)-1, or scalar).
    Returns {bone: weight array}."""
    V = np.asarray(V, float)
    pts = np.asarray(points, float)
    nb = len(bones)
    seglen = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seglen)])
    # closest point on polyline -> arc-length parameter s
    best_d = np.full(len(V), 1e18)
    s = np.zeros(len(V))
    for i in range(nb):
        a, b = pts[i], pts[i + 1]
        ab = b - a
        L2 = max(np.dot(ab, ab), 1e-12)
        t = np.clip(((V - a) @ ab) / L2, 0, 1)
        q = a + t[:, None] * ab
        d = np.linalg.norm(V - q, axis=1)
        better = d < best_d
        best_d = np.where(better, d, best_d)
        s = np.where(better, cum[i] + t * seglen[i], s)
    hw = np.broadcast_to(np.asarray(halfw, float), (max(nb - 1, 1),))
    tj = [np.ones(len(V))]                # fraction "past" joint j (j=0 sentinel: always 1)
    for j in range(1, nb):
        tj.append(smoothstep(cum[j] - hw[j - 1], cum[j] + hw[j - 1], s))
    tj.append(np.zeros(len(V)))
    out = {}
    for i in range(nb):
        out[bones[i]] = tj[i] - tj[i + 1]
    return out


def add_weights(part, wdict, mult=None):
    part.w = {k: (np.asarray(v) if mult is None else np.asarray(v) * mult) for k, v in wdict.items()}
    return part


def finalize_weights(part, bone_index, max_inf=4, prune=0.02):
    """-> (joints (n,4) int, weights (n,4) float) top-N normalised."""
    n = len(part.V)
    names = [b for b in part.w if b in bone_index]
    if not names:
        raise ValueError('part %s has no valid skin weights' % part.name)
    M = np.stack([part.w[b] for b in names], 1)          # (n, k)
    idx = np.array([bone_index[b] for b in names])
    order = np.argsort(-M, axis=1)[:, :max_inf]
    Wt = np.take_along_axis(M, order, 1)
    Jt = idx[order]
    Wt = np.where(Wt < prune, 0.0, Wt)
    sm = Wt.sum(1, keepdims=True)
    fallback = sm[:, 0] < 1e-6
    Wt[fallback, 0] = 1.0
    sm = Wt.sum(1, keepdims=True)
    Wt = Wt / sm
    if Wt.shape[1] < max_inf:
        pad = max_inf - Wt.shape[1]
        Wt = np.pad(Wt, ((0, 0), (0, pad)))
        Jt = np.pad(Jt, ((0, 0), (0, pad)))
    return Jt.astype(np.int64), Wt


# ----------------------------------------------------------------------------- baked AO
def bake_ao(V, F, normals, samples=20, max_dist=2.6, seed=3, bias=0.03, skip_mask=None):
    """Hemisphere AO per vertex using mathutils BVH (bpy)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromPolygons([tuple(map(float, v)) for v in V], [tuple(int(i) for i in f) for f in F])
    rng = np.random.default_rng(seed)
    # cosine-weighted hemisphere samples in tangent space
    u1 = (np.arange(samples) + rng.random(samples)) / samples
    u2 = rng.random(samples)
    r = np.sqrt(u1)
    th = 2 * math.pi * u2
    local = np.stack([r * np.cos(th), r * np.sin(th), np.sqrt(1 - u1)], 1)
    ao = np.ones(len(V))
    for i in range(len(V)):
        n = normals[i]
        t = np.cross(n, [0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0])
        t = nrm(t)
        b = np.cross(n, t)
        dirs = local[:, 0:1] * t + local[:, 1:2] * b + local[:, 2:3] * n
        o = Vector(V[i] + n * bias)
        occ = 0.0
        for d in dirs:
            hit = tree.ray_cast(o, Vector(d), max_dist)
            if hit[0] is not None:
                occ += 1.0 - 0.5 * (hit[3] / max_dist)
        ao[i] = 1.0 - occ / samples
    return ao

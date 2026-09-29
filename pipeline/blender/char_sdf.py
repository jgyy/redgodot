"""Signed-distance kit for the realistic character bodies (numpy + scikit-image, no bpy).

The whole body (head, neck, torso, limbs, hands, feet) is ONE implicit surface: a list of primitives
combined with smooth unions / subtractions.  Because there is a single field there are no seams between
neck, shoulders, arms and hands -- the joins are blended like clay.  The field is turned into a welded
triangle mesh with marching cubes; the mesh is decimated in Blender and every vertex is then projected
back onto the exact field, so the low-poly mesh keeps sculpted detail (lips, eyelids, knuckles) that is
finer than the voxel grid.  The same field answers "how far is this point from the skin" for the clothing,
hair and the clipping test.

Conventions: Blender space (Z up, figure faces -Y, +X is the character's left), units = sprite rows
(a 1.5 m figure is ~24 rows).
"""
import numpy as np


# ----------------------------------------------------------------------------- helpers
def _len(v):
    return np.sqrt((v * v).sum(-1))


def smin(a, b, k):
    """Polynomial smooth minimum (union)."""
    if k <= 1e-9:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    if k <= 1e-9:
        return np.maximum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k * 0.25


def rot_from_axes(x, y, z):
    return np.stack([x, y, z], 1)      # columns are the local axes in world space


def frame_from_z(z_dir, ref=(0.0, -1.0, 0.0)):
    """Orthonormal frame (3x3, columns x,y,z) whose z axis is z_dir; y is as close to `ref` as possible."""
    z = np.asarray(z_dir, float)
    z = z / np.linalg.norm(z)
    r = np.asarray(ref, float)
    x = np.cross(r, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross([1.0, 0, 0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


# ----------------------------------------------------------------------------- primitives
class Prim:
    lo = hi = None

    def bbox(self):
        return self.lo, self.hi

    def d(self, p):
        raise NotImplementedError


class RoundCone(Prim):
    """Capsule with different end radii (exact SDF, iq)."""

    def __init__(self, a, b, ra, rb):
        self.a, self.b = np.asarray(a, float), np.asarray(b, float)
        self.ra, self.rb = float(ra), float(rb)
        m = max(ra, rb)
        self.lo = np.minimum(self.a, self.b) - m
        self.hi = np.maximum(self.a, self.b) + m
        ba = self.b - self.a
        self.l2 = float(ba @ ba)
        self.rr = self.ra - self.rb
        self.a2 = self.l2 - self.rr * self.rr
        self.il2 = 1.0 / max(self.l2, 1e-12)
        self.ba = ba

    def d(self, p):
        pa = p - self.a
        y = pa @ self.ba
        z = y - self.l2
        w = pa * self.l2 - np.outer(y, self.ba)
        x2 = (w * w).sum(1)
        y2 = y * y * self.l2
        z2 = z * z * self.l2
        rr = self.rr
        k = np.sign(rr) * rr * rr * x2
        cap_b = np.sign(z) * self.a2 * z2 > k
        cap_a = np.sign(y) * self.a2 * y2 < k
        d_b = np.sqrt(x2 + z2) * self.il2 - self.rb
        d_a = np.sqrt(x2 + y2) * self.il2 - self.ra
        d_m = (np.sqrt(x2 * self.a2 * self.il2) + y * rr) * self.il2 - self.ra
        return np.where(cap_b, d_b, np.where(cap_a, d_a, d_m))


class Ellipsoid(Prim):
    def __init__(self, c, r, R=None):
        self.c = np.asarray(c, float)
        self.r = np.asarray(r, float)
        self.R = None if R is None else np.asarray(R, float)
        m = float(self.r.max())
        self.lo = self.c - m
        self.hi = self.c + m

    def d(self, p):
        q = p - self.c
        if self.R is not None:
            q = q @ self.R          # world -> local (R columns are local axes)
        k0 = _len(q / self.r)
        k1 = _len(q / (self.r * self.r))
        return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -float(self.r.min()))


class Box(Prim):
    """Rounded box, optionally rotated (R columns = local axes)."""

    def __init__(self, c, half, rnd=0.0, R=None):
        self.c = np.asarray(c, float)
        self.h = np.asarray(half, float)
        self.rnd = float(rnd)
        self.R = None if R is None else np.asarray(R, float)
        m = float(np.linalg.norm(self.h)) + rnd
        self.lo = self.c - m
        self.hi = self.c + m

    def d(self, p):
        q = p - self.c
        if self.R is not None:
            q = q @ self.R
        e = np.abs(q) - (self.h - self.rnd)
        out = _len(np.maximum(e, 0.0))
        ins = np.minimum(np.maximum(np.maximum(e[:, 0], e[:, 1]), e[:, 2]), 0.0)
        return out + ins - self.rnd


def smooth_profile(prof, step=0.08):
    """Resample station rows with Catmull-Rom so the sections vary smoothly (no facet bands between stations)."""
    t = prof[:, 0]
    n = max(int((t[-1] - t[0]) / step), 2) + 1
    tt = np.linspace(t[0], t[-1], n)
    out = np.zeros((n, prof.shape[1]))
    out[:, 0] = tt
    idx = np.clip(np.searchsorted(t, tt, side='right') - 1, 0, len(t) - 2)
    for c in range(1, prof.shape[1]):
        y = prof[:, c]
        m = np.zeros(len(t))
        m[1:-1] = (y[2:] - y[:-2]) / (t[2:] - t[:-2])
        m[0] = (y[1] - y[0]) / (t[1] - t[0])
        m[-1] = (y[-1] - y[-2]) / (t[-1] - t[-2])
        h = t[idx + 1] - t[idx]
        u = (tt - t[idx]) / h
        h00 = 2 * u ** 3 - 3 * u ** 2 + 1
        h10 = u ** 3 - 2 * u ** 2 + u
        h01 = -2 * u ** 3 + 3 * u ** 2
        h11 = u ** 3 - u ** 2
        out[:, c] = h00 * y[idx] + h10 * h * m[idx] + h01 * y[idx + 1] + h11 * h * m[idx + 1]
    return out


class Stack(Prim):
    """Elliptical loft: cross-sections (ellipse) at stations along an axis.

    axis = 'z' (torso) or 'y' (foot).  `prof` rows: (t, half_a, half_b, off_a, off_b) where a, b are the two
    other axes in (x, y) for axis z and (x, z) for axis y.  Ends are rounded by `cap`.
    """

    def __init__(self, axis, prof, cap=0.5, expo=2.0):
        self.axis = axis
        self.prof = np.asarray(prof, float)
        self.prof = smooth_profile(self.prof[np.argsort(self.prof[:, 0])])
        self.cap = cap
        self.expo = expo
        t = self.prof[:, 0]
        self.t0, self.t1 = t.min(), t.max()
        ma = (np.abs(self.prof[:, 3]) + self.prof[:, 1]).max()
        mb = (np.abs(self.prof[:, 4]) + self.prof[:, 2]).max()
        if axis == 'z':
            self.lo = np.array([-ma, -mb, self.t0 - cap])
            self.hi = np.array([ma, mb, self.t1 + cap])
        else:
            self.lo = np.array([-ma, self.t0 - cap, -mb])
            self.hi = np.array([ma, self.t1 + cap, mb])

    def d(self, p):
        if self.axis == 'z':
            a, b, t = p[:, 0], p[:, 1], p[:, 2]
        else:
            a, b, t = p[:, 0], p[:, 2], p[:, 1]
        tt = np.clip(t, self.t0, self.t1)
        pr = self.prof
        ha = np.interp(tt, pr[:, 0], pr[:, 1])
        hb = np.interp(tt, pr[:, 0], pr[:, 2])
        oa = np.interp(tt, pr[:, 0], pr[:, 3])
        ob = np.interp(tt, pr[:, 0], pr[:, 4])
        qa, qb = (a - oa) / ha, (b - ob) / hb
        if self.expo == 2.0:
            e = np.sqrt(qa * qa + qb * qb)
        else:
            e = (np.abs(qa) ** self.expo + np.abs(qb) ** self.expo) ** (1.0 / self.expo)
        dxy = (e - 1.0) * np.minimum(ha, hb) * 0.9
        # rounded ends: distance beyond the last station
        dz = np.maximum(self.t0 - t, t - self.t1)      # > 0 beyond either end
        return np.where(dz > 0, np.sqrt(np.maximum(dxy + self.cap, 0.0) ** 2 + dz ** 2) - self.cap, dxy)


class Plane(Prim):
    """Half space  n . (p - c) < 0  is inside (used for flat soles)."""

    def __init__(self, c, n, lo, hi):
        self.c = np.asarray(c, float)
        n = np.asarray(n, float)
        self.n = n / np.linalg.norm(n)
        self.lo, self.hi = np.asarray(lo, float), np.asarray(hi, float)

    def d(self, p):
        return (p - self.c) @ self.n


# ----------------------------------------------------------------------------- field
class Field:
    """Ordered list of (prim, mode, k).  mode: 'add' (smooth union), 'sub' (smooth subtract), 'cut' (intersect with -prim, hard)."""

    def __init__(self):
        self.ops = []
        self.tags = {}

    def add(self, prim, k=0.2, tag=None):
        self.ops.append((prim, 'add', k))
        self.tags[len(self.ops) - 1] = tag or self.cur_tag
        return prim

    cur_tag = None

    def tag_dist(self, pts, tag):
        """Raw distance to the primitives owned by one tag (negative inside)."""
        pts = np.asarray(pts, float).reshape(-1, 3)
        out = np.full(len(pts), 9.0)
        for i, (prim, mode, k) in enumerate(self.ops):
            if mode != 'add' or self.tags.get(i) != tag:
                continue
            lo, hi = prim.bbox()
            sel = np.where(((pts >= lo - 2.0) & (pts <= hi + 2.0)).all(1))[0]
            if len(sel):
                out[sel] = np.minimum(out[sel], prim.d(pts[sel]))
        return out

    def tag_dists(self, pts):
        """Per-tag minimum of the raw primitive distances (used for skin weights): {tag: (n,) array}."""
        pts = np.asarray(pts, float).reshape(-1, 3)
        out = {}
        for i, (prim, mode, k) in enumerate(self.ops):
            tg = self.tags.get(i)
            if mode != 'add' or tg is None:
                continue
            lo, hi = prim.bbox()
            sel = np.where(((pts >= lo - 2.0) & (pts <= hi + 2.0)).all(1))[0]
            if len(sel) == 0:
                continue
            d = prim.d(pts[sel])
            arr = out.setdefault(tg, np.full(len(pts), 9.0))
            arr[sel] = np.minimum(arr[sel], d)
        return out

    def sub(self, prim, k=0.1):
        self.ops.append((prim, 'sub', k))
        return prim

    def _apply(self, D, prim, mode, k, p):
        d = prim.d(p)
        if mode == 'add':
            return smin(D, d, k)
        if mode == 'sub':
            return smax(D, -d, k)
        return np.maximum(D, -d)

    def eval_points(self, pts, chunk=200000):
        pts = np.asarray(pts, float).reshape(-1, 3)
        out = np.full(len(pts), 4.0)
        for prim, mode, k in self.ops:
            lo, hi = prim.bbox()
            m = k + 0.05
            sel = np.where(((pts >= lo - m) & (pts <= hi + m)).all(1))[0]
            if len(sel) == 0:
                continue
            out[sel] = self._apply(out[sel], prim, mode, k, pts[sel])
        return out

    def grad(self, pts, eps=0.012):
        pts = np.asarray(pts, float).reshape(-1, 3)
        g = np.zeros_like(pts)
        for i in range(3):
            e = np.zeros(3)
            e[i] = eps
            g[:, i] = self.eval_points(pts + e) - self.eval_points(pts - e)
        return g / (2 * eps)

    def eval_grid(self, lo, hi, h):
        lo = np.asarray(lo, float)
        n = np.ceil((np.asarray(hi, float) - lo) / h).astype(int) + 1
        xs = [lo[i] + np.arange(n[i]) * h for i in range(3)]
        D = np.full(tuple(n), 3.0, np.float32)
        for prim, mode, k in self.ops:
            plo, phi = prim.bbox()
            m = k + 3 * h
            i0 = np.maximum(np.floor((plo - m - lo) / h).astype(int), 0)
            i1 = np.minimum(np.ceil((phi + m - lo) / h).astype(int) + 1, n)
            if (i1 <= i0).any():
                continue
            gx, gy, gz = np.meshgrid(xs[0][i0[0]:i1[0]], xs[1][i0[1]:i1[1]], xs[2][i0[2]:i1[2]], indexing='ij')
            p = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], 1)
            sub = D[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]].reshape(-1).astype(np.float64)
            sub = self._apply(sub, prim, mode, k, p)
            D[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]] = sub.reshape(gx.shape).astype(np.float32)
        return D, lo, h


def isosurface(field, lo, hi, h):
    """Marching cubes of the field -> welded (V, F) in world coordinates."""
    from skimage import measure
    D, lo, h = field.eval_grid(lo, hi, h)
    D[0, :, :] = D[-1, :, :] = 1.0
    D[:, 0, :] = D[:, -1, :] = 1.0
    D[:, :, 0] = D[:, :, -1] = 1.0
    V, F, _, _ = measure.marching_cubes(D, 0.0, spacing=(h, h, h))
    V = V + lo
    return V, F.astype(np.int64)


def project(field, V, iters=4, step=1.0):
    """Newton-project points onto the zero level set."""
    V = V.copy()
    for _ in range(iters):
        d = field.eval_points(V)
        g = field.grad(V)
        gl = np.maximum(_len(g), 1e-6)[:, None]
        V = V - (d[:, None] * g / (gl * gl)) * step
    return V


def field_normals(field, V):
    g = field.grad(V, eps=0.02)
    return g / np.maximum(_len(g), 1e-9)[:, None]

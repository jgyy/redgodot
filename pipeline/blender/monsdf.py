"""Signed-distance modelling + naive surface nets (pure numpy, no bpy).

Coordinates are upstream's 64x64 sprite space: x right, y DOWN, plus a depth axis d
(d < 0 = toward the front viewer, i.e. Blender -Y).  Every primitive of a Pokemon
definition becomes an SDF; the parts of one art group are smooth-unioned into a
single watertight surface which is then polygonised with surface nets.
"""
import math

import numpy as np

BIG = 1.0e4


# ----------------------------------------------------------------------------- helpers
def smin(a, b, k):
    """Polynomial smooth minimum (IQ).  k <= 0 -> hard min."""
    if k <= 1e-6:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def seg_dist2d(px, py, ax, ay, bx, by):
    ex, ey = bx - ax, by - ay
    l2 = ex * ex + ey * ey
    if l2 < 1e-12:
        t = np.zeros_like(px)
    else:
        t = np.clip(((px - ax) * ex + (py - ay) * ey) / l2, 0.0, 1.0)
    dx, dy = px - (ax + ex * t), py - (ay + ey * t)
    return np.sqrt(dx * dx + dy * dy), t


def poly_sdf2d(px, py, pts):
    """Signed distance to a closed polygon (negative inside, even-odd rule)."""
    n = len(pts)
    d = np.full(px.shape, BIG)
    inside = np.zeros(px.shape, dtype=bool)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        dd, _ = seg_dist2d(px, py, ax, ay, bx, by)
        d = np.minimum(d, dd)
        if ay != by:
            cond = ((ay > py) != (by > py)) & (px < (bx - ax) * (py - ay) / (by - ay) + ax)
            inside ^= cond
    return np.where(inside, -d, d)


# ----------------------------------------------------------------------------- primitive SDFs
def sdf_ellipsoid(X, Y, D, cx, cy, cd, rx, ry, rd, rot):
    dx, dy, w = X - cx, Y - cy, D - cd
    c, s = math.cos(rot), math.sin(rot)
    u = dx * c + dy * s
    v = -dx * s + dy * c
    k0 = np.sqrt((u / rx) ** 2 + (v / ry) ** 2 + (w / rd) ** 2)
    k1 = np.sqrt((u / (rx * rx)) ** 2 + (v / (ry * ry)) ** 2 + (w / (rd * rd)) ** 2)
    return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -min(rx, ry, rd))


def sdf_round_cone(X, Y, D, a, b, r1, r2):
    """Exact round cone (IQ) between 3D points a,b with radii r1,r2."""
    ba = np.array(b, dtype=float) - np.array(a, dtype=float)
    l2 = float(ba.dot(ba))
    rr = r1 - r2
    a2 = l2 - rr * rr
    if l2 < 1e-9 or a2 <= 1e-6:
        # degenerate: one sphere swallows the other
        if r1 >= r2:
            c, r = a, r1
        else:
            c, r = b, r2
        return np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2 + (D - c[2]) ** 2) - r
    il2 = 1.0 / l2
    pax, pay, paz = X - a[0], Y - a[1], D - a[2]
    y = pax * ba[0] + pay * ba[1] + paz * ba[2]
    z = y - l2
    qx, qy, qz = pax * l2 - ba[0] * y, pay * l2 - ba[1] * y, paz * l2 - ba[2] * y
    x2 = qx * qx + qy * qy + qz * qz
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2
    d_end = np.sqrt(x2 + z2) * il2 - r2
    d_start = np.sqrt(x2 + y2) * il2 - r1
    d_mid = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d_end, np.where(np.sign(y) * a2 * y2 < k, d_start, d_mid))


# ----------------------------------------------------------------------------- surface nets
def surface_nets(F, origin, h):
    """Naive surface nets on grid F[ix,iy,id] (inside < 0).

    Returns (verts[N,3] in (x,y,d) space, quads[M,4] vertex indices wound so the
    normals point outward in the (x, y, d) frame)."""
    s = F < 0
    nx, ny, nz = F.shape
    csum = np.zeros((nx - 1, ny - 1, nz - 1, 3))
    ccnt = np.zeros((nx - 1, ny - 1, nz - 1))
    I, J, K = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float), np.arange(nz, dtype=float),
                          indexing='ij')

    def edge(axis):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, -1)
        sl1[axis] = slice(1, None)
        f0, f1 = F[tuple(sl0)], F[tuple(sl1)]
        m = s[tuple(sl0)] != s[tuple(sl1)]
        den = np.where(m, f0 - f1, 1.0)
        t = np.where(m, f0 / den, 0.0)
        P = np.stack([I[tuple(sl0)], J[tuple(sl0)], K[tuple(sl0)]], axis=-1)
        P[..., axis] += t
        P *= m[..., None]
        return m, P

    for axis in range(3):
        m, P = edge(axis)
        # edge along `axis` touches the 4 cells offset by 0/-1 in the other two axes
        o = [a for a in range(3) if a != axis]
        for d0 in (0, 1):
            for d1 in (0, 1):
                sl = [slice(None)] * 3
                sl[o[0]] = slice(d0, d0 + (F.shape[o[0]] - 1))
                sl[o[1]] = slice(d1, d1 + (F.shape[o[1]] - 1))
                csum += P[tuple(sl)]
                ccnt += m[tuple(sl)]
    active = ccnt > 0
    idx = -np.ones(active.shape, dtype=np.int64)
    n_active = int(active.sum())
    idx[active] = np.arange(n_active)
    verts = csum[active] / ccnt[active][:, None]
    verts = np.asarray(origin, dtype=float)[None, :] + verts * h

    quads = []
    for axis in range(3):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, -1)
        sl1[axis] = slice(1, None)
        m = s[tuple(sl0)] != s[tuple(sl1)]
        inside_lo = s[tuple(sl0)]
        o = [a for a in range(3) if a != axis]
        # only interior edges (all 4 neighbouring cells exist)
        lim = [slice(None)] * 3
        lim[o[0]] = slice(1, F.shape[o[0]] - 1)
        lim[o[1]] = slice(1, F.shape[o[1]] - 1)
        mm = np.zeros_like(m)
        mm[tuple(lim)] = m[tuple(lim)]
        e = np.argwhere(mm)
        if len(e) == 0:
            continue
        flip = inside_lo[mm]

        def cell(dd0, dd1):
            c = e.copy()
            c[:, o[0]] -= dd0
            c[:, o[1]] -= dd1
            return idx[c[:, 0], c[:, 1], c[:, 2]]
        a = cell(1, 1)
        b = cell(0, 1)
        c = cell(0, 0)
        d = cell(1, 0)
        q = np.stack([a, b, c, d], axis=1)
        # orientation: (o0, o1, axis) cyclic -> outward when inside is at the low end
        cyc = (o[0], o[1], axis) in ((0, 1, 2), (1, 2, 0), (2, 0, 1))
        rev = flip if cyc else ~flip
        q[rev] = q[rev][:, ::-1]
        quads.append(q)
    quads = np.concatenate(quads, axis=0) if quads else np.zeros((0, 4), dtype=np.int64)
    return verts, quads[:, ::-1].copy()  # outward-facing

"""Unified signed-distance field of a Pokemon (numpy only, no bpy).

All art groups of a species live on ONE regular grid.  Each group has its own field
F_g (the smooth union of its parts); the model's field is a smooth union of the groups,
except that *sibling* groups (left/right legs, the near and far arm, the two ears...)
are joined with a hard minimum so they never web together.  This gives one watertight,
organically filleted surface (shoulders, necks, tail roots) instead of a pile of
interpenetrating shells, while keeping the per-group fields for

  * skin weights   (a vertex near a neighbouring group's surface is partly skinned to it),
  * texture ownership (which group's atlas layer paints a triangle),
  * ambient occlusion (self shadowing from the field itself).

Coordinates are upstream sprite space (x right, y DOWN, d depth, d<0 toward the viewer).
"""
import re

import numpy as np

import monsdf as SD

BIG = 1.0e3


# ----------------------------------------------------------------------------- grid helpers
class Grid:
    def __init__(self, lo, hi, h):
        self.h = float(h)
        self.o = np.asarray(lo, dtype=float)
        self.n = np.ceil((np.asarray(hi, dtype=float) - self.o) / self.h).astype(int) + 1

    def axis(self, a, i0=0, i1=None):
        i1 = self.n[a] if i1 is None else i1
        return self.o[a] + np.arange(i0, i1) * self.h

    def index_range(self, a, lo, hi):
        i0 = int(np.floor((lo - self.o[a]) / self.h))
        i1 = int(np.ceil((hi - self.o[a]) / self.h)) + 1
        return max(0, i0), min(int(self.n[a]), i1)


class Block:
    """Field values on a sub-box [i0:i1, j0:j1, k0:k1] of the global grid."""

    def __init__(self, sl, arr):
        self.sl = sl                      # (slice, slice, slice)
        self.arr = arr

    def extent(self):
        return tuple((s.start, s.stop) for s in self.sl)

    def paste_into(self, sl_target, fill=BIG):
        """Return this block's values on the target box (BIG where it has no data)."""
        out = np.full(tuple(s.stop - s.start for s in sl_target), fill, dtype=np.float32)
        src, dst = [], []
        for s, t in zip(self.sl, sl_target):
            a, b = max(s.start, t.start), min(s.stop, t.stop)
            if b <= a:
                return out
            src.append(slice(a - s.start, b - s.start))
            dst.append(slice(a - t.start, b - t.start))
        out[tuple(dst)] = self.arr[tuple(src)]
        return out


# ----------------------------------------------------------------------------- sibling test
_SIB = re.compile(r'^(.*?[a-z0-9])(?:[A-Z]{1,3}|[0-9]{1,2}[A-Za-z]?)?$')


def sib_key(name):
    """'legFB','legB2','legL' -> 'leg'; 'armBT' -> 'arm'; 'earF' -> 'ear' ..."""
    n = name
    n = re.sub(r'(?<=[a-z])[A-Z]{1,3}[0-9]?$', '', n)
    n = re.sub(r'[0-9]+[A-Za-z]?$', '', n)
    n = re.sub(r'(?<=[a-z])[LRFB]$', '', n)
    return n.lower() or name.lower()


def are_siblings(a, b):
    ka, kb = sib_key(a), sib_key(b)
    return ka == kb and len(ka) >= 2


# ----------------------------------------------------------------------------- group fields
def group_field(G, grid, pad):
    """Own smooth-union field of a group on its bbox block of the global grid."""
    x0 = min(q.bx0 for q in G.parts) - pad
    y0 = min(q.by0 for q in G.parts) - pad
    x1 = max(q.bx1 for q in G.parts) + pad
    y1 = max(q.by1 for q in G.parts) + pad
    dz = G.rmax + pad
    i0, i1 = grid.index_range(0, x0, x1)
    j0, j1 = grid.index_range(1, y0, y1)
    k0, k1 = grid.index_range(2, G.cd - dz, G.cd + dz)
    xs, ys, ds = grid.axis(0, i0, i1), grid.axis(1, j0, j1), grid.axis(2, k0, k1)
    F = np.full((len(xs), len(ys), len(ds)), BIG, dtype=np.float32)
    thin = min(q.thin for q in G.parts)
    multi = len(G.parts) > 1
    for q in sorted(G.parts, key=lambda q: -q.area):
        a0 = max(0, int(np.searchsorted(xs, q.bx0 - pad)) - 1)
        a1 = min(len(xs), int(np.searchsorted(xs, q.bx1 + pad)) + 1)
        b0 = max(0, int(np.searchsorted(ys, q.by0 - pad)) - 1)
        b1 = min(len(ys), int(np.searchsorted(ys, q.by1 + pad)) + 1)
        de = q.depth_extent() + pad
        c0 = max(0, int(np.searchsorted(ds, G.cd - de)) - 1)
        c1 = min(len(ds), int(np.searchsorted(ds, G.cd + de)) + 1)
        if a1 <= a0 or b1 <= b0 or c1 <= c0:
            continue
        X, Y, D = np.meshgrid(xs[a0:a1], ys[b0:b1], ds[c0:c1], indexing='ij')
        f = q.sdf(X, Y, D, G.cd)
        k = min(1.8, 0.45 * q.thin, 0.45 * thin + 0.3)
        blk = F[a0:a1, b0:b1, c0:c1]
        F[a0:a1, b0:b1, c0:c1] = (SD.smin(blk, f, k) if multi else np.minimum(blk, f)).astype(np.float32)
    return Block((slice(i0, i1), slice(j0, j1), slice(k0, k1)), F)


def blend_k(G, scale=1.0):
    """Fillet radius used when G is smooth-unioned onto the rest of the model."""
    w = sum(q.area * q.thin for q in G.parts) / max(sum(q.area for q in G.parts), 1e-6)
    return float(np.clip((0.5 * w + 0.2) * scale, 0.5, 2.2))


class Model:
    def __init__(self, groups, h, k_scale=1.0, pad_extra=0.0):
        self.groups = [G for G in groups]
        self.h = h
        x0 = min(q.bx0 for G in groups for q in G.parts)
        y0 = min(q.by0 for G in groups for q in G.parts)
        x1 = max(q.bx1 for G in groups for q in G.parts)
        y1 = max(q.by1 for G in groups for q in G.parts)
        d0 = min(G.cd - G.rmax for G in groups)
        d1 = max(G.cd + G.rmax for G in groups)
        self.pad = 3 * h + 0.6 + pad_extra
        p = self.pad + 2.5
        self.grid = Grid((x0 - p, y0 - p, d0 - p), (x1 + p, y1 + p, d1 + p), h)
        self.blocks = {}
        nx, ny, nz = self.grid.n
        F = np.full((nx, ny, nz), BIG, dtype=np.float32)
        placed = []
        for G in sorted(groups, key=lambda g: -g.area):
            fb = group_field(G, self.grid, self.pad + 2.0)
            self.blocks[G.name] = fb
            k = blend_k(G, k_scale)
            others = None
            for H in placed:
                if are_siblings(G.name, H.name):
                    continue
                hv = self.blocks[H.name].paste_into(fb.sl)
                others = hv if others is None else np.minimum(others, hv)
            blended = fb.arr if others is None else SD.smin(others, fb.arr, k).astype(np.float32)
            F[fb.sl] = np.minimum(F[fb.sl], blended)
            placed.append(G)
        self.F = F

    # ---- trilinear sampling of an array with the given origin block offset
    def _sample(self, arr, off, P, fill=BIG):
        g = self.grid
        u = (P - g.o[None, :]) / g.h - np.asarray(off, dtype=float)[None, :]
        sh = np.asarray(arr.shape)
        i = np.floor(u).astype(int)
        t = u - i
        out = np.zeros(len(P))
        inside = np.all((i >= 0) & (i < sh - 1), axis=1)
        ii = i[inside]
        tt = t[inside]
        acc = np.zeros(len(ii))
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = (tt[:, 0] if dx else 1 - tt[:, 0]) * (tt[:, 1] if dy else 1 - tt[:, 1]) * \
                        (tt[:, 2] if dz else 1 - tt[:, 2])
                    acc += w * arr[ii[:, 0] + dx, ii[:, 1] + dy, ii[:, 2] + dz]
        out[:] = fill
        out[inside] = acc
        return out

    def sample(self, P):
        return self._sample(self.F, (0, 0, 0), np.asarray(P, dtype=float), BIG)

    def sample_group(self, name, P):
        b = self.blocks[name]
        off = (b.sl[0].start, b.sl[1].start, b.sl[2].start)
        return self._sample(b.arr, off, np.asarray(P, dtype=float), BIG)

    def gradient(self, P, eps=None):
        eps = eps or self.h * 0.6
        P = np.asarray(P, dtype=float)
        g = np.zeros_like(P)
        for a in range(3):
            d = np.zeros(3)
            d[a] = eps
            g[:, a] = (self.sample(P + d) - self.sample(P - d)) / (2 * eps)
        return g

    def project(self, P, iters=3):
        """Newton steps onto the F=0 surface (the field is ~ a distance)."""
        P = np.array(P, dtype=float)
        for _ in range(iters):
            f = self.sample(P)
            g = self.gradient(P)
            n2 = np.maximum((g * g).sum(1), 1e-8)
            step = g * (f / n2)[:, None]
            L = np.linalg.norm(step, axis=1)
            sc = np.minimum(1.0, self.h * 1.2 / np.maximum(L, 1e-9))
            P -= step * sc[:, None]
        return P

    def normals(self, P):
        g = self.gradient(P)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-8)

    def ambient_occlusion(self, P, N, radius, samples=6):
        """SDF-march AO (iq): how much of a shell of size `radius` above the surface is solid."""
        occ = np.zeros(len(P))
        sca = 1.0
        tot = 0.0
        for i in range(1, samples + 1):
            d = radius * i / samples
            f = self.sample(P + N * d)
            occ += np.clip(d - f, 0.0, None) / d * sca
            tot += sca
            sca *= 0.82
        return np.clip(occ / tot, 0.0, 1.0)


# ----------------------------------------------------------------------------- polygonisation
def surface_nets_sparse(F, origin, h):
    """Naive surface nets that only touches cells along the surface (F < 0 inside).
    Returns (verts[N,3], quads[M,4]) with outward-facing winding in the (x, y, d) frame."""
    s = F < 0
    nx, ny, nz = F.shape
    sh = np.array([nx - 1, ny - 1, nz - 1], dtype=np.int64)
    strides = np.array([sh[1] * sh[2], sh[2], 1], dtype=np.int64)
    pts_cell, pts_pos = [], []
    edges = []
    for axis in range(3):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, -1)
        sl1[axis] = slice(1, None)
        m = s[tuple(sl0)] != s[tuple(sl1)]
        e = np.argwhere(m)
        if len(e) == 0:
            edges.append((axis, e, None, None))
            continue
        f0 = F[tuple(sl0)][m].astype(np.float64)
        f1 = F[tuple(sl1)][m].astype(np.float64)
        t = f0 / np.where(np.abs(f0 - f1) < 1e-12, 1.0, f0 - f1)
        pos = e.astype(np.float64)
        pos[:, axis] += t
        edges.append((axis, e, pos, s[tuple(sl0)][m]))
        o = [a for a in range(3) if a != axis]
        for d0 in (0, 1):
            for d1 in (0, 1):
                c = e.copy()
                c[:, o[0]] -= d0
                c[:, o[1]] -= d1
                ok = np.all((c >= 0) & (c < sh[None, :]), axis=1)
                pts_cell.append((c[ok] * strides).sum(1))
                pts_pos.append(pos[ok])
    if not pts_cell:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.int64)
    cells = np.concatenate(pts_cell)
    pos = np.concatenate(pts_pos)
    uc, inv = np.unique(cells, return_inverse=True)
    sums = np.zeros((len(uc), 3))
    cnt = np.zeros(len(uc))
    np.add.at(sums, inv, pos)
    np.add.at(cnt, inv, 1.0)
    verts = sums / cnt[:, None]
    verts = np.asarray(origin, dtype=float)[None, :] + (verts + 0.0) * h
    quads = []
    for axis, e, pos_, inside_lo in edges:
        if len(e) == 0:
            continue
        o = [a for a in range(3) if a != axis]
        ok = (e[:, o[0]] >= 1) & (e[:, o[0]] <= nx * 0 + F.shape[o[0]] - 2) & \
             (e[:, o[1]] >= 1) & (e[:, o[1]] <= F.shape[o[1]] - 2)
        ee = e[ok]
        flip = inside_lo[ok]

        def cell(d0, d1):
            c = ee.copy()
            c[:, o[0]] -= d0
            c[:, o[1]] -= d1
            lin = (c * strides).sum(1)
            return np.searchsorted(uc, lin)
        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], axis=1)
        cyc = (o[0], o[1], axis) in ((0, 1, 2), (1, 2, 0), (2, 0, 1))
        rev = flip if cyc else ~flip
        q[rev] = q[rev][:, ::-1]
        quads.append(q)
    quads = np.concatenate(quads, axis=0) if quads else np.zeros((0, 4), dtype=np.int64)
    return verts, quads[:, ::-1].copy()

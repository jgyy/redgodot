"""Generate rigged, animated, textured 3D Pokemon (.glb) from upstream's 2D sprite definitions.

Usage (headless Blender via the bpy wheel, or `blender --background --python ... --`):
  python3 pipeline/blender/gen_pokemon.py -- --all            # all 151 (+ MISSINGNO)
  python3 pipeline/blender/gen_pokemon.py -- --only PIKACHU,CHARIZARD
  python3 pipeline/blender/gen_pokemon.py -- --all --jobs 4   # parallel worker processes

Input : pipeline/extracted/mons.json (upstream src/data/mons/*.js), pokedata.json
Output: godot/assets/models/pokemon/<SPECIES>.glb + manifest.json

How a 2D definition becomes a model
-----------------------------------
* Geometry lives in upstream's own 64x64 sprite space (x right, y down, ground ~ y 60)
  plus a depth axis, so every part lines up exactly with the sprite.
  Blender: X = x - 32, Z = 60 - y, Y = depth (front = -Y = glTF/Godot +Z).
* Each art group (`g`) is ONE smooth watertight surface: its ellipsoids, tapered
  capsules, strokes and bevelled polygon plates are signed-distance fields,
  smooth-unioned and polygonised with surface nets (monsdf.py), then decimated.
  Groups keep their own surface (upstream draws an inner line between groups) and
  get their own bone.
* Depth: paint order (z, then array order) becomes front-to-back placement: each
  group is pushed just far enough forward/back to be in front of / behind the groups
  it overlaps (solve_depth).
* Texture: an albedo atlas holds, per group, a front and a back layer rasterised
  from the definition itself (monraster.py -- pokesprite.js's coverage/feature code
  minus its lighting): palette colours, spots, stripes, eyes, mouths, shines.  UVs
  are the planar sprite projection, front layer on front-facing faces and the
  back layer (no face parts, backOnly parts) on back-facing ones -- so eyes and
  patterns land exactly where the sprite has them.
* Lighting / outline happen in Godot (assets/shaders/toon.gdshader).
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402
import monsdf as SD  # noqa: E402
import monraster as RS  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXTRACTED = os.path.join(ROOT, 'pipeline', 'extracted')
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon')

SOLID_TYPES = ('e', 'c', 'p', 'l')
FEATURE_TYPES = ('eye', 'mouth', 'shine')
TEX_S = 4.0            # atlas texels per sprite pixel
ATLAS_W = 1024
TRI_BUDGET = 6000      # per species (before the minimum-per-group floor)


# ============================================================================ parts
def resolve_color(c, pal):
    return RS.col(c, pal)


def fnum(p, k, d=0.0):
    v = p.get(k, d)
    try:
        return float(v if v is not None else d)
    except (TypeError, ValueError):
        return d


class Part:
    """One solid primitive with an SDF and an analytic half-thickness footprint."""

    def __init__(self, p, order, gname, color):
        self.p = p
        self.t = p['t']
        self.order = order
        self.z = fnum(p, 'z', 0.0)
        self.key = self.z * 1000 + order          # upstream's z-buffer key
        self.g = gname
        self.color = color
        self.flat = bool(p.get('flat'))
        t = self.t
        if t == 'e':
            self.cx, self.cy = fnum(p, 'x'), fnum(p, 'y')
            self.rx = max(0.5, fnum(p, 'rx', 2) or 2)
            self.ry = max(0.5, fnum(p, 'ry', self.rx) or self.rx)
            self.rot = math.radians(fnum(p, 'rot', 0))
            lo, hi = min(self.rx, self.ry), max(self.rx, self.ry)
            self.rd = (0.82 * lo + 0.12 * hi) * (0.55 if self.flat else 1.0)
            self.rd = max(self.rd, 0.6)
            self.thin = min(lo, self.rd)
            self.area = math.pi * self.rx * self.ry
        elif t in ('c', 'l'):
            if t == 'c':
                r1 = max(0.45, fnum(p, 'r1', 2) or 2)
                r2 = max(0.45, fnum(p, 'r2', r1) if p.get('r2') is not None else r1)
                self.segs = [(fnum(p, 'x1'), fnum(p, 'y1'), fnum(p, 'x2'), fnum(p, 'y2'), r1, r2)]
            else:
                pts = RS.pairs(p['pts'])
                w1 = fnum(p, 'w', 2) or 2
                w2 = fnum(p, 'w2', w1) if p.get('w2') is not None else w1
                self.segs = [(a, b, c, d, max(0.45, ra), max(0.45, rb))
                             for a, b, c, d, ra, rb in RS.stroke_segments(pts, w1, w2)]
            self.thin = min(min(s[4], s[5]) for s in self.segs)
            self.area = sum(math.hypot(s[2] - s[0], s[3] - s[1]) * (s[4] + s[5]) for s in self.segs) + \
                math.pi * max(max(s[4], s[5]) for s in self.segs) ** 2
        elif t == 'p':
            pts = RS.pairs(p['pts'])
            # drop duplicate closing point
            if len(pts) > 3 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
                pts = pts[:-1]
            self.pts = pts
            cx = sum(q[0] for q in pts) / len(pts)
            cy = sum(q[1] for q in pts) / len(pts)
            R = max(math.hypot(q[0] - cx, q[1] - cy) for q in pts)
            a = 0.0
            for i in range(len(pts)):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % len(pts)]
                a += x0 * y1 - x1 * y0
            self.area = abs(a) * 0.5
            # inradius estimate on a coarse grid
            xs = np.linspace(min(q[0] for q in pts), max(q[0] for q in pts), 24)
            ys = np.linspace(min(q[1] for q in pts), max(q[1] for q in pts), 24)
            GX, GY = np.meshgrid(xs, ys)
            d2 = SD.poly_sdf2d(GX, GY, pts)
            self.inr = max(0.3, float(-d2.min()))
            k = 0.6 if self.flat else 1.0
            self.T0 = max(0.5, min(1.4, 0.05 * R)) * k
            self.T1 = max(self.T0, min(0.42 * self.inr, 0.16 * R, 6.0) * k)
            self.round = min(self.T0 * 0.85, 0.7)
            self.thin = self.T0
        else:
            raise ValueError('not a solid: %s' % t)
        self.bx0, self.by0, self.bx1, self.by1 = RS.part_bbox(p) if t != 'l' else self._stroke_bbox()

    def _stroke_bbox(self):
        xs = [s[0] for s in self.segs] + [s[2] for s in self.segs]
        ys = [s[1] for s in self.segs] + [s[3] for s in self.segs]
        r = max(max(s[4], s[5]) for s in self.segs)
        return min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r

    def depth_extent(self):
        if self.t == 'e':
            return max(self.rx, self.ry, self.rd)
        if self.t in ('c', 'l'):
            return max(max(s[4], s[5]) for s in self.segs) + abs(getattr(self, 'depth_to', 0.0))
        return self.T1

    # half-thickness at a sprite point (None outside the footprint)
    def surf(self, x, y):
        t = self.t
        if t == 'e':
            dx, dy = x - self.cx, y - self.cy
            c, s = math.cos(self.rot), math.sin(self.rot)
            u = (dx * c + dy * s) / self.rx
            v = (-dx * s + dy * c) / self.ry
            q = u * u + v * v
            return self.rd * math.sqrt(1 - q) if q < 1 else None
        if t in ('c', 'l'):
            best = None
            for ax, ay, bx, by, ra, rb in self.segs:
                ex, ey = bx - ax, by - ay
                l2 = ex * ex + ey * ey
                tt = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((x - ax) * ex + (y - ay) * ey) / l2))
                d = math.hypot(x - ax - ex * tt, y - ay - ey * tt)
                r = ra + (rb - ra) * tt
                if d < r:
                    hh = math.sqrt(r * r - d * d)
                    best = hh if best is None else max(best, hh)
            return best
        d2 = float(SD.poly_sdf2d(np.array([x]), np.array([y]), self.pts)[0])
        if d2 >= 0:
            return None
        return self.T0 + (self.T1 - self.T0) * math.sqrt(min(1.0, -d2 / self.inr))

    def samples(self):
        t = self.t
        if t == 'e':
            out = [(self.cx, self.cy)]
            c, s = math.cos(self.rot), math.sin(self.rot)
            for k in range(12):
                a = 2 * math.pi * k / 12
                for f in (0.45, 0.8):
                    u, v = math.cos(a) * self.rx * f, math.sin(a) * self.ry * f
                    out.append((self.cx + u * c - v * s, self.cy + u * s + v * c))
            return out
        if t in ('c', 'l'):
            out = []
            for ax, ay, bx, by, ra, rb in self.segs:
                for tt in (0.0, 0.25, 0.5, 0.75, 1.0):
                    out.append((ax + (bx - ax) * tt, ay + (by - ay) * tt))
            return out
        out = []
        xs = np.linspace(self.bx0, self.bx1, 9)
        ys = np.linspace(self.by0, self.by1, 9)
        for x in xs:
            for y in ys:
                if self.surf(x, y) is not None:
                    out.append((float(x), float(y)))
        cx = sum(q[0] for q in self.pts) / len(self.pts)
        cy = sum(q[1] for q in self.pts) / len(self.pts)
        return out or [(cx, cy)]

    # ---- SDF on a grid block (X, Y sprite coords, D depth)
    def sdf(self, X, Y, D, cd):
        t = self.t
        if t == 'e':
            return SD.sdf_ellipsoid(X, Y, D, self.cx, self.cy, cd, self.rx, self.ry, self.rd, self.rot)
        if t in ('c', 'l'):
            F = None
            dt = getattr(self, 'depth_to', 0.0)
            for ax, ay, bx, by, ra, rb in self.segs:
                f = SD.sdf_round_cone(X, Y, D, (ax, ay, cd), (bx, by, cd + dt), ra, rb)
                F = f if F is None else np.minimum(F, f)
            return F
        d2 = SD.poly_sdf2d(X[:, :, :1], Y[:, :, :1], self.pts)
        T = self.T0 + (self.T1 - self.T0) * np.sqrt(np.clip(-d2 / self.inr, 0.0, 1.0))
        r = self.round
        q1 = d2 + r
        q2 = np.abs(D - cd) - T + r
        return np.sqrt(np.maximum(q1, 0) ** 2 + np.maximum(q2, 0) ** 2) + np.minimum(np.maximum(q1, q2), 0) - r


class Group:
    def __init__(self, name):
        self.name = name
        self.parts = []
        self.cd = 0.0
        self.back_only = False

    @property
    def key(self):
        # paint order of the group = that of its biggest member
        return max(self.parts, key=lambda q: q.area).key

    @property
    def area(self):
        return sum(q.area for q in self.parts)

    @property
    def rmax(self):
        return max(q.depth_extent() for q in self.parts)

    def surf(self, x, y):
        best = None
        for q in self.parts:
            if q.bx0 <= x <= q.bx1 and q.by0 <= y <= q.by1:
                h = q.surf(x, y)
                if h is not None and (best is None or h > best):
                    best = h
        return best

    def samples(self):
        out = []
        for q in self.parts:
            out += q.samples()
        return out


def solve_depth(groups):
    """Paint order -> depth.  The anchor group (body, else the biggest) sits at depth 0;
    groups painted after it are pushed toward the viewer just far enough to be in front
    of the already-placed groups they overlap, groups painted before it are pushed back.

    Big groups only need most of their overlap in front (a low percentile of the
    per-sample requirement), so heads/limbs stay embedded in the body instead of
    floating off it; small decorations must be fully in front.  Ellipsoid groups that
    lie (almost) entirely over earlier groups -- belly plates, cheeks, noses, bug eyes --
    are flattened into lenses hugging that surface instead of bulging out."""
    body = [g for g in groups if g.name.lower() == 'body']
    anchor = max(body or groups, key=lambda g: g.area)
    order_front = sorted([g for g in groups if not g.back_only], key=lambda g: g.key)
    ai = order_front.index(anchor) if anchor in order_front else 0
    lim = max(anchor.rmax, 2.0) * 1.15
    placed = [anchor]

    def coverage(G):
        smp = G.samples()
        n = hit = 0
        for (x, y) in smp:
            if G.surf(x, y) is None:
                continue
            n += 1
            if any(Q.surf(x, y) is not None for Q in placed):
                hit += 1
        return hit / float(n) if n else 0.0

    def place(G, sign):
        cov = coverage(G)
        face = all(q.p.get('face') or q.p.get('frontOnly') for q in G.parts)
        if all(q.t == 'e' for q in G.parts) and (cov >= 0.92 or (face and cov >= 0.6)):
            for q in G.parts:
                q.rd = max(0.6, min(q.rd, 0.42 * min(q.rx, q.ry)))
                q.thin = min(q.rx, q.ry, q.rd)
        eps = max(0.6, 0.2 * min(G.rmax, 6.0))
        need = []
        for (x, y) in G.samples():
            sp = G.surf(x, y)
            if sp is None:
                continue
            b = None
            for Q in placed:
                sq = Q.surf(x, y)
                if sq is None:
                    continue
                v = (Q.cd - sq + sp - eps) if sign < 0 else (Q.cd + sq - sp + eps)
                if b is None or (v < b if sign < 0 else v > b):
                    b = v
            if b is not None:
                need.append(b)
        bound = 0.0
        if need:
            need.sort(reverse=(sign > 0))
            big = G.area > 120.0 and cov < 0.92 and not face
            k = int(len(need) * 0.2) if big else 0
            bound = need[min(k, len(need) - 1)]
            bound = min(bound, 0.0) if sign < 0 else max(bound, 0.0)
        if G.area > 120.0 and cov < 0.92 and not face:
            # big groups (heads, torsos): never pushed so far that they separate from
            # what they sit on when seen from behind / the side
            cap = 0.55 * min(G.rmax, anchor.rmax) + 1.0
            bound = max(-cap, min(cap, bound))
        G.cd = max(-lim, bound) if sign < 0 else min(lim, bound)
        placed.append(G)

    for G in order_front[ai + 1:]:
        place(G, -1)
    for G in reversed(order_front[:ai]):
        place(G, +1)
    for G in groups:
        if G.back_only:
            place(G, +1)
    return anchor


def _footprint(G, step=1.25):
    x0 = min(q.bx0 for q in G.parts)
    y0 = min(q.by0 for q in G.parts)
    x1 = max(q.bx1 for q in G.parts)
    y1 = max(q.by1 for q in G.parts)
    pts = []
    for x in np.arange(x0 + step * 0.5, x1, step):
        for y in np.arange(y0 + step * 0.5, y1, step):
            h = G.surf(float(x), float(y))
            if h is not None:
                pts.append((float(x), float(y), h))
    return pts


def add_connectors(groups, anchor):
    """Sprites often only *touch* two big shapes (a head resting on a body): the 2D
    outline makes them read as joined, but in 3D they'd float apart when seen from the
    side or behind.  Give such groups a short neck (a round cone of their own colour)
    reaching into the neighbour they touch."""
    big = [G for G in groups if G.area > 45.0 and not G.back_only]
    fps = {G.name: _footprint(G) for G in big}
    for G in big:
        if G is anchor:
            continue
        fp = fps[G.name]
        if not fp:
            continue
        best = None
        for Q in big:
            if Q is G or Q.area < 0.25 * G.area:
                continue
            # already solidly joined?  count 3D-overlapping footprint samples
            joined = 0
            for x, y, h in fp:
                hq = Q.surf(x, y)
                if hq is not None and abs(G.cd - Q.cd) < h + hq - 1.0:
                    joined += 1
            if joined >= 6:
                best = None
                break
            fq = fps[Q.name]
            if not fq:
                continue
            A = np.array([(x, y) for x, y, _ in fp])
            B = np.array([(x, y) for x, y, _ in fq])
            d = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
            i, j = np.unravel_index(int(np.argmin(d)), d.shape)
            if d[i, j] < 3.0 and (best is None or d[i, j] < best[0]):
                best = (d[i, j], Q, A[i], B[j])
        if best is None:
            continue
        _, Q, pa, pb = best
        main = max(G.parts, key=lambda q: q.area)
        cg = np.array([sum(q.bx0 + q.bx1 for q in G.parts) / (2 * len(G.parts)),
                       sum(q.by0 + q.by1 for q in G.parts) / (2 * len(G.parts))])
        cq = np.array([sum(q.bx0 + q.bx1 for q in Q.parts) / (2 * len(Q.parts)),
                       sum(q.by0 + q.by1 for q in Q.parts) / (2 * len(Q.parts))])
        a = pa + (cg - pa) * 0.35
        b = pb + (cq - pb) * 0.3
        r = max(1.2, min(4.0, 0.3 * min(G.rmax, Q.rmax)))
        p = {'t': 'c', 'x1': float(a[0]), 'y1': float(a[1]), 'x2': float(b[0]), 'y2': float(b[1]),
             'r1': r, 'r2': r * 0.9, 'g': G.name, 'z': main.z}
        q = Part(p, main.order, G.name, main.color)
        q.connector = True
        q.depth_to = Q.cd - G.cd
        G.parts.append(q)


# ============================================================================ geometry
def group_mesh(G):
    """Smooth-union SDF of a group's parts -> (verts[N,3] (x, y, d), quads[M,4])."""
    thin = min(q.thin for q in G.parts)
    x0 = min(q.bx0 for q in G.parts)
    y0 = min(q.by0 for q in G.parts)
    x1 = max(q.bx1 for q in G.parts)
    y1 = max(q.by1 for q in G.parts)
    dz = G.rmax
    h = float(np.clip(thin / 2.2, 0.16, 0.42))
    pad = 3 * h + 0.5
    ext = np.array([x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, 2 * dz + 2 * pad])
    vol = float(np.prod(ext))
    h = max(h, (vol / 3.0e6) ** (1.0 / 3.0))
    pad = 3 * h + 0.5
    xs = np.arange(x0 - pad, x1 + pad + h, h)
    ys = np.arange(y0 - pad, y1 + pad + h, h)
    ds = np.arange(G.cd - dz - pad, G.cd + dz + pad + h, h)
    F = np.full((len(xs), len(ys), len(ds)), SD.BIG)
    for q in sorted(G.parts, key=lambda q: -q.area):
        i0 = max(0, int(np.searchsorted(xs, q.bx0 - pad)) - 1)
        i1 = min(len(xs), int(np.searchsorted(xs, q.bx1 + pad)) + 1)
        j0 = max(0, int(np.searchsorted(ys, q.by0 - pad)) - 1)
        j1 = min(len(ys), int(np.searchsorted(ys, q.by1 + pad)) + 1)
        de = q.depth_extent() + pad
        k0 = max(0, int(np.searchsorted(ds, G.cd - de)) - 1)
        k1 = min(len(ds), int(np.searchsorted(ds, G.cd + de)) + 1)
        if i1 <= i0 or j1 <= j0 or k1 <= k0:
            continue
        X, Y, D = np.meshgrid(xs[i0:i1], ys[j0:j1], ds[k0:k1], indexing='ij')
        f = q.sdf(X, Y, D, G.cd)
        k = min(1.8, 0.45 * q.thin, 0.45 * thin + 0.3)
        blk = F[i0:i1, j0:j1, k0:k1]
        F[i0:i1, j0:j1, k0:k1] = SD.smin(blk, f, k) if len(G.parts) > 1 else np.minimum(blk, f)
    verts, quads = SD.surface_nets(F, (xs[0], ys[0], ds[0]), h)
    return verts, quads, h


def mesh_from_group(name, verts, quads, budget):
    """Blender mesh (Blender coords, px units), decimated to ~budget triangles."""
    me = bpy.data.meshes.new(name)
    V = [(float(x - 32.0), float(d), float(60.0 - y)) for x, y, d in verts]
    me.from_pydata(V, [], [tuple(int(i) for i in q) for q in quads])
    me.validate()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    tris = 2 * len(quads)
    # a pass of smoothing removes the voxel terracing without shrinking thin parts much
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    for _ in range(2):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if tris > budget:
        mod = obj.modifiers.new('dec', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.02, budget / float(tris))
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me2 = bpy.data.meshes.new_from_object(ev)
        obj.modifiers.clear()
        obj.data = me2
        bpy.data.meshes.remove(me)
        me = me2
    return obj


# ============================================================================ texture atlas
def build_layers(defn, groups, pal):
    """Per group, front + back albedo layers.  Returns {(g, side): (Region, rgb[h,w,3])}."""
    parts = defn.get('parts', []) or []
    gnames = {G.name for G in groups}
    part_group = {}
    for G in groups:
        for q in G.parts:
            part_group[q.order] = G.name
    # front composite (for deciding which group a face feature sits on)
    R = RS.Region(-8, -8, 72, 72, 2.0)
    zb = np.full(R.X.shape, -1e18)
    gid = np.full(R.X.shape, '', dtype=object)
    for order, p in enumerate(parts):
        if order in part_group and not p.get('backOnly'):
            key = fnum(p, 'z', 0) * 1000 + order
            m = RS.part_mask(R, p) & (key >= zb)
            zb[m] = key
            gid[m] = part_group[order]

    def group_at(x, y):
        i = int((x + 8) * 2.0)
        j = int((y + 8) * 2.0)
        if 0 <= j < gid.shape[0] and 0 <= i < gid.shape[1] and gid[j, i]:
            return gid[j, i]
        # nearest covered texel
        ys, xs = np.nonzero(gid != '')
        if len(xs) == 0:
            return None
        k = int(np.argmin((xs - i) ** 2 + (ys - j) ** 2))
        return gid[ys[k], xs[k]]

    feats = {}
    for order, p in enumerate(parts):
        if p.get('t') in FEATURE_TYPES:
            g = group_at(fnum(p, 'x'), fnum(p, 'y'))
            if g:
                feats.setdefault(g, []).append((order, p))

    layers = {}
    for G in groups:
        x0 = min(q.bx0 for q in G.parts) - 1.5
        y0 = min(q.by0 for q in G.parts) - 1.5
        x1 = max(q.bx1 for q in G.parts) + 1.5
        y1 = max(q.by1 for q in G.parts) + 1.5
        for side in ('front', 'back'):
            Rg = RS.Region(x0, y0, x1, y1, TEX_S)
            L = RS.Layer(Rg)
            for order, p in enumerate(parts):
                t = p.get('t')
                if side == 'front' and p.get('backOnly'):
                    continue
                if side == 'back' and (p.get('face') or p.get('frontOnly') or p.get('belly')):
                    continue
                if order in part_group:
                    if part_group[order] != G.name:
                        continue
                    z = fnum(p, 'bz', fnum(p, 'z', 0)) if side == 'back' else fnum(p, 'z', 0)
                    key = z * 1000 + order
                    m = RS.part_mask(Rg, p) & (key >= L.z)
                    L.z[m] = key
                    L.cov |= m
                    L.put(m, resolve_color(p.get('c'), pal))
                elif p.get('on') is not None and t not in FEATURE_TYPES:
                    if p.get('on') != G.name:
                        continue
                    m = RS.part_mask(Rg, p) & L.cov
                    L.put(m, resolve_color(p.get('c'), pal))
            if side == 'front':
                for order, p in feats.get(G.name, []):
                    L.draw_feature(p, pal)
            main = max(G.parts, key=lambda q: q.area).color
            layers[(G.name, side)] = (Rg, L.finish(main))
    return layers


def pack_atlas(layers):
    """Shelf-pack layers into one image.  Returns (atlas[H,W,3], {key: (ax, ay)}, W, H)."""
    items = sorted(layers.items(), key=lambda kv: -kv[1][1].shape[0])
    pad = 2
    x = y = shelf = 0
    pos = {}
    for key, (Rg, img) in items:
        h, w = img.shape[:2]
        if x + w + pad > ATLAS_W:
            x = 0
            y += shelf + pad
            shelf = 0
        pos[key] = (x, y)
        x += w + pad
        shelf = max(shelf, h)
    H = y + shelf
    H = int(math.ceil(H / 64.0) * 64)
    atlas = np.zeros((H, ATLAS_W, 3))
    for key, (Rg, img) in items:
        ax, ay = pos[key]
        h, w = img.shape[:2]
        atlas[ay:ay + h, ax:ax + w] = img
    return atlas, pos, ATLAS_W, H


def save_png(rgb, path):
    from PIL import Image
    img = Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8), 'RGB')
    img.save(path, optimize=True)


def make_textured_material(name, png_path):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    img = bpy.data.images.load(png_path)
    img.pack()
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.1
    return m


# ============================================================================ species
def collect_groups(defn, warnings):
    pal = defn.get('pal', {}) or {}
    parts = defn.get('parts', []) or []
    groups = {}
    for order, p in enumerate(parts):
        t = p.get('t')
        if t in SOLID_TYPES and p.get('on') is None:
            gname = p.get('g') or ('_%d' % order)
            try:
                q = Part(p, order, gname, resolve_color(p.get('c'), pal))
            except Exception as e:  # noqa: BLE001
                warnings.append('part %d (%s) skipped: %s' % (order, t, e))
                continue
            G = groups.get(gname)
            if G is None:
                G = groups[gname] = Group(gname)
            G.parts.append(q)
    for G in groups.values():
        G.back_only = all(q.p.get('backOnly') for q in G.parts)
    return list(groups.values())


def build_species(name, defn, warnings, tmpdir):
    pal = defn.get('pal', {}) or {}
    groups = collect_groups(defn, warnings)
    if not groups:
        raise RuntimeError('no solid parts')
    anchor = solve_depth(groups)
    add_connectors(groups, anchor)

    # ---- geometry per group
    raw = {}
    total_area = 0.0
    for G in groups:
        v, q, h = group_mesh(G)
        if len(q) == 0:
            warnings.append('group %s produced no surface' % G.name)
            continue
        # surface area estimate ~ quads * h^2
        area = len(q) * h * h
        raw[G.name] = (v, q, area)
        total_area += area
    mb = C.MeshBuilder()
    uv = mb.bm.loops.layers.uv.new('UVMap')

    # ---- texture atlas
    layers = build_layers(defn, [G for G in groups if G.name in raw], pal)
    atlas, pos, W, H = pack_atlas(layers)
    png = os.path.join(tmpdir, name + '.png')
    save_png(atlas, png)

    for G in groups:
        if G.name not in raw:
            continue
        v, q, area = raw[G.name]
        budget = max(90, int(TRI_BUDGET * area / max(total_area, 1e-6)))
        obj = mesh_from_group('g_' + G.name, v, q, budget)
        gi = mb.group_index(G.name)
        me = obj.data
        vmap = {}
        for mv in me.vertices:
            nv = mb.bm.verts.new(mv.co)
            nv[mb.grp] = gi
            vmap[mv.index] = nv
        mb.bm.verts.ensure_lookup_table()
        for poly in me.polygons:
            try:
                f = mb.bm.faces.new([vmap[i] for i in poly.vertices])
            except ValueError:
                continue
            f.smooth = True
            f.material_index = 0
            f.normal_update()
            side = 'front' if f.normal.y <= 0 else 'back'
            Rg, img = layers[(G.name, side)]
            ax, ay = pos[(G.name, side)]
            for loop in f.loops:
                co = loop.vert.co
                sx, sy = co.x + 32.0, 60.0 - co.z
                u = (ax + (sx - Rg.x0) * TEX_S) / W
                vv = (ay + (sy - Rg.y0) * TEX_S) / H
                loop[uv].uv = (u, 1.0 - vv)
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(me)
    mat = make_textured_material('mon_' + name.lower(), png)
    return mb, [mat], (W, H)


# ============================================================================ rig + export
HEAD_EXCLUDE = ('body', 'leg', 'arm', 'tail', 'wing', 'foot', 'hand', 'shell', 'belly', 'torso')


def ht_metres(sp):
    ht = sp.get('ht') or [1, 0]
    try:
        m = float(ht[0]) * 0.3048 + float(ht[1]) * 0.0254
    except Exception:  # noqa: BLE001
        m = 0.5
    return max(0.15, m)


def finalize(name, mb, mats, sp, out_path, flier=False):
    mb.finish()
    lo, hi = mb.bbox()
    H_px = max(hi.z - lo.z, 1e-3)
    target = ht_metres(sp)
    k = target / H_px
    cx, cy = (lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5
    zshift = lo.z if lo.z < 4.0 else 0.0     # keep genuine hovering (ghosts, floaters)
    mb.transform(lambda co: Vector(((co.x - cx) * k, (co.y - cy) * k, (co.z - zshift) * k)))

    stats = {}
    grp = mb.grp
    for v in mb.bm.verts:
        g = mb.groups[v[grp]]
        s = stats.setdefault(g, [Vector((0, 0, 0)), 0, []])
        s[0] += v.co
        s[1] += 1
        s[2].append(v.co.copy())
    cent = {g: s[0] / s[1] for g, s in stats.items() if s[1]}
    body_name = next((g for g in cent if g.lower() == 'body'), None) or max(stats.items(), key=lambda kv: kv[1][1])[0]
    body_c = cent[body_name]
    head = next((g for g in cent if g.lower() == 'head'), None) or next((g for g in cent if 'head' in g.lower()), None)
    head_box = None
    if head:
        hv = stats[head][2]
        hlo = Vector((min(v.x for v in hv), min(v.y for v in hv), min(v.z for v in hv)))
        hhi = Vector((max(v.x for v in hv), max(v.y for v in hv), max(v.z for v in hv)))
        hc, hs = (hlo + hhi) * 0.5, (hhi - hlo) * 0.5 * 1.35
        head_box = (hc - hs, hc + hs)

    bones, gb = [], {}
    for g in mb.groups:
        if g not in cent:
            continue
        c = cent[g]
        limb = C.is_leg(g) or C.is_arm(g) or C.is_wing(g) or C.is_tail(g) or C._has(g, 'claw', 'fin', 'ear')
        if limb:
            pts = stats[g][2]
            near = min(pts, key=lambda v: (v - body_c).length)
            pivot = near.lerp(c, 0.25)
        else:
            pivot = c
        parent = None
        if head and g != head and head_box and not C._has(g, *HEAD_EXCLUDE):
            lo_, hi_ = head_box
            if all(lo_[i] <= c[i] <= hi_[i] for i in (0, 2)):
                parent = head
        bname = g if g != 'root' else 'root_grp'
        bones.append({'name': bname, 'head': pivot, 'parent': parent, 'length': target * 0.12})
        gb[bname] = {'pivot': pivot, 'x': c.x, 'z': c.z, 'center': c}
    obj = mb.to_object(name, mats)
    if 'root' in obj.vertex_groups:
        obj.vertex_groups['root'].name = 'root_grp'
    arm = C.build_armature(name, bones, root_len=target * 0.25)
    C.skin_to_armature(obj, arm)
    C.animate_generic(arm, gb, target, body=body_name if body_name in gb else None, flier=flier,
                      hovering=zshift == 0.0 and lo.z >= 4.0)
    C.export_glb(out_path)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    # px_height: the model's height in upstream sprite pixels (64 = the whole sprite frame),
    # so the game can size models exactly like upstream's battle sprites (PokemonActor.use_sprite_scale)
    return {'height_m': round(target, 3), 'px_height': round(H_px, 2), 'groups': len(gb), 'tris': tris,
            'materials': len(mats)}


# ============================================================================ main
def is_flier(sp, defn):
    types = sp.get('types') or []
    names = ' '.join((p.get('g') or '') for p in defn.get('parts', []))
    return 'FLYING' in types and 'wing' in names.lower()


def run_one(name, defn, sp, out_dir, tmpdir):
    warnings = []
    t0 = time.time()
    out_path = os.path.join(out_dir, name + '.glb')
    C.reset_scene()
    mb, mats, tex = build_species(name, defn, warnings, tmpdir)
    info = finalize(name, mb, mats, sp, out_path, flier=is_flier(sp, defn))
    info['file'] = name + '.glb'
    info['bytes'] = os.path.getsize(out_path)
    info['status'] = 'generated'
    info['texture'] = '%dx%d' % tex
    print('%-12s %5.2fs h=%.2fm groups=%d tris=%d tex=%s %dKB %s' % (
        name, time.time() - t0, info['height_m'], info['groups'], info['tris'], info['texture'],
        info['bytes'] // 1024, ('warn=%d' % len(warnings)) if warnings else ''), flush=True)
    return info, warnings


def species_list(mons, pdata):
    species = [s for s in mons if s in pdata]
    species.sort(key=lambda s: pdata[s].get('dex', 999))
    return species


def main():
    args = C.parse_args()
    only = None
    if '--only' in args:
        only = [s for s in args[args.index('--only') + 1].split(',') if s]
    out_dir = args[args.index('--out') + 1] if '--out' in args else OUT_DIR
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 1
    C.ensure_dir(out_dir)
    mons = json.load(open(os.path.join(EXTRACTED, 'mons.json')))
    pdata = json.load(open(os.path.join(EXTRACTED, 'pokedata.json')))['species']
    species = species_list(mons, pdata)
    if only is not None:
        species = [s for s in species if s in only]
    t_all = time.time()

    if jobs > 1 and len(species) > 1:
        # fan out to worker processes (each is its own headless Blender), then merge
        chunks = [species[i::jobs] for i in range(jobs)]
        procs = []
        for i, ch in enumerate(chunks):
            if not ch:
                continue
            res = os.path.join(tempfile.gettempdir(), 'genmon_part%d.json' % i)
            cmd = [sys.executable, os.path.abspath(__file__), '--', '--only', ','.join(ch), '--out', out_dir,
                   '--result', res]
            procs.append((subprocess.Popen(cmd), res))
        results = {'species': {}, 'warnings': {}, 'errors': {}}
        for p, res in procs:
            p.wait()
            if os.path.exists(res):
                r = json.load(open(res))
                for k in results:
                    results[k].update(r.get(k, {}))
    else:
        results = {'species': {}, 'warnings': {}, 'errors': {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, name in enumerate(species):
                try:
                    info, warnings = run_one(name, mons[name], pdata[name], out_dir, tmpdir)
                    results['species'][name] = info
                    if warnings:
                        results['warnings'][name] = warnings
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    results['errors'][name] = '%s: %s' % (type(e).__name__, e)
        if '--result' in args:
            with open(args[args.index('--result') + 1], 'w') as fh:
                json.dump(results, fh)
            return

    if only is None:
        extra = {}
        try:
            import gen_missingno
            extra = gen_missingno.build(out_dir)
            results['species'].update(extra)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            results['errors']['MISSINGNO'] = '%s: %s' % (type(e).__name__, e)
        manifest = {
            'generated': [s for s in species if s in results['species']] + sorted(extra),
            'fallback': [], 'errors': results['errors'], 'warnings': results['warnings'],
            'species': results['species'],
            'animations': {'Idle': {'seconds': 2.0, 'loop': True}, 'Walk': {'seconds': 0.8, 'loop': True},
                           'Attack': {'seconds': 0.6, 'loop': False}, 'Hurt': {'seconds': 0.5, 'loop': False},
                           'Faint': {'seconds': 1.0, 'loop': False}, 'Special': {'seconds': 1.0, 'loop': False}},
            'conventions': {
                'units': 'metres; model height == Pokedex height (min 0.15 m)',
                'front': 'Blender -Y == glTF/Godot +Z (MODEL_FRONT)',
                'origin': 'bottom centre; hovering species keep their hover gap',
                'rig': "one bone per 2D art group, all under 'root'; face groups parented to 'head' when present",
                'texture': 'one albedo atlas per species (front/back sprite projections per art group); '
                           'shade with assets/shaders/toon.gdshader',
            },
            'elapsed_seconds': round(time.time() - t_all, 1),
        }
        with open(os.path.join(out_dir, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=1, sort_keys=False)
    print('DONE generated=%d errors=%d in %.1fs' % (len(results['species']), len(results['errors']),
                                                  time.time() - t_all))


if __name__ == '__main__':
    main()

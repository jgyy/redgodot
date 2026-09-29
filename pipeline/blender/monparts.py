"""Part / Group model of an upstream Pokemon sprite definition (numpy only, no bpy).

Split out of gen_pokemon.py so the geometry can be built and tested without Blender.
A *Part* is one solid primitive (ellipsoid, tapered capsule, stroke, bevelled polygon
plate) with an analytic SDF; a *Group* is an art group (`g`) -- the parts that upstream
paints as one limb / head / body.  solve_depth() turns paint order into depth, and
add_connectors() bridges groups that merely touch in 2D.
"""
import math

import numpy as np

import monsdf as SD
import monraster as RS

MIN_R = 0.75           # thinnest tube / stroke radius (sprite px): nothing is paper thin
SOLID_TYPES = ('e', 'c', 'p', 'l')
FEATURE_TYPES = ('eye', 'mouth', 'shine')

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
        self.d0 = fnum(p, 'd', 0.0)          # optional depth offset of the part (species_fixes)
        self.d1 = fnum(p, 'd1', 0.0)         # optional depth offset at a stroke/capsule start
        self.d2 = fnum(p, 'd2', 0.0)         # ... and at its end
        t = self.t
        if t == 'e':
            self.cx, self.cy = fnum(p, 'x'), fnum(p, 'y')
            self.rx = max(0.5, fnum(p, 'rx', 2) or 2)
            self.ry = max(0.5, fnum(p, 'ry', self.rx) or self.rx)
            self.rot = math.radians(fnum(p, 'rot', 0))
            lo, hi = min(self.rx, self.ry), max(self.rx, self.ry)
            self.rd = (0.82 * lo + 0.12 * hi) * (0.55 if self.flat else 1.0)
            if p.get('rd') is not None:
                self.rd = fnum(p, 'rd')
            self.rd = max(self.rd, 0.6)
            self.thin = min(lo, self.rd)
            self.area = math.pi * self.rx * self.ry
        elif t in ('c', 'l'):
            if t == 'c':
                r1 = max(MIN_R, fnum(p, 'r1', 2) or 2)
                r2 = max(MIN_R, fnum(p, 'r2', r1) if p.get('r2') is not None else r1)
                self.segs = [(fnum(p, 'x1'), fnum(p, 'y1'), fnum(p, 'x2'), fnum(p, 'y2'), r1, r2)]
            else:
                pts = RS.pairs(p['pts'])
                w1 = fnum(p, 'w', 2) or 2
                w2 = fnum(p, 'w2', w1) if p.get('w2') is not None else w1
                self.segs = [(a, b, c, d, max(MIN_R, ra), max(MIN_R, rb))
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
            if self.inr <= 3.4 and not self.flat:
                # slender plates (ears, horns, spikes, claws) get a round-ish cross-section, not a paper slab
                self.T1 = max(self.T1, 0.8 * self.inr)
            if p.get('T') is not None:
                self.T1 = max(self.T0, fnum(p, 'T'))
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
        off = abs(self.d0)
        if self.t == 'e':
            return max(self.rx, self.ry, self.rd) + off
        if self.t in ('c', 'l'):
            return max(max(s[4], s[5]) for s in self.segs) + abs(getattr(self, 'depth_to', 0.0)) + \
                max(abs(self.d1), abs(self.d2)) + off
        return self.T1 + off

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
        cd = cd + self.d0
        t = self.t
        if t == 'e':
            return SD.sdf_ellipsoid(X, Y, D, self.cx, self.cy, cd, self.rx, self.ry, self.rd, self.rot)
        if t in ('c', 'l'):
            F = None
            dt = getattr(self, 'depth_to', 0.0) + self.d2 - self.d1
            n = len(self.segs)
            for i, (ax, ay, bx, by, ra, rb) in enumerate(self.segs):
                da = cd + self.d1 + dt * i / n
                db = cd + self.d1 + dt * (i + 1) / n
                f = SD.sdf_round_cone(X, Y, D, (ax, ay, da), (bx, by, db), ra, rb)
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
        self.lens = False       # flattened ellipsoid lying on an earlier group: painted as a decal, no geometry

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
        G.lens = all(q.t == 'e' for q in G.parts) and (cov >= 0.92 or (face and cov >= 0.6))
        if G.lens:
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
        forced = [q.p['cd'] for q in G.parts if q.p.get('cd') is not None]
        if forced:
            G.cd = float(forced[0])          # species_fixes: explicit depth for this group
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




# ============================================================================ groups
import re as _re  # noqa: E402

DECAL_NAME = _re.compile(r'^(eye|mouth|ink|mask|wh|nost|slot|hole|rim|skull|grin|tooth|fang)', _re.I)


def is_decal_group(parts):
    """Groups that are only painted detail (eyes, mouths, face lines): all parts flat
    and flagged `face`.  They become texture decals on whatever they sit on."""
    return bool(parts) and all(q.get('flat') for q in parts) and any(q.get('face') for q in parts)


def collect_groups(defn, warnings):
    """Solid art groups of a definition.  Returns (groups, decal_group_names)."""
    pal = defn.get('pal', {}) or {}
    parts = defn.get('parts', []) or []
    raw = {}
    for order, p in enumerate(parts):
        if p.get('t') in SOLID_TYPES and p.get('on') is None:
            raw.setdefault(p.get('g') or ('_%d' % order), []).append((order, p))
    decals = {g for g, ps in raw.items() if is_decal_group([p for _, p in ps])}
    groups = {}
    for gname, ps in raw.items():
        if gname in decals:
            continue
        for order, p in ps:
            try:
                q = Part(p, order, gname, resolve_color(p.get('c'), pal))
            except Exception as e:  # noqa: BLE001
                warnings.append('part %d (%s) skipped: %s' % (order, p.get('t'), e))
                continue
            G = groups.get(gname)
            if G is None:
                G = groups[gname] = Group(gname)
            G.parts.append(q)
    for G in groups.values():
        G.back_only = all(q.p.get('backOnly') for q in G.parts)
    return list(groups.values()), decals

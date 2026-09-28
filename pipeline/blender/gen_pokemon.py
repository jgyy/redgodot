"""Generate rigged + animated 3D Pokemon (.glb) from the original game's 2D vector part data.

Usage:
  blender --background --python pipeline/blender/gen_pokemon.py -- --all
  blender --background --python pipeline/blender/gen_pokemon.py -- --only PIKACHU,CHARIZARD

Input : pipeline/extracted/mons.json, pipeline/extracted/pokedata.json
Output: godot/assets/models/pokemon/<SPECIES>.glb + manifest.json

Mapping (64x64 image space, y down, ground ~ y=60 -> Blender Z-up, front = -Y):
  X = x - 32, Z = 60 - y, Y = per-part depth solved from paint order (see solve_depth).
Everything is built in pixel units, then uniformly rescaled so the Z extent equals the
Pokedex height (ht feet/inches -> metres, min 0.15 m).
"""
import json
import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXTRACTED = os.path.join(ROOT, 'pipeline', 'extracted')
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon')

DARK = '#1b1a2e'
WHITE = '#ffffff'
SOLID_TYPES = ('e', 'c', 'p', 'l')


# ============================================================================ 2D solids
def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def seg_query(px, py, ax, ay, bx, by):
    ex, ey = bx - ax, by - ay
    l2 = ex * ex + ey * ey
    t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * ex + (py - ay) * ey) / l2))
    dx, dy = px - (ax + ex * t), py - (ay + ey * t)
    return t, math.hypot(dx, dy)


def poly_pairs(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def polyline_segments(pts, w1, w2):
    """[(ax,ay,bx,by,ra,rb)] with radius interpolated along cumulative length."""
    lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    total = sum(lens) or 1.0
    segs, acc = [], 0.0
    for i, l in enumerate(lens):
        t0, t1 = acc / total, (acc + l) / total
        acc += l
        segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                     (w1 + (w2 - w1) * t0) * 0.5, (w1 + (w2 - w1) * t1) * 0.5))
    return segs


class Solid:
    """A solid primitive in image space with an analytic depth half-thickness field."""

    def __init__(self, part, order, gname, color):
        self.p = part
        self.t = part['t']
        self.order = order
        self.g = gname
        self.color = color
        self.cd = 0.0  # solved depth centre (Blender Y, px units, front negative)
        t = self.t
        if t == 'e':
            self.cx, self.cy = float(part['x']), float(part['y'])
            self.rx = float(part.get('rx', 2) or 2)
            self.ry = float(part.get('ry', self.rx) or self.rx)
            self.rot = math.radians(float(part.get('rot', 0) or 0))
            self.rd = (self.rx + self.ry) * 0.5 * (0.5 if part.get('flat') else 0.9)
            self.rmax = self.rd
            self.area = math.pi * self.rx * self.ry
        elif t == 'c':
            r1 = float(part.get('r1', 2) or 2)
            r2 = float(part.get('r2', r1) if part.get('r2') is not None else r1)
            self.segs = [(float(part['x1']), float(part['y1']), float(part['x2']), float(part['y2']), r1, r2)]
            self.rmax = max(r1, r2)
            L = math.hypot(part['x2'] - part['x1'], part['y2'] - part['y1'])
            self.area = L * (r1 + r2) + math.pi * self.rmax ** 2 * 0.5
        elif t == 'l':
            pts = poly_pairs(part['pts'])
            w1 = float(part.get('w', 2) or 2)
            w2 = float(part['w2']) if part.get('w2') is not None else w1
            self.pts = pts
            self.segs = polyline_segments(pts, w1, w2)
            self.rmax = max(w1, w2) * 0.5
            self.area = sum(math.hypot(s[2] - s[0], s[3] - s[1]) * (s[4] + s[5]) for s in self.segs)
        elif t == 'p':
            pts = poly_pairs(part['pts'])
            self.pts = pts
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            self.cx, self.cy = cx, cy
            R = max(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
            self.thick = max(0.9, 0.12 * R * (0.6 if part.get('flat') else 1.0))
            self.rmax = self.thick * 0.5
            a = 0.0
            for i in range(len(pts)):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % len(pts)]
                a += x0 * y1 - x1 * y0
            self.area = abs(a) * 0.5
        else:
            raise ValueError('not a solid: %s' % t)

    # half-thickness of the solid at image point (x,y), or None if outside the footprint
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
                tt, d = seg_query(x, y, ax, ay, bx, by)
                r = ra + (rb - ra) * tt
                if d < r:
                    h = math.sqrt(r * r - d * d)
                    best = h if best is None else max(best, h)
            return best
        if t == 'p':
            return self.rmax if point_in_poly(x, y, self.pts) else None

    def samples(self):
        t = self.t
        if t == 'e':
            out = [(self.cx, self.cy)]
            c, s = math.cos(self.rot), math.sin(self.rot)
            for k in range(8):
                a = 2 * math.pi * k / 8
                u, v = math.cos(a) * self.rx * 0.6, math.sin(a) * self.ry * 0.6
                out.append((self.cx + u * c - v * s, self.cy + u * s + v * c))
            return out
        if t in ('c', 'l'):
            out = []
            for ax, ay, bx, by, ra, rb in self.segs:
                for tt in (0.0, 0.5, 1.0):
                    out.append((ax + (bx - ax) * tt, ay + (by - ay) * tt))
            return out
        if t == 'p':
            out = [(self.cx, self.cy)]
            for px, py in self.pts:
                out.append((self.cx + (px - self.cx) * 0.6, self.cy + (py - self.cy) * 0.6))
            return [p for p in out if point_in_poly(p[0], p[1], self.pts)] or [(self.cx, self.cy)]


def solve_depth(solids):
    """Turn 2D paint order into 3D depth.

    The anchor (the 'body' group's biggest part, else the biggest part) sits at Y=0.
    Parts painted AFTER it are pushed toward the viewer (-Y) just enough that they are
    visible in front of every earlier part they overlap (+ a margin); parts painted BEFORE
    it are pushed back (+Y) symmetrically.  Non-overlapping parts stay on the centre plane.
    """
    if not solids:
        return None
    body = [s for s in solids if s.g.lower() == 'body' and s.t != 'p']
    anchor = max(body or solids, key=lambda s: s.area)
    order = sorted(solids, key=lambda s: s.order)
    ai = order.index(anchor)
    lim = max(anchor.rmax, 2.0) * 1.2
    placed = [anchor]
    for P in order[ai + 1:]:
        eps = max(0.8, 0.3 * P.rmax)
        bound = 0.0
        for (x, y) in P.samples():
            sp = P.surf(x, y)
            if sp is None:
                continue
            for Q in placed:
                sq = Q.surf(x, y)
                if sq is None:
                    continue
                bound = min(bound, Q.cd - sq + sp - eps)
        P.cd = max(-lim, bound)
        placed.append(P)
    for P in reversed(order[:ai]):
        eps = max(0.8, 0.3 * P.rmax)
        bound = 0.0
        for (x, y) in P.samples():
            sp = P.surf(x, y)
            if sp is None:
                continue
            for Q in placed:
                sq = Q.surf(x, y)
                if sq is None:
                    continue
                bound = max(bound, Q.cd + sq - sp + eps)
        P.cd = min(lim, bound)
        placed.append(P)
    return anchor


def front_surface(solids, x, y, back=False):
    """(Y, solid) of the front-most (or back-most) solid surface at image point (x,y)."""
    best, who = None, None
    for S in solids:
        h = S.surf(x, y)
        if h is None:
            continue
        yv = S.cd + h if back else S.cd - h
        if best is None or (yv > best if back else yv < best):
            best, who = yv, S
    return best, who


def surface_frame(solids, x, y, back=False):
    """Surface point (Blender coords), outward unit normal and owning solid."""
    y0, who = front_surface(solids, x, y, back)
    if y0 is None:
        return None, None, None
    h = 0.75

    def f(xx, yy):
        v, _ = front_surface(solids, xx, yy, back)
        return y0 if v is None else v
    dfdx = (f(x + h, y) - f(x - h, y)) / (2 * h)        # d(Ydepth)/dX
    dfdz = -(f(x, y + h) - f(x, y - h)) / (2 * h)       # Z = 60 - y
    n = Vector((dfdx, -1.0, dfdz)) if not back else Vector((-dfdx, 1.0, -dfdz))
    n.normalize()
    axis = Vector((0, -1, 0)) if not back else Vector((0, 1, 0))
    if n.dot(axis) < 0.45:   # clamp extreme tilt (silhouette edges)
        n = (n + axis * 0.6).normalized()
    return Vector((x - 32.0, y0, 60.0 - y)), n, who


def orient_to(n):
    """3x3 rotation taking local -Y (the feature's outward axis) to n."""
    return Vector((0, -1, 0)).rotation_difference(n).to_matrix()


# ============================================================================ builder
def resolve_color(c, pal):
    if not c:
        return '#888888'
    if isinstance(c, str) and c.startswith('#'):
        return c
    v = pal.get(c)
    if isinstance(v, str):
        return v
    return '#888888'


def ht_metres(sp):
    ht = sp.get('ht') or [1, 0]
    try:
        m = float(ht[0]) * 0.3048 + float(ht[1]) * 0.0254
    except Exception:
        m = 0.5
    return max(0.15, m)


def build_species(name, defn, sp, warnings):
    pal = defn.get('pal', {}) or {}
    parts = defn.get('parts', []) or []
    mats = C.MaterialCache('mat')
    mb = C.MeshBuilder()

    solids = []
    decor = []
    for order, p in enumerate(parts):
        t = p.get('t')
        if t == 'shine':
            continue
        if t in SOLID_TYPES and 'on' not in p:
            try:
                S = Solid(p, (float(p.get('z', 0) or 0), order), p.get('g') or ('_%d' % order),
                          resolve_color(p.get('c'), pal))
                solids.append(S)
            except Exception as e:
                warnings.append('part %d (%s) skipped: %s' % (order, t, e))
        else:
            decor.append((order, p))
    if not solids:
        raise RuntimeError('no solid parts')
    anchor = solve_depth(solids)

    # ---- solid geometry
    group_faces = {}
    for S in solids:
        mi = mats.get(S.color)
        try:
            if S.t == 'e':
                faces = mb.ellipsoid((S.cx - 32, S.cd, 60 - S.cy), (S.rx, S.rd, S.ry), mi, S.g, rot_y=S.rot)
            elif S.t in ('c', 'l'):
                pts, rad = [], []
                for i, (ax, ay, bx, by, ra, rb) in enumerate(S.segs):
                    if i == 0:
                        pts.append((ax - 32, S.cd, 60 - ay))
                        rad.append(max(ra, 0.25))
                    pts.append((bx - 32, S.cd, 60 - by))
                    rad.append(max(rb, 0.25))
                faces = mb.tube(pts, rad, mi, S.g)
            else:
                faces = mb.plate([(x - 32, 60 - y) for x, y in S.pts], S.cd, S.thick, mi, S.g)
            group_faces.setdefault(S.g, []).extend(faces)
        except Exception as e:
            warnings.append('solid %s/%s failed: %s' % (S.g, S.t, e))
    if not group_faces:
        raise RuntimeError('no geometry built')
    mb.bm.normal_update()

    by_group = {}
    for S in solids:
        by_group.setdefault(S.g, []).append(S)

    # ---- decorations: clipped patterns (spot/stripe/on-polys) recolour the target
    #      group's faces; eyes & mouths become small meshes on the front surface.
    for order, p in decor:
        t = p.get('t')
        try:
            if 'on' in p:
                add_pattern(mb, mats, p, pal, by_group, group_faces, solids, warnings)
            elif t == 'eye':
                add_eye(mb, mats, p, pal, solids)
            elif t == 'mouth':
                add_mouth(mb, mats, p, pal, solids)
            elif t in ('spot', 'stripe'):
                add_pattern(mb, mats, p, pal, by_group, group_faces, solids, warnings)
        except Exception as e:
            warnings.append('decor %d (%s) failed: %s' % (order, t, e))
    return mb, mats, anchor


def region_test(p):
    """Return f(x,y)->bool for a pattern part's 2D region (image coords)."""
    t = p['t']
    if t in ('spot', 'e'):
        cx, cy = float(p['x']), float(p['y'])
        rx = float(p.get('rx', 2) or 2)
        ry = float(p.get('ry', rx) or rx)
        rot = math.radians(float(p.get('rot', 0) or 0))
        c, s = math.cos(rot), math.sin(rot)

        def f(x, y):
            dx, dy = x - cx, y - cy
            u = (dx * c + dy * s) / rx
            v = (-dx * s + dy * c) / ry
            return u * u + v * v <= 1.0
        return f
    if t in ('stripe', 'l', 'c'):
        if t == 'c':
            r1 = float(p.get('r1', 2))
            segs = [(p['x1'], p['y1'], p['x2'], p['y2'], r1, float(p.get('r2', r1)))]
        else:
            pts = poly_pairs(p['pts'])
            w1 = float(p.get('w', 2) or 2)
            w2 = float(p['w2']) if p.get('w2') is not None else w1
            segs = polyline_segments(pts, w1, w2)

        def f(x, y):
            for ax, ay, bx, by, ra, rb in segs:
                tt, d = seg_query(x, y, ax, ay, bx, by)
                if d <= ra + (rb - ra) * tt:
                    return True
            return False
        return f
    if t == 'p':
        pts = poly_pairs(p['pts'])
        return lambda x, y: point_in_poly(x, y, pts)
    return lambda x, y: False


def add_pattern(mb, mats, p, pal, by_group, group_faces, solids, warnings):
    col = resolve_color(p.get('c'), pal)
    mi = mats.get(col)
    on = p.get('on')
    inside = region_test(p)
    front_only = bool(p.get('face') or p.get('frontOnly'))
    back_only = bool(p.get('backOnly'))
    faces = group_faces.get(on, [])
    n = 0
    for f in faces:
        if not f.is_valid:
            continue
        c = f.calc_center_median()
        nrm = f.normal
        if front_only and nrm.y > 0.15:
            continue
        if back_only and nrm.y < -0.15:
            continue
        if inside(c.x + 32.0, 60.0 - c.z):
            f.material_index = mi
            n += 1
    if n:
        return
    # nothing to clip onto (group missing or too coarse) -> small raised blob/tube instead
    targets = by_group.get(on) or solids
    back = back_only
    gname = on if on in by_group else None
    t = p['t']
    if t in ('spot', 'e'):
        x, y = float(p['x']), float(p['y'])
        rx = float(p.get('rx', 2) or 2)
        ry = float(p.get('ry', rx) or rx)
        P, nrm, who = surface_frame(targets, x, y, back)
        if P is None:
            P, nrm, who = surface_frame(solids, x, y, back)
        if P is None:
            return
        d = max(0.3, 0.2 * min(rx, ry))
        mb.ellipsoid(P + nrm * (d * 0.3), (rx, d, ry), mi, gname or who.g, orient=orient_to(nrm))
    elif t in ('stripe', 'l'):
        pts = poly_pairs(p['pts'])
        w = float(p.get('w', 2) or 2)
        P3, rad, g = [], [], gname
        for x, y in pts:
            P, nrm, who = surface_frame(targets, x, y, back)
            if P is None:
                P, nrm, who = surface_frame(solids, x, y, back)
            if P is None:
                continue
            g = g or who.g
            P3.append(P + nrm * (w * 0.1))
            rad.append(w * 0.5)
        if len(P3) >= 2:
            mb.tube(P3, rad, mi, g)
    elif t == 'p':
        warnings.append('clipped polygon on %s found no faces' % on)


def add_eye(mb, mats, p, pal, solids):
    x, y = float(p['x']), float(p['y'])
    s = max(1.0, float(p.get('s', 3) or 3))
    P, n, who = surface_frame(solids, x, y)
    if P is None:
        P, n, who = Vector((x - 32, -s, 60 - y)), Vector((0, -1, 0)), None
    g = who.g if who else '_eyes'
    R = orient_to(n)
    style = p.get('style') or 'round'
    dark = mats.get(DARK, roughness=0.3)
    if style in ('closed', 'happy'):
        mb.ellipsoid(P + n * (0.1 * s), (1.2 * s, 0.25 * s, 0.28 * s), dark, g, orient=R, segs=(12, 8))
        return
    if style == 'dot':
        r = max(0.7, s * 0.45)
        mb.ellipsoid(P + n * (0.15 * r), (r, 0.55 * r, r), dark, g, orient=R, segs=(10, 7))
        return
    rx = max(1.0, s * float(p.get('wide', 0.75) or 0.75))
    ry = max(1.2, s)
    off = Vector((0, 0, 0))
    if style == 'sleepy':
        ry *= 0.55
        off = R @ Vector((0, 0, -0.35 * s))
    sclera = p.get('sclera', True) is not False
    base = P + off + n * (0.05 * s)
    if sclera:
        mb.ellipsoid(base, (rx, 0.38 * s, ry), mats.get(WHITE, roughness=0.25), g, orient=R, segs=(14, 9))
    else:
        mb.ellipsoid(base, (rx, 0.38 * s, ry), dark, g, orient=R, segs=(14, 9))
    lk = p.get('look') or [0, 0]
    pr = max(0.5, min(rx, ry) * 0.62)
    local = Vector((lk[0] * rx * 0.35, 0, -lk[1] * ry * 0.3))
    pc = base + R @ local + n * (0.3 * s)
    iris = p.get('iris')
    if iris:
        mb.ellipsoid(pc, (pr, 0.2 * s, pr), mats.get(resolve_color(iris, pal), roughness=0.3), g, orient=R, segs=(10, 7))
        mb.ellipsoid(pc + n * (0.12 * s), (pr * 0.55, 0.15 * s, pr * 0.55), dark, g, orient=R, segs=(8, 6))
    elif sclera:
        mb.ellipsoid(pc, (pr, 0.2 * s, pr), dark, g, orient=R, segs=(10, 7))
    if style == 'angry':  # brow: dark slanted bar over the eye
        sg = -1 if p.get('flip') else 1
        a = P + R @ Vector((-rx * 1.0, 0, ry * (0.75 + 0.35 * sg)))
        b = P + R @ Vector((rx * 1.0, 0, ry * (0.75 - 0.35 * sg)))
        mb.tube([a + n * (0.3 * s), b + n * (0.3 * s)], [0.35 * s, 0.3 * s], dark, g, nseg=8)


def add_mouth(mb, mats, p, pal, solids):
    x, y = float(p['x']), float(p['y'])
    w = max(1.0, float(p.get('w', 4) or 4))
    st = p.get('style') or 'smile'
    mc = mats.get(resolve_color(p['c'], pal) if p.get('c') else DARK, roughness=0.4)

    def on_surface(xx, yy, lift):
        P, n, who = surface_frame(solids, xx, yy)
        if P is None:
            return Vector((xx - 32, -1, 60 - yy)), Vector((0, -1, 0)), None
        return P + n * lift, n, who
    if st in ('open', 'fang', 'tongue'):
        hgt = max(2.0, w * 0.9)
        P, n, who = on_surface(x, y + hgt * 0.5, 0.1)
        g = who.g if who else '_mouth'
        R = orient_to(n)
        mb.ellipsoid(P, (w, 0.35 * w, hgt * 0.55), mats.get('#8a2838', roughness=0.5), g, orient=R, segs=(12, 8))
        if st == 'tongue' or st == 'open':
            mb.ellipsoid(P + R @ Vector((0, 0, -hgt * 0.2)) + n * 0.2, (w * 0.55, 0.25 * w, hgt * 0.25),
                         mats.get('#e8687a', roughness=0.5), g, orient=R, segs=(10, 6))
        if st == 'fang':
            for sx in (-1, 1):
                mb.ellipsoid(P + R @ Vector((sx * (w - 1) * 0.8, 0, hgt * 0.25)) + n * 0.25,
                             (0.45, 0.3, 0.8), mats.get(WHITE, roughness=0.3), g, orient=R, segs=(8, 6))
        return
    if st == 'line':
        prof = [(-w, 0.0), (0.0, 0.0), (w, 0.0)]
    elif st == 'frown':
        prof = [(i * w / 3.0, (i * i) / 9.0 * (w * 0.5) - w * 0.5) for i in range(-3, 4)]
    else:  # smile and unknown styles
        prof = [(i * w / 3.0, -(i * i) / 9.0 * (w * 0.5)) for i in range(-3, 4)]
    pts, g = [], None
    for dx, dy in prof:
        P, n, who = on_surface(x + dx, y + dy, 0.15)
        pts.append(P)
        if g is None and who is not None:
            g = who.g
    mb.tube(pts, [0.5] * len(pts), mc, g or '_mouth', nseg=8)


def build_fallback(name, defn):
    pal = defn.get('pal', {}) or {}
    cols = [v for v in pal.values() if isinstance(v, str)] or ['#a0a0a0']
    mats = C.MaterialCache('mat')
    mb = C.MeshBuilder()
    mb.ellipsoid((0, 0, 14), (12, 11, 14), mats.get(cols[0]), 'body')
    mb.ellipsoid((0, -2, 32), (9, 8.5, 8.5), mats.get(cols[min(1, len(cols) - 1)]), 'head')
    for sx in (-1, 1):
        mb.ellipsoid((sx * 3.5, -8.5, 34), (1.6, 0.8, 2.0), mats.get(DARK), 'head', segs=(10, 7))
    mb.tube([(-6, 0, 6), (-6, 0, 0.5)], [3.5, 3], mats.get(cols[0]), 'legL')
    mb.tube([(6, 0, 6), (6, 0, 0.5)], [3.5, 3], mats.get(cols[0]), 'legR')
    return mb, mats, None


# ============================================================================ rig + export
HEAD_EXCLUDE = ('body', 'leg', 'arm', 'tail', 'wing', 'foot', 'hand', 'shell', 'belly', 'torso')


def finalize(name, mb, mats, sp, out_path):
    mb.finish()
    lo, hi = mb.bbox()
    H_px = max(hi.z - lo.z, 1e-3)
    target = ht_metres(sp)
    k = target / H_px
    cx, cy = (lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5
    zshift = lo.z if lo.z < 4.0 else 0.0     # keep genuine hovering (ghosts, floaters)
    mb.transform(lambda co: Vector(((co.x - cx) * k, (co.y - cy) * k, (co.z - zshift) * k)))

    # per-group statistics (metres) for bone placement
    stats = {}
    grp = mb.grp
    for v in mb.bm.verts:
        g = mb.groups[v[grp]]
        s = stats.setdefault(g, [Vector((0, 0, 0)), 0, [], ])
        s[0] += v.co
        s[1] += 1
        s[2].append(v.co.copy())
    cent = {g: s[0] / s[1] for g, s in stats.items() if s[1]}
    body_c = cent.get('body')
    if body_c is None:
        body_c = max(stats.items(), key=lambda kv: kv[1][1])[0]
        body_c = cent[body_c]
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
        limb = C.is_leg(g) or C.is_arm(g) or C.is_wing(g) or C.is_tail(g) or C._has(g, 'claw', 'fin')
        if limb:
            pts = stats[g][2]
            near = min(pts, key=lambda v: (v - body_c).length)
            pivot = near.lerp(c, 0.3)
        else:
            pivot = c
        parent = None
        if head and g != head and head_box and not C._has(g, *HEAD_EXCLUDE):
            lo_, hi_ = head_box
            if all(lo_[i] <= c[i] <= hi_[i] for i in (0, 2)):
                parent = head
        bname = g if g != 'root' else 'root_grp'
        bones.append({'name': bname, 'head': pivot, 'parent': parent, 'length': target * 0.12})
        gb[bname] = {'pivot': pivot, 'x': c.x}
    obj = mb.to_object(name, mats.mats)
    if 'root' in obj.vertex_groups:
        obj.vertex_groups['root'].name = 'root_grp'
    arm = C.build_armature(name, bones, root_len=target * 0.25)
    C.skin_to_armature(obj, arm)
    C.animate_generic(arm, gb, target)
    C.export_glb(out_path)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    return {'height_m': round(target, 3), 'groups': len(gb), 'tris': tris, 'materials': len(mats.mats)}


# ============================================================================ main
def main():
    args = C.parse_args()
    only = None
    if '--only' in args:
        only = set(args[args.index('--only') + 1].split(','))
    out_dir = args[args.index('--out') + 1] if '--out' in args else OUT_DIR
    C.ensure_dir(out_dir)
    mons = json.load(open(os.path.join(EXTRACTED, 'mons.json')))
    pdata = json.load(open(os.path.join(EXTRACTED, 'pokedata.json')))['species']
    species = [s for s in mons if s in pdata]
    species.sort(key=lambda s: pdata[s].get('dex', 999))
    if only:
        species = [s for s in species if s in only]
    manifest = {'generated': [], 'fallback': [], 'errors': {}, 'warnings': {}, 'species': {}}
    t_all = time.time()
    for i, name in enumerate(species):
        t0 = time.time()
        out_path = os.path.join(out_dir, name + '.glb')
        warnings = []
        status = 'generated'
        try:
            C.reset_scene()
            mb, mats, _ = build_species(name, mons[name], pdata[name], warnings)
            info = finalize(name, mb, mats, pdata[name], out_path)
        except Exception as e:
            status = 'fallback'
            manifest['errors'][name] = '%s: %s' % (type(e).__name__, e)
            traceback.print_exc()
            C.reset_scene()
            mb, mats, _ = build_fallback(name, mons[name])
            info = finalize(name, mb, mats, pdata[name], out_path)
        manifest[status].append(name)
        if warnings:
            manifest['warnings'][name] = warnings
        info['file'] = name + '.glb'
        info['bytes'] = os.path.getsize(out_path)
        info['status'] = status
        manifest['species'][name] = info
        print('[%3d/%d] %-12s %-9s %5.2fs  h=%.2fm groups=%d tris=%d mats=%d %s' % (
            i + 1, len(species), name, status, time.time() - t0, info['height_m'], info['groups'],
            info['tris'], info['materials'], ('warn=%d' % len(warnings)) if warnings else ''), flush=True)
    manifest['animations'] = {'Idle': {'seconds': 2.0, 'loop': True}, 'Walk': {'seconds': 0.8, 'loop': True},
                              'Attack': {'seconds': 0.5, 'loop': False}}
    manifest['conventions'] = {
        'units': 'metres; model height == Pokedex height (min 0.15 m)',
        'front': 'Blender -Y == glTF/Godot +Z (MODEL_FRONT)',
        'origin': 'bottom centre; hovering species keep their hover gap',
        'rig': "one bone per 2D art group, all under 'root'; face features parented to 'head' when present",
    }
    manifest['elapsed_seconds'] = round(time.time() - t_all, 1)
    if only is None:
        with open(os.path.join(out_dir, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=1, sort_keys=False)
    print('DONE generated=%d fallback=%d in %.1fs' % (len(manifest['generated']), len(manifest['fallback']),
                                                     time.time() - t_all))


if __name__ == '__main__':
    main()

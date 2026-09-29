"""3D set dressing for the battle stages (vertex-colour props in real metres, front = Blender -Y, pivot = ground)."""
import math
import random

from mathutils import Matrix, Vector

import env_kit as K
from env_kit import Prop, hx
import env_props as EP

K.MATS.update({
    'b_leaf': ([hx(c) for c in ('#2a6a34', '#3c8a3c', '#58a846', '#78c458', '#a0e078')], 'turf', 0),
    'b_blade': ([hx(c) for c in ('#2f7a3a', '#48a043', '#6cbf4c', '#9dd95f', '#cdef82')], 'turf', 0),
    'crystal_c': ([hx(c) for c in ('#1e6a9a', '#2e94c8', '#5ac8f0', '#9aeaff', '#e6ffff')], None, 255),
    'crystal_p': ([hx(c) for c in ('#5a2a8a', '#8a44c0', '#b874f0', '#dcaaff', '#ffffff')], None, 255),
    'flame': ([hx(c) for c in ('#c8401c', '#f0781c', '#ffac28', '#ffd860', '#fff4b0')], None, 255),
    'snow': ([hx(c) for c in ('#9ab8d8', '#c4dcf0', '#e4f2fc', '#f4fbff', '#ffffff')], None, 255),
    'ice': ([hx(c) for c in ('#3e78a8', '#6aa8d0', '#9ad0ee', '#cdeaff', '#f4fcff')], None, 255),
    'shell': ([hx(c) for c in ('#c89a88', '#e0b8a4', '#f4d2c0', '#fce6d8', '#ffffff')], None, 255),
    'palm': ([hx(c) for c in ('#1c5a2c', '#2a7a38', '#3c9a44', '#5cb85a', '#8ad470')], 'turf', 0),
    'fern': ([hx(c) for c in ('#0f3a24', '#185030', '#237040', '#369050', '#5ab66a')], 'turf', 0),
    'shroom': ([hx(c) for c in ('#8a2a3a', '#b8404c', '#dc5a5c', '#f08a80', '#ffc0b0')], None, 255),
    'linen': ([hx(c) for c in ('#a09080', '#c8b8a4', '#e4d8c4', '#f4ecdc', '#ffffff')], None, 255),
    'steel': ([hx(c) for c in ('#1c2029', '#343c48', '#56606e', '#8a96a6', '#c0ccdc')], None, 255),
    'warn': ([hx(c) for c in ('#8a5a08', '#c8880c', '#f0b820', '#ffd84a', '#fff0a0')], None, 255),
    'lamp_red': ([hx(c) for c in ('#5a0c0c', '#a01818', '#e02c2c', '#ff6c5c', '#ffc0b0')], None, 255),
})


def _mk(name, seed=1):
    return Prop(name, 'vcol', seed=seed)


def tuft(seed=1, h=0.55):
    P = _mk('tuft', seed)
    rs = random.Random(seed)
    for i in range(8):
        a = rs.random() * math.tau
        r = rs.random() * 0.09
        P.blade(math.cos(a) * r, math.sin(a) * r, h * (0.6 + rs.random() * 0.5), 0.07, (rs.random() - 0.5) * 0.24, 'b_blade', lean_y=(rs.random() - 0.5) * 0.1, ao=False, bias=1 if i % 3 else 2)
    return P


def bush(seed=1, s=1.0):
    P = _mk('bush', seed)
    P.blob((0.0, 0.0, 0.36 * s), (0.5 * s, 0.42 * s, 0.34 * s), 'b_leaf', subdiv=2, jag=0.22, seed=seed, squash_below=0.02, bias=1)
    P.blob((-0.36 * s, -0.06 * s, 0.28 * s), (0.28 * s, 0.26 * s, 0.24 * s), 'b_leaf', subdiv=1, jag=0.25, seed=seed + 1, squash_below=0.02)
    P.blob((0.38 * s, -0.04 * s, 0.3 * s), (0.28 * s, 0.26 * s, 0.26 * s), 'b_leaf', subdiv=1, jag=0.25, seed=seed + 2, squash_below=0.02)
    P.blob((-0.1 * s, -0.18 * s, 0.56 * s), (0.22 * s, 0.18 * s, 0.14 * s), 'b_leaf', subdiv=1, jag=0.25, seed=seed + 3, ao=False, bias=1)
    return P


def fern(seed=1):
    P = _mk('fern', seed)
    rs = random.Random(seed)
    for i in range(9):
        a = i * math.tau / 9 + rs.random() * 0.4
        L = 0.55 + rs.random() * 0.3
        dx, dy = math.cos(a), math.sin(a)
        prev = (0.0, 0.0, 0.05)
        for seg in range(3):
            t = (seg + 1) / 3
            cur = (dx * L * t, dy * L * t, 0.05 + math.sin(t * math.pi * 0.8) * 0.28 * (1 - t * 0.3))
            w = 0.09 * (1 - t * 0.75)
            nx, ny = -dy, dx
            for side in (0, 1):
                v = [Vector((prev[0] - nx * w, prev[1] - ny * w, prev[2])), Vector((prev[0] + nx * w, prev[1] + ny * w, prev[2])),
                     Vector((cur[0] + nx * w * 0.6, cur[1] + ny * w * 0.6, cur[2])), Vector((cur[0] - nx * w * 0.6, cur[1] - ny * w * 0.6, cur[2]))]
                if side:
                    v = v[::-1]
                P.quad(*v, 'fern', ao=False, bias=1 if seg == 2 else 0)
            prev = cur
    return P


def mushroom(seed=1):
    P = _mk('mushroom', seed)
    P.cyl(0, 0, 0, 0.16, 0.05, 0.04, 'linen', seg=6, cap_top=False)
    P.lathe(0, 0, [(0.06, 0.15), (0.16, 0.19), (0.19, 0.24), (0.13, 0.3), (0.0, 0.32)], 'shroom', seg=8, ao=False)
    for k in range(3):
        a = k * 2.1 + seed
        P.blob((math.cos(a) * 0.09, math.sin(a) * 0.08 - 0.02, 0.29), (0.025, 0.025, 0.012), 'linen', subdiv=0, ao=False)
    return P


def log(seed=1):
    P = _mk('log', seed)
    P.transform_all(Matrix.Identity(4))
    b = P.bm
    import bmesh
    seg = 9
    rings = []
    for x, r in ((-0.8, 0.21), (0.8, 0.22)):
        ring = [b.verts.new((x, math.cos(2 * math.pi * i / seg) * r, 0.2 + math.sin(2 * math.pi * i / seg) * r)) for i in range(seg)]
        rings.append(ring)
    fs = []
    for i in range(seg):
        j = (i + 1) % seg
        fs.append(b.faces.new((rings[0][i], rings[1][i], rings[1][j], rings[0][j])))
    fs.append(b.faces.new(list(reversed(rings[0]))))
    fs.append(b.faces.new(rings[1]))
    bmesh.ops.recalc_face_normals(b, faces=fs)
    P.paint(fs, 'bark')
    P.blob((-0.1, 0.02, 0.4), (0.4, 0.13, 0.05), 'moss', subdiv=1, jag=0.3, seed=seed, ao=False)
    return P


def trunk(h=4.2, seed=1, r=0.24):
    P = _mk('trunk', seed)
    P.lathe(0, 0, [(r * 1.6, 0.0), (r * 1.1, 0.25), (r, 0.8), (r * 0.9, h)], 'bark', seg=8, rot=seed)
    return P


def stalagmite(seed=1, h=1.0):
    P = _mk('stalagmite', seed)
    rs = random.Random(seed)
    for i in range(3):
        a = rs.random() * math.tau
        hh = h * (0.45 + rs.random() * 0.6) if i else h
        r = 0.16 + rs.random() * 0.08
        P.cone(math.cos(a) * 0.14 * (i > 0), math.sin(a) * 0.14 * (i > 0), 0, hh, r, 'rock', seg=6)
    return P


def crystal(kind='c', seed=1, h=0.9):
    m = 'crystal_' + kind
    P = _mk('crystal', seed)
    rs = random.Random(seed)
    for i in range(5):
        a = rs.random() * math.tau
        d = 0.05 + rs.random() * 0.2 if i else 0
        hh = h * (0.5 + rs.random() * 0.6) if i else h
        r = 0.055 + rs.random() * 0.05
        cx, cy = math.cos(a) * d, math.sin(a) * d
        lean = (rs.random() - 0.5) * 0.3
        P.cyl(cx, cy, 0, hh * 0.72, r, r * 0.9, m, seg=6, cap_top=False, ao=False)
        P.cone(cx, cy, hh * 0.72, hh, r * 0.9, m, seg=6, ao=False, bias=1)
    return P


def snow_mound(seed=1):
    P = _mk('snow_mound', seed)
    P.blob((0, 0, 0.0), (0.55, 0.42, 0.28), 'snow', subdiv=1, jag=0.12, seed=seed, squash_below=0.0, ao=False)
    return P


def ice_shards(seed=1, h=1.1):
    P = _mk('ice_shards', seed)
    rs = random.Random(seed)
    for i in range(5):
        a = rs.random() * math.tau
        d = 0.05 + rs.random() * 0.22 if i else 0
        hh = h * (0.4 + rs.random() * 0.7) if i else h
        P.cone(math.cos(a) * d, math.sin(a) * d, 0, hh, 0.09 + rs.random() * 0.07, 'ice', seg=5, ao=False, bias=1)
    return P


def rock(seed=1, s=0.5, mat='rock'):
    P = _mk('rock', seed)
    P.blob((0, 0, s * 0.45), (s, s * 0.8, s * 0.55), mat, subdiv=1, jag=0.3, seed=seed, squash_below=0.02, bias=1)
    P.blob((s * 0.7, -s * 0.2, s * 0.22), (s * 0.5, s * 0.4, s * 0.3), mat, subdiv=1, jag=0.3, seed=seed + 5, squash_below=0.02, bias=1)
    return P


def spire(seed=1, h=3.2, mat='cliff'):
    P = _mk('spire', seed)
    rs = random.Random(seed)
    for i in range(3):
        d = 0.0 if i == 0 else 0.5 + rs.random() * 0.2
        a = rs.random() * math.tau
        hh = h * (1 if i == 0 else 0.45 + rs.random() * 0.3)
        r = 0.55 if i == 0 else 0.35
        P.cyl(math.cos(a) * d, math.sin(a) * d, 0, hh * 0.65, r, r * 0.55, mat, seg=6, cap_top=False, rot=rs.random(), bias=1)
        P.cone(math.cos(a) * d, math.sin(a) * d, hh * 0.65, hh, r * 0.55, mat, seg=6, bias=1)
    return P


def column(h=3.9, r=0.3, mat='stone', seed=1):
    P = _mk('column', seed)
    P.box((-r * 1.5, -r * 1.5, 0), (r * 1.5, r * 1.5, 0.22), mat, bevel=0.02)
    P.lathe(0, 0, [(r * 1.15, 0.22), (r, 0.3), (r, h - 0.42), (r * 1.1, h - 0.32)], mat, seg=10, rot=0.3)
    for k in range(10):
        a = k * math.tau / 10 + 0.3
        P.box((math.cos(a) * r * 0.98 - 0.012, math.sin(a) * r * 0.98 - 0.012, 0.3), (math.cos(a) * r * 0.98 + 0.012, math.sin(a) * r * 0.98 + 0.012, h - 0.45), mat, flat_idx=1, ao=False) if math.sin(a) < 0.3 else None
    P.box((-r * 1.6, -r * 1.6, h - 0.32), (r * 1.6, r * 1.6, h - 0.1), mat, bevel=0.02)
    P.box((-r * 1.8, -r * 1.8, h - 0.1), (r * 1.8, r * 1.8, h), mat, bevel=0.02, bias=1)
    return P


def candelabra(seed=1):
    P = _mk('candelabra', seed)
    P.lathe(0, 0, [(0.2, 0.0), (0.18, 0.05), (0.06, 0.12), (0.04, 0.9), (0.09, 0.96), (0.03, 1.02)], 'gold', seg=8, ao=False)
    for sx in (-1, 0, 1):
        x = sx * 0.28
        if sx:
            P.box((min(0, x) - 0.015 * 0, -0.015, 0.94), (max(0, x) + 0.0, 0.015, 0.975), 'gold', ao=False)
        P.cyl(x, 0, 0.975, 1.18, 0.028, 0.028, 'linen', seg=5, cap_top=True, ao=False)
    return P


def flame(scale=1.0):
    P = _mk('flame')
    P.blob((0, 0, 0.09 * scale), (0.05 * scale, 0.05 * scale, 0.1 * scale), 'flame', subdiv=1, ao=False, bias=0, flat_idx=3)
    P.cone(0, 0, 0.14 * scale, 0.27 * scale, 0.035 * scale, 'flame', seg=5, ao=False, flat_idx=4)
    return P


def generator(seed=1):
    P = _mk('generator', seed)
    P.box((-0.7, -0.5, 0), (0.7, 0.5, 1.05), 'steel', bevel=0.04)
    P.box((-0.74, -0.54, 0.95), (0.74, 0.54, 1.1), 'steel', bevel=0.03, bias=1)
    for i in range(6):
        P.box((-0.55, -0.515, 0.2 + i * 0.09), (0.05, -0.49, 0.25 + i * 0.09), 'dark', ao=False)
    P.blob((0.4, -0.52, 0.72), (0.09, 0.03, 0.09), 'lamp_red', subdiv=1, flat_idx=3, ao=False)
    P.blob((0.4, -0.52, 0.45), (0.09, 0.03, 0.09), 'warn', subdiv=1, flat_idx=3, ao=False)
    P.cyl(-0.4, 0.2, 1.1, 1.6, 0.09, 0.09, 'steel', seg=8, cap_top=True)
    return P


def palm(seed=1, h=4.2):
    P = _mk('palm', seed)
    rs = random.Random(seed)
    lean = (rs.random() - 0.5) * 1.2
    pts = []
    n = 5
    for i in range(n + 1):
        t = i / n
        pts.append((lean * t * t * 0.9, 0.0, h * t))
    for i in range(n):
        r0 = 0.2 * (1 - i / n * 0.45)
        r1 = 0.2 * (1 - (i + 1) / n * 0.45)
        a, b = pts[i], pts[i + 1]
        seg = 6
        import bmesh
        bm = P.bm
        ra = [bm.verts.new((a[0] + math.cos(2 * math.pi * k / seg) * r0, math.sin(2 * math.pi * k / seg) * r0, a[2])) for k in range(seg)]
        rb = [bm.verts.new((b[0] + math.cos(2 * math.pi * k / seg) * r1, math.sin(2 * math.pi * k / seg) * r1, b[2])) for k in range(seg)]
        fs = [bm.faces.new((ra[k], ra[(k + 1) % seg], rb[(k + 1) % seg], rb[k])) for k in range(seg)]
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        P.paint(fs, 'bark', flat_idx=None, bias=-1 if i % 2 else 0)
    top = pts[-1]
    for k in range(9):
        a = k * math.tau / 9 + rs.random() * 0.3
        dx, dy = math.cos(a), math.sin(a)
        L = 1.7 + rs.random() * 0.5
        prev = (top[0], top[1], top[2])
        for seg in range(4):
            t = (seg + 1) / 4
            cur = (top[0] + dx * L * t, top[1] + dy * L * t * 0.7, top[2] + math.sin(t * 2.1) * 0.6 - t * t * 0.7)
            w = 0.25 * (1 - t * 0.85)
            nx, ny = -dy, dx
            for side in (0, 1):
                v = [Vector((prev[0] - nx * w, prev[1] - ny * w, prev[2])), Vector((prev[0] + nx * w, prev[1] + ny * w, prev[2])),
                     Vector((cur[0] + nx * w * 0.7, cur[1] + ny * w * 0.7, cur[2])), Vector((cur[0] - nx * w * 0.7, cur[1] - ny * w * 0.7, cur[2]))]
                if side:
                    v = v[::-1]
                P.quad(*v, 'palm', ao=False, bias=(k % 2))
            prev = cur
    for k in range(3):
        a = k * 2.1
        P.blob((top[0] + math.cos(a) * 0.14, math.sin(a) * 0.14, top[2] - 0.15), (0.11, 0.11, 0.13), 'wood', subdiv=1, ao=False, seed=k)
    return P


def shell(seed=1):
    P = _mk('shell', seed)
    P.lathe(0, 0, [(0.001, 0.0), (0.09, 0.02), (0.11, 0.06), (0.06, 0.11), (0.001, 0.13)], 'shell', seg=6, ao=False)
    return P


def sea_rock(seed=1, s=0.8):
    P = rock(seed, s, 'rock')
    # foam collar
    P.lathe(0, 0, [(s * 1.5, 0.0), (s * 1.6, 0.02), (s * 1.3, 0.05), (s * 1.1, 0.02)], 'foam', seg=10, ao=False)
    return P


def urn(seed=1):
    P = _mk('urn', seed)
    P.lathe(0, 0, [(0.12, 0.0), (0.2, 0.15), (0.23, 0.3), (0.16, 0.5), (0.1, 0.6), (0.16, 0.66)], 'terracotta', seg=8)
    return P


def bench(seed=1):
    P = _mk('bench', seed)
    P.box((-0.9, -0.2, 0.36), (0.9, 0.2, 0.44), 'wood', bevel=0.02)
    P.box((-0.9, 0.16, 0.44), (0.9, 0.2, 0.85), 'wood', bevel=0.02)
    for sx in (-0.8, 0.8):
        P.box((sx - 0.04, -0.16, 0), (sx + 0.04, 0.16, 0.38), 'wood_dark', bevel=0.01)
    return P


def grave_row(seed=1):
    return EP.p_grave_a('vcol') if seed % 2 else EP.p_grave_b('vcol')


def cable_coil(seed=1):
    P = _mk('coil', seed)
    for i in range(3):
        P.lathe(0, 0, [(0.34, i * 0.09), (0.4, i * 0.09 + 0.02), (0.4, i * 0.09 + 0.07), (0.34, i * 0.09 + 0.09)], 'dark', seg=10, ao=False)
    P.cyl(0, 0, 0.0, 0.28, 0.3, 0.3, 'dark', seg=10, cap_top=True, ao=False)
    return P


def candle_cluster(seed=1):
    P = _mk('candles', seed)
    rs = random.Random(seed)
    for i in range(4):
        a = rs.random() * math.tau
        d = rs.random() * 0.14 if i else 0.0
        h = 0.34 if i == 0 else 0.16 + rs.random() * 0.2
        P.cyl(math.cos(a) * d, math.sin(a) * d, 0, h, 0.04, 0.038, 'linen', seg=5, cap_top=True, ao=False)
        P.blob((math.cos(a) * d, math.sin(a) * d, h + 0.01), (0.07, 0.07, 0.02), 'linen', subdiv=0, ao=False)
    P.lathe(0, 0, [(0.001, 0.0), (0.16, 0.0), (0.18, 0.02)], 'dark', seg=8, ao=False)
    return P

"""Modular environment kit pieces (tiles + furniture/props), built with env_kit.Prop.

1 m footprint (sprite units), pivot bottom centre, front = Blender -Y.  Bevelled edges, layered silhouettes, baked AO in
the vertex colours.  gen_tiles.py exports each in the 'tex' style (seamless procedural textures from env_textures.py).
"""
import math
import random

from mathutils import Matrix

import env_kit as K
from env_kit import Prop
import env_props as EP


def _blades(P, n, seed, hmin, hmax, w, mat, area=0.46, bias=0, lean=0.06):
    rs = random.Random(seed)
    for i in range(n):
        x, y = rs.uniform(-area, area), rs.uniform(-area, area)
        P.blade(x, y, rs.uniform(hmin, hmax), w * rs.uniform(0.8, 1.3), (rs.random() - 0.5) * lean * 2, mat,
                lean_y=(rs.random() - 0.5) * lean, ao=True, bias=bias + (1 if i % 3 == 0 else 0))


# ------------------------------------------------------------------ ground tiles
def t_floor_grass(style):
    P = Prop('floor_grass', style, seed=101)
    P.box((-0.5, -0.5, -0.09), (0.5, 0.5, -0.02), 'soil', bevel=0.01)
    P.box((-0.5, -0.5, -0.03), (0.5, 0.5, 0.03), 'grass', bevel=0.014, ao=False)
    _blades(P, 60, 1, 0.07, 0.17, 0.04, 'blade')
    rs = random.Random(3)
    for i in range(6):
        x, y = rs.uniform(-0.4, 0.4), rs.uniform(-0.4, 0.4)
        P.cyl(x, y, 0.03, 0.045, 0.045, 0.035, 'moss', seg=5, ao=False)
    for i, (m, x, y) in enumerate((('white', -0.26, 0.2), ('yellow', 0.3, -0.24), ('pink', 0.12, 0.34))):
        P.box((x - 0.006, y - 0.006, 0.03), (x + 0.006, y + 0.006, 0.12), 'leaf', ao=False)
        P.cyl(x, y, 0.115, 0.14, 0.04, 0.03, m, seg=5, ao=False, bias=1)
    return P


def t_floor_path(style):
    P = Prop('floor_path', style, seed=102)
    P.box((-0.5, -0.5, -0.09), (0.5, 0.5, -0.02), 'soil', bevel=0.01)
    P.box((-0.5, -0.5, -0.03), (0.5, 0.5, 0.02), 'path', bevel=0.014, ao=False)
    for x in (-0.18, 0.18):     # wheel ruts
        P.box((x - 0.05, -0.5, 0.019), (x + 0.05, 0.5, 0.024), 'soil', ao=False)
    rs = random.Random(5)
    for i in range(12):
        s = rs.uniform(0.025, 0.055)
        P.blob((rs.uniform(-0.42, 0.42), rs.uniform(-0.42, 0.42), 0.02), (s, s * 0.85, s * 0.55), 'stone', subdiv=1, jag=0.2,
               seed=i, squash_below=0.015, ao=False)
    _blades(P, 10, 7, 0.05, 0.1, 0.035, 'blade', area=0.48)
    return P


def t_floor_pave(style):
    P = Prop('floor_pave', style, seed=103)
    P.box((-0.5, -0.5, -0.09), (0.5, 0.5, 0.0), 'stone', bevel=0.01)
    rs = random.Random(9)
    for ix in (-1, 1):
        for iy in (-1, 1):
            h = 0.03 + rs.uniform(-0.005, 0.008)
            P.box((ix * 0.25 - 0.226, iy * 0.25 - 0.226, -0.01), (ix * 0.25 + 0.226, iy * 0.25 + 0.226, h), 'pave', bevel=0.014, ao=False)
    P.blob((-0.4, 0.4, 0.015), (0.07, 0.06, 0.02), 'moss', subdiv=1, jag=0.3, seed=2, squash_below=0.01, ao=False)
    P.quad((0.02, -0.02, 0.034), (0.05, -0.02, 0.034), (0.28, 0.24, 0.034), (0.25, 0.24, 0.034), 'stone', flat_idx=0, ao=False)
    return P


def t_tallgrass(style):
    P = Prop('tallgrass', style, seed=104)
    P.box((-0.5, -0.5, -0.08), (0.5, 0.5, 0.0), 'soil', bevel=0.01)
    P.box((-0.5, -0.5, -0.02), (0.5, 0.5, 0.03), 'grass', bevel=0.012, ao=False)
    _blades(P, 74, 11, 0.28, 0.52, 0.06, 'blade', area=0.47, lean=0.09, bias=1)
    rs = random.Random(13)
    for i in range(5):
        x, y = rs.uniform(-0.4, 0.4), rs.uniform(-0.4, 0.4)
        P.box((x - 0.006, y - 0.006, 0.03), (x + 0.006, y + 0.006, 0.45), 'leaf', ao=False)
        P.blob((x, y, 0.47), (0.02, 0.02, 0.05), 'yellow', subdiv=0, ao=False)
    return P


def t_water(style):
    P = Prop('water', style, seed=105)
    P.box((-0.5, -0.5, -0.34), (0.5, 0.5, -0.24), 'sand', bevel=0.01)
    P.box((-0.5, -0.5, -0.24), (0.5, 0.5, -0.07), 'water', ao=False, flat_idx=1)
    P.box((-0.5, -0.5, -0.09), (0.5, 0.5, -0.05), 'water', ao=False, flat_idx=3)
    for r, z in ((0.16, -0.048), (0.3, -0.049)):     # ripple rings
        P.lathe(0.08, -0.05, [(r, z), (r + 0.018, z), (r + 0.018, z + 0.004), (r, z + 0.004)], 'foam', seg=14, ao=False, flat_idx=3)
    for (x, y) in ((-0.5, 0), (0.5, 0)):             # shoreline foam on the left/right edges
        P.box((x - 0.03 if x < 0 else x - 0.005, -0.5, -0.052), (x + 0.005 if x < 0 else x + 0.03, 0.5, -0.048), 'foam', ao=False, flat_idx=4)
    P.cyl(0.28, 0.25, -0.052, -0.046, 0.09, 0.09, 'leaf', seg=8, ao=False, cap_top=True, bias=1)
    P.cyl(-0.25, -0.3, -0.052, -0.046, 0.06, 0.06, 'leaf', seg=8, ao=False, cap_top=True, bias=1)
    return P


def t_tree(style):
    P = Prop('tree', style, seed=106)
    P.lathe(0, 0.02, [(0.2, 0.0), (0.15, 0.1), (0.12, 0.5), (0.1, 1.05)], 'bark', seg=8, rot=0.2)
    for ang, ln in ((0.6, 0.26), (2.5, 0.22), (4.4, 0.24)):     # root flare
        P.cone(math.cos(ang) * 0.13, math.sin(ang) * 0.13, 0.0, 0.11, 0.07, 'bark', seg=4)
    P.cyl(0.02, 0.0, 0.8, 1.15, 0.03, 0.02, 'bark', seg=5, cap_top=True, rx_scale=1.0)
    clumps = [((0.0, 0.0, 1.35), (0.62, 0.58, 0.5), 'leaf'), ((-0.32, 0.12, 1.1), (0.42, 0.4, 0.34), 'leaf'),
              ((0.34, -0.06, 1.16), (0.44, 0.42, 0.36), 'leaf'), ((0.05, -0.1, 1.72), (0.5, 0.46, 0.42), 'leaf_light'),
              ((-0.22, 0.05, 1.98), (0.32, 0.3, 0.3), 'leaf_light'), ((0.2, 0.0, 2.05), (0.3, 0.28, 0.28), 'leaf_light')]
    for k, (c, r, m) in enumerate(clumps):
        P.blob(c, r, m, subdiv=2, jag=0.2, seed=k + 20, squash_below=0.86 if k < 3 else None, ao=False, dark_below=(c[2] - r[2] * 0.2, 0.0))
    for k in range(6):
        a = k * 1.1
        P.blob((math.cos(a) * 0.44, math.sin(a) * 0.36 - 0.1, 1.55 + 0.13 * (k % 3)), (0.15, 0.14, 0.13), 'leaf_light', subdiv=1, jag=0.3, seed=k + 60, ao=False, bias=1)
    return P


def t_wall(style):
    P = Prop('wall', style, seed=107)
    P.box((-0.52, -0.52, 0.0), (0.52, 0.52, 0.09), 'stone', bevel=0.012)
    rs = random.Random(21)
    for c in range(3):
        z0, z1 = 0.09 + c * 0.28, 0.09 + (c + 1) * 0.28 - 0.012
        cuts = [-0.5, 0.0 + (0.18 if c % 2 else -0.18), 0.5]
        for a, b in zip(cuts[:-1], cuts[1:]):
            P.box((a + 0.006, -0.5 + rs.uniform(0, 0.012), z0), (b - 0.006, 0.5, z1), 'stone', bevel=0.014, ao=(c == 0))
    P.box((-0.54, -0.54, 0.93), (0.54, 0.54, 1.02), 'stone', bevel=0.02, bias=1)
    P.blob((-0.3, -0.5, 0.18), (0.14, 0.03, 0.09), 'moss', subdiv=1, jag=0.25, seed=4, ao=False)
    P.blob((0.36, -0.52, 0.5), (0.08, 0.02, 0.07), 'moss', subdiv=1, jag=0.25, seed=5, ao=False)
    return P


def t_building_wall(style):
    P = Prop('building_wall', style, seed=108)
    P.box((-0.51, -0.51, 0.0), (0.51, 0.51, 0.22), 'brick', bevel=0.012)
    P.box((-0.5, -0.5, 0.22), (0.5, 0.5, 1.14), 'plaster')
    for sx in (-1, 1):
        P.box((sx * 0.44 - 0.06, -0.535, 0.0), (sx * 0.44 + 0.06, -0.49, 1.16), 'wood_dark', bevel=0.01)
    P.box((-0.5, -0.525, 0.62), (0.5, -0.49, 0.68), 'wood_dark', bevel=0.008)
    P.box((-0.53, -0.54, 1.12), (0.53, -0.48, 1.22), 'wood', bevel=0.014, bias=1)
    P.box((-0.26, -0.52, 0.34), (0.26, -0.5, 0.56), 'glass', ao=False)
    P.box((-0.3, -0.545, 0.3), (0.3, -0.5, 0.34), 'paint', bevel=0.008, bias=1)
    return P


def t_roof(style):
    """Gable roof piece: ridge along X, 0.6 tall, shingle rows with lips, ridge cap, rake boards and fascia."""
    P = Prop('roof', style, seed=109)
    zt = 0.6
    P.prism(-0.5, 0.5, -0.5, 0.5, 0.0, zt, 'roof_red', ao=False)
    rows = 6
    for side in (-1, 1):
        for r in range(rows):
            t0, t1 = r / rows, (r + 1) / rows
            ya, za = side * (0.5 - 0.5 * t0), zt * t0
            yb, zb = side * (0.5 - 0.5 * t1), zt * t1
            P.poly_prism_x([(ya + side * 0.025, za + 0.014), (yb, zb + 0.002), (yb, zb - 0.03), (ya + side * 0.025, za - 0.03)],
                           -0.505, 0.505, 'roof_red', ao=False, bias=(1 if r % 2 else 0))
    P.box((-0.53, -0.05, zt - 0.03), (0.53, 0.05, zt + 0.045), 'roof_red', bevel=0.012, bias=2)
    for side in (-1, 1):
        for x0, x1 in ((-0.545, -0.5), (0.5, 0.545)):
            P.poly_prism_x([(side * 0.56, -0.02), (0.0, zt + 0.03), (0.0, zt - 0.02), (side * 0.56, -0.07)], x0, x1, 'wood', ao=False)
        P.box((-0.55, side * 0.56 - 0.02, -0.06), (0.55, side * 0.56 + 0.02, 0.02), 'wood_dark', bevel=0.006)
    return P


def t_door(style):
    P = Prop('door', style, seed=110)
    P.box((-0.5, -0.45, 0.0), (0.5, 0.5, 1.0), 'plaster')
    P.box((-0.36, -0.53, 0.0), (0.36, -0.44, 0.06), 'stone', bevel=0.012, bias=1)          # step
    P.box((-0.4, -0.52, 0.06), (-0.3, -0.46, 0.94), 'wood_dark', bevel=0.01)
    P.box((0.3, -0.52, 0.06), (0.4, -0.46, 0.94), 'wood_dark', bevel=0.01)
    P.box((-0.4, -0.52, 0.86), (0.4, -0.46, 0.96), 'wood_dark', bevel=0.01)                 # lintel
    for i in range(3):
        P.box((-0.3 + i * 0.2, -0.5, 0.06), (-0.11 + i * 0.2, -0.46, 0.86), 'wood', bevel=0.008, bias=0)
    for z in (0.22, 0.66):
        P.box((-0.3, -0.512, z), (0.3, -0.496, z + 0.05), 'wood_dark', bevel=0.005)
    for z in (0.2, 0.68):
        P.box((-0.315, -0.52, z), (-0.28, -0.49, z + 0.08), 'metal', bevel=0.004)
    P.box((-0.2, -0.508, 0.6), (0.06, -0.494, 0.78), 'glass', ao=False)
    P.cyl(0.21, -0.515, 0.42, 0.44, 0.03, 0.03, 'gold', seg=6, cap_top=True)
    P.box((-0.46, -0.6, 0.94), (0.46, -0.44, 0.99), 'roof_red', bevel=0.01, bias=1)     # little canopy
    return P


def t_counter(style):
    P = Prop('counter', style, seed=111)
    P.box((-0.5, -0.3, 0.0), (0.5, 0.3, 0.06), 'wood_dark', bevel=0.01)
    P.box((-0.5, -0.3, 0.06), (0.5, 0.3, 0.84), 'wood', bevel=0.014)
    for i in range(3):
        x = -0.33 + i * 0.33
        P.box((x - 0.13, -0.312, 0.16), (x + 0.13, -0.29, 0.7), 'wood_dark', bevel=0.008)
        P.box((x - 0.1, -0.318, 0.2), (x + 0.1, -0.3, 0.66), 'wood', bevel=0.006, bias=1)
    P.box((-0.55, -0.36, 0.84), (0.55, 0.34, 0.92), 'wood', bevel=0.02, bias=2)
    P.box((-0.5, -0.362, 0.83), (0.5, -0.34, 0.85), 'gold', bevel=0.004)
    return P


def t_ledge(style):
    P = Prop('ledge', style, seed=112)
    P.box((-0.5, -0.5, 0.0), (0.5, 0.5, 0.2), 'soil', bevel=0.012)
    for z in (0.06, 0.13):
        P.box((-0.5, -0.505, z), (0.5, -0.49, z + 0.02), 'path', ao=False)
    P.box((-0.51, -0.53, 0.19), (0.51, 0.51, 0.27), 'grass', bevel=0.03, ao=False)
    rs = random.Random(14)
    for i in range(6):
        x = -0.42 + i * 0.17 + rs.uniform(-0.02, 0.02)
        s = rs.uniform(0.05, 0.075)
        P.blob((x, -0.5, 0.11), (s, 0.045, s * 0.8), 'stone', subdiv=1, jag=0.2, seed=i, squash_below=0.02, ao=False)
    _blades(P, 26, 15, 0.05, 0.11, 0.04, 'blade', area=0.47)
    for i in range(4):
        x = -0.35 + i * 0.25
        P.cone(x, -0.42, 0.0, 0.1, 0.02, 'bark', seg=4)
    return P


def t_rock(style):
    P = EP.p_boulder(style)
    P.name = 'rock'
    return P


# ------------------------------------------------------------------ props that only live in the kit
def p_lamp_post(style):
    P = Prop('lamp_post', style, seed=120)
    P.cyl(0, 0, 0, 0.1, 0.16, 0.1, 'metal', seg=8, cap_top=True)
    P.lathe(0, 0, [(0.05, 0.1), (0.04, 0.3), (0.035, 1.35), (0.05, 1.4)], 'metal', seg=8)
    P.box((-0.13, -0.13, 1.4), (0.13, 0.13, 1.44), 'metal', bevel=0.01)
    P.box((-0.11, -0.11, 1.44), (0.11, 0.11, 1.72), 'glass', ao=False, flat_idx=4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.11 - 0.01, sy * 0.11 - 0.01, 1.44), (sx * 0.11 + 0.01, sy * 0.11 + 0.01, 1.72), 'metal')
    P.cone(0, 0, 1.72, 1.86, 0.18, 'metal', seg=4)
    P.blob((0, 0, 1.58), (0.06, 0.06, 0.1), 'yellow', subdiv=1, ao=False, flat_idx=4)
    return P


def p_mailbox(style):
    P = Prop('mailbox', style, seed=121)
    P.box((-0.035, -0.035, 0.0), (0.035, 0.035, 0.62), 'wood_dark', bevel=0.008)
    P.lathe(0, 0, [(0.001, 0.62), (0.15, 0.64), (0.17, 0.75), (0.1, 0.84), (0.001, 0.86)], 'blue', seg=10, ao=False)
    P.box((-0.17, -0.03, 0.66), (0.17, 0.02, 0.72), 'blue', bevel=0.006)
    P.box((0.16, -0.035, 0.75), (0.2, -0.015, 0.92), 'red', bevel=0.004)
    return P


def p_pc(style):
    P = Prop('pc', style, seed=122)
    P.box((-0.46, -0.32, 0.0), (0.46, 0.32, 0.5), 'metal', bevel=0.02)
    P.box((-0.4, -0.335, 0.08), (-0.06, -0.31, 0.44), 'metal', flat_idx=1, bevel=0.006)
    P.box((-0.46, -0.32, 0.5), (0.46, 0.32, 0.53), 'white', bevel=0.01)
    P.box((-0.3, -0.06, 0.53), (0.3, 0.1, 0.58), 'white', bevel=0.01)
    P.box((-0.3, 0.02, 0.58), (0.3, 0.1, 1.02), 'white', bevel=0.02)
    P.box((-0.25, 0.0, 0.64), (0.25, 0.022, 0.97), 'screen', ao=False, flat_idx=3)
    P.box((-0.26, -0.28, 0.53), (0.26, -0.12, 0.555), 'dark', bevel=0.006)
    return P


def p_shelf(style):
    P = Prop('shelf', style, seed=123)
    P.box((-0.5, -0.2, 0.0), (0.5, 0.2, 1.3), 'wood', bevel=0.01)
    for i in range(4):
        z = 0.06 + i * 0.3
        P.box((-0.46, -0.2, z), (0.46, 0.16, z + 0.03), 'wood_dark', bevel=0.005)
        rs = random.Random(30 + i)
        x = -0.44
        while x < 0.38:
            w = rs.uniform(0.04, 0.09)
            h = rs.uniform(0.15, 0.24)
            m = rs.choice(['red', 'blue', 'yellow', 'pink', 'white', 'leaf'])
            P.box((x, -0.16, z + 0.03), (x + w, 0.12, z + 0.03 + h), m, ao=False, bias=1)
            x += w + 0.008
    return P


def p_bed(style):
    P = Prop('bed', style, seed=124)
    P.box((-0.46, -0.9, 0.06), (0.46, 0.9, 0.26), 'wood', bevel=0.015)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.42 - 0.04, sy * 0.86 - 0.04, 0.0), (sx * 0.42 + 0.04, sy * 0.86 + 0.04, 0.08), 'wood_dark')
    P.box((-0.43, -0.86, 0.26), (0.43, 0.86, 0.34), 'white', bevel=0.02)
    P.box((-0.43, -0.2, 0.34), (0.43, 0.86, 0.4), 'blue', bevel=0.03)
    P.box((-0.33, -0.82, 0.34), (0.33, -0.42, 0.42), 'white', bevel=0.03, bias=1)
    P.box((-0.48, 0.86, 0.06), (0.48, 0.92, 0.62), 'wood_dark', bevel=0.012)
    P.box((-0.48, -0.94, 0.06), (0.48, -0.88, 0.42), 'wood_dark', bevel=0.012)
    return P


def p_table(style):
    P = Prop('table', style, seed=125)
    P.box((-0.5, -0.4, 0.5), (0.5, 0.4, 0.58), 'wood', bevel=0.02, bias=1)
    P.box((-0.42, -0.32, 0.44), (0.42, 0.32, 0.5), 'wood_dark', bevel=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.4 - 0.04, sy * 0.3 - 0.04, 0.0), (sx * 0.4 + 0.04, sy * 0.3 + 0.04, 0.5), 'wood_dark', bevel=0.008)
    return P


def p_chair(style):
    P = Prop('chair', style, seed=126)
    P.box((-0.22, -0.22, 0.26), (0.22, 0.22, 0.32), 'wood', bevel=0.012)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.19 - 0.025, sy * 0.19 - 0.025, 0.0), (sx * 0.19 + 0.025, sy * 0.19 + 0.025, 0.27), 'wood_dark')
    P.box((-0.22, 0.17, 0.32), (0.22, 0.22, 0.72), 'wood', bevel=0.012)
    P.box((-0.18, 0.15, 0.5), (0.18, 0.17, 0.62), 'wood_dark', bevel=0.008)
    return P


def p_bench(style):
    P = Prop('bench', style, seed=127)
    P.box((-0.5, -0.2, 0.34), (0.5, 0.2, 0.4), 'wood', bevel=0.012)
    P.box((-0.5, 0.16, 0.4), (0.5, 0.2, 0.78), 'wood', bevel=0.012)
    for sx in (-0.42, 0.42):
        P.box((sx - 0.04, -0.17, 0.0), (sx + 0.04, 0.17, 0.36), 'metal', bevel=0.008)
    return P


def p_window(style):
    P = Prop('window', style, seed=128)
    P.box((-0.5, -0.06, 0.0), (0.5, 0.06, 1.0), 'plaster')
    P.box((-0.34, -0.09, 0.3), (0.34, 0.0, 0.86), 'wood_dark', bevel=0.012)
    P.box((-0.28, -0.1, 0.36), (0.28, -0.01, 0.8), 'glass', ao=False, flat_idx=3)
    P.box((-0.015, -0.11, 0.36), (0.015, -0.02, 0.8), 'wood_dark')
    P.box((-0.28, -0.11, 0.57), (0.28, -0.02, 0.6), 'wood_dark')
    P.box((-0.4, -0.15, 0.25), (0.4, -0.04, 0.3), 'paint', bevel=0.01, bias=1)          # sill
    P.box((-0.34, -0.17, 0.16), (0.34, -0.08, 0.25), 'wood', bevel=0.008)               # flower box
    for i, m in enumerate(('red', 'pink', 'yellow', 'white', 'red')):
        P.blob((-0.27 + i * 0.135, -0.13, 0.27), (0.045, 0.04, 0.045), m, subdiv=1, seed=i, ao=False)
    for sx in (-1, 1):
        P.box((sx * 0.4 - 0.045, -0.1, 0.3), (sx * 0.4 + 0.045, -0.06, 0.86), 'blue', bevel=0.006)
    return P


def p_pillar(style):
    P = Prop('pillar', style, seed=129)
    P.box((-0.4, -0.4, 0.0), (0.4, 0.4, 0.14), 'stone', bevel=0.02)
    P.lathe(0, 0, [(0.3, 0.14), (0.26, 0.2), (0.24, 1.3), (0.28, 1.36)], 'stone', seg=10)
    P.box((-0.38, -0.38, 1.36), (0.38, 0.38, 1.5), 'stone', bevel=0.02, bias=1)
    return P


def p_podium(style):
    P = Prop('podium', style, seed=130)
    P.lathe(0, 0, [(0.5, 0.0), (0.5, 0.06), (0.42, 0.1), (0.42, 0.28), (0.46, 0.3), (0.46, 0.34), (0.001, 0.34)], 'stone', seg=8, rot=0.39)
    P.lathe(0, 0, [(0.4, 0.34), (0.36, 0.36), (0.001, 0.36)], 'gold', seg=8, rot=0.39, ao=False)
    return P


def p_fence_x_kit(style):
    P = EP.p_fence_x(style)
    P.name = 'fence'
    P.transform_all(Matrix.Identity(4))
    return P


TILES = [
    ('floor_grass', t_floor_grass, 'walkable ground: turf with blades, clover, flowers on an earth slab'),
    ('floor_path', t_floor_path, 'walkable ground: packed dirt with ruts and pebbles'),
    ('floor_pave', t_floor_pave, 'walkable ground (town): four bevelled slabs, grout, moss and a crack'),
    ('tallgrass', t_tallgrass, 'walkable, wild encounters: 70+ sway-ready blades'),
    ('water', t_water, 'blocking unless surfing; surface at -0.05 m, foam edges, ripple rings, lily pads'),
    ('tree', t_tree, 'blocking, ~2.3 m: root flare, layered faceted canopy'),
    ('wall', t_wall, 'blocking 1 m: staggered ashlar courses, plinth, coping, moss'),
    ('building_wall', t_building_wall, 'blocking 1.2 m: brick plinth, plaster, timber posts, window and eave trim'),
    ('roof', t_roof, 'gable roof piece, ridge along X, 0.6 m: shingle rows, ridge cap, rake boards; stack on building_wall'),
    ('door', t_door, 'warp tile: framed plank door, hinges, handle, step, lintel and canopy on the -Y face'),
    ('counter', t_counter, 'blocking, waist height: panelled cabinet, overhanging top, gold trim'),
    ('ledge', t_ledge, 'one-way jump-down: earth strata, grassy overhang, edge stones; lip on -Y'),
    ('rock', t_rock, 'blocking boulder: facets, chips, moss, crack'),
]

PROPS_EXTRA = [
    ('lamp_post', p_lamp_post, 'street lamp'),
    ('mailbox', p_mailbox, 'mailbox on a post'),
    ('pc', p_pc, 'PC terminal on a desk'),
    ('shelf', p_shelf, 'bookshelf with books'),
    ('bed', p_bed, 'bed with headboard, blanket and pillow (1 x 1.8 m)'),
    ('table', p_table, 'wooden table'),
    ('chair', p_chair, 'wooden chair'),
    ('bench', p_bench, 'park bench'),
    ('window', p_window, 'wall segment with framed window, sill, flower box and shutters'),
    ('pillar', p_pillar, 'stone pillar with base and capital'),
    ('podium', p_podium, 'gym trainer podium'),
]

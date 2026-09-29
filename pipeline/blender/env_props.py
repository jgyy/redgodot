"""Environment prop definitions (bmesh, see env_kit.Prop). Every function takes the output style ('vcol' for the
in-game world/ props, 'tex' for the textured tiles/ kit) and returns a finished Prop.  Sprite units, pivot bottom centre,
front = Blender -Y.
"""
import math
import random

from mathutils import Vector, Matrix
from env_kit import Prop


# ------------------------------------------------------------------ signs / fences / plants
def p_sign(style):
    P = Prop('sign', style, seed=3)
    P.blob((0, 0.02, 0), (0.16, 0.11, 0.07), 'soil', subdiv=1, squash_below=0.0, jag=0.15, seed=1)
    for x, y, l in ((-0.14, -0.06, -0.03), (0.13, -0.05, 0.03), (0.03, -0.1, 0.0), (-0.06, -0.09, 0.02)):
        P.blade(x, y, 0.13, 0.05, l, 'tallgrass')
    P.box((-0.06, -0.04, 0.0), (0.06, 0.045, 0.5), 'wood_dark', bevel=0.012)
    P.box((-0.47, -0.06, 0.32), (0.47, 0.045, 0.94), 'wood', bevel=0.022)
    fr = 'wood_dark'
    P.box((-0.47, -0.078, 0.32), (0.47, -0.055, 0.36), fr, bevel=0.006)
    P.box((-0.47, -0.078, 0.90), (0.47, -0.055, 0.94), fr, bevel=0.006)
    P.box((-0.47, -0.078, 0.32), (-0.43, -0.055, 0.94), fr, bevel=0.006)
    P.box((0.43, -0.078, 0.32), (0.47, -0.055, 0.94), fr, bevel=0.006)
    for z, w in ((0.76, 0.66), (0.62, 0.5)):
        P.box((-0.33, -0.07, z), (-0.33 + w, -0.058, z + 0.06), 'wood_dark')
    for sx in (-1, 1):
        for z in (0.43, 0.83):
            P.box((sx * 0.37 - 0.018, -0.082, z - 0.018), (sx * 0.37 + 0.018, -0.06, z + 0.018), 'metal')
    return P


def _picket_pts(x, w=0.075, h=0.56, tip=0.66, z0=0.05):
    return [(x - w, z0), (x + w, z0), (x + w, h), (x, tip), (x - w, h)]


def p_fence_x(style):
    """One cell of picket fence running along X (rails behind the pickets)."""
    P = Prop('fence_x', style, seed=5)
    P.box((-0.5, 0.02, 0.17), (0.5, 0.075, 0.26), 'paint', bevel=0.008, bias=1)
    P.box((-0.5, 0.02, 0.39), (0.5, 0.075, 0.48), 'paint', bevel=0.008, bias=1)
    for i, x in enumerate((-0.375, -0.125, 0.125, 0.375)):
        h = 0.58 + (0.025 if i % 2 else 0.0)
        P.poly_prism(_picket_pts(x, 0.075, h, h + 0.1), -0.05, 0.02, 'paint', bias=1)
    return P


def p_fence_z(style):
    """One cell of picket fence running along Z (into the screen): rails along Y, pickets edge on."""
    P = Prop('fence_z', style, seed=6)
    P.box((-0.035, -0.5, 0.17), (0.035, 0.5, 0.26), 'paint', bevel=0.008, bias=1)
    P.box((-0.035, -0.5, 0.39), (0.035, 0.5, 0.48), 'paint', bevel=0.008, bias=1)
    for i, y in enumerate((-0.375, -0.125, 0.125, 0.375)):
        h = 0.58 + (0.025 if i % 2 else 0.0)
        pts = [(y - 0.075, 0.05), (y + 0.075, 0.05), (y + 0.075, h), (y, h + 0.1), (y - 0.075, h)]
        # picket plane is YZ: extrude along X
        from env_kit import bmesh
        b = P.bm
        f0 = [b.verts.new((-0.06, py, pz)) for py, pz in pts]
        f1 = [b.verts.new((0.04, py, pz)) for py, pz in pts]
        n = len(pts)
        fs = [b.faces.new(list(reversed(f0))), b.faces.new(f1)]
        for k in range(n):
            j = (k + 1) % n
            fs.append(b.faces.new((f0[k], f1[k], f1[j], f0[j])))
        bmesh.ops.recalc_face_normals(b, faces=fs)
        P.paint(fs, 'paint', bias=1)
    return P


def p_fence_post(style):
    P = Prop('fence_post', style, seed=7)
    P.box((-0.08, -0.07, 0.0), (0.08, 0.07, 0.72), 'paint', bevel=0.014, bias=1)
    P.cyl(0, 0, 0.72, 0.8, 0.115, 0.03, 'paint', seg=4, rot=math.pi / 4, cap_top=True, bias=1)
    P.box((-0.1, -0.09, 0.0), (0.1, 0.09, 0.05), 'stone', bevel=0.01)
    return P


def p_plant(style):
    """Potted indoor plant."""
    P = Prop('plant', style, seed=9)
    P.lathe(0, 0, [(0.10, 0.0), (0.145, 0.12), (0.145, 0.13), (0.19, 0.13), (0.19, 0.19), (0.155, 0.195)], 'terracotta', seg=10)
    P.cyl(0, 0, 0.185, 0.185, 0.15, 0.15, 'soil', seg=10, cap_top=True)
    P.lathe(0, 0, [(0.15, 0.185), (0.15, 0.19)], 'soil', seg=10)
    blobs = [((0.0, 0.0, 0.40), (0.24, 0.20, 0.22), 'leaf'),
             ((-0.17, 0.02, 0.32), (0.16, 0.14, 0.14), 'leaf'),
             ((0.17, 0.01, 0.34), (0.17, 0.14, 0.15), 'leaf'),
             ((0.04, -0.05, 0.58), (0.19, 0.16, 0.16), 'leaf_light'),
             ((-0.10, 0.03, 0.60), (0.14, 0.12, 0.13), 'leaf'),
             ((0.09, 0.03, 0.72), (0.12, 0.10, 0.10), 'leaf_light')]
    for k, (c, r, m) in enumerate(blobs):
        P.blob(c, r, m, subdiv=1, jag=0.16, seed=k + 3, ao=False)
    return P


def p_barrel(style):
    P = Prop('barrel', style, seed=11)
    P.lathe(0, 0, [(0.17, 0.0), (0.225, 0.12), (0.25, 0.3), (0.225, 0.48), (0.17, 0.6)], 'wood', seg=10)
    for z, r in ((0.11, 0.222), (0.5, 0.222)):
        rr = 0.235 if z < 0.3 else 0.2
        P.lathe(0, 0, [(rr, z - 0.03), (rr + 0.012, z - 0.03), (rr + 0.012, z + 0.03), (rr, z + 0.03)], 'metal', seg=10, ao=False)
    P.cyl(0, 0, 0.6, 0.6, 0.165, 0.165, 'wood', seg=10, cap_top=True)
    P.transform_all(Matrix.Scale(1.3, 4))
    return P


def p_crate(style):
    P = Prop('crate', style, seed=12)
    P.box((-0.38, -0.38, 0.0), (0.38, 0.38, 0.7), 'wood', bevel=0.03)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * 0.38, sy * 0.38
            P.box((cx - 0.05, cy - 0.05, 0.0), (cx + 0.05, cy + 0.05, 0.7), 'wood_dark', bevel=0.012)
    for z0, z1 in ((0.08, 0.16), (0.52, 0.6)):
        P.box((-0.34, -0.405, z0), (0.34, -0.375, z1), 'wood_dark', bevel=0.008)
        P.box((-0.405, -0.34, z0), (-0.375, 0.34, z1), 'wood_dark', bevel=0.008)
    # diagonal brace on the front face
    P.quad((-0.3, -0.41, 0.16), (-0.22, -0.41, 0.16), (0.3, -0.41, 0.52), (0.22, -0.41, 0.52), 'wood_dark')
    P.box((-0.34, -0.34, 0.7), (0.34, 0.34, 0.72), 'wood_dark', bevel=0.005, ao=False)
    for sx in (-0.2, 0.0, 0.2):
        P.box((sx - 0.03, -0.32, 0.72), (sx + 0.03, 0.32, 0.735), 'wood', ao=False)
    return P


def p_boulder(style):
    """Strength boulder: faceted lump with chipped edges, a moss cap and a crack, lit from the top-left."""
    P = Prop('boulder', style, seed=21)
    P.blob((0.0, 0.0, 0.10), (0.52, 0.42, 0.18), 'soil', subdiv=1, squash_below=0.0, jag=0.1, seed=3)
    P.blob((0.0, 0.0, 0.40), (0.47, 0.38, 0.40), 'boulder', subdiv=2, jag=0.26, seed=41, squash_below=0.06, ao=True)
    P.blob((-0.30, -0.10, 0.20), (0.21, 0.19, 0.17), 'boulder', subdiv=1, jag=0.3, seed=42, squash_below=0.02)
    P.blob((0.32, -0.02, 0.16), (0.17, 0.16, 0.14), 'boulder', subdiv=1, jag=0.3, seed=43, squash_below=0.02)
    P.blob((0.12, 0.10, 0.70), (0.26, 0.2, 0.09), 'moss', subdiv=1, jag=0.3, seed=44, ao=False)
    P.blob((-0.2, 0.06, 0.62), (0.14, 0.12, 0.07), 'moss', subdiv=1, jag=0.3, seed=45, ao=False)
    P.box((0.05, -0.36, 0.22), (0.075, -0.33, 0.54), 'boulder', flat_idx=0, ao=False)
    P.box((0.02, -0.36, 0.5), (0.09, -0.33, 0.54), 'boulder', flat_idx=0, ao=False)
    return P


def p_pokeball(style):
    """Item ball: red cap, white belly, black band with a raised push button."""
    P = Prop('pokeball', style, seed=22)
    cz = 0.28
    R = 0.31
    seg = 14
    prof = []
    # southern hemisphere (white), band, northern hemisphere (red)
    for i in range(0, 5):
        a = -math.pi / 2 + i * (math.pi / 2 - 0.16) / 4
        prof.append((math.cos(a) * R, cz + math.sin(a) * R * 0.86))
    P.lathe(0, 0, [(max(0.001, r), z) for r, z in prof], 'ball_white', seg=seg, ao=False)
    P.lathe(0, 0, [(R * 1.015, cz - 0.045), (R * 1.03, cz - 0.045), (R * 1.03, cz + 0.045), (R * 1.015, cz + 0.045)], 'ball_ink', seg=seg, ao=False)
    prof2 = []
    for i in range(0, 5):
        a = 0.16 + i * (math.pi / 2 - 0.16) / 4
        prof2.append((math.cos(a) * R, cz + math.sin(a) * R * 0.86))
    P.lathe(0, 0, [(max(0.001, r), z) for r, z in prof2], 'ball_red', seg=seg, ao=False)
    # button: ring + white disc on the front (-Y)
    ring = [(math.cos(2 * math.pi * i / 10) * 0.085, cz + math.sin(2 * math.pi * i / 10) * 0.085) for i in range(10)]
    P.poly_prism(ring, -R * 1.07, -R * 0.85, 'ball_ink', ao=False)
    disc = [(math.cos(2 * math.pi * i / 10) * 0.055, cz + math.sin(2 * math.pi * i / 10) * 0.055) for i in range(10)]
    P.poly_prism(disc, -R * 1.12, -R * 0.9, 'ball_white', ao=False)
    return P


def p_grave(style, variant=0):
    """Gravestone (Pokemon Tower): weathered slab on a footing, cross relief, moss and a chipped corner."""
    P = Prop('grave_%s' % 'ab'[variant], style, seed=30 + variant)
    P.box((-0.36, -0.2, 0.0), (0.36, 0.2, 0.07), 'stone', bevel=0.012)
    if variant == 0:      # rounded-top slab
        pts = [(-0.24, 0.05), (0.24, 0.05), (0.24, 0.55), (0.19, 0.66), (0.09, 0.73), (0.0, 0.75), (-0.09, 0.73), (-0.19, 0.66), (-0.24, 0.55)]
        P.poly_prism(pts, -0.07, 0.07, 'stone')
        P.box((-0.025, -0.085, 0.3), (0.025, -0.07, 0.64), 'stone', flat_idx=1, ao=False)     # cross relief
        P.box((-0.11, -0.085, 0.48), (0.11, -0.07, 0.53), 'stone', flat_idx=1, ao=False)
    else:                  # taller slab with a cross on top
        P.box((-0.22, -0.07, 0.05), (0.22, 0.07, 0.5), 'stone', bevel=0.02)
        P.box((-0.045, -0.05, 0.5), (0.045, 0.05, 0.85), 'stone', bevel=0.012)
        P.box((-0.17, -0.05, 0.66), (0.17, 0.05, 0.75), 'stone', bevel=0.012)
    for z in (0.32, 0.24):
        P.box((-0.13, -0.075, z), (0.13, -0.063, z + 0.03), 'stone', flat_idx=0, ao=False)     # inscription
    P.blob((-0.2, -0.13, 0.06), (0.13, 0.09, 0.05), 'moss', subdiv=1, jag=0.3, seed=7 + variant, squash_below=0.02, ao=False)
    P.blob((0.22, 0.02, 0.05), (0.1, 0.1, 0.05), 'moss', subdiv=1, jag=0.3, seed=9 + variant, squash_below=0.02, ao=False)
    return P


def p_grave_a(style):
    return p_grave(style, 0)


def p_grave_b(style):
    return p_grave(style, 1)


def p_brazier(style):
    """Stone brazier: stepped base, fluted column and an iron bowl of embers (the flame is drawn by fx.gdshader)."""
    P = Prop('brazier', style, seed=33)
    P.box((-0.4, -0.32, 0.0), (0.4, 0.32, 0.09), 'stone', bevel=0.02)
    P.box((-0.3, -0.24, 0.09), (0.3, 0.24, 0.5), 'stone', bevel=0.025)
    P.box((-0.34, -0.28, 0.46), (0.34, 0.28, 0.54), 'stone', bevel=0.02)
    for sx in (-1, 1):
        P.box((sx * 0.3 - 0.02, -0.255, 0.16), (sx * 0.3 + 0.02, -0.235, 0.44), 'stone', flat_idx=1, ao=False)
    P.lathe(0, 0, [(0.16, 0.54), (0.3, 0.6), (0.36, 0.72), (0.31, 0.72), (0.26, 0.64), (0.0, 0.62)], 'metal', seg=10, ao=False)
    P.cyl(0, 0, 0.66, 0.66, 0.29, 0.29, 'red', seg=10, cap_top=True, flat_idx=3, ao=False)
    for i in range(3):
        a = i * 2.1
        P.blob((math.cos(a) * 0.12, math.sin(a) * 0.1, 0.66), (0.07, 0.07, 0.04), 'yellow', subdiv=1, seed=i, jag=0.1, ao=False)
    return P


def p_bush(style):
    """A small round tree (HM Cut target)."""
    P = Prop('bush', style, seed=35)
    P.cyl(0, 0, 0, 0.32, 0.075, 0.055, 'bark', seg=6, cap_top=False)
    P.blob((0.0, 0.02, 0.62), (0.44, 0.38, 0.4), 'leaf', subdiv=2, jag=0.24, seed=61, squash_below=0.26)
    P.blob((-0.24, -0.06, 0.5), (0.24, 0.22, 0.24), 'leaf', subdiv=1, jag=0.25, seed=62, squash_below=0.24)
    P.blob((0.26, -0.03, 0.52), (0.24, 0.22, 0.24), 'leaf', subdiv=1, jag=0.25, seed=63, squash_below=0.24)
    P.blob((-0.1, -0.12, 0.84), (0.2, 0.16, 0.14), 'leaf_light', subdiv=1, jag=0.25, seed=64, ao=False)
    P.blob((0.14, 0.05, 0.9), (0.14, 0.12, 0.1), 'leaf_light', subdiv=1, jag=0.25, seed=65, ao=False)
    return P


def p_statue(style):
    """Guardian statue (gym / mansion): a horned Pokemon on a plinth."""
    P = Prop('statue', style, seed=36)
    P.box((-0.5, -0.34, 0.0), (0.5, 0.34, 0.34), 'stone', bevel=0.03)
    P.box((-0.56, -0.4, 0.34), (0.56, 0.4, 0.42), 'stone', bevel=0.025)
    z0 = 0.42
    for sx in (-1, 1):
        P.blob((sx * 0.24, -0.02, z0 + 0.2), (0.17, 0.2, 0.22), 'stone', subdiv=1, jag=0.12, seed=70 + sx, ao=False)            # legs
        P.blob((sx * 0.25, -0.14, z0 + 0.06), (0.16, 0.2, 0.08), 'stone', subdiv=1, jag=0.1, seed=72 + sx, ao=False)             # feet
        P.blob((sx * 0.5, -0.08, z0 + 0.95), (0.13, 0.14, 0.3), 'stone', subdiv=1, jag=0.12, seed=74 + sx, ao=False)             # arms
    P.blob((0, 0.02, z0 + 0.7), (0.42, 0.32, 0.5), 'stone', subdiv=2, jag=0.1, seed=76, ao=False)                                # torso
    P.blob((0, -0.1, z0 + 0.62), (0.28, 0.2, 0.32), 'stone', subdiv=1, jag=0.08, seed=77, ao=False, bias=1)                       # belly
    P.blob((0, -0.1, z0 + 1.32), (0.27, 0.25, 0.25), 'stone', subdiv=2, jag=0.1, seed=78, ao=False)                               # head
    P.blob((0, -0.32, z0 + 1.24), (0.14, 0.16, 0.11), 'stone', subdiv=1, jag=0.08, seed=79, ao=False)                            # snout
    P.cone(0, -0.3, z0 + 1.32, z0 + 1.68, 0.075, 'stone', seg=5, ao=False)                                                         # horn
    for i, zz in enumerate((1.05, 0.82, 0.6)):
        P.cone(0, 0.3, z0 + zz, z0 + zz + 0.06, 0.09, 'stone', seg=4, ao=False)
        P.blob((0, 0.3 + i * 0.02, z0 + zz + 0.06), (0.07, 0.1, 0.1), 'stone', subdiv=1, seed=80 + i, jag=0.1, ao=False)
    P.blob((0, 0.42, z0 + 0.3), (0.13, 0.3, 0.12), 'stone', subdiv=1, jag=0.1, seed=85, ao=False)                                # tail
    P.blob((0.0, 0.66, z0 + 0.16), (0.09, 0.2, 0.08), 'stone', subdiv=1, jag=0.1, seed=86, ao=False)
    P.blob((-0.32, -0.02, 0.44), (0.16, 0.12, 0.05), 'moss', subdiv=1, jag=0.3, seed=87, squash_below=0.36, ao=False)
    P.transform_all(Matrix.Scale(1.3, 4))
    return P


def p_rail_x(style):
    P = Prop('rail_x', style, seed=37)
    P.box((-0.5, -0.03, 0.42), (0.5, 0.03, 0.5), 'wood', bevel=0.012, bias=1)
    P.box((-0.5, -0.02, 0.22), (0.5, 0.02, 0.27), 'wood', bevel=0.01, bias=1)
    for x in (-0.36, -0.12, 0.12, 0.36):
        P.box((x - 0.018, -0.02, 0.05), (x + 0.018, 0.02, 0.44), 'wood_dark', bevel=0.006)
    return P


def p_rail_z(style):
    P = Prop('rail_z', style, seed=38)
    P.box((-0.03, -0.5, 0.42), (0.03, 0.5, 0.5), 'wood', bevel=0.012, bias=1)
    P.box((-0.02, -0.5, 0.22), (0.02, 0.5, 0.27), 'wood', bevel=0.01, bias=1)
    for y in (-0.36, -0.12, 0.12, 0.36):
        P.box((-0.02, y - 0.018, 0.05), (0.02, y + 0.018, 0.44), 'wood_dark', bevel=0.006)
    return P


def p_rail_post(style):
    P = Prop('rail_post', style, seed=39)
    P.box((-0.045, -0.045, 0.0), (0.045, 0.045, 0.56), 'wood_dark', bevel=0.01)
    P.box((-0.06, -0.06, 0.54), (0.06, 0.06, 0.6), 'wood', bevel=0.01, bias=1)
    return P


def _flower(style, name, petal, centre='yellow', seed=40):
    P = Prop(name, style, seed=seed)
    rs = random.Random(seed)
    # three blooms of different height on thin stems with leaves, over a small tuft
    for i, (x, y, h) in enumerate(((-0.05, 0.0, 0.34), (0.12, -0.06, 0.26), (-0.14, 0.09, 0.22))):
        P.box((x - 0.009, y - 0.009, 0.0), (x + 0.009, y + 0.009, h), 'leaf', ao=False)
        P.blade(x + 0.03, y, 0.14, 0.05, 0.05, 'leaf_light', ao=False)
        P.cyl(x, y - 0.012, h - 0.005, h + 0.03, 0.09, 0.065, petal, seg=6, rot=i * 0.5, ao=False, cap_top=True, bias=1)
        P.cyl(x, y - 0.014, h + 0.02, h + 0.04, 0.025, 0.02, centre, seg=5, ao=False, cap_top=True)
    return P


def p_flower_red(style):
    return _flower(style, 'flower_red', 'red', seed=41)


def p_flower_yellow(style):
    return _flower(style, 'flower_yellow', 'yellow', centre='red', seed=42)


def p_flower_white(style):
    return _flower(style, 'flower_white', 'white', seed=43)


def p_flower_pink(style):
    return _flower(style, 'flower_pink', 'pink', seed=44)


def p_rockcell(style):
    """A knee-high rounded rock filling one cell (cave / gym obstacles)."""
    P = Prop('rockcell', style, seed=47)
    P.blob((0.0, 0.0, 0.2), (0.44, 0.38, 0.26), 'cave_stone', subdiv=2, jag=0.16, seed=5, squash_below=0.0, bias=0)
    P.blob((-0.2, -0.08, 0.3), (0.2, 0.18, 0.15), 'cave_stone', subdiv=1, jag=0.2, seed=6, ao=False, bias=1)
    P.blob((0.22, 0.1, 0.24), (0.18, 0.16, 0.13), 'cave_stone', subdiv=1, jag=0.2, seed=7, ao=False, bias=0)
    return P


def p_tuft(style):
    """A wind-swept grass tuft (scattered on plain grass and along ledges)."""
    P = Prop('tuft', style, seed=45)
    rs = random.Random(45)
    for i in range(9):
        a = rs.random() * math.tau
        r = rs.random() * 0.07
        P.blade(math.cos(a) * r, math.sin(a) * r, 0.11 + rs.random() * 0.13, 0.045, (rs.random() - 0.5) * 0.14, 'blade',
                lean_y=(rs.random() - 0.5) * 0.06, ao=False, bias=1 if i % 3 else 2)
    return P


def p_pebbles(style):
    """Two or three small stones (ledge feet, path edges)."""
    P = Prop('pebbles', style, seed=46)
    P.blob((-0.07, 0.0, 0.03), (0.085, 0.07, 0.05), 'stone', subdiv=1, jag=0.25, seed=1, squash_below=0.0, ao=False, bias=1)
    P.blob((0.09, 0.03, 0.025), (0.055, 0.05, 0.035), 'stone', subdiv=1, jag=0.25, seed=2, squash_below=0.0, ao=False, bias=1)
    P.blob((0.02, -0.07, 0.02), (0.04, 0.035, 0.028), 'stone', subdiv=1, jag=0.25, seed=3, squash_below=0.0, ao=False, bias=1)
    return P


def p_bed_game(style):
    import env_tiles
    P = env_tiles.p_bed(style)
    return P


PROPS = {
    'sign': (p_sign, 'wooden sign on a post with nails and text lines'),
    'fence_x': (p_fence_x, 'white picket fence cell running along X'),
    'fence_z': (p_fence_z, 'white picket fence cell running along Z'),
    'fence_post': (p_fence_post, 'fence post with cap and footing'),
    'plant': (p_plant, 'potted plant'),
    'barrel': (p_barrel, 'banded wooden barrel'),
    'crate': (p_crate, 'wooden crate'),
    'boulder': (p_boulder, 'strength boulder'),
    'pokeball': (p_pokeball, 'item ball'),
    'grave_a': (p_grave_a, 'gravestone, rounded slab'),
    'grave_b': (p_grave_b, 'gravestone, slab with a cross'),
    'brazier': (p_brazier, 'stone brazier (flame drawn by fx.gdshader)'),
    'bush': (p_bush, 'small round tree (HM Cut target)'),
    'statue': (p_statue, 'gym / mansion guardian statue'),
    'rail_x': (p_rail_x, 'wooden ship railing along X'),
    'rail_z': (p_rail_z, 'wooden ship railing along Z'),
    'rail_post': (p_rail_post, 'railing post'),
    'bed': (p_bed_game, 'bed, head toward +Y (fitted to the 14 x 32 px sprite footprint by PropKit)'),
    'rockcell': (p_rockcell, 'small rock filling a cell'),
    'tuft': (p_tuft, 'grass tuft (wind sway in game)'),
    'pebbles': (p_pebbles, 'small stones'),
    'flower_red': (p_flower_red, 'flower tuft (3 blooms)'),
    'flower_yellow': (p_flower_yellow, 'flower tuft (3 blooms)'),
    'flower_white': (p_flower_white, 'flower tuft (3 blooms)'),
    'flower_pink': (p_flower_pink, 'flower tuft (3 blooms)'),
}


# exported to godot/assets/models/world (used by PropKit / OwActor); the rest only go into the tiles/ kit
GAME = ['sign', 'fence_x', 'fence_z', 'fence_post', 'plant', 'barrel', 'crate', 'boulder', 'pokeball', 'grave_a', 'grave_b',
        'brazier', 'bush', 'statue', 'bed', 'rockcell', 'tuft', 'pebbles', 'flower_red', 'flower_yellow', 'flower_white', 'flower_pink']

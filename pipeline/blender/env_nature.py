"""Natural elements: tree species, bushes, rocks, water plants, flowers, cave crystals, ice, lava, driftwood ...
(bmesh via env_kit.Prop; sprite units, pivot = base centre, front = -Y).  Tree glbs share the pivot and footprint
conventions of gen_world's tree_* meshes (pivot at the trunk foot, canopy ~1.8 wide) so TileKit can swap species in
without moving anything.  Leaf ramps come from upstream's PAL.leaf / leaf2 plus per-species ramps in env_ext.
"""
import math

from mathutils import Vector, Matrix
from env_kit import Prop
import env_ext as X
from env_ext import leafy, rot_part


def _trunk(P, h, r0=0.09, r1=0.06, mat='bark', lean=0.0, flare=True, seg=7):
    pts = [(0, 0, 0), (lean * 0.3, 0, h * 0.35), (lean * 0.7, 0, h * 0.7), (lean, 0, h)]
    P.tube([(0, 0, -0.01), (0, 0, 0.05)] + pts[1:], r0, mat, seg=seg, r_end=r1, ao=True)
    if flare:
        for k in range(3):
            a = k * 2.1 + 0.4
            P.between((math.cos(a) * r0 * 2.0, math.sin(a) * r0 * 2.0, 0.0), (math.cos(a) * r0 * 0.6, math.sin(a) * r0 * 0.6, 0.2), r0 * 0.34, r0 * 0.2, mat, seg=4, cap1=False)


# ------------------------------------------------------------------------------------------ trees
def p_tree_pine(style, tiers=5, h=2.7, r=0.85, name='tree_pine'):
    P = Prop(name, style, seed=301 + tiers)
    _trunk(P, 0.5, 0.075, 0.055, 'bark')
    rg = X.rs(31 + tiers)
    for i in range(tiers):
        t = i / max(1, tiers - 1)
        z0 = 0.38 + t * (h - 1.0)
        rr = r * (1.0 - t * 0.78)
        th = 0.62 - t * 0.14
        prof = []
        for k in range(3):
            prof.append((rr * (1.0 - 0.05 * k), z0 + k * 0.03))
        prof = [(rr, z0), (rr * 0.84, z0 + 0.1), (rr * 0.94, z0 + 0.13), (rr * 0.5, z0 + th * 0.55), (rr * 0.62, z0 + th * 0.6), (0.001, z0 + th)]
        P.lathe((rg.random() - 0.5) * 0.04, (rg.random() - 0.5) * 0.04, prof, 'pine', seg=8, rot=rg.random(), ao=False, bias=0)
    P.cone(0, 0, h - 0.12, h + 0.08, 0.05, 'pine', seg=4, ao=False, bias=2)
    return P


def p_tree_pine_slim(style):
    P = p_tree_pine(style, tiers=4, h=2.3, r=0.6, name='tree_pine_slim')
    return P


def p_tree_oak(style):
    """Broad round oak: thick forked trunk, seven overlapping leaf clumps, hanging shadows, sunlit tufts."""
    P = Prop('tree_oak', style, seed=310)
    _trunk(P, 0.85, 0.13, 0.085, 'bark', lean=0.03)
    P.between((0.02, 0, 0.7), (-0.32, 0.05, 1.28), 0.055, 0.035, 'bark', seg=5)
    P.between((0.03, 0, 0.72), (0.36, 0.02, 1.22), 0.05, 0.03, 'bark', seg=5)
    rg = X.rs(311)
    clumps = [(0.0, 0.0, 1.55, 0.62, 'leaf'), (-0.5, -0.05, 1.32, 0.46, 'leaf'), (0.5, -0.03, 1.3, 0.48, 'leaf'), (-0.28, 0.12, 1.9, 0.44, 'leaf'),
              (0.3, 0.1, 1.86, 0.44, 'leaf'), (0.0, -0.18, 1.2, 0.44, 'leaf'), (0.0, 0.05, 2.15, 0.36, 'leaf_light'), (-0.55, 0.08, 1.7, 0.34, 'leaf_light'), (0.58, 0.05, 1.7, 0.33, 'leaf_light')]
    for i, (x, y, z, r, m) in enumerate(clumps):
        P.blob((x, y, z), (r, r * 0.86, r * 0.78), m, subdiv=2, jag=0.2, seed=320 + i, ao=False)
    return P


def p_tree_birch(style):
    P = Prop('tree_birch', style, seed=312)
    _trunk(P, 1.5, 0.06, 0.04, 'birch_bark', lean=0.05, seg=6)
    rg = X.rs(313)
    for i in range(7):
        z = 0.25 + i * 0.16
        a = rg.random() * math.tau
        P.box((-0.06, -0.061, z), (0.06, -0.05, z + 0.035), 'graphite', ao=False)
    for i, (x, y, z, r) in enumerate(((0.05, 0, 1.75, 0.5), (-0.34, 0, 1.5, 0.34), (0.42, 0.02, 1.45, 0.32), (-0.05, -0.2, 1.4, 0.3), (0.0, 0.08, 2.1, 0.32), (-0.3, 0.06, 1.95, 0.26))):
        P.blob((x, y, z), (r, r * 0.8, r * 0.85), 'leaf_light' if i % 2 else 'leaf', subdiv=1, jag=0.28, seed=330 + i, ao=False)
    P.between((0.03, 0, 1.0), (-0.3, 0, 1.4), 0.02, 0.014, 'birch_bark', seg=4)
    P.between((0.04, 0, 1.15), (0.38, 0, 1.45), 0.02, 0.014, 'birch_bark', seg=4)
    return P


def p_tree_dead(style):
    P = Prop('tree_dead', style, seed=314)
    _trunk(P, 1.5, 0.11, 0.05, 'dead_wood', lean=-0.08, seg=6)
    rg = X.rs(315)
    branches = [(0.5, -1, 0.55, 0.5), (0.7, 1, 0.5, 0.6), (0.95, -1, 0.42, 0.7), (1.1, 1, 0.38, 0.8), (1.3, -1, 0.3, 0.6), (0.4, 1, 0.4, 0.3)]
    for z, s, ln, up in branches:
        x0 = -0.04 * z
        e = (x0 + s * ln, (rg.random() - 0.5) * 0.15, z + up * ln)
        P.between((x0, 0, z), e, 0.038 * (1.6 - z * 0.5), 0.014, 'dead_wood', seg=5)
        P.between(e, (e[0] + s * ln * 0.4, e[1], e[2] + ln * 0.5), 0.014, 0.006, 'dead_wood', seg=4)
    P.blob((0.05, 0.05, 0.03), (0.2, 0.16, 0.06), 'soil', subdiv=1, jag=0.2, seed=3, squash_below=0.0, ao=False)
    return P


def p_tree_cherry(style):
    P = Prop('tree_cherry', style, seed=316)
    _trunk(P, 0.8, 0.1, 0.07, 'bark', lean=0.06)
    P.between((0.03, 0, 0.6), (-0.4, 0, 1.15), 0.05, 0.03, 'bark', seg=5)
    P.between((0.04, 0, 0.7), (0.45, 0, 1.15), 0.05, 0.03, 'bark', seg=5)
    cl = [(0, 0, 1.55, 0.6), (-0.5, 0, 1.3, 0.42), (0.52, 0, 1.28, 0.44), (-0.22, 0.1, 1.9, 0.38), (0.3, 0.1, 1.85, 0.38), (0.0, -0.16, 1.25, 0.4)]
    for i, (x, y, z, r) in enumerate(cl):
        P.blob((x, y, z), (r, r * 0.86, r * 0.76), 'cherry', subdiv=2, jag=0.22, seed=340 + i, ao=False)
    rg = X.rs(341)
    for i in range(14):
        a = rg.random() * math.tau
        P.sphere((math.cos(a) * 0.7 * rg.random(), -0.35 - rg.random() * 0.12, 1.3 + rg.random() * 0.6), 0.035, 'white', subdiv=1, ao=False)
    for i in range(10):     # fallen petals
        a = rg.random() * math.tau
        d = 0.25 + rg.random() * 0.5
        P.box((math.cos(a) * d - 0.03, math.sin(a) * d * 0.7 - 0.02, 0.0), (math.cos(a) * d + 0.03, math.sin(a) * d * 0.7 + 0.02, 0.008), 'cherry', ao=False, bias=2)
    return P


def p_tree_palm(style):
    P = Prop('tree_palm', style, seed=317)
    pts = [(0, 0, -0.01), (0.02, 0, 0.4), (0.1, 0, 0.9), (0.22, 0, 1.4), (0.3, 0, 1.85)]
    P.tube(pts, 0.085, 'bark', seg=7, r_end=0.05)
    for i in range(1, 9):
        P.box((0.02 * i - 0.1, -0.09, 0.2 * i), (0.02 * i + 0.1, -0.075, 0.2 * i + 0.03), 'bark', ao=False, flat_idx=1)
    tip = Vector((0.3, 0, 1.85))
    n = 9
    for i in range(n):
        a = i * math.tau / n
        d = Vector((math.cos(a), math.sin(a), 0))
        p1 = tip + d * 0.4 + Vector((0, 0, 0.16))
        p2 = tip + d * 0.78 + Vector((0, 0, -0.05))
        p3 = tip + d * 0.98 + Vector((0, 0, -0.34))
        side = Vector((-d.y, d.x, 0)) * 0.11
        # a frond as a folded ribbon of two triangles pairs
        for (a0, a1, w0, w1) in ((tip, p1, 0.02, 0.13), (p1, p2, 0.13, 0.1), (p2, p3, 0.1, 0.0)):
            s0 = Vector((-d.y, d.x, 0)) * w0
            s1 = Vector((-d.y, d.x, 0)) * w1
            P.quad(a0 - s0, a0 + s0, a1 + s1 + Vector((0, 0, 0.0)), a1 - s1, 'palm', toward=(0, 0, 1), ao=False, bias=1 if i % 2 else 0)
            P.quad(a0 - s0 + Vector((0, 0, -0.03)), a0 + s0 + Vector((0, 0, -0.03)), a1 + s1 + Vector((0, 0, -0.03)), a1 - s1 + Vector((0, 0, -0.03)), 'palm', toward=(0, 0, -1), ao=False, bias=0)
    for i in range(3):
        a = i * 2.1
        P.sphere((tip.x + math.cos(a) * 0.09, math.sin(a) * 0.09, 1.78), 0.075, 'brass' if i % 2 else 'wood_dark', subdiv=1, ao=False)
    return P


def p_tree_autumn(style):
    Q = Prop('tree_autumn', style, seed=318)
    _trunk(Q, 0.85, 0.13, 0.085, 'bark', lean=0.03)
    Q.between((0.02, 0, 0.7), (-0.32, 0.05, 1.28), 0.055, 0.035, 'bark', seg=5)
    Q.between((0.03, 0, 0.72), (0.36, 0.02, 1.22), 0.05, 0.03, 'bark', seg=5)
    clumps = [(0.0, 0.0, 1.55, 0.62, 'autumn'), (-0.5, -0.05, 1.32, 0.46, 'orange'), (0.5, -0.03, 1.3, 0.48, 'autumn'), (-0.28, 0.12, 1.9, 0.44, 'autumn'),
              (0.3, 0.1, 1.86, 0.44, 'orange'), (0.0, -0.18, 1.2, 0.44, 'autumn'), (0.0, 0.05, 2.15, 0.36, 'yellow'), (-0.55, 0.08, 1.7, 0.34, 'yellow'), (0.58, 0.05, 1.7, 0.33, 'orange')]
    for i, (x, y, z, r, m) in enumerate(clumps):
        Q.blob((x, y, z), (r, r * 0.86, r * 0.78), m, subdiv=2, jag=0.22, seed=350 + i, ao=False)
    rg = X.rs(351)
    for i in range(12):
        a = rg.random() * math.tau
        d = 0.3 + rg.random() * 0.6
        Q.box((math.cos(a) * d - 0.03, math.sin(a) * d * 0.7 - 0.02, 0.0), (math.cos(a) * d + 0.03, math.sin(a) * d * 0.7 + 0.02, 0.008), rg.choice(['autumn', 'orange', 'yellow']), ao=False, bias=1)
    return Q


def p_tree_apple(style):
    """Small orchard tree with red fruit."""
    P = Prop('tree_apple', style, seed=319)
    _trunk(P, 0.5, 0.09, 0.065, 'bark')
    for i, (x, y, z, r) in enumerate(((0, 0, 0.98, 0.46), (-0.32, 0, 0.82, 0.3), (0.34, 0.02, 0.8, 0.3), (0.0, -0.14, 0.72, 0.3), (0.0, 0.04, 1.28, 0.28))):
        P.blob((x, y, z), (r, r * 0.86, r * 0.82), 'leaf', subdiv=2, jag=0.22, seed=360 + i, ao=False)
    rg = X.rs(361)
    for i in range(9):
        a = rg.random() * math.tau
        P.sphere((math.cos(a) * 0.42 * rg.random(), -0.32 - rg.random() * 0.1, 0.72 + rg.random() * 0.5), 0.04, 'red', subdiv=1, ao=False, flat_idx=3)
    return P


# ------------------------------------------------------------------------------------------ bushes / plants
def p_bush_round(style):
    P = Prop('bush_round', style, seed=330)
    leafy(P, (0, 0, 0.3), 0.3, 'leaf', n=6, spread=0.9, seed=5, mat2='leaf_light', squash=0.8)
    return P


def p_bush_flowering(style):
    P = Prop('bush_flowering', style, seed=331)
    leafy(P, (0, 0, 0.28), 0.3, 'leaf', n=6, spread=0.9, seed=6, squash=0.8)
    rg = X.rs(332)
    for i in range(11):
        a = rg.random() * math.tau
        d = rg.random() * 0.34
        P.sphere((math.cos(a) * d, math.sin(a) * d * 0.8 - 0.1, 0.32 + rg.random() * 0.22), 0.04, rg.choice(['pink', 'white', 'pink', 'yellow']), subdiv=1, ao=False, flat_idx=3)
    return P


def p_bush_berry(style):
    P = Prop('bush_berry', style, seed=333)
    leafy(P, (0, 0, 0.26), 0.28, 'moss', n=5, spread=0.8, seed=7, squash=0.8)
    rg = X.rs(334)
    for i in range(8):
        a = rg.random() * math.tau
        P.sphere((math.cos(a) * 0.25 * rg.random(), -0.2 - rg.random() * 0.08, 0.2 + rg.random() * 0.24), 0.028, rg.choice(['blue', 'purple', 'red']), subdiv=1, ao=False)
    return P


def p_fern(style):
    P = Prop('fern', style, seed=335)
    n = 9
    for i in range(n):
        a = i * math.tau / n + 0.2
        d = Vector((math.cos(a), math.sin(a), 0))
        tip = d * (0.34 + 0.06 * (i % 2)) + Vector((0, 0, 0.1))
        mid = d * 0.18 + Vector((0, 0, 0.32 - 0.04 * (i % 3)))
        s = Vector((-d.y, d.x, 0)) * 0.05
        P.quad(Vector((0, 0, 0.0)) - s * 0.3, Vector((0, 0, 0.0)) + s * 0.3, mid + s, mid - s, 'leaf', toward=(0, 0, 1), ao=False, bias=1)
        P.quad(mid - s, mid + s, tip + s * 0.2, tip - s * 0.2, 'leaf_light' if i % 2 else 'leaf', toward=(0, 0, 1), ao=False, bias=1)
        P.quad(mid - s, mid + s, tip + s * 0.2, tip - s * 0.2, 'leaf', toward=(0, 0, -1), ao=False)
        P.quad(Vector((0, 0, 0.0)) - s * 0.3, Vector((0, 0, 0.0)) + s * 0.3, mid + s, mid - s, 'leaf', toward=(0, 0, -1), ao=False)
    return P


def p_tall_reeds(style):
    """Cluster of reeds with brown cattail heads."""
    P = Prop('tall_reeds', style, seed=336)
    rg = X.rs(337)
    for i in range(11):
        x = (rg.random() - 0.5) * 0.5
        y = (rg.random() - 0.5) * 0.3
        h = 0.55 + rg.random() * 0.5
        P.blade(x, y, h, 0.045, (rg.random() - 0.5) * 0.14, 'reed', lean_y=(rg.random() - 0.5) * 0.08, ao=False, bias=1)
        if i % 3 == 0:
            lean = 0.0
            P.between((x + 0.02, y, h * 0.62), (x + 0.03, y, h * 0.62 + 0.05), 0.01, 0.01, 'reed', seg=4)
            P.cyl(x + 0.03, y, h * 0.62 + 0.03, h * 0.62 + 0.2, 0.026, 0.02, 'cattail', seg=5, ao=False)
    return P


def p_lily_pads(style):
    """Three lily pads (notched discs) and a pink lotus flower."""
    P = Prop('lily_pads', style, seed=338)
    for i, (x, y, r) in enumerate(((-0.18, 0.0, 0.18), (0.16, -0.1, 0.15), (0.08, 0.16, 0.13))):
        P.cyl(x, y, 0.0, 0.012, r, r * 0.96, 'lily', seg=10, cap_top=True, ao=False, bias=1, rot=i)
        P.box((x, y - 0.006, 0.012), (x + r * 0.9, y + 0.006, 0.013), 'water_deep', ao=False, flat_idx=0)
    for k in range(6):
        a = k * math.tau / 6
        P.cyl(0.02 + math.cos(a) * 0.05, -0.02 + math.sin(a) * 0.05, 0.012, 0.09, 0.03, 0.006, 'pk_pink', seg=4, rot=a, ao=False, bias=2)
    P.sphere((0.02, -0.02, 0.05), 0.02, 'yellow', subdiv=1, ao=False)
    return P


def p_seaweed(style):
    P = Prop('seaweed', style, seed=339)
    rg = X.rs(340)
    for i in range(6):
        x = (rg.random() - 0.5) * 0.4
        y = (rg.random() - 0.5) * 0.3
        P.tube([(x, y, 0), (x + 0.04, y, 0.15), (x - 0.03, y, 0.3), (x + 0.03, y, 0.44)], 0.02, 'lily', seg=4, r_end=0.006, ao=False)
    return P


def p_mushrooms(style):
    """Cluster of red spotted toadstools and small brown ones."""
    P = Prop('mushrooms', style, seed=341)
    for i, (x, y, h, r, m) in enumerate(((0.0, 0.0, 0.2, 0.15, 'mushroom'), (0.2, -0.06, 0.13, 0.1, 'mushroom'), (-0.18, 0.04, 0.1, 0.08, 'mushroom_brown'), (0.1, 0.12, 0.09, 0.07, 'mushroom_brown'), (-0.08, -0.14, 0.12, 0.09, 'mushroom'))):
        P.cyl(x, y, 0, h, r * 0.34, r * 0.28, 'cloth_cream', seg=6, cap_top=False, ao=False, bias=1)
        P.lathe(x, y, [(r, h - 0.02), (r * 0.94, h + r * 0.28), (r * 0.6, h + r * 0.5), (0.001, h + r * 0.56)], m, seg=8, ao=False)
        if m == 'mushroom':
            for k in range(3):
                a = k * 2.1 + i
                P.sphere((x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5 - 0.02, h + r * 0.4), r * 0.16, 'white', subdiv=1, ao=False)
    return P


def p_flower_patch(style, kind=0):
    """A patch of 12 flowers in mixed colours over a leafy bed (walkable ground dressing)."""
    P = Prop('flower_patch_' + 'abc'[kind], style, seed=345 + kind)
    rg = X.rs(346 + kind)
    cols = [['red', 'yellow', 'white'], ['pink', 'white', 'purple'], ['yellow', 'orange', 'led_blue']][kind]
    for i in range(16):
        a = rg.random() * math.tau
        d = math.sqrt(rg.random()) * 0.4
        x, y = math.cos(a) * d, math.sin(a) * d * 0.75
        h = 0.12 + rg.random() * 0.16
        P.blade(x, y, h * 0.7, 0.05, (rg.random() - 0.5) * 0.06, 'blade', ao=False)
        P.box((x - 0.006, y - 0.006, 0.0), (x + 0.006, y + 0.006, h), 'leaf', ao=False)
        m = rg.choice(cols)
        P.cyl(x, y, h, h + 0.03, 0.05, 0.036, m, seg=5, rot=rg.random(), ao=False, bias=1)
        P.cyl(x, y, h + 0.025, h + 0.04, 0.014, 0.01, 'yellow', seg=4, ao=False)
    return P


def p_flower_patch_b(style):
    return p_flower_patch(style, 1)


def p_flower_patch_c(style):
    return p_flower_patch(style, 2)


def p_sunflower(style):
    P = Prop('sunflower', style, seed=350)
    for i, (x, y, h) in enumerate(((0, 0, 0.9), (0.2, -0.05, 0.7), (-0.18, 0.05, 0.78))):
        P.tube([(x, y, 0), (x, y + 0.02, h * 0.5), (x + 0.02, y, h)], 0.02, 'leaf', seg=4, ao=False)
        P.blade(x + 0.02, y, h * 0.4, 0.09, 0.12, 'leaf_light', ao=False)
        P.blade(x - 0.02, y, h * 0.3, 0.08, -0.12, 'leaf', ao=False)
        for k in range(10):
            a = k * math.tau / 10
            P.between((x + 0.02, y - 0.03, h), (x + 0.02 + math.cos(a) * 0.115, y - 0.03, h + math.sin(a) * 0.115), 0.028, 0.01, 'yellow', seg=4, cap0=True, ao=False, bias=1)
        P.cyl(x + 0.02, y - 0.03, h - 0.02, h + 0.02, 0.055, 0.055, 'cattail', seg=7, ao=False)
    P.transform_all(Matrix.Scale(1.0, 4))
    return P


def p_grass_clump(style):
    P = Prop('grass_clump', style, seed=351)
    rg = X.rs(352)
    for i in range(16):
        a = rg.random() * math.tau
        r = rg.random() * 0.11
        P.blade(math.cos(a) * r, math.sin(a) * r, 0.26 + rg.random() * 0.34, 0.05, (rg.random() - 0.5) * 0.24, 'blade', lean_y=(rg.random() - 0.5) * 0.1, ao=False, bias=1 if i % 3 else 2)
    return P


def p_cactus(style):
    P = Prop('cactus', style, seed=353)
    P.lathe(0, 0, [(0.001, 0.0), (0.1, 0.0), (0.12, 0.3), (0.1, 0.64), (0.001, 0.74)], 'cactus', seg=8)
    P.tube([(0.1, 0, 0.32), (0.26, 0, 0.36), (0.3, 0, 0.56)], 0.06, 'cactus', seg=6, ao=False)
    P.tube([(-0.1, 0, 0.26), (-0.24, 0, 0.3), (-0.27, 0, 0.44)], 0.055, 'cactus', seg=6, ao=False)
    for z in (0.15, 0.32, 0.5):
        P.sphere((0.0, -0.11, z), 0.02, 'pink', subdiv=1, ao=False)
    return P


# ------------------------------------------------------------------------------------------ rocks / stone
def _rock(P, cx, cy, r, mat, seed, h=0.7, sub=2, jag=0.24, moss=False):
    P.blob((cx, cy, r * h * 0.6), (r, r * 0.86, r * h), mat, subdiv=sub, jag=jag, seed=seed, squash_below=0.0)
    if moss:
        P.blob((cx + r * 0.1, cy + r * 0.1, r * h * 1.15), (r * 0.6, r * 0.5, r * h * 0.25), 'moss', subdiv=1, jag=0.3, seed=seed + 5, ao=False)


def p_rock_small_a(style):
    P = Prop('rock_small_a', style, seed=360)
    _rock(P, 0, 0, 0.2, 'rock', 1)
    _rock(P, 0.22, -0.08, 0.1, 'rock', 2, sub=1)
    return P


def p_rock_small_b(style):
    P = Prop('rock_small_b', style, seed=361)
    _rock(P, -0.05, 0, 0.16, 'stone', 3, sub=1)
    _rock(P, 0.14, 0.05, 0.12, 'stone', 4, sub=1)
    _rock(P, 0.02, -0.14, 0.08, 'stone', 5, sub=1)
    return P


def p_rock_mossy(style):
    P = Prop('rock_mossy', style, seed=362)
    _rock(P, 0, 0, 0.32, 'boulder', 6, h=0.75, moss=True)
    _rock(P, -0.3, -0.08, 0.15, 'boulder', 7, sub=1, moss=True)
    return P


def p_boulder_large(style):
    P = Prop('boulder_large', style, seed=363)
    _rock(P, 0, 0, 0.55, 'boulder', 8, h=0.85, sub=2, jag=0.3)
    _rock(P, -0.42, -0.2, 0.26, 'boulder', 9, sub=1, jag=0.3)
    _rock(P, 0.4, -0.14, 0.22, 'boulder', 10, sub=1, jag=0.3)
    P.blob((0.1, 0.05, 0.62), (0.32, 0.26, 0.09), 'moss', subdiv=1, jag=0.3, seed=11, ao=False)
    return P


def p_rock_pile(style):
    P = Prop('rock_pile', style, seed=364)
    rg = X.rs(365)
    for i in range(7):
        a = rg.random() * math.tau
        d = rg.random() * 0.22
        _rock(P, math.cos(a) * d, math.sin(a) * d * 0.8, 0.09 + rg.random() * 0.1, rg.choice(['rock', 'stone', 'boulder']), 20 + i, sub=1, h=0.6)
    return P


def p_cairn(style):
    """Balanced stone stack marker."""
    P = Prop('cairn', style, seed=366)
    for i, (r, h) in enumerate(((0.22, 0.09), (0.17, 0.08), (0.13, 0.07), (0.09, 0.06))):
        z = sum(hh for _, hh in ((0.22, 0.09), (0.17, 0.08), (0.13, 0.07), (0.09, 0.06))[:i]) * 1.7
        P.blob((0.01 * i, 0, z + h), (r, r * 0.85, h), 'stone' if i % 2 else 'rock', subdiv=1, jag=0.12, seed=30 + i, squash_below=z)
    return P


def p_stalagmite(style, variant=0):
    P = Prop('stalagmite_' + 'ab'[variant], style, seed=367 + variant)
    if variant == 0:
        P.lathe(0, 0, [(0.2, 0.0), (0.15, 0.2), (0.08, 0.55), (0.001, 0.95)], 'cave_stone', seg=7, rot=0.3)
        P.lathe(0.22, 0.05, [(0.1, 0.0), (0.06, 0.15), (0.001, 0.4)], 'cave_stone', seg=6)
        P.lathe(-0.2, -0.05, [(0.08, 0.0), (0.05, 0.12), (0.001, 0.3)], 'cave_stone', seg=6)
    else:
        for i, (x, y, r, h) in enumerate(((0, 0, 0.16, 0.7), (0.2, -0.05, 0.11, 0.45), (-0.18, 0.06, 0.1, 0.55), (0.06, 0.16, 0.08, 0.3))):
            P.lathe(x, y, [(r, 0.0), (r * 0.7, h * 0.4), (r * 0.36, h * 0.8), (0.001, h)], 'cave_stone', seg=6, rot=i)
    return P


def p_stalagmite_b(style):
    return p_stalagmite(style, 1)


def _crystal(P, cx, cy, r, h, mat, tilt=(0, 0), seg=6):
    top = (cx + tilt[0] * h, cy + tilt[1] * h, h)
    ring = []
    for i in range(seg):
        a = i * math.tau / seg
        ring.append(P.bm.verts.new((cx + math.cos(a) * r, cy + math.sin(a) * r, 0.0)))
    mid = [P.bm.verts.new((cx + math.cos(i * math.tau / seg) * r * 1.05 + tilt[0] * h * 0.72, cy + math.sin(i * math.tau / seg) * r * 1.05 + tilt[1] * h * 0.72, h * 0.72)) for i in range(seg)]
    tp = P.bm.verts.new(top)
    fs = []
    for i in range(seg):
        j = (i + 1) % seg
        fs.append(P.bm.faces.new((ring[i], ring[j], mid[j], mid[i])))
        fs.append(P.bm.faces.new((mid[i], mid[j], tp)))
    import bmesh
    bmesh.ops.recalc_face_normals(P.bm, faces=fs)
    P.paint(fs, mat, ao=False, bias=1)


def p_crystal(style, mat='crystal_b', name='crystal_blue', seed=1):
    P = Prop(name, style, seed=370 + seed)
    P.blob((0, 0, 0.03), (0.3, 0.24, 0.06), 'cave_stone', subdiv=1, jag=0.2, seed=seed, squash_below=0.0)
    rg = X.rs(371 + seed)
    for i, (x, y, r, h, tx, ty) in enumerate(((0, 0, 0.11, 0.62, 0.05, 0.0), (0.19, -0.06, 0.08, 0.4, 0.28, -0.05), (-0.18, 0.02, 0.085, 0.46, -0.3, 0.05),
                                              (0.05, 0.14, 0.06, 0.3, 0.05, 0.3), (-0.06, -0.15, 0.06, 0.26, -0.05, -0.22))):
        _crystal(P, x, y, r, h, mat, (tx, ty))
    return P


def p_crystal_purple(style):
    return p_crystal(style, 'crystal_p', 'crystal_purple', 2)


def p_crystal_green(style):
    return p_crystal(style, 'crystal_g', 'crystal_green', 3)


def p_ice_spike(style):
    P = Prop('ice_spike', style, seed=380)
    P.blob((0, 0, 0.02), (0.3, 0.25, 0.05), 'snow', subdiv=1, jag=0.2, seed=2, squash_below=0.0)
    for i, (x, y, r, h, tx, ty) in enumerate(((0, 0, 0.14, 0.8, 0.0, 0.0), (0.22, -0.05, 0.09, 0.5, 0.2, 0.0), (-0.2, 0.03, 0.1, 0.55, -0.2, 0.0), (0.05, 0.16, 0.07, 0.34, 0.0, 0.2))):
        _crystal(P, x, y, r, h, 'ice', (tx, ty), seg=5)
    return P


def p_ice_block(style):
    P = Prop('ice_block', style, seed=381)
    P.box((-0.4, -0.34, 0.0), (0.4, 0.34, 0.62), 'ice', bevel=0.08, seg=2)
    P.box((-0.34, -0.352, 0.1), (-0.06, -0.33, 0.48), 'snow', bevel=0.02, ao=False, flat_idx=4)
    P.box((0.08, -0.352, 0.3), (0.3, -0.33, 0.52), 'snow', bevel=0.02, ao=False, flat_idx=3)
    P.blob((0, 0, 0.62), (0.4, 0.3, 0.08), 'snow', subdiv=1, jag=0.2, seed=3, ao=False)
    return P


def p_lava_rock(style):
    P = Prop('lava_rock', style, seed=382)
    _rock(P, 0, 0, 0.3, 'obsidian', 12, h=0.7, jag=0.3)
    _rock(P, -0.26, -0.1, 0.14, 'obsidian', 13, sub=1, jag=0.3)
    for i, (x, z0, z1) in enumerate(((-0.05, 0.1, 0.42), (0.1, 0.06, 0.3), (0.04, 0.2, 0.34))):
        P.box((x, -0.245 - i * 0.02, z0), (x + 0.03, -0.235 - i * 0.02, z1), 'lava', ao=False, flat_idx=3 + (i % 2))
    return P


def p_log_fallen(style):
    P = Prop('log_fallen', style, seed=383)
    P.between((-0.48, 0, 0.14), (0.42, 0.04, 0.16), 0.14, 0.12, 'bark', seg=8)
    P.between((0.42, 0.04, 0.16), (0.425, 0.04, 0.16), 0.115, 0.115, 'wood_pale', seg=8, cap0=False)
    P.between((0.4, 0.04, 0.16), (0.41, 0.04, 0.16), 0.11, 0.11, 'wood_pale', seg=8, cap0=False)
    P.between((-0.2, 0.0, 0.24), (-0.32, -0.06, 0.4), 0.03, 0.015, 'bark', seg=4)
    P.blob((0.0, -0.12, 0.26), (0.2, 0.06, 0.05), 'moss', subdiv=1, jag=0.3, seed=4, ao=False)
    return P


def p_stump(style):
    P = Prop('stump', style, seed=384)
    P.lathe(0, 0, [(0.26, 0.0), (0.2, 0.06), (0.17, 0.2), (0.16, 0.3)], 'bark', seg=9)
    P.cyl(0, 0, 0.3, 0.3, 0.16, 0.16, 'wood_pale', seg=9, cap_top=True, ao=False, flat_idx=3)
    for k, r in enumerate((0.11, 0.06)):
        P.lathe(0, 0, [(r, 0.302), (r + 0.012, 0.304), (r, 0.306)], 'wood_orange', seg=9, ao=False)
    for a in (0.5, 2.4, 4.2):
        P.between((math.cos(a) * 0.22, math.sin(a) * 0.22, 0.0), (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.12), 0.04, 0.02, 'bark', seg=4, cap1=False)
    P.blob((0.1, -0.1, 0.3), (0.06, 0.05, 0.03), 'moss', subdiv=1, ao=False)
    return P


def p_log_pile(style):
    P = Prop('log_pile', style, seed=385)
    for row, n in enumerate((4, 3, 2)):
        for i in range(n):
            x = (i - (n - 1) / 2) * 0.19
            z = 0.085 + row * 0.15
            P.between((x, -0.2, z), (x, 0.2, z), 0.085, 0.085, 'bark', seg=7)
            P.between((x, -0.2, z), (x, -0.205, z), 0.075, 0.075, 'wood_pale', seg=7, cap0=False)
    return P


def p_driftwood(style):
    P = Prop('driftwood', style, seed=386)
    P.tube([(-0.42, 0.0, 0.05), (-0.2, 0.05, 0.1), (0.05, 0.0, 0.08), (0.36, -0.06, 0.14)], 0.055, 'wood_pale', seg=6, r_end=0.04)
    P.between((-0.1, 0.04, 0.09), (-0.16, 0.14, 0.22), 0.03, 0.012, 'wood_pale', seg=4)
    P.between((0.14, -0.02, 0.1), (0.2, -0.12, 0.24), 0.028, 0.01, 'wood_pale', seg=4)
    P.blob((0.3, 0.1, 0.02), (0.1, 0.06, 0.03), 'shell', subdiv=1, ao=False)
    return P


def p_shell(style):
    P = Prop('seashell', style, seed=387)
    for k in range(9):
        a = -0.9 + k * 0.225
        P.tri((0, 0, 0.01), (math.sin(a) * 0.17, -math.cos(a) * 0.17, 0.04), (math.sin(a + 0.22) * 0.17, -math.cos(a + 0.22) * 0.17, 0.04), 'shell', toward=(0, 0, 1), ao=False, bias=k % 2)
    P.box((-0.05, -0.02, 0.0), (0.05, 0.03, 0.03), 'shell', ao=False)
    P.blob((0.25, 0.08, 0.02), (0.06, 0.05, 0.03), 'coral', subdiv=1, ao=False)
    return P


def p_coral(style):
    P = Prop('coral', style, seed=388)
    rg = X.rs(389)
    for i in range(6):
        x = (rg.random() - 0.5) * 0.4
        y = (rg.random() - 0.5) * 0.3
        h = 0.2 + rg.random() * 0.25
        P.tube([(x, y, 0), (x + (rg.random() - 0.5) * 0.1, y, h * 0.6), (x + (rg.random() - 0.5) * 0.2, y, h)], 0.04, 'coral', seg=5, r_end=0.02, ao=False, bias=1)
    return P


def p_bones(style):
    P = Prop('bones', style, seed=390)
    P.blob((0, 0, 0.09), (0.12, 0.14, 0.1), 'bone', subdiv=1, jag=0.08, seed=1, ao=False)
    P.box((-0.045, -0.15, 0.02), (0.045, -0.1, 0.07), 'graphite', ao=False, flat_idx=0)
    P.box((-0.1, -0.09, 0.09), (-0.05, -0.07, 0.13), 'graphite', ao=False, flat_idx=0)
    P.box((0.05, -0.09, 0.09), (0.1, -0.07, 0.13), 'graphite', ao=False, flat_idx=0)
    P.between((0.2, 0.0, 0.03), (0.5, 0.05, 0.03), 0.02, 0.02, 'bone', seg=5)
    P.sphere((0.2, 0.0, 0.03), 0.03, 'bone', subdiv=1, ao=False)
    P.sphere((0.5, 0.05, 0.03), 0.03, 'bone', subdiv=1, ao=False)
    return P


NATURE = {
    'tree_pine': (p_tree_pine, 'conifer: five drooping tiers on a straight trunk'),
    'tree_pine_slim': (p_tree_pine_slim, 'slim four-tier conifer'),
    'tree_oak': (p_tree_oak, 'broad oak: forked trunk, nine leaf clumps'),
    'tree_birch': (p_tree_birch, 'birch: white bark with black bands, light foliage'),
    'tree_dead': (p_tree_dead, 'leafless dead tree'),
    'tree_cherry': (p_tree_cherry, 'cherry blossom tree with fallen petals'),
    'tree_palm': (p_tree_palm, 'coconut palm with nine fronds'),
    'tree_autumn': (p_tree_autumn, 'autumn oak (orange/red/yellow) with leaf litter'),
    'tree_apple': (p_tree_apple, 'small orchard tree with apples'),
    'bush_round': (p_bush_round, 'round bush'),
    'bush_flowering': (p_bush_flowering, 'bush with pink/white blooms'),
    'bush_berry': (p_bush_berry, 'bush with berries'),
    'fern': (p_fern, 'nine-frond fern'),
    'tall_reeds': (p_tall_reeds, 'reeds with cattail heads'),
    'lily_pads': (p_lily_pads, 'lily pads with a lotus'),
    'seaweed': (p_seaweed, 'seaweed strands'),
    'mushrooms': (p_mushrooms, 'toadstool cluster'),
    'flower_patch_a': (p_flower_patch, 'mixed flower patch (red/yellow/white)'),
    'flower_patch_b': (p_flower_patch_b, 'mixed flower patch (pink/white/purple)'),
    'flower_patch_c': (p_flower_patch_c, 'mixed flower patch (yellow/orange/blue)'),
    'sunflower': (p_sunflower, 'three sunflowers'),
    'grass_clump': (p_grass_clump, 'tall grass clump (wind sway)'),
    'cactus': (p_cactus, 'desert cactus'),
    'rock_small_a': (p_rock_small_a, 'two small rocks'),
    'rock_small_b': (p_rock_small_b, 'three grey pebbles'),
    'rock_mossy': (p_rock_mossy, 'mossy rock pair'),
    'boulder_large': (p_boulder_large, 'large boulder with chunks and moss'),
    'rock_pile': (p_rock_pile, 'pile of stones'),
    'cairn': (p_cairn, 'stone cairn'),
    'stalagmite_a': (p_stalagmite, 'stalagmite trio'),
    'stalagmite_b': (p_stalagmite_b, 'stalagmite cluster'),
    'crystal_blue': (p_crystal, 'blue crystal cluster'),
    'crystal_purple': (p_crystal_purple, 'purple crystal cluster'),
    'crystal_green': (p_crystal_green, 'green crystal cluster'),
    'ice_spike': (p_ice_spike, 'ice spikes on snow'),
    'ice_block': (p_ice_block, 'ice block'),
    'lava_rock': (p_lava_rock, 'obsidian rock with glowing veins'),
    'log_fallen': (p_log_fallen, 'fallen log with moss'),
    'stump': (p_stump, 'tree stump with rings'),
    'log_pile': (p_log_pile, 'stack of 9 logs'),
    'driftwood': (p_driftwood, 'driftwood branch and shell'),
    'seashell': (p_shell, 'fan shell'),
    'coral': (p_coral, 'coral branches'),
    'bones': (p_bones, 'skull and bone'),
}

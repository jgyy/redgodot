"""Town, harbour and street dressing (bmesh via env_kit.Prop; sprite units, pivot = base centre, front = -Y).
Mailboxes, lamps, benches, a fountain, a well, market stall, boats, harbour gear, power-plant pylons, Safari and
Pokemon Tower ornaments ...  Colours follow upstream's palette (blue mailboxes, white pickets, wood browns)."""
import math

from mathutils import Vector, Matrix
from env_kit import Prop
import env_ext as X
from env_ext import rot_part, tilt_x, rot_z, sign_face, bars


def p_mailbox(style):
    """Roadside mailbox: turned post, arched blue box with rounded door, red flag, house-number plate."""
    P = Prop('mailbox', style, seed=401)
    P.box((-0.035, -0.03, 0.0), (0.035, 0.03, 0.5), 'wood_dark', bevel=0.008)
    P.box((-0.1, -0.06, 0.44), (0.1, 0.06, 0.5), 'wood', bevel=0.008)
    P.box((-0.15, -0.1, 0.5), (0.15, 0.22, 0.64), 'blue', bevel=0.03, seg=2)
    P.box((-0.12, -0.1, 0.64), (0.12, 0.22, 0.7), 'blue', bevel=0.03, seg=2, bias=1)
    P.box((-0.1, -0.118, 0.52), (0.1, -0.1, 0.66), 'blue', bevel=0.02, bias=1)
    P.box((-0.04, -0.128, 0.56), (0.04, -0.118, 0.575), 'white', ao=False)
    P.box((0.13, -0.05, 0.62), (0.15, -0.03, 0.82), 'red', bevel=0.004)
    P.box((0.13, -0.09, 0.78), (0.15, -0.03, 0.83), 'red', bevel=0.004)
    return P


def p_lamp_post(style):
    """Iron street lamp: fluted base, tapered pole, scroll arm, glass lantern with lit flame and cap."""
    P = Prop('lamp_post', style, seed=402)
    P.lathe(0, 0, [(0.16, 0.0), (0.16, 0.06), (0.1, 0.12), (0.075, 0.2), (0.05, 0.3)], 'graphite', seg=8)
    P.lathe(0, 0, [(0.05, 0.3), (0.036, 0.5), (0.03, 1.4)], 'graphite', seg=8, ao=False)
    P.cyl(0, 0, 1.0, 1.02, 0.06, 0.06, 'brass', seg=8, ao=False, cap_top=True)
    P.cyl(0, 0, 1.4, 1.44, 0.06, 0.075, 'graphite', seg=8)
    P.box((-0.11, -0.11, 1.44), (0.11, 0.11, 1.48), 'graphite', bevel=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.1 - 0.012, sy * 0.1 - 0.012, 1.48), (sx * 0.1 + 0.012, sy * 0.1 + 0.012, 1.74), 'graphite')
    P.box((-0.09, -0.09, 1.49), (0.09, 0.09, 1.73), 'yellow', ao=False, flat_idx=3)
    P.sphere((0, 0, 1.6), 0.05, 'white', subdiv=1, ao=False, flat_idx=4)
    P.lathe(0, 0, [(0.16, 1.74), (0.13, 1.8), (0.06, 1.86), (0.001, 1.9)], 'graphite', seg=4, rot=0.78)
    P.sphere((0, 0, 1.92), 0.025, 'brass', subdiv=1, ao=False)
    return P


def p_park_bench(style):
    """Outdoor bench: three seat slats, four-slat back, cast-iron scroll ends, 1 cell wide."""
    P = Prop('park_bench', style, seed=403)
    for i in range(3):
        P.box((-0.46, -0.2 + i * 0.13, 0.32), (0.46, -0.1 + i * 0.13, 0.36), 'wood_orange', bevel=0.008)
    for i in range(3):
        P.box((-0.46, 0.17, 0.44 + i * 0.1), (0.46, 0.2, 0.52 + i * 0.1), 'wood_orange', bevel=0.008)
    for sx in (-1, 1):
        x = sx * 0.4
        P.box((x - 0.022, -0.2, 0.0), (x + 0.022, -0.16, 0.34), 'graphite', bevel=0.004)
        P.box((x - 0.022, 0.16, 0.0), (x + 0.022, 0.2, 0.34), 'graphite', bevel=0.004)
        P.box((x - 0.022, 0.16, 0.34), (x + 0.022, 0.2, 0.74), 'graphite', bevel=0.004)
        P.box((x - 0.022, -0.2, 0.3), (x + 0.022, 0.2, 0.34), 'graphite', bevel=0.004)
        P.box((x - 0.03, -0.22, 0.34), (x + 0.03, 0.18, 0.4), 'graphite', bevel=0.006)
    return P


def p_fountain(style):
    """Town fountain, 2 x 2 cells: octagonal basin with water, tiered bowls, a spout and jet arcs."""
    P = Prop('fountain', style, seed=404)
    P.lathe(0, 0, [(0.98, 0.0), (0.98, 0.26), (0.9, 0.3), (0.9, 0.27)], 'stone', seg=8, rot=0.39, ao=True)
    P.cyl(0, 0, 0.25, 0.25, 0.9, 0.9, 'water', seg=8, rot=0.39, cap_top=True, ao=False, flat_idx=3)
    P.lathe(0, 0, [(0.98, 0.26), (1.02, 0.28), (1.02, 0.32), (0.9, 0.32)], 'stone', seg=8, rot=0.39, bias=1)
    P.lathe(0, 0, [(0.001, 0.24), (0.22, 0.24), (0.2, 0.44), (0.1, 0.5), (0.08, 0.86)], 'stone', seg=8, rot=0.39)
    P.lathe(0, 0, [(0.5, 0.78), (0.5, 0.86), (0.4, 0.9), (0.001, 0.88)], 'stone', seg=8, rot=0.39, bias=1)
    P.lathe(0, 0, [(0.06, 0.86), (0.06, 1.1), (0.1, 1.16)], 'stone', seg=8)
    P.cyl(0, 0, 0.87, 0.87, 0.44, 0.44, 'water', seg=8, cap_top=True, ao=False, flat_idx=3)
    for k in range(6):
        a = k * math.tau / 6 + 0.39
        pts = [(math.cos(a) * 0.04, math.sin(a) * 0.04, 1.14), (math.cos(a) * 0.16, math.sin(a) * 0.16, 1.22), (math.cos(a) * 0.3, math.sin(a) * 0.3, 1.1), (math.cos(a) * 0.4, math.sin(a) * 0.4, 0.9)]
        P.tube(pts, 0.018, 'foam', seg=4, ao=False, flat_idx=4)
    for k in range(6):
        a = k * math.tau / 6
    return P


def p_fire_hydrant(style):
    P = Prop('fire_hydrant', style, seed=405)
    P.lathe(0, 0, [(0.14, 0.0), (0.14, 0.04), (0.09, 0.08), (0.09, 0.4), (0.12, 0.44), (0.001, 0.5)], 'red', seg=8)
    P.cyl(0, 0, 0.44, 0.5, 0.12, 0.1, 'red', seg=8, ao=False, bias=1)
    P.between((-0.16, 0, 0.28), (0.16, 0, 0.28), 0.04, 0.04, 'red', seg=6)
    for x in (-0.18, 0.18):
        P.between((x, 0, 0.28), (x + math.copysign(0.03, x), 0, 0.28), 0.052, 0.052, 'chrome', seg=6)
    P.between((0, -0.09, 0.24), (0, -0.14, 0.24), 0.045, 0.045, 'red', seg=6)
    P.sphere((0, 0, 0.52), 0.04, 'yellow', subdiv=1, ao=False)
    return P


def p_market_stall(style):
    """Market stall, 2 cells wide: striped canvas awning on poles, counter with crates of fruit, a cloth banner."""
    P = Prop('market_stall', style, seed=406)
    for sx in (-1, 1):
        P.box((sx * 0.92 - 0.03, 0.2, 0.0), (sx * 0.92 + 0.03, 0.26, 1.15), 'wood_dark', bevel=0.006)
        P.box((sx * 0.92 - 0.03, -0.34, 0.0), (sx * 0.92 + 0.03, -0.28, 0.9), 'wood_dark', bevel=0.006)
    P.box((-0.98, -0.3, 0.42), (0.98, 0.22, 0.48), 'wood_orange', bevel=0.01, bias=1)
    P.box((-0.94, -0.28, 0.0), (0.94, 0.2, 0.42), 'wood_orange', bevel=0.014)
    P.box((-0.9, -0.292, 0.06), (0.9, -0.28, 0.36), 'wood_dark', bevel=0.006, ao=False)
    for i in range(10):
        m = 'red' if i % 2 == 0 else 'white'
        x0 = -1.0 + i * 0.2
        P.quad((x0, 0.25, 1.15), (x0 + 0.2, 0.25, 1.15), (x0 + 0.2, -0.42, 0.88), (x0, -0.42, 0.88), m, toward=(0, -0.3, 1), bias=1)
        P.quad((x0, -0.42, 0.88), (x0 + 0.2, -0.42, 0.88), (x0 + 0.2, -0.44, 0.8), (x0, -0.44, 0.8), m, toward=(0, -1, 0), bias=0)
    for i, (x, m) in enumerate(((-0.7, 'red'), (-0.25, 'orange'), (0.2, 'yellow'), (0.65, 'leaf'))):
        P.box((x - 0.17, -0.24, 0.48), (x + 0.17, 0.0, 0.58), 'wood_dark', bevel=0.008)
        rg = X.rs(410 + i)
        for k in range(6):
            P.sphere((x - 0.12 + (k % 3) * 0.12, -0.18 + (k // 3) * 0.12, 0.62), 0.058, m, subdiv=1, ao=False, flat_idx=3)
    return P


def p_flag_pole(style):
    """Flag pole with a blue pennant carrying a Poke Ball (waves through the wind shader)."""
    P = Prop('flag_pole', style, seed=407)
    P.lathe(0, 0, [(0.12, 0.0), (0.1, 0.05), (0.03, 0.12)], 'stone', seg=8)
    P.between((0, 0, 0.1), (0, 0, 2.1), 0.022, 0.014, 'chrome', seg=6)
    P.sphere((0, 0, 2.14), 0.04, 'brass', subdiv=1, ao=False)
    P.box((0.0, -0.005, 1.5), (0.7, 0.005, 2.0), 'blue', ao=False, bias=1)
    P.box((0.0, -0.008, 1.5), (0.7, -0.005, 1.56), 'white', ao=False)
    P.sphere((0.34, -0.01, 1.76), 0.1, 'ball_red', subdiv=1, ao=False)
    P.box((0.24, -0.02, 1.745), (0.44, -0.012, 1.775), 'ball_ink', ao=False)
    return P


def p_satellite_dish(style):
    """Roof dish on a mast with an LNB arm."""
    P = Prop('satellite_dish', style, seed=408)
    P.box((-0.12, -0.1, 0.0), (0.12, 0.1, 0.05), 'concrete', bevel=0.01)
    P.between((0, 0, 0.05), (0, 0, 0.3), 0.03, 0.025, 'steel', seg=6)

    def dish(S):
        S.lathe(0, 0, [(0.001, 0.0), (0.12, 0.02), (0.24, 0.07), (0.34, 0.15)], 'white_paint', seg=12, ao=False, bias=1)
        S.between((0, 0, 0.0), (0.0, 0.0, 0.3), 0.012, 0.012, 'graphite', seg=4)
        S.sphere((0, 0, 0.32), 0.035, 'graphite', subdiv=1, ao=False)
    rot_part(P, dish, Matrix.Translation((0, 0, 0.34)) @ Matrix.Rotation(math.radians(-115), 4, 'X'))
    return P


def p_windmill(style):
    """Small wooden windmill: tapered stone-and-timber tower, cap, four lattice sails on a hub."""
    P = Prop('windmill', style, seed=409)
    P.lathe(0, 0, [(0.62, 0.0), (0.5, 1.6)], 'stone', seg=8, rot=0.39)
    P.lathe(0, 0, [(0.5, 1.6), (0.56, 1.66), (0.56, 1.72), (0.001, 2.25)], 'roof_brown', seg=8, rot=0.39, bias=1)
    P.box((-0.12, -0.6, 0.0), (0.12, -0.5, 0.5), 'wood_dark', bevel=0.01)
    for z in (0.7, 1.15):
        P.box((-0.08, -0.54, z), (0.08, -0.47, z + 0.24), 'sky_glass', ao=False, flat_idx=2)
    P.between((0, -0.4, 1.9), (0, -0.65, 1.9), 0.06, 0.05, 'wood_dark', seg=6)

    def sails(S):
        for k in range(4):
            a = k * math.pi / 2 + 0.3
            d = Vector((math.cos(a), 0, math.sin(a)))
            S.between((0, 0, 0), d * 1.4, 0.03, 0.03, 'wood_dark', seg=4)
            n = Vector((-d.z, 0, d.x))
            for j in range(4):
                p = d * (0.35 + j * 0.27)
                S.quad(p + n * 0.02, p + n * 0.23, p + n * 0.23 + d * 0.2, p + n * 0.02 + d * 0.2, 'cloth_cream', toward=(0, -1, 0), ao=False, bias=1)
    rot_part(P, sails, Matrix.Translation((0, -0.7, 1.9)) @ Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Rotation(0, 4, 'Z'))
    return P


def p_wooden_gate(style):
    """Ranch gate: two posts, five-bar gate with diagonal brace and a latch, 1 cell wide."""
    P = Prop('wooden_gate', style, seed=410)
    for sx in (-1, 1):
        P.box((sx * 0.46 - 0.05, -0.05, 0.0), (sx * 0.46 + 0.05, 0.05, 0.86), 'wood_dark', bevel=0.012)
        P.box((sx * 0.46 - 0.06, -0.06, 0.84), (sx * 0.46 + 0.06, 0.06, 0.9), 'wood', bevel=0.008)
    for z in (0.16, 0.32, 0.48, 0.64):
        P.box((-0.4, -0.02, z), (0.4, 0.02, z + 0.06), 'wood_orange', bevel=0.006, bias=1)
    P.between((-0.4, -0.03, 0.18), (0.4, -0.03, 0.68), 0.022, 0.022, 'wood_orange', seg=4)
    P.box((0.3, -0.05, 0.4), (0.4, -0.03, 0.46), 'steel', bevel=0.004, ao=False)
    return P


def p_stone_arch(style):
    """Stone gateway arch, 3 cells wide: two pillars with capitals and a keystone arch between them."""
    P = Prop('stone_arch', style, seed=411)
    for sx in (-1, 1):
        x = sx * 1.1
        P.box((x - 0.26, -0.24, 0.0), (x + 0.26, 0.24, 0.16), 'stone', bevel=0.02)
        P.box((x - 0.2, -0.18, 0.16), (x + 0.2, 0.18, 1.5), 'stone', bevel=0.02, seg=2)
        P.box((x - 0.25, -0.23, 1.5), (x + 0.25, 0.23, 1.62), 'stone', bevel=0.02, bias=1)
    n = 9
    for i in range(n):
        a0 = math.pi - i * math.pi / n
        a1 = math.pi - (i + 1) * math.pi / n
        r0, r1 = 0.88, 1.12
        P.poly_prism([(math.cos(a0) * r0, 1.62 + math.sin(a0) * 0.6), (math.cos(a0) * r1, 1.62 + math.sin(a0) * 0.75), (math.cos(a1) * r1, 1.62 + math.sin(a1) * 0.75), (math.cos(a1) * r0, 1.62 + math.sin(a1) * 0.6)],
                     -0.2, 0.2, 'stone', bias=1 if i % 2 else 0)
    P.box((-0.1, -0.22, 2.16), (0.1, 0.22, 2.4), 'stone', bevel=0.02, bias=2)
    return P


def p_footbridge(style):
    """One cell of arched plank bridge running along X, with rope railings (bridges span water)."""
    P = Prop('footbridge', style, seed=412)
    for i in range(8):
        P.box((-0.5 + i * 0.125, -0.32, 0.0 + 0.08 * math.sin(i / 7 * math.pi)), (-0.5 + i * 0.125 + 0.11, 0.32, 0.05 + 0.08 * math.sin(i / 7 * math.pi)), 'wood_orange', bevel=0.006)
    for sy in (-1, 1):
        P.box((-0.5, sy * 0.32 - 0.02, 0.02), (0.5, sy * 0.32 + 0.02, 0.07), 'wood_dark', bevel=0.004)
    return P


def p_pier_post(style):
    P = Prop('pier_post', style, seed=413)
    P.between((0, 0, -0.2), (0, 0, 0.5), 0.07, 0.06, 'wood_dark', seg=7)
    P.cyl(0, 0, 0.48, 0.5, 0.07, 0.07, 'wood_pale', seg=7, cap_top=True, ao=False)
    P.tube([(0.06, 0, 0.3), (0.16, -0.06, 0.24), (0.14, -0.14, 0.22), (0.02, -0.1, 0.26), (0.0, -0.04, 0.3)], 0.014, 'rope', seg=4, ao=False)
    return P


def p_dock_plank(style):
    """A dock deck section (one cell): planks on stringers with nail heads."""
    P = Prop('dock_plank', style, seed=414)
    for i in range(6):
        P.box((-0.5 + i * 0.0, -0.5 + i * 0.17, 0.0), (0.5, -0.5 + i * 0.17 + 0.155, 0.06), 'wood_orange' if i % 2 else 'wood_light', bevel=0.006)
        for sx in (-0.4, 0.4):
            P.box((sx - 0.012, -0.5 + i * 0.17 + 0.07, 0.06), (sx + 0.012, -0.5 + i * 0.17 + 0.09, 0.064), 'steel', ao=False)
    return P


def p_rowboat(style):
    """Wooden rowboat, 2 cells long (along X), with thwarts, oars and a coiled rope."""
    P = Prop('rowboat', style, seed=415)
    n = 9
    for i in range(n):
        x0 = -0.95 + i * (1.9 / n)
        x1 = x0 + 1.9 / n
        def w(x):
            t = x / 0.95
            return 0.36 * math.sqrt(max(0.0, 1.0 - abs(t) ** 2.4))
        z0 = 0.06 + 0.1 * (abs(x0) / 0.95) ** 2
        z1 = 0.06 + 0.1 * (abs(x1) / 0.95) ** 2
        for sy in (-1, 1):
            P.quad((x0, sy * w(x0), z0 + 0.22), (x1, sy * w(x1), z1 + 0.22), (x1, sy * w(x1) * 0.55, z1), (x0, sy * w(x0) * 0.55, z0), 'wood_orange', toward=(0, sy, 0.5), bias=1 if i % 2 else 0)
            P.quad((x0, sy * w(x0) * 0.9, z0 + 0.2), (x1, sy * w(x1) * 0.9, z1 + 0.2), (x1, sy * w(x1) * 0.5, z1 + 0.02), (x0, sy * w(x0) * 0.5, z0 + 0.02), 'wood_dark', toward=(0, -sy, 0.5), ao=False)
        P.quad((x0, -w(x0) * 0.5, z0 + 0.02), (x1, -w(x1) * 0.5, z1 + 0.02), (x1, w(x1) * 0.5, z1 + 0.02), (x0, w(x0) * 0.5, z0 + 0.02), 'wood_pale', toward=(0, 0, 1), ao=False)
    for x in (-0.4, 0.05, 0.5):
        P.box((x - 0.05, -0.32, 0.2), (x + 0.05, 0.32, 0.24), 'wood_light', bevel=0.006)
    P.between((-0.1, -0.34, 0.3), (0.5, -0.7, 0.16), 0.014, 0.014, 'wood_pale', seg=4)
    P.box((0.5, -0.74, 0.14), (0.62, -0.66, 0.18), 'wood_pale', bevel=0.004)
    P.lathe(0.7, 0.0, [(0.001, 0.06), (0.09, 0.06), (0.09, 0.1), (0.05, 0.11)], 'rope', seg=8, ao=False)
    return P


def p_sailboat(style):
    """Little sailboat: white hull with red stripe, mast, mainsail and jib."""
    P = Prop('sailboat', style, seed=416)
    n = 10
    for i in range(n):
        x0 = -1.0 + i * (2.0 / n)
        x1 = x0 + 2.0 / n
        def w(x):
            t = x / 1.0
            return 0.38 * math.sqrt(max(0.0, 1.0 - max(0.0, t) ** 2.4 - 0.0 * t))
        z0 = 0.06 + 0.12 * max(0.0, x0) ** 2 + 0.06 * (x0 < 0) * (abs(x0)) ** 2
        z1 = 0.06 + 0.12 * max(0.0, x1) ** 2 + 0.06 * (x1 < 0) * (abs(x1)) ** 2
        for sy in (-1, 1):
            P.quad((x0, sy * w(x0), z0 + 0.3), (x1, sy * w(x1), z1 + 0.3), (x1, sy * w(x1) * 0.5, z1), (x0, sy * w(x0) * 0.5, z0), 'white', toward=(0, sy, 0.4))
            P.quad((x0, sy * w(x0), z0 + 0.27), (x1, sy * w(x1), z1 + 0.27), (x1, sy * w(x1) * 0.98, z1 + 0.22), (x0, sy * w(x0) * 0.98, z0 + 0.22), 'red', toward=(0, sy, 0.4), ao=False)
        P.quad((x0, -w(x0), z0 + 0.3), (x1, -w(x1), z1 + 0.3), (x1, w(x1), z1 + 0.3), (x0, w(x0), z0 + 0.3), 'wood_light', toward=(0, 0, 1), ao=False)
    P.between((0.0, 0, 0.3), (0.0, 0, 1.8), 0.028, 0.02, 'wood_pale', seg=6)
    P.tri((0.03, 0, 0.5), (0.03, 0, 1.75), (0.75, 0, 0.5), 'cloth_cream', toward=(0, -1, 0), ao=False, bias=1)
    P.tri((0.03, 0.01, 0.5), (0.03, 0.01, 1.75), (0.75, 0.01, 0.5), 'cloth_cream', toward=(0, 1, 0), ao=False)
    P.tri((-0.03, 0, 0.45), (-0.03, 0, 1.6), (-0.7, 0, 0.45), 'white', toward=(0, -1, 0), ao=False, bias=1)
    P.tri((-0.03, 0.01, 0.45), (-0.03, 0.01, 1.6), (-0.7, 0.01, 0.45), 'white', toward=(0, 1, 0), ao=False)
    P.between((0, 0, 0.5), (0.8, 0, 0.5), 0.016, 0.016, 'wood_pale', seg=4)
    return P


def p_lighthouse(style):
    """Striped lighthouse, 2 cells wide, 4.6 tall: tapered tower, gallery rail, glass lamp room and a cone roof."""
    P = Prop('lighthouse', style, seed=417)
    prof = [(0.76, 0.0), (0.7, 0.9), (0.6, 2.6), (0.48, 3.5)]
    n = 4
    for i in range(n):
        m = 'white' if i % 2 == 0 else 'red'
        z0 = i * 0.9
        z1 = (i + 1) * 0.9
        r0 = 0.76 - 0.07 * z0 / 0.9 * 0.55
        r1 = 0.76 - 0.07 * z1 / 0.9 * 0.55
        P.cyl(0, 0, z0, z1, r0, r1, m, seg=10, cap_top=False, rot=0.3)
    zt = 3.6
    P.cyl(0, 0, zt, zt + 0.1, 0.62, 0.62, 'graphite', seg=10, cap_top=True, rot=0.3)
    for k in range(10):
        a = k * math.tau / 10 + 0.3
        P.box((math.cos(a) * 0.6 - 0.02, math.sin(a) * 0.6 - 0.02, zt + 0.1), (math.cos(a) * 0.6 + 0.02, math.sin(a) * 0.6 + 0.02, zt + 0.35), 'graphite')
    P.lathe(0, 0, [(0.6, zt + 0.34), (0.62, zt + 0.34), (0.62, zt + 0.37), (0.6, zt + 0.37)], 'graphite', seg=10, rot=0.3, ao=False)
    P.cyl(0, 0, zt + 0.1, zt + 0.7, 0.36, 0.34, 'yellow', seg=8, cap_top=False, ao=False, flat_idx=4)
    for k in range(8):
        a = k * math.tau / 8
        P.box((math.cos(a) * 0.35 - 0.02, math.sin(a) * 0.35 - 0.02, zt + 0.1), (math.cos(a) * 0.35 + 0.02, math.sin(a) * 0.35 + 0.02, zt + 0.7), 'graphite')
    P.lathe(0, 0, [(0.46, zt + 0.7), (0.4, zt + 0.82), (0.2, zt + 0.98), (0.001, zt + 1.08)], 'red', seg=8)
    P.sphere((0, 0, zt + 1.12), 0.05, 'brass', subdiv=1, ao=False)
    P.box((-0.12, -0.78, 0.0), (0.12, -0.66, 0.5), 'wood_dark', bevel=0.01)
    return P


def p_street_sign(style):
    """Blue street-name plate on a post with an arrow board below."""
    P = Prop('street_sign', style, seed=418)
    P.between((0, 0, 0), (0, 0, 1.05), 0.025, 0.02, 'graphite', seg=6)
    sign_face(P, -0.3, 0.3, -0.03, 0.78, 1.02, 'blue', lines=2, ink='white')
    P.poly_prism([(-0.3, 0.55), (0.14, 0.55), (0.14, 0.5), (0.3, 0.63), (0.14, 0.76), (0.14, 0.7), (-0.3, 0.7)], -0.03, -0.01, 'white', ao=False)
    return P


def p_bin_street(style):
    """Street litter bin: green steel drum on a post ring with a flap and a paper cup."""
    P = Prop('bin_street', style, seed=419)
    P.cyl(0, 0, 0, 0.5, 0.2, 0.19, 'cloth_green', seg=10, cap_top=True)
    for z in (0.1, 0.4):
        P.lathe(0, 0, [(0.196, z - 0.015), (0.212, z), (0.196, z + 0.015)], 'steel', seg=10, ao=False)
    P.box((-0.1, -0.21, 0.28), (0.1, -0.19, 0.42), 'graphite', bevel=0.01)
    P.lathe(0, 0, [(0.2, 0.5), (0.2, 0.54), (0.001, 0.54)], 'steel', seg=10)
    P.cyl(0.07, -0.05, 0.54, 0.6, 0.04, 0.034, 'white', seg=6, ao=False)
    return P


def p_water_tower(style):
    """Elevated tank on a lattice frame, 2 cells wide, 3.3 tall."""
    P = Prop('water_tower', style, seed=420)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.between((sx * 0.5, sy * 0.5, 0.0), (sx * 0.4, sy * 0.4, 2.0), 0.04, 0.035, 'steel', seg=5)
    for z in (0.6, 1.2, 1.9):
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            k = 0.5 - 0.1 * z / 2.0
            P.between((a[0] * k, a[1] * k, z), (b[0] * k, b[1] * k, z), 0.018, 0.018, 'steel', seg=4)
    for s in (-1, 1):
        k0, k1 = 0.5 - 0.1 * 0.6 / 2.0, 0.5 - 0.1 * 1.2 / 2.0
        P.between((s * k0, -k0, 0.6), (-s * k1, -k1, 1.2), 0.014, 0.014, 'steel', seg=4)
    P.box((-0.46, -0.46, 1.98), (0.46, 0.46, 2.04), 'steel', bevel=0.01)
    P.lathe(0, 0, [(0.5, 2.04), (0.55, 2.3), (0.55, 2.9), (0.5, 3.0), (0.3, 3.2), (0.001, 3.28)], 'copper', seg=12, bias=0)
    for z in (2.24, 2.62, 2.96):
        P.lathe(0, 0, [(0.548, z - 0.02), (0.57, z), (0.548, z + 0.02)], 'graphite', seg=12, ao=False)
    P.between((0.4, 0, 2.06), (0.5, 0, 0.1), 0.02, 0.02, 'steel', seg=4)
    return P


def p_billboard(style):
    """Roadside billboard on two posts with a Poke Ball advert and catwalk."""
    P = Prop('billboard', style, seed=421)
    for sx in (-1, 1):
        P.box((sx * 0.7 - 0.04, -0.04, 0.0), (sx * 0.7 + 0.04, 0.04, 1.2), 'steel', bevel=0.006)
    P.box((-0.94, -0.06, 1.0), (0.94, 0.02, 1.86), 'graphite', bevel=0.012)
    P.box((-0.88, -0.07, 1.06), (0.88, -0.05, 1.8), 'sky_glass', ao=False, flat_idx=3)
    P.box((-0.88, -0.075, 1.06), (0.88, -0.06, 1.28), 'grass', ao=False, flat_idx=3)
    P.sphere((0.3, -0.1, 1.55), 0.24, 'ball_red', subdiv=1, ao=False)
    P.box((0.05, -0.11, 1.535), (0.55, -0.09, 1.575), 'ball_ink', ao=False)
    P.box((-0.7, -0.08, 1.5), (-0.2, -0.06, 1.62), 'white', ao=False)
    P.box((-0.7, -0.08, 1.3), (-0.3, -0.06, 1.4), 'white', ao=False)
    P.box((-0.94, -0.16, 0.94), (0.94, 0.0, 1.0), 'steel', bevel=0.006)
    return P


def p_telephone_pole(style):
    P = Prop('telephone_pole', style, seed=422)
    P.between((0, 0, 0), (0, 0, 2.6), 0.07, 0.055, 'wood_dark', seg=7)
    P.box((-0.4, -0.04, 2.3), (0.4, 0.04, 2.36), 'wood', bevel=0.006)
    P.box((-0.28, -0.035, 1.98), (0.28, 0.035, 2.03), 'wood', bevel=0.006)
    for x in (-0.36, -0.2, 0.2, 0.36):
        P.cyl(x, 0, 2.36, 2.42, 0.03, 0.02, 'porcelain', seg=5, ao=False)
    for x in (-0.24, 0.24):
        P.cyl(x, 0, 2.03, 2.08, 0.03, 0.02, 'porcelain', seg=5, ao=False)
    P.tube([(-0.4, 0, 2.4), (-0.1, 0, 2.3), (0.1, 0, 2.3), (0.4, 0, 2.4)], 0.008, 'graphite', seg=3, ao=False)
    return P


def p_barricade(style):
    """Striped road barrier with two blinker lamps."""
    P = Prop('barricade', style, seed=423)
    for sx in (-1, 1):
        P.between((sx * 0.4, -0.12, 0.0), (sx * 0.4, 0.0, 0.5), 0.02, 0.02, 'steel', seg=4)
        P.between((sx * 0.4, 0.12, 0.0), (sx * 0.4, 0.0, 0.5), 0.02, 0.02, 'steel', seg=4)
    for z in (0.32, 0.46):
        for i in range(6):
            P.box((-0.46 + i * 0.155, -0.03, z), (-0.46 + (i + 1) * 0.155, 0.01, z + 0.1), 'hazard' if i % 2 == 0 else 'graphite', bevel=0.004, bias=1)
    for x in (-0.36, 0.36):
        P.cyl(x, 0, 0.56, 0.62, 0.04, 0.04, 'led_amber', seg=6, ao=False, flat_idx=3)
    return P


def p_traffic_cone(style):
    P = Prop('traffic_cone', style, seed=424)
    P.box((-0.13, -0.13, 0.0), (0.13, 0.13, 0.03), 'graphite', bevel=0.006)
    P.lathe(0, 0, [(0.1, 0.03), (0.075, 0.2), (0.05, 0.36), (0.02, 0.4), (0.001, 0.4)], 'orange', seg=8, rot=0.39)
    P.lathe(0, 0, [(0.087, 0.14), (0.076, 0.21), (0.068, 0.21), (0.079, 0.14)], 'white', seg=8, rot=0.39, ao=False)
    return P


def p_hay_bale(style):
    P = Prop('hay_bale', style, seed=425)
    P.box((-0.34, -0.22, 0.0), (0.34, 0.22, 0.34), 'hay', bevel=0.03, seg=2)
    for x in (-0.16, 0.16):
        P.box((x - 0.012, -0.226, 0.0), (x + 0.012, 0.226, 0.344), 'rope', bevel=0.004, ao=False)
    rg = X.rs(426)
    for i in range(22):
        x = -0.32 + rg.random() * 0.64
        z = 0.03 + rg.random() * 0.28
        P.box((x, -0.232, z), (x + 0.1 + rg.random() * 0.08, -0.226, z + 0.012), 'straw' if i % 2 else 'hay', ao=False, bias=1)
    return P


def p_well(style):
    """Stone well: round wall with cap ring, timber frame, small roof, crank and bucket with rope."""
    P = Prop('well', style, seed=427)
    P.lathe(0, 0, [(0.4, 0.0), (0.4, 0.4), (0.44, 0.42), (0.44, 0.48), (0.3, 0.48), (0.3, 0.3)], 'stone', seg=10, rot=0.3)
    P.cyl(0, 0, 0.44, 0.44, 0.3, 0.3, 'water_deep', seg=10, cap_top=True, ao=False)
    for sx in (-1, 1):
        P.box((sx * 0.4 - 0.03, -0.04, 0.48), (sx * 0.4 + 0.03, 0.04, 1.2), 'wood_dark', bevel=0.006)
    P.between((-0.42, 0, 0.98), (0.48, 0, 0.98), 0.03, 0.03, 'wood_pale', seg=6)
    P.between((0.48, 0, 0.98), (0.6, 0.0, 0.98), 0.012, 0.012, 'steel', seg=4)
    P.between((0.6, 0.0, 0.98), (0.6, 0.0, 0.86), 0.012, 0.012, 'steel', seg=4)
    P.prism(-0.55, 0.55, -0.42, 0.42, 1.18, 1.5, 'roof_brown', ridge_y=0.0)
    P.between((0, 0, 0.96), (0, 0, 0.66), 0.006, 0.006, 'rope', seg=3)
    P.lathe(0, 0, [(0.07, 0.5), (0.085, 0.6), (0.08, 0.66)], 'wood', seg=7, ao=False)
    return P


def p_scarecrow(style):
    P = Prop('scarecrow', style, seed=428)
    P.between((0, 0, 0), (0, 0, 1.1), 0.028, 0.022, 'wood_dark', seg=5)
    P.between((-0.4, 0, 0.82), (0.4, 0, 0.82), 0.02, 0.02, 'wood_dark', seg=5)
    P.box((-0.15, -0.08, 0.5), (0.15, 0.08, 0.9), 'cloth_blue', bevel=0.03, seg=2)
    P.box((-0.4, -0.05, 0.75), (-0.15, 0.05, 0.85), 'cloth_blue', bevel=0.02)
    P.box((0.15, -0.05, 0.75), (0.4, 0.05, 0.85), 'cloth_blue', bevel=0.02)
    P.sphere((0, 0, 1.02), 0.11, 'straw', subdiv=1, ao=False)
    P.lathe(0, 0, [(0.2, 1.08), (0.18, 1.12), (0.09, 1.14), (0.09, 1.28), (0.001, 1.3)], 'wood_light', seg=8, ao=False)
    P.box((-0.06, -0.115, 1.03), (-0.03, -0.1, 1.06), 'graphite', ao=False)
    P.box((0.03, -0.115, 1.03), (0.06, -0.1, 1.06), 'graphite', ao=False)
    for x in (-0.42, 0.42):
        P.tube([(x, 0, 0.82), (x + math.copysign(0.04, x), 0, 0.72), (x + math.copysign(0.07, x), 0, 0.68)], 0.012, 'straw', seg=4, ao=False)
    return P


def p_buoy(style):
    P = Prop('buoy', style, seed=429)
    P.lathe(0, 0, [(0.001, 0.0), (0.22, 0.04), (0.28, 0.18), (0.22, 0.32), (0.1, 0.38)], 'red', seg=10)
    P.lathe(0, 0, [(0.25, 0.14), (0.28, 0.18), (0.26, 0.22), (0.23, 0.2)], 'white', seg=10, ao=False)
    P.between((0, 0, 0.36), (0, 0, 0.9), 0.02, 0.016, 'graphite', seg=5)
    P.sphere((0, 0, 0.94), 0.06, 'led_amber', subdiv=1, ao=False, flat_idx=3)
    P.cyl(0, 0, 0.012, 0.012, 0.5, 0.5, 'foam', seg=12, cap_top=True, ao=False, flat_idx=3)
    return P


def p_anchor(style):
    P = Prop('anchor', style, seed=430)
    P.between((0, 0, 0.05), (0, 0, 0.7), 0.028, 0.028, 'graphite', seg=5)
    P.tube([(0, 0, 0.7), (0.05, 0, 0.75), (0.0, 0, 0.8), (-0.05, 0, 0.75), (0, 0, 0.7)], 0.014, 'graphite', seg=4, ao=False)
    P.between((-0.14, 0, 0.6), (0.14, 0, 0.6), 0.024, 0.024, 'graphite', seg=5)
    P.tube([(-0.3, 0, 0.32), (-0.24, 0, 0.1), (-0.06, 0, 0.03), (0.0, 0, 0.08), (0.06, 0, 0.03), (0.24, 0, 0.1), (0.3, 0, 0.32)], 0.026, 'graphite', seg=5, ao=False)
    P.tri((-0.3, 0, 0.32), (-0.38, 0, 0.42), (-0.22, 0, 0.42), 'graphite', toward=(0, -1, 0), ao=False)
    P.tri((0.3, 0, 0.32), (0.38, 0, 0.42), (0.22, 0, 0.42), 'graphite', toward=(0, -1, 0), ao=False)
    return P


def p_container(style):
    """Corrugated shipping container, 2 cells long: red or blue by seed, door lock bars, corner castings."""
    P = Prop('container', style, seed=431)
    P.box((-0.94, -0.4, 0.06), (0.94, 0.4, 0.94), 'blue', bevel=0.02)
    for i in range(13):
        P.box((-0.9 + i * 0.14, -0.415, 0.1), (-0.9 + i * 0.14 + 0.07, -0.4, 0.9), 'blue', ao=False, bias=-1 if False else 1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.0, 0.88):
                P.box((sx * 0.94 - 0.05, sy * 0.4 - 0.05, z), (sx * 0.94 + 0.05, sy * 0.4 + 0.05, z + 0.12), 'graphite', bevel=0.008)
    P.box((0.8, -0.418, 0.12), (0.86, -0.4, 0.88), 'steel', bevel=0.004, ao=False)
    P.box((0.88, -0.418, 0.12), (0.92, -0.4, 0.88), 'steel', bevel=0.004, ao=False)
    return P


def p_cargo_crates(style):
    """Three stacked wooden cargo crates with strapping and a stencilled label."""
    P = Prop('cargo_crates', style, seed=432)
    P.box((-0.45, -0.3, 0.0), (0.05, 0.3, 0.5), 'wood_light', bevel=0.02)
    P.box((0.05, -0.3, 0.0), (0.5, 0.3, 0.42), 'wood_orange', bevel=0.02)
    P.box((-0.3, -0.26, 0.5), (0.2, 0.26, 0.9), 'wood_light', bevel=0.02)
    for (x0, x1, z0, z1) in ((-0.45, 0.05, 0.0, 0.5), (0.05, 0.5, 0.0, 0.42), (-0.3, 0.2, 0.5, 0.9)):
        zc = (z0 + z1) / 2
        yf = -0.3 if z0 < 0.4 else -0.26
        P.box((x0, yf - 0.012, zc - 0.02), (x1, yf, zc + 0.02), 'steel', ao=False)
        P.box(((x0 + x1) / 2 - 0.02, yf - 0.012, z0), ((x0 + x1) / 2 + 0.02, yf, z1), 'steel', ao=False)
    P.box((-0.4, -0.315, 0.32), (-0.1, -0.3, 0.42), 'paper_w', ao=False)
    P.box((-0.36, -0.32, 0.36), (-0.14, -0.315, 0.38), 'red', ao=False)
    return P


def p_life_ring(style):
    P = Prop('life_ring', style, seed=433)
    seg = 16
    for i in range(seg):
        a0 = i * math.tau / seg
        a1 = (i + 1) * math.tau / seg
        m = 'red' if (i // 2) % 2 == 0 else 'white'
        P.quad((math.cos(a0) * 0.2, 0, 0.3 + math.sin(a0) * 0.2), (math.cos(a1) * 0.2, 0, 0.3 + math.sin(a1) * 0.2),
               (math.cos(a1) * 0.1, 0, 0.3 + math.sin(a1) * 0.1), (math.cos(a0) * 0.1, 0, 0.3 + math.sin(a0) * 0.1), m, toward=(0, -1, 0), ao=False)
    return P


def p_power_pylon(style):
    """Lattice transmission pylon (Power Plant): four legs, cross bracing, two arms with insulators and cable stubs."""
    P = Prop('power_pylon', style, seed=434)
    H = 3.4
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.between((sx * 0.5, sy * 0.4, 0.0), (sx * 0.14, sy * 0.12, H), 0.03, 0.02, 'steel', seg=4)
    for z in (0.5, 1.2, 1.9, 2.6):
        k = 1.0 - z / H * 0.72
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            P.between((a[0] * 0.5 * k, a[1] * 0.4 * k, z), (b[0] * 0.5 * k, b[1] * 0.4 * k, z), 0.012, 0.012, 'steel', seg=3)
        k2 = 1.0 - (z + 0.7) / H * 0.72
        P.between((-0.5 * k, -0.4 * k, z), (0.5 * k2, -0.4 * k2, z + 0.7), 0.01, 0.01, 'steel', seg=3)
        P.between((0.5 * k, -0.4 * k, z), (-0.5 * k2, -0.4 * k2, z + 0.7), 0.01, 0.01, 'steel', seg=3)
    for z, w in ((2.9, 0.9), (3.2, 0.6)):
        P.between((-w, 0, z), (w, 0, z), 0.026, 0.026, 'steel', seg=4)
        for x in (-w, w):
            P.between((x, 0, z), (x, 0, z - 0.22), 0.02, 0.02, 'porcelain', seg=5)
            P.tube([(x, 0, z - 0.22), (x + math.copysign(0.05, x), 0.6, z - 0.32)], 0.012, 'graphite', seg=3, ao=False)
    return P


def p_incense_burner(style):
    """Pokemon Tower incense burner: tripod bowl with glowing embers and a wisp of smoke (a thin spiral)."""
    P = Prop('incense_burner', style, seed=435)
    for k in range(3):
        a = k * 2.094
        P.between((math.cos(a) * 0.16, math.sin(a) * 0.16, 0.0), (math.cos(a) * 0.08, math.sin(a) * 0.08, 0.2), 0.02, 0.016, 'brass', seg=4)
    P.lathe(0, 0, [(0.05, 0.18), (0.16, 0.24), (0.2, 0.34), (0.16, 0.36)], 'brass', seg=10)
    P.lathe(0, 0, [(0.16, 0.34), (0.001, 0.33)], 'lava', seg=10, ao=False, flat_idx=3)
    P.tube([(0, 0, 0.34), (0.04, 0.02, 0.5), (-0.03, 0.0, 0.64), (0.03, -0.02, 0.78)], 0.012, 'paper_w', seg=4, r_end=0.004, ao=False)
    return P


def p_candle_stand(style):
    P = Prop('candle_stand', style, seed=436)
    P.cyl(0, 0, 0, 0.04, 0.12, 0.1, 'brass', seg=8)
    P.between((0, 0, 0.04), (0, 0, 0.6), 0.02, 0.014, 'brass', seg=6)
    for sx in (-1, 0, 1):
        P.tube([(0, 0, 0.5), (sx * 0.1, 0, 0.56), (sx * 0.16, 0, 0.62)], 0.012, 'brass', seg=4, ao=False)
        P.cyl(sx * 0.16, 0, 0.62, 0.7, 0.02, 0.02, 'cloth_cream', seg=6, ao=False)
        P.sphere((sx * 0.16, 0, 0.72), 0.018, 'led_amber', subdiv=1, ao=False, flat_idx=4)
    return P


def p_town_sign(style):
    """Town welcome board: two posts, arched timber board with painted lettering lines and small roof."""
    P = Prop('town_sign', style, seed=437)
    for sx in (-1, 1):
        P.box((sx * 0.6 - 0.04, -0.03, 0.0), (sx * 0.6 + 0.04, 0.03, 1.0), 'wood_dark', bevel=0.008)
    P.box((-0.66, -0.05, 0.45), (0.66, 0.02, 0.95), 'wood_orange', bevel=0.02, seg=2)
    P.box((-0.6, -0.062, 0.5), (0.6, -0.05, 0.9), 'wood_light', bevel=0.008)
    for i, w in enumerate((0.8, 0.56)):
        P.box((-w / 2, -0.07, 0.78 - i * 0.16), (w / 2, -0.062, 0.85 - i * 0.16), 'wood_dark', ao=False)
    P.prism(-0.72, 0.72, -0.1, 0.1, 0.94, 1.08, 'roof_brown', ridge_y=0.0)
    return P


def p_safari_gate(style):
    """Safari Zone entrance frame, 3 cells wide: log posts, a header board and a hanging safari ball emblem."""
    P = Prop('safari_gate', style, seed=438)
    for sx in (-1, 1):
        P.between((sx * 1.2, 0, 0.0), (sx * 1.2, 0, 1.7), 0.09, 0.075, 'wood_dark', seg=7)
        P.sphere((sx * 1.2, 0, 1.74), 0.09, 'wood_light', subdiv=1, ao=False)
    P.box((-1.36, -0.05, 1.3), (1.36, 0.06, 1.62), 'cloth_green', bevel=0.02, seg=2)
    P.box((-1.3, -0.062, 1.34), (1.3, -0.05, 1.58), 'cloth_green', bevel=0.01, bias=1)
    sign_face(P, -0.9, 0.9, -0.06, 1.38, 1.54, 'cloth_cream', lines=1)
    P.sphere((0, -0.1, 1.05), 0.14, 'cloth_green', subdiv=2, ao=False)
    P.box((-0.15, -0.24, 1.03), (0.15, -0.2, 1.07), 'white', ao=False)
    P.tube([(0, 0, 1.3), (0, -0.04, 1.2), (0, -0.09, 1.16)], 0.008, 'rope', seg=3, ao=False)
    return P


def p_truck(style):
    """Delivery truck (Vermilion dock): cream box body on a blue cab, wheels with hubs, bumpers and mirrors."""
    P = Prop('truck', style, seed=439)
    P.box((-0.4, -0.5, 0.2), (0.96, 0.5, 1.02), 'cloth_cream', bevel=0.03, seg=2)
    P.box((-0.94, -0.48, 0.2), (-0.4, 0.48, 0.62), 'blue', bevel=0.04, seg=2)
    P.box((-0.86, -0.46, 0.62), (-0.46, 0.46, 0.92), 'blue', bevel=0.05, seg=2)
    P.box((-0.9, -0.42, 0.66), (-0.82, 0.42, 0.88), 'sky_glass', ao=False, flat_idx=2)
    P.box((-0.4, -0.5, 0.2), (0.96, 0.5, 0.26), 'graphite')
    P.box((-0.98, -0.48, 0.16), (-0.86, 0.48, 0.24), 'chrome', bevel=0.02)
    for x in (-0.6, 0.55):
        for sy in (-1, 1):
            y0, y1 = sy * 0.44, sy * 0.58
            P.between((x, y0, 0.18), (x, y1, 0.18), 0.17, 0.17, 'graphite', seg=10)
            P.between((x, y1, 0.18), (x, y1 + sy * 0.012, 0.18), 0.09, 0.09, 'steel', seg=8)
    P.box((0.96, -0.36, 0.3), (1.0, 0.36, 0.42), 'red', bevel=0.006, ao=False)
    P.box((-0.86, -0.53, 0.72), (-0.82, -0.5, 0.82), 'graphite')
    for sy in (-1, 1):
        P.box((-0.7, sy * 0.51 - 0.005, 0.38), (-0.44, sy * 0.51 + 0.005, 0.58), 'blue', ao=False, flat_idx=1)
    return P


def p_ship_funnel(style):
    """S.S. Anne funnel: oval red stack with white band, black top and steam pipes."""
    P = Prop('ship_funnel', style, seed=440)
    P.lathe(0, 0, [(0.52, 0.0), (0.46, 0.5), (0.4, 1.4)], 'red', seg=12, ao=True)
    P.lathe(0, 0, [(0.44, 0.7), (0.47, 0.72), (0.42, 1.0), (0.418, 0.98)], 'white', seg=12, ao=False, flat_idx=3)
    P.lathe(0, 0, [(0.4, 1.4), (0.42, 1.42), (0.42, 1.58), (0.34, 1.6), (0.001, 1.6)], 'graphite', seg=12)
    for x in (-0.22, 0.22):
        P.between((x, 0.3, 1.4), (x, 0.3, 1.7), 0.03, 0.03, 'steel', seg=5)
        P.sphere((x, 0.3, 1.72), 0.05, 'steel', subdiv=1, ao=False)
    return P


TOWN = {
    'mailbox': (p_mailbox, 'roadside mailbox with flag'),
    'lamp_post': (p_lamp_post, 'iron street lamp with lit lantern'),
    'park_bench': (p_park_bench, 'outdoor slatted bench'),
    'fountain': (p_fountain, 'town fountain, 2 x 2 cells'),
    'fire_hydrant': (p_fire_hydrant, 'fire hydrant'),
    'market_stall': (p_market_stall, 'striped-awning market stall, 2 cells'),
    'flag_pole': (p_flag_pole, 'flag pole with Poke Ball pennant'),
    'satellite_dish': (p_satellite_dish, 'roof satellite dish'),
    'windmill': (p_windmill, 'small windmill with lattice sails'),
    'wooden_gate': (p_wooden_gate, 'five-bar ranch gate'),
    'stone_arch': (p_stone_arch, 'stone gateway arch, 3 cells'),
    'footbridge': (p_footbridge, 'plank bridge section'),
    'pier_post': (p_pier_post, 'mooring post with rope'),
    'dock_plank': (p_dock_plank, 'dock deck cell'),
    'rowboat': (p_rowboat, 'rowboat with oars, 2 cells'),
    'sailboat': (p_sailboat, 'sailboat with mast and two sails, 2 cells'),
    'lighthouse': (p_lighthouse, 'striped lighthouse, 3.6 + lamp room'),
    'street_sign': (p_street_sign, 'street name plate with arrow'),
    'bin_street': (p_bin_street, 'street litter bin'),
    'water_tower': (p_water_tower, 'lattice water tower'),
    'billboard': (p_billboard, 'roadside billboard'),
    'telephone_pole': (p_telephone_pole, 'utility pole with insulators'),
    'barricade': (p_barricade, 'striped barrier with blinkers'),
    'traffic_cone': (p_traffic_cone, 'traffic cone'),
    'hay_bale': (p_hay_bale, 'hay bale'),
    'well': (p_well, 'stone well with roof and bucket'),
    'scarecrow': (p_scarecrow, 'scarecrow'),
    'buoy': (p_buoy, 'floating buoy with lamp'),
    'anchor': (p_anchor, 'ship anchor'),
    'container': (p_container, 'shipping container, 2 cells'),
    'cargo_crates': (p_cargo_crates, 'stack of cargo crates'),
    'life_ring': (p_life_ring, 'red/white life ring (wall mounted)'),
    'power_pylon': (p_power_pylon, 'lattice power pylon'),
    'incense_burner': (p_incense_burner, 'brass incense burner with smoke'),
    'candle_stand': (p_candle_stand, 'three-arm candle stand'),
    'town_sign': (p_town_sign, 'town welcome board'),
    'safari_gate': (p_safari_gate, 'Safari Zone entrance frame, 3 cells'),
    'truck': (p_truck, 'delivery truck (Vermilion dock)'),
    'ship_funnel': (p_ship_funnel, 'S.S. Anne funnel'),
}

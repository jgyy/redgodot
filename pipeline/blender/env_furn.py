"""Interior furniture, appliances and machines (bmesh, env_kit.Prop).  Sprite units: 1 = one map cell wide, vertical 1 =
one cell (Godot stretches Y by K so a prop reads exactly like the 2D sprite it replaces from the game camera); origin =
bottom centre of the footprint, front (toward the player camera) = Blender -Y.

Each function takes the style ('vcol' in-game, 'tex' kit) and returns a Prop.  `SETS` are modular families (tables,
counters, benches ... with a connectivity mask per piece) exported as ONE glb holding several meshes (PropKit picks the
mesh by name from the neighbouring cells).  Colours come from upstream's own sprites: white-lavender plastic with
green CRTs, orange-brown wood, red vending cabinets, black-bezel TVs with sky-blue glass ...
"""
import math

from mathutils import Vector, Matrix
from env_kit import Prop
import env_ext as X
from env_ext import bars, screen, legs4, rot_part, tilt_x, rot_z, sign_face


# ------------------------------------------------------------------------------------------ computers / TVs
def _monitor(P, cx, z0, w=0.56, h=0.42, d=0.09, mat='plastic', scr='screen', dark=False, tilt=6.0, y=0.02):
    """Flat monitor on a stand, screen toward -Y, leaned back by `tilt` degrees."""
    def build(S):
        S.box((cx - 0.13, y - 0.06, z0), (cx + 0.13, y + 0.10, z0 + 0.025), mat, bevel=0.008)               # foot
        S.box((cx - 0.035, y - 0.01, z0 + 0.02), (cx + 0.035, y + 0.055, z0 + 0.13), 'graphite', bevel=0.006)  # neck
        zb = z0 + 0.11
        S.box((cx - w / 2, y - d / 2, zb), (cx + w / 2, y + d / 2, zb + h), mat, bevel=0.022, seg=2)        # housing
        S.box((cx - w / 2 + 0.022, y - d / 2 - 0.006, zb + 0.022), (cx + w / 2 - 0.022, y - d / 2 + 0.002, zb + h - 0.022), 'graphite', bevel=0.008)   # bezel
        sx0, sx1, sz0, sz1 = cx - w / 2 + 0.05, cx + w / 2 - 0.05, zb + 0.05, zb + h - 0.05
        if dark:
            S.box((sx0, y - d / 2 - 0.012, sz0), (sx1, y - d / 2 - 0.004, sz1), 'graphite', ao=False, flat_idx=0)
            S.quad((sx0 + 0.04, y - d / 2 - 0.0135, sz1 - 0.03), (sx0 + 0.16, y - d / 2 - 0.0135, sz1 - 0.03),
                   (sx0 + 0.07, y - d / 2 - 0.0135, sz0 + 0.03), (sx0 + 0.02, y - d / 2 - 0.0135, sz0 + 0.03), 'graphite', toward=(0, -1, 0), ao=False, flat_idx=2)
        else:
            screen(S, sx0, sx1, y - d / 2 - 0.014, sz0, sz1, scr)
        S.box((cx + w / 2 - 0.09, y - d / 2 - 0.008, zb + 0.008), (cx + w / 2 - 0.06, y - d / 2 - 0.002, zb + 0.02), 'led_green', ao=False, flat_idx=3)
        S.box((cx - 0.06, y + d / 2, zb + 0.06), (cx + 0.06, y + d / 2 + 0.05, zb + h - 0.06), mat, bevel=0.02)   # back hump
    rot_part(P, build, tilt_x(tilt, (0, y, z0 + 0.03)))


def _keyboard(P, cx, y, z, w=0.42, mat='plastic_warm'):
    P.box((cx - w / 2, y - 0.075, z), (cx + w / 2, y + 0.075, z + 0.022), mat, bevel=0.008)
    for i in range(4):
        yy = y - 0.055 + i * 0.037
        P.box((cx - w / 2 + 0.02, yy, z + 0.022), (cx + w / 2 - 0.02, yy + 0.026, z + 0.031), 'graphite' if i % 2 == 0 else 'steel', ao=False, bias=0)
    P.box((cx - 0.09, y - 0.07, z + 0.022), (cx + 0.09, y - 0.05, z + 0.031), 'graphite', ao=False)


def p_pc(style, dark=False):
    """PC terminal (Pokemon Center / houses / labs): steel-lavender desk cabinet with drive bay, LCD monitor with a
    lit green screen, keyboard, mouse, mini-tower and cables."""
    P = Prop('pc_dark' if dark else 'pc', style, seed=211 if dark else 210)
    body = 'plastic'
    P.box((-0.46, -0.31, 0.0), (0.46, 0.27, 0.05), 'graphite', bevel=0.01)                   # kick plate
    P.box((-0.46, -0.31, 0.05), (0.46, 0.27, 0.40), body, bevel=0.02, seg=2)                    # desk cabinet
    P.box((-0.47, -0.32, 0.40), (0.47, 0.28, 0.435), 'plastic_warm', bevel=0.014, seg=2, bias=1)  # top slab
    # front: drive bay, drawer with handle, status LEDs
    P.box((-0.40, -0.322, 0.21), (-0.04, -0.306, 0.35), body, bevel=0.008, bias=1)
    P.box((-0.33, -0.331, 0.25), (-0.11, -0.319, 0.262), 'graphite', ao=False)
    P.box((-0.33, -0.331, 0.29), (-0.11, -0.319, 0.302), 'graphite', ao=False)
    P.box((0.04, -0.322, 0.21), (0.40, -0.306, 0.35), body, bevel=0.008, bias=1)
    P.box((0.14, -0.334, 0.28), (0.30, -0.318, 0.295), 'steel', bevel=0.004, ao=False)
    for x, m in ((-0.36, 'led_green'), (-0.30, 'led_amber')):
        P.box((x - 0.012, -0.326, 0.155), (x + 0.012, -0.31, 0.175), m, ao=False, flat_idx=3)
    P.box((-0.40, -0.322, 0.09), (0.40, -0.31, 0.11), 'graphite', ao=False, flat_idx=1)        # vent slot
    # monitor + keyboard + mouse
    _monitor(P, -0.06, 0.435, dark=dark, mat='plastic' if not dark else 'graphite')
    _keyboard(P, -0.06, -0.18, 0.435)
    P.box((0.19, -0.2, 0.435), (0.27, -0.13, 0.452), 'plastic_warm', bevel=0.012, seg=2)
    P.tube([(0.23, -0.13, 0.44), (0.23, -0.06, 0.442), (0.2, 0.0, 0.442), (0.12, 0.08, 0.46)], 0.006, 'graphite', seg=4, ao=False)
    # mini tower on the right
    P.box((0.29, -0.06, 0.435), (0.44, 0.22, 0.79), 'plastic_warm', bevel=0.016, seg=2)
    P.box((0.31, -0.072, 0.68), (0.42, -0.06, 0.70), 'graphite', ao=False)
    P.box((0.31, -0.072, 0.63), (0.42, -0.06, 0.65), 'graphite', ao=False)
    P.box((0.325, -0.074, 0.735), (0.345, -0.06, 0.755), 'led_green', ao=False, flat_idx=3)
    P.box((0.36, -0.074, 0.735), (0.38, -0.06, 0.755), 'led_amber', ao=False, flat_idx=3)
    bars(P, 0.31, 0.42, -0.068, 0.47, 0.60, 4, 'graphite', gap=0.5)
    # cables to the wall
    P.tube([(-0.06, 0.13, 0.5), (-0.06, 0.20, 0.46), (-0.02, 0.25, 0.436), (0.2, 0.27, 0.436), (0.34, 0.24, 0.5)], 0.008, 'graphite', seg=4, ao=False)
    return P


def p_pc_dark(style):
    return p_pc(style, dark=True)


def p_laptop(style):
    """Open laptop on a small stand (Red's room)."""
    P = Prop('laptop', style, seed=212)
    P.box((-0.34, -0.2, 0.0), (0.34, 0.22, 0.02), 'graphite', bevel=0.006)
    P.box((-0.3, -0.2, 0.02), (0.3, 0.16, 0.055), 'steel', bevel=0.012, seg=2)
    P.box((-0.25, -0.16, 0.055), (0.25, 0.02, 0.064), 'graphite', ao=False)
    for i in range(3):
        P.box((-0.24, -0.15 + i * 0.045, 0.064), (0.24, -0.12 + i * 0.045, 0.07), 'steel' if i % 2 else 'graphite', ao=False)
    P.box((-0.08, -0.192, 0.058), (0.08, -0.16, 0.066), 'steel', ao=False, bias=1)

    def lid(S):
        S.box((-0.3, 0.0, 0.0), (0.3, 0.03, 0.4), 'steel', bevel=0.014, seg=2)
        S.box((-0.27, -0.006, 0.03), (0.27, 0.002, 0.37), 'graphite', bevel=0.006, ao=False)
        screen(S, -0.24, 0.24, -0.012, 0.06, 0.34, 'crt', scan=6)
    rot_part(P, lid, Matrix.Translation((0, 0.16, 0.055)) @ Matrix.Rotation(math.radians(-14), 4, 'X') @ Matrix.Rotation(math.radians(0), 4, 'Z'))
    return P


def p_tv_crt(style, game=False):
    """CRT television on a low cabinet: bezelled sky-blue glass, knobs, speaker grille, aerial; `game` adds a console + pads."""
    P = Prop('tv_game' if game else 'tv_crt', style, seed=214 if game else 213)
    P.box((-0.42, -0.26, 0.0), (0.42, 0.26, 0.26), 'wood_orange', bevel=0.02, seg=2)
    P.box((-0.36, -0.272, 0.05), (-0.02, -0.256, 0.22), 'wood_orange', bevel=0.008, bias=1)
    P.box((0.02, -0.272, 0.05), (0.36, -0.256, 0.22), 'wood_orange', bevel=0.008, bias=1)
    for x in (-0.05, 0.05):
        P.box((x - 0.012, -0.28, 0.12), (x + 0.012, -0.264, 0.15), 'brass', ao=False)
    P.box((-0.44, -0.28, 0.26), (0.44, 0.28, 0.285), 'wood_orange', bevel=0.012, bias=1)
    # tube body
    P.box((-0.36, -0.2, 0.285), (0.36, 0.2, 0.74), 'graphite', bevel=0.03, seg=2)
    P.box((-0.24, 0.16, 0.34), (0.24, 0.3, 0.66), 'graphite', bevel=0.03)
    P.box((-0.3, -0.212, 0.335), (0.19, -0.19, 0.69), 'graphite', bevel=0.012, ao=False)
    P.box((-0.26, -0.222, 0.375), (0.15, -0.205, 0.655), 'sky_glass', ao=False, flat_idx=3)
    P.quad((-0.24, -0.224, 0.64), (-0.12, -0.224, 0.64), (-0.19, -0.224, 0.39), (-0.24, -0.224, 0.39), 'sky_glass', toward=(0, -1, 0), ao=False, flat_idx=4)
    P.quad((-0.02, -0.224, 0.64), (0.05, -0.224, 0.64), (-0.03, -0.224, 0.55), (-0.08, -0.224, 0.55), 'sky_glass', toward=(0, -1, 0), ao=False, flat_idx=4)
    P.blob((0.28, -0.213, 0.62), (0.036, 0.02, 0.036), 'steel', subdiv=1, ao=False)               # knobs
    P.blob((0.28, -0.213, 0.53), (0.036, 0.02, 0.036), 'steel', subdiv=1, ao=False)
    bars(P, 0.23, 0.33, -0.216, 0.36, 0.46, 4, 'graphite', gap=0.55, bias=2)
    # rabbit-ear aerial
    P.between((0.0, 0.0, 0.74), (-0.22, 0.02, 0.98), 0.006, 0.004, 'steel', seg=4)
    P.between((0.0, 0.0, 0.74), (0.24, 0.02, 0.96), 0.006, 0.004, 'steel', seg=4)
    if game:
        P.box((-0.34, -0.245, 0.285), (-0.08, -0.13, 0.318), 'plastic_warm', bevel=0.008)
        P.box((-0.3, -0.252, 0.29), (-0.24, -0.246, 0.31), 'graphite', ao=False)
        P.box((-0.2, -0.252, 0.295), (-0.12, -0.246, 0.305), 'led_red', ao=False, flat_idx=3)
        P.tube([(-0.2, -0.15, 0.3), (-0.12, -0.26, 0.29), (0.0, -0.36, 0.286), (0.12, -0.34, 0.286)], 0.006, 'graphite', seg=4, ao=False)
        P.box((0.1, -0.4, 0.286), (0.23, -0.31, 0.306), 'plastic_warm', bevel=0.014, seg=2)
        P.box((0.12, -0.39, 0.306), (0.14, -0.34, 0.314), 'graphite', ao=False)
        P.box((0.19, -0.37, 0.306), (0.21, -0.35, 0.314), 'led_red', ao=False)
    return P


def p_tv_game(style):
    return p_tv_crt(style, game=True)


def p_game_console(style):
    """Retro console with controller and a cartridge sticking out (Celadon game room)."""
    P = Prop('game_console', style, seed=215)
    P.box((-0.36, -0.2, 0.0), (0.36, 0.2, 0.12), 'plastic_warm', bevel=0.018, seg=2)
    P.box((-0.2, -0.212, 0.06), (0.2, -0.2, 0.09), 'graphite', ao=False)
    P.box((-0.3, -0.212, 0.03), (-0.24, -0.2, 0.05), 'led_red', ao=False, flat_idx=3)
    P.box((-0.13, -0.05, 0.12), (0.13, 0.08, 0.2), 'led_blue', bevel=0.008)
    P.box((-0.11, -0.07, 0.2), (0.11, 0.09, 0.204), 'graphite', ao=False)
    P.box((0.2, -0.36, 0.0), (0.34, -0.26, 0.03), 'plastic_warm', bevel=0.012, seg=2)
    P.tube([(0.2, -0.3, 0.01), (0.08, -0.26, 0.006), (0.0, -0.22, 0.02)], 0.005, 'graphite', seg=4, ao=False)
    P.box((0.23, -0.33, 0.03), (0.25, -0.31, 0.037), 'led_red', ao=False)
    return P


def p_server_rack(style):
    """Silph Co. / lab data rack: tall graphite cabinet, bays of blinking lights and drive faces."""
    P = Prop('server_rack', style, seed=216)
    P.box((-0.44, -0.3, 0.0), (0.44, 0.24, 1.0), 'graphite', bevel=0.02, seg=2)
    P.box((-0.46, -0.31, 0.0), (0.46, 0.25, 0.05), 'steel', bevel=0.01)
    r = X.rs(7)
    for i in range(8):
        z = 0.09 + i * 0.108
        P.box((-0.4, -0.312, z), (0.4, -0.3, z + 0.09), 'graphite', bevel=0.004, bias=2)
        P.box((-0.37, -0.318, z + 0.03), (-0.1, -0.306, z + 0.06), 'steel', ao=False, bias=0)
        for k in range(6):
            m = r.choice(['led_green', 'led_green', 'led_amber', 'led_red', 'led_blue'])
            P.box((0.0 + k * 0.05, -0.32, z + 0.04), (0.02 + k * 0.05, -0.306, z + 0.06), m, ao=False, flat_idx=3)
    P.box((-0.44, -0.3, 1.0), (0.44, 0.24, 1.03), 'steel', bevel=0.012, bias=1)
    return P


def p_cash_register(style):
    """Mart till: register with keypad, display and pull-out drawer, on a small mat."""
    P = Prop('cash_register', style, seed=217)
    P.box((-0.28, -0.2, 0.0), (0.28, 0.2, 0.16), 'steel', bevel=0.014, seg=2)
    P.box((-0.26, -0.212, 0.03), (0.26, -0.2, 0.11), 'plastic_warm', bevel=0.006)
    P.box((-0.05, -0.222, 0.06), (0.05, -0.208, 0.075), 'brass', ao=False)

    def top(S):
        S.box((-0.26, -0.18, 0.0), (0.26, 0.16, 0.05), 'plastic_warm', bevel=0.014, seg=2)
        for i in range(3):
            for j in range(4):
                S.box((-0.2 + j * 0.06, -0.15 + i * 0.045, 0.05), (-0.16 + j * 0.06, -0.12 + i * 0.045, 0.058), 'graphite' if (i + j) % 3 else 'led_amber', ao=False)
    rot_part(P, top, Matrix.Translation((0, 0, 0.16)) @ Matrix.Rotation(math.radians(-14), 4, 'X'))
    P.box((-0.2, 0.08, 0.16), (0.2, 0.14, 0.34), 'graphite', bevel=0.01)
    screen(P, -0.16, 0.16, 0.076, 0.21, 0.31, 'led_green', scan=3, glare=False, depth=0.004)
    P.box((0.12, -0.3, 0.0), (0.26, -0.22, 0.03), 'paper_w', bevel=0.004)
    return P


def p_vending_machine(style):
    """Red drinks machine: glass window with three shelves of cans, coin slot, buttons and delivery flap."""
    P = Prop('vending_machine', style, seed=218)
    P.box((-0.42, -0.34, 0.0), (0.42, 0.28, 1.25), 'red', bevel=0.03, seg=2)
    P.box((-0.44, -0.35, 0.0), (0.44, 0.29, 0.06), 'graphite', bevel=0.008)
    P.box((-0.34, -0.352, 0.5), (0.1, -0.33, 1.12), 'graphite', bevel=0.012)                    # window frame
    P.box((-0.3, -0.36, 0.54), (0.06, -0.345, 1.08), 'sky_glass', ao=False, flat_idx=2)
    r = X.rs(3)
    for row in range(3):
        z = 0.58 + row * 0.17
        P.box((-0.3, -0.36, z - 0.012), (0.06, -0.31, z), 'steel', ao=False)
        for k in range(6):
            m = r.choice(['blue', 'yellow', 'white', 'orange', 'led_green'])
            P.cyl(-0.27 + k * 0.06, -0.34, z, z + 0.11, 0.024, 0.024, m, seg=6, ao=False, bias=1)
    P.box((0.16, -0.352, 0.86), (0.36, -0.336, 1.12), 'graphite', bevel=0.008)                 # coin panel
    for i in range(3):
        for j in range(2):
            P.box((0.19 + j * 0.08, -0.362, 0.99 + i * 0.045), (0.24 + j * 0.08, -0.348, 1.02 + i * 0.045), 'white' if (i + j) % 2 else 'yellow', ao=False)
    P.box((0.2, -0.36, 0.86), (0.32, -0.348, 0.89), 'led_red', ao=False, flat_idx=3)
    P.box((-0.26, -0.352, 0.12), (0.34, -0.336, 0.34), 'graphite', bevel=0.012)                # delivery flap
    P.box((-0.2, -0.36, 0.2), (0.28, -0.346, 0.3), 'graphite', ao=False, flat_idx=0)
    P.box((-0.4, -0.352, 1.14), (0.4, -0.34, 1.23), 'white', bevel=0.006, bias=1)                # lit header
    P.box((-0.28, -0.358, 1.17), (0.28, -0.348, 1.2), 'red', ao=False, flat_idx=3)
    return P


def p_slot_machine(style):
    """Game Corner slot machine: cabinet with three reels in a window, lever, marquee lights, coin tray."""
    P = Prop('slot_machine', style, seed=219)
    P.box((-0.36, -0.28, 0.0), (0.36, 0.26, 0.14), 'graphite', bevel=0.014)
    P.box((-0.34, -0.26, 0.14), (0.34, 0.24, 0.66), 'gold_paint', bevel=0.03, seg=2)
    P.box((-0.28, -0.272, 0.36), (0.28, -0.25, 0.6), 'graphite', bevel=0.012)                    # reel window frame
    for i in range(3):
        x = -0.2 + i * 0.2
        P.box((x - 0.075, -0.28, 0.4), (x + 0.075, -0.262, 0.56), 'white', ao=False, flat_idx=3)
        P.box((x - 0.03, -0.288, 0.44), (x + 0.03, -0.278, 0.5), ['red', 'led_blue', 'led_amber'][i], ao=False, flat_idx=2)
    P.box((-0.3, -0.29, 0.24), (0.3, -0.25, 0.34), 'graphite', bevel=0.012)                      # control deck
    for i in range(5):
        P.box((-0.22 + i * 0.11, -0.3, 0.27), (-0.14 + i * 0.11, -0.276, 0.3), ['red', 'led_amber', 'led_green', 'led_blue', 'red'][i], ao=False, flat_idx=3)
    P.box((-0.14, -0.3, 0.16), (0.14, -0.26, 0.21), 'steel', bevel=0.008)                        # coin tray
    P.box((-0.3, -0.26, 0.66), (0.3, 0.2, 0.9), 'red', bevel=0.02, seg=2)                         # marquee
    P.box((-0.26, -0.272, 0.7), (0.26, -0.262, 0.86), 'yellow', bevel=0.006)
    for i in range(6):
        P.sphere((-0.23 + i * 0.092, -0.28, 0.885), 0.022, 'led_amber' if i % 2 else 'white', subdiv=1, ao=False, flat_idx=4)
    P.between((0.34, -0.1, 0.4), (0.44, -0.1, 0.56), 0.012, 0.012, 'chrome', seg=5)               # lever
    P.sphere((0.44, -0.1, 0.6), 0.038, 'led_red', subdiv=1, ao=False)
    return P


# ------------------------------------------------------------------------------------------ Pokemon Center
def p_heal_machine(style):
    """Pokemon Center healing machine, 2 x 2 cells: a white wall unit with the pink cross, a slanted tray holding six
    Poke Balls in their cradles, a lit status strip and hose, on a panelled counter base."""
    P = Prop('heal_machine', style, seed=220)
    # rear cabinet against the wall
    P.box((-0.96, 0.1, 0.0), (0.96, 0.62, 1.2), 'plastic', bevel=0.03, seg=2)
    P.box((-0.9, 0.08, 1.2), (0.9, 0.6, 1.26), 'plastic_warm', bevel=0.012, bias=1)
    for x in (-0.5, 0.0, 0.5):
        P.box((x - 0.008, 0.088, 0.1), (x + 0.008, 0.1, 1.12), 'plastic', flat_idx=1, ao=False)
    P.box((-0.96, 0.088, 0.0), (0.96, 0.6, 0.06), 'graphite', bevel=0.006)
    # pink cross emblem panel
    P.box((-0.22, 0.086, 0.82), (0.22, 0.1, 1.14), 'white', bevel=0.012)
    P.box((-0.05, 0.078, 0.87), (0.05, 0.088, 1.09), 'pk_red_roof', ao=False, flat_idx=3)
    P.box((-0.13, 0.078, 0.94), (0.13, 0.088, 1.04), 'pk_red_roof', ao=False, flat_idx=3)
    # front console (counter height) with slanted tray
    P.box((-0.9, -0.62, 0.0), (0.9, 0.12, 0.5), 'plastic', bevel=0.026, seg=2)
    P.box((-0.9, -0.632, 0.0), (0.9, -0.62, 0.06), 'graphite')
    for x in (-0.6, 0.0, 0.6):
        P.box((x - 0.24, -0.634, 0.1), (x + 0.24, -0.622, 0.4), 'plastic', bevel=0.01, bias=1)
    P.box((-0.9, -0.66, 0.5), (0.9, 0.14, 0.53), 'plastic_warm', bevel=0.012, seg=2, bias=1)

    def tray(S):
        S.box((-0.72, -0.4, 0.0), (0.72, 0.4, 0.06), 'steel', bevel=0.014, seg=2)
        S.box((-0.72, -0.4, 0.06), (0.72, -0.34, 0.12), 'steel', bevel=0.01)
        S.box((-0.72, 0.34, 0.06), (0.72, 0.4, 0.12), 'steel', bevel=0.01)
        S.box((-0.72, -0.4, 0.06), (-0.66, 0.4, 0.12), 'steel', bevel=0.01)
        S.box((0.66, -0.4, 0.06), (0.72, 0.4, 0.12), 'steel', bevel=0.01)
        S.box((-0.66, -0.34, 0.06), (0.66, 0.34, 0.075), 'led_blue', ao=False, flat_idx=1)
        for k in range(6):
            cx = -0.5 + (k % 3) * 0.5
            cy = -0.12 + (k // 3) * -0.0 + (0.14 if k >= 3 else -0.14)
            S.lathe(cx, cy, [(0.085, 0.075), (0.12, 0.085), (0.12, 0.11), (0.09, 0.115)], 'steel', seg=10, ao=False)   # cradle
            S.lathe(cx, cy, [(0.001, 0.09), (0.095, 0.1), (0.1, 0.13)], 'graphite', seg=10, ao=False)
            # ball in the cradle: red cap + white belly + black band + button
            S.lathe(cx, cy, [(0.001, 0.09), (0.09, 0.115), (0.105, 0.15)], 'ball_white', seg=10, ao=False)
            S.lathe(cx, cy, [(0.106, 0.152), (0.108, 0.16), (0.1, 0.166)], 'ball_ink', seg=10, ao=False)
            S.lathe(cx, cy, [(0.1, 0.168), (0.09, 0.2), (0.05, 0.226), (0.001, 0.234)], 'ball_red', seg=10, ao=False)
            S.box((cx - 0.02, cy - 0.11, 0.166), (cx + 0.02, cy - 0.096, 0.198), 'ball_white', ao=False, flat_idx=4)
    rot_part(P, tray, Matrix.Translation((0, -0.26, 0.53)) @ Matrix.Rotation(math.radians(8), 4, 'X'))
    # status lamps and glow strip on the console face
    for i, m in enumerate(('led_green', 'led_green', 'led_green', 'led_amber', 'led_red', 'led_blue')):
        P.sphere((-0.66 + i * 0.26, -0.646, 0.44), 0.026, m, subdiv=1, ao=False, flat_idx=4)
    P.tube([(0.86, 0.1, 0.9), (0.98, 0.0, 0.8), (1.0, -0.3, 0.55), (0.9, -0.55, 0.52)], 0.03, 'graphite', seg=6, ao=False)
    return P


def p_heal_cabinet(style):
    """Single-cell Pokemon Center wall cabinet (lone machine cell): white panel with slot, green lamp, cross plate."""
    P = Prop('heal_cabinet', style, seed=221)
    P.box((-0.46, -0.16, 0.0), (0.46, 0.34, 0.9), 'plastic', bevel=0.026, seg=2)
    P.box((-0.4, -0.172, 0.5), (0.4, -0.16, 0.84), 'plastic_warm', bevel=0.008, bias=1)
    P.box((-0.16, -0.18, 0.6), (0.16, -0.17, 0.75), 'white', bevel=0.006)
    P.box((-0.03, -0.186, 0.62), (0.03, -0.178, 0.73), 'pk_red_roof', ao=False, flat_idx=3)
    P.box((-0.07, -0.186, 0.655), (0.07, -0.178, 0.695), 'pk_red_roof', ao=False, flat_idx=3)
    P.box((-0.3, -0.18, 0.22), (0.3, -0.168, 0.3), 'graphite', bevel=0.006, ao=False)
    P.box((-0.24, -0.186, 0.14), (0.24, -0.174, 0.155), 'led_green', ao=False, flat_idx=3)
    return P


# ------------------------------------------------------------------------------------------ storage / display
_BOOK = ['red', 'blue', 'yellow', 'pink', 'white', 'leaf', 'orange', 'purple', 'teal']


def p_bookshelf(style, hgt=1.35):
    """Tall bookcase: carcass with plinth and cornice, five shelves of varied books (leaning, stacked, gaps), globes."""
    P = Prop('bookshelf', style, seed=222)
    P.box((-0.5, -0.06, 0.0), (-0.45, 0.36, hgt), 'wood_orange', bevel=0.012, seg=2)                     # sides
    P.box((0.45, -0.06, 0.0), (0.5, 0.36, hgt), 'wood_orange', bevel=0.012, seg=2)
    P.box((-0.46, 0.3, 0.04), (0.46, 0.36, hgt - 0.02), 'wood_dark', ao=False, flat_idx=0)              # back panel
    P.box((-0.5, -0.08, 0.0), (0.5, 0.0, 0.09), 'wood_dark', bevel=0.008)                                   # plinth
    P.box((-0.53, -0.09, hgt - 0.05), (0.53, 0.38, hgt + 0.02), 'wood_orange', bevel=0.012, bias=1)         # cornice
    rg = X.rs(5)
    nshelf = 4
    for s in range(nshelf + 1):
        z = 0.1 + s * (hgt - 0.2) / nshelf
        P.box((-0.46, -0.09, z), (0.46, 0.32, z + 0.03), 'wood_orange', bevel=0.005, bias=1)
        if s == nshelf:
            break
        top = z + 0.03
        gap = (hgt - 0.2) / nshelf - 0.03
        x = -0.42
        while x < 0.36:
            if rg.random() < 0.09:
                x += rg.uniform(0.05, 0.12)
                continue
            w = rg.uniform(0.032, 0.062)
            h = rg.uniform(0.6, 0.95) * gap
            m = rg.choice(_BOOK)
            if rg.random() < 0.08:            # a leaning book
                P.box((x, -0.06, top), (x + w * 2.6, 0.2, top + 0.03), m, ao=False)
                x += w * 2.7
                continue
            P.box((x, -0.06, top), (x + w, 0.2, top + h), m, ao=False, bias=1)
            P.box((x + w * 0.2, -0.066, top + h * 0.5), (x + w * 0.8, -0.06, top + h * 0.55), 'gold_paint', ao=False, flat_idx=3)   # spine label
            x += w + 0.004
    return P


def p_bookshelf_low(style):
    return p_bookshelf(style, hgt=0.9)


def p_mart_shelf(style, hgt=1.3):
    """Mart goods shelf: steel uprights, four levels stocked with potions, balls, boxes and cans in pastel packs."""
    P = Prop('mart_shelf', style, seed=223)
    P.box((-0.5, -0.02, 0.0), (0.5, 0.36, 0.06), 'graphite', bevel=0.008)
    for x in (-0.5, 0.46):
        P.box((x, -0.02, 0.0), (x + 0.04, 0.36, hgt), 'steel', bevel=0.006)
    P.box((-0.5, 0.32, 0.0), (0.5, 0.36, hgt), 'plastic_warm', ao=False, bias=0)
    rg = X.rs(11)
    for s in range(4):
        z = 0.08 + s * (hgt - 0.12) / 4
        P.box((-0.5, -0.04, z), (0.5, 0.36, z + 0.024), 'steel', bevel=0.004, bias=1)
        P.box((-0.5, -0.05, z), (0.5, -0.03, z + 0.05), 'led_amber' if s % 2 else 'plastic', ao=False, bias=1)   # price rail
        top = z + 0.024
        x = -0.44
        while x < 0.4:
            kind = rg.random()
            if kind < 0.35:      # potion bottle
                m = rg.choice(['pk_pink', 'led_blue', 'purple', 'led_green', 'yellow'])
                P.cyl(x + 0.04, 0.08, top, top + 0.12, 0.035, 0.035, m, seg=6, ao=False, bias=1)
                P.cyl(x + 0.04, 0.08, top + 0.12, top + 0.16, 0.014, 0.014, 'white', seg=5, ao=False)
                x += 0.09
            elif kind < 0.6:     # box
                m = rg.choice(['red', 'blue', 'yellow', 'white', 'orange'])
                P.box((x, 0.0, top), (x + 0.1, 0.16, top + rg.uniform(0.1, 0.19)), m, ao=False, bias=1)
                x += 0.11
            elif kind < 0.8:     # ball
                P.sphere((x + 0.04, 0.09, top + 0.04), 0.04, rg.choice(['ball_red', 'ball_white', 'led_blue']), subdiv=1, ao=False)
                x += 0.09
            else:                # can stack
                m = rg.choice(['orange', 'red', 'cloth_green'])
                for k in range(2):
                    P.cyl(x + 0.04, 0.09, top + k * 0.09, top + k * 0.09 + 0.085, 0.036, 0.036, m, seg=6, ao=False)
                x += 0.09
    return P


def p_cabinet_wood(style):
    """Two-drawer + door cabinet in orange-brown wood with brass knobs and a plinth; small lamp/plant free top."""
    P = Prop('cabinet_wood', style, seed=224)
    P.box((-0.46, -0.16, 0.0), (0.46, 0.34, 0.66), 'wood_orange', bevel=0.02, seg=2)
    P.box((-0.48, -0.17, 0.66), (0.48, 0.36, 0.7), 'wood_orange', bevel=0.014, bias=1)
    P.box((-0.44, -0.176, 0.0), (0.44, -0.16, 0.07), 'wood_dark', bevel=0.004)
    for i, (x0, x1) in enumerate(((-0.42, -0.02), (0.02, 0.42))):
        for z0, z1 in ((0.38, 0.6), (0.09, 0.34)):
            P.box((x0, -0.186, z0), (x1, -0.17, z1), 'wood_orange', bevel=0.01, bias=1)
            xm = (x0 + x1) / 2
            P.box((xm - 0.045, -0.2, (z0 + z1) / 2 - 0.008), (xm + 0.045, -0.186, (z0 + z1) / 2 + 0.012), 'brass', bevel=0.004, ao=False)
    return P


def p_display_case(style):
    """Glass display case (museum / bike shop): wood plinth, glass box with brass edges and a spot of merchandise."""
    P = Prop('display_case', style, seed=225)
    P.box((-0.46, -0.28, 0.0), (0.46, 0.26, 0.36), 'wood_orange', bevel=0.02, seg=2)
    P.box((-0.4, -0.292, 0.06), (0.4, -0.28, 0.3), 'wood_dark', bevel=0.006, ao=False)
    P.box((-0.46, -0.28, 0.36), (0.46, 0.26, 0.4), 'brass', bevel=0.01)
    P.box((-0.42, -0.24, 0.4), (0.42, 0.22, 0.42), 'plastic_warm')
    for x in (-0.44, 0.42):
        for y in (-0.28, 0.24):
            P.box((x, y, 0.4), (x + 0.04, y + 0.04, 0.78), 'brass', bevel=0.004)
    P.box((-0.44, -0.28, 0.76), (0.46, 0.26, 0.8), 'brass', bevel=0.008)
    P.quad((-0.36, -0.272, 0.74), (-0.18, -0.272, 0.74), (-0.3, -0.272, 0.44), (-0.4, -0.272, 0.44), 'sky_glass', toward=(0, -1, 0), ao=False, flat_idx=4)
    P.quad((0.1, -0.272, 0.74), (0.16, -0.272, 0.74), (0.08, -0.272, 0.5), (0.03, -0.272, 0.5), 'sky_glass', toward=(0, -1, 0), ao=False, flat_idx=3)
    P.box((-0.26, -0.1, 0.42), (-0.06, 0.06, 0.46), 'cloth_red', bevel=0.006)
    P.sphere((-0.16, -0.02, 0.5), 0.05, 'gold_paint', subdiv=1, ao=False)
    P.box((0.08, -0.1, 0.42), (0.3, 0.06, 0.44), 'cloth_blue')
    P.cyl(0.2, -0.02, 0.44, 0.52, 0.03, 0.03, 'led_blue', seg=6, ao=False)
    return P


def p_fridge(style):
    """Two-door fridge/freezer: rounded body, chrome handles, magnet notes, vent grille."""
    P = Prop('fridge', style, seed=226)
    P.box((-0.4, -0.28, 0.0), (0.4, 0.3, 1.32), 'plastic', bevel=0.036, seg=2)
    P.box((-0.4, -0.29, 0.86), (0.4, -0.274, 0.88), 'graphite', flat_idx=0, ao=False)
    P.box((-0.36, -0.294, 0.9), (0.36, -0.276, 1.28), 'plastic', bevel=0.014, bias=1)
    P.box((-0.36, -0.294, 0.06), (0.36, -0.276, 0.84), 'plastic', bevel=0.014, bias=1)
    P.box((0.24, -0.312, 0.94), (0.28, -0.29, 1.2), 'chrome', bevel=0.008, ao=False)
    P.box((0.24, -0.312, 0.46), (0.28, -0.29, 0.78), 'chrome', bevel=0.008, ao=False)
    for x, z, m in ((-0.2, 1.12, 'led_red'), (-0.1, 1.04, 'led_blue'), (-0.26, 0.98, 'yellow')):
        P.box((x, -0.298, z), (x + 0.06, -0.29, z + 0.06), m, ao=False, flat_idx=3)
    bars(P, -0.3, 0.1, -0.278, 0.0, 0.05, 3, 'graphite', gap=0.5)
    return P


def p_stove(style):
    """Kitchen range: enamel body, four black burner rings with pans, oven door with window, knobs, hood pipe."""
    P = Prop('stove', style, seed=227)
    P.box((-0.46, -0.3, 0.0), (0.46, 0.3, 0.6), 'plastic', bevel=0.02, seg=2)
    P.box((-0.48, -0.31, 0.6), (0.48, 0.32, 0.64), 'plastic', bevel=0.014, bias=1)
    P.box((-0.36, -0.312, 0.08), (0.36, -0.296, 0.42), 'plastic', bevel=0.008, bias=1)
    P.box((-0.26, -0.322, 0.14), (0.26, -0.308, 0.34), 'graphite', bevel=0.008, ao=False)
    P.box((-0.3, -0.33, 0.44), (0.3, -0.316, 0.47), 'chrome', bevel=0.005, ao=False)
    for i in range(4):
        P.sphere((-0.3 + i * 0.2, -0.318, 0.53), 0.026, 'graphite', subdiv=1, ao=False)
    for cx, cy in ((-0.2, -0.08), (0.2, -0.08), (-0.2, 0.15), (0.2, 0.15)):
        P.lathe(cx, cy, [(0.13, 0.64), (0.13, 0.655), (0.09, 0.665), (0.09, 0.655)], 'graphite', seg=10, ao=False)
        P.lathe(cx, cy, [(0.05, 0.655), (0.05, 0.668), (0.001, 0.672)], 'graphite', seg=8, ao=False, bias=1)
    P.lathe(-0.2, -0.08, [(0.11, 0.664), (0.12, 0.72), (0.12, 0.78), (0.001, 0.78)], 'steel', seg=10)              # pot
    P.box((-0.32, -0.14, 0.72), (-0.28, -0.02, 0.74), 'graphite')
    P.box((-0.46, 0.3, 0.64), (0.46, 0.34, 1.0), 'steel', bevel=0.01)                                             # backsplash
    return P


def p_sink(style):
    """Lab / kitchen basin: cabinet with door + drawer, worktop, deep steel bowl and a swan-neck mixer tap."""
    P = Prop('sink', style, seed=228)
    P.box((-0.46, -0.28, 0.0), (0.46, 0.28, 0.5), 'plastic', bevel=0.018, seg=2)
    P.box((-0.4, -0.294, 0.08), (0.0, -0.278, 0.44), 'plastic', bevel=0.008, bias=1)
    P.box((0.04, -0.294, 0.3), (0.4, -0.278, 0.44), 'plastic', bevel=0.008, bias=1)
    P.box((0.04, -0.294, 0.08), (0.4, -0.278, 0.26), 'plastic', bevel=0.008, bias=1)
    P.box((-0.48, -0.3, 0.5), (0.48, 0.3, 0.54), 'cloth_blue', bevel=0.012, seg=2, bias=1)
    P.box((-0.3, -0.2, 0.535), (0.3, 0.14, 0.545), 'steel', ao=False, bias=1)
    P.box((-0.28, -0.18, 0.535), (0.28, 0.12, 0.546), 'graphite', ao=False, flat_idx=1)
    P.tube([(0.0, 0.22, 0.54), (0.0, 0.22, 0.72), (0.0, 0.16, 0.8), (0.0, 0.06, 0.78)], 0.02, 'chrome', seg=6, ao=False)
    P.box((-0.1, 0.2, 0.54), (-0.06, 0.24, 0.62), 'chrome', bevel=0.004, ao=False)
    P.box((0.06, 0.2, 0.54), (0.1, 0.24, 0.62), 'chrome', bevel=0.004, ao=False)
    P.box((-0.48, 0.3, 0.54), (0.48, 0.34, 0.9), 'plastic', bevel=0.006)
    return P


def p_trash_can(style):
    """Metal bin: tapered body with two rolled ribs, domed lid with a handle, a wrapper hanging over the rim."""
    P = Prop('trash_can', style, seed=229)
    P.lathe(0, 0, [(0.15, 0.0), (0.17, 0.03), (0.2, 0.5)], 'steel', seg=10)
    for z in (0.14, 0.34):
        r = 0.16 + z * 0.08
        P.lathe(0, 0, [(r, z - 0.014), (r + 0.016, z), (r, z + 0.014)], 'steel', seg=10, ao=False, bias=1)
    P.lathe(0, 0, [(0.215, 0.48), (0.215, 0.52), (0.17, 0.56), (0.06, 0.6), (0.001, 0.6)], 'steel', seg=10, bias=1)
    P.between((-0.06, 0, 0.61), (0.06, 0, 0.61), 0.016, 0.016, 'graphite', seg=6)
    P.box((0.08, -0.22, 0.34), (0.13, -0.19, 0.5), 'paper_w', ao=False, bias=1)
    P.transform_all(Matrix.Scale(1.15, 4))
    return P


# ------------------------------------------------------------------------------------------ seating
def p_chair(style):
    """Wooden dining chair (faces -Y): four turned legs, stretcher, seat with cushion, slatted back."""
    P = Prop('chair', style, seed=230)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.17 - 0.022, sy * 0.15 - 0.022, 0.0), (sx * 0.17 + 0.022, sy * 0.15 + 0.022, 0.29), 'wood_dark', bevel=0.006)
    P.box((-0.17, -0.15, 0.08), (0.17, -0.13, 0.1), 'wood_dark', bevel=0.004)
    P.box((-0.2, -0.19, 0.28), (0.2, 0.19, 0.325), 'wood_orange', bevel=0.014, seg=2, bias=1)
    P.box((-0.17, -0.16, 0.325), (0.17, 0.15, 0.355), 'orange', bevel=0.014, seg=2, bias=1)
    for sx in (-1, 1):
        P.box((sx * 0.17 - 0.022, 0.13, 0.32), (sx * 0.17 + 0.022, 0.17, 0.78), 'wood_dark', bevel=0.006)
    P.box((-0.2, 0.13, 0.7), (0.2, 0.18, 0.8), 'wood_orange', bevel=0.012, seg=2)
    P.box((-0.15, 0.135, 0.44), (0.15, 0.16, 0.62), 'wood_orange', bevel=0.006, bias=1)
    return P


def p_stool(style):
    """Round three-legged stool."""
    P = Prop('stool', style, seed=231)
    for k in range(3):
        a = k * 2.094 + 0.3
        P.between((math.cos(a) * 0.16, math.sin(a) * 0.16, 0.0), (math.cos(a) * 0.09, math.sin(a) * 0.09, 0.3), 0.022, 0.02, 'wood_dark', seg=5)
    P.cyl(0, 0, 0.29, 0.34, 0.2, 0.19, 'wood_orange', seg=10, cap_top=True, bias=1)
    P.cyl(0, 0, 0.34, 0.36, 0.17, 0.16, 'cloth_red', seg=10, cap_top=True, bias=1)
    return P


def p_armchair(style):
    """Living-room armchair with rolled arms, back cushion and seat cushion (faces -Y)."""
    P = Prop('armchair', style, seed=232)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.3 - 0.03, sy * 0.24 - 0.03, 0.0), (sx * 0.3 + 0.03, sy * 0.24 + 0.03, 0.08), 'wood_dark', bevel=0.006)
    P.box((-0.36, -0.3, 0.07), (0.36, 0.3, 0.3), 'cloth_red', bevel=0.04, seg=2)
    P.box((-0.28, -0.28, 0.3), (0.28, 0.24, 0.4), 'cloth_red', bevel=0.05, seg=2, bias=1)
    P.box((-0.4, -0.3, 0.07), (-0.28, 0.3, 0.5), 'cloth_red', bevel=0.05, seg=2)
    P.box((0.28, -0.3, 0.07), (0.4, 0.3, 0.5), 'cloth_red', bevel=0.05, seg=2)
    P.box((-0.4, 0.2, 0.07), (0.4, 0.34, 0.78), 'cloth_red', bevel=0.05, seg=2)
    P.box((-0.3, 0.12, 0.4), (0.3, 0.22, 0.7), 'cloth_red', bevel=0.05, seg=2, bias=2)
    return P


def p_sofa(style):
    """Two-cell sofa (2.0 wide): 3 cushions, tall back, thick arms, wooden feet."""
    P = Prop('sofa', style, seed=233)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.9 - 0.03, sy * 0.24 - 0.03, 0.0), (sx * 0.9 + 0.03, sy * 0.24 + 0.03, 0.09), 'wood_dark', bevel=0.006)
    P.box((-0.98, -0.3, 0.08), (0.98, 0.3, 0.3), 'cloth_blue', bevel=0.04, seg=2)
    for i in range(3):
        x0 = -0.72 + i * 0.5
        P.box((x0, -0.3, 0.3), (x0 + 0.48, 0.22, 0.4), 'cloth_blue', bevel=0.05, seg=2, bias=1)
    P.box((-0.98, 0.16, 0.08), (0.98, 0.34, 0.72), 'cloth_blue', bevel=0.05, seg=2)
    P.box((-0.98, -0.3, 0.08), (-0.76, 0.3, 0.5), 'cloth_blue', bevel=0.05, seg=2, bias=1)
    P.box((0.76, -0.3, 0.08), (0.98, 0.3, 0.5), 'cloth_blue', bevel=0.05, seg=2, bias=1)
    P.box((0.5, 0.1, 0.4), (0.7, 0.2, 0.6), 'yellow', bevel=0.04, seg=2)
    return P


# ------------------------------------------------------------------------------------------ misc interior
def p_floor_lamp(style):
    """Standing lamp: weighted base, thin pole, pleated cream shade (warm lit)."""
    P = Prop('floor_lamp', style, seed=234)
    P.cyl(0, 0, 0, 0.04, 0.16, 0.14, 'brass', seg=10)
    P.between((0, 0, 0.04), (0, 0, 1.0), 0.018, 0.014, 'brass', seg=6)
    P.lathe(0, 0, [(0.12, 0.98), (0.18, 1.1), (0.2, 1.22), (0.12, 1.26)], 'cloth_cream', seg=12, ao=False, bias=1)
    P.cyl(0, 0, 1.26, 1.26, 0.12, 0.12, 'yellow', seg=12, cap_top=True, flat_idx=4, ao=False)
    return P


def p_wall_clock(style):
    """Round wall clock, face toward -Y (hang it on a wall)."""
    P = Prop('wall_clock', style, seed=235)
    S = P.sub()
    S.lathe(0, 0, [(0.22, 0.0), (0.22, 0.055), (0.19, 0.06), (0.19, 0.03)], 'wood_orange', seg=16, ao=False)
    S.cyl(0, 0, 0.032, 0.034, 0.188, 0.188, 'white', seg=16, cap_top=True, ao=False, flat_idx=4)
    for i in range(12):
        a = i * math.pi / 6
        big = i % 3 == 0
        r = 0.15
        S.box((math.sin(a) * r - (0.014 if big else 0.008), math.cos(a) * r - (0.014 if big else 0.008), 0.034),
              (math.sin(a) * r + (0.014 if big else 0.008), math.cos(a) * r + (0.014 if big else 0.008), 0.042), 'graphite', ao=False)
    S.box((-0.009, -0.01, 0.042), (0.009, 0.11, 0.05), 'graphite', ao=False)
    S.box((-0.01, -0.009, 0.05), (0.075, 0.009, 0.058), 'graphite', ao=False)
    S.cyl(0, 0, 0.05, 0.062, 0.02, 0.02, 'red', seg=6, ao=False)
    P.attach(S, Matrix.Translation((0, 0.0, 0.5)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    return P


def p_poster(style, kind=0):
    """Framed poster / picture for interior walls (kind 0 landscape, 1 Poke Ball emblem, 2 map, 3 painting)."""
    P = Prop('poster', style, seed=236 + kind)
    w, h = (0.7, 0.5) if kind != 1 else (0.5, 0.66)
    P.box((-w / 2 - 0.04, 0.0, 0.0), (w / 2 + 0.04, 0.04, h + 0.08), 'wood_dark', bevel=0.008)
    if kind == 0:
        P.box((-w / 2, -0.008, 0.04), (w / 2, 0.0, 0.04 + h), 'sky_glass', ao=False, flat_idx=3)
        P.box((-w / 2, -0.012, 0.04), (w / 2, -0.006, 0.04 + h * 0.4), 'grass', ao=False, flat_idx=3)
        P.blob((0.1, -0.016, 0.04 + h * 0.5), (0.1, 0.01, 0.06), 'leaf', subdiv=1, ao=False)
        P.blob((-0.16, -0.016, 0.04 + h * 0.6), (0.06, 0.01, 0.05), 'white', subdiv=1, ao=False)
    elif kind == 1:
        P.box((-w / 2, -0.008, 0.04), (w / 2, 0.0, 0.04 + h), 'white', ao=False, flat_idx=3)
        P.sphere((0, -0.016, 0.04 + h * 0.5), 0.15, 'ball_red', subdiv=1, ao=False)
        P.box((-0.16, -0.02, 0.04 + h * 0.5 - 0.02), (0.16, -0.012, 0.04 + h * 0.5 + 0.02), 'ball_ink', ao=False)
    elif kind == 2:
        P.box((-w / 2, -0.008, 0.04), (w / 2, 0.0, 0.04 + h), 'sand', ao=False, flat_idx=3)
        for i, (x, z, ww, hh, m) in enumerate(((-0.2, 0.15, 0.24, 0.16, 'grass'), (0.1, 0.3, 0.3, 0.12, 'grass'), (0.2, 0.1, 0.18, 0.2, 'water'), (-0.28, 0.32, 0.14, 0.12, 'water'))):
            P.box((x, -0.014, z), (x + ww, -0.006, z + hh), m, ao=False, flat_idx=3)
    else:
        P.box((-w / 2, -0.008, 0.04), (w / 2, 0.0, 0.04 + h), 'cloth_cream', ao=False, flat_idx=3)
        P.blob((0, -0.016, 0.04 + h * 0.5), (0.22, 0.01, 0.15), 'teal', subdiv=1, ao=False)
        P.blob((0.1, -0.02, 0.04 + h * 0.6), (0.09, 0.01, 0.07), 'yellow', subdiv=1, ao=False)
    return P


def p_poster_ball(style):
    P = p_poster(style, 1)
    P.name = 'poster_ball'
    return P


def p_poster_map(style):
    P = p_poster(style, 2)
    P.name = 'poster_map'
    return P


def p_painting(style):
    P = p_poster(style, 3)
    P.name = 'painting'
    return P


def p_poster_view(style):
    P = p_poster(style, 0)
    P.name = 'poster_view'
    return P


def p_doormat(style):
    """Woven welcome mat, slightly thick with a border."""
    P = Prop('doormat', style, seed=237)
    P.box((-0.44, -0.3, 0.0), (0.44, 0.3, 0.03), 'cloth_red', bevel=0.01, bias=0)
    P.box((-0.38, -0.24, 0.03), (0.38, 0.24, 0.036), 'cloth_cream', ao=False, bias=0)
    for i in range(4):
        P.box((-0.3, -0.16 + i * 0.1, 0.036), (0.3, -0.14 + i * 0.1, 0.04), 'cloth_red', ao=False)
    return P


def p_globe(style):
    """Desk globe on a brass ring stand."""
    P = Prop('globe', style, seed=238)
    P.cyl(0, 0, 0, 0.03, 0.14, 0.12, 'wood_dark', seg=10)
    P.between((0, 0, 0.03), (0.0, 0, 0.14), 0.014, 0.014, 'brass', seg=5)
    P.sphere((0, 0, 0.32), 0.17, 'water_deep', subdiv=2, ao=False, bias=0)
    for i, (x, y, z, r) in enumerate(((0.05, -0.12, 0.36, 0.09), (-0.1, -0.08, 0.28, 0.07), (0.1, 0.08, 0.26, 0.08), (-0.02, 0.1, 0.4, 0.06))):
        P.blob((x, y, z), (r, r * 0.4, r * 0.8), 'grass', subdiv=1, jag=0.3, seed=i, ao=False)
    return P


def p_microscope(style):
    """Lab microscope with stage, eyepiece and turret."""
    P = Prop('microscope', style, seed=239)
    P.box((-0.16, -0.14, 0.0), (0.16, 0.14, 0.035), 'graphite', bevel=0.012)
    P.between((0.0, 0.1, 0.03), (0.0, 0.08, 0.36), 0.03, 0.026, 'graphite', seg=6)
    P.between((0.0, 0.06, 0.34), (0.0, -0.06, 0.5), 0.028, 0.024, 'steel', seg=6)
    P.between((0.0, -0.06, 0.5), (0.0, -0.09, 0.56), 0.02, 0.02, 'graphite', seg=6)
    P.box((-0.09, -0.1, 0.16), (0.09, 0.06, 0.18), 'steel', bevel=0.004)
    P.between((0.0, -0.05, 0.3), (0.0, -0.05, 0.19), 0.014, 0.01, 'brass', seg=5)
    return P


def _dome_cage(P, cx, cy, z0, r, h, ribs=6):
    """Glass dome drawn as a rim ring, meridian ribs and a cap plus two glare strips, so what is under it stays visible."""
    pts = [(r * math.cos(a), z0 + h * math.sin(a)) for a in [i * math.pi / 2 / 5 for i in range(6)]]
    for k in range(ribs):
        t = k * math.tau / ribs
        path = [(cx + math.cos(t) * pr, cy + math.sin(t) * pr, z) for pr, z in pts]
        P.tube(path, 0.011, 'chrome', seg=4, ao=False)
    P.lathe(cx, cy, [(r + 0.02, z0), (r + 0.02, z0 + 0.03), (r - 0.01, z0 + 0.03), (r - 0.01, z0)], 'chrome', seg=ribs * 2, ao=False)
    P.sphere((cx, cy, z0 + h + 0.01), 0.03, 'chrome', subdiv=1, ao=False)
    P.quad((cx - r * 0.55, cy - r * 0.86, z0 + h * 0.85), (cx - r * 0.4, cy - r * 0.86, z0 + h * 0.9), (cx - r * 0.66, cy - r * 0.86, z0 + h * 0.3), (cx - r * 0.74, cy - r * 0.86, z0 + h * 0.3), 'sky_glass', toward=(0, -1, 0), ao=False, flat_idx=4)


def p_lab_machine(style):
    """Lab analyser ('Cell separator', Bill's machines): cream cabinet, dome window with glowing chamber, dials, pipes, display."""
    P = Prop('lab_machine', style, seed=240)
    P.box((-0.46, -0.3, 0.0), (0.46, 0.3, 0.5), 'plastic', bevel=0.022, seg=2)
    P.box((-0.4, -0.312, 0.08), (0.4, -0.3, 0.2), 'graphite', bevel=0.006, ao=False)
    for i in range(5):
        P.box((-0.34 + i * 0.16, -0.322, 0.1), (-0.26 + i * 0.16, -0.31, 0.18), ['led_green', 'led_amber', 'led_blue', 'led_green', 'led_red'][i], ao=False, flat_idx=3)
    P.box((-0.4, -0.3, 0.5), (0.4, 0.26, 0.56), 'steel', bevel=0.01)
    P.lathe(0, -0.02, [(0.14, 0.58), (0.17, 0.64), (0.14, 0.74), (0.001, 0.78)], 'led_green', seg=10, ao=False, flat_idx=3)   # glowing chamber
    _dome_cage(P, 0.0, -0.02, 0.56, 0.3, 0.3)
    P.between((0.36, 0.1, 0.56), (0.36, 0.1, 0.96), 0.03, 0.03, 'steel', seg=6)
    P.between((0.36, 0.1, 0.94), (0.1, 0.1, 0.96), 0.03, 0.03, 'steel', seg=6)
    P.tube([(0.4, 0.2, 0.52), (0.5, 0.2, 0.3), (0.5, 0.0, 0.14)], 0.02, 'copper', seg=5, ao=False)
    P.box((-0.4, -0.05, 0.56), (-0.16, 0.05, 0.72), 'plastic', bevel=0.012)
    P.sphere((-0.28, -0.06, 0.66), 0.05, 'white', subdiv=1, ao=False)
    return P


def p_teleporter_pad(style):
    """Silph Co. warp pad: octagonal plate with chevron ring, bevelled frame and a glowing centre disc."""
    P = Prop('teleporter_pad', style, seed=241)
    P.lathe(0, 0, [(0.5, 0.0), (0.5, 0.03), (0.44, 0.05), (0.001, 0.05)], 'steel', seg=8, rot=0.39)
    P.lathe(0, 0, [(0.4, 0.05), (0.4, 0.062), (0.34, 0.066), (0.001, 0.066)], 'led_blue', seg=8, rot=0.39, ao=False, flat_idx=3)
    P.lathe(0, 0, [(0.2, 0.066), (0.2, 0.074), (0.001, 0.078)], 'led_blue', seg=8, rot=0.39, ao=False, flat_idx=4)
    for k in range(8):
        a = k * math.pi / 4 + 0.39
        P.box((math.cos(a) * 0.44 - 0.03, math.sin(a) * 0.44 - 0.03, 0.05), (math.cos(a) * 0.44 + 0.03, math.sin(a) * 0.44 + 0.03, 0.07), 'led_amber', ao=False, flat_idx=3)
    return P


def p_generator(style):
    """Power Plant generator: squat steel drum with coil bands, gauges, pipes and a caged fan."""
    P = Prop('generator', style, seed=242)
    P.box((-0.46, -0.32, 0.0), (0.46, 0.32, 0.1), 'graphite', bevel=0.01)
    P.lathe(0, 0, [(0.001, 0.1), (0.4, 0.1), (0.44, 0.2), (0.44, 0.62), (0.4, 0.7), (0.001, 0.72)], 'steel', seg=12, bias=0)
    for z in (0.26, 0.44, 0.58):
        P.lathe(0, 0, [(0.44, z - 0.02), (0.462, z - 0.02), (0.462, z + 0.02), (0.44, z + 0.02)], 'copper', seg=12, ao=False)
    P.box((-0.2, -0.46, 0.34), (0.2, -0.4, 0.62), 'graphite', bevel=0.012)
    P.lathe(0, -0.5, [(0.001, 0.0), (0.09, 0.0), (0.09, 0.02), (0.001, 0.02)], 'white', seg=10, ao=False)
    P.box((-0.14, -0.462, 0.5), (0.14, -0.452, 0.58), 'led_green', ao=False, flat_idx=3)
    P.box((-0.14, -0.462, 0.38), (0.14, -0.452, 0.44), 'led_amber', ao=False, flat_idx=2)
    P.tube([(0.3, 0.2, 0.7), (0.3, 0.3, 0.9), (0.0, 0.34, 1.0), (-0.3, 0.3, 0.9), (-0.3, 0.2, 0.7)], 0.03, 'copper', seg=6, ao=False)
    P.between((0.0, 0.0, 0.72), (0.0, 0.0, 0.86), 0.05, 0.05, 'graphite', seg=8)
    P.sphere((0.0, 0.0, 0.9), 0.08, 'led_blue', subdiv=1, ao=False, flat_idx=3)
    return P


def p_rocket_console(style):
    """Rocket hideout control desk: black steel console with a red R panel, twin screens, key rows, hazard trim."""
    P = Prop('rocket_console', style, seed=243)
    P.box((-0.46, -0.32, 0.0), (0.46, 0.3, 0.44), 'graphite', bevel=0.02, seg=2)
    P.box((-0.46, -0.335, 0.0), (0.46, -0.32, 0.06), 'hazard', ao=False)
    for x0 in (-0.4, 0.04):
        P.box((x0, -0.336, 0.14), (x0 + 0.36, -0.322, 0.38), 'graphite', bevel=0.008, bias=2)
    P.box((-0.24, -0.345, 0.24), (-0.16, -0.334, 0.32), 'red', ao=False, flat_idx=3)
    P.box((-0.46, -0.34, 0.44), (0.46, 0.3, 0.48), 'steel', bevel=0.012, seg=2)
    for i, x in enumerate((-0.24, 0.24)):
        def scr(S, x=x):
            S.box((x - 0.19, -0.02, 0.0), (x + 0.19, 0.06, 0.3), 'graphite', bevel=0.014, seg=2)
            screen(S, x - 0.16, x + 0.16, -0.032, 0.03, 0.27, 'led_green' if i == 0 else 'led_red', scan=6)
        rot_part(P, scr, tilt_x(-10, (0, 0.0, 0.48)) @ Matrix.Translation((0, 0.0, 0.48)))
    for r in range(2):
        for c in range(8):
            P.box((-0.22 + c * 0.06, -0.24 + r * 0.05, 0.48), (-0.18 + c * 0.06, -0.2 + r * 0.05, 0.5), 'red' if (c + r) % 5 == 0 else 'steel', ao=False)
    return P


def p_fossil_case(style):
    """Museum fossil plinth: stone base, glass hood and a dome fossil with ribbed shell inside."""
    P = Prop('fossil_case', style, seed=244)
    P.box((-0.44, -0.3, 0.0), (0.44, 0.3, 0.36), 'stone', bevel=0.02, seg=2)
    P.box((-0.4, -0.312, 0.1), (0.4, -0.3, 0.3), 'plastic', bevel=0.006, ao=False, flat_idx=3)
    P.box((-0.47, -0.32, 0.36), (0.47, 0.32, 0.4), 'stone', bevel=0.014, bias=1)
    P.blob((0.0, 0.0, 0.5), (0.22, 0.2, 0.16), 'bone', subdiv=2, jag=0.08, seed=4, squash_below=0.4, ao=False)
    for k in range(6):
        P.box((-0.19 + k * 0.075, -0.19, 0.42), (-0.17 + k * 0.075, -0.15, 0.6), 'bone', ao=False, flat_idx=1 if k % 2 else 3)
    _dome_cage(P, 0.0, 0.0, 0.4, 0.4, 0.5)
    return P


def p_school_desk(style):
    """Classroom desk with sloped lid, chair back and inkwell."""
    P = Prop('school_desk', style, seed=245)
    for sx in (-1, 1):
        P.box((sx * 0.38 - 0.02, -0.26, 0.0), (sx * 0.38 + 0.02, 0.26, 0.4), 'steel', bevel=0.004)
    P.box((-0.4, -0.24, 0.16), (0.4, 0.24, 0.2), 'wood_orange', bevel=0.006)
    def lid(S):
        S.box((-0.46, -0.28, 0.0), (0.46, 0.28, 0.04), 'wood_light', bevel=0.01, seg=2)
    rot_part(P, lid, Matrix.Translation((0, 0, 0.44)) @ Matrix.Rotation(math.radians(-6), 4, 'X'))
    P.cyl(0.32, -0.16, 0.48, 0.52, 0.022, 0.02, 'graphite', seg=6, ao=False)
    return P


def p_blackboard(style):
    """Wall blackboard with chalk scribbles, tray and eraser."""
    P = Prop('blackboard', style, seed=246)
    P.box((-0.98, 0.0, 0.0), (0.98, 0.05, 0.78), 'wood_dark', bevel=0.012)
    P.box((-0.92, -0.01, 0.06), (0.92, 0.0, 0.72), 'teal', ao=False, flat_idx=0)
    for i, (x0, x1, z) in enumerate(((-0.8, -0.1, 0.55), (-0.8, -0.3, 0.42), (0.1, 0.7, 0.55), (0.1, 0.5, 0.42))):
        P.box((x0, -0.014, z), (x1, -0.008, z + 0.03), 'white', ao=False, flat_idx=3)
    P.box((-0.98, -0.06, 0.0), (0.98, 0.0, 0.05), 'wood_dark', bevel=0.006)
    P.box((0.5, -0.05, 0.05), (0.66, -0.01, 0.09), 'white', bevel=0.004, ao=False)
    return P


def p_wardrobe(style):
    """Tall two-door wardrobe with carved panels and brass pulls."""
    P = Prop('wardrobe', style, seed=247)
    P.box((-0.48, -0.06, 0.0), (0.48, 0.38, 1.3), 'wood_orange', bevel=0.026, seg=2)
    P.box((-0.5, -0.08, 1.28), (0.5, 0.4, 1.34), 'wood_dark', bevel=0.012)
    for x0, x1 in ((-0.44, -0.01), (0.01, 0.44)):
        P.box((x0, -0.08, 0.06), (x1, -0.06, 1.24), 'wood_orange', bevel=0.012, bias=1)
        P.box((x0 + 0.05, -0.092, 0.14), (x1 - 0.05, -0.078, 0.6), 'wood_dark', bevel=0.006, bias=1)
        P.box((x0 + 0.05, -0.092, 0.7), (x1 - 0.05, -0.078, 1.16), 'wood_dark', bevel=0.006, bias=1)
    P.box((-0.06, -0.1, 0.64), (-0.03, -0.086, 0.76), 'brass', ao=False)
    P.box((0.03, -0.1, 0.64), (0.06, -0.086, 0.76), 'brass', ao=False)
    return P


def p_cooking_pot_shelf(style):
    """Kitchen wall rack with hanging pans and jars (S.S. Anne kitchen)."""
    P = Prop('kitchen_rack', style, seed=248)
    P.box((-0.48, 0.0, 0.66), (0.48, 0.06, 0.72), 'wood_dark', bevel=0.006)
    for i, x in enumerate((-0.36, -0.12, 0.12, 0.36)):
        P.between((x, 0.03, 0.7), (x, -0.02, 0.66), 0.01, 0.01, 'steel', seg=4)
        P.between((x, -0.02, 0.66), (x, -0.02, 0.5), 0.008, 0.008, 'steel', seg=4)
        P.lathe(x, -0.06, [(0.09, 0.32), (0.11, 0.34), (0.12, 0.44), (0.001, 0.44)] if i % 2 == 0 else [(0.06, 0.34), (0.08, 0.5), (0.001, 0.5)], 'steel' if i != 1 else 'copper', seg=8, ao=False)
    P.box((-0.48, 0.0, 0.2), (0.48, 0.14, 0.24), 'wood_dark', bevel=0.006)
    for i in range(5):
        P.cyl(-0.36 + i * 0.18, 0.06, 0.24, 0.36, 0.045, 0.045, ['orange', 'cloth_green', 'red', 'yellow', 'cloth_cream'][i], seg=6, ao=False)
    return P


# ------------------------------------------------------------------------------------------ modular sets
def make_table(style, mask, name='table', top_mat='wood_light', leg_mat='wood_dark', h=0.5):
    P = Prop('%s_m%d' % (name, mask), style, seed=250 + mask)
    L, R, U, D = bool(mask & 1), bool(mask & 2), bool(mask & 4), bool(mask & 8)
    x0 = -0.5 if not L else -0.502
    x1 = 0.5 if not R else 0.502
    y0 = -0.42 if not D else -0.502           # front (toward camera) extends to the cell edge when a neighbour is in front
    y1 = 0.42 if not U else 0.502
    P.box((x0 - (0.02 if not L else 0), y0 - (0.02 if not D else 0), h - 0.06), (x1 + (0.02 if not R else 0), y1 + (0.02 if not U else 0), h), top_mat,
          bevel=0.012 if not (L or R or U or D) else 0.004, seg=2, bias=1)
    # apron under the top on the open sides
    if not D:
        P.box((x0 + 0.04, y0 + 0.02, h - 0.14), (x1 - 0.04, y0 + 0.05, h - 0.06), leg_mat, bevel=0.004)
    if not U:
        P.box((x0 + 0.04, y1 - 0.05, h - 0.14), (x1 - 0.04, y1 - 0.02, h - 0.06), leg_mat, bevel=0.004)
    if not L:
        P.box((x0 + 0.02, y0 + 0.04, h - 0.14), (x0 + 0.05, y1 - 0.04, h - 0.06), leg_mat, bevel=0.004)
    if not R:
        P.box((x1 - 0.05, y0 + 0.04, h - 0.14), (x1 - 0.02, y1 - 0.04, h - 0.06), leg_mat, bevel=0.004)
    # legs at corners that have no neighbours on either adjoining side
    for sx, ex in ((-1, L), (1, R)):
        for sy, ey in ((-1, D), (1, U)):
            if not ex and not ey:
                cx = sx * (0.5 - 0.06)
                cy = sy * (0.42 - 0.05)
                P.box((cx - 0.035, cy - 0.035, 0.0), (cx + 0.035, cy + 0.035, h - 0.06), leg_mat, bevel=0.007)
    return P


def make_counter(style, mask, name='counter_center'):
    """Counter piece. mask bits: 1 left neighbour, 2 right, 4 up, 8 down.  center = white + pink Pokemon Center counter;
    mart = warm wood counter with a brass rail."""
    center = name == 'counter_center'
    P = Prop('%s_m%d' % (name, mask), style, seed=270 + mask + (0 if center else 40))
    L, R, U, D = bool(mask & 1), bool(mask & 2), bool(mask & 4), bool(mask & 8)
    body = 'plastic' if center else 'wood_orange'
    front = 'pk_pink' if center else 'wood_dark'
    x0 = -0.5 if not L else -0.502
    x1 = 0.5 if not R else 0.502
    y0 = -0.4 if not D else -0.502
    y1 = 0.4 if not U else 0.502
    h = 0.6
    P.box((x0, y0, 0.0), (x1, y1, h - 0.06), body, bevel=0.006 if (L or R) else 0.014, seg=2)
    if not D:
        # panelled front with pink/dark inset and toe kick
        P.box((x0, y0 - 0.012, 0.0), (x1, y0 + 0.02, 0.06), 'graphite', bevel=0.002)
        P.box((x0 + (0.05 if not L else 0.0), y0 - 0.014, 0.1), (x1 - (0.05 if not R else 0.0), y0 + 0.01, 0.4), front, bevel=0.006, bias=1)
    if not L:
        P.box((x0 - 0.012, y0 + 0.02, 0.02), (x0 + 0.02, y1 - 0.02, h - 0.08), body, bevel=0.005)
    if not R:
        P.box((x1 - 0.02, y0 + 0.02, 0.02), (x1 + 0.012, y1 - 0.02, h - 0.08), body, bevel=0.005)
    # worktop overhanging toward the customer
    P.box((x0 - (0.02 if not L else 0), y0 - (0.06 if not D else 0), h - 0.06), (x1 + (0.02 if not R else 0), y1, h), 'white' if center else 'wood_light',
          bevel=0.008, seg=2, bias=1)
    if not center and not D:
        P.box((x0 + (0.02 if not L else 0), y0 - 0.075, h - 0.02), (x1 - (0.02 if not R else 0), y0 - 0.06, h + 0.01), 'brass', bevel=0.004, ao=False)
    return P


def make_bench(style, mask):
    """Indoor waiting bench (Pokemon Center): bit1 left neighbour, bit2 right neighbour; faces -Y; backrest optional."""
    P = Prop('bench_m%d' % mask, style, seed=290 + mask)
    L, R = bool(mask & 1), bool(mask & 2)
    x0 = -0.5 if not L else -0.502
    x1 = 0.5 if not R else 0.502
    P.box((x0 + (0.02 if not L else 0), -0.24, 0.3), (x1 - (0.02 if not R else 0), 0.16, 0.36), 'wood_orange', bevel=0.012, seg=2, bias=1)
    P.box((x0 + (0.02 if not L else 0), -0.235, 0.3), (x1 - (0.02 if not R else 0), -0.21, 0.24), 'wood_dark', bevel=0.004)
    P.box((x0 + (0.02 if not L else 0), 0.14, 0.36), (x1 - (0.02 if not R else 0), 0.19, 0.74), 'wood_orange', bevel=0.012, seg=2)
    P.box((x0 + (0.03 if not L else 0), 0.135, 0.5), (x1 - (0.03 if not R else 0), 0.145, 0.68), 'wood_dark', ao=False, bias=0)
    for sx, e in ((-1, L), (1, R)):
        if not e:
            cx = sx * 0.42
            P.box((cx - 0.035, -0.2, 0.0), (cx + 0.035, 0.14, 0.32), 'steel', bevel=0.006)
            P.box((cx - 0.035, 0.12, 0.3), (cx + 0.035, 0.18, 0.75), 'steel', bevel=0.006)
    return P


FURN = {
    'pc': (p_pc, 'PC terminal: cabinet desk, tilted LCD with lit screen, keyboard, mouse, mini-tower, cables'),
    'pc_dark': (p_pc_dark, 'PC terminal with a switched-off monitor (Celadon mansion)'),
    'laptop': (p_laptop, 'open laptop on a stand'),
    'tv_crt': (p_tv_crt, 'CRT television with aerial on a wooden cabinet'),
    'tv_game': (p_tv_game, 'CRT television with a console and pad'),
    'game_console': (p_game_console, 'retro game console with pad'),
    'server_rack': (p_server_rack, 'tall data rack with blinking bays'),
    'cash_register': (p_cash_register, 'mart till'),
    'vending_machine': (p_vending_machine, 'red drinks vending machine'),
    'slot_machine': (p_slot_machine, 'Game Corner slot machine'),
    'heal_machine': (p_heal_machine, 'Pokemon Center healing machine, 2 x 2 cells (six balls in cradles)'),
    'heal_cabinet': (p_heal_cabinet, 'Pokemon Center wall cabinet, 1 cell'),
    'bookshelf': (p_bookshelf, 'bookcase, 1.35 tall, five shelves of books'),
    'bookshelf_low': (p_bookshelf_low, 'low bookcase, 0.9 tall'),
    'mart_shelf': (p_mart_shelf, 'mart goods shelf, four stocked levels'),
    'cabinet_wood': (p_cabinet_wood, 'drawer cabinet'),
    'display_case': (p_display_case, 'glass display case'),
    'fridge': (p_fridge, 'two-door fridge'),
    'stove': (p_stove, 'kitchen range with pot'),
    'sink': (p_sink, 'basin with tap'),
    'trash_can': (p_trash_can, 'metal bin'),
    'chair': (p_chair, 'wooden chair'),
    'stool': (p_stool, 'three-legged stool'),
    'armchair': (p_armchair, 'armchair'),
    'sofa': (p_sofa, 'sofa, 2 cells wide'),
    'floor_lamp': (p_floor_lamp, 'standing lamp'),
    'wall_clock': (p_wall_clock, 'wall clock'),
    'poster_view': (p_poster_view, 'framed landscape picture'),
    'poster_ball': (p_poster_ball, 'Poke Ball poster'),
    'poster_map': (p_poster_map, 'framed map'),
    'painting': (p_painting, 'framed painting'),
    'doormat': (p_doormat, 'welcome mat'),
    'globe': (p_globe, 'desk globe'),
    'microscope': (p_microscope, 'lab microscope'),
    'lab_machine': (p_lab_machine, 'lab analyser with dome chamber'),
    'teleporter_pad': (p_teleporter_pad, 'warp pad'),
    'generator': (p_generator, 'power plant generator'),
    'rocket_console': (p_rocket_console, 'Rocket hideout control desk'),
    'fossil_case': (p_fossil_case, 'museum fossil plinth with glass hood'),
    'school_desk': (p_school_desk, 'classroom desk'),
    'blackboard': (p_blackboard, 'wall blackboard'),
    'wardrobe': (p_wardrobe, 'wardrobe'),
    'kitchen_rack': (p_cooking_pot_shelf, 'kitchen rack with pans'),
}

# modular families: name -> (piece names, builder(style, mask) )
SETS = {
    'table_set': ([('m%d' % m, m) for m in range(16)], lambda style, m: make_table(style, m)),
    'counter_center_set': ([('m%d' % m, m) for m in range(16)], lambda style, m: make_counter(style, m, 'counter_center')),
    'counter_mart_set': ([('m%d' % m, m) for m in range(16)], lambda style, m: make_counter(style, m, 'counter_mart')),
    'bench_set': ([('m%d' % m, m) for m in range(4)], lambda style, m: make_bench(style, m)),
    'desk_set': ([('m%d' % m, m) for m in range(16)], lambda style, m: make_table(style, m, 'desk', 'wood_orange', 'wood_dark', 0.55)),
}

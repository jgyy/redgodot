"""Building modules: roof and wall pieces that dress the procedural buildings (BuildingBuilder / PropKit place them from the
building blocks' geometry) - roof antennas and vanes, wall lanterns, radio masts and hatches for the flat-roofed labs and
offices, and one ornament per gym type (rock, water, electric, grass, poison, psychic, fire, ground) for the roof of that
town's gym.  bmesh via env_kit.Prop; sprite units; pivot = base centre on the roof/ground; front = -Y."""
import math

from mathutils import Vector, Matrix
from env_kit import Prop
import env_ext as X
from env_ext import rot_part


def p_tv_antenna(style):
    """Roof TV aerial: mast with three cross-arms of decreasing length and a tripod foot."""
    P = Prop('tv_antenna', style, seed=501)
    for k in range(3):
        a = k * 2.094 + 0.5
        P.between((math.cos(a) * 0.09, math.sin(a) * 0.09, 0.0), (0.0, 0.0, 0.16), 0.008, 0.008, 'steel', seg=4)
    P.between((0, 0, 0.08), (0, 0, 0.95), 0.012, 0.01, 'steel', seg=5)
    for i, (z, w) in enumerate(((0.35, 0.3), (0.55, 0.24), (0.72, 0.18), (0.86, 0.12))):
        P.between((-w, 0, z), (w, 0, z), 0.007, 0.007, 'steel', seg=4)
        P.between((-w * 0.5, 0, z - 0.03), (-w * 0.5, 0, z + 0.03), 0.005, 0.005, 'steel', seg=3)
        P.between((w * 0.5, 0, z - 0.03), (w * 0.5, 0, z + 0.03), 0.005, 0.005, 'steel', seg=3)
    return P


def p_weather_vane(style):
    """Roof-ridge weather vane: post, compass cross and a rooster-shaped arrow."""
    P = Prop('weather_vane', style, seed=502)
    P.between((0, 0, 0.0), (0, 0, 0.5), 0.014, 0.01, 'graphite', seg=5)
    P.between((-0.11, 0, 0.3), (0.11, 0, 0.3), 0.008, 0.008, 'graphite', seg=4)
    P.between((0, -0.11, 0.3), (0, 0.11, 0.3), 0.008, 0.008, 'graphite', seg=4)
    P.sphere((0, 0, 0.3), 0.022, 'brass', subdiv=1, ao=False)
    P.poly_prism([(-0.2, 0.49), (0.16, 0.49), (0.2, 0.53), (0.16, 0.57), (-0.2, 0.57), (-0.26, 0.64), (-0.26, 0.5)], -0.008, 0.008, 'brass', ao=False)
    P.poly_prism([(0.16, 0.57), (0.2, 0.62), (0.24, 0.57)], -0.008, 0.008, 'brass', ao=False)
    return P


def p_wall_lantern(style):
    """Porch lantern on a wrought bracket (mount with its back on the wall, +Y)."""
    P = Prop('wall_lantern', style, seed=503)
    P.box((-0.03, 0.0, 0.0), (0.03, 0.03, 0.22), 'graphite', bevel=0.004)
    P.between((0, 0.02, 0.18), (0, -0.09, 0.2), 0.008, 0.008, 'graphite', seg=4)
    P.box((-0.05, -0.14, 0.0), (0.05, -0.04, 0.02), 'graphite', bevel=0.004)
    P.box((-0.04, -0.13, 0.02), (0.04, -0.05, 0.13), 'lamp_glass', ao=False, flat_idx=4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box((sx * 0.04 - 0.006, -0.09 + sy * 0.04 - 0.006, 0.02), (sx * 0.04 + 0.006, -0.09 + sy * 0.04 + 0.006, 0.13), 'graphite')
    P.lathe(0, -0.09, [(0.07, 0.13), (0.05, 0.16), (0.001, 0.19)], 'graphite', seg=4, rot=0.78)
    return P


def p_radio_mast(style):
    """Rooftop radio mast with red/white bands, guy wires, a beacon and a small dish."""
    P = Prop('radio_mast', style, seed=504)
    P.box((-0.14, -0.14, 0.0), (0.14, 0.14, 0.06), 'concrete', bevel=0.01)
    h = 1.6
    for i in range(8):
        P.between((0, 0, 0.06 + i * (h - 0.06) / 8), (0, 0, 0.06 + (i + 1) * (h - 0.06) / 8), 0.028 - i * 0.002, 0.028 - (i + 1) * 0.002, 'red' if i % 2 == 0 else 'white', seg=6, ao=False)
    for a in (0.4, 2.5, 4.6):
        P.between((0, 0, 1.3), (math.cos(a) * 0.5, math.sin(a) * 0.5, 0.06), 0.005, 0.005, 'steel', seg=3)
    P.sphere((0, 0, h + 0.03), 0.04, 'led_red', subdiv=1, ao=False, flat_idx=4)
    P.between((0, 0, 1.0), (0.18, 0, 1.0), 0.008, 0.008, 'steel', seg=4)
    P.lathe(0.2, 0, [(0.001, 0.94), (0.06, 0.98), (0.09, 1.04)], 'white_paint', seg=8, ao=False)
    return P


def p_roof_hatch(style):
    """Rooftop stair hatch: small concrete box with a steel door, a step and a vent pipe."""
    P = Prop('roof_hatch', style, seed=505)
    P.box((-0.32, -0.26, 0.0), (0.32, 0.26, 0.4), 'concrete', bevel=0.015)
    P.box((-0.34, -0.28, 0.4), (0.34, 0.28, 0.44), 'concrete', bevel=0.01, bias=1)
    P.box((-0.12, -0.272, 0.0), (0.12, -0.26, 0.32), 'steel', bevel=0.006)
    P.box((0.06, -0.28, 0.14), (0.09, -0.27, 0.18), 'graphite', ao=False)
    P.box((-0.14, -0.34, 0.0), (0.14, -0.26, 0.05), 'concrete', bevel=0.006)
    P.between((0.24, 0.1, 0.44), (0.24, 0.1, 0.66), 0.03, 0.03, 'steel', seg=6)
    P.lathe(0.24, 0.1, [(0.05, 0.64), (0.05, 0.7), (0.001, 0.72)], 'steel', seg=6, ao=False)
    return P


def p_roof_tank(style):
    """Small rooftop water tank on a steel stand."""
    P = Prop('roof_tank', style, seed=506)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.between((sx * 0.2, sy * 0.16, 0.0), (sx * 0.18, sy * 0.14, 0.24), 0.015, 0.015, 'steel', seg=4)
    P.box((-0.22, -0.18, 0.24), (0.22, 0.18, 0.27), 'steel', bevel=0.004)
    P.lathe(0, 0, [(0.24, 0.27), (0.26, 0.3), (0.26, 0.58), (0.22, 0.62), (0.001, 0.64)], 'copper', seg=10)
    P.lathe(0, 0, [(0.262, 0.4), (0.27, 0.42), (0.262, 0.44)], 'graphite', seg=10, ao=False)
    P.between((0.26, 0, 0.3), (0.3, 0, 0.05), 0.012, 0.012, 'steel', seg=4)
    return P


# ------------------------------------------------------------------------------------------ gym ornaments
def _plinth(P, w=0.46):
    P.box((-w, -w * 0.7, 0.0), (w, w * 0.7, 0.1), 'stone', bevel=0.02)
    P.box((-w * 0.8, -w * 0.55, 0.1), (w * 0.8, w * 0.55, 0.16), 'stone', bevel=0.015, bias=1)


def p_gym_rock(style):
    P = Prop('gym_top_rock', style, seed=510)
    _plinth(P)
    P.blob((0, 0, 0.42), (0.34, 0.26, 0.28), 'boulder', subdiv=2, jag=0.28, seed=1, squash_below=0.16)
    P.blob((-0.3, -0.1, 0.28), (0.16, 0.14, 0.14), 'boulder', subdiv=1, jag=0.3, seed=2, squash_below=0.16)
    P.blob((0.32, -0.06, 0.26), (0.13, 0.12, 0.11), 'boulder', subdiv=1, jag=0.3, seed=3, squash_below=0.16)
    P.blob((0.04, 0.02, 0.72), (0.12, 0.1, 0.08), 'moss', subdiv=1, jag=0.3, seed=4, ao=False)
    return P


def p_gym_water(style):
    P = Prop('gym_top_water', style, seed=511)
    _plinth(P)
    # a breaking wave and a droplet
    pts = []
    for i in range(9):
        t = i / 8.0
        pts.append((-0.34 + t * 0.68, 0.16 + math.sin(t * math.pi) * (0.28 + 0.16 * t) + t * 0.08))
    top = [(x, z) for x, z in pts]
    poly = [(-0.34, 0.16)] + top + [(0.34, 0.16)]
    P.poly_prism(poly, -0.12, 0.12, 'blue', bias=1)
    P.poly_prism([(-0.34, 0.16), (-0.34, 0.2), (0.34, 0.2), (0.34, 0.16)], -0.126, 0.126, 'foam', ao=False)
    P.lathe(0.28, 0, [(0.001, 0.56), (0.07, 0.62), (0.09, 0.7), (0.05, 0.78), (0.001, 0.9)], 'water', seg=8, ao=False, flat_idx=3)
    return P


def p_gym_electric(style):
    P = Prop('gym_top_electric', style, seed=512)
    _plinth(P, 0.4)
    P.between((0, 0, 0.16), (0, 0, 0.7), 0.03, 0.022, 'steel', seg=6)
    P.sphere((0, 0, 0.74), 0.09, 'chrome', subdiv=1, ao=False)
    bolt = [(-0.12, 0.98), (0.02, 0.98), (-0.06, 0.78), (0.14, 0.8), (-0.1, 0.5), (-0.02, 0.7), (-0.16, 0.7)]
    P.poly_prism([(x, z) for x, z in bolt], -0.03, 0.03, 'yellow', ao=False, flat_idx=4)
    for a in (0.6, 2.6, 4.7):
        P.tube([(0, 0, 0.5), (math.cos(a) * 0.14, math.sin(a) * 0.14, 0.44), (math.cos(a) * 0.28, math.sin(a) * 0.28, 0.24)], 0.012, 'copper', seg=4, ao=False)
    return P


def p_gym_grass(style):
    P = Prop('gym_top_grass', style, seed=513)
    _plinth(P, 0.4)
    P.between((0, 0, 0.16), (0, 0, 0.36), 0.05, 0.05, 'bark', seg=6)
    for i, (x, y, z, r, m) in enumerate(((0, 0, 0.6, 0.3, 'leaf'), (-0.2, 0, 0.5, 0.2, 'leaf_light'), (0.22, 0.02, 0.5, 0.2, 'leaf'), (0.02, -0.1, 0.8, 0.18, 'leaf_light'))):
        P.blob((x, y, z), (r, r * 0.9, r * 0.9), m, subdiv=2, jag=0.2, seed=20 + i, ao=False)
    for i in range(6):
        a = i * 1.05
        P.sphere((math.cos(a) * 0.26, -0.24 + math.sin(a) * 0.05, 0.5 + 0.06 * (i % 3)), 0.03, 'pink' if i % 2 else 'yellow', subdiv=1, ao=False)
    return P


def p_gym_poison(style):
    P = Prop('gym_top_poison', style, seed=514)
    _plinth(P, 0.4)
    P.lathe(0, 0, [(0.3, 0.16), (0.32, 0.3), (0.34, 0.42), (0.26, 0.52), (0.28, 0.54)], 'graphite', seg=10)
    P.lathe(0, 0, [(0.27, 0.53), (0.26, 0.5), (0.001, 0.5)], 'purple', seg=10, ao=False, flat_idx=3)
    for i, (x, y, z, r) in enumerate(((0.06, 0.0, 0.62, 0.09), (-0.12, 0.02, 0.72, 0.07), (0.1, -0.03, 0.84, 0.06), (-0.04, 0, 0.96, 0.05))):
        P.sphere((x, y, z), r, 'purple', subdiv=1, ao=False, flat_idx=3 + (i % 2))
    for s in (-1, 1):
        P.between((s * 0.32, 0, 0.34), (s * 0.4, 0, 0.42), 0.02, 0.02, 'graphite', seg=4)
    return P


def p_gym_psychic(style):
    P = Prop('gym_top_psychic', style, seed=515)
    _plinth(P, 0.4)
    P.lathe(0, 0, [(0.2, 0.16), (0.12, 0.3), (0.16, 0.36)], 'purple', seg=6)
    P.sphere((0, 0, 0.62), 0.24, 'crystal_p', subdiv=2, jag=0.05, seed=6, ao=False, bias=1)
    P.sphere((0, -0.16, 0.62), 0.09, 'white', subdiv=1, ao=False)
    P.sphere((0, -0.24, 0.62), 0.045, 'graphite', subdiv=1, ao=False)
    for a in range(3):
        t = a * 2.094
        P.tube([(math.cos(t) * 0.34, math.sin(t) * 0.34, 0.5), (math.cos(t) * 0.38, math.sin(t) * 0.38, 0.62), (math.cos(t) * 0.34, math.sin(t) * 0.34, 0.76)], 0.012, 'crystal_p', seg=4, ao=False)
    return P


def p_gym_fire(style):
    P = Prop('gym_top_fire', style, seed=516)
    _plinth(P, 0.4)
    P.lathe(0, 0, [(0.16, 0.16), (0.14, 0.36), (0.26, 0.46), (0.3, 0.56), (0.24, 0.56)], 'graphite', seg=10)
    P.lathe(0, 0, [(0.24, 0.54), (0.001, 0.52)], 'lava', seg=10, ao=False, flat_idx=3)
    for i, (x, h, r) in enumerate(((0, 0.62, 0.15), (-0.12, 0.36, 0.09), (0.12, 0.32, 0.08))):
        P.lathe(x, 0, [(r, 0.54), (r * 0.9, 0.54 + h * 0.4), (r * 0.5, 0.54 + h * 0.75), (0.001, 0.54 + h)], 'lava', seg=6, ao=False, flat_idx=3 + (i % 2))
    P.lathe(0, 0, [(0.07, 0.56), (0.05, 0.56 + 0.3), (0.001, 0.56 + 0.44)], 'yellow', seg=6, ao=False, flat_idx=4)
    return P


def p_gym_ground(style):
    P = Prop('gym_top_ground', style, seed=517)
    _plinth(P, 0.42)
    for i, (r, z) in enumerate(((0.32, 0.16), (0.24, 0.32), (0.16, 0.46))):
        P.cyl(0, 0, z, z + 0.16, r, r * 0.86, 'sand_dark', seg=8, rot=i * 0.3, bias=1)
    P.blob((0, 0, 0.7), (0.12, 0.1, 0.1), 'boulder', subdiv=1, jag=0.2, seed=8, ao=False)
    P.between((0, 0, 0.7), (0, 0, 0.98), 0.028, 0.02, 'wood_dark', seg=5)
    P.tri((0.02, 0, 0.98), (0.02, 0, 0.78), (0.3, 0, 0.88), 'cloth_red', toward=(0, -1, 0), ao=False)
    P.tri((0.02, 0.005, 0.98), (0.02, 0.005, 0.78), (0.3, 0.005, 0.88), 'cloth_red', toward=(0, 1, 0), ao=False)
    return P


MODS = {
    'tv_antenna': (p_tv_antenna, 'roof TV aerial'),
    'weather_vane': (p_weather_vane, 'roof-ridge weather vane'),
    'wall_lantern': (p_wall_lantern, 'porch wall lantern'),
    'radio_mast': (p_radio_mast, 'red/white radio mast with beacon'),
    'roof_hatch': (p_roof_hatch, 'rooftop stair hatch'),
    'roof_tank': (p_roof_tank, 'rooftop water tank'),
    'gym_top_rock': (p_gym_rock, 'gym roof ornament: rock'),
    'gym_top_water': (p_gym_water, 'gym roof ornament: wave and droplet'),
    'gym_top_electric': (p_gym_electric, 'gym roof ornament: lightning rod'),
    'gym_top_grass': (p_gym_grass, 'gym roof ornament: topiary'),
    'gym_top_poison': (p_gym_poison, 'gym roof ornament: bubbling cauldron'),
    'gym_top_psychic': (p_gym_psychic, 'gym roof ornament: crystal eye orb'),
    'gym_top_fire': (p_gym_fire, 'gym roof ornament: flame brazier'),
    'gym_top_ground': (p_gym_ground, 'gym roof ornament: earth tiers with pennant'),
}

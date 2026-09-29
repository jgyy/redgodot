"""Extra 3D props that replace upstream's remaining 2D object sprites (ground items) and the overworld emote bubbles.
Same env_kit.Prop framework and units as env_props.py (sprite units, pivot bottom centre, front = Blender -Y).

  ground items: fossil, old_amber, pokedex, clipboard, paper       -> godot/assets/models/world/<name>.glb
  emotes:       emote_exclaim, emote_question, emote_heart, emote_dots -> godot/assets/models/world/<name>.glb
"""
import math

from env_kit import Prop


def p_fossil(style):
    """Spiral helix fossil: a coiled shell with ridges, resting on a small rock plinth."""
    P = Prop('fossil', style, seed=51)
    P.blob((0, 0, 0.05), (0.34, 0.26, 0.07), 'rock', subdiv=1, squash_below=0.0, jag=0.12, seed=2)
    P.blob((0, 0, 0.3), (0.28, 0.2, 0.24), 'sand', subdiv=2, jag=0.05, seed=4, squash_below=0.1)
    for i, z in enumerate((0.16, 0.24, 0.32, 0.4, 0.47)):
        r = 0.27 - i * 0.03
        P.lathe(0, 0, [(r, z - 0.018), (r + 0.02, z), (r, z + 0.018)], 'rock', seg=12, ao=False)
    P.blob((0.0, -0.13, 0.36), (0.09, 0.07, 0.09), 'cream', subdiv=1, jag=0.1, seed=6, ao=False)
    return P


def p_old_amber(style):
    """Old Amber: a glowing amber block with a trapped insect silhouette, on a stone slab."""
    P = Prop('old_amber', style, seed=52)
    P.box((-0.3, -0.22, 0.0), (0.3, 0.22, 0.07), 'stone', bevel=0.02)
    P.blob((0, 0, 0.32), (0.24, 0.17, 0.26), 'yellow', subdiv=2, jag=0.04, seed=8, squash_below=0.05)
    P.blob((0.0, -0.06, 0.34), (0.09, 0.05, 0.13), 'red', subdiv=1, jag=0.05, seed=9, ao=False)
    P.blob((-0.05, -0.1, 0.4), (0.05, 0.02, 0.05), 'dark', subdiv=1, ao=False)
    P.blob((0.05, -0.1, 0.4), (0.05, 0.02, 0.05), 'dark', subdiv=1, ao=False)
    P.blob((-0.11, -0.05, 0.22), (0.05, 0.05, 0.05), 'yellow', subdiv=1, jag=0.1, seed=10, ao=False)
    return P


def p_pokedex(style):
    """POKéDEX: red folding device standing open on a little stand, green screen, white buttons."""
    P = Prop('pokedex', style, seed=53)
    P.box((-0.16, -0.12, 0.0), (0.16, 0.12, 0.06), 'metal', bevel=0.015)
    P.box((-0.24, -0.05, 0.06), (0.24, 0.05, 0.66), 'red', bevel=0.03)
    P.box((-0.2, -0.062, 0.36), (0.2, -0.048, 0.6), 'dark', bevel=0.01, ao=False)
    P.box((-0.16, -0.07, 0.4), (0.16, -0.058, 0.56), 'screen', ao=False)
    P.box((-0.005, -0.055, 0.06), (0.005, -0.048, 0.66), 'dark', ao=False)
    for x in (-0.12, -0.04, 0.04, 0.12):
        P.box((x - 0.025, -0.062, 0.2), (x + 0.025, -0.05, 0.25), 'white', bevel=0.006, ao=False)
    P.blob((-0.17, -0.06, 0.62), (0.035, 0.015, 0.035), 'blue', subdiv=1, ao=False)
    return P


def p_clipboard(style):
    """Clipboard on a stand: wooden board, paper with text lines, metal clip."""
    P = Prop('clipboard', style, seed=54)
    P.box((-0.22, -0.06, 0.0), (-0.18, 0.06, 0.28), 'wood_dark', bevel=0.008)
    P.box((0.18, -0.06, 0.0), (0.22, 0.06, 0.28), 'wood_dark', bevel=0.008)
    P.box((-0.24, -0.03, 0.26), (0.24, 0.03, 0.86), 'wood', bevel=0.02)
    P.box((-0.19, -0.038, 0.31), (0.19, -0.03, 0.78), 'white', ao=False)
    for i, z in enumerate((0.7, 0.62, 0.54, 0.46, 0.38)):
        w = 0.15 if i % 2 == 0 else 0.11
        P.box((-0.15, -0.042, z), (-0.15 + w * 2, -0.038, z + 0.02), 'dark', ao=False)
    P.box((-0.07, -0.05, 0.78), (0.07, -0.02, 0.9), 'metal', bevel=0.008)
    return P


def p_paper(style):
    """A few loose sheets of paper on the floor with scribbled lines."""
    P = Prop('paper', style, seed=55)
    for k, (x, y, w, h, z) in enumerate(((-0.1, 0.02, 0.26, 0.34, 0.0), (0.08, -0.04, 0.24, 0.32, 0.012), (0.0, 0.05, 0.22, 0.3, 0.024))):
        P.box((x - w / 2, y - h / 2, z), (x + w / 2, y + h / 2, z + 0.012), 'white', bevel=0.003, ao=False)
    for i in range(5):
        P.box((-0.1 + 0.0, -0.1 + i * 0.05, 0.037), (0.05 + (i % 2) * 0.04, -0.09 + i * 0.05, 0.041), 'dark', ao=False)
    return P


# ------------------------------------------------------------------ emotes (thin, front facing, outlined)
def _outline(P, pts, y0, y1, mat_fill, grow=0.035):
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    big = []
    for x, z in pts:
        dx, dz = x - cx, z - cz
        n = math.hypot(dx, dz) or 1.0
        big.append((x + dx / n * grow, z + dz / n * grow))
    P.poly_prism(big, y0 - 0.02, y1 + 0.02, 'white', ao=False)
    P.poly_prism(pts, y0 - 0.03, y1, mat_fill, ao=False)


def p_emote_exclaim(style):
    P = Prop('emote_exclaim', style, seed=61)
    _outline(P, [(-0.08, 0.36), (0.08, 0.36), (0.11, 0.86), (0.0, 0.92), (-0.11, 0.86)], -0.02, 0.02, 'red')
    disc = [(math.cos(2 * math.pi * i / 10) * 0.075, 0.2 + math.sin(2 * math.pi * i / 10) * 0.075) for i in range(10)]
    _outline(P, disc, -0.02, 0.02, 'red')
    return P


def p_emote_question(style):
    P = Prop('emote_question', style, seed=62)
    # hook: an arc of thick segments
    pts_c = []
    for i in range(0, 13):
        a = math.radians(200 - i * 20)
        pts_c.append((math.cos(a) * 0.2, 0.68 + math.sin(a) * 0.2))
    pts_c += [(0.1, 0.5), (0.0, 0.4)]
    th = 0.075
    outer, inner = [], []
    for i, (x, z) in enumerate(pts_c):
        nx, nz = pts_c[min(i + 1, len(pts_c) - 1)]
        px, pz = pts_c[max(i - 1, 0)]
        dx, dz = nx - px, nz - pz
        n = math.hypot(dx, dz) or 1.0
        ox, oz = -dz / n * th, dx / n * th
        outer.append((x + ox, z + oz))
        inner.append((x - ox, z - oz))
    shape = outer + list(reversed(inner))
    _outline(P, shape, -0.02, 0.02, 'blue')
    disc = [(math.cos(2 * math.pi * i / 10) * 0.075, 0.2 + math.sin(2 * math.pi * i / 10) * 0.075) for i in range(10)]
    _outline(P, disc, -0.02, 0.02, 'blue')
    return P


def p_emote_heart(style):
    P = Prop('emote_heart', style, seed=63)
    pts = []
    for i in range(24):
        t = 2 * math.pi * i / 24
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * 0.028, 0.55 + z * 0.028))
    _outline(P, pts, -0.02, 0.02, 'pink')
    return P


def p_emote_dots(style):
    P = Prop('emote_dots', style, seed=64)
    for x in (-0.24, 0.0, 0.24):
        disc = [(x + math.cos(2 * math.pi * i / 10) * 0.075, 0.5 + math.sin(2 * math.pi * i / 10) * 0.075) for i in range(10)]
        _outline(P, disc, -0.02, 0.02, 'dark')
    return P


ITEM_PROPS = {
    'fossil': (p_fossil, 'helix fossil on a plinth'),
    'old_amber': (p_old_amber, 'old amber block'),
    'pokedex': (p_pokedex, 'pokedex device'),
    'clipboard': (p_clipboard, 'clipboard on a stand'),
    'paper': (p_paper, 'loose sheets of paper'),
    'emote_exclaim': (p_emote_exclaim, '"!" bubble'),
    'emote_question': (p_emote_question, '"?" bubble'),
    'emote_heart': (p_emote_heart, 'heart bubble'),
    'emote_dots': (p_emote_dots, '"..." bubble'),
}

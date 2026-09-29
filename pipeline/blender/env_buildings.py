"""Modular building parts (bmesh, env_kit.Prop 'vcol' style) that WorldBuilder / BuildingBuilder.gd assemble into real
3D building volumes: windows with frames / sills / lintels / gradient glass, shutters, doors, porches, awnings, gym
pillars, lanterns, dormers, chimneys, rooftop units.

Conventions: sprite units (1 = one map cell = 16 px, horizontally and vertically), wall plane at Blender y = 0 with the
outside toward -Y (glTF/Godot +Z), z up.  Origin: bottom centre of the part on the wall plane (dormers: on the roof
slope).  Colours: tintable parts carry a neutral grey ramp and a *slot* in the vertex alpha (env_kit detail id 11..15 ->
wall, roof, trim, door, shutter); BuildingBuilder replaces them by the colour it sampled from the building's own baked
atlas sprite.  Everything else (glass, metal, gold, stone, lamp glow) has fixed colours (vertex alpha 1).
"""
import math

from env_kit import Prop, MATS, hx

_GREY = [0.36, 0.54, 0.72, 0.88, 1.0]
for _name, _slot in (('bld_wall', 11), ('bld_roof', 12), ('bld_trim', 13), ('bld_door', 14), ('bld_shutter', 15)):
    MATS[_name] = ([(g, g, g) for g in _GREY], None, _slot)
MATS['bld_glass'] = ([hx(c) for c in ('#1a3f86', '#2c62b4', '#4c8cd8', '#8ec4f0', '#d8f0ff')], None, 255)
MATS['bld_glass_dk'] = ([hx(c) for c in ('#10285a', '#183c80', '#245ca8', '#3c84d0', '#6cb0f0')], None, 255)
MATS['bld_step'] = ([hx(c) for c in ('#6a6c84', '#8a8ca4', '#a8aac0', '#c4c6d6', '#dcdeea')], None, 255)
MATS['bld_lamp'] = ([hx(c) for c in ('#c8901c', '#e8b838', '#ffd860', '#ffe89a', '#fff8d0')], None, 255)
MATS['bld_steel'] = ([hx(c) for c in ('#3c4452', '#5c6678', '#8490a4', '#aab4c4', '#d0d8e4')], None, 255)
MATS['bld_dark'] = ([hx(c) for c in ('#0c0c14', '#181824', '#242434', '#343448', '#4a4a60')], None, 255)
MATS['bld_white'] = ([hx(c) for c in ('#9a9ab0', '#c0c0d4', '#dcdce8', '#f0f0f8', '#ffffff')], None, 255)

U = 1.0 / 16.0     # one art pixel


def _P(name, seed=1):
    return Prop(name, 'vcol', seed=seed)


def glass(P, x0, x1, z0, z1, y, bands=4, dark=False):
    """Vertical gradient glass in `bands` flat slabs + a diagonal reflection streak."""
    m = 'bld_glass_dk' if dark else 'bld_glass'
    for i in range(bands):
        a = z0 + (z1 - z0) * i / bands
        b = z0 + (z1 - z0) * (i + 1) / bands
        idx = min(4, bands - 1 - i + (0 if dark else 0))
        P.quad((x0, y, a), (x1, y, a), (x1, y, b), (x0, y, b), m, flat_idx=max(0, min(4, 1 + (i * 3) // bands)), ao=False)
    w = x1 - x0
    h = z1 - z0
    # reflection streak (two thin parallelograms, a touch in front of the pane)
    for off, wd, k in ((0.22, 0.12, 4), (0.42, 0.05, 3)):
        xa = x0 + w * off
        P.quad((xa, y - 0.004, z0 + h * 0.12), (xa + w * wd, y - 0.004, z0 + h * 0.12),
               (xa + w * wd + w * 0.34, y - 0.004, z0 + h * 0.86), (xa + w * 0.34, y - 0.004, z0 + h * 0.86),
               'bld_glass', flat_idx=k, ao=False)


def window(cols=2):
    """Standard 10 x 9 px window: protruding frame bars, cross mullion, recessed gradient glass, sill and lintel.
    Origin = bottom centre of the glass."""
    P = _P('bld_window', 3)
    gw, gh = 10 * U, 9 * U
    x0, x1 = -gw / 2, gw / 2
    fb = 1.1 * U
    fy = -1.5 * U
    P.box((x0 - fb, fy, 0), (x0, 0, gh + fb), 'bld_trim', ao=False, bias=0)
    P.box((x1, fy, 0), (x1 + fb, 0, gh + fb), 'bld_trim', ao=False, bias=0)
    P.box((x0 - fb, fy, gh), (x1 + fb, 0, gh + fb), 'bld_trim', ao=False, bias=1)
    P.box((x0, 0, 0), (x1, 0.01, gh), 'bld_dark', ao=False)                                    # reveal shadow
    glass(P, x0, x1, 0, gh, -0.5 * U)
    for i in range(1, cols):
        xm = x0 + gw * i / cols
        P.box((xm - 0.35 * U, -1.2 * U, 0), (xm + 0.35 * U, -0.2 * U, gh), 'bld_trim', ao=False, bias=0)
    P.box((x0, -1.2 * U, gh * 0.52), (x1, -0.2 * U, gh * 0.52 + 0.7 * U), 'bld_trim', ao=False, bias=0)
    P.box((x0 - fb - 0.5 * U, -2.3 * U, -0.9 * U), (x1 + fb + 0.5 * U, 0, 0), 'bld_trim', ao=False, bias=2)        # sill
    P.box((x0 - fb - 0.3 * U, -1.9 * U, gh + fb), (x1 + fb + 0.3 * U, 0, gh + fb + 0.9 * U), 'bld_trim', ao=False, bias=1)   # lintel
    return P


def window_big():
    """A tall 12 x 12 window (window_big cells)."""
    P = _P('bld_window_big', 4)
    gw, gh = 12 * U, 12 * U
    x0, x1 = -gw / 2, gw / 2
    fb = 1.1 * U
    P.box((x0 - fb, -1.5 * U, 0), (x0, 0, gh + fb), 'bld_trim', ao=False)
    P.box((x1, -1.5 * U, 0), (x1 + fb, 0, gh + fb), 'bld_trim', ao=False)
    P.box((x0 - fb, -1.5 * U, gh), (x1 + fb, 0, gh + fb), 'bld_trim', ao=False, bias=1)
    glass(P, x0, x1, 0, gh, -0.5 * U, bands=5)
    P.box((-0.4 * U, -1.2 * U, 0), (0.4 * U, -0.2 * U, gh), 'bld_trim', ao=False)
    P.box((x0 - fb - 0.5 * U, -2.3 * U, -0.9 * U), (x1 + fb + 0.5 * U, 0, 0), 'bld_trim', ao=False, bias=2)
    return P


def shutter():
    """One louvred shutter, 3 x 9 px."""
    P = _P('bld_shutter', 5)
    w, h = 3 * U, 9.6 * U
    P.box((-w / 2, -1.2 * U, 0), (w / 2, 0, h), 'bld_shutter', ao=False, bias=0)
    n = 6
    for i in range(n):
        z = 0.5 * U + i * (h - 1 * U) / n
        P.box((-w / 2 + 0.4 * U, -1.6 * U, z), (w / 2 - 0.4 * U, -1.2 * U, z + 0.9 * U), 'bld_shutter', ao=False, bias=2)
    P.box((-w / 2, -1.5 * U, 0), (w / 2, -1.2 * U, 0.6 * U), 'bld_shutter', ao=False, bias=1)
    return P


def door():
    """Wooden door 10 x 14 px in a frame with lintel, hinges, handle, doorbell and two stone steps. Origin = ground."""
    P = _P('bld_door', 6)
    dw, dh = 10 * U, 14 * U
    x0, x1 = -dw / 2, dw / 2
    fb = 1.4 * U
    P.box((x0 - fb, -1.6 * U, 0), (x0, 0, dh + fb), 'bld_trim', ao=False)
    P.box((x1, -1.6 * U, 0), (x1 + fb, 0, dh + fb), 'bld_trim', ao=False)
    P.box((x0 - fb - 0.5 * U, -2.2 * U, dh), (x1 + fb + 0.5 * U, 0, dh + fb + 0.6 * U), 'bld_trim', ao=False, bias=1)
    P.box((x0, 0, 0), (x1, 0.01, dh), 'bld_dark', ao=False)
    for i in range(3):        # planks, recessed a hair
        xa = x0 + dw * i / 3
        P.box((xa + 0.15 * U, -0.9 * U, 0.2 * U), (xa + dw / 3 - 0.15 * U, -0.2 * U, dh), 'bld_door', ao=False, bias=(0, 1, 0)[i])
    for z in (3.0 * U, 10.0 * U):
        P.box((x0, -1.1 * U, z), (x1, -0.85 * U, z + 1.1 * U), 'bld_door', ao=False, bias=-1)
        P.box((x0 - 0.2 * U, -1.3 * U, z + 0.1 * U), (x0 + 1.3 * U, -0.9 * U, z + 0.9 * U), 'bld_steel', ao=False)
    glass(P, -2.4 * U, 2.4 * U, 9.4 * U, 12.6 * U, -1.0 * U, bands=3, dark=True)
    P.cyl(x1 - 1.6 * U, -1.5 * U, 5.6 * U, 6.2 * U, 0.55 * U, 0.55 * U, 'gold', seg=6, ao=False)
    P.box((x1 + fb + 0.6 * U, -1.0 * U, 6.5 * U), (x1 + fb + 1.8 * U, 0, 8.0 * U), 'bld_white', ao=False)          # doorbell plate
    P.cyl(x1 + fb + 1.2 * U, -1.3 * U, 7.0 * U, 7.5 * U, 0.35 * U, 0.35 * U, 'gold', seg=6, ao=False)
    P.box((x0 - fb - 1.2 * U, -4.4 * U, 0), (x1 + fb + 1.2 * U, -0.6 * U, 1.0 * U), 'bld_step', ao=False, bias=1)
    P.box((x0 - fb - 2.2 * U, -6.8 * U, 0), (x1 + fb + 2.2 * U, -4.4 * U, 0.55 * U), 'bld_step', ao=False, bias=0)
    return P


def glassdoor():
    """Automatic glass door 10 x 14 px with white frame and pull bar (Pokemon Center / Mart)."""
    P = _P('bld_glassdoor', 7)
    dw, dh = 10 * U, 14 * U
    x0, x1 = -dw / 2, dw / 2
    fb = 1.2 * U
    P.box((x0 - fb, -1.5 * U, 0), (x0, 0, dh + fb), 'bld_trim', ao=False, bias=1)
    P.box((x1, -1.5 * U, 0), (x1 + fb, 0, dh + fb), 'bld_trim', ao=False, bias=1)
    P.box((x0 - fb, -1.8 * U, dh), (x1 + fb, 0, dh + fb + 0.6 * U), 'bld_trim', ao=False, bias=2)
    P.box((x0, 0, 0), (x1, 0.01, dh), 'bld_dark', ao=False)
    glass(P, x0 + 0.5 * U, x1 - 0.5 * U, 0.4 * U, dh - 0.4 * U, -0.7 * U, bands=5)
    P.box((-0.35 * U, -1.2 * U, 0.4 * U), (0.35 * U, -0.6 * U, dh - 0.4 * U), 'bld_trim', ao=False, bias=1)
    P.box((x0 + 0.5 * U, -1.3 * U, 4.6 * U), (x0 + 1.4 * U, -0.6 * U, 8.6 * U), 'bld_steel', ao=False, bias=3)
    P.box((x0 - fb - 1.0 * U, -3.6 * U, 0), (x1 + fb + 1.0 * U, -0.6 * U, 0.8 * U), 'bld_step', ao=False, bias=1)
    return P


def awning():
    """1-cell-wide striped awning module, 5 px deep, sloping down and out from the wall. Origin = wall line at its top."""
    P = _P('bld_awning', 8)
    w = 1.0
    d = 5.5 * U
    drop = 2.6 * U
    n = 4
    for i in range(n):
        xa, xb = -w / 2 + w * i / n, -w / 2 + w * (i + 1) / n
        m, bias = ('bld_trim', 1) if i % 2 == 0 else ('bld_white', 1)
        P.quad((xa, 0, 0), (xb, 0, 0), (xb, -d, -drop), (xa, -d, -drop), m, toward=(0, -0.4, 1), ao=False, bias=bias)
        # valance
        P.quad((xa, -d, -drop), (xb, -d, -drop), (xb, -d - 0.3 * U, -drop - 1.8 * U), (xa, -d - 0.3 * U, -drop - 1.8 * U), m, toward=(0, -1, -0.1), ao=False, bias=-1)
    P.box((-w / 2, -0.2 * U, -0.5 * U), (w / 2, 0, 0.3 * U), 'bld_trim', ao=False, bias=-1)
    return P


def porch():
    """House porch: two posts and a small gable roof over the door (14 px wide, 6 px deep). Origin = ground on the wall line."""
    P = _P('bld_porch', 9)
    w, d = 14 * U, 6 * U
    hp = 15.5 * U
    for sx in (-1, 1):
        P.box((sx * (w / 2 - 0.9 * U) - 0.8 * U, -d + 0.4 * U, 0), (sx * (w / 2 - 0.9 * U) + 0.8 * U, -d + 2.0 * U, hp), 'bld_trim', ao=False, bias=1)
        P.box((sx * (w / 2 - 0.9 * U) - 1.2 * U, -d + 0.1 * U, 0), (sx * (w / 2 - 0.9 * U) + 1.2 * U, -d + 2.3 * U, 1.2 * U), 'bld_step', ao=False, bias=1)
    P.box((-w / 2, -d, hp), (w / 2, 0, hp + 1.2 * U), 'bld_trim', ao=False, bias=2)                     # beam
    # gable roof: ridge along Y (depth), rises 3.6 px
    rz = hp + 1.2 * U + 3.8 * U
    ov = 1.2 * U
    for sx in (-1, 1):
        P.quad((sx * (w / 2 + ov), 0, hp + 0.8 * U), (sx * (w / 2 + ov), -d - ov, hp + 0.8 * U), (0, -d - ov, rz), (0, 0, rz), 'bld_roof', toward=(sx * 0.7, -0.2, 1), ao=False, bias=0 if sx < 0 else -1)
    P.tri((-(w / 2 + ov), -d - ov, hp + 0.8 * U), (w / 2 + ov, -d - ov, hp + 0.8 * U), (0, -d - ov, rz), 'bld_wall', toward=(0, -1, 0), ao=False, bias=0)
    P.box((-0.4 * U, -d - ov - 0.3 * U, rz - 0.3 * U), (0.4 * U, 0, rz + 0.5 * U), 'bld_roof', ao=False, bias=2)
    return P


def pillar():
    """Stone column, 4 px wide, 1 cell tall (scale Y for the real height). Origin = ground on the wall line."""
    P = _P('bld_pillar', 10)
    P.box((-2.6 * U, -5.2 * U, 0), (2.6 * U, 0, 1.1 * U), 'bld_wall', ao=False, bias=1)
    P.lathe(0, -2.6 * U, [(2.0 * U, 1.1 * U), (1.7 * U, 1.6 * U), (1.7 * U, 14.0 * U), (2.0 * U, 14.5 * U)], 'bld_wall', seg=8, ao=False, bias=2, rot=0.39)
    P.box((-2.8 * U, -5.4 * U, 14.5 * U), (2.8 * U, 0, 16.0 * U), 'bld_wall', ao=False, bias=2)
    return P


def lamp():
    """Wall lantern on a bracket (glows at night through the day/night lights)."""
    P = _P('bld_lamp', 11)
    P.box((-0.4 * U, -2.4 * U, 3.2 * U), (0.4 * U, 0, 3.9 * U), 'bld_steel', ao=False)
    P.box((-1.6 * U, -4.6 * U, 0.6 * U), (1.6 * U, -2.0 * U, 1.0 * U), 'bld_steel', ao=False)
    P.box((-1.3 * U, -4.3 * U, 1.0 * U), (1.3 * U, -2.3 * U, 3.6 * U), 'bld_lamp', ao=False, flat_idx=3)
    P.box((-1.7 * U, -4.7 * U, 3.6 * U), (1.7 * U, -1.9 * U, 4.1 * U), 'bld_steel', ao=False, bias=1)
    return P


def dormer():
    """Gable dormer standing on a roof slope: 14 px wide front wall with a recessed window, cheeks and a small gable roof.
    Origin = bottom centre of the front wall at the slope; extends back (+Y) into the roof."""
    P = _P('bld_dormer', 12)
    w, hw_, dep = 14 * U, 7.5 * U, 12 * U
    x0, x1 = -w / 2, w / 2
    rise = 4.6 * U
    ov = 1.2 * U
    P.box((x0, -0.0, -2.0 * U), (x1, 0.4 * U, hw_), 'bld_wall', ao=False, bias=1)             # front wall (thin, pattern via slot)
    P.tri((x0, 0, hw_), (x1, 0, hw_), (0, 0, hw_ + rise), 'bld_wall', toward=(0, -1, 0), ao=False, bias=1)      # gable end
    # cheeks
    P.quad((x0, 0, -2.0 * U), (x0, dep, -2.0 * U), (x0, dep, hw_), (x0, 0, hw_), 'bld_wall', toward=(-1, 0, 0), ao=False, bias=-1)
    P.quad((x1, dep, -2.0 * U), (x1, 0, -2.0 * U), (x1, 0, hw_), (x1, dep, hw_), 'bld_wall', toward=(1, 0, 0), ao=False, bias=-1)
    # window
    gw, gh = 6 * U, 4.6 * U
    glass(P, -gw / 2, gw / 2, 1.6 * U, 1.6 * U + gh, -0.6 * U, bands=3)
    fb = 1.1 * U
    P.box((-gw / 2 - fb, -1.6 * U, 1.6 * U - fb * 0.6), (-gw / 2, 0, 1.6 * U + gh + fb), 'bld_trim', ao=False)
    P.box((gw / 2, -1.6 * U, 1.6 * U - fb * 0.6), (gw / 2 + fb, 0, 1.6 * U + gh + fb), 'bld_trim', ao=False)
    P.box((-gw / 2 - fb, -1.6 * U, 1.6 * U + gh), (gw / 2 + fb, 0, 1.6 * U + gh + fb), 'bld_trim', ao=False, bias=1)
    P.box((-gw / 2 - fb, -2.4 * U, 1.6 * U - fb * 0.6 - 1.0 * U), (gw / 2 + fb, 0, 1.6 * U - fb * 0.6), 'bld_trim', ao=False, bias=2)
    # roof slopes with overhang + fascia + ridge
    for sx in (-1, 1):
        P.quad((sx * (w / 2 + ov), -ov, hw_ - 0.2 * U), (sx * (w / 2 + ov), dep, hw_ - 0.2 * U), (0, dep, hw_ + rise + 0.4 * U), (0, -ov, hw_ + rise + 0.4 * U),
               'bld_roof', toward=(sx * 0.7, -0.1, 1), ao=False, bias=0 if sx < 0 else -1)
    P.tri((-w / 2 - ov, -ov, hw_ - 0.2 * U), (w / 2 + ov, -ov, hw_ - 0.2 * U), (0, -ov, hw_ + rise + 0.4 * U), 'bld_trim', toward=(0, -1, 0), ao=False, bias=0)
    P.box((-0.5 * U, -ov - 0.2 * U, hw_ + rise - 0.1 * U), (0.5 * U, dep, hw_ + rise + 0.7 * U), 'bld_roof', ao=False, bias=2)
    return P


def chimney():
    """Brick chimney stack 6 x 5 px base, 10 px tall, with a capping slab and a flue. Origin = bottom centre."""
    P = _P('bld_chimney', 13)
    w, d, h = 6 * U, 5 * U, 10 * U
    P.box((-w / 2, -d / 2, 0), (w / 2, d / 2, h), 'bld_wall', ao=False, bias=0)
    for z in (2.5 * U, 5.0 * U, 7.5 * U):
        P.box((-w / 2 - 0.15 * U, -d / 2 - 0.15 * U, z), (w / 2 + 0.15 * U, d / 2 + 0.15 * U, z + 0.5 * U), 'bld_wall', ao=False, bias=-1)
    P.box((-w / 2 - 0.9 * U, -d / 2 - 0.9 * U, h), (w / 2 + 0.9 * U, d / 2 + 0.9 * U, h + 1.3 * U), 'bld_trim', ao=False, bias=2)
    P.box((-w / 2 + 1.1 * U, -d / 2 + 1.0 * U, h + 1.3 * U), (w / 2 - 1.1 * U, d / 2 - 1.0 * U, h + 1.45 * U), 'bld_dark', ao=False)
    return P


def acunit():
    """Rooftop AC / vent unit, 1 cell wide x 0.6 deep x 0.45 tall (scaled per use)."""
    P = _P('bld_acunit', 14)
    P.box((-0.5, -0.3, 0), (0.5, 0.3, 0.42), 'bld_steel', ao=False, bias=1)
    P.box((-0.52, -0.32, 0.4), (0.52, 0.32, 0.46), 'bld_steel', ao=False, bias=2)
    for i in range(4):
        P.box((0.02, -0.325, 0.08 + i * 0.08), (0.45, -0.3, 0.12 + i * 0.08), 'bld_dark', ao=False)
    P.box((-0.42, -0.325, 0.06), (-0.06, -0.3, 0.36), 'bld_dark', ao=False, bias=1)
    return P


PARTS = {
    'bld_window': window, 'bld_window_big': window_big, 'bld_shutter': shutter, 'bld_door': door, 'bld_glassdoor': glassdoor,
    'bld_awning': awning, 'bld_porch': porch, 'bld_pillar': pillar, 'bld_lamp': lamp, 'bld_dormer': dormer,
    'bld_chimney': chimney, 'bld_acunit': acunit,
}

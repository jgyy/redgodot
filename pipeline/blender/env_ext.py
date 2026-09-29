"""Extra materials + shared builders for the furniture / nature / town / building-module prop sets
(env_furn.py, env_nature.py, env_town.py, env_mods.py).

Import this module once (it registers the ramps in env_kit.MATS).  Every ramp is dark -> light, 5 steps, in the same
colour families as upstream's sprites (white-lavender machine plastic with green screens, orange-brown wood, red
vending cabinets ...) so a 3D prop sits next to the 2D art it replaces without changing the palette.
"""
import math
import random

from mathutils import Vector, Matrix
import env_kit as K
from env_kit import Prop, hx


def _ramp(*cols):
    return [hx(c) for c in cols]


# name: (ramp, texture for the 'tex' kit style, detail tile id for the in-game overlay; 255 = none)
K.MATS.update({
    # plastics / machines
    'plastic': (_ramp('#7c7f98', '#a4a7be', '#cfd1de', '#eceaf2', '#ffffff'), None, 255),
    'plastic_warm': (_ramp('#8a8272', '#b0a892', '#d4ccb6', '#eee8d6', '#fffcf0'), None, 255),
    'graphite': (_ramp('#0e0f16', '#1c1e2a', '#2c2f3e', '#40445a', '#5c6180'), None, 255),
    'steel': (_ramp('#3a4150', '#5c6676', '#8490a2', '#b0bacb', '#e0e6f0'), 'metal', 255),
    'chrome': (_ramp('#4a5468', '#8090a8', '#c0d0e4', '#eef4fc', '#ffffff'), None, 255),
    'copper': (_ramp('#4a2418', '#7c3e26', '#b0643a', '#d88a52', '#f0b47c'), None, 255),
    'brass': (_ramp('#5a4214', '#8c6a20', '#c09a32', '#e6c454', '#fff0a0'), None, 255),
    'led_green': (_ramp('#0c4a2a', '#18804a', '#30c070', '#7cf0a0', '#d8ffe4'), None, 255),
    'led_red': (_ramp('#5a0c14', '#98182a', '#e02c3c', '#ff6a6a', '#ffc0b8'), None, 255),
    'led_amber': (_ramp('#7a4a08', '#b87814', '#f0a824', '#ffd060', '#fff2b0'), None, 255),
    'led_blue': (_ramp('#0c2a6a', '#184cb0', '#2c7cf0', '#70b4ff', '#d0eaff'), None, 255),
    'crt': (_ramp('#0a2a30', '#14505a', '#2c8a90', '#68c8c8', '#c8f4f0'), None, 255),
    'sky_glass': (_ramp('#3670c8', '#5a9ae0', '#88c4f4', '#bfe4ff', '#f4fbff'), None, 255),
    # cloth / paint
    'cloth_red': (_ramp('#4a1018', '#7c1c28', '#b02c3c', '#d85060', '#f08c94'), None, 255),
    'cloth_blue': (_ramp('#14204a', '#24387c', '#3a58b0', '#6884d8', '#9cb4f0'), None, 255),
    'cloth_green': (_ramp('#0e3420', '#1a5a34', '#2c8a4c', '#54b870', '#8ce0a0'), None, 255),
    'cloth_cream': (_ramp('#8a7a5c', '#b8a880', '#dcd0a8', '#f0e8c8', '#fffcec'), None, 255),
    'cloth_pink': (_ramp('#7a2848', '#b04870', '#e07098', '#f8a0c0', '#ffd0e0'), None, 255),
    'leather': (_ramp('#2a1610', '#442418', '#66382a', '#8a5238', '#b07850'), None, 255),
    'orange': (_ramp('#7a2c10', '#b04818', '#e06c20', '#f89438', '#ffc070'), None, 255),
    'porcelain': (_ramp('#9aa0b8', '#c4cad8', '#e2e6ee', '#f4f6fa', '#ffffff'), None, 255),
    'paper_w': (_ramp('#a8a49a', '#cbc7bc', '#e6e2d6', '#f6f3e8', '#ffffff'), None, 255),
    'cork': (_ramp('#5a3e22', '#7c5a34', '#a07a48', '#c29c64', '#dcbc84'), None, 255),
    'wood_light': (_ramp('#7c5232', '#a07048', '#c8975c', '#e0b878', '#f4d49c'), 'wood', 7),
    'wood_orange': (_ramp('#5a3020', '#8c5028', '#c07838', '#e0a04c', '#f4c878'), 'wood', 7),
    'wood_pale': (_ramp('#8c7250', '#b89c70', '#d8c090', '#ecdcb0', '#fbf0d0'), 'wood', 7),
    'straw': (_ramp('#8a6a28', '#b8923c', '#dcb856', '#f0d47c', '#fbeaa8'), None, 255),
    'rope': (_ramp('#5a4a2c', '#84703e', '#a8925a', '#c8b47a', '#e0d09c'), None, 255),
    'bone': (_ramp('#8c8470', '#b8b09a', '#d8d0b8', '#ece6d0', '#faf6e6'), None, 255),
    'shell': (_ramp('#a86a6a', '#d4908c', '#f0b8ac', '#fcd8c8', '#fff0e4'), None, 255),
    'coral': (_ramp('#8a2a3c', '#c04458', '#e8687a', '#f890a0', '#ffc0c8'), None, 255),
    # nature
    'pine': (_ramp('#0a2a24', '#12433a', '#1a5c48', '#2a7a58', '#42986c'), 'turf', 0),
    'birch_bark': (_ramp('#4a4a4c', '#7c7c7e', '#b0b0b0', '#dcdcdc', '#f6f6f2'), 'bark', 255),
    'dead_wood': (_ramp('#2a2422', '#48403a', '#6a5e52', '#8e8070', '#b0a290'), 'bark', 255),
    'cherry': (_ramp('#8a3058', '#c04c7c', '#e878a0', '#f8a8c4', '#ffd4e2'), None, 255),
    'autumn': (_ramp('#5a2010', '#98381c', '#d05c20', '#ec8a30', '#f8b850'), None, 255),
    'palm': (_ramp('#0e4028', '#1a6a38', '#2c9448', '#54bc5c', '#94dc78'), None, 255),
    'reed': (_ramp('#3a5a24', '#587c34', '#80a44a', '#a8c866', '#d0e890'), None, 255),
    'cattail': (_ramp('#3a2418', '#54341e', '#744a2a', '#946438', '#b4844c'), None, 255),
    'lily': (_ramp('#0e4a30', '#1a6e3e', '#2c9a50', '#58c070', '#90e098'), None, 255),
    'mushroom': (_ramp('#7a1a20', '#b02830', '#dc4044', '#f27068', '#ffa8a0'), None, 255),
    'mushroom_brown': (_ramp('#4a3020', '#6e4a30', '#946440', '#b88458', '#dcaa78'), None, 255),
    'ice': (_ramp('#4a7ac0', '#78acdc', '#a8d8f4', '#d4f0ff', '#f6fcff'), None, 255),
    'crystal_b': (_ramp('#1c3a9a', '#2c5cd8', '#4c8cf8', '#8cc4ff', '#dcf0ff'), None, 255),
    'crystal_p': (_ramp('#4a1a8a', '#7434c8', '#a45cf0', '#cc94ff', '#eed8ff'), None, 255),
    'crystal_g': (_ramp('#0c5a3c', '#18905c', '#34c886', '#84f0b8', '#d4ffe8'), None, 255),
    'lava': (_ramp('#3a0c08', '#8a1c10', '#d84a10', '#ff8a20', '#ffd060'), None, 255),
    'obsidian': (_ramp('#0a080e', '#16121e', '#241e30', '#382e4a', '#54486c'), None, 255),
    'snow': (_ramp('#8a9cc0', '#b4c4e0', '#d8e4f4', '#f0f6fc', '#ffffff'), None, 255),
    'sand_dark': (_ramp('#7a6238', '#a08450', '#c4a66c', '#dcc48c', '#f0e0ac'), 'sand', 2),
    'cactus': (_ramp('#164a2a', '#22703c', '#36964e', '#5cbc6c', '#98e094'), None, 255),
    'water_deep': (_ramp('#0e1a4a', '#16307c', '#2250a8', '#3a78d0', '#66a4ec'), None, 255),
    'hay': (_ramp('#8a6c1c', '#b8922c', '#dcb444', '#f0d068', '#faea98'), None, 255),
    'brick_dark': (_ramp('#3a1a1c', '#582826', '#743830', '#94503e', '#b26e52'), 'brick', 255),
    'concrete': (_ramp('#585a66', '#787a88', '#9a9cab', '#bcbecb', '#dcdde6'), 'stone', 3),
    'asphalt': (_ramp('#1e2028', '#2c2e3a', '#3c3e4c', '#50526a', '#686a86'), None, 255),
    'hazard': (_ramp('#7a6008', '#b89410', '#f0c81c', '#fce65c', '#fff6a8'), None, 255),
    'white_paint': (_ramp('#9498b0', '#bcc0d4', '#dcdeea', '#f0f1f8', '#ffffff'), None, 255),
    'teal': (_ramp('#0e3c46', '#1a6470', '#2c98a0', '#5cc4c4', '#98e4e0'), None, 255),
    'purple': (_ramp('#2c1850', '#4a2c84', '#6c48b8', '#9270e0', '#bc9cf8'), None, 255),
    'gold_paint': (_ramp('#8a6a1c', '#b98f2a', '#e0b83a', '#f4d046', '#fff0a0'), None, 255),
    'pk_pink': (_ramp('#8a2a4a', '#c04070', '#e86090', '#f890b0', '#ffc0d4'), None, 255),
    'pk_red_roof': (_ramp('#5c1c22', '#8f2a2c', '#bb4034', '#dc6244', '#f08a70'), None, 255),
})


def rs(seed):
    return random.Random(seed)


# ---------------------------------------------------------------------------------------------- builders
def bars(P, x0, x1, y, z0, z1, n, mat, gap=0.35, flat_idx=None, **kw):
    """n horizontal stripes between z0 and z1 on a face at depth y (front = -Y): vents, scanlines, book spines ..."""
    h = (z1 - z0) / n
    for i in range(n):
        za = z0 + i * h
        P.box((x0, y, za + h * gap * 0.5), (x1, y + 0.004, za + h * (1 - gap * 0.5)), mat, ao=False, flat_idx=flat_idx, **kw)


def screen(P, x0, x1, y, z0, z1, mat='screen', scan=8, glare=True, dark_mat=None, depth=0.008):
    """A lit screen inset: bright base, faint scanlines, a diagonal glare streak and a couple of text lines."""
    P.box((x0, y, z0), (x1, y + depth, z1), mat, ao=False, flat_idx=3)
    w = x1 - x0
    h = z1 - z0
    for i in range(scan):
        z = z0 + h * (i + 0.5) / scan
        P.box((x0, y - 0.001, z - h / scan * 0.16), (x1, y + depth * 0.5, z + h / scan * 0.16), mat, ao=False, flat_idx=2)
    if glare:
        P.quad((x0 + w * 0.10, y - 0.003, z1 - h * 0.08), (x0 + w * 0.34, y - 0.003, z1 - h * 0.08),
               (x0 + w * 0.16, y - 0.003, z0 + h * 0.08), (x0 + w * 0.06, y - 0.003, z0 + h * 0.08), mat, toward=(0, -1, 0), ao=False, flat_idx=4)
    for i, ww in enumerate((0.55, 0.4, 0.62)):
        zc = z1 - h * (0.28 + i * 0.16)
        P.box((x0 + w * 0.42, y - 0.002, zc), (x0 + w * (0.42 + ww * 0.5), y + 0.002, zc + h * 0.045), mat, ao=False, flat_idx=1)


def legs4(P, x0, x1, y0, y1, h, mat, t=0.04, inset=0.0, bevel=0.006):
    for x in (x0 + inset, x1 - inset - t):
        for y in (y0 + inset, y1 - inset - t):
            P.box((x, y, 0.0), (x + t, y + t, h), mat, bevel=bevel)


def rot_part(P, builder, M):
    """Build a part with builder(sub_prop) in its own frame, transform it with M and merge it into P."""
    sp = P.sub()
    builder(sp)
    P.attach(sp, M)


def tilt_x(deg, pivot=(0, 0, 0)):
    """Rotation about the X axis through `pivot` (positive tilts the top toward +Y, away from the camera)."""
    pv = Vector(pivot)
    return Matrix.Translation(pv) @ Matrix.Rotation(math.radians(deg), 4, 'X') @ Matrix.Translation(-pv)


def rot_z(deg, pivot=(0, 0, 0)):
    pv = Vector(pivot)
    return Matrix.Translation(pv) @ Matrix.Rotation(math.radians(deg), 4, 'Z') @ Matrix.Translation(-pv)


def leafy(P, center, r, mat, n=5, spread=0.6, seed=1, subdiv=1, mat2=None, squash=0.85):
    """A cluster of faceted leaf blobs (bushes, canopies, ferns)."""
    rg = rs(seed)
    cx, cy, cz = center
    for i in range(n):
        a = rg.random() * math.tau
        d = rg.random() * spread * r
        rr = r * (0.55 + rg.random() * 0.45)
        m = mat2 if (mat2 and rg.random() < 0.35) else mat
        P.blob((cx + math.cos(a) * d, cy + math.sin(a) * d * 0.9, cz + (rg.random() - 0.3) * r * 0.5), (rr, rr * 0.92, rr * squash), m,
               subdiv=subdiv, jag=0.2, seed=seed * 13 + i, ao=False)


def sign_face(P, x0, x1, y, z0, z1, mat, lines=2, ink='dark'):
    """A painted board with n ink lines standing in for lettering."""
    P.box((x0, y, z0), (x1, y + 0.012, z1), mat, bevel=0.006)
    w = x1 - x0
    h = z1 - z0
    for i in range(lines):
        zc = z1 - h * (0.3 + i * 0.28)
        ww = w * (0.62 - 0.14 * i)
        P.box((x0 + (w - ww) / 2, y - 0.004, zc), (x0 + (w + ww) / 2, y, zc + h * 0.09), ink, ao=False, flat_idx=1)

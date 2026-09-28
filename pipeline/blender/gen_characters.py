"""Chibi 3D trainers / NPCs for every humanoid in upstream's cast (src/data/cast.js).

  python3 pipeline/blender/gen_characters.py -- [--only red,oak] [--no-humanoid]

Upstream draws each character as a 16x24 sprite composed from a head template
(cap / spiky / short / long / bald / hat / beanie / bun / pony), a body template
(normal / coat / dress / shorts / swim), palette colours and extras (backpack,
glasses, beard, emblem) -- src/art/chars.js.  This builds the same recipe as a clean
chibi figure: big round head (half the height, like the sprite), SDF-modelled hair and
hats (monsdf surface nets: hair is a shell around the head with the face carved out),
rounded torso, sleeves, hands, legs, shoes, skirts/coats and accessories.  Every surface
gets a material named after its palette ROLE (mat_skin, mat_hair, mat_hat, mat_top, ...)
so runtime recolouring (the customiser) can still retint it.

Output: godot/assets/models/characters/<sprite>.glb (sprite = cast.json key, which is
the `sprite` of mapdata objs), humanoid.glb (legacy tinted base, humanoid_legacy.py),
manifest.json ({sprites: {...}, aliases: {...}}).
Clips: Idle, Walk, Run (looping).  Front = -Y (Godot +Z), feet at origin, 1.5 m tall.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402
import monsdf as SD  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXTRACTED = os.path.join(ROOT, 'pipeline', 'extracted')
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'characters')
TARGET_HEIGHT = 1.5
UNITS_TALL = 24.0          # model is built in sprite rows (24 = full height)
TRI_BUDGET = 4500

DEFAULTS = {'skin': '#f0b88a', 'hair': '#4a3428', 'hat': '#d03a3a', 'shirt': '#4a78c8', 'pants': '#3a4058',
            'shoes': '#2e2e3e', 'accent': '#f8f8f8', 'coat': '#f4f4f8', 'bag': '#c8a040'}


# ----------------------------------------------------------------------------- colour helpers
def _rgb(h):
    h = h.lstrip('#')
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def shade(h, amt):
    """gfx.js shade() (hue-shifted lighten/darken), for accents like hat brims."""
    import colorsys
    r, g, b = _rgb(h)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    hd = hh * 360
    if amt < 0:
        dh = ((250 - hd + 540) % 360) - 180
        hd, ss, ll = hd + dh * min(1, -amt) * 0.35, min(1, ss * (1 - amt * 0.15)), max(0, ll + amt * 0.5)
    else:
        dh = ((55 - hd + 540) % 360) - 180
        hd, ss, ll = hd + dh * min(1, amt) * 0.3, max(0, ss * (1 - amt * 0.1)), min(1, ll + amt * 0.5)
    r, g, b = colorsys.hls_to_rgb((hd % 360) / 360.0, ll, ss)
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in (r, g, b))


# ----------------------------------------------------------------------------- SDF primitives (x, y=depth, z up)
def ell(c, r):
    def f(X, Y, Z):
        return SD.sdf_ellipsoid(X, Z, Y, c[0], c[2], c[1], r[0], r[2], r[1], 0.0)
    f.bb = (c[0] - r[0], c[1] - r[1], c[2] - r[2], c[0] + r[0], c[1] + r[1], c[2] + r[2])
    return f


def cone(a, b, r1, r2):
    def f(X, Y, Z):
        return SD.sdf_round_cone(X, Y, Z, a, b, r1, r2)
    R = max(r1, r2)
    f.bb = (min(a[0], b[0]) - R, min(a[1], b[1]) - R, min(a[2], b[2]) - R,
            max(a[0], b[0]) + R, max(a[1], b[1]) + R, max(a[2], b[2]) + R)
    return f


def rbox(c, half, r):
    def f(X, Y, Z):
        qx = np.abs(X - c[0]) - half[0] + r
        qy = np.abs(Y - c[1]) - half[1] + r
        qz = np.abs(Z - c[2]) - half[2] + r
        out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
        return out + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0) - r
    f.bb = (c[0] - half[0], c[1] - half[1], c[2] - half[2], c[0] + half[0], c[1] + half[1], c[2] + half[2])
    return f


def cyl(c, radius, half_h, r=0.3):
    """Vertical rounded cylinder (disc) centred at c."""
    def f(X, Y, Z):
        d = np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2) - radius + r
        q = np.abs(Z - c[2]) - half_h + r
        return np.sqrt(np.maximum(d, 0) ** 2 + np.maximum(q, 0) ** 2) + np.minimum(np.maximum(d, q), 0) - r
    f.bb = (c[0] - radius, c[1] - radius, c[2] - half_h, c[0] + radius, c[1] + radius, c[2] + half_h)
    return f


def halfspace(axis, value, keep_above=True):
    """Keep the side of a plane: axis 0/1/2, keep coord > value (or < value)."""
    def f(X, Y, Z):
        v = (X, Y, Z)[axis]
        return (value - v) if keep_above else (v - value)
    f.bb = None
    return f


class Piece:
    """One smooth surface: union of `add` SDFs, minus `sub`, intersected with `clip`."""

    def __init__(self, name, role, bone, add, sub=(), clip=(), k=0.8, h=0.2):
        self.name, self.role, self.bone = name, role, bone
        self.add, self.sub, self.clip = list(add), list(sub), list(clip)
        self.k, self.h = k, h

    def mesh(self):
        bbs = [f.bb for f in self.add]
        lo = np.min([b[:3] for b in bbs], axis=0)
        hi = np.max([b[3:] for b in bbs], axis=0)
        h = self.h
        pad = 3 * h + 0.3
        vol = float(np.prod(hi - lo + 2 * pad))
        h = max(h, (vol / 2.5e6) ** (1 / 3.0))
        xs = np.arange(lo[0] - pad, hi[0] + pad + h, h)
        ys = np.arange(lo[1] - pad, hi[1] + pad + h, h)
        zs = np.arange(lo[2] - pad, hi[2] + pad + h, h)
        X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
        F = None
        for f in self.add:
            v = f(X, Y, Z)
            F = v if F is None else SD.smin(F, v, self.k)
        for f in self.sub:
            F = np.maximum(F, -f(X, Y, Z))
        for f in self.clip:
            F = np.maximum(F, f(X, Y, Z))
        return SD.surface_nets(F, (xs[0], ys[0], zs[0]), h)


# ----------------------------------------------------------------------------- the recipe
HEAD_C = (0.0, 0.0, 17.0)
HEAD_R = (6.2, 5.7, 5.9)


def face_cut():
    """Region carved out of hair shells so the face shows (below a fringe line)."""
    return ell((0.0, -6.3, 15.0), (5.3, 5.2, 3.9))


def hair_shell(extra=0.45, top_off=0.35):
    c = (HEAD_C[0], HEAD_C[1] + 0.35, HEAD_C[2] + top_off)
    return ell(c, (HEAD_R[0] + extra, HEAD_R[1] + extra, HEAD_R[2] + extra))


def build_recipe(d):
    """cast.json entry -> list of Pieces + material colours by role."""
    col = dict(DEFAULTS)
    for k in ('skin', 'hair', 'hat', 'shirt', 'pants', 'shoes', 'accent', 'coat'):
        if d.get(k):
            col[k] = d[k]
    col['bag'] = d.get('backpack') or d.get('bag') or DEFAULTS['bag']
    col['hatk'] = d.get('hatK') or shade(col['hat'], 0.45)
    col['brim'] = d.get('brim') or shade(col['hat'], -0.3)
    col['eye'] = '#1e1a2a'
    col['white'] = '#ffffff'
    col['mouth'] = '#7a3038'
    col['beard'] = d.get('beard') or col['hair']
    col['glasses'] = '#2a2a3a'
    col['emblem'] = d.get('emblem') or '#e04040'
    head = d.get('head') or 'short'
    body = d.get('body') or 'normal'
    P = []
    # ---------- head + face
    P.append(Piece('head', 'skin', 'head', [ell(HEAD_C, HEAD_R), cone((0, 0, 11.6), (0, 0, 12.8), 1.4, 1.5),
                                            ell((-6.1, 0.3, 16.2), (0.9, 1.1, 1.4)), ell((6.1, 0.3, 16.2), (0.9, 1.1, 1.4))],
                   k=0.6))
    for sx in (-1, 1):
        ex = 2.25 * sx
        P.append(Piece('eye%d' % sx, 'eye', 'head', [ell((ex, -5.05, 16.0), (0.78, 0.55, 1.25))], h=0.12))
        P.append(Piece('eyehl%d' % sx, 'white', 'head', [ell((ex - 0.25, -5.45, 16.5), (0.3, 0.25, 0.34))], h=0.08))
    P.append(Piece('mouth', 'mouth', 'head', [cone((-0.7, -5.5, 13.6), (0.7, -5.5, 13.6), 0.28, 0.28)], h=0.08))
    if d.get('glasses'):
        for sx in (-1, 1):
            P.append(Piece('lens%d' % sx, 'glasses', 'head',
                           [ell((2.25 * sx, -5.5, 16.0), (1.55, 0.35, 1.2))],
                           sub=[ell((2.25 * sx, -5.9, 16.0), (1.05, 0.6, 0.75))], h=0.1))
        P.append(Piece('bridge', 'glasses', 'head', [cone((-0.8, -5.9, 16.3), (0.8, -5.9, 16.3), 0.25, 0.25)], h=0.1))
    if d.get('beard'):
        P.append(Piece('beard', 'beard', 'head', [ell((0, -3.6, 12.9), (4.4, 2.6, 2.3)), ell((0, -4.4, 14.0), (2.6, 1.4, 1.0))],
                       sub=[cone((-0.9, -5.6, 13.9), (0.9, -5.6, 13.9), 0.45, 0.45)], k=0.8))
    # ---------- hair / hats
    shell = hair_shell()
    fringe_clip = []
    if head == 'short':
        P.append(Piece('hair', 'hair', 'head', [shell, ell((-2.5, -4.6, 20.0), (2.8, 1.8, 2.0)), ell((2.0, -4.8, 20.3), (2.6, 1.6, 1.8))],
                       sub=[face_cut()], clip=[halfspace(2, 12.8)], k=0.8))
    elif head == 'spiky':
        spikes = [cone((x, y, 20.0), (x * 1.6, y * 1.4 + 0.8, 25.2 - abs(x) * 0.25), 2.2, 0.35)
                  for x, y in ((-3.5, -1.5), (-1.2, -2.5), (1.3, -2.0), (3.6, -0.8), (0.0, 1.5), (-2.8, 2.5), (2.8, 2.5))]
        spikes += [cone((sx * 5.0, 1.0, 18.5), (sx * 8.2, 1.2, 19.8), 1.8, 0.3) for sx in (-1, 1)]
        spikes += [cone((0, 4.5, 18.0), (0, 8.0, 17.5), 2.0, 0.35)]
        P.append(Piece('hair', 'hair', 'head', [shell] + spikes + [ell((-2.0, -4.7, 20.2), (3.0, 1.8, 2.0)),
                                                                     ell((2.5, -4.6, 20.4), (2.5, 1.6, 1.9))],
                       sub=[face_cut()], clip=[halfspace(2, 12.8)], k=1.0))
    elif head == 'long':
        P.append(Piece('hair', 'hair', 'head', [shell, ell((0, 2.2, 13.4), (6.6, 4.2, 5.4)),
                                                ell((-5.8, -1.0, 13.5), (1.8, 3.0, 4.6)), ell((5.8, -1.0, 13.5), (1.8, 3.0, 4.6)),
                                                ell((0.0, -4.7, 20.1), (5.0, 1.8, 2.0))],
                       sub=[face_cut()], clip=[halfspace(2, 8.6)], k=1.2))
    elif head == 'bald':
        P.append(Piece('hair', 'hair', 'head', [hair_shell(0.35, -0.2)], sub=[face_cut()],
                       clip=[halfspace(2, 16.6, keep_above=False), halfspace(1, -3.0), halfspace(2, 12.8)], k=0.5))
        P.append(Piece('shine', 'white', 'head', [ell((-2.2, -3.2, 21.6), (1.0, 0.5, 0.7))], h=0.1))
    elif head == 'pony':
        P.append(Piece('hair', 'hair', 'head', [shell, ell((0.0, -4.7, 20.2), (5.2, 1.8, 2.0)),
                                                cone((0.0, 6.4, 19.0), (0.3, 8.6, 14.5), 2.4, 1.7),
                                                cone((0.3, 8.6, 14.5), (0.0, 7.6, 10.5), 1.7, 0.6)],
                       sub=[face_cut()], clip=[halfspace(2, 9.0)], k=1.0))
        P.append(Piece('tie', 'accent', 'head', [ell((0, 6.2, 19.2), (1.5, 1.3, 1.5))], h=0.12))
    elif head == 'bun':
        P.append(Piece('hair', 'hair', 'head', [shell, ell((0.0, -4.7, 20.3), (5.2, 1.8, 2.0)),
                                                ell((0.0, 1.5, 23.6), (2.9, 2.9, 2.4))],
                       sub=[face_cut()], clip=[halfspace(2, 12.8)], k=1.0))
    elif head == 'cap':
        P.append(Piece('hair', 'hair', 'head', [shell, ell((-5.2, -3.6, 17.2), (1.6, 1.6, 1.6)), ell((5.2, -3.6, 17.2), (1.6, 1.6, 1.6))],
                       sub=[face_cut()], clip=[halfspace(2, 12.8), halfspace(2, 19.0, keep_above=False)], k=0.8))
        dome_c = (0.0, 0.35, 18.4)
        P.append(Piece('hat', 'hat', 'head', [ell(dome_c, (6.75, 6.45, 5.6)), cyl((0, 0.35, 18.9), 6.8, 0.6, 0.3)],
                       clip=[halfspace(2, 18.3)], k=0.4))
        P.append(Piece('hatk', 'hatk', 'head', [ell((0.0, -4.3, 21.2), (3.6, 2.8, 2.6))],
                       clip=[halfspace(2, 18.9)], sub=[ell(dome_c, (6.35, 6.05, 5.2))], h=0.14))
        P.append(Piece('brim', 'brim', 'head', [ell((0.0, -6.2, 18.6), (5.2, 4.2, 0.55))], clip=[halfspace(1, -9.5), halfspace(1, -4.0, False)], h=0.12))
    elif head == 'hat':
        P.append(Piece('hair', 'hair', 'head', [shell], sub=[face_cut()],
                       clip=[halfspace(2, 12.8), halfspace(2, 19.0, keep_above=False)], k=0.8))
        P.append(Piece('hat', 'hat', 'head', [ell((0, 0.3, 19.6), (5.9, 5.7, 5.0)), cyl((0, 0.3, 19.2), 9.4, 0.45, 0.35)],
                       clip=[halfspace(2, 18.7)], k=0.6))
        P.append(Piece('band', 'brim', 'head', [cyl((0, 0.3, 20.0), 6.05, 0.6, 0.25)], h=0.14))
    elif head == 'beanie':
        P.append(Piece('hair', 'hair', 'head', [shell, ell((-5.4, -2.8, 16.8), (1.5, 1.8, 2.0)), ell((5.4, -2.8, 16.8), (1.5, 1.8, 2.0))],
                       sub=[face_cut()], clip=[halfspace(2, 12.8), halfspace(2, 19.2, keep_above=False)], k=0.8))
        P.append(Piece('hat', 'hat', 'head', [ell((0, 0.3, 18.6), (6.8, 6.5, 5.6))], clip=[halfspace(2, 18.6)], k=0.6))
        P.append(Piece('band', 'hatk', 'head', [cyl((0, 0.3, 19.0), 6.95, 0.75, 0.5)],
                       sub=[cyl((0, 0.3, 19.0), 5.6, 2.0, 0.1)], h=0.14))
    # ---------- torso / arms / legs
    top = 'coat' if body == 'coat' else ('skin' if body == 'swim' else 'top')
    col['top'] = col['shirt']
    P.append(Piece('torso', top, 'spine', [ell((0, 0.1, 8.9), (3.9, 2.9, 3.4)), cone((0, 0.1, 11.3), (0, 0.1, 7.0), 3.0, 3.4)], k=1.0))
    if body != 'swim':
        P.append(Piece('collar', 'accent', 'spine', [ell((0, -1.9, 11.35), (1.6, 1.2, 0.8))], h=0.12))
    if body == 'coat':
        P.append(Piece('shirt', 'top', 'spine', [ell((0, -2.3, 9.4), (1.5, 1.3, 2.0))], h=0.14))
        P.append(Piece('coattail', 'coat', 'hips', [cone((0, 0.2, 7.0), (0, 0.4, 3.4), 3.5, 4.1)],
                       sub=[rbox((0, -4.6, 3.0), (0.9, 2.0, 3.5), 0.3)], clip=[halfspace(2, 3.0)], k=0.6))
    if d.get('emblem'):
        P.append(Piece('emblem', 'emblem', 'spine', [ell((0.4, -2.95, 9.3), (1.1, 0.5, 1.2))], h=0.1))
    arm_role = 'skin' if body == 'swim' else top
    for sx in (-1, 1):
        bone = 'arm_L' if sx > 0 else 'arm_R'
        P.append(Piece('arm%d' % sx, arm_role, bone, [cone((sx * 3.6, 0.2, 10.6), (sx * 4.9, 0.1, 7.6), 1.35, 1.15)], k=0.5, h=0.15))
        P.append(Piece('hand%d' % sx, 'skin', bone, [ell((sx * 5.05, 0.0, 6.6), (1.15, 1.15, 1.2))], h=0.13))
    leg_role = 'pants' if body in ('normal', 'coat') else 'skin'
    if body in ('normal', 'coat', 'shorts', 'swim'):
        P.append(Piece('hips', 'pants', 'hips', [ell((0, 0.1, 6.0), (3.5, 2.6, 1.7))], k=0.6))
    if body == 'shorts':
        for sx in (-1, 1):
            P.append(Piece('short%d' % sx, 'pants', 'leg_L' if sx > 0 else 'leg_R',
                           [cone((sx * 1.75, 0.1, 5.4), (sx * 1.85, 0.1, 3.9), 1.6, 1.55)], h=0.15))
    if body == 'dress':
        P.append(Piece('skirt', 'top', 'hips', [cone((0, 0.1, 7.4), (0, 0.2, 3.6), 3.3, 4.4)], clip=[halfspace(2, 3.4)], k=0.6))
    for sx in (-1, 1):
        bone = 'leg_L' if sx > 0 else 'leg_R'
        P.append(Piece('leg%d' % sx, leg_role, bone, [cone((sx * 1.75, 0.1, 5.6), (sx * 1.85, 0.0, 1.8), 1.4, 1.3)], h=0.15))
        P.append(Piece('shoe%d' % sx, 'shoes', bone, [ell((sx * 1.9, -0.55, 1.05), (1.55, 2.1, 1.1))],
                       clip=[halfspace(2, 0.0)], h=0.15))
    if d.get('backpack'):
        P.append(Piece('pack', 'bag', 'spine', [rbox((0, 3.9, 8.6), (3.0, 1.5, 2.8), 1.0)], k=0.5))
        P.append(Piece('flap', 'bagd', 'spine', [rbox((0, 4.3, 10.0), (3.1, 1.3, 1.3), 0.7)], h=0.15))
        col['bagd'] = shade(col['bag'], -0.25)
        for sx in (-1, 1):
            P.append(Piece('strap%d' % sx, 'bagd', 'spine',
                           [cone((sx * 2.2, 1.6, 11.3), (sx * 2.4, -2.95, 10.4), 0.45, 0.45),
                            cone((sx * 2.4, -2.95, 10.4), (sx * 2.5, -2.4, 6.9), 0.45, 0.45)], k=0.3, h=0.12))
    return P, col


# ----------------------------------------------------------------------------- build + export
def build_character(key, d, out_dir):
    C.reset_scene()
    pieces, col = build_recipe(d)
    mats = []
    mat_index = {}

    def mat_for(role):
        if role not in mat_index:
            mat_index[role] = len(mats)
            m = C.make_material('mat_' + role, col.get(role, '#ff00ff'), roughness=0.8, specular=0.1)
            mats.append(m)
        return mat_index[role]

    mb = C.MeshBuilder()
    raw = []
    total = 0.0
    for pc in pieces:
        v, q = pc.mesh()
        if len(q) == 0:
            continue
        area = len(q) * pc.h * pc.h
        raw.append((pc, v, q, area))
        total += area
    for pc, v, q, area in raw:
        budget = max(60, int(TRI_BUDGET * area / total))
        me = bpy.data.meshes.new(pc.name)
        me.from_pydata([tuple(map(float, p)) for p in v], [], [tuple(int(i) for i in f) for f in q])
        me.validate()
        obj = bpy.data.objects.new(pc.name, me)
        bpy.context.scene.collection.objects.link(obj)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        if 2 * len(q) > budget:
            mod = obj.modifiers.new('dec', 'DECIMATE')
            mod.ratio = max(0.03, budget / float(2 * len(q)))
            me2 = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            obj.modifiers.clear()
            obj.data = me2
            bpy.data.meshes.remove(me)
            me = me2
        gi = mb.group_index(pc.bone)
        mi = mat_for(pc.role)
        vm = {}
        for mv in me.vertices:
            nv = mb.bm.verts.new(mv.co)
            nv[mb.grp] = gi
            vm[mv.index] = nv
        for poly in me.polygons:
            try:
                f = mb.bm.faces.new([vm[i] for i in poly.vertices])
            except ValueError:
                continue
            f.smooth = True
            f.material_index = mi
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(me)
    for g in ('hips', 'spine', 'head', 'arm_L', 'arm_R', 'leg_L', 'leg_R'):
        mb.group_index(g)
    mb.finish()
    k = TARGET_HEIGHT / UNITS_TALL
    mb.transform(lambda co: Vector((co.x * k, co.y * k, co.z * k)))
    bones = [
        {'name': 'hips', 'head': Vector((0, 0, 6.2 * k)), 'parent': None, 'length': 0.1},
        {'name': 'spine', 'head': Vector((0, 0, 7.0 * k)), 'parent': 'hips', 'length': 0.1},
        {'name': 'head', 'head': Vector((0, 0, 11.8 * k)), 'parent': 'spine', 'length': 0.2},
        {'name': 'arm_L', 'head': Vector((3.8 * k, 0, 10.4 * k)), 'parent': 'spine', 'length': 0.1},
        {'name': 'arm_R', 'head': Vector((-3.8 * k, 0, 10.4 * k)), 'parent': 'spine', 'length': 0.1},
        {'name': 'leg_L', 'head': Vector((1.75 * k, 0, 5.6 * k)), 'parent': 'hips', 'length': 0.1},
        {'name': 'leg_R', 'head': Vector((-1.75 * k, 0, 5.6 * k)), 'parent': 'hips', 'length': 0.1},
    ]
    obj = mb.to_object(key, mats)
    arm = C.build_armature(key, bones, root_len=0.2)
    C.skin_to_armature(obj, arm)
    animate_humanoid(arm, [b['name'] for b in bones])
    path = os.path.join(out_dir, key + '.glb')
    C.export_glb(path)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    return {'file': key + '.glb', 'tris': tris, 'bytes': os.path.getsize(path), 'head': d.get('head') or 'short',
            'body': d.get('body') or 'normal', 'materials': [m.name for m in mats]}


def animate_humanoid(arm, names):
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    allb = ['root'] + names
    idle = C.ActionWriter(arm, 'Idle', 60)
    for f in range(0, 61, 2):
        t = f / 60.0
        sn = math.sin(2 * math.pi * t)
        idle.key('hips', f, loc=(0, 0, -0.006 * (0.5 - 0.5 * math.cos(2 * math.pi * t))))
        idle.key('spine', f, scl=(1 + 0.012 * sn, 1 + 0.012 * sn, 1 + 0.02 * sn))
        idle.key('head', f, rot=(X, math.radians(2.0) * math.sin(2 * math.pi * t + 0.8)))
        idle.key('arm_L', f, rot=(Y, -math.radians(3) * sn))
        idle.key('arm_R', f, rot=(Y, math.radians(3) * sn))
    acts = [idle.write(allb)]
    for name, n, amp_leg, amp_arm, bob, lean in (('Walk', 24, 32, 30, 0.035, 3), ('Run', 16, 48, 55, 0.06, 10)):
        w_ = C.ActionWriter(arm, name, n)
        for f in range(0, n + 1):
            w = 2 * math.pi * f / n
            w_.key('hips', f, loc=(0, 0, bob * (0.5 - 0.5 * math.cos(2 * w))))
            w_.key('leg_L', f, rot=(X, math.radians(amp_leg) * math.sin(w)))
            w_.key('leg_R', f, rot=(X, -math.radians(amp_leg) * math.sin(w)))
            w_.key('arm_L', f, rot=(X, -math.radians(amp_arm) * math.sin(w)))
            w_.key('arm_R', f, rot=(X, math.radians(amp_arm) * math.sin(w)))
            w_.key('spine', f, rot=(Z, math.radians(5) * math.sin(w)))
            w_.key('head', f, rot=(X, math.radians(lean * 0.3) + math.radians(2) * math.sin(2 * w)))
        acts.append(w_.write(allb))
    C.stash_actions(arm, acts)


# sprite keys that aren't humanoids (creatures / objects) are left to other models;
# story sprites without their own cast entry fall back to these archetypes
ALIASES = {'gambler_asleep': 'gambler'}


def main():
    args = C.parse_args()
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    C.ensure_dir(OUT_DIR)
    cast = json.load(open(os.path.join(EXTRACTED, 'cast.json')))['cast']
    humanoid_info = None
    if '--no-humanoid' not in args and only is None:
        import humanoid_legacy
        humanoid_info = humanoid_legacy.build_humanoid([])
    t0 = time.time()
    sprites = {}
    for key, d in cast.items():
        if d.get('creature') or d.get('object'):
            continue
        if only and key not in only:
            continue
        if key in ALIASES:
            continue
        info = build_character(key, d, OUT_DIR)
        sprites[key] = info
        print('%-20s tris=%5d %4dKB  %s/%s' % (key, info['tris'], info['bytes'] // 1024, info['head'], info['body']), flush=True)
    if only is None:
        manifest = {
            'sprites': sprites,
            'aliases': ALIASES,
            'humanoid': humanoid_info,
            'height_m': TARGET_HEIGHT,
            'animations': {'Idle': {'seconds': 2.0, 'loop': True}, 'Walk': {'seconds': 0.8, 'loop': True},
                           'Run': {'seconds': 0.53, 'loop': True}},
            'conventions': {'front': 'Blender -Y == glTF/Godot +Z', 'origin': 'feet at origin',
                            'materials': 'mat_<role>: skin hair hat hatk brim top coat pants shoes accent bag eye '
                                         'white mouth beard glasses emblem (flat colours; cel-shade with Toon.apply)',
                            'bones': 'root > hips > spine > head / arm_L / arm_R, hips > leg_L / leg_R'},
            'source': 'upstream src/data/cast.js (pipeline/extracted/cast.json) + src/art/chars.js head/body styles',
            'elapsed_seconds': round(time.time() - t0, 1),
        }
        with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=1)
    print('DONE characters=%d in %.1fs' % (len(sprites), time.time() - t0))


if __name__ == '__main__':
    main()

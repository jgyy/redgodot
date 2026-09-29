"""Battle-effect meshes for every particle shape upstream's src/art/vfx.js draws
(drawShape: dot, spark, star, ring, bubble, flame, leaf, snow, rock, note, z, coin,
seed, needle, bone, egg, shard, heart) plus the extra 3D pieces the move recipes
use (impact burst, claw crescent, fist, water drop, poke ball).

    python3 pipeline/blender/gen_vfx.py          (or: blender --background --python ...)

Output: godot/assets/models/vfx/<name>.glb + manifest.json. Each mesh is centred on
the origin with a ~1 m nominal size (BattleVfx.gd scales it to upstream's pixel size
at the effect's depth) and faces the camera along +Z in Godot (Blender -Y). Colour is
applied per particle in Godot (unshaded override), except poke_ball which keeps its
named materials (ball_top / ball_bottom / ball_band / ball_button).
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector, Matrix, noise

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'vfx')


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, hexcol='#ffffff', emit=0.0, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    h = hexcol.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]
    b.inputs['Base Color'].default_value = lin
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = lin
        b.inputs['Emission Strength'].default_value = emit
    return m


def finish(bm, name, mats, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# Blender coords: X right, Z up, -Y toward the camera (== Godot +Z)
def extrude_poly(bm, pts, depth, mi=0):
    """Flat polygon in the XZ plane (facing -Y), extruded along Y."""
    top = [bm.verts.new((x, -depth / 2, z)) for x, z in pts]
    bot = [bm.verts.new((x, depth / 2, z)) for x, z in pts]
    f1 = bm.faces.new(top)
    f2 = bm.faces.new(list(reversed(bot)))
    f1.material_index = f2.material_index = mi
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((top[i], bot[i], bot[j], top[j]))
        f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def ico(bm, r=0.5, sub=2, center=(0, 0, 0), scale=(1, 1, 1), mi=0):
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    for v in res['verts']:
        v.co = Vector((v.co.x * scale[0] + center[0], v.co.y * scale[1] + center[1], v.co.z * scale[2] + center[2]))
    for f in {f for v in res['verts'] for f in v.link_faces}:
        f.material_index = mi
    return res['verts']


def cyl(bm, r1, r2, depth, seg=12, mat_=Matrix.Identity(4), mi=0, caps=True):
    res = bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r1, radius2=r2, depth=depth, matrix=mat_)
    for f in {f for v in res['verts'] for f in v.link_faces}:
        f.material_index = mi
    return res['verts']


# ------------------------------------------------------------------ shapes (~1 m nominal)
def s_dot(bm):
    ico(bm, 0.5, 2)


def s_flame(bm):
    # upstream flame: round bottom, stretched pointed top (height 2.6x radius)
    res = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=0.5)
    for v in res['verts']:
        z = v.co.z / 0.5
        if z > 0:
            k = (1 - z) ** 1.15
            v.co.x *= k
            v.co.y *= k
            v.co.z = z * 0.5 * 1.9
        v.co.x += 0.06 * math.sin(v.co.z * 9)
        v.co.z -= 0.2


def s_spark(bm):
    for rot in (0, math.pi / 2):
        pts = [(0, 0.55), (0.08, 0.08), (0.55, 0), (0.08, -0.08), (0, -0.55), (-0.08, -0.08), (-0.55, 0), (-0.08, 0.08)]
        pts = [(x * math.cos(rot) - z * math.sin(rot), x * math.sin(rot) + z * math.cos(rot)) for x, z in pts]
        extrude_poly(bm, pts, 0.06)
        break
    ico(bm, 0.12, 1)


def s_star(bm):
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = 0.5 if i % 2 == 0 else 0.21
        pts.append((math.cos(a) * r, math.sin(a) * r))
    extrude_poly(bm, pts, 0.14)


def s_ring(bm):
    R, r, nu, nv = 0.5, 0.05, 40, 6
    rings = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        c = Vector((math.cos(a), 0, math.sin(a)))
        ring = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            ring.append(bm.verts.new(c * (R + r * math.cos(b)) + Vector((0, r * math.sin(b), 0))))
        rings.append(ring)
    for i in range(nu):
        A, B2 = rings[i], rings[(i + 1) % nu]
        for j in range(nv):
            bm.faces.new((A[j], B2[j], B2[(j + 1) % nv], A[(j + 1) % nv]))


def s_bubble(bm):
    ico(bm, 0.5, 3)


def s_leaf(bm):
    pts = []
    n = 16
    for i in range(n):
        a = 2 * math.pi * i / n
        x = math.sin(a) * 0.22 * (1 - abs(math.cos(a)) ** 2.5)
        z = -math.cos(a) * 0.5
        pts.append((x, z))
    extrude_poly(bm, pts, 0.04)
    # midrib
    cyl(bm, 0.02, 0.02, 0.9, seg=5, mat_=Matrix.Translation((0, -0.03, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X') @ Matrix.Rotation(math.pi / 2, 4, 'X'))


def s_snow(bm):
    # six-armed snowflake (upstream 'snow': a plus with diagonal ticks)
    pts = []
    for i in range(12):
        a = math.pi / 2 + i * math.pi / 6
        r = 0.5 if i % 2 == 0 else 0.1
        pts.append((math.cos(a) * r, math.sin(a) * r))
    extrude_poly(bm, pts, 0.08)


def s_rock(bm):
    vs = ico(bm, 0.5, 1)
    for v in vs:
        v.co *= 1.0 + 0.28 * noise.noise(v.co * 4.0 + Vector((0.3, 0.9, 1.7)))


def s_note(bm):
    ico(bm, 0.2, 2, center=(-0.12, 0, -0.32), scale=(1.2, 0.8, 0.9))
    cyl(bm, 0.035, 0.035, 0.75, seg=6, mat_=Matrix.Translation((0.07, 0, 0.05)))
    extrude_poly(bm, [(0.07, 0.42), (0.34, 0.2), (0.3, 0.12), (0.07, 0.28)], 0.07)


def s_z(bm):
    pts = [(-0.35, 0.4), (0.35, 0.4), (0.35, 0.27), (-0.12, -0.27), (0.35, -0.27), (0.35, -0.4), (-0.35, -0.4),
           (-0.35, -0.27), (0.12, 0.27), (-0.35, 0.27)]
    extrude_poly(bm, pts, 0.12)


def s_coin(bm):
    cyl(bm, 0.5, 0.5, 0.12, seg=20, mat_=Matrix.Rotation(math.pi / 2, 4, 'X'))


def s_seed(bm):
    ico(bm, 0.5, 2, scale=(0.75, 0.75, 1.0))


def s_needle(bm):
    # along +X (the travel direction)
    cyl(bm, 0.06, 0.0, 0.7, seg=6, mat_=Matrix.Translation((0.35, 0, 0)) @ Matrix.Rotation(-math.pi / 2, 4, 'Y'))
    cyl(bm, 0.06, 0.0, 0.3, seg=6, mat_=Matrix.Translation((-0.15, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))


def s_bone(bm):
    cyl(bm, 0.09, 0.09, 0.8, seg=8, mat_=Matrix.Rotation(math.pi / 2, 4, 'Y'))
    for x in (-0.42, 0.42):
        for z in (-0.09, 0.09):
            ico(bm, 0.13, 1, center=(x, 0, z))


def s_egg(bm):
    res = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=0.4)
    for v in res['verts']:
        if v.co.z > 0:
            v.co.z *= 1.35
        v.co.z *= 1.05


def s_shard(bm):
    top = cyl(bm, 0.2, 0.0, 0.6, seg=6, mat_=Matrix.Translation((0, 0, 0.2)), caps=False)
    bot = cyl(bm, 0.2, 0.0, 0.3, seg=6, mat_=Matrix.Translation((0, 0, -0.25)) @ Matrix.Rotation(math.pi, 4, 'X'), caps=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-3)
    _ = (top, bot)


def s_heart(bm):
    pts = []
    for i in range(24):
        t = 2 * math.pi * i / 24
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 34, z / 34 + 0.05))
    extrude_poly(bm, pts, 0.18)


def s_impact(bm):
    pts = []
    for i in range(16):
        a = math.pi / 2 + i * math.pi / 8
        r = 0.5 if i % 2 == 0 else 0.2
        pts.append((math.cos(a) * r, math.sin(a) * r))
    extrude_poly(bm, pts, 0.05)


def s_claw(bm):
    # crescent streak (a slash mark), long axis along the X/Z diagonal
    pts = []
    n = 14
    for i in range(n + 1):
        t = i / n
        a = -0.9 + 1.8 * t
        w = math.sin(t * math.pi) * 0.09 + 0.005
        pts.append((math.sin(a) * 0.55, math.cos(a) * 0.55 - 0.45 + w))
    for i in range(n, -1, -1):
        t = i / n
        a = -0.9 + 1.8 * t
        w = math.sin(t * math.pi) * 0.09 + 0.005
        pts.append((math.sin(a) * 0.55, math.cos(a) * 0.55 - 0.45 - w))
    pts = pts[:-1]
    rot = math.radians(-45)
    pts = [(x * math.cos(rot) - z * math.sin(rot), x * math.sin(rot) + z * math.cos(rot)) for x, z in pts]
    extrude_poly(bm, pts, 0.03)


def s_fist(bm):
    ico(bm, 0.36, 2, scale=(1.0, 0.8, 0.85))
    for i in range(4):
        ico(bm, 0.13, 1, center=(-0.24 + i * 0.16, -0.26, 0.12))
    ico(bm, 0.14, 1, center=(0.32, -0.12, -0.12))


def s_drop(bm):
    res = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=9, radius=0.35)
    for v in res['verts']:
        z = v.co.z / 0.35
        if z > 0:
            k = (1 - z) ** 1.3
            v.co.x *= k
            v.co.y *= k
            v.co.z = z * 0.35 * 2.2


def s_pokeball(bm):
    res = bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=18, radius=0.5)
    for f in {f for v in res['verts'] for f in v.link_faces}:
        cz = sum(v.co.z for v in f.verts) / len(f.verts)
        f.material_index = 0 if cz > 0.035 else (2 if cz > -0.035 else 1)
    # front button (toward -Y == Godot +Z)
    cyl(bm, 0.15, 0.15, 0.08, seg=16, mat_=Matrix.Translation((0, -0.49, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X'), mi=2)
    cyl(bm, 0.1, 0.1, 0.08, seg=16, mat_=Matrix.Translation((0, -0.53, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X'), mi=3)


SHAPES = [
    ('dot', s_dot), ('flame', s_flame), ('spark', s_spark), ('star', s_star), ('ring', s_ring), ('bubble', s_bubble),
    ('leaf', s_leaf), ('snow', s_snow), ('rock', s_rock), ('note', s_note), ('z', s_z), ('coin', s_coin), ('seed', s_seed),
    ('needle', s_needle), ('bone', s_bone), ('egg', s_egg), ('shard', s_shard), ('heart', s_heart), ('impact', s_impact),
    ('claw', s_claw), ('fist', s_fist), ('drop', s_drop), ('poke_ball', s_pokeball),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith('.glb'):
            os.remove(os.path.join(OUT_DIR, f))
    manifest = {'conventions': {'origin': 'centred', 'size': '~1 m nominal', 'front': 'Godot +Z',
                                'colour': 'applied per particle in Godot (BattleVfx.gd), except poke_ball'}, 'vfx': {}}
    for name, fn in SHAPES:
        reset()
        bm = bmesh.new()
        fn(bm)
        if name == 'poke_ball':
            mats = [mat('ball_top', '#e04848', rough=0.3), mat('ball_bottom', '#f4f4f4', rough=0.3),
                    mat('ball_band', '#1b1a2e', rough=0.6), mat('ball_button', '#f8f8f8', rough=0.2)]
        else:
            mats = [mat('vfx', '#ffffff', emit=1.0)]
        smooth = name in ('dot', 'bubble', 'egg', 'seed', 'flame', 'drop', 'poke_ball', 'fist', 'ring')
        ob = finish(bm, name, mats, smooth)
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        path = os.path.join(OUT_DIR, name + '.glb')
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True, export_animations=False)
        manifest['vfx'][name] = {'file': name + '.glb', 'tris': tris}
        print('vfx %-10s tris=%d' % (name, tris))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1)


if __name__ == '__main__':
    main()

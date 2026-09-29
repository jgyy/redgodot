"""Battle-effect meshes for every particle shape upstream's src/art/vfx.js draws
(drawShape: dot, spark, star, ring, bubble, flame, leaf, snow, rock, note, z, coin,
seed, needle, bone, egg, shard, heart) plus the extra 3D pieces the move recipes
use (impact burst, claw crescent, fist, water drop, poke ball).

    python3 pipeline/blender/gen_vfx.py          (or: blender --background --python ...)

Output: godot/assets/models/vfx/<name>.glb + manifest.json. Each mesh is centred on
the origin with a ~1 m nominal size (BattleVfx.gd scales it to upstream's pixel size
at the effect's depth) and faces the camera along +Z in Godot (Blender -Y). Colour is
applied per particle in Godot (unshaded override, multiplied with the mesh's baked vertex colours),
except poke_ball which keeps its named materials (ball_top / ball_bottom / ball_band / ball_button).

Every prop carries a baked light-to-dark gradient in its COLOR_0 vertex colours (paint() below): bright
cores / lit faces, darker rims / shadowed faces, so a flat-tinted particle still reads as a rounded, lit
object under the game's unshaded material. Shapes are bevelled or puffed rather than flat cut-outs.
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




# ------------------------------------------------------------------ vertex-colour painting
def paint(bm, fn):
    """fn(co, normal, face) -> brightness 0..1, written to the COLOR_0 layer (grey; the tint comes from Godot)."""
    layer = bm.loops.layers.color.get('Col') or bm.loops.layers.color.new('Col')
    bm.normal_update()
    for f in bm.faces:
        for l in f.loops:
            v = max(0.0, min(1.0, fn(l.vert.co, l.vert.normal, f)))
            l[layer] = (v, v, v, 1.0)


def paint_radial(lo=0.62, hi=1.0, r=0.5, axis=None):
    """Bright in the middle, darker toward the rim."""
    def fn(co, n, f):
        d = math.sqrt(co.x * co.x + co.z * co.z) if axis is None else abs(co[axis])
        return lo + (hi - lo) * (1.0 - min(1.0, d / r))
    return fn


def paint_lit(lo=0.5, hi=1.0, light=(0.35, -0.6, 0.72)):
    """Flat-shaded faces lit from the upper front (Blender -Y is toward the camera)."""
    L = Vector(light).normalized()

    def fn(co, n, f):
        return lo + (hi - lo) * max(0.0, f.normal.dot(L))
    return fn


def paint_height(lo=0.7, hi=1.0, z0=-0.5, z1=0.5):
    """Bright at the top of the shape (Blender +Z), darker at the bottom."""
    def fn(co, n, f):
        return lo + (hi - lo) * max(0.0, min(1.0, (co.z - z0) / (z1 - z0)))
    return fn


def teardrop(bm, r, height, cx=0.0, cz=0.0, bend=0.0, seg=14, rings=10, pow_=1.15, sy=1.0):
    """Round bottom, pointed top; the tip leans sideways by `bend`."""
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=0.5)
    for v in res['verts']:
        z = v.co.z / 0.5
        if z > 0:
            k = (1 - z) ** pow_
            v.co.x *= k
            v.co.y *= k
            v.co.z = z * 0.5 * height
        v.co.x = v.co.x * r * 2 + cx + bend * max(0.0, v.co.z) ** 2 * 2.0
        v.co.y *= r * 2 * sy
        v.co.z = v.co.z * (r * 2 if v.co.z < 0 else 1.0) + cz
    return res['verts']


def puffy_outline(bm, pts, depth, apex, mi=0):
    """A flat outline with a raised centre (a soft gem / pillow): front fan to an apex vertex, flat back."""
    front = [bm.verts.new((x, -depth / 2, z)) for x, z in pts]
    back = [bm.verts.new((x, depth / 2, z)) for x, z in pts]
    cx = sum(x for x, _ in pts) / len(pts)
    cz = sum(z for _, z in pts) / len(pts)
    ap = bm.verts.new((cx, -depth / 2 - apex, cz))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((front[i], front[j], ap))
        f.material_index = mi
        f = bm.faces.new((front[i], back[i], back[j], front[j]))
        f.material_index = mi
    f = bm.faces.new(list(reversed(back)))
    f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


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
    # a tongue of flame: round belly, pointed swaying tip, two small licks at its sides
    teardrop(bm, 0.36, 1.9, cx=0.0, cz=-0.2, bend=0.35, pow_=1.15)
    teardrop(bm, 0.13, 1.5, cx=-0.24, cz=-0.24, bend=-0.5, seg=10, rings=8)
    teardrop(bm, 0.11, 1.3, cx=0.25, cz=-0.26, bend=0.6, seg=10, rings=8)


def s_spark(bm):
    # four-pointed glint: long vertical/horizontal needles with pinched waists, hot little core
    for rot in (0, math.pi / 2):
        pts = [(0, 0.56), (0.07, 0.10), (0.56, 0), (0.07, -0.10), (0, -0.56), (-0.07, -0.10), (-0.56, 0), (-0.07, 0.10)]
        pts = [(x * math.cos(rot) - z * math.sin(rot), x * math.sin(rot) + z * math.cos(rot)) for x, z in pts]
        extrude_poly(bm, pts, 0.05)
        break
    ico(bm, 0.13, 2)


def s_star(bm):
    # five-point gem star with a raised centre
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = 0.5 if i % 2 == 0 else 0.21
        pts.append((math.cos(a) * r, math.sin(a) * r))
    puffy_outline(bm, pts, 0.10, 0.09)


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
    # a curled leaf: folded along its midrib, tip bent toward the camera, thin shell so it reads from both sides
    n = 14
    rows = []
    for i in range(n + 1):
        u = i / n
        z = -0.5 + u
        w = math.sin(u * math.pi) ** 0.75 * 0.24 * (1.0 - 0.25 * u)
        bend = -0.09 * (u ** 2)              # toward the camera (-Y)
        rows.append((z, w, bend))
    front = []
    back = []
    for z, w, bend in rows:
        L = bm.verts.new((-w, bend, z))
        M = bm.verts.new((0, bend - 0.045, z))
        R = bm.verts.new((w, bend, z))
        front.append((L, M, R))
        L2 = bm.verts.new((-w, bend + 0.018, z))
        M2 = bm.verts.new((0, bend - 0.03, z))
        R2 = bm.verts.new((w, bend + 0.018, z))
        back.append((L2, M2, R2))
    for i in range(n):
        a, b = front[i], front[i + 1]
        bm.faces.new((a[0], a[1], b[1], b[0]))
        bm.faces.new((a[1], a[2], b[2], b[1]))
        a, b = back[i], back[i + 1]
        bm.faces.new((a[1], a[0], b[0], b[1]))
        bm.faces.new((a[2], a[1], b[1], b[2]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def s_snow(bm):
    # six-armed snow crystal: arms with two pairs of barbs
    def bar(cx, cz, length, ang, wdt=0.05):
        c, sn = math.cos(ang), math.sin(ang)
        hl, hw = length / 2, wdt / 2
        pts = [(-hl, -hw), (hl, -hw), (hl + hw, 0), (hl, hw), (-hl, hw)]
        extrude_poly(bm, [(cx + x * c - z * sn, cz + x * sn + z * c) for x, z in pts], 0.05)
    for k in range(6):
        a = math.pi / 2 + k * math.pi / 3
        ca, sa = math.cos(a), math.sin(a)
        bar(ca * 0.25, sa * 0.25, 0.5, a)
        for t, ln in ((0.3, 0.2), (0.16, 0.14)):
            for sgn in (-1, 1):
                ba = a + sgn * math.radians(55)
                bar(ca * t + math.cos(ba) * ln / 2, sa * t + math.sin(ba) * ln / 2, ln, ba, 0.04)
    ico(bm, 0.07, 1)


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
    # disc with a raised rim and a shallow dish inside
    cyl(bm, 0.5, 0.5, 0.10, seg=24, mat_=Matrix.Rotation(math.pi / 2, 4, 'X'))
    cyl(bm, 0.5, 0.5, 0.15, seg=24, mat_=Matrix.Rotation(math.pi / 2, 4, 'X'), caps=False)
    cyl(bm, 0.36, 0.36, 0.14, seg=24, mat_=Matrix.Rotation(math.pi / 2, 4, 'X'))


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
    # ice crystal: hexagonal prism capped by two pyramids, flat-shaded facets
    cyl(bm, 0.2, 0.2, 0.34, seg=6, mat_=Matrix.Translation((0, 0, 0)) @ Matrix.Rotation(0, 4, 'X'), caps=False)
    cyl(bm, 0.2, 0.0, 0.3, seg=6, mat_=Matrix.Translation((0, 0, 0.32)), caps=False)
    cyl(bm, 0.2, 0.0, 0.3, seg=6, mat_=Matrix.Translation((0, 0, -0.32)) @ Matrix.Rotation(math.pi, 4, 'X'), caps=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-3)


def s_heart(bm):
    pts = []
    for i in range(28):
        t = 2 * math.pi * i / 28
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 34, z / 34 + 0.05))
    puffy_outline(bm, pts, 0.14, 0.12)


def s_impact(bm):
    # comic burst: 16 points of uneven length
    radii = [0.5, 0.20, 0.42, 0.19, 0.5, 0.22, 0.38, 0.18, 0.48, 0.21, 0.44, 0.2, 0.5, 0.19, 0.4, 0.22]
    pts = []
    for i in range(16):
        a = math.pi / 2 + i * math.pi / 8
        pts.append((math.cos(a) * radii[i], math.sin(a) * radii[i]))
    puffy_outline(bm, pts, 0.04, 0.03)


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
    teardrop(bm, 0.35, 1.54, cz=0.0, seg=12, rings=9, pow_=1.3)


def s_arrow(bm):
    # chevron arrow pointing up (+Z), for stat changes
    pts = [(-0.11, -0.5), (0.11, -0.5), (0.11, 0.02), (0.38, 0.02), (0.0, 0.5), (-0.38, 0.02), (-0.11, 0.02)]
    puffy_outline(bm, pts, 0.07, 0.06)


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
    ('claw', s_claw), ('fist', s_fist), ('drop', s_drop), ('arrow', s_arrow), ('poke_ball', s_pokeball),
]

# baked shading per shape (see paint()); shapes not listed use a soft radial gradient
_side = lambda co, n, f: 0.62 + 0.38 * (0.5 + 0.5 * (-n.y))


def _bubble_paint(co, n, f):
    # rim light: facing the camera (normal -Y) is dim, grazing edges bright, like a soap film
    return 0.5 + 0.5 * (1.0 - abs(n.y)) ** 1.5


PAINT = {
    'dot': paint_radial(0.6, 1.0, 0.5),
    'flame': paint_height(0.62, 1.0, -0.4, 0.9),
    'spark': paint_radial(0.7, 1.0, 0.56),
    'star': paint_radial(0.6, 1.0, 0.5),
    'ring': paint_radial(0.75, 1.0, 0.6, axis=1),
    'bubble': _bubble_paint,
    'leaf': lambda co, n, f: 0.7 + 0.3 * (0.5 + 0.5 * n.x * 2.0) if abs(co.x) > 0.002 else 1.0,
    'snow': paint_radial(0.75, 1.0, 0.5),
    'rock': paint_lit(0.5, 1.0),
    'note': paint_lit(0.65, 1.0),
    'z': paint_radial(0.7, 1.0, 0.45),
    'coin': lambda co, n, f: 1.0 if (math.hypot(co.x, co.z) > 0.42 or abs(n.y) < 0.6) else 0.72,
    'seed': paint_lit(0.55, 1.0),
    'needle': paint_radial(0.7, 1.0, 0.4, axis=0),
    'bone': paint_lit(0.72, 1.0),
    'egg': paint_lit(0.62, 1.0),
    'shard': paint_lit(0.55, 1.0),
    'heart': paint_radial(0.68, 1.0, 0.5),
    'impact': paint_radial(0.72, 1.0, 0.5),
    'claw': paint_radial(0.85, 1.0, 0.6),
    'fist': paint_lit(0.6, 1.0),
    'drop': paint_height(0.55, 1.0, -0.35, 0.6),
    'arrow': paint_height(0.6, 1.0, -0.5, 0.5),
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith('.glb'):
            os.remove(os.path.join(OUT_DIR, f))
    manifest = {'conventions': {'origin': 'centred', 'size': '~1 m nominal', 'front': 'Godot +Z',
                                'colour': 'tint applied per particle in Godot (BattleVfx.gd) x the baked COLOR_0 shading, except poke_ball'}, 'vfx': {}}
    for name, fn in SHAPES:
        reset()
        bm = bmesh.new()
        fn(bm)
        if name == 'poke_ball':
            mats = [mat('ball_top', '#e04848', rough=0.3), mat('ball_bottom', '#f4f4f4', rough=0.3),
                    mat('ball_band', '#1b1a2e', rough=0.6), mat('ball_button', '#f8f8f8', rough=0.2)]
        else:
            mats = [mat('vfx', '#ffffff', emit=1.0)]
        smooth = name in ('dot', 'bubble', 'egg', 'seed', 'flame', 'drop', 'poke_ball', 'fist', 'ring', 'leaf', 'heart', 'star', 'arrow')
        if name in PAINT:
            paint(bm, PAINT[name])
        ob = finish(bm, name, mats, smooth)
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        path = os.path.join(OUT_DIR, name + '.glb')
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True, export_animations=False,
                                  export_vertex_color='ACTIVE' if name in PAINT else 'MATERIAL')
        manifest['vfx'][name] = {'file': name + '.glb', 'tris': tris}
        print('vfx %-10s tris=%d' % (name, tris))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1)


if __name__ == '__main__':
    main()

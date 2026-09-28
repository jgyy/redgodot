"""Overworld 3D props generated from upstream's own sprite definitions (headless Blender).

  python3 pipeline/blender/gen_world.py          (pip bpy)   |   blender --background --python pipeline/blender/gen_world.py

Reads pipeline/blender/world_defs.json (written by pipeline/scripts/bake_maps.js from upstream's terrain.js:
the tree clump layouts for both tree kinds x 6 variants, evaluated with upstream's hash) and builds:

  godot/assets/models/world/tree_<kind><v>.glb   leafy canopy of lit clumps + trunk, vertex-coloured with the
                                                 exact PAL.leaf / PAL.leaf2 / PAL.trunk ramps

Units ("sprite units"): 1 = one map cell horizontally; vertically 1 = 16 px of 2D art (Godot scales Y by
K = tan(camera pitch) so the model projects onto its 2D sprite). Pivot = trunk base (the sprite's bottom
edge), front (toward the camera) = Blender -Y = Godot +Z.
Each canopy clump is an ellipsoid with radii (r, 0.707r, 0.707r) so that seen from the game camera it is the
round clump of the sprite, but it has real depth. Faces are flat-coloured by upstream's foliage() lighting
(L = [-0.55, -0.7, 0.45] in sprite space, ramp thresholds 0.62/0.4/0.15/-0.1, rim shadow at the clump bottom,
per-face speckle) so the canopy reads like the 2D pixel foliage.
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'world')


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def hash2(x, y, s):
    """upstream gfx.hash2 (32-bit integer hash)"""
    def i32(v):
        v &= 0xffffffff
        return v - (1 << 32) if v & 0x80000000 else v
    def imul(a, b):
        return i32((a & 0xffffffff) * (b & 0xffffffff))
    h = i32(imul(int(x), 374761393) + imul(int(y), 668265263) + i32(imul(int(s), 2147483647)))
    h = imul(h ^ ((h & 0xffffffff) >> 13), 1274126177)
    h = h ^ ((h & 0xffffffff) >> 16)
    return (h & 0xffffffff) / 4294967296.0


def new_mesh_obj(name):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def vcol_layer(bm):
    return bm.loops.layers.color.get('Col') or bm.loops.layers.color.new('Col')


def set_face_color(bm, f, rgb, layer):
    for loop in f.loops:
        loop[layer] = (rgb[0], rgb[1], rgb[2], 1.0)


def foliage_index(n_sprite, lit, speck, ramp_len, rim):
    """upstream terrain.js foliage(): n_sprite = (dx, dy, nz) in sprite space (x right, y down, z to viewer)"""
    L = (-0.55, -0.7, 0.45)
    I = n_sprite[0] * L[0] + n_sprite[1] * L[1] + n_sprite[2] * L[2]
    I = I * 0.9 + lit + speck
    if rim:
        return 1
    if I > 0.62:
        return ramp_len - 2
    if I > 0.4:
        return ramp_len - 3
    if I > 0.15:
        return ramp_len - 4
    if I > -0.1:
        return ramp_len - 5
    return 1


def build_tree(key, d, pal):
    ramp = [hex_rgb(c) for c in (pal['leaf2'] if d['kind'] == 'tree2' else pal['leaf'])]
    trunk = [hex_rgb(c) for c in pal['trunk']]
    seed = d['seed']
    rng = random.Random(1000 + seed)
    ob = new_mesh_obj(key)
    bm = bmesh.new()
    col = vcol_layer(bm)
    # ---- trunk: a slightly tapered box, 4px wide, lit from the left like the sprite
    tx0, ty0, tx1, ty1 = d['trunk']
    w = (tx1 - tx0) / 16.0
    h = (26 - ty0) / 16.0 + 0.1
    dep = 0.16
    x0, x1 = (tx0 - 8) / 16.0, (tx1 - 8) / 16.0
    verts = []
    for (z, sc) in ((0.0, 1.15), (h, 0.85)):
        cx = (x0 + x1) / 2
        for (xx, yy) in ((x0, -dep / 2), (x1, -dep / 2), (x1, dep / 2), (x0, dep / 2)):
            verts.append(bm.verts.new((cx + (xx - cx) * sc, yy * sc, z)))
    faces = [((0, 1, 5, 4), trunk[2]), ((1, 2, 6, 5), trunk[1]), ((2, 3, 7, 6), trunk[1]), ((3, 0, 4, 7), trunk[3])]
    for idx, c in faces:
        f = bm.faces.new([verts[i] for i in idx])
        set_face_color(bm, f, c, col)
    # ---- canopy clumps (back to front, like the sprite)
    clumps = sorted(d['clumps'], key=lambda c: c['y'])
    for ci, c in enumerate(clumps):
        r = c['r'] / 16.0
        cx = (c['x'] - 8) / 16.0
        cz = (26 - c['y']) / 16.0
        # lower clumps sit nearer the camera (they overlap the upper ones in the sprite)
        cy = -((c['y'] - 9.0) / 16.0) * 0.45
        sph = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        sv = sph['verts']
        for v in sv:
            n = v.co.normalized()
            jag = 1.0 + (hash2(int(n.x * 50 + 99), int(n.z * 50 + 99), seed + ci) - 0.5) * 0.22
            v.co = Vector((cx + n.x * r * jag, cy + n.y * r * 0.707 * jag, cz + n.z * r * 0.707 * jag))
        fs = {f for v in sv for f in v.link_faces}
        for f in fs:
            fc = f.calc_center_median()
            nd = Vector(((fc.x - cx) / r, (fc.y - cy) / (r * 0.707), (fc.z - cz) / (r * 0.707)))
            if nd.length > 0:
                nd.normalize()
            # sprite space: x right, y down (= -Blender z), z toward viewer (= -Blender y)
            ns = (nd.x, -nd.z, -nd.y)
            speck = (rng.random() - 0.5) * 0.18
            rim = nd.z < -0.62 and ns[2] > -0.2
            idx = foliage_index(ns, c.get('lit', 0.0), speck, len(ramp), rim)
            if idx == len(ramp) - 2 and rng.random() < 0.18:
                idx = len(ramp) - 1
            set_face_color(bm, f, ramp[max(0, min(len(ramp) - 1, idx))], col)
    bm.to_mesh(ob.data)
    bm.free()
    me = ob.data
    for a in list(me.color_attributes):
        if a.name != 'Col':
            me.color_attributes.remove(a)
    me.color_attributes.active_color = me.color_attributes['Col']
    mat = bpy.data.materials.new(key + '_mat')
    mat.use_nodes = True
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def export_static(path):
    C.ensure_dir(os.path.dirname(path))
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', check_existing=False, use_selection=False,
                              export_apply=True, export_yup=True, export_materials='EXPORT', export_animations=False,
                              export_vertex_color='NAME', export_vertex_color_name='Col', export_all_vertex_colors=False, export_normals=True)


def main():
    defs = json.load(open(os.path.join(HERE, 'world_defs.json')))
    pal = defs['pal']
    C.ensure_dir(OUT_DIR)
    manifest = {}
    for key, d in sorted(defs['trees'].items()):
        C.reset_scene()
        ob = build_tree(key, d, pal)
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        path = os.path.join(OUT_DIR, 'tree_%s.glb' % key)
        export_static(path)
        manifest['tree_%s' % key] = {'tris': tris, 'kind': d['kind'], 'variant': d['v']}
        print('[gen_world] %s: %d tris' % (path, tris))
    json.dump(manifest, open(os.path.join(OUT_DIR, 'manifest.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()

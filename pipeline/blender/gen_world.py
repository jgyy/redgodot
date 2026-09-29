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
import env_kit as K  # noqa: E402
import env_props as EP  # noqa: E402

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
    # ---- trunk: octagonal tapered stem with a root flare, bark stripes and two root buttresses,
    # lit from the left like the sprite (the sprite's trunk is 4 px wide)
    tx0, ty0, tx1, ty1 = d['trunk']
    h = (26 - ty0) / 16.0 + 0.12
    cxt = ((tx0 + tx1) / 2.0 - 8) / 16.0
    wr = (tx1 - tx0) / 16.0 * 0.5
    rings = [(0.0, wr * 1.55), (0.07, wr * 1.18), (0.22, wr * 1.0), (h, wr * 0.82)]
    nseg = 8
    rvs = []
    for (z, r) in rings:
        rv = []
        for k in range(nseg):
            a_ = 2 * math.pi * k / nseg + math.pi / 8
            rv.append(bm.verts.new((cxt + math.cos(a_) * r, math.sin(a_) * r * 0.8, z)))
        rvs.append(rv)
    for i in range(len(rvs) - 1):
        for k in range(nseg):
            k2 = (k + 1) % nseg
            f = bm.faces.new((rvs[i][k], rvs[i][k2], rvs[i + 1][k2], rvs[i + 1][k]))
            f.normal_update()
            nrm = f.normal
            lit = -nrm.x * 0.55 - nrm.y * 0.45 + nrm.z * 0.3
            ti = 3 if lit > 0.55 else 2 if lit > 0.15 else 1 if lit > -0.35 else 0
            if (k + i) % 3 == 0 and ti > 0:
                ti -= 1                                  # dark bark furrow
            if i == 0:
                ti = max(0, ti - 1)                      # shadowed root flare
            set_face_color(bm, f, trunk[ti], col)
    for (ang, ln) in ((-0.6, 0.20), (0.75, 0.17)):        # root buttresses
        bx, by = cxt + math.cos(ang) * wr * 1.3, math.sin(ang) * wr * 1.0 - 0.02
        tip = bm.verts.new((bx + math.cos(ang) * ln, by + math.sin(ang) * ln * 0.6, 0.0))
        v1 = bm.verts.new((bx - math.sin(ang) * wr * 0.5, by + math.cos(ang) * wr * 0.4, 0.0))
        v2 = bm.verts.new((bx + math.sin(ang) * wr * 0.5, by - math.cos(ang) * wr * 0.4, 0.0))
        top = bm.verts.new((bx, by, 0.11))
        for tri, ti in (((v1, v2, top), 1), ((tip, v1, top), 2), ((v2, tip, top), 0)):
            try:
                f = bm.faces.new(tri)
                f.normal_update()
                if f.normal.z < -0.9:
                    f.normal_flip()
                set_face_color(bm, f, trunk[ti], col)
            except ValueError:
                pass
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
        if c['r'] >= 3.9:
            # a sunlit leaf tuft on the upper-left shoulder of each large clump (breaks the round silhouette)
            tr = r * 0.46
            tcx, tcz = cx - r * 0.55, cz + r * 0.5 * 0.707
            tcy = cy - r * 0.18
            sph = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            for v in sph['verts']:
                nn = v.co.normalized()
                jag = 1.0 + (hash2(int(nn.x * 50 + 99), int(nn.z * 50 + 99), seed + ci + 40) - 0.5) * 0.3
                v.co = Vector((tcx + nn.x * tr * jag, tcy + nn.y * tr * 0.707 * jag, tcz + nn.z * tr * 0.707 * jag))
            for f in {f for v in sph['verts'] for f in v.link_faces}:
                fc = f.calc_center_median()
                nd = Vector(((fc.x - tcx) / tr, (fc.y - tcy) / (tr * 0.707), (fc.z - tcz) / (tr * 0.707)))
                if nd.length > 0:
                    nd.normalize()
                ns = (nd.x, -nd.z, -nd.y)
                idx = foliage_index(ns, 0.18, (rng.random() - 0.5) * 0.12, len(ramp), nd.z < -0.6)
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


def finish_mesh(ob, bm):
    bm.to_mesh(ob.data)
    bm.free()
    me = ob.data
    for a in list(me.color_attributes):
        if a.name != 'Col':
            me.color_attributes.remove(a)
    mat = bpy.data.materials.new(ob.name + '_mat')
    mat.use_nodes = True
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = False


def ellipsoid(bm, center, rx, ry, rz, subdiv=2, jag=0.0, seed=0):
    sph = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    sv = sph['verts']
    for v in sv:
        n = v.co.normalized()
        j = 1.0 + (hash2(int(n.x * 50 + 99), int(n.z * 50 + 99), seed) - 0.5) * jag
        v.co = Vector((center[0] + n.x * rx * j, center[1] + n.y * ry * j, center[2] + n.z * rz * j))
    return {f for v in sv for f in v.link_faces}


def build_pokeball():
    """Item ball (objsprites.js ART.ball): 10px across, red top with a highlight, black band, white bottom."""
    P = {'O': '#1b1a2e', 'R': '#e04848', 'r': '#a82838', 'L': '#ff9a8a', 'W': '#f8f8f8', 'w': '#c8c8d8'}
    c = {k: hex_rgb(v) for k, v in P.items()}
    ob = new_mesh_obj('pokeball')
    bm = bmesh.new()
    col = vcol_layer(bm)
    r = 5.0 / 16.0
    cz = 4.5 / 16.0
    fs = ellipsoid(bm, (0.0, 0.0, cz), r, r * 0.8, r * 0.8, subdiv=3)
    for f in fs:
        m = f.calc_center_median()
        n = Vector(((m.x) / r, (m.y) / (r * 0.8), (m.z - cz) / (r * 0.8))).normalized()
        front = n.y < -0.86 and abs(n.z) < 0.4 and abs(n.x) < 0.4
        if front and n.y < -0.95:
            k = 'W'
        elif front:
            k = 'O'
        elif abs(n.z) < 0.13:
            k = 'O'
        elif n.z > 0:
            lit = -n.x * 0.55 + n.z * 0.7 - n.y * 0.45
            k = 'L' if lit > 0.85 else ('r' if lit < 0.1 else 'R')
        else:
            lit = -n.x * 0.55 - n.y * 0.45
            k = 'W' if lit > -0.1 else 'w'
        set_face_color(bm, f, c[k], col)
    finish_mesh(ob, bm)
    return ob


def build_boulder():
    """Strength boulder (objsprites.js ART.boulder): a lumpy rock lit from the top-left, A (light) .. E (dark)."""
    ramp = [hex_rgb(h) for h in ['#56463c', '#786454', '#a08c78', '#c8b8a4', '#e8dccc']]
    ob = new_mesh_obj('boulder')
    bm = bmesh.new()
    col = vcol_layer(bm)
    r = 7.5 / 16.0
    cz = 6.5 / 16.0
    rng = random.Random(7)
    fs = ellipsoid(bm, (0.0, 0.0, cz), r, r * 0.72, r * 0.72, subdiv=2, jag=0.25, seed=41)
    for f in fs:
        m = f.calc_center_median()
        n = f.normal
        lit = -n.x * 0.55 + n.z * 0.7 - n.y * 0.45 + (rng.random() - 0.5) * 0.2
        idx = 4 if lit > 0.75 else 3 if lit > 0.4 else 2 if lit > 0.0 else 1 if lit > -0.4 else 0
        set_face_color(bm, f, ramp[idx], col)
    finish_mesh(ob, bm)
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
    for name in EP.GAME:
        fn, note = EP.PROPS[name]
        K.reset()
        P = fn('vcol')
        tris = P.tri_count()
        P.to_object()
        path = os.path.join(OUT_DIR, '%s.glb' % name)
        size = K.export(path)
        manifest[name] = {'tris': tris, 'bytes': size, 'notes': note}
        print('[gen_world] %s: %d tris' % (path, tris))
    json.dump(manifest, open(os.path.join(OUT_DIR, 'manifest.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()

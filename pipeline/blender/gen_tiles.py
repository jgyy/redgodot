"""Low-poly overworld tile kit: 1x1 m footprint, pivot at bottom centre, front = -Y (Godot +Z).

  blender --background --python pipeline/blender/gen_tiles.py
Colours are taken from the original game's palette ramps (src/art/palette.js).
Output: godot/assets/models/tiles/<name>.glb + manifest.json
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Vector, Matrix, noise  # noqa: E402
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'tiles')

PAL = {  # from palette.js ramps
    'grass': ['#2f7a3a', '#48a043', '#6cbf4c'],
    'tallgrass': ['#26703a', '#389040', '#58b04a', '#86cf58'],
    'path': ['#b58c5c', '#cfa874', '#e2c28e'],
    'pave': ['#81849c', '#a3a6bb', '#c2c4d3'],
    'water': ['#2552ad', '#3176d0', '#4d9be6'],
    'leaf': ['#2a723a', '#3c9142', '#5bb04d'],
    'trunk': ['#6a3f2e', '#8e5a3a'],
    'stone': ['#5a5c74', '#7b7e95', '#9da0b4'],
    'cream': ['#ded0b8', '#f0e6d2'],
    'brick': ['#94463a', '#b35f47'],
    'roof_red': ['#8f2a2c', '#bb4034'],
    'wood': ['#744630', '#9a6340', '#bd8554'],
    'gold': ['#f4d046'],
}


def grid(mb, mat_ids, gname, n=4, z=0.0, seed=1, size=1.0):
    rnd = random.Random(seed)
    res = bmesh.ops.create_grid(mb.bm, x_segments=n, y_segments=n, size=size * 0.5,
                                matrix=Matrix.Translation((0, 0, z)))
    faces = {f for v in res['verts'] for f in v.link_faces}
    for f in faces:
        f.material_index = rnd.choice(mat_ids)
        f.smooth = False
    for v in res['verts']:
        v[mb.grp] = mb.group_index(gname)
    return faces


def slab(mb, mats, ramp, seed, n=4, z=0.0, **kw):
    ids = [mats.get(h, **kw) for h in ramp]
    grid(mb, ids, 'tile', n=n, z=z, seed=seed)


def t_floor_grass(mb, m):
    slab(mb, m, PAL['grass'], 3, roughness=0.9, specular=0.2)


def t_floor_path(mb, m):
    slab(mb, m, PAL['path'], 5, roughness=0.95, specular=0.15)


def t_floor_pave(mb, m):
    slab(mb, m, PAL['pave'], 7, n=2, roughness=0.8)


def t_water(mb, m):
    ids = [m.get(h, roughness=0.08, specular=0.8, emission='#4d9be6', emission_strength=0.25)
           for h in PAL['water']]
    grid(mb, ids, 'tile', n=4, z=-0.05, seed=9)


def t_tallgrass(mb, m):
    slab(mb, m, PAL['grass'][:2], 11, n=2, roughness=0.9)
    rnd = random.Random(42)
    ids = [m.get(h, roughness=0.8) for h in PAL['tallgrass']]
    for i in range(16):
        bx, by = rnd.uniform(-0.42, 0.42), rnd.uniform(-0.42, 0.42)
        h = rnd.uniform(0.28, 0.45)
        lean = Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0))
        pts = [Vector((bx, by, 0)), Vector((bx, by, h * 0.55)) + lean * 0.4, Vector((bx, by, h)) + lean]
        mb.tube(pts, [0.03, 0.018, 0.002], rnd.choice(ids), 'tile', nseg=3, caps=False, smooth=False)


def t_tree(mb, m):
    mb.tube([(0, 0, 0), (0, 0, 1.0)], [0.14, 0.11], m.get(PAL['trunk'][0], roughness=0.9), 'tile', nseg=8)
    leaves = [m.get(h, roughness=0.8) for h in PAL['leaf']]
    mb.ellipsoid((0, 0, 1.55), (0.62, 0.6, 0.62), leaves[1], 'tile', segs=(12, 8))
    mb.ellipsoid((0.08, -0.1, 2.05), (0.42, 0.42, 0.45), leaves[2], 'tile', segs=(10, 7))
    mb.ellipsoid((-0.22, 0.15, 1.35), (0.42, 0.4, 0.4), leaves[0], 'tile', segs=(10, 7))


def t_wall(mb, m):
    mb.box((-0.5, -0.5, 0), (0.5, 0.5, 1.0), m.get(PAL['stone'][1], roughness=0.85), 'tile')
    mb.box((-0.52, -0.52, 0.94), (0.52, 0.52, 1.02), m.get(PAL['stone'][2], roughness=0.85), 'tile')


def t_building_wall(mb, m):
    mb.box((-0.5, -0.5, 0.2), (0.5, 0.5, 1.2), m.get(PAL['cream'][0], roughness=0.8), 'tile')
    mb.box((-0.5, -0.5, 0.0), (0.5, 0.5, 0.2), m.get(PAL['brick'][1], roughness=0.85), 'tile')


def t_roof(mb, m):
    mb.plate([(-0.5, 0.0), (0.5, 0.0), (0.0, 0.6)], 0.0, 1.0, m.get(PAL['roof_red'][1], roughness=0.7),
             'tile', target_edge=10, bulge=False)
    for f in mb.bm.faces:
        f.smooth = False


def t_door(mb, m):
    mb.box((-0.5, -0.45, 0), (0.5, 0.5, 1.0), m.get(PAL['cream'][0], roughness=0.8), 'tile')
    mb.box((-0.3, -0.5, 0), (0.3, -0.44, 0.85), m.get(PAL['wood'][1], roughness=0.7), 'tile')
    mb.ellipsoid((0.2, -0.52, 0.42), (0.035, 0.03, 0.035), m.get(PAL['gold'][0], roughness=0.3, metallic=0.8),
                 'tile', segs=(8, 6))


def t_counter(mb, m):
    mb.box((-0.5, -0.3, 0), (0.5, 0.3, 0.85), m.get(PAL['wood'][1], roughness=0.7), 'tile')
    mb.box((-0.5, -0.36, 0.85), (0.5, 0.34, 0.92), m.get(PAL['wood'][2], roughness=0.5), 'tile')


def t_sign(mb, m):
    mb.tube([(0, 0, 0), (0, 0, 0.9)], [0.045, 0.04], m.get(PAL['wood'][0], roughness=0.8), 'tile', nseg=6)
    mb.box((-0.35, -0.08, 0.55), (0.35, -0.02, 0.95), m.get(PAL['wood'][2], roughness=0.7), 'tile')


def t_ledge(mb, m):
    mb.box((-0.5, -0.5, 0), (0.5, 0.5, 0.25), m.get(PAL['path'][0], roughness=0.9), 'tile')
    grid(mb, [m.get(PAL['grass'][1], roughness=0.9)], 'tile', n=1, z=0.251)
    mb.tube([(-0.5, -0.46, 0.25), (0.5, -0.46, 0.25)], [0.07, 0.07], m.get(PAL['grass'][0], roughness=0.9),
            'tile', nseg=8)


def t_rock(mb, m):
    res = bmesh.ops.create_icosphere(mb.bm, subdivisions=2, radius=0.4)
    for v in res['verts']:
        n = noise.noise(v.co * 4.0 + Vector((1.3, 2.1, 0.7)))
        v.co *= 1.0 + 0.22 * n
        v.co.z = max(0.0, v.co.z * 0.8 + 0.24)
    mid = m.get(PAL['stone'][1], roughness=0.9)
    faces = {f for v in res['verts'] for f in v.link_faces}
    for f in faces:
        f.material_index = mid
        f.smooth = False
    for v in res['verts']:
        v[mb.grp] = mb.group_index('tile')


TILES = [
    ('floor_grass', t_floor_grass, 'walkable ground'),
    ('floor_path', t_floor_path, 'walkable ground'),
    ('floor_pave', t_floor_pave, 'walkable ground (town)'),
    ('tallgrass', t_tallgrass, 'walkable, wild encounters'),
    ('water', t_water, 'blocking unless surfing; top at -0.05 m'),
    ('tree', t_tree, 'blocking, ~2.5 m'),
    ('wall', t_wall, 'blocking 1 m cube'),
    ('building_wall', t_building_wall, 'blocking 1.2 m'),
    ('roof', t_roof, 'prism, ridge along X, 0.6 m tall; stack on building_wall'),
    ('door', t_door, 'warp tile, door panel on the -Y (Godot +Z) face'),
    ('counter', t_counter, 'blocking, waist height, interact across'),
    ('sign', t_sign, 'blocking, interactable'),
    ('ledge', t_ledge, 'one-way jump-down; lip on the -Y (Godot +Z) edge'),
    ('rock', t_rock, 'blocking boulder'),
]


def main():
    C.ensure_dir(OUT_DIR)
    manifest = {'tiles': {}, 'conventions': {
        'footprint': '1 x 1 m, pivot at bottom centre', 'front': 'Blender -Y == glTF/Godot +Z',
        'palette': 'colours from src/art/palette.js ramps'}}
    for name, fn, note in TILES:
        C.reset_scene()
        mats = C.MaterialCache('tile_' + name)
        mb = C.MeshBuilder()
        fn(mb, mats)
        mb.finish()
        obj = mb.to_object(name, mats.mats, with_vgroups=False)
        tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
        path = os.path.join(OUT_DIR, name + '.glb')
        C.export_glb(path, animations=False)
        manifest['tiles'][name] = {'file': name + '.glb', 'tris': tris, 'bytes': os.path.getsize(path), 'notes': note}
        print('tile %-14s tris=%d' % (name, tris))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1)
    print('DONE tiles=%d' % len(TILES))


if __name__ == '__main__':
    main()

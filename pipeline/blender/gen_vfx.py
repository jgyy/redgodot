"""Tiny particle meshes for battle VFX (use as GPUParticles3D draw passes). Centered at origin,
roughly 0.1-0.3 m, no animation.

  blender --background --python pipeline/blender/gen_vfx.py
Output: godot/assets/models/vfx/<name>.glb + manifest.json
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Vector, Matrix, noise  # noqa: E402
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'vfx')


def _tag(mb, verts, mi, smooth):
    gi = mb.group_index('vfx')
    for v in verts:
        v[mb.grp] = gi
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mi
        f.smooth = smooth


def teardrop(mb, mi, r, h, smooth=True):
    """Round bottom, pointed top, centred on origin."""
    res = bmesh.ops.create_uvsphere(mb.bm, u_segments=12, v_segments=9, radius=1.0)
    for v in res['verts']:
        z = v.co.z
        if z > 0:
            k = (1 - z) ** 1.3
            v.co.x *= k
            v.co.y *= k
            v.co.z = z * (h / r - 1)
        v.co *= r
        v.co.z -= (h - 2 * r) * 0.5
    _tag(mb, res['verts'], mi, smooth)


def v_spark(mb, m):
    res = bmesh.ops.create_uvsphere(mb.bm, u_segments=4, v_segments=2, radius=1.0)
    for v in res['verts']:
        v.co = Vector((v.co.x * 0.03, v.co.y * 0.03, v.co.z * 0.11))
    _tag(mb, res['verts'], m.get('#fff08a', roughness=0.3, emission='#f4d046', emission_strength=3.0), False)


def v_flame_blob(mb, m):
    teardrop(mb, m.get('#f09058', roughness=0.6, emission='#e0792c', emission_strength=2.5), 0.06, 0.2)


def v_water_droplet(mb, m):
    teardrop(mb, m.get('#7fc3f3', roughness=0.05, specular=0.9, alpha=0.8), 0.05, 0.14)


def v_leaf_bit(mb, m):
    pts = [(math.sin(a) * 0.045 * (1 - abs(math.cos(a)) ** 3), -math.cos(a) * 0.09)
           for a in [2 * math.pi * i / 12 for i in range(12)]]
    mb.plate(pts, 0.0, 0.01, m.get('#5bb04d', roughness=0.7), 'vfx', target_edge=1.0)


def v_rock_chunk(mb, m):
    res = bmesh.ops.create_icosphere(mb.bm, subdivisions=1, radius=0.06)
    for v in res['verts']:
        v.co *= 1.0 + 0.3 * noise.noise(v.co * 30.0 + Vector((0.3, 0.9, 1.7)))
    _tag(mb, res['verts'], m.get('#8f6c50', roughness=0.95), False)


def v_ice_shard(mb, m):
    mi = m.get('#bde6ff', roughness=0.1, specular=0.9, emission='#86b6f0', emission_strength=0.6, alpha=0.85)
    top = bmesh.ops.create_cone(mb.bm, cap_ends=False, segments=6, radius1=0.035, radius2=0.0, depth=0.12,
                                matrix=Matrix.Translation((0, 0, 0.06 - 0.035)))
    bot = bmesh.ops.create_cone(mb.bm, cap_ends=False, segments=6, radius1=0.035, radius2=0.0, depth=0.05,
                                matrix=Matrix.Translation((0, 0, -0.025 - 0.035)) @ Matrix.Rotation(math.pi, 4, 'X'))
    _tag(mb, top['verts'] + bot['verts'], mi, False)
    bmesh.ops.remove_doubles(mb.bm, verts=mb.bm.verts[:], dist=1e-4)


def v_poison_bubble(mb, m):
    mb.ellipsoid((0, 0, 0), (0.06, 0.06, 0.06), m.get('#9163c2', roughness=0.1, specular=0.8, alpha=0.55,
                                                       emission='#b58ddb', emission_strength=0.4), 'vfx', segs=(14, 9))


def v_status_ring(mb, m):
    R, r, nu, nv = 0.15, 0.012, 32, 6
    bm = mb.bm
    rings = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        c, d = Vector((math.cos(a), math.sin(a), 0)), Vector((0, 0, 1))
        rings.append([bm.verts.new(c * (R + r * math.cos(2 * math.pi * j / nv)) + d * r * math.sin(2 * math.pi * j / nv))
                      for j in range(nv)])
    for i in range(nu):
        A, B = rings[i], rings[(i + 1) % nu]
        for j in range(nv):
            bm.faces.new((A[j], B[j], B[(j + 1) % nv], A[(j + 1) % nv]))
    _tag(mb, [v for rr in rings for v in rr], m.get('#ffffff', roughness=0.4, emission='#ffffff',
                                                    emission_strength=1.5), True)


def v_impact_star(mb, m):
    pts = []
    for i in range(10):
        a = math.pi / 2 + 2 * math.pi * i / 10
        rr = 0.12 if i % 2 == 0 else 0.05
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    mb.plate(pts, 0.0, 0.015, m.get('#fff08a', roughness=0.4, emission='#f4d046', emission_strength=2.0),
             'vfx', target_edge=10, bulge=False)


VFX = [
    ('spark', v_spark, 'emissive yellow octahedral shard (electric)'),
    ('flame_blob', v_flame_blob, 'emissive orange teardrop, point up (+Y in Godot)'),
    ('water_droplet', v_water_droplet, 'translucent blue teardrop'),
    ('leaf_bit', v_leaf_bit, 'thin leaf plate in the XY plane (Godot)'),
    ('rock_chunk', v_rock_chunk, 'faceted brown chunk'),
    ('ice_shard', v_ice_shard, 'translucent hexagonal bipyramid crystal'),
    ('poison_bubble', v_poison_bubble, 'translucent purple sphere (alpha blend)'),
    ('status_ring', v_status_ring, 'flat emissive torus in the ground plane, r=0.15 m; tint via material override'),
    ('impact_star', v_impact_star, 'flat 5-point emissive star facing the camera (Godot +Z)'),
]


def main():
    C.ensure_dir(OUT_DIR)
    manifest = {'vfx': {}, 'conventions': {'origin': 'centred', 'scale': '~0.1-0.3 m; scale via particle params',
                                           'front': 'Blender -Y == glTF/Godot +Z', 'animation': 'none'}}
    for name, fn, note in VFX:
        C.reset_scene()
        mats = C.MaterialCache('vfx_' + name)
        mb = C.MeshBuilder()
        fn(mb, mats)
        mb.finish()
        obj = mb.to_object(name, mats.mats, with_vgroups=False)
        tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
        path = os.path.join(OUT_DIR, name + '.glb')
        C.export_glb(path, animations=False)
        manifest['vfx'][name] = {'file': name + '.glb', 'tris': tris, 'bytes': os.path.getsize(path), 'notes': note}
        print('vfx %-14s tris=%d' % (name, tris))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1)
    print('DONE vfx=%d' % len(VFX))


if __name__ == '__main__':
    main()

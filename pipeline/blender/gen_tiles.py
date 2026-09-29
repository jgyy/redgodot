"""Overworld tile + prop kit: 1x1 m footprint (sprite units), pivot at bottom centre, front = -Y (Godot +Z).

  python3 pipeline/blender/env_textures.py        # (re)paint the seamless textures once
  python3 pipeline/blender/gen_tiles.py           # or:  blender --background --python pipeline/blender/gen_tiles.py

Every piece is built by pipeline/blender/env_tiles.py / env_props.py with bevelled edges, layered silhouettes and
baked vertex-colour AO, textured with the procedural seamless PBR-less textures of env_textures.py (colours from
upstream's palette ramps).  Output: godot/assets/models/tiles/<name>.glb + manifest.json.  The in-game overworld is
drawn from upstream's baked pixel art (godot/assets/maps) with the vertex-colour twins of the props in
godot/assets/models/world (gen_world.py); this kit is the textured, reusable modular set.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402,F401
import env_kit as K  # noqa: E402
import env_props as EP  # noqa: E402
import env_textures as ET  # noqa: E402
import env_tiles as TL  # noqa: E402
import env_buildings as EBL  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'tiles')

# in-game prop twins that are also part of the textured kit (same geometry, 'tex' style)
KIT_PROPS = ['bed', 'sign', 'fence_x', 'fence_post', 'plant', 'barrel', 'crate', 'grave_a', 'grave_b', 'brazier', 'bush', 'statue',
             'flower_red', 'flower_yellow', 'flower_white', 'flower_pink', 'pokeball', 'rail_x', 'rail_z', 'rail_post']


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ET.build_textures()
    ET.build_detail_atlas()
    manifest = {'tiles': {}, 'props': {}, 'conventions': {
        'footprint': '1 x 1 m, pivot at bottom centre', 'front': 'Blender -Y == glTF/Godot +Z',
        'palette': 'colours from src/art/palette.js ramps (env_textures.PAL)',
        'textures': 'pipeline/data/env_tex/*.png, embedded'}}
    jobs = [(n, fn, note, 'tiles') for n, fn, note in TL.TILES]
    jobs += [(n, fn, note, 'props') for n, fn, note in TL.PROPS_EXTRA]
    jobs += [(n, EP.PROPS[n][0], EP.PROPS[n][1], 'props') for n in KIT_PROPS]
    jobs += [(n, (lambda style, f=f: f()), 'building part (neutral grey in the kit; tinted per building in game)', 'props') for n, f in EBL.PARTS.items()]
    for name, fn, note, group in jobs:
        K.reset()
        P = fn('tex')
        P.name = name
        tris = P.tri_count()
        P.to_object()
        path = os.path.join(OUT_DIR, name + '.glb')
        size = K.export(path)
        manifest[group][name] = {'file': name + '.glb', 'tris': tris, 'bytes': size, 'notes': note}
        print('kit %-14s tris=%4d bytes=%d' % (name, tris, size))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1)
    print('DONE tiles=%d props=%d' % (len(manifest['tiles']), len(manifest['props'])))


if __name__ == '__main__':
    main()

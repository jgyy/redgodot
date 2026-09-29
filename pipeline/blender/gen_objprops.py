"""Ground-item props + emote bubbles as 3D glbs (headless Blender).

  python3 pipeline/blender/gen_objprops.py
Writes godot/assets/models/world/{fossil,old_amber,pokedex,clipboard,paper,emote_*}.glb (env_props_items.ITEM_PROPS).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_kit as K  # noqa: E402
import env_props_items as EI  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'world')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (fn, note) in EI.ITEM_PROPS.items():
        K.reset()
        P = fn('vcol')
        tris = P.tri_count()
        P.to_object()
        size = K.export(os.path.join(OUT_DIR, '%s.glb' % name))
        print('[gen_objprops] %-15s %5d tris %7d bytes  %s' % (name, tris, size, note))


if __name__ == '__main__':
    main()

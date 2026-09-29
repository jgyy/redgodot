"""Chibi 3D trainers / NPCs for every humanoid in upstream's cast (src/data/cast.js).

  python3 pipeline/blender/gen_characters.py [--only red,oak] [--no-humanoid] [--preview out.png]

Design pipeline (all procedural, informed by how the characters look in Pokemon Red/Blue/
FireRed and the anime/manga -- see pipeline/data/character_looks.json):

  cast.json (palette, head/body template)  +  character_looks.json (hair, face, outfit, extras)
        -> char_build.py   assembles numpy parts: head/face (char_body), hair (char_hair),
                           clothing (char_outfit), accessories + hats (char_extras)
        -> char_paint.py   one procedural texture atlas per character (ramp cells: AO x gradient,
                           detail cells: eyes / cheeks / emblems)
        -> char_asm.py     baked AO, smooth <=4-influence skin weights, armature (char_rig.py),
                           actions (char_anim.py) and the .glb export

Output: godot/assets/models/characters/<sprite>.glb (+ humanoid.glb legacy base, manifest.json).
Conventions: front = Blender -Y (glTF/Godot +Z), feet at the origin, 1.5 m nominal height,
bones root > hips > spine > chest > neck > head (+ arms, legs, eyes, mouth, hair chains),
one material `mat_atlas`.  Clips (60 fps): Idle Walk Run Talk Wave Cheer + 13 gestures (Nod Shake Think Laugh Bow Point Sleep Surprised Salute Stretch Dance Sad Shiver).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXTRACTED = os.path.join(ROOT, 'pipeline', 'extracted')
DATA = os.path.join(ROOT, 'pipeline', 'data')
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'characters')

# sprite keys that aren't humanoids (creatures / objects) are left to other models;
# story sprites without their own cast entry fall back to these archetypes
ALIASES = {'gambler_asleep': 'gambler'}


def load_looks():
    with open(os.path.join(DATA, 'character_looks.json')) as fh:
        return json.load(fh)


def main():
    import char_build as CB
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    preview = args[args.index('--preview') + 1] if '--preview' in args else None
    os.makedirs(OUT_DIR, exist_ok=True)
    cast = json.load(open(os.path.join(EXTRACTED, 'cast.json')))['cast']
    looks = load_looks().get('characters', {})
    t0 = time.time()
    sprites = {}
    previews = []
    tmp = os.environ.get('TMPDIR', '/tmp')
    for key, d in cast.items():
        if d.get('creature') or d.get('object'):
            continue
        if only and key not in only:
            continue
        if key in ALIASES:
            continue
        look = CB.resolve_look(key, d, looks)
        ctx = CB.build(key, d, look)
        if preview:
            import char_preview as PV
            previews.append((key, ctx))
            print('%-20s verts=%5d' % (key, sum(len(p.V) for p in ctx.parts)), flush=True)
            continue
        import char_asm as AS
        info = AS.build_and_export(ctx, os.path.join(OUT_DIR, key + '.glb'), tmp_dir=tmp, log=print)
        info.update({'file': key + '.glb', 'head': d.get('head') or 'short', 'body': d.get('body') or 'normal'})
        sprites[key] = {k: info[k] for k in ('file', 'tris', 'bytes', 'head', 'body', 'verts', 'bones')}
        print('%-20s verts=%5d tris=%5d %4dKB %.1fs' % (key, info['verts'], info['tris'], info['bytes'] // 1024, info['seconds']), flush=True)
    if preview:
        import char_preview as PV
        from PIL import Image
        rows = []
        for key, ctx in previews:
            tiles = [PV.render_view([(p.V, p.F, PV.part_colors(ctx.atlas, p), __import__('char_geo').vertex_normals(p.V, p.F)) for p in ctx.parts
                                     if len(p.V)], 300, yaw=y) for y in (0, 90, 180)]
            rows.append(np.hstack(tiles))
        Image.fromarray((np.vstack(rows) * 255).astype(np.uint8)).save(preview)
        print('preview ->', preview)
        return
    if only is None:
        humanoid_info = None
        if '--no-humanoid' not in args:
            import humanoid_legacy
            humanoid_info = humanoid_legacy.build_humanoid([])
        manifest = {
            'sprites': sprites,
            'aliases': ALIASES,
            'humanoid': humanoid_info,
            'height_m': 1.5,
            'animations': {
                'Idle': {'seconds': 1.6, 'loop': True},
                'Walk': {'seconds': 0.2667, 'loop': True, 'note': 'one full 2-step gait per 16-frame cell (feet plant at walk speed)'},
                'Run': {'seconds': 0.2667, 'loop': True},
                'Talk': {'seconds': 1.2, 'loop': True}, 'Wave': {'seconds': 0.8, 'loop': True},
                'Cheer': {'seconds': 0.6667, 'loop': True},
                **{n: {'loop': n not in ('Bow', 'Surprised'), 'note': 'NPC gesture'} for n in
                   ('Nod', 'Shake', 'Think', 'Laugh', 'Bow', 'Point', 'Sleep', 'Surprised', 'Salute', 'Stretch', 'Dance', 'Sad', 'Shiver')}},
            'conventions': {'front': 'Blender -Y == glTF/Godot +Z', 'origin': 'feet at origin',
                            'materials': 'single mat_atlas (procedural atlas: AO x gradient ramps + eye/cheek/emblem decals); cel-shade with Toon.apply',
                            'bones': 'root > hips > spine > chest > neck > head; chest > clavicle_X > upper_arm_X > forearm_X > hand_X; '
                                     'hips > thigh_X > shin_X > foot_X; head > eye_L/eye_R (blink = scale z), mouth (talk = scale z); '
                                     'optional hair_tail*/hair_back*/hair_twin*/cape*/scarf*/band_* chains'},
            'source': 'pipeline/extracted/cast.json palettes + pipeline/data/character_looks.json designs',
            'elapsed_seconds': round(time.time() - t0, 1),
        }
        with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=1)
    print('DONE characters=%d in %.1fs' % (len(sprites), time.time() - t0))


if __name__ == '__main__':
    main()

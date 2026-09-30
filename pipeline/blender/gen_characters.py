"""Realistic 3D trainers / NPCs for every humanoid in upstream's cast (src/data/cast.js).

  python3 pipeline/blender/gen_characters.py [--only red,oak] [--jobs 4] [--no-humanoid]

Pipeline (procedural, numpy + headless Blender; designs in pipeline/data/character_looks.json):

  build params (height, width, age, sex ...)                 char_rig.Prop        proportions + landmark heights
        -> ONE implicit body: head, face, neck, torso, limbs, hands with fingers, feet   char_anat / char_sdf
        -> marching cubes, graded vertex clustering, projection back onto the field     char_mesh   (welded, no seams)
        -> skin weights from the anatomy primitives that own each vertex               char_skin
        -> face details on the sculpted skin: painted eyes + rotating eyelids, brows, lips        char_face / char_eye
        -> hair (scalp cap + soft locks / curtains / tails), hats, glasses, facial hair  char_hair / char_extras
        -> clothing as offset shells cut from the body (no clipping by construction)  char_outfit / char_shell
        -> one procedural texture atlas, baked AO, skinned + animated .glb              char_paint / char_asm / char_anim
        -> automated clipping test over all 19 clips                                   char_clip

Output: godot/assets/models/characters/<sprite>.glb (+ humanoid.glb legacy fallback, manifest.json).
Conventions: front = Blender -Y (glTF/Godot +Z), feet at the origin, 1.5 m nominal height (a standard adult is ~7 heads),
bones root > hips > spine > chest > neck > head (+ arms, legs, eyes, mouth, hair chains), one material `mat_atlas`.
Clips (60 fps): Idle Walk Run Talk Wave Cheer + 13 gestures (Nod Shake Think Laugh Bow Point Sleep Surprised Salute Stretch Dance Sad Shiver).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

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


def sprite_keys(cast, only=None):
    return [k for k, d in cast.items() if not (d.get('creature') or d.get('object')) and k not in ALIASES and (not only or k in only)]


def build_one(key, d, looks, tmp):
    import char_build as CB
    import char_asm as AS
    look = CB.resolve_look(key, d, looks)
    ctx = CB.build(key, d, look)
    # Godot extracts the glb's embedded atlas to <key>_<key>_atlas.png on import and never overwrites it, so a stale
    # extraction would texture the new mesh with the old atlas: drop it, the next import writes a fresh one
    for stale in ('_%s_atlas.png' % key, '_%s_atlas.png.import' % key):
        p_ = os.path.join(OUT_DIR, key + stale)
        if os.path.exists(p_):
            os.remove(p_)
    info = AS.build_and_export(ctx, os.path.join(OUT_DIR, key + '.glb'), tmp_dir=tmp, log=print)
    info.update({'file': key + '.glb', 'head': d.get('head') or 'short', 'body': d.get('body') or 'normal'})
    return {k: info[k] for k in ('file', 'tris', 'bytes', 'head', 'body', 'verts', 'bones')}


def build_humanoid(looks, tmp):
    """humanoid.glb: the neutral mannequin CharacterSkin falls back to for a sprite key without its own model."""
    entry = {'head': 'short', 'body': 'normal', 'skin': '#e8c4a0', 'hair': '#6a5a50', 'shirt': '#9aa0b0', 'pants': '#6c7080',
             'shoes': '#4a4a52', 'accent': '#f0f0f4'}
    info = build_one('humanoid', entry, looks, tmp)
    print('%-20s verts=%5d tris=%5d %4dKB (fallback mannequin)' % ('humanoid', info['verts'], info['tris'], info['bytes'] // 1024), flush=True)
    return info


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 1
    info_out = args[args.index('--info-out') + 1] if '--info-out' in args else None
    os.makedirs(OUT_DIR, exist_ok=True)
    cast = json.load(open(os.path.join(EXTRACTED, 'cast.json')))['cast']
    looks = load_looks().get('characters', {})
    t0 = time.time()
    keys = sprite_keys(cast, only)
    tmp = os.environ.get('TMPDIR', '/tmp')
    sprites = {}
    if jobs > 1 and len(keys) > 1:
        procs = []
        for i in range(jobs):
            part = keys[i::jobs]
            if part:
                out = os.path.join(tmp, 'gen_characters_%d.json' % i)
                procs.append((subprocess.Popen([sys.executable, os.path.abspath(__file__), '--only', ','.join(part), '--info-out', out]), out))
        codes = [p.wait() for p, _ in procs]
        if any(codes):
            sys.exit(1)
        for _, out in procs:
            sprites.update(json.load(open(out)))
    else:
        for key in keys:
            sprites[key] = build_one(key, cast[key], looks, tmp)
            s = sprites[key]
            print('%-20s verts=%5d tris=%5d %4dKB' % (key, s['verts'], s['tris'], s['bytes'] // 1024), flush=True)
    if info_out:
        json.dump(sprites, open(info_out, 'w'))
        return
    if only is None:
        humanoid_info = None
        if '--no-humanoid' not in args:
            humanoid_info = build_humanoid(looks, tmp)
        order = [k for k in cast if k in sprites]
        manifest = {
            'sprites': {k: sprites[k] for k in order},
            'aliases': ALIASES,
            'humanoid': humanoid_info,
            'height_m': 1.5,
            'animations': {
                'Idle': {'seconds': 1.6, 'loop': True},
                'Walk': {'seconds': 0.2667, 'loop': True, 'note': 'one full 2-step gait per 16-frame cell (feet plant at walk speed)'},
                'Run': {'seconds': 0.2667, 'loop': True},
                'Talk': {'seconds': 1.2, 'loop': True}, 'Wave': {'seconds': 0.8, 'loop': True},
                'Cheer': {'seconds': 0.6667, 'loop': True}, 'Surf': {'seconds': 1.5, 'loop': True},
                **{n: {'loop': n not in ('Bow', 'Surprised'), 'note': 'NPC gesture'} for n in
                   ('Nod', 'Shake', 'Think', 'Laugh', 'Bow', 'Point', 'Sleep', 'Surprised', 'Salute', 'Stretch', 'Dance', 'Sad', 'Shiver')}},
            'conventions': {'front': 'Blender -Y == glTF/Godot +Z', 'origin': 'feet at origin',
                            'materials': 'single mat_atlas (procedural atlas: AO x gradient ramps + painted eye decals); cel-shade with Toon.apply',
                            'bones': 'root > hips > spine > chest > neck > head; chest > clavicle_X > upper_arm_X > forearm_X > hand_X; '
                                     'hips > thigh_X > shin_X > foot_X; head > eye_L/eye_R (blink = the eyelid cap rotates about the eyeball, rot X), '
                                     'mouth (talk = scale z); optional hair_tail*/hair_back*/hair_twin*/cape*/scarf*/band_* chains'},
            'source': 'pipeline/extracted/cast.json palettes + pipeline/data/character_looks.json designs',
            'elapsed_seconds': round(time.time() - t0, 1),
        }
        with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=1)
    print('DONE characters=%d in %.1fs' % (len(sprites), time.time() - t0))


if __name__ == '__main__':
    main()

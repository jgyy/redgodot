"""Modular, runtime-recolourable player model parts (headless Blender) for the new-game character creator.

  python3 pipeline/blender/gen_player_parts.py [--jobs 4] [--only head_short_cap_round,body_dress]

The player is assembled in Godot from two skinned parts on one skeleton (godot/scripts/util/PlayerModel.gd):

  head_<hair>_<hat>_<eyes>.glb   head + face + hair + hat, the skeleton (incl. hair-follow-through bones) and every
                                 clip of char_anim.py (Idle Walk Run Talk ... + 13 gestures)      6 x 3 x 2 = 36
  body_<outfit>.glb              arms, torso, legs, shoes, backpack skinned to the standard bones     7 outfits

Both halves are cut from ONE welded body surface at the middle of the neck, so the cut vertices, their normals and their
skin weights are identical in every head and every body part and the join is invisible in any pose.

Colours are applied at runtime.  Each part ships an RGBA atlas (<part>.png): RGB = the atlas painted with a neutral
reference palette, ALPHA = 255 - 20 * role (0 = fixed colour, 1.. = index into manifest["roles"]).  The role map is found
by rebuilding the part once per role with that role's colour changed and diffing the painted atlases, so it needs no
knowledge of the painters.  PlayerModel multiplies the pixels of role r by target / reference colour.

Output: godot/assets/models/player/*.glb + *.png + manifest.json
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'player')

ROLES = ['skin', 'hair', 'hat', 'hatk', 'shirt', 'pants', 'shoes', 'bag', 'coat', 'iris']
C0 = {'skin': '#f4cca4', 'hair': '#d0d0d0', 'hat': '#d0d0d0', 'hatk': '#d0d0d0', 'shirt': '#d0d0d0', 'pants': '#d0d0d0',
      'shoes': '#d0d0d0', 'bag': '#d0d0d0', 'coat': '#d0d0d0', 'iris': '#d0d0d0'}
HAIRS = {'short': {'style': 'short', 'bang_n': 4, 'part': 0.4}, 'spiky': {'style': 'spiky', 'len': 3.8, 'sweep_back': 0.45, 'seed': 5},
         'long': {'style': 'long', 'part': 0.0}, 'pony': {'style': 'pony', 'length': 1.0, 'tie': 'accent'},
         'bun': {'style': 'bun', 'bun': 'top', 'bun_r': 2.5, 'tie': 'accent'}, 'bald': {'style': 'bald'}}
HATS = {'none': None,
        'cap': {'type': 'cap', 'color': 'hat', 'panel': 'hatk', 'brim': 'hat', 'logo': 'ball'},
        'beanie': {'type': 'beanie', 'color': 'hat'}}
EYES = ['round', 'lash']
JACKET = {'type': 'jacket', 'sleeves': 'short', 'sleeve_color': 'accent', 'trim': 'accent', 'collar': 'crew',
          'collar_color': 'accent', 'under': '#2a2a30', 'zip': True}
OUTFITS = {
    'tee_jeans': ({'type': 'shirt', 'sleeves': 'short'}, {'type': 'pants', 'cuff': '#e8e8f0'}),
    'jacket_jeans': (JACKET, {'type': 'pants', 'cuff': '#e8e8f0'}),
    'tee_shorts': ({'type': 'shirt', 'sleeves': 'short'}, {'type': 'shorts'}),
    'dress': ({'type': 'dress', 'sleeves': 'short'}, {'type': 'skirt'}),
    'tee_skirt': ({'type': 'shirt', 'sleeves': 'short'}, {'type': 'skirt'}),
    'coat_pants': ({'type': 'coat', 'color': 'coat', 'under_color': 'shirt'}, {'type': 'pants'}),
    'long_pants': ({'type': 'shirt', 'sleeves': 'long', 'collar': 'high'}, {'type': 'pants'}),
}
# one androgynous teenage body for every look (the creator's hair / outfit / eye choices carry the boy / girl styling)
PLAYER_BUILD = {'sh': 0.96, 'sw': 0.95, 'hs': 1.0, 'bulk': 0.95, 'sex': 'm', 'age': 'teen', 'jaw': 0.9, 'lift': 0.28}
FACE = {'nose': 'small'}


def head_names():
    return ['head_%s_%s_%s' % (h, t, e) for h in HAIRS for t in HATS for e in EYES]


def body_names():
    return ['body_%s' % o for o in OUTFITS]


def cast_for(colors):
    return {'skin': colors['skin'], 'hair': colors['hair'], 'hat': colors['hat'], 'hatK': colors['hatk'],
            'shirt': colors['shirt'], 'pants': colors['pants'], 'shoes': colors['shoes'], 'accent': '#f8f8f8',
            'backpack': colors['bag'], 'coat': colors['coat']}


def variant_colors(role=None):
    """Reference palette, with `role` swapped to a very different colour (used to find the role's pixels)."""
    import char_paint as PT
    c = dict(C0)
    if role:
        v = 1.0 - PT.hex2rgb(C0[role])
        v = v * 0.5 + 0.1
        c[role] = PT.rgb2hex(v)
    return c


def neck_cut(P):
    return P.neck_base + 0.35


# ---------------------------------------------------------------------------------------------- part builders
def new_ctx(name, colors, look):
    import char_body as B
    import char_hair as H
    ctx = B.Ctx(name, cast_for(colors), look)
    B.build_body(ctx, cache=True)
    ctx.headref = H.HeadRef(ctx)
    return ctx


def build_head_ctx(name, colors):
    import char_body as B
    import char_face as FC
    import char_hair as H
    import char_extras as X
    _, hair_k, hat_k, eyes_k = name.split('_')
    face = dict(FACE, eyes=eyes_k, iris=colors['iris'], brows='thin' if eyes_k == 'lash' else 'normal', mouth='smile', lash=(eyes_k == 'lash'))
    look = {'build': dict(PLAYER_BUILD), 'face': face, 'hair': dict(HAIRS[hair_k]), 'headwear': HATS[hat_k]}
    ctx = new_ctx(name, colors, look)
    hw = look['headwear']
    ctx.cover = bool(hw and hw['type'] in ('cap', 'beanie'))
    FC.build_face(ctx, face)
    if hw:
        X.build_hat(ctx, hw)
    if look['hair'].get('style') != 'none':
        H.build_hair(ctx, dict(look['hair']))
    ctx.add(B.skin_part(ctx, drop_covered=False, z_range=(neck_cut(ctx.P), 1e9)))
    ctx.ao_extra = (ctx.body.V, ctx.body.F)
    return ctx


def build_body_ctx(name, colors):
    import char_body as B
    import char_outfit as O
    import char_extras as X
    outfit = name[len('body_'):]
    top, legs = OUTFITS[outfit]
    look = {'build': dict(PLAYER_BUILD), 'face': dict(FACE), 'top': top, 'legs': legs,
            'shoes': {'type': 'sneaker', 'color': 'shoes', 'sole': '#f4f4f8'}, 'extras': {'backpack': {'color': 'bag', 'size': 1.0}}}
    ctx = new_ctx(name, colors, look)
    O.build_top(ctx, top)
    O.build_legs(ctx, legs)
    O.build_shoes(ctx, look['shoes'])
    X.backpack(ctx, look['extras']['backpack'])
    ctx.add(B.skin_part(ctx, drop_covered=True, z_range=(-1e9, neck_cut(ctx.P))))
    ctx.ao_extra = (ctx.body.V, ctx.body.F)
    return ctx


def builder(name):
    return build_head_ctx if name.startswith('head_') else build_body_ctx


# ---------------------------------------------------------------------------------------------- atlas + role map
def role_atlas(name, base_ctx):
    """(256, 256, 4) uint8: reference-palette atlas + role index in alpha."""
    import numpy as np
    r0 = base_ctx.atlas.render().astype(np.int32)
    diffs = []
    for role in ROLES:
        ctx = builder(name)(name, variant_colors(role))
        d = np.abs(ctx.atlas.render().astype(np.int32) - r0).max(axis=2)
        diffs.append(d)
    diffs = np.stack(diffs, 0)
    best = diffs.argmax(0)
    role = np.where(diffs.max(0) >= 4, best + 1, 0)
    out = np.zeros(r0.shape[:2] + (4,), np.uint8)
    out[..., :3] = r0.astype(np.uint8)
    out[..., 3] = 255 - 20 * role
    return out, {ROLES[i]: int((role == i + 1).sum()) for i in range(len(ROLES))}


# ---------------------------------------------------------------------------------------------- export
def build_one(name, out_dir):
    from PIL import Image
    import char_asm as AS
    t0 = time.time()
    ctx = builder(name)(name, dict(C0))
    info = AS.build_and_export(ctx, os.path.join(out_dir, name + '.glb'), white_material=True, anims=name.startswith('head_'))
    rgba, counts = role_atlas(name, ctx)
    Image.fromarray(rgba, 'RGBA').save(os.path.join(out_dir, name + '.png'), optimize=True)
    return {'verts': info['verts'], 'tris': info['tris'], 'roles': counts, 'seconds': round(time.time() - t0, 1),
            'bytes': os.path.getsize(os.path.join(out_dir, name + '.glb'))}


def write_manifest(out_dir):
    man = {'roles': ROLES, 'reference': C0, 'alpha': 'a = 255 - 20 * role (0 = fixed)',
           'hairs': list(HAIRS), 'hats': list(HATS), 'eyes': EYES, 'outfits': list(OUTFITS),
           'heads': head_names(), 'bodies': body_names(), 'animations': 'see gen_characters.py / char_anim.py'}
    with open(os.path.join(out_dir, 'manifest.json'), 'w') as fh:
        json.dump(man, fh, indent=1)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
    jobs = int(argv[argv.index('--jobs') + 1]) if '--jobs' in argv else 1
    out_dir = argv[argv.index('--out') + 1] if '--out' in argv else OUT_DIR
    names = only or (body_names() + head_names())
    if jobs > 1 and len(names) > 1:
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), '--only', ','.join(names[i::jobs]), '--out', out_dir])
                 for i in range(jobs) if names[i::jobs]]
        codes = [p.wait() for p in procs]   # wait for every worker (any(generator) stopped at the first failure and orphaned the rest)
        if any(codes):
            sys.exit(1)
    else:
        os.makedirs(out_dir, exist_ok=True)
        for nm in names:
            info = build_one(nm, out_dir)
            print('%-28s verts=%5d tris=%5d %5dKB %.1fs roles=%s' % (nm, info['verts'], info['tris'], info['bytes'] // 1024,
                                                                   info['seconds'], {k: v for k, v in info['roles'].items() if v}), flush=True)
    if only is None:
        write_manifest(out_dir)


if __name__ == '__main__':
    main()

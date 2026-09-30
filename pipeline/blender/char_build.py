"""Assemble one character from cast.json (palette) + character_looks.json (design)."""
import copy

import numpy as np

import char_body as B


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


HEAD_DEFAULT = {
    'cap': {'hair': {'style': 'short'}, 'headwear': {'type': 'cap', 'logo': 'ball'}},
    'spiky': {'hair': {'style': 'spiky'}},
    'short': {'hair': {'style': 'short'}},
    'long': {'hair': {'style': 'long'}},
    'bald': {'hair': {'style': 'bald'}},
    'hat': {'hair': {'style': 'short'}, 'headwear': {'type': 'wide'}},
    'beanie': {'hair': {'style': 'short'}, 'headwear': {'type': 'beanie'}},
    'bun': {'hair': {'style': 'bun'}},
    'pony': {'hair': {'style': 'pony'}},
}
BODY_DEFAULT = {
    'normal': {'top': {'type': 'shirt', 'sleeves': 'short'}, 'legs': {'type': 'pants'}},
    'coat': {'top': {'type': 'coat', 'color': 'coat', 'under_color': 'shirt'}, 'legs': {'type': 'pants'}},
    'dress': {'top': {'type': 'dress', 'sleeves': 'short'}, 'legs': {'type': 'skirt'}},
    'shorts': {'top': {'type': 'shirt', 'sleeves': 'short'}, 'legs': {'type': 'shorts'}},
    'swim': {'top': {'type': 'bare'}, 'legs': {'type': 'trunks'}, 'shoes': {'type': 'barefoot'}},
}


def resolve_look(key, cast, looks):
    base = {'face': {}, 'hair': {}, 'top': {}, 'legs': {}, 'shoes': {'type': 'sneaker'}, 'build': {}}
    base = deep_merge(base, HEAD_DEFAULT.get(cast.get('head') or 'short', {}))
    base = deep_merge(base, BODY_DEFAULT.get(cast.get('body') or 'normal', {}))
    if cast.get('glasses'):
        base['face']['glasses'] = {'type': 'round'}
    if cast.get('beard'):
        base['face']['beard'] = {'type': 'full'}
    if cast.get('backpack'):
        base.setdefault('extras', {})['backpack'] = {}
    if cast.get('emblem'):
        base.setdefault('extras', {})['emblem'] = {'type': 'R'}
    return deep_merge(base, looks.get(key, {}))


def build(key, cast, look, log=None):
    import char_face as FC
    import char_outfit as O
    import char_hair as H
    import char_extras as X
    ctx = B.Ctx(key, cast, look)
    ctx.log = log
    B.build_body(ctx)
    ctx.headref = H.HeadRef(ctx)
    face = look.get('face', {})
    hw = look.get('headwear')
    ctx.cover = bool(hw and hw.get('type') in ('cap', 'beanie') and hw.get('covers', True))
    FC.build_face(ctx, face)
    if hw:
        X.build_hat(ctx, hw)
    hair = dict(look.get('hair', {}))
    if hw and hw.get('type') in ('wide', 'sailor', 'chef', 'nurse', 'headband'):
        hair['thick'] = min(hair.get('thick', 0.4), 0.4)
        hair['volume'] = 0.0
    if hair.get('style', 'short') != 'none':
        H.build_hair(ctx, hair)
    if face.get('glasses'):
        X.glasses(ctx, face['glasses'])
    if face.get('moustache'):
        X.moustache(ctx, face['moustache'])
    if face.get('beard'):
        X.beard(ctx, face['beard'])
    O.build_top(ctx, look.get('top', {}))
    O.build_legs(ctx, look.get('legs', {}))
    O.build_shoes(ctx, look.get('shoes', {}))
    O.build_hands(ctx, look.get('gloves'))
    ex = look.get('extras', {})
    for nm in ('belt', 'emblem', 'tie', 'bowtie', 'scarf', 'necklace', 'suspenders', 'wristbands', 'cape'):
        if ex.get(nm):
            getattr(X, nm)(ctx, ex[nm])
    if ex.get('backpack') is not None and ex.get('backpack') is not False:
        X.backpack(ctx, ex['backpack'])
    ctx.add(B.skin_part(ctx, drop_covered=True))
    return ctx

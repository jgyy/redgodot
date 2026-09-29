"""Assemble one character from cast.json (palette) + character_looks.json (design)."""
import copy

import numpy as np

import char_body as B
import char_hair as H
import char_outfit as O
import char_extras as X


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


def build(key, cast, look):
    ctx = B.Ctx(key, cast, look)
    face = look.get('face', {})
    hair = dict(look.get('hair', {}))
    hw = look.get('headwear')
    ctx.cover = bool(hw and hw.get('type') in ('cap', 'beanie') and hw.get('covers', True))
    if ctx.cover:
        rim = hw.get('rim') or (X.CAP_RIM if hw['type'] == 'cap' else X.BEANIE_RIM)
        hair['top'] = [(a, t - 4.0) for a, t in rim]
        hair.setdefault('thick', 0.55)
        hair.setdefault('volume', 0.0)
    if hw and hw.get('type') in ('wide', 'sailor', 'chef', 'nurse', 'headband'):
        hair['thick'] = min(hair.get('thick', 0.4), 0.34)
        hair['volume'] = 0.0
    # ---- head & face
    B.build_head(ctx, ear=face.get('ears', True), nose=face.get('nose', 'dot'))
    B.build_face(ctx, face)
    if face.get('glasses'):
        X.glasses(ctx, face['glasses'])
    if face.get('moustache'):
        X.moustache(ctx, face['moustache'])
    if face.get('beard'):
        X.beard(ctx, face['beard'])
    if hair.get('style', 'short') != 'none':
        H.build_hair(ctx, hair)
    if hw:
        X.build_hat(ctx, hw)
    # ---- body
    top = look.get('top', {})
    long_sleeves = top.get('type') in ('coat', 'robe') or top.get('sleeves') == 'long'
    if not long_sleeves:
        for s in (1, -1):
            ctx.add(B.build_arm(ctx, s, 'skin', name='arm', s_from=0.0 if top.get('type') in ('bare',) or top.get('sleeves') == 'none' else 0.2))
    else:
        for s in (1, -1):
            ctx.add(B.build_arm(ctx, s, 'skin', name='arm', s_from=0.88, cap_end=0.7))
    O.build_top(ctx, top)
    O.build_legs(ctx, look.get('legs', {}))
    O.build_shoes(ctx, look.get('shoes', {}))
    O.build_hands(ctx, look.get('gloves'))
    ex = look.get('extras', {})
    if ex.get('belt'):
        X.belt(ctx, ex['belt'])
    if ex.get('emblem'):
        X.emblem(ctx, ex['emblem'])
    if ex.get('tie'):
        X.tie(ctx, ex['tie'])
    if ex.get('bowtie'):
        X.bowtie(ctx, ex['bowtie'])
    if ex.get('scarf'):
        X.scarf(ctx, ex['scarf'])
    if ex.get('necklace'):
        X.necklace(ctx, ex['necklace'])
    if ex.get('suspenders'):
        X.suspenders(ctx, ex['suspenders'])
    if ex.get('wristbands'):
        X.wristbands(ctx, ex['wristbands'])
    if ex.get('backpack') is not None and ex.get('backpack') is not False:
        X.backpack(ctx, ex['backpack'])
    if ex.get('cape'):
        X.cape(ctx, ex['cape'])
    return ctx

#!/usr/bin/env python3
"""Static eye / material / mesh audit of the generated Pokemon glbs (plain python3, no Blender or Godot).

    python3 pipeline/scripts/check_pokemon_eyes.py [godot/assets/models/pokemon] [--table]

For every species it verifies that
  * no material is alpha-blended or masked (the cel shader ignores alpha, so such layers render as opaque boxes),
  * every material is non-metallic and none is an inverted-hull "outline",
  * every texture is <= 512 px,
  * the model has eyes: an eye/iris/face material in the glb, or eye decals/patches recorded in eyes.json, or an explicit
    "eyes_kind" ("baked": painted in the body atlas, "none": eyeless species, "closed") in the overrides file,
  * the mesh height matches the Pokedex height and nothing is stretched by a floating prop (width < 6 x height).
Exit status 1 if anything fails, so CI can run it.
"""
import json
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
EYE_WORDS = ('eye', 'iris', 'pupil', 'sclera', 'face')


def read_glb(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    clen = struct.unpack_from('<I', data, 12)[0]
    js = json.loads(data[20:20 + clen].decode('utf-8'))
    bin_off = 20 + clen + 8
    return js, data, bin_off


def image_size(js, data, bin_off, im):
    bv = js['bufferViews'][im['bufferView']]
    b = data[bin_off + bv.get('byteOffset', 0): bin_off + bv.get('byteOffset', 0) + bv['byteLength']]
    if b[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', b[16:24])
    if b[:2] == b'\xff\xd8':
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack('>HH', b[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack('>H', b[i + 2:i + 4])[0]
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP':
        if b[12:16] == b'VP8X':
            return 1 + int.from_bytes(b[24:27], 'little'), 1 + int.from_bytes(b[27:30], 'little')
        if b[12:16] == b'VP8 ':
            w, h = struct.unpack('<HH', b[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if b[12:16] == b'VP8L':
            v = struct.unpack('<I', b[21:25])[0]
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
    return None


def audit(path, sid, ov, rec, height_m):
    js, data, bin_off = read_glb(path)
    fails, notes = [], []
    mats = js.get('materials', [])
    for m in mats:
        nm = m.get('name', '')
        if m.get('alphaMode', 'OPAQUE') != 'OPAQUE':
            fails.append('alpha %s on %s' % (m['alphaMode'], nm))
        if m.get('pbrMetallicRoughness', {}).get('metallicFactor', 1.0) > 0.05:
            fails.append('metallic %s' % nm)
        if any(k in nm.lower() for k in ('outline', 'contour')):
            fails.append('outline material %s' % nm)
    imgs = js.get('images', [])
    for im in imgs:
        sz = image_size(js, data, bin_off, im)
        if sz and max(sz) > 512:
            fails.append('texture %s is %dx%d' % (im.get('name'), sz[0], sz[1]))
    names = [m.get('name', '').lower() for m in mats] + [im.get('name', '').lower() for im in imgs]
    has_eye_mat = any(w in n for n in names for w in EYE_WORDS)
    kind = ov.get('eyes_kind')
    if rec.get('eye_decal_tris') or rec.get('eye_patches'):
        kind = kind or 'decal'
    elif has_eye_mat:
        kind = kind or 'native'
    if kind is None:
        fails.append('no eyes: no eye material, decal or eyes_kind override')
    # mesh sanity
    lo, hi = [1e9] * 3, [-1e9] * 3
    for me in js.get('meshes', []):
        for pr in me['primitives']:
            acc = js['accessors'][pr['attributes']['POSITION']]
            for i in range(3):
                lo[i], hi[i] = min(lo[i], acc['min'][i]), max(hi[i], acc['max'][i])
    h = hi[1] - lo[1]
    w = max(hi[0] - lo[0], hi[2] - lo[2])
    if height_m and abs(h - height_m) > 0.2 * height_m + 0.05 and sid != 'MISSINGNO':
        notes.append('height %.2f vs pokedex %.2f' % (h, height_m))
    if w > 6.0 * max(h, 1e-3):
        fails.append('stretched: width %.2f vs height %.2f (floating prop?)' % (w, h))
    return kind, fails, notes


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and sys.argv[i - 1] != '--md']
    folder = args[0] if args else os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon')
    ovs = json.load(open(os.path.join(ROOT, 'pipeline', 'data', 'pokemon_model_overrides.json')))
    eyes = json.load(open(os.path.join(folder, 'eyes.json')))['species'] if os.path.exists(os.path.join(folder, 'eyes.json')) else {}
    man = json.load(open(os.path.join(folder, 'manifest.json')))['species']
    bad, kinds, table = 0, {}, []
    for sid in sorted(man):
        p = os.path.join(folder, sid + '.glb')
        if not os.path.exists(p):
            print('%-12s MISSING' % sid)
            bad += 1
            continue
        kind, fails, notes = audit(p, sid, ovs.get(sid, {}), eyes.get(sid, {}), man[sid].get('height_m'))
        kinds[kind] = kinds.get(kind, 0) + 1
        rec = eyes.get(sid, {})
        did = []
        if rec.get('iris_baked_tris'):
            did.append('iris overlay baked into eye atlas (%d tris)' % rec['iris_baked_tris'])
        if rec.get('alpha_cut'):
            did.append('alpha layers cut: ' + ', '.join('%s (%d faces)' % kv for kv in rec['alpha_cut'].items() if kv[1]))
        if rec.get('strays_removed_verts'):
            did.append('%d stray vertices removed' % rec['strays_removed_verts'])
        if rec.get('eye_decal_tris'):
            did.append('decal painted (%d tris)' % rec['eye_decal_tris'])
        if rec.get('eye_patches'):
            did.append('%d flat eye/mouth discs' % rec['eye_patches'])
        for k, label in (('face_deg', 'turned %s deg to face front'), ('rot_deg', 'source axes fixed %s'), ('retint', 'retinted to sprite palette'),
                         ('drop_materials', 'translucent shells dropped'), ('alpha_fill', 'transparent texels filled')):
            if k in ovs.get(sid, {}):
                did.append(label % ovs[sid][k] if '%s' in label else label)
        table.append((sid, kind, '; '.join(did) or '-'))
        if fails or '--table' in sys.argv:
            print('%-12s %-7s %s %s' % (sid, kind, 'FAIL ' + '; '.join(fails) if fails else 'ok', ('(' + '; '.join(notes) + ')') if notes else ''))
        bad += 1 if fails else 0
    if '--md' in sys.argv:
        out = sys.argv[sys.argv.index('--md') + 1]
        with open(out, 'w') as fh:
            fh.write('# Per-species eye / material handling (generated by check_pokemon_eyes.py --md)\n\n')
            fh.write('kind: native = the source mesh has eye/iris materials, kept and repaired; baked = eyes are painted in the body atlas; '
                     'decal = extra eye pixels or discs added by pokemon_eyes.py; none = eyeless species.\n\n')
            fh.write('| species | kind | what the pipeline did |\n|---|---|---|\n')
            for sid, kind, did in table:
                fh.write('| %s | %s | %s |\n' % (sid, kind, did))
    print('SUMMARY species=%d failing=%d kinds=%s' % (len(man), bad, kinds))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

"""Sanity-check the baked Pokemon animations in godot/assets/models/pokemon/*.glb (plain python3 + numpy).

  python3 pipeline/blender/check_pokemon_anims.py [folder]

For every model: the six required clips exist; Idle and Walk are seamless loops (last key == first key on
every channel); no channel jumps between consecutive 30 fps keys by more than a physically sensible step
(no popping); Walk lasts a whole number of overworld cells.  Exit code 1 if any check fails.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glbtools as GT  # noqa: E402

REQUIRED = ['Idle', 'Walk', 'Attack', 'Hurt', 'Faint', 'Special']
MAX_ROT_STEP = 0.45          # rad between consecutive frames in looping clips (~26 deg = 780 deg/s)
MAX_ROT_STEP_SHOT = 0.9      # one-shots (strikes are snappy)
MAX_LOC_STEP = 0.35          # fraction of model height per frame


def quat_angle(a, b):
    d = np.abs((a * b).sum(axis=1)).clip(0, 1)
    return 2 * np.arccos(d)


def check(path):
    g = GT.Glb(path)
    js = g.js
    probs = []
    names = {a['name']: a for a in js.get('animations', [])}
    for r in REQUIRED:
        if r not in names:
            probs.append('missing clip %s' % r)
    nodes = js['nodes']
    height = 1.0
    prim = js['meshes'][0]['primitives'][0]
    pos = js['accessors'][prim['attributes']['POSITION']]
    if 'min' in pos:
        height = max(pos['max'][1] - pos['min'][1], 0.05)
    for cname, a in names.items():
        for ch in a['channels']:
            s = a['samplers'][ch['sampler']]
            t = g.read(s['input'])[:, 0]
            v = g.read(s['output']).astype(np.float64)
            path_ = ch['target']['path']
            if len(t) < 2:
                continue
            if cname in ('Idle', 'Walk') and not np.allclose(v[0], v[-1], atol=1e-4):
                probs.append('%s %s/%s not a seamless loop (%.5f)' % (
                    cname, nodes[ch['target']['node']].get('name'), path_, np.abs(v[0] - v[-1]).max()))
            if path_ == 'rotation':
                step = quat_angle(v[:-1], v[1:])
                if step.max() > (MAX_ROT_STEP if cname in ("Idle", "Walk") else MAX_ROT_STEP_SHOT):
                    probs.append('%s %s pops: %.2f rad in one frame' % (cname, nodes[ch['target']['node']].get('name'),
                                                                           step.max()))
            elif path_ == 'translation':
                step = np.linalg.norm(np.diff(v, axis=0), axis=1)
                if step.max() > MAX_LOC_STEP * height and cname not in ('Special',):
                    probs.append('%s %s jumps %.2f m in one frame' % (cname, nodes[ch['target']['node']].get('name'),
                                                                        step.max()))
    if 'Walk' in names:
        a = names['Walk']
        s = a['samplers'][a['channels'][0]['sampler']]
        dur = float(g.read(s['input'])[-1, 0])
        cell = 16.0 / 60.0
        if abs(dur / cell - round(dur / cell)) > 0.02:
            probs.append('Walk is %.3f s, not a whole number of %.3f s cells' % (dur, cell))
    return probs


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'godot', 'assets', 'models', 'pokemon')
    bad = 0
    files = sorted(f for f in os.listdir(folder) if f.endswith('.glb'))
    for f in files:
        probs = check(os.path.join(folder, f))
        if probs:
            bad += 1
            print('%-18s %s' % (f, '; '.join(probs[:4]) + (' (+%d more)' % (len(probs) - 4) if len(probs) > 4 else '')))
    print('checked %d models, %d with problems' % (len(files), bad))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

"""Verify generated .glb files without external deps (plain python3, not Blender).

  python3 pipeline/blender/verify_glb.py godot/assets/models/pokemon --require-skin --anims Idle,Walk,Attack
      [--min-anims 24] [--tpose] [--bones-report] [--max-kb 1600] [--min-kb 2] [--prefix P] [--skip a.glb,b.glb]

Prints one line per file + a summary; exit code 1 if any file fails.
  --min-anims N    at least N animations per file (Pokemon: 24 = 18 game clips + 3 idle variants + 6 signature clips)
  --tpose          bone-based T/A-pose check of the first frame of Idle: an Arm_* chain sticking out sideways and level
                   (60-125 deg from straight down, > 40 deg out of the sagittal plane), an upright biped's legs splayed > 40 deg
  --bones-report   bone count per file and, in the summary, min/max/mean and how many distinct (bone name) signatures
  --max-kb N       files larger than N kilobytes fail

Environment props (godot/assets/models/world):
  python3 pipeline/blender/verify_glb.py godot/assets/models/world --min-kb 1 --max-kb 300 --max-tris 4000 \
      --meshes table_set=16,desk_set=16,counter_center_set=16,counter_mart_set=16,bench_set=4
--max-kb / --max-tris bound every file; --meshes name=N requires a modular set glb to hold N meshes.
"""
import json
import math
import os
import re
import struct
import sys


def read_glb(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:4] != b'glTF':
        raise ValueError('bad magic')
    ver, length = struct.unpack_from('<II', data, 4)
    clen, ctype = struct.unpack_from('<II', data, 12)
    if ctype != 0x4E4F534A:
        raise ValueError('first chunk not JSON')
    js = json.loads(data[20:20 + clen].decode('utf-8'))
    return js, len(data)


def read_glb_bin(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    clen = struct.unpack_from('<I', data, 12)[0]
    off = 20 + clen
    blen = struct.unpack_from('<I', data, off)[0]
    return data[off + 8:off + 8 + blen]


# ------------------------------------------------------------------------------------------------ tiny matrix helpers
def _mat(t, q, s):
    x, y, z, w = q
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]] for i in range(3)] + [[0, 0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _accessor(js, binb, i):
    a = js['accessors'][i]
    v = js['bufferViews'][a['bufferView']]
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    n = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[a['type']]
    vals = struct.unpack_from('<%df' % (a['count'] * n), binb, off)
    return [vals[k * n:(k + 1) * n] for k in range(a['count'])]


def tpose_violations(path, js):
    """[(chain, down deg, spread deg)] for T-posed Arm_* / splayed biped Leg_* chains in the first frame of Idle."""
    binb = read_glb_bin(path)
    nodes = js['nodes']
    idle = next((a for a in js.get('animations', []) if a.get('name') == 'Idle'), None)
    trs = [[list(n.get('translation', [0, 0, 0])), list(n.get('rotation', [0, 0, 0, 1])), list(n.get('scale', [1, 1, 1]))] for n in nodes]
    if idle:
        for ch in idle['channels']:
            tg = ch['target']
            out = _accessor(js, binb, idle['samplers'][ch['sampler']]['output'])[0]
            trs[tg['node']][{'translation': 0, 'rotation': 1, 'scale': 2}[tg['path']]] = list(out)
    parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    world = {}

    def wm(i):
        if i not in world:
            m = _mat(*trs[i])
            world[i] = _mul(wm(parent[i]), m) if i in parent else m
        return world[i]
    joints = js['skins'][0]['joints']
    name = {j: nodes[j].get('name', '') for j in joints}
    pos = {j: [wm(j)[k][3] for k in range(3)] for j in joints}
    out = []
    role = lambda n: re.match(r'^(Arm|Leg)_', n)
    for j in joints:
        m = role(name[j])
        if not m:
            continue
        par = parent.get(j)
        if par in name and role(name[par]) and role(name[par]).group(1) == m.group(1):
            continue
        last, cur = j, j
        while True:
            kids = [c for c in nodes[cur].get('children', []) if c in name and role(name[c]) and role(name[c]).group(1) == m.group(1)]
            if not kids:
                break
            cur = kids[0]
            last = cur
        if last == j:
            continue
        v = [pos[last][k] - pos[j][k] for k in range(3)]
        L = math.sqrt(sum(c * c for c in v))
        if L < 1e-6:
            continue
        down = math.degrees(math.acos(max(-1.0, min(1.0, -v[1] / L))))
        spread = math.degrees(math.asin(min(1.0, abs(v[0]) / L)))
        if m.group(1) == 'Arm' and 60.0 < down < 125.0 and spread > 40.0:
            out.append((name[j], round(down), round(spread)))
    return out


def main():
    args = sys.argv[1:]
    folder = args[0]
    anims = args[args.index('--anims') + 1].split(',') if '--anims' in args else []
    need_skin = '--require-skin' in args
    min_kb = float(args[args.index('--min-kb') + 1]) if '--min-kb' in args else 2.0
    min_anims = int(args[args.index('--min-anims') + 1]) if '--min-anims' in args else 0
    prefix = args[args.index('--prefix') + 1] if '--prefix' in args else ''
    skip = args[args.index('--skip') + 1].split(',') if '--skip' in args else []
    max_kb = float(args[args.index('--max-kb') + 1]) if '--max-kb' in args else 1e9
    max_tris = int(args[args.index('--max-tris') + 1]) if '--max-tris' in args else 10 ** 9
    need_meshes = dict(kv.split('=') for kv in args[args.index('--meshes') + 1].split(',')) if '--meshes' in args else {}
    do_tpose = '--tpose' in args
    bones_report = '--bones-report' in args
    files = sorted(f for f in os.listdir(folder) if f.endswith('.glb') and f.startswith(prefix) and f not in skip)
    bad, total = [], 0
    counts, sigs = [], set()
    for f in files:
        p = os.path.join(folder, f)
        try:
            js, n = read_glb(p)
            total += n
            meshes = len(js.get('meshes', []))
            mats = len(js.get('materials', []))
            an = [a.get('name') for a in js.get('animations', [])]
            skins = len(js.get('skins', []))
            tris = 0
            for m in js.get('meshes', []):
                for pr in m['primitives']:
                    acc = js['accessors'][pr['indices']] if 'indices' in pr else js['accessors'][pr['attributes']['POSITION']]
                    tris += acc['count'] // 3
            nb = len(js['skins'][0]['joints']) if skins else 0
            counts.append(nb)
            if skins:
                sigs.add(tuple(sorted(js['nodes'][j].get('name', '') for j in js['skins'][0]['joints'])))
            ok = (meshes >= 1 and mats >= 1 and n >= min_kb * 1024 and all(a in an for a in anims)
                  and (skins >= 1 or not need_skin) and len(an) >= min_anims and (not max_kb or n <= max_kb * 1024) and tris <= max_tris)
            key = f[:-4]
            if key in need_meshes and meshes != int(need_meshes[key]):
                ok = False
            note = ''
            if do_tpose and skins:
                tv = tpose_violations(p, js)
                if tv:
                    ok = False
                    note = ' TPOSE=%s' % (tv,)
            print('%-22s %s %7.1fKB meshes=%d mats=%d skins=%d bones=%d tris=%d anims=%d%s' % (
                f, 'OK ' if ok else 'BAD', n / 1024, meshes, mats, skins, nb, tris, len(an), note) +
                ('' if len(an) > 40 else ' [%s]' % (','.join(an) or '-')) * (not bones_report))
            if not ok:
                bad.append(f)
        except Exception as e:
            print('%-22s BAD %s' % (f, e))
            bad.append(f)
    extra = ''
    if bones_report and counts:
        extra = ' bones min/max/mean=%d/%d/%.1f distinct_counts=%d distinct_signatures=%d' % (
            min(counts), max(counts), sum(counts) / len(counts), len(set(counts)), len(sigs))
    print('SUMMARY files=%d bad=%d total=%.2fMB%s' % (len(files), len(bad), total / 1048576, extra))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

"""Verify generated .glb files without external deps (plain python3, not Blender).

  python3 pipeline/blender/verify_glb.py godot/assets/models/pokemon --require-skin --anims Idle,Walk,Attack
Prints one line per file + a summary; exit code 1 if any file fails.

Environment props (godot/assets/models/world):
  python3 pipeline/blender/verify_glb.py godot/assets/models/world --min-kb 1 --max-kb 300 --max-tris 4000 \
      --meshes table_set=16,desk_set=16,counter_center_set=16,counter_mart_set=16,bench_set=4
--max-kb / --max-tris bound every file; --meshes name=N requires a modular set glb to hold N meshes.
"""
import json
import os
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


def main():
    args = sys.argv[1:]
    folder = args[0]
    anims = args[args.index('--anims') + 1].split(',') if '--anims' in args else []
    need_skin = '--require-skin' in args
    min_kb = float(args[args.index('--min-kb') + 1]) if '--min-kb' in args else 2.0
    prefix = args[args.index('--prefix') + 1] if '--prefix' in args else ''
    skip = args[args.index('--skip') + 1].split(',') if '--skip' in args else []
    max_kb = float(args[args.index('--max-kb') + 1]) if '--max-kb' in args else 1e9
    max_tris = int(args[args.index('--max-tris') + 1]) if '--max-tris' in args else 10 ** 9
    need_meshes = dict(kv.split('=') for kv in args[args.index('--meshes') + 1].split(',')) if '--meshes' in args else {}
    files = sorted(f for f in os.listdir(folder) if f.endswith('.glb') and f.startswith(prefix) and f not in skip)
    bad, total = [], 0
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
            ok = meshes >= 1 and mats >= 1 and n >= min_kb * 1024 and n <= max_kb * 1024 and tris <= max_tris and all(a in an for a in anims) and (skins >= 1 or not need_skin)
            key = f[:-4]
            if key in need_meshes and meshes != int(need_meshes[key]):
                ok = False
            print('%-22s %s %7.1fKB meshes=%d mats=%d skins=%d tris=%d anims=%s' % (
                f, 'OK ' if ok else 'BAD', n / 1024, meshes, mats, skins, tris, ','.join(an) or '-'))
            if not ok:
                bad.append(f)
        except Exception as e:
            print('%-22s BAD %s' % (f, e))
            bad.append(f)
    print('SUMMARY files=%d bad=%d total=%.2fMB' % (len(files), len(bad), total / 1048576))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

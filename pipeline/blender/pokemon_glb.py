"""Post-process an exported Pokemon .glb (pure python): drop animation channels that never move and share identical data.

Blender's glTF exporter writes TRS channels for every bone of every clip (bones x 3 x 30 clips = thousands of channels,
each with its own two accessors), although most are constant.  A channel is dropped when its bone property equals the
node's rest value in *every* clip of the file; channels that move in any clip stay in *all* clips (so Godot never
leaves a bone in the pose the previous clip ended in), and byte-identical accessors are stored once.
"""
import json
import struct

NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
PATH_REST = {'translation': [0.0, 0.0, 0.0], 'rotation': [0.0, 0.0, 0.0, 1.0], 'scale': [1.0, 1.0, 1.0]}


def read(path):
    with open(path, 'rb') as fh:
        d = fh.read()
    jl, jt = struct.unpack_from('<II', d, 12)
    js = json.loads(d[20:20 + jl].decode('utf-8'))
    off = 20 + jl
    bl, bt = struct.unpack_from('<II', d, off)
    return js, d[off + 8:off + 8 + bl]


def write(path, js, binb):
    j = json.dumps(js, separators=(',', ':')).encode('utf-8')
    j += b' ' * (-len(j) % 4)
    binb = binb + b'\0' * (-len(binb) % 4)
    total = 12 + 8 + len(j) + 8 + len(binb)
    with open(path, 'wb') as fh:
        fh.write(struct.pack('<4sII', b'glTF', 2, total))
        fh.write(struct.pack('<II', len(j), 0x4E4F534A) + j)
        fh.write(struct.pack('<II', len(binb), 0x004E4942) + binb)


def prune(path, eps=1e-5):
    js, binb = read(path)
    acc, bvs = js['accessors'], js['bufferViews']
    nodes = js['nodes']

    def raw(ai):
        a = acc[ai]
        v = bvs[a['bufferView']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        n = a['count'] * NCOMP[a['type']]
        return off, n

    def floats(ai):
        off, n = raw(ai)
        return struct.unpack_from('<%df' % n, binb, off)

    def rest(node, path_):
        r = nodes[node].get(path_)
        return list(r) if r is not None else PATH_REST[path_]

    moving = set()
    for an in js.get('animations', []):
        for ch in an['channels']:
            t = ch['target']
            key = (t['node'], t['path'])
            if key in moving:
                continue
            vals = floats(an['samplers'][ch['sampler']]['output'])
            r = rest(*key)
            k = len(r)
            n = len(vals) // k
            neg = -1.0 if t['path'] == 'rotation' else 1.0
            same = all(abs(vals[i * k + j] - r[j]) <= eps for i in range(n) for j in range(k))
            if not same and t['path'] == 'rotation':   # q and -q are the same rotation
                same = all(abs(vals[i * k + j] + r[j]) <= eps for i in range(n) for j in range(k))
            if not same:
                moving.add(key)
    for an in js.get('animations', []):
        chans, samplers, remap = [], [], {}
        for ch in an['channels']:
            t = ch['target']
            if (t['node'], t['path']) not in moving:
                continue
            si = ch['sampler']
            if si not in remap:
                remap[si] = len(samplers)
                samplers.append(an['samplers'][si])
            chans.append({'sampler': remap[si], 'target': t})
        if not chans:      # never leave an empty (zero length) clip: keep the first channel
            ch = an['channels'][0]
            samplers = [an['samplers'][ch['sampler']]]
            chans = [{'sampler': 0, 'target': ch['target']}]
        an['channels'], an['samplers'] = chans, samplers

    # ---- gather used accessors, dedupe by content, rebuild buffer views -------------------------------------------
    used = []

    def use(i):
        if i is not None and i not in used:
            used.append(i)
    for m in js.get('meshes', []):
        for p in m['primitives']:
            for v in p.get('attributes', {}).values():
                use(v)
            use(p.get('indices'))
            for tg in p.get('targets', []):
                for v in tg.values():
                    use(v)
    for s in js.get('skins', []):
        use(s.get('inverseBindMatrices'))
    for an in js.get('animations', []):
        for s in an['samplers']:
            use(s['input'])
            use(s['output'])
    new_bin = bytearray()
    new_bvs, new_acc, amap, seen = [], [], {}, {}
    # images keep their buffer views
    img_bv = {}
    for im in js.get('images', []):
        if 'bufferView' in im:
            v = bvs[im['bufferView']]
            off = v.get('byteOffset', 0)
            new_bin += b'\0' * (-len(new_bin) % 4)
            nv = {'buffer': 0, 'byteOffset': len(new_bin), 'byteLength': v['byteLength']}
            new_bin += binb[off:off + v['byteLength']]
            new_bvs.append(nv)
            im['bufferView'] = len(new_bvs) - 1
    for ai in used:
        a = dict(acc[ai])
        v = bvs[a['bufferView']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        csz = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}[a['componentType']]
        n = a['count'] * NCOMP[a['type']] * csz
        chunk = bytes(binb[off:off + n])
        key = (a['type'], a['componentType'], a['count'], chunk) if v.get('target') is None else None
        if key is not None and key in seen:
            amap[ai] = seen[key]
            continue
        new_bin += b'\0' * (-len(new_bin) % 4)
        nv = {'buffer': 0, 'byteOffset': len(new_bin), 'byteLength': n}
        if v.get('target') is not None:
            nv['target'] = v['target']
        new_bin += chunk
        new_bvs.append(nv)
        a['bufferView'] = len(new_bvs) - 1
        a.pop('byteOffset', None)
        new_acc.append(a)
        amap[ai] = len(new_acc) - 1
        if key is not None:
            seen[key] = amap[ai]
    for m in js.get('meshes', []):
        for p in m['primitives']:
            p['attributes'] = {k: amap[v] for k, v in p['attributes'].items()}
            if 'indices' in p:
                p['indices'] = amap[p['indices']]
            for tg in p.get('targets', []):
                for k in tg:
                    tg[k] = amap[tg[k]]
    for s in js.get('skins', []):
        if 'inverseBindMatrices' in s:
            s['inverseBindMatrices'] = amap[s['inverseBindMatrices']]
    for an in js.get('animations', []):
        for s in an['samplers']:
            s['input'], s['output'] = amap[s['input']], amap[s['output']]
    js['accessors'], js['bufferViews'] = new_acc, new_bvs
    js['buffers'] = [{'byteLength': len(new_bin)}]
    write(path, js, bytes(new_bin))
    return len(moving)

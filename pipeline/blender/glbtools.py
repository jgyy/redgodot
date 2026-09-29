"""Small binary-glTF post-processing helpers (no bpy): move embedded textures out to sibling files
(optionally transcoded to lossy WebP) and shrink vertex attributes (vertex colour + skin weights to
normalised bytes) so 151 skinned, animated models stay small."""
import json
import os
import struct

import numpy as np


class Glb:
    def __init__(self, path):
        data = open(path, 'rb').read()
        magic, ver, length = struct.unpack_from('<4sII', data, 0)
        assert magic == b'glTF' and ver == 2
        off = 12
        self.js = None
        binc = b''
        while off < length:
            clen, ctype = struct.unpack_from('<II', data, off)
            chunk = data[off + 8: off + 8 + clen]
            if ctype == 0x4E4F534A:
                self.js = json.loads(chunk.decode('utf-8'))
            elif ctype == 0x004E4942:
                binc = chunk
            off += 8 + clen
        self.views = []
        for bv in self.js.get('bufferViews', []):
            o = bv.get('byteOffset', 0)
            self.views.append(bytes(binc[o: o + bv['byteLength']]))

    # ---- accessors as numpy arrays
    _CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
    _NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

    def read(self, ai):
        a = self.js['accessors'][ai]
        bv = self.js['bufferViews'][a['bufferView']]
        dt = np.dtype(self._CT[a['componentType']])
        nc = self._NC[a['type']]
        raw = self.views[a['bufferView']]
        stride = bv.get('byteStride') or dt.itemsize * nc
        start = a.get('byteOffset', 0)
        if stride == dt.itemsize * nc:
            arr = np.frombuffer(raw, dtype=dt, count=a['count'] * nc, offset=start)
        else:
            arr = np.stack([np.frombuffer(raw, dtype=dt, count=nc, offset=start + i * stride)
                            for i in range(a['count'])])
        return arr.reshape(a['count'], nc)

    def replace(self, ai, arr, component, typ, normalized=False, target=34962):
        """Point accessor ai at a fresh buffer view holding `arr`."""
        a = self.js['accessors'][ai]
        dt = np.dtype(self._CT[component])
        data = np.ascontiguousarray(arr.astype(dt)).tobytes()
        self.js['bufferViews'].append({'buffer': 0, 'byteOffset': 0, 'byteLength': len(data), 'target': target})
        self.views.append(data)
        a['bufferView'] = len(self.views) - 1
        a['componentType'] = component
        a['type'] = typ
        a.pop('byteOffset', None)
        a.pop('min', None)
        a.pop('max', None)
        if normalized:
            a['normalized'] = True
        else:
            a.pop('normalized', None)

    def save(self, path):
        js = self.js
        used = set()
        for a in js.get('accessors', []):
            if 'bufferView' in a:
                used.add(a['bufferView'])
        for im in js.get('images', []):
            if 'bufferView' in im:
                used.add(im['bufferView'])
        remap, keep_views, keep_data = {}, [], []
        for i, bv in enumerate(js['bufferViews']):
            if i in used:
                remap[i] = len(keep_views)
                keep_views.append(dict(bv))
                keep_data.append(self.views[i])
        newbin = bytearray()
        for bv, data in zip(keep_views, keep_data):
            while len(newbin) % 4:
                newbin.append(0)
            bv['byteOffset'] = len(newbin)
            bv['byteLength'] = len(data)
            newbin += data
        for a in js.get('accessors', []):
            if 'bufferView' in a:
                a['bufferView'] = remap[a['bufferView']]
        for im in js.get('images', []):
            if 'bufferView' in im:
                im['bufferView'] = remap[im['bufferView']]
        js['bufferViews'] = keep_views
        js['buffers'][0]['byteLength'] = len(newbin)
        jb = json.dumps(js, separators=(',', ':')).encode('utf-8')
        jb += b' ' * ((4 - len(jb) % 4) % 4)
        b = bytes(newbin) + b'\x00' * ((4 - len(newbin) % 4) % 4)
        total = 12 + 8 + len(jb) + 8 + len(b)
        with open(path, 'wb') as fh:
            fh.write(struct.pack('<4sII', b'glTF', 2, total))
            fh.write(struct.pack('<II', len(jb), 0x4E4F534A))
            fh.write(jb)
            fh.write(struct.pack('<II', len(b), 0x004E4942))
            fh.write(b)


def _read(path):          # kept for the small debugging scripts
    g = Glb(path)
    return g.js, b''.join(g.views)


def externalize_images(path, name_for, transcode=None):
    """Move every embedded image out of the .glb into a sibling file and reference it by relative uri.
    `name_for(i, mime)` -> base file name (no extension); `transcode(raw)` -> (bytes, ext, mime) to
    re-encode (e.g. lossy WebP).  Returns the list of written file paths."""
    g = Glb(path)
    outdir = os.path.dirname(path)
    written = []
    for i, im in enumerate(g.js.get('images', [])):
        if 'bufferView' not in im:
            continue
        raw = g.views[im['bufferView']]
        mime = im.get('mimeType', 'image/png')
        ext = 'png' if 'png' in mime else 'jpg'
        if transcode is not None:
            raw, ext, mime = transcode(raw)
        fn = '%s.%s' % (name_for(i, mime), ext)
        with open(os.path.join(outdir, fn), 'wb') as fh:
            fh.write(raw)
        written.append(os.path.join(outdir, fn))
        im.pop('bufferView')
        im['uri'] = fn
        im['mimeType'] = mime
    g.save(path)
    return written


def quantize_attributes(path):
    """COLOR_0 -> normalised RGBA bytes; WEIGHTS_0 -> normalised bytes summing to exactly 255."""
    g = Glb(path)
    for m in g.js.get('meshes', []):
        for prim in m['primitives']:
            at = prim['attributes']
            if 'COLOR_0' in at:
                c = g.read(at['COLOR_0']).astype(np.float32)
                if c.shape[1] == 3:
                    c = np.concatenate([c, np.ones((len(c), 1), np.float32)], axis=1)
                q = np.clip(np.round(c * 255.0), 0, 255)
                g.replace(at['COLOR_0'], q, 5121, 'VEC4', normalized=True)
            if 'WEIGHTS_0' in at:
                w = g.read(at['WEIGHTS_0']).astype(np.float64)
                w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-9)
                raw = w * 255.0
                q = np.floor(raw)
                rem = 255 - q.sum(axis=1)
                frac = raw - q
                order = np.argsort(-frac, axis=1)
                for k in range(4):
                    add = (rem > k)
                    q[np.arange(len(q))[add], order[add, k]] += 1
                g.replace(at['WEIGHTS_0'], q, 5121, 'VEC4', normalized=True)
    g.save(path)

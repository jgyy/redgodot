"""Measure exported Pokemon .glb files (numpy only, no Blender): skinned poses, T-pose detector, clip distinctness, stretch.

    python3 pipeline/blender/pokemon_check.py godot/assets/models/pokemon [--only PIKACHU,...] [--json out.json]

The T-pose detector works on the *exported* file: it skins the mesh at frame 0 of the Idle clip and measures, for every arm/leg/wing chain,
the angle between the limb (root joint -> centroid of the farthest vertices bound to the chain) and straight down / the body's sagittal plane.
"""
import json
import math
import os
import re
import struct
import sys

import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

# a limb further than this from straight down (or a wing more spread than this) counts as a T/A pose
ARM_MAX_DOWN = 60.0     # deg: natural arms hang 15-35, forward-holding arms up to ~50
LEG_MAX_SPREAD = 40.0
WING_MAX_SPREAD = 65.0


class Glb:
    def __init__(self, path):
        with open(path, 'rb') as fh:
            d = fh.read()
        jl = struct.unpack_from('<I', d, 12)[0]
        self.js = json.loads(d[20:20 + jl].decode())
        bo = 20 + jl + 8
        self.bin = d[bo:]
        self.path = path
        js = self.js
        self.nodes = js['nodes']
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                self.parent[c] = i
        sk = js['skins'][0]
        self.joints = sk['joints']
        self.ibm = self.acc(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        mesh_node = next(i for i, n in enumerate(self.nodes) if 'mesh' in n)
        prims = js['meshes'][self.nodes[mesh_node]['mesh']]['primitives']
        P, J, W = [], [], []
        for p in prims:
            P.append(self.acc(p['attributes']['POSITION']))
            J.append(self.acc(p['attributes']['JOINTS_0']).astype(int))
            W.append(self.acc(p['attributes']['WEIGHTS_0']).astype(float))
        self.P = np.concatenate(P).astype(float)
        self.J = np.concatenate(J)
        self.W = np.concatenate(W)
        self.jnames = [self.nodes[j]['name'] for j in self.joints]
        self.H = float(self.P[:, 1].max() - self.P[:, 1].min())
        self.anims = {}
        for a in js.get('animations', []):
            ch = {}
            for c in a['channels']:
                s = a['samplers'][c['sampler']]
                ch[(c['target']['node'], c['target']['path'])] = (self.acc(s['input']), self.acc(s['output']))
            dur = max(float(t[-1]) for t, _ in ch.values()) if ch else 0.0
            self.anims[a['name']] = (ch, dur)
        self._order = self._toposort()

    def acc(self, i):
        a = self.js['accessors'][i]
        v = self.js['bufferViews'][a['bufferView']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        n = a['count'] * NC[a['type']]
        arr = np.frombuffer(self.bin, dtype=CT[a['componentType']], count=n, offset=off)
        if a.get('normalized'):
            arr = arr / float(np.iinfo(arr.dtype).max)
        return arr.reshape(a['count'], NC[a['type']]) if NC[a['type']] > 1 else arr.copy()

    def _toposort(self):
        seen, out = set(), []

        def visit(i):
            if i in seen:
                return
            if i in self.parent:
                visit(self.parent[i])
            seen.add(i)
            out.append(i)
        for i in range(len(self.nodes)):
            visit(i)
        return out

    # ---- evaluation ---------------------------------------------------------------------------
    def local_trs(self, clip, t):
        trs = {}
        ch = self.anims[clip][0] if clip else {}
        for i, n in enumerate(self.nodes):
            trs[i] = [np.array(n.get('translation', [0, 0, 0]), float), np.array(n.get('rotation', [0, 0, 0, 1]), float),
                      np.array(n.get('scale', [1, 1, 1]), float)]
        for (node, path), (ts, vs) in ch.items():
            k = {'translation': 0, 'rotation': 1, 'scale': 2}[path]
            trs[node][k] = _sample(ts, vs, t, path == 'rotation')
        return trs

    def globals(self, clip, t):
        trs = self.local_trs(clip, t)
        G = {}
        for i in self._order:
            T, Q, S = trs[i]
            M = np.eye(4)
            M[:3, :3] = _qmat(Q) * S[None, :]
            M[:3, 3] = T
            G[i] = G[self.parent[i]] @ M if i in self.parent else M
        return G

    def skin(self, clip, t, idx=None):
        G = self.globals(clip, t)
        JM = np.array([G[j] for j in self.joints]) @ self.ibm      # (nj, 4, 4)
        P = self.P if idx is None else self.P[idx]
        J = self.J if idx is None else self.J[idx]
        W = self.W if idx is None else self.W[idx]
        ph = np.concatenate([P, np.ones((len(P), 1))], axis=1)
        out = np.zeros((len(P), 3))
        for k in range(4):
            m = JM[J[:, k]]                                          # (n, 4, 4)
            out += W[:, k:k + 1] * np.einsum('nij,nj->ni', m, ph)[:, :3]
        return out

    def joint_positions(self, clip, t):
        G = self.globals(clip, t)
        return {self.nodes[j]['name']: G[j][:3, 3] for j in self.joints}

    def duration(self, clip):
        return self.anims[clip][1]


def _qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _sample(ts, vs, t, quat):
    if len(ts) == 1 or t <= ts[0]:
        return vs[0].astype(float) if vs.ndim > 1 else np.array([float(vs[0])])
    if t >= ts[-1]:
        return vs[-1].astype(float)
    i = int(np.searchsorted(ts, t, side='right')) - 1
    a = (t - ts[i]) / max(ts[i + 1] - ts[i], 1e-9)
    v0, v1 = vs[i].astype(float), vs[i + 1].astype(float)
    if quat:
        if v0 @ v1 < 0:
            v1 = -v1
        r = v0 + (v1 - v0) * a
        return r / np.linalg.norm(r)
    return v0 + (v1 - v0) * a


# ------------------------------------------------------------------------------------------------ T-pose detector
def limb_chains(g):
    """{chain start joint name: [joint names]} for Arm_/Leg_/Wing_ chains, from the joint hierarchy."""
    role = lambda n: re.match(r'^(Arm|Leg|Wing)_', n)
    names = {j: g.nodes[j]['name'] for j in g.joints}
    out = {}
    for j in g.joints:
        nm = names[j]
        m = role(nm)
        if not m:
            continue
        par = g.parent.get(j)
        if par in names and role(names[par]) and role(names[par]).group(1) == m.group(1):
            continue
        chain, cur = [nm], j
        while True:
            kids = [c for c in g.nodes[cur].get('children', []) if c in names and role(names[c]) and role(names[c]).group(1) == m.group(1)]
            if not kids:
                break
            cur = kids[0]
            chain.append(names[cur])
        out[nm] = chain
    return out


BIPED_PLANS = ('biped_humanoid', 'biped_tail', 'shell', 'winged')


def tpose_report(g, clip='Idle', t=0.0, plan=None):
    """per limb chain: {role, down (deg from straight down), spread (deg out of the sagittal plane), violation}.

    An arm is T-posed when it sticks out sideways and roughly level (60-125 deg from straight down with most of that
    outward); arms raised overhead or held forward are poses, not T-poses.  Legs only count for upright bipeds (birds and quadrupeds splay theirs naturally)."""
    if clip not in g.anims:
        clip = None
    pos = g.skin(clip, t)
    G = g.globals(clip, t)
    jindex = {g.nodes[j]['name']: k for k, j in enumerate(g.joints)}
    # world-space skin weights per joint
    wj = np.zeros((len(pos), len(g.joints)))
    for k in range(4):
        np.add.at(wj, (np.arange(len(pos)), g.J[:, k]), g.W[:, k])
    out = {}
    for start, chain in limb_chains(g).items():
        root_j = next(j for j in g.joints if g.nodes[j]['name'] == start)
        root = G[root_j][:3, 3]
        cols = [jindex[n] for n in chain]
        w = wj[:, cols].sum(axis=1)
        sel = w > 0.5
        if sel.sum() < 6:
            continue
        pts = pos[sel]
        d = np.linalg.norm(pts - root, axis=1)
        far = pts[d >= np.percentile(d, 85)]
        v = far.mean(0) - root
        role = start.split('_')[0]
        if role == 'Leg' and len(chain) > 1:      # legs are judged by their bones: hip joint -> last joint of the chain
            v = G[next(j for j in g.joints if g.nodes[j]['name'] == chain[-1])][:3, 3] - root
        L = np.linalg.norm(v)
        if L < 1e-6:
            continue
        down = math.degrees(math.acos(float(np.clip(-v[1] / L, -1, 1))))
        spread = math.degrees(math.asin(float(min(1.0, abs(v[0]) / L))))       # glTF: X lateral, Y up, Z forward
        if role == 'Arm':
            bad = ARM_MAX_DOWN < down < 125.0 and spread > 40.0
        elif role == 'Leg':
            bad = spread > LEG_MAX_SPREAD and plan in BIPED_PLANS and re.match(r'^Leg_[LR]?\d*_', start) is not None
        else:
            bad = spread > WING_MAX_SPREAD
        out[start] = dict(role=role, down=down, spread=spread, violation=bool(bad))
    return out


def clip_features(g, samples=12, nv=350):
    """time-aligned skinned vertex positions of every clip: {clip: (samples, nv, 3)} relative to the rest mesh."""
    idx = np.arange(0, len(g.P), max(1, len(g.P) // nv))
    rest = g.skin(None, 0.0, idx)
    out = {}
    for clip, (ch, dur) in g.anims.items():
        arr = []
        for k in range(samples):
            t = dur * k / samples
            arr.append(g.skin(clip, t, idx) - rest)
        out[clip] = np.array(arr)
    return out, rest


def stretch(g, clip, frames=6, nedge=1500):
    """99.5th percentile edge stretch factor (relative to the median stretch, so uniform scaling clips are fine)."""
    js = g.js
    prim = js['meshes'][next(n['mesh'] for n in g.nodes if 'mesh' in n)]['primitives'][0]
    idx = g.acc(prim['indices']).astype(int).reshape(-1, 3)
    step = max(1, len(idx) // nedge)
    tri = idx[::step]
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]]])
    P0 = g.skin(None, 0.0)
    L0 = np.linalg.norm(P0[e[:, 0]] - P0[e[:, 1]], axis=1) + 1e-9
    keep = L0 > 0.012 * g.H          # slivers and seam duplicates (length ~0) would make any ratio meaningless
    if keep.sum() > 30:
        e, L0 = e[keep], L0[keep]
    dur = g.duration(clip)
    worst = 1.0
    for k in range(frames):
        Pk = g.skin(clip, dur * k / frames)
        r = np.linalg.norm(Pk[e[:, 0]] - Pk[e[:, 1]], axis=1) / L0
        r = r / max(np.median(r), 1e-3)
        worst = max(worst, float(np.percentile(r, 99.5)), 1.0 / max(float(np.percentile(r, 0.5)), 1e-3))
    return worst


def _plans():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'pokemon_species_rig.json')
    with open(p) as fh:
        return {k: v['plan'] for k, v in json.load(fh)['species'].items()}


PLANS = _plans()


def main():
    args = sys.argv[1:]
    folder = args[0]
    only = args[args.index('--only') + 1].split(',') if '--only' in args else None
    files = sorted(f for f in os.listdir(folder) if f.endswith('.glb') and (not only or f[:-4] in only))
    worst_down, viol, sig = 0.0, 0, set()
    for f in files:
        g = Glb(os.path.join(folder, f))
        rep = tpose_report(g, plan=PLANS.get(f[:-4]))
        v = [k for k, r in rep.items() if r['violation']]
        viol += len(v)
        worst = max([r['down'] for r in rep.values() if r['role'] == 'Arm'] or [0.0])
        worst_down = max(worst_down, worst)
        sig.add(tuple(sorted(g.jnames)))
        print('%-12s bones=%2d clips=%2d limbs=%d maxArmDown=%5.1f violations=%s' % (f[:-4], len(g.joints), len(g.anims), len(rep), worst, v or '-'))
    print('SUMMARY species=%d tpose_violations=%d max_arm_down=%.1f distinct_signatures=%d' % (len(files), viol, worst_down, len(sig)))
    sys.exit(1 if viol else 0)


if __name__ == '__main__':
    main()

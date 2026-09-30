"""Mesh analysis for the Pokemon rigger (pure numpy, no bpy): geodesic extremities + cross-section centres.

Coordinates are Blender space as gen_rigged_pokemon leaves them: Z up, the creature faces -Y, X is lateral.
`fwd` below means -Y.
"""
import heapq

import numpy as np

try:   # optional speed-up; the heap fallback is fast enough for 14k-vertex meshes
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra as _sp_dijkstra
except Exception:   # pragma: no cover
    _sp_dijkstra = None


def weld(V, tol):
    """ids of unique positions (glTF vertices are split along UV/normal seams)."""
    q = np.round(V / tol).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.reshape(-1)


class Graph:
    """Surface graph on welded positions + bridges between disconnected shells (eyes, spikes, floating parts)."""

    def __init__(self, V, T, H):
        self.V = V
        tol = max(H * 1e-4, 1e-6)
        self.vid = weld(V, tol)
        n = int(self.vid.max()) + 1
        self.n = n
        P = np.zeros((n, 3))
        P[self.vid] = V
        self.P = P
        e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        a, b = self.vid[e[:, 0]], self.vid[e[:, 1]]
        k = a != b
        a, b = a[k], b[k]
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        key = np.unique(lo * n + hi)
        self.ea, self.eb = key // n, key % n
        self._bridge(H)

    def _components(self):
        parent = np.arange(self.n)

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a, b in zip(self.ea.tolist(), self.eb.tolist()):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        return np.array([find(i) for i in range(self.n)])

    def _bridge(self, H):
        """Join every shell to the biggest one with its single closest vertex pair, so distances stay finite."""
        comp = self._components()
        labels, counts = np.unique(comp, return_counts=True)
        if len(labels) == 1:
            return
        main = labels[np.argmax(counts)]
        in_main = comp == main
        ea, eb = [self.ea], [self.eb]
        base = np.nonzero(in_main)[0]
        for lb in labels:
            if lb == main:
                continue
            idx = np.nonzero(comp == lb)[0]
            if len(idx) > 400:
                sel = idx[:: len(idx) // 400]
            else:
                sel = idx
            bsel = base[:: max(1, len(base) // 3000)]
            d = np.linalg.norm(self.P[sel][:, None, :] - self.P[bsel][None, :, :], axis=2)
            i, j = np.unravel_index(np.argmin(d), d.shape)
            ea.append(np.array([sel[i]]))
            eb.append(np.array([bsel[j]]))
            base = np.concatenate([base, idx])
        self.ea, self.eb = np.concatenate(ea), np.concatenate(eb)

    def dijkstra(self, src):
        """geodesic distance and predecessor from welded vertex `src`."""
        w = np.linalg.norm(self.P[self.ea] - self.P[self.eb], axis=1) + 1e-9
        if _sp_dijkstra is not None:
            m = csr_matrix((np.concatenate([w, w]), (np.concatenate([self.ea, self.eb]), np.concatenate([self.eb, self.ea]))),
                           shape=(self.n, self.n))
            d, pred = _sp_dijkstra(m, indices=src, return_predecessors=True)
            return d, pred
        adj = [[] for _ in range(self.n)]
        for a, b, x in zip(self.ea.tolist(), self.eb.tolist(), w.tolist()):
            adj[a].append((b, x))
            adj[b].append((a, x))
        d = np.full(self.n, np.inf)
        pred = np.full(self.n, -9999, dtype=np.int64)
        d[src] = 0
        pq = [(0.0, src)]
        while pq:
            dd, u = heapq.heappop(pq)
            if dd > d[u]:
                continue
            for v, x in adj[u]:
                nd = dd + x
                if nd < d[v]:
                    d[v] = nd
                    pred[v] = u
                    heapq.heappush(pq, (nd, v))
        return d, pred

    def path(self, pred, tip):
        out = [tip]
        while pred[out[-1]] >= 0:
            out.append(int(pred[out[-1]]))
        return out[::-1]


def find_tips(g, root_pos, H, max_tips=24, min_len=0.10):
    """Protrusions of the surface by topological persistence of the geodesic distance from the root.

    Vertices are swept from far to near; every local maximum opens a component and two components merging
    at level d close the lower one with persistence (peak - d).  A limb, ear or tail therefore survives with a
    persistence about its own length, while bumps on the torso die young.  Returns
    (root, pred, d_root, [(vertex, d_root, persistence, merge_vertex)]) sorted by persistence, largest first.
    """
    root = int(np.argmin(np.linalg.norm(g.P - root_pos, axis=1)))
    d_root, pred = g.dijkstra(root)
    d_root = np.where(np.isfinite(d_root), d_root, 0.0)
    adj = [[] for _ in range(g.n)]
    for a, b in zip(g.ea.tolist(), g.eb.tolist()):
        adj[a].append(b)
        adj[b].append(a)
    order = np.argsort(-d_root)
    seen = np.zeros(g.n, dtype=bool)
    parent = np.arange(g.n)
    peak = d_root.copy()          # per component root: its highest vertex' distance
    top = np.arange(g.n)          # ... and that vertex

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    found = []
    for v in order.tolist():
        seen[v] = True
        comps = {find(u) for u in adj[v] if seen[u]}
        if not comps:
            continue
        comps = sorted(comps, key=lambda c: -peak[c])
        keep = comps[0]
        parent[v] = keep
        for c in comps[1:]:
            found.append((int(top[c]), float(peak[c]), float(peak[c] - d_root[v]), int(v)))
            parent[c] = keep
    # the global maximum never dies: it is a tip of infinite persistence
    gm = int(order[0])
    found.append((gm, float(d_root[gm]), float(d_root[gm]), root))
    found = [f for f in found if f[2] >= min_len * H]
    found.sort(key=lambda f: -f[2])
    return root, pred, d_root, found[:max_tips]


def section_center(V, p, axis, half_width, thickness):
    """centroid of the vertices lying within `thickness` of the plane through p (normal axis) and `half_width` of p."""
    a = axis / (np.linalg.norm(axis) + 1e-12)
    rel = V - p
    along = rel @ a
    perp = np.linalg.norm(rel - along[:, None] * a, axis=1)
    m = (np.abs(along) < thickness) & (perp < half_width)
    if m.sum() < 3:
        return p
    return V[m].mean(0)


def resample(poly, n):
    """n+1 points evenly spaced by arc length along the polyline."""
    poly = np.asarray(poly, dtype=float)
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < 1e-9:
        return np.repeat(poly[:1], n + 1, axis=0)
    u = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(u, s, poly[:, k]) for k in range(3)], axis=1)


def centered_chain(V, g, pred, tip, root_v, n, H, radius=0.07):
    """Skeleton chain from a tip back to its branch with the trunk: geodesic path pulled to section centroids."""
    pth = g.path(pred, tip)
    pts = g.P[pth]
    if len(pts) < 3:
        return resample(pts, n)
    pts = resample(pts, max(n * 3, 6))
    out = []
    for i, p in enumerate(pts):
        a = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        out.append(section_center(V, p, a, radius * H, 0.03 * H))
    out = np.array(out)
    out[0] = out[0]
    return resample(out, n)

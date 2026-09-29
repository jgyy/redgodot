"""Mesh plumbing for the realistic characters: marching cubes -> decimate -> project back onto the field,
adjacency / smoothing helpers, region masks and BVH queries (bpy's mathutils).
"""
import numpy as np

import bpy  # noqa: F401  (mathutils is only importable once bpy is loaded)

import char_sdf as S


# ----------------------------------------------------------------------------- bpy <-> numpy
def to_bpy_mesh(name, V, F):
    import bpy
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', np.asarray(V, np.float32).reshape(-1))
    me.loops.add(len(F) * 3)
    me.loops.foreach_set('vertex_index', np.asarray(F, np.int32).reshape(-1))
    me.polygons.add(len(F))
    me.polygons.foreach_set('loop_start', np.arange(0, len(F) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(F), 3, np.int32))
    me.update(calc_edges=True)
    return me


def from_bpy_mesh(me):
    V = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', V)
    n = len(me.polygons)
    F = np.empty(n * 3, np.int32)
    me.polygons.foreach_get('vertices', F)
    return V.reshape(-1, 3).astype(np.float64), F.reshape(-1, 3).astype(np.int64)


def decimate(V, F, ratio, importance=None, iters=1):
    """Blender collapse decimation; `importance` (n,) in 0..1 keeps detail where high (face, hands)."""
    import bpy
    me = to_bpy_mesh('dec_src', V, F)
    ob = bpy.data.objects.new('dec_src', me)
    bpy.context.scene.collection.objects.link(ob)
    md = ob.modifiers.new('dec', 'DECIMATE')
    md.decimate_type = 'COLLAPSE'
    md.ratio = float(ratio)
    md.use_collapse_triangulate = True
    md.use_symmetry = False
    if importance is not None:
        vg = ob.vertex_groups.new(name='imp')
        imp = np.clip(1.0 - importance, 0.001, 1.0)      # group weight = how eagerly a vertex is collapsed
        for w in np.unique(np.round(imp, 2)):
            idx = np.where(np.round(imp, 2) == w)[0]
            vg.add(idx.tolist(), float(w), 'REPLACE')
        md.vertex_group = 'imp'
        md.vertex_group_factor = 1.0
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me2 = ev.to_mesh()
    V2, F2 = from_bpy_mesh(me2)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return V2, F2


# ----------------------------------------------------------------------------- topology
def adjacency(nv, F):
    """CSR-like neighbour lists (list of arrays)."""
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    order = np.lexsort((e[:, 1], e[:, 0]))
    e = e[order]
    keep = np.ones(len(e), bool)
    keep[1:] = (e[1:] != e[:-1]).any(1)
    e = e[keep]
    start = np.searchsorted(e[:, 0], np.arange(nv + 1))
    return [e[start[i]:start[i + 1], 1] for i in range(nv)]


def smooth_attr(A, F, iters=4, lam=0.5, nbrs=None):
    """Laplacian smoothing of a per-vertex array (vectorised via edge lists)."""
    nv = len(A)
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    deg = np.bincount(e[:, 0], minlength=nv).astype(float)
    deg = np.maximum(deg, 1)
    A = np.asarray(A, float)
    for _ in range(iters):
        acc = np.zeros_like(A)
        np.add.at(acc, e[:, 0], A[e[:, 1]])
        mean = acc / (deg[:, None] if A.ndim > 1 else deg)
        A = A * (1 - lam) + mean * lam
    return A


def face_normals(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return np.cross(b - a, c - a)


def vertex_normals(V, F):
    fn = face_normals(V, F)
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def bvh(V, F):
    from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons([tuple(map(float, v)) for v in V], [tuple(int(i) for i in f) for f in F], epsilon=0.0)


def nearest(tree, pts):
    """-> (loc (n,3), normal (n,3), face index (n,), dist (n,))  for each point."""
    from mathutils import Vector
    loc = np.zeros((len(pts), 3))
    nor = np.zeros((len(pts), 3))
    idx = np.zeros(len(pts), np.int64)
    dist = np.zeros(len(pts))
    for i, p in enumerate(pts):
        l, n, ix, d = tree.find_nearest(Vector((float(p[0]), float(p[1]), float(p[2]))))
        if l is None:
            dist[i] = 1e9
            continue
        loc[i] = (l.x, l.y, l.z)
        nor[i] = (n.x, n.y, n.z)
        idx[i] = ix
        dist[i] = d
    return loc, nor, idx, dist


def cluster_simplify(V, F, size, jitter=0.31):
    """Graded vertex-clustering decimation.  `size` (n,) is the wanted cell edge at each vertex; vertices that fall in
    the same (size level, grid cell) merge.  It is a pure vertex map, so regions of different density stay welded
    (no cracks) -- unlike per-region decimation.  Cluster positions are the members' mean; the caller projects
    them back onto the field."""
    levels = np.geomspace(max(size.min(), 1e-3), size.max(), 14) if size.max() > size.min() * 1.01 else np.array([size.min()])
    lev = np.abs(np.log(size[:, None]) - np.log(levels[None, :])).argmin(1)
    cs = levels[lev]
    off = jitter * cs[:, None] * np.array([1.0, 0.71, 0.53])[None, :]
    cell = np.floor((V + off) / cs[:, None]).astype(np.int64)
    key = np.concatenate([lev[:, None].astype(np.int64), cell - cell.min(0)], 1)
    mx = key.max(0) + 1
    flat = ((key[:, 0] * mx[1] + key[:, 1]) * mx[2] + key[:, 2]) * mx[3] + key[:, 3]
    uniq, inv = np.unique(flat, return_inverse=True)
    n = len(uniq)
    cnt = np.bincount(inv, minlength=n).astype(float)
    Vn = np.stack([np.bincount(inv, weights=V[:, k], minlength=n) / cnt for k in range(3)], 1)
    Fn = inv[F]
    ok = (Fn[:, 0] != Fn[:, 1]) & (Fn[:, 1] != Fn[:, 2]) & (Fn[:, 2] != Fn[:, 0])
    Fn = Fn[ok]
    srt = np.sort(Fn, axis=1)
    _, first = np.unique(srt, axis=0, return_index=True)
    Fn = Fn[np.sort(first)]
    # drop unreferenced vertices
    used = np.zeros(n, bool)
    used[Fn.reshape(-1)] = True
    remap = -np.ones(n, np.int64)
    remap[used] = np.arange(used.sum())
    return Vn[used], remap[Fn]


def make_surface(field, lo, hi, h, size_fn, log=None, relax=2):
    """Field -> graded, field-projected, welded surface: (V, F, N)."""
    V, F = S.isosurface(field, lo, hi, h)
    V = S.project(field, V, iters=2)
    if log:
        log('  marching cubes: %d verts %d tris' % (len(V), len(F)))
    V, F = cluster_simplify(V, F, size_fn(V))
    V = S.project(field, V, iters=3)
    for _ in range(relax):                      # even out the clustered triangles, then snap back to the skin
        V = smooth_attr(V, F, iters=1, lam=0.5)
        V = S.project(field, V, iters=2)
    N = S.field_normals(field, V)
    # winding: counter-clockwise seen from outside (marching cubes gives the opposite for an inside-negative field)
    fn = face_normals(V, F)
    flip = (fn * N[F].sum(1)).sum(1) < 0
    F = np.where(flip[:, None], F[:, ::-1], F)
    return V, F, N

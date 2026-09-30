"""Offset shells cut from the body surface: clothing that follows the skin with thickness, clean hems and no clipping.

A shell is the body triangle mesh, clipped by a smooth scalar (so hems, cuffs and collars are exact level
lines, not mesh-edge staircases), pushed out along the body normals by a per-vertex thickness, and closed at the
clip boundary with a small rim wall down to the skin.  Because it is derived from the very same vertices, it
inherits their skin weights and deforms with the body.
"""
import math

import numpy as np

import char_geo as G
import char_mesh as M


# ----------------------------------------------------------------------------- clipping
def clip_mesh(V, F, vals, attrs=None):
    """Keep the part of the mesh where vals >= 0.  Triangles crossing the zero level are split; new vertices are
    linear blends of the edge ends.  Returns (V2, F2, attrs2, src) where src (m, 2) gives the two original vertices
    and blend factor for every output vertex ((i, i, 0) for kept originals)."""
    attrs = attrs or {}
    n = len(V)
    inside = vals >= 0
    ins = inside[F]
    cnt = ins.sum(1)
    keep_full = F[cnt == 3]
    new_V = [V]
    new_attr = {k: [a] for k, a in attrs.items()}
    src_a = [np.arange(n)]
    src_b = [np.arange(n)]
    src_t = [np.zeros(n)]
    edge_cache = {}
    extra = []

    def edge_vertex(a, b):
        key = (a, b) if a < b else (b, a)
        if key in edge_cache:
            return edge_cache[key]
        va, vb = vals[key[0]], vals[key[1]]
        t = va / (va - vb)
        idx = n + len(extra)
        extra.append((key[0], key[1], t))
        edge_cache[key] = idx
        return idx

    out = [keep_full]
    tris = []
    for f, c in zip(F[(cnt == 1) | (cnt == 2)], cnt[(cnt == 1) | (cnt == 2)]):
        i0, i1, i2 = f
        # rotate so that the lone vertex (inside for c == 1, outside for c == 2) comes first
        flags = [inside[i0], inside[i1], inside[i2]]
        if c == 1:
            k = flags.index(True)
        else:
            k = flags.index(False)
        a, b, cc = f[k], f[(k + 1) % 3], f[(k + 2) % 3]
        e1 = edge_vertex(a, b)
        e2 = edge_vertex(a, cc)
        if c == 1:
            tris.append((a, e1, e2))
        else:
            # a is outside; b, cc inside: quad (e1, b, cc, e2)
            tris.append((e1, b, cc))
            tris.append((e1, cc, e2))
    if extra:
        ea = np.array([e[0] for e in extra])
        eb = np.array([e[1] for e in extra])
        et = np.array([e[2] for e in extra])
        new_V.append(V[ea] * (1 - et)[:, None] + V[eb] * et[:, None])
        for k, a in attrs.items():
            aa = np.asarray(a)
            t = et[:, None] if aa.ndim > 1 else et
            new_attr[k].append(aa[ea] * (1 - t) + aa[eb] * t)
        src_a.append(ea)
        src_b.append(eb)
        src_t.append(et)
    if tris:
        out.append(np.array(tris, np.int64))
    F2 = np.concatenate(out) if len(out) else np.zeros((0, 3), np.int64)
    V2 = np.concatenate(new_V)
    at2 = {k: np.concatenate(v) for k, v in new_attr.items()}
    # drop unreferenced vertices
    used = np.zeros(len(V2), bool)
    used[F2.reshape(-1)] = True
    remap = -np.ones(len(V2), np.int64)
    remap[used] = np.arange(used.sum())
    sa = np.concatenate(src_a)[used]
    sb = np.concatenate(src_b)[used]
    st = np.concatenate(src_t)[used]
    return V2[used], remap[F2], {k: v[used] for k, v in at2.items()}, (sa, sb, st)


def boundary_edges(F):
    """Directed boundary edges (a, b) of a triangle set (edges used by exactly one triangle), orientation as in the triangle."""
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    key = np.sort(e, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    return e[cnt[inv.reshape(-1)] == 1]


# ----------------------------------------------------------------------------- shells
def shell_from_body(ctx, cut, thick, cell, name='shell', g=None, rim=0.025, rim_cell=None, bone=None, cover=True,
                    wobble=0.0, seed=0, close_rim=True, weights_from='body', g_fn=None, extra_attrs=None, offset_vec=None):
    """cut: (n_body,) array, keep where >= 0.   thick: scalar or (n_body,) array (world rows, along the body normal).
    g: optional (n_body,) gradient parameter (0..1) for the texture cell; g_fn(V, Nout, body_idx) alternative."""
    B = ctx.body
    n = len(B.V)
    th = np.broadcast_to(np.asarray(thick, float), (n,)).copy() * getattr(B, 'relief', 1.0)
    attrs = {'V': B.V, 'N': B.Ns, 'th': th, 'ao': np.zeros(n)}
    if offset_vec is not None:
        attrs['ov'] = np.asarray(offset_vec, float)          # extra displacement (hair clumps): (n_body, 3)
    if g is not None:
        attrs['g'] = np.broadcast_to(np.asarray(g, float), (n,)).copy()
    if extra_attrs:
        attrs.update(extra_attrs)
    for b, a in B.w.items():
        attrs['w_' + b] = a
    # only triangles touching the kept side matter -> cheap: pre-select
    Fsel = B.F[(cut[B.F] >= 0).any(1)]
    V2, F2, at, src = clip_mesh(B.V, Fsel, cut, attrs)
    if len(F2) == 0:
        return None
    Vb, Nb = at['V'], at['N']
    Nb = Nb / np.maximum(np.linalg.norm(Nb, axis=1, keepdims=True), 1e-9)
    t = at['th'].copy()
    if wobble:
        t += wobble * _noise(Vb, seed)
    Vs = Vb + Nb * t[:, None] + (at['ov'] if 'ov' in at else 0.0)
    parts_V, parts_F = [Vs], [F2]
    src_idx = [np.arange(len(Vs))]
    if close_rim:
        be = boundary_edges(F2)
        if len(be):
            bv = np.unique(be.reshape(-1))
            m = -np.ones(len(Vs), np.int64)
            m[bv] = np.arange(len(bv))
            ring = Vb[bv] + Nb[bv] * rim
            base = len(Vs)
            parts_V.append(ring)
            src_idx.append(bv)
            walls = []
            for a, b in be:
                ra, rb = base + m[a], base + m[b]
                d = Vs[b] - Vs[a]
                nn = Nb[a] + Nb[b]
                right = np.cross(d, nn)               # outward from the kept region
                for tri in ((a, ra, rb), (a, rb, b)):
                    p0, p1, p2 = [(Vs[x] if x < base else ring[x - base]) for x in tri]
                    nrm = np.cross(p1 - p0, p2 - p0)
                    walls.append(tri if nrm @ right >= 0 else (tri[0], tri[2], tri[1]))
            parts_F.append(np.array(walls, np.int64))
    V3 = np.concatenate(parts_V)
    F3 = np.concatenate(parts_F)
    sidx = np.concatenate(src_idx)
    g3 = at['g'][sidx] if 'g' in at else np.full(len(V3), 0.5)
    part = G.Part(name, V3, F3, cell, g=g3)
    part.w = {k[2:]: v[sidx] for k, v in at.items() if k.startswith('w_')}
    part.body_vert = sidx                                  # index into the clipped source vertex list (for extra attrs)
    part.src_attrs = {k: v[sidx] for k, v in at.items() if k not in ('V', 'N') and not k.startswith('w_')}
    part.src_pos = at['V'][sidx]
    part.src_nrm = Nb[sidx]
    part.N = None
    if g_fn is not None:
        part.g = g_fn(part)
    inside = cut > 0.0
    B.layer[inside] = np.maximum(B.layer[inside], th[inside])
    if cover:
        mark_covered(ctx, cut, margin=rim)
    return part


def mark_covered(ctx, cut, margin=0.0):
    """Body vertices with cut > margin margin (strictly inside the clip) are hidden by the shell."""
    B = ctx.body
    ctx.covered |= cut > 0.02


def _noise(P, seed=0, freq=1.0):
    rng = np.random.default_rng(seed + 17)
    acc = np.zeros(len(P))
    for k in range(4):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        acc += np.sin(P @ d * (0.9 + 0.7 * k) * freq + rng.uniform(0, 6.28)) / (1 + k * 0.6)
    return acc / 2.2


# ----------------------------------------------------------------------------- ring lofts (skirts, hems, bands)
def ring_loft(centers, radii_fn, z_levels, seg=28, cell='cloth', name='ring', close_top=False, e=2.0, g0=0.0, g1=1.0):
    """Radial loft: at every z a closed curve given by radii_fn(z, angle) -> (radius, cx, cy) around a centre.

    Returns a Part (open at both ends unless close_top)."""
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    rows = []
    for z in z_levels:
        r, cx, cy = radii_fn(z, ang)
        rows.append(np.stack([cx + r * np.sin(ang), cy - r * np.cos(ang), np.full(seg, z)], 1))
    Vv = np.concatenate(rows)
    nz = len(z_levels)
    Ff = []
    for i in range(nz - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            c, d = (i + 1) * seg + j, (i + 1) * seg + (j + 1) % seg
            Ff += [(a, b, d), (a, d, c)]
    g = np.repeat(np.linspace(g0, g1, nz), seg)
    return G.Part(name, Vv, np.array(Ff, np.int64), cell, g=g)

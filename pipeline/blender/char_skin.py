"""Skin weights for the welded body.

Every anatomy primitive carries the name of the bone that owns it (char_anat.py sets Field.cur_tag), so a vertex's
weights come straight from how close it is to each bone's own primitives (softmax of the raw distances), the
trunk is then split hips / spine / chest by height, and the result is relaxed over the mesh so elbows, knees,
shoulders and hips bend smoothly instead of hinging.
"""
import numpy as np

import char_geo as G
import char_mesh as M


def smooth01(a, b, x):
    return G.smoothstep(a, b, x)


def body_weights(field, P, V, F, tau=0.16, relax=2):
    D = field.tag_dists(V)
    tags = sorted(D)
    A = np.stack([D[t] for t in tags], 1)
    W = np.exp(-(A - A.min(1, keepdims=True)) / tau)
    W /= W.sum(1, keepdims=True)
    out = {}
    z = V[:, 2]
    for i, t in enumerate(tags):
        if t == 'trunk':
            w_h = 1.0 - smooth01(P.waist - 1.1, P.waist + 0.6, z)
            w_c = smooth01(P.chest - 0.9, P.chest + 0.9, z)
            w_s = np.clip(1.0 - w_h - w_c, 0, 1)
            for b, w in (('hips', w_h), ('spine', w_s), ('chest', w_c)):
                out[b] = out.get(b, 0) + W[:, i] * w
        else:
            out[t] = out.get(t, 0) + W[:, i]
    names = list(out)
    Mx = np.stack([out[n] for n in names], 1)
    for _ in range(relax):
        Mx = M.smooth_attr(Mx, F, iters=1, lam=0.5)
    Mx = np.maximum(Mx, 0)
    Mx /= np.maximum(Mx.sum(1, keepdims=True), 1e-9)
    return {n: Mx[:, k] for k, n in enumerate(names)}


def transfer_weights(body_V, body_F, body_w, pts, tree=None, k=1):
    """Copy skin weights from the nearest body surface point (barycentre-free: nearest vertex of the nearest face)."""
    tree = tree or M.bvh(body_V, body_F)
    loc, nor, idx, dist = M.nearest(tree, pts)
    f = body_F[idx]
    d = np.linalg.norm(body_V[f] - loc[:, None, :], axis=2)
    w = 1.0 / (d + 0.05) ** 2
    w /= w.sum(1, keepdims=True)
    out = {}
    for b, arr in body_w.items():
        out[b] = (arr[f] * w).sum(1)
    return out

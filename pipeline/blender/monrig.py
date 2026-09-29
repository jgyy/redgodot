"""Skeleton + smooth skin weights for a Pokemon mesh (numpy only, no bpy).

Input : the final mesh (Blender coordinates, sprite px units: X right, Y depth (front = -Y),
        Z up), per-vertex soft group weights and per-group facts.
Output: a bone hierarchy (one bone per art group, plus secondary chains along tails, necks,
        legs, ears, wings and serpent bodies) and up to 4 blended influences per vertex.

Bones all point +Z with no roll (build_armature's convention), so animation deltas
expressed in world axes are also the local deltas -- the animation module relies on it.
"""
import math
import re

import numpy as np

# ----------------------------------------------------------------------------- roles
_ROLE_RULES = [
    ('head', r'^(head|skull|face|dome|hd)\w*$'),
    ('jaw', r'^(jaw|mouth|lip|beak|tongue|snout|mand|bill)\w*'),
    ('ear', r'^(ear|antenna|ant\d?$|anten|antB|antF)\w*'),
    ('horn', r'^(horn|crest|tusk|tooth|fang|spike|spk|sp\d|nose|nos|str|fore|hair|tuft|mane|ruff|frill|comb|cap|stalk|eye|must|cheek|gem|coin)\w*'),
    ('neck', r'^(neck|stem|trunk|trnk)\w*'),
    ('hand', r'^(hand|fist|glove|claw|blade|cuff|spoon|pincer|scythe)\w*'),
    ('body', r'^(sh[BF]|shoulder)\w*'),
    ('arm', r'^(arm)\w*'),
    ('foot', r'^(foot|feet|paw|hoof|shoe|toe)\w*'),
    ('leg', r'^(leg|knee|thigh)\w*'),
    ('wing', r'^(wing|w[UL]?[FNB]?[UL]?\d?$|wF|wN|fin|pect|dorsal|pelv|tfin|ridge|dfin|tailfin)\w*'),
    ('tail', r'^(tail|t\d|nt\d|tent|ten\d|rattle|tip|curl|coil|vine|root|whip|tailF)\w*'),
    ('leaf', r'^(leaf|lf|petal|frond|bud|p[BLRF]\d?$|ctr|lfL|lfR)\w*'),
    ('body', r'^(body|torso|shell|thx|abd|chest|belly|pouch|hip|s\d+|seg\d+|coil\d|core|gas|ball|b\d)\w*'),
]


def role_of(name):
    for role, pat in _ROLE_RULES:
        if re.match(pat, name, re.I):
            return role
    return 'other'


# roles a group of the given role may hang from, in preference order
_PARENT_ROLES = {
    'head': ['neck', 'body'],
    'neck': ['body'],
    'jaw': ['head', 'body'],
    'ear': ['head', 'body'],
    'horn': ['head', 'body'],
    'arm': ['body', 'neck'],
    'hand': ['arm', 'body'],
    'leg': ['body'],
    'foot': ['leg', 'body'],
    'wing': ['body'],
    'tail': ['body'],
    'leaf': ['body', 'neck', 'head'],
    'other': ['body', 'head', 'neck'],
    'body': [],
}


# ----------------------------------------------------------------------------- geometry helpers
def _edges(tris):
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]], axis=0)
    e = np.sort(e, axis=1)
    return np.unique(e, axis=0)


def geodesic(P, edges, sources, mask=None, iters=600):
    """Shortest path lengths along mesh edges from `sources` (Bellman-Ford, vectorised)."""
    n = len(P)
    d = np.full(n, np.inf)
    d[sources] = 0.0
    L = np.linalg.norm(P[edges[:, 0]] - P[edges[:, 1]], axis=1)
    if mask is not None:
        ok = mask[edges[:, 0]] & mask[edges[:, 1]]
        edges, L = edges[ok], L[ok]
    a, b = edges[:, 0], edges[:, 1]
    for _ in range(iters):
        nd = d.copy()
        np.minimum.at(nd, a, d[b] + L)
        np.minimum.at(nd, b, d[a] + L)
        if np.array_equal(nd, d):
            break
        d = nd
    return d


def smooth_weights(W, edges, iters=2, keep=0.5):
    n = len(W)
    for _ in range(iters):
        acc = np.zeros_like(W)
        cnt = np.zeros(n)
        np.add.at(acc, edges[:, 0], W[edges[:, 1]])
        np.add.at(acc, edges[:, 1], W[edges[:, 0]])
        np.add.at(cnt, edges[:, 0], 1)
        np.add.at(cnt, edges[:, 1], 1)
        avg = acc / np.maximum(cnt, 1)[:, None]
        W = keep * W + (1 - keep) * avg
    return W


class Rig:
    pass


def _extent(V):
    """(length along the principal axis, thickness across it) of a point cloud."""
    c = V - V.mean(0)
    u, s, vt = np.linalg.svd(c, full_matrices=False)
    proj = c @ vt[0]
    length = float(proj.max() - proj.min())
    rest = c - np.outer(proj, vt[0])
    thick = float(2.0 * math.sqrt((rest ** 2).sum(1).mean() / 2.0)) * 1.6 + 1e-3
    return length, thick


def auto_chain(role, V):
    """Number of chain bones for elongated groups (0/1 = a single bone)."""
    if len(V) < 30:
        return 0
    length, thick = _extent(V)
    if role == 'tail':
        if length > 2.2 * thick and length > 6:
            return int(np.clip(round(length / 4.5), 3, 8))
    elif role == 'neck':
        if length > 1.5 * thick:
            return 3
    elif role == 'body':
        if length > 3.0 * thick and length > 24:
            return int(np.clip(round(length / 5.0), 5, 10))
    elif role in ('leg', 'arm'):
        if length > 2.3 * thick and length > 7:
            return 2
    elif role == 'ear':
        if length > 2.4 * thick and length > 8:
            return 3 if length > 18 else 2
    elif role == 'wing':
        if length > 10:
            return 2
    return 0


def build(names, P, tris, W, ginfo, chain_hint=None, role_hint=None):
    """
    names : group names (order of W columns)
    P     : (n,3) vertex positions, Blender coords in sprite px
    tris  : (m,3)
    W     : (n,G) raw soft weights (already >=0)
    ginfo : {name: dict(area=, cd=, anchor=bool)}
    chain_hint : {name: n_bones} overrides automatic chain detection
    role_hint  : {name: role} overrides the name-based role
    """
    G = len(names)
    edges = _edges(tris)
    W = smooth_weights(W, edges, iters=2, keep=0.5)
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-9)
    owner = W.argmax(1)
    roles = {g: role_of(g) for g in names}
    if role_hint:
        roles.update({g: r for g, r in role_hint.items() if g in roles})
    anchor = next((g for g in names if ginfo[g].get('anchor')), names[0])
    roles[anchor] = 'body'
    cen, count = {}, {}
    for gi, g in enumerate(names):
        sel = owner == gi
        if sel.sum() < 4:
            sel = W[:, gi] > 0.2
        if sel.sum() == 0:
            sel = np.zeros(len(P), dtype=bool)
            sel[int(np.argmax(W[:, gi]))] = True
        cen[g] = P[sel].mean(0)
        count[g] = int(sel.sum())
    rng = np.random.RandomState(7)
    samp = {}
    for gi, g in enumerate(names):
        idx = np.nonzero(W[:, gi] > 0.5)[0]
        if len(idx) == 0:
            idx = np.array([int(np.argmax(W[:, gi]))])
        if len(idx) > 300:
            idx = rng.choice(idx, 300, replace=False)
        samp[g] = idx

    def contact(a, b):
        A, B = P[samp[a]], P[samp[b]]
        d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
        i, j = np.unravel_index(int(np.argmin(d)), d.shape)
        return float(d[i, j]), A[i], B[j]

    parent = {}
    contactpt = {}
    has_head = any(roles[g] == 'head' for g in names)
    for g in names:
        if g == anchor:
            parent[g] = None
            continue
        want = list(_PARENT_ROLES.get(roles[g], ['body']))
        best = None
        for pref_i, r in enumerate(want):
            if r == 'body':
                cands = [h for h in names if h != g and (roles[h] == 'body' or h == anchor)]
            else:
                cands = [h for h in names if h != g and roles[h] == r]
            for h in cands:
                if r != 'body' and ginfo[h]['area'] < 0.4 * ginfo[g]['area'] and roles[g] not in ('hand', 'foot'):
                    continue
                d, pa, pb = contact(g, h)
                score = d + pref_i * 2.0 - (0.0 if h != anchor else 0.6)
                if best is None or score < best[0]:
                    best = (score, h, d, pa, pb)
        if best is None:
            best = (0, anchor, *contact(g, anchor))
        parent[g] = best[1]
        contactpt[g] = (best[3], best[4], best[2])
    for g in names:           # never emit a cyclic tree
        seen = set()
        cur = g
        while cur is not None and cur not in seen:
            seen.add(cur)
            cur = parent.get(cur)
        if cur is not None:
            parent[g] = anchor
    # ---- pivots (joint at the contact, nudged into the child)
    pivot = {}
    for g in names:
        if g == anchor:
            pivot[g] = cen[g].copy()
        else:
            a = contactpt[g][0]
            pivot[g] = a + (cen[g] - a) * 0.12
    head_grp = next((g for g in names if roles[g] == 'head'), None)

    # ---- bones (with chains)
    bones = []
    cols = []
    chain_of = {}                    # group -> list of bone names
    order = sorted(names, key=lambda g: (0 if g == anchor else 1))
    # process parents before children so child bones can attach to a chain bone
    depth = {}
    for g in names:
        d, cur = 0, g
        while parent.get(cur) is not None:
            cur = parent[cur]
            d += 1
        depth[g] = d
    order = sorted(names, key=lambda g: depth[g])
    for g in order:
        gi = names.index(g)
        w = W[:, gi]
        Vsel = P[w > 0.4]
        if chain_hint is not None and g in chain_hint:
            n_chain = int(chain_hint[g])
        else:
            n_chain = auto_chain(roles[g], Vsel) if len(Vsel) else 0
        par_bone = None
        if parent[g] is not None:
            pc = chain_of[parent[g]]
            if len(pc) == 1:
                par_bone = pc[0]
            else:
                hp = {b['name']: b['head'] for b in bones}
                par_bone = min(pc, key=lambda bn: np.linalg.norm(hp[bn] - pivot[g]))
        made = False
        if n_chain >= 2:
            if g == anchor:
                # serpent / long body: root the chain at the end nearest the head
                target_pt = cen[head_grp] if head_grp else Vsel[np.argmin(Vsel[:, 0])]
                sel_idx = np.nonzero(w > 0.15)[0]
                base = P[sel_idx[np.argmin(np.linalg.norm(P[sel_idx] - target_pt, axis=1))]]
            else:
                base = pivot[g]
            sel = np.nonzero(w > 0.15)[0]
            src = sel[np.argsort(np.linalg.norm(P[sel] - base, axis=1))[:6]]
            dist = geodesic(P, edges, src, mask=(w > 0.05))
            fin = np.isfinite(dist) & (w > 0.05)
            if fin.sum() >= 12:
                L = max(float(np.percentile(dist[fin], 99.5)), 1e-3)
                t = np.clip(np.where(fin, dist / L, 0.0), 0, 1)
                heads = []
                for i in range(n_chain):
                    t0 = i / n_chain
                    sel_i = fin & (t >= t0 - 0.5 / n_chain) & (t < t0 + 0.5 / n_chain) & (w > 0.4)
                    heads.append(P[sel_i].mean(0) if sel_i.sum() >= 3 else None)
                heads[0] = pivot[g] if g != anchor else base
                for i in range(1, n_chain):
                    if heads[i] is None:
                        heads[i] = heads[i - 1] + (cen[g] - heads[i - 1]) * 0.3
                tb = np.array([i / n_chain for i in range(n_chain)])
                prev = par_bone
                names_g = []
                for i in range(n_chain):
                    nm = g if i == 0 else '%s_%d' % (g, i)
                    bones.append(dict(name=nm, group=g, role=roles[g], parent=prev, head=heads[i],
                                      chain=(i, n_chain)))
                    prev = nm
                    names_g.append(nm)
                    if i == 0:
                        h = np.where(t <= tb[1], 1 - (t - tb[0]) / (tb[1] - tb[0]), 0.0)
                    elif i == n_chain - 1:
                        h = np.where(t >= tb[i - 1], np.clip((t - tb[i - 1]) / (tb[i] - tb[i - 1]), 0, 1), 0.0)
                    else:
                        up = np.clip((t - tb[i - 1]) / (tb[i] - tb[i - 1]), 0, 1)
                        dn = np.clip(1 - (t - tb[i]) / (tb[i + 1] - tb[i]), 0, 1)
                        h = np.where(t < tb[i], up, dn)
                    cols.append(w * np.where(fin, h, 1.0 if i == 0 else 0.0))
                chain_of[g] = names_g
                made = True
        if not made:
            bones.append(dict(name=g, group=g, role=roles[g], parent=par_bone, head=pivot[g], chain=None))
            cols.append(w)
            chain_of[g] = [g]
    Wb = np.stack(cols, axis=1)
    n_b = Wb.shape[1]
    if n_b < 4:
        Wb = np.concatenate([Wb, np.zeros((len(P), 4 - n_b))], axis=1)
    top = np.argsort(-Wb, axis=1)[:, :4]
    top = np.minimum(top, n_b - 1)
    rows = np.arange(len(P))[:, None]
    tw = Wb[rows, top]
    if n_b < 4:
        tw[:, n_b:] = 0.0
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    tw[tw < 0.03] = 0.0
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    r = Rig()
    r.bones = bones
    r.bone_names = [b['name'] for b in bones]
    r.influence_idx = top
    r.influence_w = tw
    r.group_weights = W
    r.owner = owner
    r.roles = roles
    r.anchor = anchor
    r.parent = parent
    r.centroid = cen
    r.chain_of = chain_of
    r.edges = edges
    r.group_names = list(names)
    return r

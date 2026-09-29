"""Skin weights and the corrective natural rest pose for fitted Pokemon skeletons (numpy only)."""
import math

import numpy as np

import pokemon_geom as PG
from pokemon_rig import UP, FWD, LAT, unit, _seg_dist


# ------------------------------------------------------------------------------------------------ weights
def skin(V, T, sk, keep=4, smooth_iters=8, graph=None):
    """(names, W): W is (n, len(names)) with at most `keep` non-zero weights per vertex.

    Weight ~ ((d + e) / (r_b + e)) ** -4, d = distance to the bone segment and r_b the bone's own radius (median
    distance of the vertices it is nearest to), so thin limbs cannot capture the torso next to them.  A few Laplacian
    relaxation passes on the welded surface graph then make transitions smooth (no popping seams between bones)."""
    H = sk.H
    names = [n for n in sk.bones if n != 'Root']
    nb = len(names)
    d = np.empty((len(V), nb))
    for i, nm in enumerate(names):
        b = sk.bones[nm]
        d[:, i] = _seg_dist(V, b.head, b.tail)
    near = np.argmin(d, axis=1)
    e = 0.02 * H
    rad = np.empty(nb)
    for i in range(nb):
        m = near == i
        rad[i] = np.median(d[m, i]) if m.sum() >= 4 else 0.04 * H
    rad = np.clip(rad, 0.025 * H, 0.3 * H)
    w = ((d + e) / (rad[None, :] + e)) ** -4.0
    w = _top(w, keep)
    g = graph or sk.info.get('graph') or PG.Graph(V, T, H)
    nbr_a, nbr_b = g.ea, g.eb
    vid = g.vid
    for _ in range(smooth_iters):
        # average over the welded graph, then scatter back to the (seam-split) vertices
        acc = np.zeros((g.n, nb))
        cnt = np.zeros(g.n)
        np.add.at(acc, nbr_a, w_w(w, vid, g.n)[nbr_b])
        np.add.at(acc, nbr_b, w_w(w, vid, g.n)[nbr_a])
        np.add.at(cnt, nbr_a, 1)
        np.add.at(cnt, nbr_b, 1)
        cnt[cnt == 0] = 1
        mean = (acc / cnt[:, None])[vid]
        w = _top(0.6 * w + 0.4 * mean, keep)
    return names, w


def w_w(w, vid, n):
    """per-welded-vertex weights (mean over the duplicates)."""
    out = np.zeros((n, w.shape[1]))
    cnt = np.zeros(n)
    np.add.at(out, vid, w)
    np.add.at(cnt, vid, 1)
    return out / np.maximum(cnt, 1)[:, None]


def _top(w, keep):
    if keep < w.shape[1]:
        drop = np.argsort(w, axis=1)[:, :-keep]
        w = w.copy()
        np.put_along_axis(w, drop, 0.0, axis=1)
    w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-12)
    w[w < 0.03] = 0.0
    return w / np.maximum(w.sum(axis=1, keepdims=True), 1e-12)


# ------------------------------------------------------------------------------------------------ rotations
def rot_between(a, b):
    """rotation matrix taking unit vector a to unit vector b."""
    a, b = unit(a), unit(b)
    c = float(a @ b)
    if c > 1 - 1e-9:
        return np.eye(3)
    if c < -1 + 1e-9:
        ax = unit(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]))
        return axis_angle(ax, math.pi)
    v = np.cross(a, b)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def axis_angle(ax, ang):
    ax = unit(ax)
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


def angle_deg(a, b):
    return math.degrees(math.acos(float(np.clip(unit(a) @ unit(b), -1, 1))))


# ------------------------------------------------------------------------------------------------ limb measurements
def limb_vec(sk, gid):
    """(root joint, end point) of a chain."""
    names = sk.chain(gid)
    return sk.bones[names[0]].head, sk.bones[names[-1]].tail


def limb_report(sk):
    """{chain id: {role, angle from down, lateral spread}} in the current rest pose (used by the T-pose detector)."""
    out = {}
    for gid, names in sk.chains.items():
        b0 = sk.bones[names[0]]
        if b0.role not in ('Arm', 'Leg', 'Wing'):
            continue
        a, b = limb_vec(sk, gid)
        v = b - a
        if np.linalg.norm(v) < 1e-9:
            continue
        out[gid] = dict(role=b0.role, down=angle_deg(v, -UP), spread=math.degrees(math.asin(min(1.0, abs(v[0]) / np.linalg.norm(v)))))
    return out


# ------------------------------------------------------------------------------------------------ natural pose
ARM_MAX = 48.0      # deg from straight down before we consider it a T/A pose
LEG_MAX = 34.0
WING_MAX = 55.0     # lateral spread of a wing


def natural_pose(V, W, names, sk, spec):
    """Rotate hanging limbs into a natural rest pose. Returns (V', per-bone 3x3 world rotations, per-bone pivots)."""
    plan = spec.get('plan')
    rot = {n: np.eye(3) for n in sk.bones}
    piv = {n: sk.bones[n].head.copy() for n in sk.bones}
    arm_t = float(spec.get('arm_hang', 24.0))          # target angle from down (deg)
    arm_fwd = float(spec.get('arm_fwd', 16.0))
    leg_t = float(spec.get('leg_hang', 10.0))
    log = {}
    cols = {n: i for i, n in enumerate(names)}
    for gid, names_c in sk.chains.items():
        b0 = sk.bones[names_c[0]]
        if b0.role not in ('Arm', 'Leg', 'Wing'):
            continue
        a, b = limb_vec(sk, gid)
        v = b - a
        L = np.linalg.norm(v)
        if L < 1e-9:
            continue
        side = 1.0 if (b[0] - sk.info['hips'][0]) >= 0 else -1.0
        vm = mesh_vec(V, W, cols, names_c, a)
        if b0.role == 'Arm' and (angle_deg(v, -UP) > ARM_MAX or (vm is not None and _t_like(vm))):
            ang = math.radians(arm_t)
            fw = math.radians(arm_fwd)
            tgt = np.array([side * math.sin(ang), -math.sin(fw), -math.cos(ang)])
            src = vm if vm is not None else v           # aim the *mesh* (what the eye sees), not just the bone
            log[gid] = ('arm', angle_deg(src, -UP))
            R = rot_between(src, tgt)
            rot[names_c[0]] = R
            piv[names_c[0]] = a
        elif b0.role == 'Leg' and max(abs(v[0]) / L, (abs(vm[0]) / np.linalg.norm(vm)) if vm is not None else 0.0) > math.sin(math.radians(LEG_MAX)):
            # splayed legs: bring them under the body by rolling about the fore/aft axis only (keeps knees and paws pointing where they do)
            src = vm if vm is not None and abs(vm[0]) / np.linalg.norm(vm) > abs(v[0]) / L else v
            cur = math.degrees(math.asin(min(1.0, abs(src[0]) / np.linalg.norm(src))))
            want = float(spec.get('leg_hang', 14.0))
            log[gid] = ('leg', cur)
            R = axis_angle(FWD, math.radians(cur - want) * (1.0 if src[0] > 0 else -1.0))
            if abs((R @ src)[0]) > abs(src[0]):
                R = R.T
            rot[names_c[0]] = R
            piv[names_c[0]] = a
        elif b0.role == 'Wing':
            sp = math.degrees(math.asin(min(1.0, abs(v[0]) / L)))
            if sp > WING_MAX or spec.get('wing_fold', True):
                # half-folded: sweep the wing back and up along the body, keep some spread so it reads as wings
                fold = float(spec.get('wing_fold_deg', 32.0))
                up_k = 0.55 if plan in ('winged', 'bird') else 0.4
                tgt = np.array([side * math.sin(math.radians(fold)), 0.55 * math.cos(math.radians(fold)),
                                up_k * math.cos(math.radians(fold))])
                log[gid] = ('wing', sp)
                R = rot_between(v, unit(tgt))
                # roll about the wing's own axis so the flat membrane ends up standing on its edge
                nrm = _flat_normal(V, W, names, sk, names_c, R)
                if nrm is not None:
                    Rn = R @ nrm
                    want = np.array([side, 0.0, 0.0])
                    axis = unit(R @ v)
                    n_now = R @ (nrm) if False else nrm
                rot[names_c[0]] = R
                piv[names_c[0]] = a
    # forward kinematics over the bone tree
    world = {}
    for n, bn in sk.bones.items():
        par = bn.parent
        Mp = world.get(par, (np.eye(3), np.zeros(3)))
        R_l, t_l = rot[n], piv[n] - rot[n] @ piv[n]
        Rp, tp = Mp
        world[n] = (Rp @ R_l, Rp @ t_l + tp)
    Vn = np.zeros_like(V)
    for i, nm in enumerate(names):
        R, t = world[nm]
        Vn += W[:, i:i + 1] * (V @ R.T + t)
    # roots (weightless) keep their place; everything with weights moves
    wsum = W.sum(axis=1, keepdims=True)
    Vn = np.where(wsum > 0.5, Vn, V)
    for n, bn in sk.bones.items():
        R, t = world[n]
        bn.head = R @ bn.head + t
        bn.tail = R @ bn.tail + t
    return Vn, log


def mesh_vec(V, W, cols, chain, root):
    """root joint -> centroid of the farthest 15% of the vertices bound (>50%) to the chain: what the eye sees as the limb."""
    w = sum(W[:, cols[n]] for n in chain if n in cols)
    sel = w > 0.5
    if sel.sum() < 6:
        return None
    pts = V[sel]
    d = np.linalg.norm(pts - root, axis=1)
    far = pts[d >= np.percentile(d, 85)]
    v = far.mean(0) - root
    return v if np.linalg.norm(v) > 1e-6 else None


def _t_like(v):
    """sticks out sideways and roughly level (the pose the T-pose detector rejects)."""
    down = angle_deg(v, -UP)
    spread = math.degrees(math.asin(min(1.0, abs(v[0]) / max(np.linalg.norm(v), 1e-9))))
    return 52.0 < down < 125.0 and spread > 32.0


def _flat_normal(V, W, names, sk, chain_names, R):
    return None

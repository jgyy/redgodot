"""Pose algebra shared by the clip authoring code and the tests (numpy only, no bpy).

A `Pose` holds, per bone, a world-axis rotation about the bone's head, a world-space translation and a world-axis scale.
That is exactly what common.ActionWriter.key() takes, so what the tests evaluate is what Blender bakes.
Directions: creatures face -Y, +Z is up, +X is their left.
"""
import math

import numpy as np

UP = np.array([0.0, 0.0, 1.0])
DOWN = -UP
FWD = np.array([0.0, -1.0, 0.0])
BACK = -FWD
LEFT = np.array([1.0, 0.0, 0.0])
RIGHT = -LEFT


def unit(v):
    n = float(np.linalg.norm(v))
    return np.asarray(v, dtype=float) / n if n > 1e-12 else np.array([0.0, 0.0, 1.0])


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def qaxis(axis, deg):
    a = unit(axis)
    h = math.radians(deg) * 0.5
    s = math.sin(h)
    return (math.cos(h), a[0] * s, a[1] * s, a[2] * s)


def qmat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def qslerp(a, b, t):
    d = sum(p * q for p, q in zip(a, b))
    if d < 0:
        b = tuple(-c for c in b)
        d = -d
    if d > 0.9995:
        r = tuple(p + (q - p) * t for p, q in zip(a, b))
    else:
        th = math.acos(d)
        s = math.sin(th)
        r = tuple((math.sin((1 - t) * th) * p + math.sin(t * th) * q) / s for p, q in zip(a, b))
    n = math.sqrt(sum(c * c for c in r))
    return tuple(c / n for c in r)


IDQ = (1.0, 0.0, 0.0, 0.0)


class Pose:
    """accumulates rotations/translations/scales per bone; later calls compose on top of earlier ones."""

    def __init__(self, rig):
        self.rig = rig
        self.q = {}
        self.loc = {}
        self.scl = {}

    # -- raw ------------------------------------------------------------------------------------
    def rotw(self, bone, axis, deg):
        if bone is None or bone not in self.rig.bones or abs(deg) < 1e-9:
            return self
        self.q[bone] = qmul(qaxis(axis, deg), self.q.get(bone, IDQ))
        return self

    def move(self, bone, vec=None, x=0.0, y=0.0, z=0.0):
        if bone is None or bone not in self.rig.bones:
            return self
        v = np.asarray(vec, dtype=float) if vec is not None else np.array([x, y, z], dtype=float)
        self.loc[bone] = self.loc.get(bone, np.zeros(3)) + v
        return self

    def scale(self, bone, sx=1.0, sy=1.0, sz=1.0):
        if bone is None or bone not in self.rig.bones:
            return self
        o = self.scl.get(bone, np.ones(3))
        self.scl[bone] = o * np.array([sx, sy, sz])
        return self

    # -- semantic ---------------------------------------------------------------------------------
    def bend(self, bone, toward, deg):
        """swing the bone's rest direction toward a world direction (degrees; >90 keeps going past it)."""
        if bone is None or bone not in self.rig.bones:
            return self
        d = self.rig.bones[bone].dir
        ax = np.cross(d, unit(toward))
        if np.linalg.norm(ax) < 1e-4:                 # bone already points along/against the target: use the side axis
            ax = np.cross(d, LEFT if abs(d[0]) < 0.9 else UP)
        return self.rotw(bone, ax, deg)

    def twist(self, bone, deg):
        if bone is None or bone not in self.rig.bones:
            return self
        return self.rotw(bone, self.rig.bones[bone].dir, deg)

    def pitch(self, bone, deg):
        """+deg: front of the bone goes UP (look up / rear up)."""
        return self.rotw(bone, LEFT, -deg)

    def yaw(self, bone, deg):
        """+deg: front turns toward +X."""
        return self.rotw(bone, UP, deg)

    def roll(self, bone, deg):
        """+deg: the +X side goes up."""
        return self.rotw(bone, FWD, deg)

    def chain(self, names, toward, total, weights=None):
        """spread `total` degrees of bend over a chain (weights default to equal)."""
        if not names:
            return self
        w = weights or [1.0] * len(names)
        s = sum(w)
        for n, k in zip(names, w):
            self.bend(n, toward, total * k / s)
        return self

    def wave(self, names, toward, amp, u, cycles=1.0, lag=0.5, phase=0.0, taper=(0.4, 1.0)):
        """travelling sine along a chain: bone i bends amp*sin(2pi(cycles*u) - lag*i + phase)."""
        n = len(names)
        for i, b in enumerate(names):
            k = taper[0] + (taper[1] - taper[0]) * (i / max(1, n - 1))
            self.bend(b, toward, amp * k * math.sin(math.tau * cycles * u - lag * i + phase))
        return self

    def copy(self):
        p = Pose(self.rig)
        p.q, p.loc, p.scl = dict(self.q), {k: v.copy() for k, v in self.loc.items()}, {k: v.copy() for k, v in self.scl.items()}
        return p


# ------------------------------------------------------------------------------------------------ evaluation
class Deformer:
    """numpy forward kinematics + linear blend skinning identical in structure to what Blender/Godot do."""

    def __init__(self, sk, V, names, W):
        self.sk = sk
        self.V = np.asarray(V)
        self.names = names
        self.W = W
        self.order = list(sk.bones)

    def world(self, pose):
        M = {}
        for n in self.order:
            b = self.sk.bones[n]
            R = qmat(pose.q.get(n, IDQ))
            S = np.diag(pose.scl.get(n, np.ones(3)))
            A = R @ S
            t = b.head + pose.loc.get(n, 0.0) - A @ b.head
            local = (A, t)
            if b.parent is None:
                M[n] = local
            else:
                Rp, tp = M[b.parent]
                M[n] = (Rp @ A, Rp @ t + tp)
        return M

    def vertices(self, pose, idx=None):
        M = self.world(pose)
        V = self.V if idx is None else self.V[idx]
        W = self.W if idx is None else self.W[idx]
        out = np.zeros_like(V)
        for i, nm in enumerate(self.names):
            col = W[:, i]
            if not col.any():
                continue
            R, t = M[nm]
            out += col[:, None] * (V @ R.T + t)
        return out

    def joints(self, pose):
        """head and tail positions of every bone in the pose (n_bones*2, 3)."""
        M = self.world(pose)
        pts = []
        for n in self.order:
            b = self.sk.bones[n]
            R, t = M[n]
            pts.append(R @ b.head + t)
            pts.append(R @ b.tail + t)
        return np.array(pts)

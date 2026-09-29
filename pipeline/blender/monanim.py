"""Archetype-driven baked animation for the Pokemon rigs (bpy + mathutils).

Every clip is sampled at 30 fps from smooth closed-form motion (no coarse linear keys):

  Idle    2.0 s loop   breathing / hovering / slithering ... per archetype
  Walk    0.533 s loop one full stride cycle = TWO overworld cells (a cell is 0.267 s), first == last frame
  Attack  0.73 s       anticipation - strike - follow-through - recovery, type-flavoured
  Hurt    0.5 s        recoil with a damped spring settle
  Faint   1.2 s        collapse, holds the last frame
  Special 1.0 s        hop-spin / roar / pulse / dance ... per archetype

The archetype ("gait", "attack", "special", "view", "weight") comes from pipeline/data/species_looks.json;
anything missing is inferred from the rig.  Conventions: model front = Blender -Y; up = +Z.  For
side-on sprites ("view": "side") the creature looks toward -X (or +X) in the sprite plane, so limb swings
happen in the sprite plane; for "front" sprites the creature faces the viewer (-Y).
"""
import math

from mathutils import Quaternion, Vector

import common as C

FPS = 30
TAU = 2.0 * math.pi
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))

DUR = {'Idle': 60, 'Walk': 16, 'Attack': 22, 'Hurt': 15, 'Faint': 36, 'Special': 30}
CLIP_INFO = {
    'Idle': {'seconds': DUR['Idle'] / FPS, 'loop': True},
    'Walk': {'seconds': DUR['Walk'] / FPS, 'loop': True, 'cells': 2},
    'Attack': {'seconds': DUR['Attack'] / FPS, 'loop': False},
    'Hurt': {'seconds': DUR['Hurt'] / FPS, 'loop': False},
    'Faint': {'seconds': DUR['Faint'] / FPS, 'loop': False},
    'Special': {'seconds': DUR['Special'] / FPS, 'loop': False},
}


# ============================================================================ curves
def sstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def bump(u, a, b):
    """0 outside [a, b], smooth 0 -> 1 -> 0 inside."""
    if u <= a or u >= b:
        return 0.0
    return math.sin(math.pi * (u - a) / (b - a)) ** 2


def spline(u, keys):
    """Catmull-Rom style curve through (t, v) keys (clamped ends, zero end slopes)."""
    if u <= keys[0][0]:
        return keys[0][1]
    if u >= keys[-1][0]:
        return keys[-1][1]
    for i in range(len(keys) - 1):
        t0, v0 = keys[i]
        t1, v1 = keys[i + 1]
        if t0 <= u <= t1:
            s = (u - t0) / (t1 - t0)
            if i > 0:
                m0 = (v1 - keys[i - 1][1]) / (t1 - keys[i - 1][0])
            else:
                m0 = 0.0
            if i + 2 < len(keys):
                m1 = (keys[i + 2][1] - v0) / (keys[i + 2][0] - t0)
            else:
                m1 = 0.0
            d = t1 - t0
            h00 = 2 * s ** 3 - 3 * s ** 2 + 1
            h10 = s ** 3 - 2 * s ** 2 + s
            h01 = -2 * s ** 3 + 3 * s ** 2
            h11 = s ** 3 - s ** 2
            return h00 * v0 + h10 * d * m0 + h01 * v1 + h11 * d * m1
    return keys[-1][1]


def spring(u, freq=3.0, damp=4.5):
    """Damped oscillation 0 -> 1 -> settle (u in 0..1)."""
    return 1.0 - math.exp(-damp * u) * math.cos(TAU * freq * u * 0.5)


def rad(d):
    return math.radians(d)


# ============================================================================ pose accumulation
class Pose:
    def __init__(self, names):
        self.names = names
        self.q = {}
        self.loc = {}
        self.sc = {}

    def rot(self, b, axis, ang):
        if b not in self.names or abs(ang) < 1e-9:
            return
        q = Quaternion(Vector(axis).normalized(), ang)
        self.q[b] = q @ self.q.get(b, Quaternion())

    def move(self, b, v):
        if b not in self.names:
            return
        self.loc[b] = self.loc.get(b, Vector((0, 0, 0))) + Vector(v)

    def scale(self, b, sx, sy=None, sz=None):
        if b not in self.names:
            return
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        o = self.sc.get(b, Vector((1, 1, 1)))
        self.sc[b] = Vector((o.x * sx, o.y * sy, o.z * sz))


class Writer(C.ActionWriter):
    """ActionWriter that takes a whole Pose per frame (quaternions composed in world axes)."""

    def __init__(self, arm, name, n):
        super().__init__(arm, name, n)
        self.touched = set()

    def key_pose(self, frame, pose):
        for b in set(pose.q) | set(pose.loc) | set(pose.sc):
            bone = self.arm.data.bones[b]
            R = bone.matrix_local.to_3x3()
            Ri = R.transposed()
            lv = Ri @ pose.loc[b] if b in pose.loc else Vector((0, 0, 0))
            if b in pose.q:
                q = pose.q[b]
                ax, an = q.to_axis_angle()
                ql = Quaternion(Ri @ ax, an)
            else:
                ql = Quaternion()
            if b in pose.sc:
                s = pose.sc[b]
                ls = Vector([sum(abs(Ri[i][j]) * s[j] for j in range(3)) for i in range(3)])
            else:
                ls = Vector((1, 1, 1))
            self.keys.setdefault(b, {})[frame] = (lv, ql, ls)
            self.touched.add(b)

    def finalize(self):
        # a bone touched on some frames but not others needs explicit identity keys
        for b in self.touched:
            fr = self.keys[b]
            for f in range(self.n + 1):
                if f not in fr:
                    fr[f] = (Vector((0, 0, 0)), Quaternion(), Vector((1, 1, 1)))


# ============================================================================ skeleton analysis
class Skel:
    def __init__(self, rig, bones, verts_m, owner, look, sp, target, hovering):
        self.look = look or {}
        self.sp = sp
        self.h = target
        self.hover = hovering
        self.names = [b['name'] for b in bones]
        self.bone = {}
        for rb, bb in zip(rig.bones, bones):
            self.bone[bb['name']] = dict(role=rb['role'], group=rb['group'], chain=rb['chain'],
                                         head=Vector(bb['head']), parent=bb['parent'])
        self.bname = {rb['name']: bb['name'] for rb, bb in zip(rig.bones, bones)}
        self.groups = {}
        for rb in rig.bones:
            self.groups.setdefault(rb['group'], []).append(self.bname[rb['name']])
        self.role = {g: rig.roles[g] for g in self.groups}
        self.anchor = rig.anchor
        gi = {g: i for i, g in enumerate(rig.group_names)}
        self.cen, self.tip, self.pivot, self.size = {}, {}, {}, {}
        V = verts_m
        for g, bl in self.groups.items():
            sel = rig.owner == gi[g]
            if sel.sum() < 4:
                sel = rig.group_weights[:, gi[g]] > 0.3
            pts = V[sel] if sel.sum() else V[:1]
            c = pts.mean(0)
            pv = self.bone[bl[0]]['head']
            d = ((pts - [pv.x, pv.y, pv.z]) ** 2).sum(1)
            k = max(3, len(pts) // 20)
            far = pts[d.argsort()[-k:]].mean(0)
            self.cen[g] = Vector(c)
            self.tip[g] = Vector(far)
            self.pivot[g] = pv
            self.size[g] = float(pts.max(0)[2] - pts.min(0)[2]), float(pts.max(0)[0] - pts.min(0)[0])
        lo, hi = V.min(0), V.max(0)
        self.bbox = (Vector(lo), Vector(hi))
        self.width = float(hi[0] - lo[0])
        self.height = float(hi[2] - lo[2])
        self.body_c = self.cen[self.anchor]
        self.body_b = self.groups[self.anchor][0]
        role_groups = {}
        for g, r in self.role.items():
            role_groups.setdefault(r, []).append(g)
        self.by_role = role_groups
        self.heads = role_groups.get('head', [])
        legs = role_groups.get('leg', [])
        if not legs:
            legs = role_groups.get('foot', [])
        self.legs = legs
        self.feet = [g for g in role_groups.get('foot', []) if g not in legs]
        arms = role_groups.get('arm', [])
        if not arms:
            arms = [g for g in role_groups.get('hand', []) if self._parent_role(g) != 'arm']
        self.arms = arms
        self.hands = [g for g in role_groups.get('hand', []) if g not in arms]
        self.wings = role_groups.get('wing', [])
        self.tails = role_groups.get('tail', [])
        self.ears = role_groups.get('ear', [])
        self.horns = role_groups.get('horn', [])
        self.jaws = role_groups.get('jaw', [])
        self.necks = role_groups.get('neck', [])
        self.leaves = role_groups.get('leaf', [])
        self.others = role_groups.get('other', [])
        self.bodies = [g for g in role_groups.get('body', []) if g != self.anchor]
        # facing
        view = self.look.get('view')
        if view is None:
            hc = self.cen[self.heads[0]] if self.heads else None
            if hc is not None and abs(hc.x - self.body_c.x) > 0.13 * self.width:
                view = 'side'
            else:
                view = 'front'
        self.view = view
        if view == 'side':
            sgn = -1.0
            if self.heads:
                sgn = -1.0 if self.cen[self.heads[0]].x < self.body_c.x else 1.0
            if self.look.get('face') in ('left', 'right'):
                sgn = -1.0 if self.look['face'] == 'left' else 1.0
            self.fwd = Vector((sgn, 0, 0))
        else:
            self.fwd = Vector((0, -1, 0))
        self.a_sw = self.fwd.cross(Z).normalized()          # +angle swings a downward limb toward fwd
        self.lat = Z.cross(self.fwd).normalized()
        self.leg_phase = self._phases(self.legs)
        for g in self.feet:
            pg = self.bone[self.groups[g][0]]['parent']
            pgroup = self.bone[pg]['group'] if pg in self.bone else None
            self.leg_phase[g] = self.leg_phase.get(pgroup, 0.0)
        self.arm_phase = {}
        lp = self.leg_phase
        for g in self.arms:
            if lp:
                # opposite of the leg on the same lateral side
                near = min(self.legs, key=lambda l: abs(self._lat(l) - self._lat(g)))
                self.arm_phase[g] = (lp[near] + math.pi) % TAU
            else:
                self.arm_phase[g] = self._phases(self.arms)[g]
        self.leg_len = {g: max(0.02, (self.pivot[g] - self.tip[g]).length) for g in self.legs}

    def _parent_role(self, g):
        p = self.bone[self.groups[g][0]]['parent']
        return self.bone[p]['role'] if p in self.bone else None

    def _lat(self, g):
        d = self.cen[g] - self.body_c
        if self.view == 'side':
            return -d.y            # nearer to the camera = positive
        return d.x

    def _fwdc(self, g):
        return (self.cen[g] - self.body_c).dot(self.fwd)

    def _phases(self, gs):
        out = {}
        if not gs:
            return out
        if len(gs) == 1:
            return {gs[0]: 0.0}
        lat = {g: self._lat(g) for g in gs}
        fw = {g: self._fwdc(g) for g in gs}
        spread_l = max(lat.values()) - min(lat.values())
        spread_f = max(fw.values()) - min(fw.values())
        if len(gs) >= 3 and spread_l > 0.02 * self.h and spread_f > 0.02 * self.h:
            mf = sum(fw.values()) / len(gs)
            ml = sum(lat.values()) / len(gs)
            for g in gs:
                same = (fw[g] > mf) == (lat[g] > ml)
                out[g] = 0.0 if same else math.pi
            return out
        key = lat if spread_l >= spread_f * 0.6 else fw
        order = sorted(gs, key=lambda g: key[g])
        for i, g in enumerate(order):
            out[g] = math.pi * (i % 2)
        # break exact ties in the deciding coordinate by the other one
        return out

    def chain(self, g):
        return self.groups.get(g, [])

    def first(self, g):
        return self.groups[g][0]

    def all_bones(self, groups):
        out = []
        for g in groups:
            out += self.groups[g]
        return out

    def sign_toward(self, g, axis, target):
        """+1/-1 so that a positive rotation about `axis` moves group g's tip toward `target`."""
        v = self.tip[g] - self.pivot[g]
        s = axis.normalized().cross(v).dot(target)
        return 1.0 if s >= 0 else -1.0


# ============================================================================ motion helpers
def wave(P, S, g, u, amp_deg, axis, cycles=1.0, lag=0.5, phase=0.0, ramp=(0.35, 1.0), bias=0.0, lagphase=True):
    """Travelling wave down a chain (or a single bone) of group g."""
    bl = S.chain(g)
    n = len(bl)
    for i, b in enumerate(bl):
        k = ramp[0] + (ramp[1] - ramp[0]) * (i / max(1, n - 1)) if n > 1 else 1.0
        a = rad(amp_deg) * k * math.sin(TAU * cycles * u - i * lag + phase) + rad(bias) * k
        P.rot(b, axis, a)


def swing_limb(P, S, g, ang, axis=None):
    """Rotate a limb group's first bone by `ang` (+ = tip toward fwd) about the swing axis."""
    P.rot(S.first(g), S.a_sw if axis is None else axis, ang)


def knee(P, S, g, flex):
    """Bend the lower chain bones of a limb backwards (foot trails) by `flex` radians."""
    bl = S.chain(g)
    if len(bl) >= 2:
        for b in bl[1:]:
            P.rot(b, S.a_sw, -flex)


def head_bones(S):
    return S.all_bones(S.heads)


def stabilise_head(P, S, body_pitch, body_roll=0.0, body_yaw=0.0, k=0.6):
    """Head counter-rotates a fraction of the body's motion so it stays steady."""
    for g in S.heads:
        b = S.first(g)
        P.rot(b, S.a_sw, -body_pitch * k)
        P.rot(b, S.fwd, -body_roll * k)
        P.rot(b, Z, -body_yaw * k)


def secondary(P, S, u, amp=1.0, lagu=0.12, rate=1.0, sway_axis=None):
    """Tail / ear / leaf / accessory follow-through driven by the body's own cycle."""
    ax = Y if S.view == 'side' else Y
    for g in S.tails:
        wave(P, S, g, u, 9 * amp, ax, cycles=rate, lag=0.55, phase=-TAU * lagu)
    for g in S.ears:
        wave(P, S, g, u, 4.0 * amp, ax, cycles=rate, lag=0.4, phase=-TAU * lagu * 1.6 + 1.0)
    for g in S.leaves + S.horns:
        if S.role[g] == 'leaf':
            wave(P, S, g, u, 3.5 * amp, ax, cycles=rate, lag=0.4, phase=-TAU * lagu + 2.0)


# ============================================================================ gait: inference
def infer_gait(S, sp):
    g = S.look.get('gait')
    if g:
        return g
    types = (sp or {}).get('types') or []
    n_legs = len(S.legs)
    if S.wings and ('FLYING' in types or n_legs == 0):
        return 'flap'
    if n_legs >= 3:
        return 'quad'
    if n_legs >= 1:
        return 'biped'
    if any(len(S.chain(g)) >= 5 for g in S.groups if S.role[g] in ('body', 'tail')):
        return 'serpent'
    return 'float'


# ============================================================================ Idle
def idle_pose(S, P, u, gait):
    h = S.h
    ph = TAU * u
    breath = math.sin(ph)
    body = S.body_b
    heavy = S.look.get('weight') == 'heavy'
    if gait in ('float', 'hover', 'flap'):
        bob = (0.035 if gait != 'flap' else 0.03) * h * math.sin(ph)
        P.move('root', (0, 0, bob))
        P.rot(body, Y, rad(3.0) * math.sin(ph + 1.0))
        P.rot(body, S.a_sw, rad(2.0) * math.sin(ph))
        P.scale(body, 1 + 0.010 * math.sin(2 * ph), 1 + 0.010 * math.sin(2 * ph), 1 - 0.012 * math.sin(2 * ph))
        for g in S.arms + S.hands:
            wave(P, S, g, u, 9, Y, 1.0, 0.5, phase=-0.9)
        if gait == 'flap':
            for g in S.wings:
                fl = 22 if gait == 'flap' else 8
                _flap(P, S, g, u, fl, cycles=2, phase=0)
            for g in S.legs:
                P.rot(S.first(g), S.a_sw, rad(-14) + rad(3) * math.sin(ph))
        for g in S.heads:
            P.rot(S.first(g), S.a_sw, rad(3) * math.sin(ph - 0.8))
    elif gait in ('serpent', 'slither'):
        chains = [g for g in S.groups if len(S.chain(g)) >= 3]
        for g in chains:
            wave(P, S, g, u, 7, Y, 1.0, 0.75, ramp=(0.5, 1.6))
            wave(P, S, g, u, 3, Z, 1.0, 0.75, phase=1.2)
        if not chains:
            # segments: ripple through the parent chain
            _segment_wave(P, S, u, 5, cycles=1.0, lag=0.5)
        P.move('root', (0, 0, 0.012 * h * math.sin(ph)))
        for g in S.heads:
            P.rot(S.first(g), S.a_sw, rad(3) * math.sin(ph + 0.9))
        secondary(P, S, u, 0.8)
    else:
        # legged / general: breathe, weight-shift, secondary motion
        sq = 0.018 * breath
        P.scale(body, 1 - 0.5 * sq, 1 - 0.5 * sq, 1 + sq)
        P.move(body, (0, 0, 0.004 * h * breath))
        shift = math.sin(ph + 0.5)
        P.rot(body, S.fwd, rad(1.8 if not heavy else 1.2) * shift)
        P.rot(body, Z, rad(1.5) * math.sin(ph + 2.0))
        for g in S.heads:
            b = S.first(g)
            P.rot(b, S.a_sw, rad(3.5) * math.sin(ph - 0.7) - rad(1.0) * breath)
            P.rot(b, Z, rad(4.0) * math.sin(ph * 1.0 + 1.9))
        for g in S.arms:
            sd = 1.0 if S._lat(g) >= 0 else -1.0
            wave(P, S, g, u, 4.0, S.fwd, 1.0, 0.3, phase=0.3)
            P.rot(S.first(g), S.a_sw, rad(3.0) * math.sin(ph + S.arm_phase.get(g, 0) * 0.5 - 0.7))
        for g in S.hands:
            wave(P, S, g, u, 5.0, S.a_sw, 1.0, 0.3, phase=-1.0)
        for g in S.legs:
            # subtle weight shift: the leg on the loaded side stiffens
            P.rot(S.first(g), S.a_sw, rad(1.2) * math.sin(ph + S.leg_phase[g]))
        for g in S.wings:
            _flap(P, S, g, u, 6, cycles=1, phase=0.6)
        for g in S.tails:
            wave(P, S, g, u, 10, Y, 2.0 if not heavy else 1.0, 0.6, phase=-0.5)
        for g in S.ears:
            wave(P, S, g, u, 4.5, Y, 1.0, 0.45, phase=-1.4)
            # occasional twitch (once per loop)
            tw = bump(u, 0.62, 0.72)
            for b in S.chain(g):
                P.rot(b, Y, rad(9) * tw * (1 if S._lat(g) >= 0 else -1))
        for g in S.leaves + S.others:
            wave(P, S, g, u, 4, Y, 1.0, 0.4, phase=-0.8)
        for g in S.jaws:
            P.rot(S.first(g), S.a_sw, rad(2) * max(0, math.sin(ph - 0.3)))
    if gait in ('sway', 'plant'):
        for g in S.groups:
            if S.role[g] in ('neck', 'leaf', 'tail', 'head', 'other'):
                wave(P, S, g, u, 5, Y, 1.0, 0.6, phase=-0.7)
    if gait in ('blob', 'hop', 'roll'):
        sq = 0.04 * math.sin(2 * ph)
        P.scale(body, 1 - 0.5 * sq, 1 - 0.5 * sq, 1 + sq)


def _flap(P, S, g, u, amp_deg, cycles=2, phase=0.0, lagv=0.9):
    """Wing beat about an axis that reads from the camera for both front- and side-on sprites."""
    ax = (S.fwd + Vector((0, -0.9, 0))).normalized() if S.view == 'side' else S.fwd
    sg = S.sign_toward(g, ax, Z)
    bl = S.chain(g)
    for i, b in enumerate(bl):
        a = sg * rad(amp_deg) * (1.0 + 0.5 * i) * math.sin(TAU * cycles * u + phase - i * lagv)
        P.rot(b, ax, a)


def _segment_wave(P, S, u, amp, cycles=1.0, lag=0.5):
    """Serpents / caterpillars built from one group per segment: ripple through the parent chain."""
    depth = {}
    for g in S.groups:
        d, b = 0, S.first(g)
        while S.bone[b]['parent'] in S.bone:
            b = S.bone[b]['parent']
            d += 1
        depth[g] = d
    for g, d in depth.items():
        if S.role[g] in ('body', 'tail', 'other', 'head') and g != S.anchor:
            P.rot(S.first(g), Y, rad(amp) * math.sin(TAU * cycles * u - d * lag))


# ============================================================================ Walk
def walk_pose(S, P, u, gait):
    h = S.h
    ph = TAU * u
    body = S.body_b
    heavy = S.look.get('weight') == 'heavy'
    light = S.look.get('weight') == 'light'
    if gait in ('biped', 'waddle', 'quad', 'stomp', 'bound', 'scuttle', 'crawl'):
        _walk_legged(S, P, u, gait, heavy, light)
    elif gait in ('serpent', 'slither'):
        chains = [g for g in S.groups if len(S.chain(g)) >= 3]
        for g in chains:
            wave(P, S, g, u, 20, Y, 1.0, 0.85, ramp=(0.45, 1.6))
            wave(P, S, g, u, 8, Z, 1.0, 0.85, phase=0.9)
        if not chains:
            _segment_wave(P, S, u, 11, cycles=1.0, lag=0.6)
        P.rot(body, Y, rad(4) * math.sin(ph))
        P.move('root', (0.012 * h * math.sin(ph), 0, 0.012 * h * math.sin(2 * ph)))
        for g in S.heads:
            P.rot(S.first(g), Y, -rad(9) * math.sin(ph - 0.3))
        secondary(P, S, u, 1.5, rate=1.0)
        for g in S.groups:
            if S.role[g] in ('wing',):
                wave(P, S, g, u, 12, Y, 1.0, 0.5, phase=-1)
    elif gait in ('flap', 'fly'):
        for g in S.wings:
            _flap(P, S, g, u, 38, cycles=2, phase=0)
        P.move('root', (0, 0, 0.05 * h * math.sin(TAU * 2 * u + 1.2)))
        P.rot(body, S.a_sw, rad(-6) + rad(3) * math.sin(TAU * 2 * u))
        for g in S.legs:
            P.rot(S.first(g), S.a_sw, rad(-30))
            knee(P, S, g, rad(20))
        for g in S.arms + S.hands:
            wave(P, S, g, u, 12, Y, 2.0, 0.4, phase=-1)
        secondary(P, S, u, 1.4, rate=2.0)
        for g in S.heads:
            P.rot(S.first(g), S.a_sw, rad(-4) - rad(3) * math.sin(TAU * 2 * u + 0.5))
    elif gait in ('float', 'hover'):
        P.move('root', (0, 0, 0.045 * h * math.sin(ph)))
        P.rot(body, S.fwd, rad(6) * math.sin(ph))
        P.rot(body, S.a_sw, rad(-9))
        for g in S.arms + S.hands + S.tails + S.leaves + S.others + S.ears:
            wave(P, S, g, u, 14, Y, 1.0, 0.55, phase=-1.4)
        for g in S.wings:
            _flap(P, S, g, u, 20, cycles=2, phase=0.2)
        for g in S.heads:
            P.rot(S.first(g), S.a_sw, rad(4) * math.sin(ph - 0.6))
    elif gait in ('hop', 'blob', 'roll'):
        _walk_hop(S, P, u, gait, heavy)
    elif gait in ('swim', 'flop'):
        _walk_swim(S, P, u, gait)
    elif gait in ('sway', 'plant'):
        _walk_hop(S, P, u, 'hop', heavy)
    else:
        _walk_legged(S, P, u, 'biped', heavy, light)


def _walk_legged(S, P, u, gait, heavy, light):
    h = S.h
    ph = TAU * u
    body = S.body_b
    quad = gait in ('quad', 'bound', 'crawl', 'scuttle') or (len(S.legs) >= 4 and S.view == 'side')
    waddle = gait in ('waddle', 'stomp') or heavy
    A = rad(26 if not waddle else 15)
    if gait == 'bound':
        A = rad(34)
    if gait == 'crawl' or gait == 'scuttle':
        A = rad(24)
    lift_f = 0.16 if not waddle else 0.22
    bob = (0.028 if not waddle else 0.02) * h * (0.5 if quad else 1.0)
    front = S.view == 'front'
    # ---- torso
    z = bob * math.cos(2 * ph)
    P.move('root', (0, 0, z))
    roll = rad(4.5 if front else 2.0) * math.sin(ph) * (1.8 if waddle else 1.0)
    P.rot(body, S.fwd, roll)
    if front:
        P.move('root', (0.02 * h * math.sin(ph) * (2.0 if waddle else 1.0), 0, 0))
    pitch = rad(2.5 if quad else 1.5) * math.sin(2 * ph + 0.6)
    P.rot(body, S.a_sw, pitch)
    yaw = rad(5.0 if not quad else 3.0) * math.sin(ph)
    P.rot(body, Z, yaw)
    if waddle:
        sq = 0.03 * math.cos(2 * ph)
        P.scale(body, 1 - 0.5 * sq, 1 - 0.5 * sq, 1 + sq)
    # ---- legs (feet stay planted while the torso bobs)
    for g in S.legs:
        f = S.leg_phase[g]
        a = A * math.sin(ph + f)
        sw = max(0.0, math.cos(ph + f))                 # swing (air) phase weight
        b0 = S.first(g)
        P.rot(b0, S.a_sw, a)
        P.move(b0, (0, 0, -z + lift_f * S.leg_len[g] * sw ** 0.9))
        knee(P, S, g, rad(38) * sw ** 1.2)
    for g in S.feet:
        f = S.leg_phase.get(g, 0.0)
        sw = max(0.0, math.cos(ph + f))
        P.rot(S.first(g), S.a_sw, -rad(12) * sw + rad(10) * (1 - sw) * 0.3)
    # ---- arms: swing opposite to the leg on the same side, hands lag
    for g in S.arms:
        f = S.arm_phase[g]
        amp = rad(24 if not quad else 14) * (0.7 if waddle else 1.0)
        P.rot(S.first(g), S.a_sw, amp * math.sin(ph + f))
        bl = S.chain(g)
        for b in bl[1:]:
            P.rot(b, S.a_sw, rad(14) * (0.5 + 0.5 * math.sin(ph + f + 1.2)))
        if front:
            P.rot(S.first(g), S.fwd, rad(6) * math.sin(ph + f + 0.5) * (1 if S._lat(g) >= 0 else -1))
    for g in S.hands:
        P.rot(S.first(g), S.a_sw, rad(10) * math.sin(ph + 1.0))
    # ---- head & neck
    stabilise_head(P, S, pitch, roll, yaw, 0.7)
    for g in S.heads:
        P.rot(S.first(g), S.a_sw, rad(3.0) * math.sin(2 * ph + 1.4))
    for g in S.necks:
        wave(P, S, g, u, 5, S.a_sw, 2.0, 0.5, phase=1.0)
    # ---- follow-through
    for g in S.tails:
        wave(P, S, g, u, 13 if not heavy else 8, Y, 1.0, 0.6, phase=-0.9)
        if S.view == 'side':
            wave(P, S, g, u, 5, Z, 2.0, 0.6, phase=0.4)
        else:
            wave(P, S, g, u, 5, S.a_sw, 2.0, 0.6, phase=0.4)
    for g in S.ears:
        wave(P, S, g, u, 7, S.a_sw, 2.0, 0.5, phase=-1.1)
        wave(P, S, g, u, 4, Y, 1.0, 0.4, phase=-0.6)
    for g in S.leaves + S.others + S.horns:
        if S.role[g] in ('leaf', 'other'):
            wave(P, S, g, u, 5, Y, 2.0, 0.5, phase=-1.0)
    for g in S.wings:
        _flap(P, S, g, u, 9, cycles=2, phase=0.4)
    for g in S.jaws:
        P.rot(S.first(g), S.a_sw, rad(2.0) * (0.5 + 0.5 * math.sin(2 * ph)))


def _walk_hop(S, P, u, gait, heavy):
    """Two hops per cycle (one per cell): squat, launch, airborne stretch, landing squash."""
    h = S.h
    body = S.body_b
    hop_h = (0.09 if not heavy else 0.05) * h
    if gait == 'roll':
        hop_h *= 0.7
    v = (u * 2.0) % 1.0                        # per-cell phase
    air = bump(v, 0.18, 0.82)
    z = hop_h * math.sin(math.pi * min(1.0, max(0.0, (v - 0.18) / 0.64))) if 0.18 < v < 0.82 else 0.0
    # squash before takeoff / on landing, stretch in the air
    crouch = spline(v, [(0, 0.55), (0.12, 1.0), (0.22, 0.0), (0.5, -0.65), (0.78, 0.0), (0.9, 0.9), (1.0, 0.55)])
    P.move('root', (0, 0, z))
    sz = 1 - 0.13 * crouch
    P.scale(body, 1 + 0.06 * crouch, 1 + 0.06 * crouch, sz)
    lean = rad(6) * math.sin(TAU * v) * (-1)
    P.rot(body, S.a_sw, lean * 0.5)
    for g in S.legs + S.feet:
        P.rot(S.first(g), S.a_sw, rad(-18) * air + rad(6) * crouch)
        knee(P, S, g, rad(30) * (crouch if crouch > 0 else 0))
    for g in S.arms + S.hands + S.wings:
        if S.role[g] == 'wing':
            _flap(P, S, g, u, 20, cycles=2, phase=0)
        else:
            P.rot(S.first(g), S.a_sw, rad(-40) * air + rad(10) * crouch)
    if gait == 'roll':
        P.rot(body, S.fwd, rad(12) * math.sin(TAU * u))
    for g in S.tails + S.ears + S.leaves + S.others:
        wave(P, S, g, u, 12, Y, 2.0, 0.5, phase=-1.6)
    for g in S.heads:
        P.rot(S.first(g), S.a_sw, rad(4) * math.sin(TAU * v + 0.8))


def _walk_swim(S, P, u, gait):
    h = S.h
    ph = TAU * u
    body = S.body_b
    if gait == 'flop':
        v = u
        hopz = 0.14 * h * max(0.0, math.sin(TAU * v * 1.0)) ** 1.2
        P.move('root', (0, 0, hopz))
        P.rot(body, Y, rad(24) * math.sin(TAU * v + 1.0))
        for g in S.tails + S.wings:
            wave(P, S, g, u, 30, Y, 2.0, 0.7, phase=-0.6)
    else:
        P.move('root', (0, 0, 0.03 * h * math.sin(ph)))
        P.rot(body, Y, rad(6) * math.sin(ph))
        for g in S.tails:
            wave(P, S, g, u, 26, Y, 1.0, 0.8, ramp=(0.4, 1.5))
        for g in S.groups:
            if S.role[g] in ('wing', 'leaf', 'other', 'ear'):
                wave(P, S, g, u, 20, Y, 2.0, 0.6, phase=-0.8)
    for g in S.heads:
        P.rot(S.first(g), Y, -rad(6) * math.sin(ph))


# ============================================================================ Attack
ATTACK_STYLES = {
    #        lunge lean  head jaw  arms      twist tail  rise hold
    'tackle': dict(lunge=0.32, lean=15, head=0.05, jaw=0, arms='tuck', twist=0, tail=24, rise=0, sq=0.10),
    'charge': dict(lunge=0.42, lean=20, head=0.10, jaw=0, arms='tuck', twist=0, tail=30, rise=0, sq=0.14),
    'bite': dict(lunge=0.26, lean=12, head=0.14, jaw=34, arms='tuck', twist=0, tail=22, rise=0, sq=0.08),
    'headbutt': dict(lunge=0.22, lean=24, head=0.16, jaw=0, arms='tuck', twist=0, tail=18, rise=0, sq=0.08),
    'punch': dict(lunge=0.16, lean=8, head=0.04, jaw=0, arms='punch', twist=24, tail=14, rise=0, sq=0.06),
    'slash': dict(lunge=0.14, lean=6, head=0.03, jaw=0, arms='slash', twist=16, tail=16, rise=0, sq=0.05),
    'tail': dict(lunge=0.06, lean=0, head=0.02, jaw=0, arms='none', twist=-26, tail=80, rise=0, sq=0.05),
    'rear': dict(lunge=0.10, lean=-22, head=0.05, jaw=10, arms='slam', twist=0, tail=16, rise=0.12, sq=0.10),
    'beam': dict(lunge=0.05, lean=-9, head=0.11, jaw=24, arms='raise', twist=0, tail=14, rise=0, sq=0.05),
    'slam': dict(lunge=0.10, lean=10, head=0.04, jaw=0, arms='slam', twist=0, tail=16, rise=0.30, sq=0.20),
    'peck': dict(lunge=0.12, lean=18, head=0.14, jaw=8, arms='none', twist=0, tail=20, rise=0, sq=0.06),
    'coil': dict(lunge=0.20, lean=8, head=0.15, jaw=30, arms='none', twist=0, tail=40, rise=0.05, sq=0.05),
    'psychic': dict(lunge=0.0, lean=-4, head=0.02, jaw=0, arms='raise', twist=0, tail=10, rise=0.10, sq=0.03),
}


def attack_pose(S, P, u, style_name, gait):
    st = ATTACK_STYLES.get(style_name) or ATTACK_STYLES['tackle']
    h = S.h
    body = S.body_b
    # timing envelope: windup (negative), strike, hold, recover
    env = spline(u, [(0.0, 0.0), (0.24, -0.42), (0.36, 0.25), (0.46, 1.0), (0.60, 0.85), (0.80, 0.18), (1.0, 0.0)])
    fast = spline(u, [(0.0, 0.0), (0.28, 0.0), (0.42, 1.0), (0.56, 0.7), (0.8, 0.1), (1.0, 0.0)])
    wind = max(0.0, -env)
    fwd_s = max(0.0, env)
    lunge = st['lunge'] * h
    # translate along the model front (-Y) = toward the opponent; profile creatures also lean into their facing
    fwdv = Vector((0, -1, 0)) if S.view == 'front' else (Vector((0, -0.75, 0)) + S.fwd * 0.6)
    P.move('root', fwdv * (lunge * env))
    hop = st['rise'] * h * math.sin(math.pi * min(1.0, max(0.0, (u - 0.28) / 0.34))) if 0.28 < u < 0.62 else 0.0
    P.move('root', (0, 0, hop))
    lean = rad(st['lean'])
    sgn = 1.0 if lean >= 0 else -1.0
    P.rot(body, S.a_sw, rad(8) * sgn * wind - lean * fwd_s)
    sq = st['sq']
    P.scale(body, 1 + 0.5 * sq * wind, 1 + 0.5 * sq * wind, 1 - sq * wind + 0.5 * sq * fwd_s)
    if st['twist']:
        tw = rad(st['twist'])
        P.rot(body, Z, tw * (-wind * 0.8 + fast))
    # legs brace: bend in windup, push on strike
    for g in S.legs:
        b0 = S.first(g)
        P.rot(b0, S.a_sw, rad(10) * wind - rad(8) * fast * (1 if S.leg_phase[g] == 0 else -0.3))
        knee(P, S, g, rad(28) * wind)
        P.move(b0, (0, 0, 0.0))
    # head
    for g in S.heads:
        b = S.first(g)
        P.move(b, S.fwd * (st['head'] * h * env) if S.view == 'side' else Vector((0, -st['head'] * h * env, 0)))
        P.rot(b, S.a_sw, -rad(14) * fast * (1 if style_name in ('headbutt', 'peck', 'bite', 'coil') else 0.3)
              + rad(10) * wind)
    for g in S.necks:
        wave(P, S, g, u, 10 * fast, S.a_sw, 1.0, 0.5)
    for g in S.jaws:
        P.rot(S.first(g), S.a_sw, rad(st['jaw']) * bump(u, 0.30, 0.78))
    # arms
    mode = st['arms']
    for g in S.arms:
        b0 = S.first(g)
        ph = S.arm_phase.get(g, 0.0)
        striker = ph < 1.0
        if mode == 'punch':
            a = (rad(-50) * wind + rad(-80) * fast) if striker else (rad(30) * wind + rad(-20) * fast)
            P.rot(b0, S.a_sw, -a if False else -a)
        elif mode == 'slash':
            side = 1.0 if S._lat(g) >= 0 else -1.0
            P.rot(b0, S.a_sw, rad(-40) * wind + rad(-95) * fast)
            P.rot(b0, S.fwd, side * (rad(35) * wind - rad(50) * fast))
        elif mode == 'slam':
            P.rot(b0, S.a_sw, rad(-70) * bump(u, 0.15, 0.5) + rad(-10) * fast)
        elif mode == 'raise':
            P.rot(b0, S.a_sw, rad(-70) * spline(u, [(0, 0), (0.3, 0.6), (0.5, 1.0), (0.85, 0.9), (1, 0)]))
        elif mode == 'tuck':
            P.rot(b0, S.a_sw, rad(20) * wind - rad(25) * fast)
        for b in S.chain(g)[1:]:
            P.rot(b, S.a_sw, rad(30) * wind)
    for g in S.hands:
        P.rot(S.first(g), S.a_sw, -rad(25) * fast)
    # wings flare / tail lash / ears pin back
    for g in S.wings:
        ax = (S.fwd + Vector((0, -0.9, 0))).normalized() if S.view == 'side' else S.fwd
        sg = S.sign_toward(g, ax, Z)
        for i, b in enumerate(S.chain(g)):
            P.rot(b, ax, sg * (rad(40) * wind - rad(35) * fast + rad(8) * math.sin(TAU * 3 * u)) * (1 + 0.5 * i))
    for g in S.tails:
        lash = rad(st['tail']) * (0.6 * math.sin(TAU * (u * 1.3) - 0.5) + 1.2 * fast)
        for i, b in enumerate(S.chain(g)):
            k = 0.4 + 0.6 * (i / max(1, len(S.chain(g)) - 1)) if len(S.chain(g)) > 1 else 1.0
            lag = spline(u - 0.05 * i, [(0, 0), (0.3, -0.4), (0.5, 1.0), (0.7, 0.4), (1.0, 0)])
            P.rot(b, Y, rad(st['tail']) * k * (lag if st['twist'] > -1 else lag))
    for g in S.ears:
        for b in S.chain(g):
            P.rot(b, S.a_sw, rad(20) * fast + rad(8) * wind)
    for g in S.leaves + S.others:
        wave(P, S, g, u, 8 * (0.3 + fast), Y, 1.0, 0.5, phase=-0.6)
    if gait in ('serpent', 'slither'):
        for g in S.groups:
            if len(S.chain(g)) >= 3:
                for i, b in enumerate(S.chain(g)):
                    k = (i + 1) / len(S.chain(g))
                    P.rot(b, Y, rad(28) * k * spline(u - 0.05 * i, [(0, 0), (0.26, -0.7), (0.46, 0.9), (0.7, 0.2), (1, 0)]))
        if not any(len(S.chain(g)) >= 3 for g in S.groups):
            _segment_wave(P, S, u, 14 * fast + 6 * wind, cycles=1.0, lag=0.5)


# ============================================================================ Hurt
def hurt_pose(S, P, u, gait):
    h = S.h
    body = S.body_b
    hit = spline(u, [(0, 0), (0.12, 1.0), (0.3, 0.55), (0.6, 0.12), (1.0, 0)])
    sp = math.exp(-5.0 * u) * math.sin(TAU * 2.6 * u)
    P.move('root', Vector((0, 1, 0)) * (0.11 * h * hit) + Vector((0.02 * h * sp, 0, 0.03 * h * hit)))
    P.rot(body, S.a_sw, rad(16) * hit)
    P.rot(body, Y, rad(7) * sp)
    P.scale(body, 1 + 0.07 * hit, 1 + 0.07 * hit, 1 - 0.10 * hit + 0.04 * sp)
    for g in S.heads:
        P.rot(S.first(g), S.a_sw, rad(26) * hit + rad(6) * sp)
        P.rot(S.first(g), Z, rad(9) * sp)
    for g in S.legs:
        P.rot(S.first(g), S.a_sw, rad(12) * hit * (1 if S.leg_phase[g] == 0 else -1))
        knee(P, S, g, rad(20) * hit)
    for g in S.arms + S.hands:
        side = 1.0 if S._lat(g) >= 0 else -1.0
        P.rot(S.first(g), S.fwd, side * rad(40) * hit)
        P.rot(S.first(g), S.a_sw, rad(-14) * sp)
    for g in S.wings:
        ax = (S.fwd + Vector((0, -0.9, 0))).normalized() if S.view == 'side' else S.fwd
        sg = S.sign_toward(g, ax, Z)
        for b in S.chain(g):
            P.rot(b, ax, sg * rad(35) * hit)
    for g in S.tails + S.ears + S.leaves + S.others + S.horns:
        for i, b in enumerate(S.chain(g)):
            P.rot(b, Y, rad(20) * (0.5 + 0.5 * i) * spring(u, 2.5, 5.0) * math.exp(-2 * u) * (1 if i % 2 == 0 else 1))
    if gait in ('serpent', 'slither'):
        for g in S.groups:
            for i, b in enumerate(S.chain(g)):
                if len(S.chain(g)) >= 3:
                    P.rot(b, Y, rad(14) * math.sin(TAU * 2 * u - i * 0.9) * math.exp(-3 * u))
        if not any(len(S.chain(g)) >= 3 for g in S.groups):
            _segment_wave(P, S, u, 12 * math.exp(-3 * u), cycles=2.0, lag=0.6)


# ============================================================================ Faint
def faint_pose(S, P, u, gait):
    h = S.h
    body = S.body_b
    shudder = math.sin(TAU * 5 * u) * bump(u, 0.0, 0.28) * 0.6
    drop = spline(u, [(0, 0), (0.25, 0.08), (0.55, 0.85), (0.75, 1.0), (1.0, 1.0)])
    topple = sstep((u - 0.30) / 0.55)
    settle = 1.0 - math.exp(-6 * max(0.0, u - 0.8) / 0.2) if u > 0.8 else 0.0
    floaty = gait in ('float', 'hover', 'flap', 'serpent', 'slither', 'swim')
    ground = 0.0 if not S.hover else 0.0
    if floaty and S.hover:
        # let it sink to the ground
        low = -min(S.bbox[0].z, 0.0)
    P.move('root', (0.012 * h * shudder, 0, -0.10 * h * drop * (0.7 if not floaty else 1.0)))
    side = 1.0 if S.look.get('fall', 'right') == 'right' else -1.0
    roll_ang = rad(78 if not floaty else 55) * topple * side
    P.rot(body, S.fwd, roll_ang)
    P.rot(body, S.a_sw, rad(-8) * topple)
    sq = 0.28 * drop
    P.scale(body, 1 + 0.35 * sq, 1 + 0.35 * sq, 1 - sq)
    P.move('root', (0.06 * h * topple * side, 0, 0.0))
    for g in S.heads:
        P.rot(S.first(g), S.a_sw, rad(-30) * drop)
        P.rot(S.first(g), S.fwd, rad(-10) * topple * side)
    for g in S.legs:
        b0 = S.first(g)
        fold = sstep((u - 0.15) / 0.5)
        P.rot(b0, S.a_sw, rad(22) * fold * (1 if S.leg_phase[g] == 0 else -0.6))
        knee(P, S, g, rad(70) * fold)
    for g in S.arms + S.hands + S.wings:
        for i, b in enumerate(S.chain(g)):
            side2 = 1.0 if S._lat(g) >= 0 else -1.0
            if S.role[g] == 'wing':
                ax = (S.fwd + Vector((0, -0.9, 0))).normalized() if S.view == 'side' else S.fwd
                sg = S.sign_toward(g, ax, Z)
                P.rot(b, ax, -sg * rad(55) * drop)
            else:
                P.rot(b, S.fwd, side2 * rad(45) * drop)
                P.rot(b, S.a_sw, rad(20) * drop)
    for g in S.tails + S.ears + S.leaves + S.others + S.horns:
        for i, b in enumerate(S.chain(g)):
            P.rot(b, Y, rad(35) * (0.4 + 0.3 * i) * drop * (1 if S._lat(g) >= 0 else -1) + rad(4) * shudder)
    for g in S.jaws:
        P.rot(S.first(g), S.a_sw, rad(15) * drop)
    if gait in ('serpent', 'slither'):
        for g in S.groups:
            n = len(S.chain(g))
            for i, b in enumerate(S.chain(g)):
                if n >= 3:
                    P.rot(b, Y, rad(20 + 6 * i) * drop * (1 if i % 2 == 0 else -1) * 0.6)
        if not any(len(S.chain(g)) >= 3 for g in S.groups):
            _segment_wave(P, S, u, 16 * drop, cycles=1.0, lag=0.9)


# ============================================================================ Special
def special_pose(S, P, u, style, gait):
    h = S.h
    body = S.body_b
    ph = TAU * u
    if style == 'spin':
        e = sstep(u)
        P.move('root', (0, 0, 0.16 * h * math.sin(math.pi * min(1.0, u * 1.05))))
        P.rot('root', Z, TAU * e * 0.9995)
        sq = spline(u, [(0, 0), (0.1, 0.7), (0.25, -0.5), (0.7, -0.2), (0.9, 0.5), (1.0, 0)])
        P.scale(body, 1 + 0.05 * sq, 1 + 0.05 * sq, 1 - 0.10 * sq)
        for g in S.arms + S.hands + S.wings + S.ears + S.tails + S.leaves:
            if S.role[g] == 'wing':
                _flap(P, S, g, u, 30, cycles=3)
            else:
                for i, b in enumerate(S.chain(g)):
                    P.rot(b, Y, rad(30) * (0.5 + 0.5 * i) * math.sin(TAU * u * 2 - i * 0.6) * bump(u, 0.1, 0.95))
    elif style == 'roar':
        inh = spline(u, [(0, 0), (0.28, 1.0), (0.5, 0.0), (0.7, 0.3), (1.0, 0)])
        roar = bump(u, 0.42, 0.85)
        P.scale(body, 1 + 0.09 * inh, 1 + 0.09 * inh, 1 + 0.05 * inh)
        P.rot(body, S.a_sw, rad(10) * inh - rad(12) * roar)       # lean back to roar
        for g in S.heads:
            P.rot(S.first(g), S.a_sw, rad(22) * roar + rad(10) * inh)
            P.move(S.first(g), (0, 0, 0.02 * h * roar))
        for g in S.jaws:
            P.rot(S.first(g), S.a_sw, rad(36) * roar)
        for g in S.arms + S.hands:
            side = 1.0 if S._lat(g) >= 0 else -1.0
            P.rot(S.first(g), S.fwd, side * rad(50) * roar)
            P.rot(S.first(g), S.a_sw, -rad(25) * roar)
        for g in S.wings:
            ax = (S.fwd + Vector((0, -0.9, 0))).normalized() if S.view == 'side' else S.fwd
            sg = S.sign_toward(g, ax, Z)
            for b in S.chain(g):
                P.rot(b, ax, sg * rad(35) * roar)
        for g in S.tails:
            wave(P, S, g, u, 20 * roar, Y, 3.0, 0.6)
        P.move('root', (0.006 * h * math.sin(ph * 6) * roar, 0, 0))
        for g in S.legs:
            knee(P, S, g, rad(14) * inh)
        if gait in ('serpent', 'slither'):
            for g in S.groups:
                for i, b in enumerate(S.chain(g)):
                    if len(S.chain(g)) >= 3:
                        P.rot(b, Y, rad(12) * math.sin(ph * 2 - i * 0.7) * roar)
    elif style == 'pulse':
        p = 0.5 - 0.5 * math.cos(ph * 2)
        P.move('root', (0, 0, 0.07 * h * math.sin(math.pi * u)))
        P.scale(body, 1 + 0.10 * p, 1 + 0.10 * p, 1 + 0.10 * p)
        P.rot(body, Z, rad(14) * math.sin(ph * 2))
        for g in S.arms + S.hands + S.tails + S.leaves + S.others + S.ears:
            for i, b in enumerate(S.chain(g)):
                P.rot(b, Y, rad(24) * math.sin(ph * 2 - i * 0.7 - 0.5))
        for g in S.wings:
            _flap(P, S, g, u, 26, cycles=3)
    elif style == 'dance':
        sw = math.sin(ph * 2)
        P.move('root', (0.04 * h * sw, 0, 0.04 * h * abs(math.sin(ph * 2))))
        P.rot(body, S.fwd, rad(9) * sw)
        for g in S.arms + S.hands:
            side = 1.0 if S._lat(g) >= 0 else -1.0
            P.rot(S.first(g), S.fwd, side * rad(80) * (0.5 + 0.5 * math.sin(ph * 2 + (0 if side > 0 else math.pi))))
        for g in S.legs:
            P.rot(S.first(g), S.a_sw, rad(12) * math.sin(ph * 2 + S.leg_phase[g]))
        for g in S.tails + S.ears + S.leaves:
            wave(P, S, g, u, 22, Y, 2.0, 0.6, phase=-0.6)
        for g in S.heads:
            P.rot(S.first(g), S.fwd, -rad(8) * sw)
    elif style == 'shake':
        env = bump(u, 0.05, 0.95)
        P.move('root', (0.016 * h * math.sin(ph * 9) * env, 0, 0.01 * h * math.sin(ph * 13) * env))
        P.rot(body, Z, rad(6) * math.sin(ph * 9 + 1) * env)
        for g in S.tails + S.ears + S.leaves + S.others + S.arms:
            wave(P, S, g, u, 12 * env, Y, 5.0, 0.6)
        for g in S.wings:
            _flap(P, S, g, u, 20, cycles=6)
    else:   # 'hop' default: a happy double hop with a twirl of the tail
        v = (u * 2.0) % 1.0
        z = 0.11 * h * math.sin(math.pi * v) ** 1.5
        crouch = spline(v, [(0, 0.3), (0.12, 1.0), (0.3, 0.0), (0.7, -0.4), (0.92, 0.9), (1.0, 0.3)])
        P.move('root', (0, 0, z))
        P.scale(body, 1 + 0.05 * crouch, 1 + 0.05 * crouch, 1 - 0.10 * crouch)
        for g in S.arms + S.hands:
            P.rot(S.first(g), S.a_sw, -rad(70) * math.sin(math.pi * v))
        for g in S.legs:
            knee(P, S, g, rad(30) * max(0, crouch))
        for g in S.tails + S.ears + S.leaves + S.wings:
            if S.role[g] == 'wing':
                _flap(P, S, g, u, 30, cycles=4)
            else:
                wave(P, S, g, u, 20, Y, 2.0, 0.6, phase=-0.8)
        for g in S.heads:
            P.rot(S.first(g), S.a_sw, rad(8) * math.sin(TAU * v))


# ============================================================================ driver
def default_attack(S, gait, sp):
    a = S.look.get('attack')
    if a:
        return a
    types = (sp or {}).get('types') or []
    if gait in ('serpent', 'slither'):
        return 'coil'
    if gait in ('flap',):
        return 'peck'
    if S.arms and any(S.role[g] == 'hand' for g in S.groups):
        return 'punch'
    if 'FIGHTING' in types:
        return 'punch'
    if 'FIRE' in types or 'WATER' in types or 'ICE' in types:
        return 'beam'
    if 'PSYCHIC_TYPE' in types or 'GHOST' in types:
        return 'psychic'
    return 'tackle'


def default_special(S, gait, sp):
    s = S.look.get('special')
    if s:
        return s
    if gait in ('float', 'hover'):
        return 'pulse'
    if gait in ('serpent', 'slither'):
        return 'roar'
    if S.look.get('weight') == 'heavy':
        return 'roar'
    return 'spin'


def animate(arm, name, sp, look, rig, bones, xf, target, hovering, verts_m=None):
    S = Skel(rig, bones, verts_m, rig.owner, look, sp, target, hovering)
    gait = infer_gait(S, sp)
    atk = default_attack(S, gait, sp)
    spc = default_special(S, gait, sp)
    names = set(S.names) | {'root'}
    all_bones = ['root'] + S.names

    def make(clip, n, fn, loop):
        W = Writer(arm, clip, n)
        for f in range(0, n + 1):
            P = Pose(names)
            if loop:
                u = (f % n) / float(n)
            else:
                u = f / float(n)
            fn(P, u)
            W.key_pose(f, P)
        W.finalize()
        return W.write(all_bones)

    acts = [
        make('Idle', DUR['Idle'], lambda P, u: idle_pose(S, P, u, gait), True),
        make('Walk', DUR['Walk'], lambda P, u: walk_pose(S, P, u, gait), True),
        make('Attack', DUR['Attack'], lambda P, u: attack_pose(S, P, u, atk, gait), False),
        make('Hurt', DUR['Hurt'], lambda P, u: hurt_pose(S, P, u, gait), False),
        make('Faint', DUR['Faint'], lambda P, u: faint_pose(S, P, u, gait), False),
        make('Special', DUR['Special'], lambda P, u: special_pose(S, P, u, spc, gait), False),
    ]
    C.stash_actions(arm, acts)
    return acts

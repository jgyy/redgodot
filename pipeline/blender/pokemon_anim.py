"""Species-authored animation for the Pokemon rigs: rig view, motion layers and the 18 base clips + idle variants.

Nothing here touches bpy: a clip is a function of (context, pose, u in [0,1]) so the same code drives the Blender
bake (gen_rigged_pokemon.py) and the tests (tests/test_pokemon_anim.py evaluates poses with pokemon_pose.Deformer).

What makes clips species-specific:
  * the RigView exposes the species' *own* chains (its wings, ears, tail bones, tentacles ...) so every layer moves
    exactly the bones that exist and nothing else;
  * a Style (mass, tempo, temper, stable per-species jitter) scales amplitudes, durations, cycle counts and picks between
    several authored variants of each clip (three attack styles, three victory styles ...);
  * body-plan families change what a clip *is* (a serpent's Walk is a slither, a bird's a head-bobbing strut, a blob's a
    squash-hop, a starfish's a cartwheel).
"""
import hashlib
import math

import numpy as np

from pokemon_pose import Pose, UP, DOWN, FWD, BACK, LEFT, RIGHT, unit

TAU = math.tau

BASE_CLIPS = ['Idle', 'Walk', 'Run', 'Attack', 'Special', 'Hurt', 'Faint', 'Victory', 'Sleep', 'Roar',
              'Dodge', 'Spin', 'Hop', 'Charge', 'Taunt', 'Spawn', 'Hover', 'Talk']
IDLE_VARIANTS = ['IdleLook', 'IdleStretch', 'IdleFidget']
LOOPING = ['Idle', 'Walk', 'Run', 'Sleep', 'Charge', 'Taunt', 'Hover', 'Talk']

TEMPER = {   # amplitude, speed, snappiness
    'bouncy': (1.15, 1.15), 'calm': (0.85, 0.85), 'fierce': (1.15, 1.1), 'sly': (0.95, 1.0), 'timid': (0.9, 1.1),
    'sturdy': (0.8, 0.85), 'dreamy': (0.85, 0.8), 'playful': (1.1, 1.1), 'aloof': (0.85, 0.9), 'wild': (1.2, 1.2),
}

FAMILY = {'biped_humanoid': 'biped', 'biped_tail': 'biped', 'shell': 'biped', 'quadruped': 'quad', 'quadruped_small': 'quad',
          'bird': 'bird', 'winged': 'winged', 'serpent': 'serpent', 'fish': 'fish', 'blob': 'blob', 'sphere': 'blob',
          'multileg': 'multi', 'plant': 'plant', 'floating': 'float', 'rock': 'rock', 'radial': 'radial'}


def sm(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def bump(u, a, b, c):
    """0 before a, smooth rise to 1 at b, smooth fall to 0 at c."""
    if u <= a or u >= c:
        return 0.0
    return sm((u - a) / max(b - a, 1e-9)) if u < b else 1.0 - sm((u - b) / max(c - b, 1e-9))


def hold(u, a, b, c, d):
    """0 -> rise a..b -> 1 until c -> fall c..d -> 0."""
    if u <= a or u >= d:
        return 0.0
    if u < b:
        return sm((u - a) / max(b - a, 1e-9))
    if u <= c:
        return 1.0
    return 1.0 - sm((u - c) / max(d - c, 1e-9))


def h01(*keys):
    """stable float in [0,1) from strings/numbers (species-specific jitter that never changes between builds)."""
    d = hashlib.md5('|'.join(str(k) for k in keys).encode()).digest()
    return int.from_bytes(d[:6], 'big') / float(1 << 48)


class Chain:
    def __init__(self, sk, gid, names):
        self.gid, self.names = gid, names
        b0, b1 = sk.bones[names[0]], sk.bones[names[-1]]
        self.side = b0.side
        self.root = b0.head
        self.tip = b1.tail
        v = self.tip - self.root
        self.length = float(np.linalg.norm(v))
        self.dir = unit(v)
        self.fh = 'F' if gid.startswith('Leg_F') else 'H' if gid.startswith('Leg_H') else ''
        self.sign = 1.0 if self.side == 'L' else -1.0 if self.side == 'R' else (1.0 if self.tip[0] >= 0 else -1.0)


class RigView:
    def __init__(self, sk, spec):
        self.sk = sk
        self.bones = sk.bones
        self.H = sk.H
        self.plan = spec.get('plan', 'quadruped')
        self.fam = FAMILY.get(self.plan, 'quad')
        by = {}
        for gid, names in sk.chains.items():
            by.setdefault(sk.bones[names[0]].role, []).append(Chain(sk, gid, names))
        self.arms, self.legs, self.tails = by.get('Arm', []), by.get('Leg', []), by.get('Tail', [])
        self.ears, self.wings, self.fins = by.get('Ear', []), by.get('Wing', []), by.get('Fin', [])
        self.extras = by.get('Extra', [])
        self.sides = [c.names[0] for c in by.get('Side', [])]
        info = sk.info
        nm = info.get('names', {})
        self.serpent = info.get('posture') == 'chain'
        self.core = info.get('posture') == 'core'
        self.root = 'Root'
        self.hips = nm.get('hips', 'Hips')
        self.head = nm.get('head', 'Head')
        self.jaw = 'Jaw' if 'Jaw' in sk.bones else None
        self.face = 'Face' if 'Face' in sk.bones else None
        if self.serpent:
            body = [b for b in sk.bones.values() if b.role == 'Spine']
            self.body = [b.name for b in sorted(body, key=lambda b: b.index)]
            self.spine, self.neck = [], []
        else:
            self.body = []
            self.spine = ['Hips'] * (not self.core and 'Hips' in sk.bones) + [n for n in sk.bones if sk.bones[n].role == 'Spine']
            if self.core:
                self.spine = [n for n in ('Body',) if n in sk.bones]
            self.neck = [n for n in sk.bones if sk.bones[n].role == 'Neck']
        self.horizontal = info.get('posture') == 'horizontal'
        self.upper = self.spine[-1] if self.spine else self.hips

    @property
    def all_chains(self):
        return self.arms + self.legs + self.tails + self.ears + self.wings + self.fins + self.extras


class Ctx:
    """everything a clip needs to know about one species."""

    def __init__(self, sid, spec, sk):
        self.sid, self.spec = sid, spec
        self.rig = RigView(sk, spec)
        self.sk = sk
        self.H = sk.H
        self.fam = self.rig.fam
        self.mass = int(spec.get('mass', 3))
        ta, ts = TEMPER.get(spec.get('temper', 'calm'), (1.0, 1.0))
        self.temper = spec.get('temper', 'calm')
        self.tempo = float(spec.get('tempo', 1.0)) * ts
        self.amp = float(np.clip((1.3 - 0.11 * self.mass) * ta, 0.6, 1.35))
        self.heavy = self.mass >= 4
        self.light = self.mass <= 2

    # -- stable per-species randomness ----------------------------------------------------------
    def opt(self, key, n):
        return int(h01(self.sid, key) * n) % n

    def jit(self, key, lo=0.0, hi=1.0):
        return lo + (hi - lo) * h01(self.sid, key, 'j')

    def frames(self, base, floor=12):
        """clip length in frames, stretched by the species' tempo (quick species animate faster)."""
        n = int(max(floor, round(base / max(0.6, min(1.6, self.tempo)))))
        return n + (n % 2)      # even: the glb is sampled every 2nd frame (15 Hz keys, linear)

    # -- body access -------------------------------------------------------------------------------
    def pose(self):
        return Pose(self.rig)

    def spine_pitch(self, P, deg, weights=None):
        """pitch the whole trunk (+: front up). Serpents raise their head half only."""
        r = self.rig
        if r.serpent:
            n = len(r.body)
            for i, b in enumerate(r.body):
                k = max(0.0, (i - n * 0.35) / (n * 0.65))
                P.pitch(b, deg * k / max(1, n * 0.3))
            return
        names = r.spine
        w = weights or [1.0] * len(names)
        s = sum(w) or 1.0
        for n, k in zip(names, w):
            P.pitch(n, deg * k / s)

    def spine_bend(self, P, toward, deg, weights=None):
        r = self.rig
        names = r.body if r.serpent else r.spine
        P.chain(names, toward, deg, weights)

    def spine_yaw(self, P, deg):
        names = self.rig.body if self.rig.serpent else self.rig.spine
        for n in names:
            P.yaw(n, deg / max(1, len(names)))

    def spine_roll(self, P, deg):
        names = self.rig.body if self.rig.serpent else self.rig.spine
        for n in names:
            P.roll(n, deg / max(1, len(names)))

    def head_look(self, P, yaw=0.0, pitch=0.0, roll=0.0):
        r = self.rig
        parts = (r.neck + [r.head]) if r.head in r.bones else r.neck
        if not parts:
            return
        n = len(parts)
        for i, b in enumerate(parts):
            k = (0.4 + 0.6 * (i + 1) / n) / (sum(0.4 + 0.6 * (j + 1) / n for j in range(n)))
            P.yaw(b, yaw * k)
            P.pitch(b, pitch * k)
            P.roll(b, roll * k)

    def mouth(self, P, deg):
        if self.rig.jaw:
            P.bend(self.rig.jaw, DOWN, deg)

    def root_move(self, P, x=0.0, f=0.0, z=0.0):
        """translate the whole body: x lateral, f forward (in units of H), z up."""
        P.move(self.rig.root, np.array([x, -f, z]) * self.H)

    def squash(self, P, k):
        """k>0 squash (wider, flatter), k<0 stretch."""
        P.scale(self.rig.root, 1 + 0.45 * k, 1 + 0.45 * k, 1 - k)

    # -- secondary motion ----------------------------------------------------------------------------
    def tails_sway(self, P, u, amp=14.0, cycles=1.0, lag=0.55, vertical=0.0, phase=0.0):
        for k, t in enumerate(self.rig.tails):
            ph = phase + k * 0.7
            P.wave(t.names, LEFT, amp * self.amp, u, cycles, lag, ph)
            if vertical:
                P.wave(t.names, UP, vertical * self.amp, u, cycles, lag, ph + 1.3)

    def tails_pose(self, P, toward, deg):
        for t in self.rig.tails:
            P.chain(t.names, toward, deg)

    def ears_move(self, P, u, amp=8.0, cycles=1.0, phase=0.0, flick=0.0):
        for k, e in enumerate(self.rig.ears):
            if cycles:
                P.wave(e.names, OUT(e.sign), amp * self.amp, u, cycles, 0.5, phase + k)
            if flick:
                P.bend(e.names[0], BACK, flick)

    def extras_sway(self, P, u, amp=12.0, cycles=1.0, lag=0.6, phase=0.0, toward=None):
        for k, e in enumerate(self.rig.extras):
            tw = toward if toward is not None else (LEFT if abs(e.dir[0]) < 0.6 else FWD)
            P.wave(e.names, tw, amp * self.amp, u, cycles, lag, phase + k * 0.9)

    def wings_flap(self, P, u, amp=25.0, cycles=1.0, spread=0.0, lag=0.5, phase=0.0, fold=0.0):
        """flap around a (partly) spread pose. spread/fold in degrees of sweep away from / toward the body."""
        for k, w in enumerate(self.rig.wings):
            sg = w.sign
            base = w.names[0]
            if spread:
                P.bend(base, OUT(sg), spread)
            a = amp * self.amp
            P.rotw(base, FWD, sg * a * math.sin(TAU * cycles * u + phase + 0.35 * (k // 2)))
            for i, b in enumerate(w.names[1:], 1):
                P.rotw(b, FWD, sg * a * 0.55 * math.sin(TAU * cycles * u + phase - lag * i + 0.35 * (k // 2)))
            if fold:
                P.bend(base, BACK, fold)

    def fins_move(self, P, u, amp=16.0, cycles=2.0, phase=0.0):
        for k, f in enumerate(self.rig.fins):
            P.wave(f.names, LEFT if abs(f.dir[0]) < 0.5 else UP, amp * self.amp, u, cycles, 0.6, phase + k)

    def sides_wobble(self, P, u, amp=0.1, cycles=1.0, phase=0.0):
        for k, s in enumerate(self.rig.sides):
            P.scale(s, 1 + amp * math.sin(TAU * cycles * u + phase + k * math.pi), 1, 1)

    # -- limbs ---------------------------------------------------------------------------------------------
    def leg_phases(self):
        """[(chain, phase)] for a walking gait appropriate to the leg count."""
        legs = self.rig.legs
        out = []
        n = len(legs)
        if n == 0:
            return out
        if n == 2:
            return [(c, 0.0 if c.sign > 0 else math.pi) for c in legs]
        if n == 4 and self.rig.horizontal:
            return [(c, 0.0 if ((c.fh == 'F') == (c.sign > 0)) else math.pi) for c in legs]
        order = sorted(legs, key=lambda c: (-c.root[1] * 0 + c.tip[1], c.sign))
        for i, c in enumerate(order):
            out.append((c, math.pi * ((i // 2 + (0 if c.sign > 0 else 1)) % 2)))
        return out

    def stride(self, P, u, cycles=1.0, amp=26.0, lift=30.0, foot=12.0, out=0.0):
        """walk/run legs: swing at the hip, fold at the knee while lifting, flick at the ankle."""
        for c, ph in self.leg_phases():
            a = TAU * cycles * u + ph
            sw = math.sin(a)
            n = c.names
            P.bend(n[0], FWD, amp * self.amp * sw)
            if len(n) > 1:
                P.bend(n[1], BACK, lift * self.amp * max(0.0, math.sin(a + 1.2)) - 4 * self.amp)
            if len(n) > 2:
                P.bend(n[2], FWD, foot * self.amp * max(0.0, math.sin(a + 0.3)))
            if out:
                P.bend(n[0], OUT(c.sign), out * math.sin(a))

    def arms_counter(self, P, u, cycles=1.0, amp=22.0, elbow=18.0):
        legs = dict((id(c), ph) for c, ph in self.leg_phases())
        for i, c in enumerate(self.rig.arms):
            ph = math.pi if c.sign > 0 else 0.0
            a = TAU * cycles * u + ph
            P.bend(c.names[0], FWD, amp * self.amp * math.sin(a))
            if len(c.names) > 1:
                P.bend(c.names[1], FWD, elbow + 0.5 * elbow * math.sin(a + 0.6))

    def arm_pose(self, P, kind, amt=1.0, only=None, phase=0.0, u=0.0, cycles=0.0, which=None):
        """static arm poses: raise, forward, out, guard, back, up (overhead), tuck."""
        for i, c in enumerate(self.rig.arms):
            if only is not None and c.sign != only:
                continue
            if which is not None and i not in which:
                continue
            n = c.names
            wob = 1.0 + (0.15 * math.sin(TAU * cycles * u + phase + i) if cycles else 0.0)
            s = c.sign
            if kind == 'raise':
                P.bend(n[0], FWD, 150 * amt * wob)
                if len(n) > 1:
                    P.bend(n[1], FWD, 10 * amt)
            elif kind == 'forward':
                P.bend(n[0], FWD, 80 * amt * wob)
                if len(n) > 1:
                    P.bend(n[1], FWD, 25 * amt)
            elif kind == 'out':
                P.bend(n[0], OUT(s), 70 * amt * wob)
            elif kind == 'guard':
                P.bend(n[0], FWD, 55 * amt)
                if len(n) > 1:
                    P.bend(n[1], FWD, 75 * amt)
                    P.bend(n[1], IN(s), 30 * amt)
            elif kind == 'back':
                P.bend(n[0], BACK, 40 * amt * wob)
            elif kind == 'up':
                P.bend(n[0], OUT(s), 140 * amt * wob)
                if len(n) > 1:
                    P.bend(n[1], IN(s), 25 * amt)
            elif kind == 'tuck':
                P.bend(n[0], BACK, 25 * amt)
                if len(n) > 1:
                    P.bend(n[1], FWD, 60 * amt)

    def crouch(self, P, k):
        """legs fold, body lowers (k 0..1)."""
        for c in self.rig.legs:
            n = c.names
            up_dir = BACK if c.fh != 'F' else FWD
            P.bend(n[0], FWD if c.fh != 'F' else BACK, 28 * k)
            if len(n) > 1:
                P.bend(n[1], BACK if c.fh != 'F' else FWD, 52 * k)
            if len(n) > 2:
                P.bend(n[2], FWD, 24 * k)
        self.root_move(P, z=-0.075 * k * (1.0 if self.rig.legs else 0.0))


def OUT(sign):
    return LEFT if sign > 0 else RIGHT


def IN(sign):
    return RIGHT if sign > 0 else LEFT

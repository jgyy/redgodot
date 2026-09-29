"""Procedural animation for the chibi rig (numpy) + Blender action writer.

Poses are authored per bone as *world-axis Euler deltas from the rest pose* (degrees, applied
X then Y then Z about the bone head, in armature axes), plus optional translation / scale.

Axis cheat-sheet (front = -Y, +X = character's left, Z up):
  rot X  (+) tilts an upward bone's tip forward (lean)   / swings a downward bone's tip BACK
  rot Y  (+) rolls an upward bone toward +X (left)       / swings a downward bone toward -X
  rot Z  (+) turns counter-clockwise seen from above (head turns to the character's right... -X)
Legs use planar 2-bone IK (sagittal plane): feet plant in stance with heel strike / toe off,
the pelvis bobs & sways, the torso counter-twists and the head stays level.

Clips (60 fps, all loop; first frame == last frame):
  Idle        120 f  breathing, weight shift, blinks, look-around, hair follow-through
  Walk         16 f  ONE full gait cycle (2 steps) per 16-frame cell => feet plant, seamless if restarted
  Run          16 f  flight-phase run (one cycle per two cells at run speed)
  Talk         90 f  nods, mouth flaps, gesturing
  Wave         60 f  right arm raised and waving
  Cheer        40 f  two hops with both arms up
  Surf         90 f  seated, gentle sway
  Nod Shake Think Laugh Point Sleep Salute Stretch Dance Sad Shiver (loops), Bow Surprised (one-shots): NPC gestures
"""
import math

import numpy as np

TAU = 2 * math.pi


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class Clip:
    def __init__(self, name, n, step=1):
        self.name, self.n, self.step = name, n, step
        self.rot, self.loc, self.scl = {}, {}, {}

    def r(self, bone):
        if bone not in self.rot:
            self.rot[bone] = np.zeros((self.n + 1, 3))
        return self.rot[bone]

    def l(self, bone):
        if bone not in self.loc:
            self.loc[bone] = np.zeros((self.n + 1, 3))
        return self.loc[bone]

    def s(self, bone):
        if bone not in self.scl:
            self.scl[bone] = np.ones((self.n + 1, 3))
        return self.scl[bone]


def fs(n):
    return np.arange(n + 1) / float(n)


def periodic_smooth(a, sigma=1.0, radius=3):
    """Gaussian smoothing of a periodic sample array (last sample == first)."""
    k = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    k /= k.sum()
    core = a[:-1]
    ext = np.concatenate([core[-radius:], core, core[:radius]])
    sm = np.convolve(ext, k, mode='valid')
    return np.concatenate([sm, sm[:1]])


# ----------------------------------------------------------------------------- IK
def ik_leg(hip, ankle, L1, L2):
    """Planar 2-bone IK; hip / ankle (n,2) = (forward, up).  Returns thigh forward angle
    (rad, + = forward) and knee flexion (rad, knee bends forward)."""
    d = ankle - hip
    dist = np.linalg.norm(d, axis=1)
    dist = np.clip(dist, abs(L1 - L2) + 1e-3, (L1 + L2) * 0.9995)
    c = (L1 * L1 + L2 * L2 - dist * dist) / (2 * L1 * L2)
    gamma = np.arccos(np.clip(c, -1, 1))
    k = math.pi - gamma
    alpha = np.arctan2(d[:, 0], -d[:, 1])
    beta = np.arctan2(L2 * np.sin(k), L1 + L2 * np.cos(k))
    return alpha + beta, k


def gait(P, n, *, S, ds, lift, sway=0.3, lean=3.0, arm_amp=30.0, elbow=14.0, yaw=5.0, run=False,
         mult=1, name='Walk', toe=1.0, arm_bend=12.0, head_bob=1.0, bob_gain=1.0):
    c = Clip(name, n)
    t = fs(n)
    ph = TAU * t * mult
    L1, L2 = P.hip - P.knee, P.knee - P.ankle
    Lmax = (L1 + L2) * 0.985
    legs = {}
    for side, off in (('L', 0.0), ('R', 0.5)):
        p = (t * mult + off) % 1.0
        stance = p < ds
        u = np.clip(p / ds, 0, 1)
        v = np.clip((p - ds) / (1 - ds), 0, 1)
        x_st = S - 2 * S * u
        x_sw = -S + 2 * S * ease(v)
        rest = P.ankle
        z_st = rest + toe * (0.55 * (1 - ease(u / 0.18)) + 1.3 * ease((u - 0.72) / 0.28))
        z_start, z_end = rest + toe * 1.3, rest + toe * 0.55
        z_sw = z_start + (z_end - z_start) * ease(v) + lift * np.sin(math.pi * v) ** 0.85
        pitch_st = 14 * (1 - ease(u / 0.22)) - 28 * ease((u - 0.7) / 0.3)
        pitch_sw = -28 + 42 * ease(v * 1.5) - 8 * np.sin(math.pi * v)
        legs[side] = dict(x=np.where(stance, x_st, x_sw), z=np.where(stance, z_st, z_sw),
                          pitch=np.where(stance, pitch_st, pitch_sw))
    if run:
        hh = (P.hip - 0.55) - 0.75 * np.cos(2 * TAU * (t * mult - 0.18))
    else:
        need = [legs[s]['z'] + np.sqrt(np.maximum(Lmax ** 2 - legs[s]['x'] ** 2, 0.4)) for s in ('L', 'R')]
        hh = periodic_smooth(np.minimum(need[0], need[1]), 1.1)
    bob = (hh - P.hip) * bob_gain
    lr = (legs['L']['x'] - legs['R']['x']) / (2 * S)          # +1 when the left foot is far forward
    # pelvis: bob, weight shift toward the stance foot, forward surge, yaw & roll
    hips = c.r('hips')
    c.l('hips')[:, 2] = bob
    c.l('hips')[:, 0] = sway * np.sin(ph)
    c.l('hips')[:, 1] = -0.2 * np.cos(2 * ph)
    hips[:, 2] = -yaw * lr
    hips[:, 1] = -2.2 * np.sin(ph)
    hips[:, 0] = lean * 0.3
    for side, sg in (('L', 1), ('R', -1)):
        lg = legs[side]
        th, kf = ik_leg(np.stack([np.zeros(n + 1), hh], 1), np.stack([lg['x'], lg['z']], 1), L1, L2)
        thd, kfd = np.degrees(th), np.degrees(kf)
        c.r('thigh_' + side)[:, 0] = -thd - hips[:, 0]
        c.r('shin_' + side)[:, 0] = kfd
        c.r('foot_' + side)[:, 0] = -lg['pitch'] - (-thd + kfd)
        c.r('thigh_' + side)[:, 1] = sg * 1.5
        c.r('thigh_' + side)[:, 2] = yaw * lr * 0.9      # cancel most of the pelvis yaw so the feet keep pointing ahead
    # arms swing against the same-side leg
    for side, sg, other in (('L', 1, 'R'), ('R', -1, 'L')):
        legx = legs[other]['x'] / S
        c.r('upper_arm_' + side)[:, 0] = -arm_amp * legx
        c.r('upper_arm_' + side)[:, 1] = -sg * 3.0
        c.r('forearm_' + side)[:, 0] = -(arm_bend + elbow * np.clip(legx, 0, 1))
        c.r('hand_' + side)[:, 0] = -7 * legx
        c.r('clavicle_' + side)[:, 1] = -sg * 1.6 * np.sin(2 * ph)
    # torso: counter-twist, lean, roll opposite the pelvis
    c.r('spine')[:, 2] = yaw * 1.0 * lr
    c.r('spine')[:, 0] = lean * 0.4 + 0.7 * np.cos(2 * ph)
    c.r('spine')[:, 1] = 1.6 * np.sin(ph)
    c.r('chest')[:, 2] = yaw * 0.6 * lr
    c.r('chest')[:, 0] = lean * 0.3
    # head: stabilise (cancel torso yaw), keep the gaze forward, nod a little on each footfall
    c.r('neck')[:, 2] = -yaw * 0.9 * lr * 1.0
    c.r('head')[:, 2] = -yaw * 0.7 * lr
    c.r('head')[:, 0] = -lean * 0.7 + head_bob * 1.7 * np.cos(2 * ph + 0.5)
    c.r('head')[:, 1] = -1.6 * np.sin(ph)
    return c


def secondary_hair(c, names, amp, freq, t, lag=0.55, axis=0, bias=0.0, phase=0.0, ax2=None, amp2=0.0):
    for i, nm in enumerate(names):
        a = amp * (0.6 + 0.4 * i)
        c.r(nm)[:, axis] += bias + a * np.sin(TAU * freq * t - lag * (i + 1) + phase)
        if ax2 is not None:
            c.r(nm)[:, ax2] += amp2 * (0.6 + 0.4 * i) * np.sin(TAU * freq * t - lag * (i + 1) + phase + 1.2)


def hair_motion(c, t, hair, mode):
    amp = {'idle': 2.5, 'walk': 8.0, 'run': 15.0, 'talk': 3.5, 'cheer': 18.0}.get(mode, 3.0)
    fr = {'idle': 1, 'walk': 2, 'run': 2, 'talk': 2, 'cheer': 2}.get(mode, 1)
    for grp, names in hair.items():
        if not names:
            continue
        if grp == 'hair_back':
            secondary_hair(c, names, amp * 0.8, fr, t, lag=0.5, axis=0)
        elif grp == 'hair_tail':
            secondary_hair(c, names, amp * 1.2, fr, t, lag=0.6, axis=0, bias=(2.0 if mode != 'idle' else 0.0), ax2=1, amp2=amp * 0.7)
        elif grp == 'hair_twin':
            half = len(names) // 2
            for k, nm in enumerate(names):
                sg = 1 if k < half else -1
                bi = k % max(half, 1)
                a = amp * (0.7 + 0.4 * bi)
                c.r(nm)[:, 0] += a * 0.9 * np.sin(TAU * fr * t - 0.6 * (bi + 1))
                c.r(nm)[:, 1] += sg * a * 0.7 * np.sin(TAU * fr * t - 0.6 * (bi + 1) + 1.0)
        else:
            secondary_hair(c, names, amp, fr, t, lag=0.6, axis=0)


def blink_curve(t, at, width=0.02):
    d = np.abs(((t - at + 0.5) % 1.0) - 0.5)
    return np.clip(1 - d / width, 0, 1) ** 0.8


def add_face(c, t, blinks=(0.32, 0.74), talk=None):
    b = np.zeros_like(t)
    for at in blinks:
        b = np.maximum(b, blink_curve(t, at, 0.022))
    for eye in ('eye_L', 'eye_R'):
        c.s(eye)[:, 2] = 1.0 - 0.88 * b
        c.s(eye)[:, 0] = 1.0 + 0.06 * b
    if talk is not None:
        c.s('mouth')[:, 2] = talk
        c.s('mouth')[:, 0] = 1.0 - (talk - 1.0) * 0.2


# ----------------------------------------------------------------------------- clips
def build_idle(P, hair, name='Idle', n=96):
    c = Clip(name, n, step=2)
    t = fs(n)
    w = TAU * t
    breath = np.sin(w)
    shift = np.sin(w + 0.4)
    c.l('hips')[:, 2] = -0.1 - 0.06 * (0.5 - 0.5 * np.cos(w))
    c.l('hips')[:, 0] = 0.25 * shift
    c.r('hips')[:, 1] = 1.0 * shift
    c.r('spine')[:, 0] = 0.8 * breath
    c.r('spine')[:, 1] = -1.0 * shift
    c.r('chest')[:, 0] = 1.6 * breath
    c.s('chest')[:, 0] = 1.0 + 0.012 * breath
    c.s('chest')[:, 1] = 1.0 + 0.018 * breath
    c.s('chest')[:, 2] = 1.0 + 0.008 * breath
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 0] = 1.6 * np.sin(w - 0.9)
        c.r('upper_arm_' + side)[:, 1] = -sg * (3.0 + 0.9 * breath)
        c.r('forearm_' + side)[:, 0] = -6 - 1.5 * np.sin(w - 1.4)
        c.r('clavicle_' + side)[:, 1] = -sg * 1.2 * breath
        c.r('hand_' + side)[:, 0] = -3 + 2 * np.sin(w - 1.9)
        c.r('thigh_' + side)[:, 1] = sg * 1.0
        c.r('shin_' + side)[:, 0] = 2.0
        c.r('foot_' + side)[:, 0] = -1.0
    c.r('thigh_L')[:, 0] = -1.0 - 1.0 * shift
    c.r('thigh_R')[:, 0] = -1.0 + 1.0 * shift
    look = ease((t - 0.10) / 0.10) - ease((t - 0.28) / 0.12) - ease((t - 0.52) / 0.10) + ease((t - 0.68) / 0.12)
    c.r('neck')[:, 2] = 9.0 * look
    c.r('head')[:, 2] = 6.0 * look
    c.r('head')[:, 0] = 1.8 * np.sin(w + 0.8) + 1.5 * (ease((t - 0.10) / 0.1) - ease((t - 0.28) / 0.12))
    c.r('head')[:, 1] = 2.2 * shift
    add_face(c, t, blinks=(0.30, 0.83))
    hair_motion(c, t, hair, 'idle')
    return c


def resample_clip(base, name, n):
    c = Clip(name, n, step=2)
    src, dst = fs(base.n), fs(n)
    for attr in ('rot', 'loc', 'scl'):
        for bone, arr in getattr(base, attr).items():
            out = np.stack([np.interp(dst, src, arr[:, k]) for k in range(3)], 1)
            getattr(c, attr)[bone] = out
    return c


def build_walk(P, hair, name='Walk', n=16, mult=1):
    stride = 1.0 if mult == 1 and n == 16 else 1.12
    c = gait(P, n, S=3.1 * stride, ds=0.58, lift=1.6, sway=0.34, lean=3.0, arm_amp=32, elbow=16, yaw=6.0, name=name, mult=mult)
    t = fs(n)
    add_face(c, t, blinks=())
    hair_motion(c, t, hair, 'walk')
    return c


def build_run(P, hair, n=16):
    c = gait(P, n, S=3.9, ds=0.36, lift=2.9, sway=0.25, lean=11.0, arm_amp=48, elbow=40, yaw=8.0, name='Run', run=True,
             arm_bend=55, head_bob=1.4, toe=1.4)
    t = fs(n)
    add_face(c, t, blinks=())
    hair_motion(c, t, hair, 'run')
    return c


def build_talk(P, hair):
    n = 72
    c = resample_clip(build_idle(P, hair), 'Talk', n)
    t = fs(n)
    w = TAU * t
    mouth = 1.0 + 1.5 * np.clip(np.sin(w * 4.0) * np.sin(w * 6.3 + 1.0) + 0.2, 0, 1) * (0.6 + 0.4 * np.sin(w * 2))
    add_face(c, t, blinks=(0.4,), talk=mouth)
    c.r('head')[:, 0] += 1.8 * np.sin(w * 3) + 2.0 * np.sin(w * 2 + 1)
    c.r('head')[:, 2] += 4.0 * np.sin(w) + 2.0 * np.sin(w * 3 + 0.4)
    c.r('head')[:, 1] += 2.0 * np.sin(w * 2 + 0.3)
    c.r('neck')[:, 0] += 1.5 * np.sin(w * 3)
    g = np.clip(np.sin(w * 2 - 0.5), 0, 1)
    c.r('upper_arm_R')[:, 0] += -28 * g
    c.r('upper_arm_R')[:, 1] += 10 * g
    c.r('forearm_R')[:, 0] += -46 * g
    c.r('hand_R')[:, 0] += -14 * g + 8 * np.sin(w * 6) * g
    hair_motion(c, t, hair, 'talk')
    return c


def build_wave(P, hair):
    n = 48
    c = resample_clip(build_idle(P, hair), 'Wave', n)
    t = fs(n)
    w = TAU * t
    up = ease(t / 0.2) * (1 - ease((t - 0.85) / 0.15))
    c.r('upper_arm_R')[:, 1] = 128 * up
    c.r('upper_arm_R')[:, 0] = -12 * up
    c.r('forearm_R')[:, 1] = 30 * np.sin(w * 4) * up
    c.r('forearm_R')[:, 0] = -20 * up
    c.r('hand_R')[:, 1] = 16 * np.sin(w * 4 - 0.6) * up
    c.r('head')[:, 2] += 6 * up
    c.r('head')[:, 1] += -5 * up
    c.l('hips')[:, 0] += 0.15 * up
    hair_motion(c, t, hair, 'talk')
    return c


def build_cheer(P, hair):
    n = 40
    c = resample_clip(build_idle(P, hair), 'Cheer', n)
    t = fs(n)
    w = TAU * t
    hop = np.sin(math.pi * ((t * 2) % 1.0))
    crouch = 1 - hop
    c.l('hips')[:, 2] = 1.9 * hop - 0.7 * crouch ** 3
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 1] = -sg * (-(150 + 8 * np.sin(w * 2)) + 0) * -1
        c.r('upper_arm_' + side)[:, 1] = -sg * (150 + 8 * np.sin(w * 2))
        c.r('upper_arm_' + side)[:, 0] = -10
        c.r('forearm_' + side)[:, 0] = -10 - 12 * hop
        c.r('thigh_' + side)[:, 0] = -(12 * crouch ** 2) - 4 * hop
        c.r('shin_' + side)[:, 0] = 24 * crouch ** 2 + 2
        c.r('foot_' + side)[:, 0] = -8 * crouch ** 2 + 10 * hop
    c.r('head')[:, 0] = -6 * hop
    c.r('spine')[:, 0] = -2 * hop
    add_face(c, t, blinks=())
    hair_motion(c, t, hair, 'cheer')
    return c


def build_surf(P, hair):
    n = 90
    c = resample_clip(build_idle(P, hair), 'Surf', n)
    t = fs(n)
    w = TAU * t
    for side, sg in (('L', 1), ('R', -1)):
        c.r('thigh_' + side)[:, 0] = -84 + 1.5 * np.sin(w + sg)
        c.r('shin_' + side)[:, 0] = 78 + 2 * np.sin(w - sg)
        c.r('foot_' + side)[:, 0] = -6
        c.r('thigh_' + side)[:, 1] = sg * 4
        c.r('upper_arm_' + side)[:, 0] = -18 + 2 * np.sin(w)
        c.r('forearm_' + side)[:, 0] = -26
    c.l('hips')[:, 2] = -(P.hip - P.ankle) * 0.62 + 0.15 * np.sin(w)
    c.l('hips')[:, 1] = -1.0
    c.r('spine')[:, 0] += 3 + 1.5 * np.sin(w - 0.4)
    c.r('hips')[:, 1] = 2.5 * np.sin(w)
    hair_motion(c, t, hair, 'talk')
    return c


# ----------------------------------------------------------------------------- NPC gestures (12 extra clips)
def _base(P, hair, name, n):
    """A resampled Idle (breathing, weight shift, hair follow-through) that a gesture is layered on."""
    c = resample_clip(build_idle(P, hair), name, n)
    return c, fs(n), TAU * fs(n)


def _window(t, a, b, fade=0.15):
    """0 -> 1 -> 0 envelope: rises over `fade` from a, falls over `fade` before b."""
    return ease((t - a) / fade) * (1 - ease((t - (b - fade)) / fade))


def build_nod(P, hair):
    c, t, w = _base(P, hair, 'Nod', 60)
    nod = np.sin(w * 3)
    c.r('head')[:, 0] += 5 + 11 * nod
    c.r('neck')[:, 0] += 2 + 4 * np.sin(w * 3 - 0.35)
    c.r('spine')[:, 0] += 1.2 * nod
    add_face(c, t, blinks=(0.55,))
    return c


def build_shake(P, hair):
    c, t, w = _base(P, hair, 'Shake', 60)
    s = np.sin(w * 3)
    c.r('head')[:, 2] += 24 * s
    c.r('neck')[:, 2] += 8 * np.sin(w * 3 - 0.35)
    c.r('chest')[:, 2] += 2.5 * s
    c.r('head')[:, 0] += 3
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 1] += -sg * 10
    add_face(c, t, blinks=(0.25, 0.75))
    return c


def build_think(P, hair):
    c, t, w = _base(P, hair, 'Think', 96)
    a = _window(t, 0.0, 1.0, 0.16)
    c.r('upper_arm_R')[:, 0] += -68 * a
    c.r('upper_arm_R')[:, 1] += -18 * a
    c.r('forearm_R')[:, 0] += -112 * a
    c.r('hand_R')[:, 0] += -10 * a
    c.r('upper_arm_L')[:, 0] += -30 * a
    c.r('forearm_L')[:, 0] += -70 * a
    c.r('upper_arm_L')[:, 1] += 24 * a
    c.r('head')[:, 1] += 7 * a
    c.r('head')[:, 2] += 10 * a * np.sin(w)
    c.r('head')[:, 0] += -3 * a
    c.r('thigh_R')[:, 0] += -4 * a * np.clip(np.sin(w * 3), 0, 1)
    add_face(c, t, blinks=(0.4, 0.85))
    return c


def build_laugh(P, hair):
    c, t, w = _base(P, hair, 'Laugh', 60)
    shake = np.sin(w * 6)
    bounce = np.abs(np.sin(w * 3))
    c.l('hips')[:, 2] += 0.16 * bounce
    c.r('head')[:, 0] += -9 - 4 * shake
    c.r('neck')[:, 0] += -4
    c.r('chest')[:, 0] += -3 + 2.2 * shake
    c.r('spine')[:, 0] += -2
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 0] += -22
        c.r('upper_arm_' + side)[:, 1] += sg * 14
        c.r('forearm_' + side)[:, 0] += -55 - 6 * shake
    mouth = 1.0 + 1.6 * (0.5 + 0.5 * np.sin(w * 6 + 0.5))
    add_face(c, t, blinks=(), talk=mouth)
    for eye in ('eye_L', 'eye_R'):
        c.s(eye)[:, 2] = 0.35
    return c


def build_bow(P, hair):
    c, t, w = _base(P, hair, 'Bow', 72)
    b = ease(t / 0.35) * (1 - ease((t - 0.65) / 0.35))
    c.r('spine')[:, 0] += 30 * b
    c.r('chest')[:, 0] += 14 * b
    c.r('neck')[:, 0] += 8 * b
    c.r('head')[:, 0] += 8 * b
    c.l('hips')[:, 0] += -0.25 * b
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 0] += 10 * b
        c.r('thigh_' + side)[:, 0] += -6 * b
    add_face(c, t, blinks=(0.5,))
    return c


def build_point(P, hair):
    c, t, w = _base(P, hair, 'Point', 60)
    p = _window(t, 0.0, 1.0, 0.18)
    c.r('upper_arm_R')[:, 0] += -86 * p
    c.r('upper_arm_R')[:, 1] += 6 * p
    c.r('forearm_R')[:, 0] += -6 * p
    c.r('hand_R')[:, 0] += 2 * p
    c.r('spine')[:, 0] += 3 * p
    c.r('head')[:, 2] += 5 * p
    c.r('head')[:, 0] += -2 * p + 1.5 * np.sin(w * 2) * p
    c.r('upper_arm_R')[:, 0] += 3 * np.sin(w * 2) * p
    return c


def build_sleep(P, hair):
    c, t, w = _base(P, hair, 'Sleep', 120)
    br = np.sin(w)
    c.r('head')[:, 0] += 26 + 3 * br
    c.r('neck')[:, 0] += 12
    c.r('spine')[:, 0] += 7 + 1.5 * br
    c.r('chest')[:, 0] += 1.5 * br
    c.l('hips')[:, 2] += -0.2
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 0] += 8
        c.r('upper_arm_' + side)[:, 1] += -sg * (-3 - 1.2 * br)
        c.r('thigh_' + side)[:, 0] += -6
        c.r('shin_' + side)[:, 0] += 8
    add_face(c, t, blinks=(), talk=1.0 + 0.5 * np.clip(np.sin(w) , 0, 1))
    for eye in ('eye_L', 'eye_R'):
        c.s(eye)[:, 2] = 0.1
    return c


def build_surprised(P, hair):
    c, t, w = _base(P, hair, 'Surprised', 36)
    s = ease(t / 0.12) * (1 - ease((t - 0.55) / 0.45))
    jump = np.sin(math.pi * np.clip(t / 0.4, 0, 1)) ** 1.2
    c.l('hips')[:, 2] += 1.1 * jump
    c.r('spine')[:, 0] += -9 * s
    c.r('head')[:, 0] += -7 * s
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 1] += -sg * 62 * s
        c.r('upper_arm_' + side)[:, 0] += -18 * s
        c.r('forearm_' + side)[:, 0] += -30 * s
        c.r('thigh_' + side)[:, 0] += -10 * jump
        c.r('shin_' + side)[:, 0] += 16 * jump
    add_face(c, t, blinks=(), talk=1.0 + 1.4 * s)
    for eye in ('eye_L', 'eye_R'):
        c.s(eye)[:, 2] = 1.0 + 0.3 * s
    return c


def build_salute(P, hair):
    c, t, w = _base(P, hair, 'Salute', 60)
    a = _window(t, 0.0, 1.0, 0.2)
    c.r('upper_arm_R')[:, 0] += -34 * a
    c.r('upper_arm_R')[:, 1] += 78 * a
    c.r('forearm_R')[:, 0] += -128 * a
    c.r('forearm_R')[:, 1] += -14 * a
    c.r('hand_R')[:, 1] += -10 * a
    c.r('head')[:, 0] += -4 * a
    c.r('spine')[:, 0] += -2 * a
    add_face(c, t, blinks=())
    return c


def build_stretch(P, hair):
    c, t, w = _base(P, hair, 'Stretch', 120)
    a = _window(t, 0.05, 0.95, 0.25)
    tremble = np.sin(w * 8) * 0.6
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 1] += -sg * 168 * a
        c.r('upper_arm_' + side)[:, 0] += -8 * a + tremble * a
        c.r('forearm_' + side)[:, 0] += -6 * a
        c.r('clavicle_' + side)[:, 1] += -sg * -8 * a
    c.r('spine')[:, 0] += -12 * a
    c.r('chest')[:, 0] += -8 * a
    c.r('head')[:, 0] += -12 * a
    c.l('hips')[:, 2] += 0.1 * a
    add_face(c, t, blinks=(), talk=1.0 + 1.7 * a * np.clip(np.sin(math.pi * np.clip((t - 0.3) / 0.4, 0, 1)), 0, 1))
    for eye in ('eye_L', 'eye_R'):
        c.s(eye)[:, 2] = 1.0 - 0.8 * a
    return c


def build_dance(P, hair):
    c, t, w = _base(P, hair, 'Dance', 48)
    beat = np.sin(w * 2)
    c.l('hips')[:, 0] += 0.7 * np.sin(w)
    c.l('hips')[:, 2] += -0.25 + 0.32 * np.abs(np.sin(w * 2))
    c.r('hips')[:, 1] += 9 * np.sin(w)
    c.r('spine')[:, 1] += -6 * np.sin(w)
    for side, sg, ph in (('L', 1, 0.0), ('R', -1, math.pi)):
        c.r('upper_arm_' + side)[:, 1] += -sg * (70 + 52 * np.sin(w * 2 + ph))
        c.r('upper_arm_' + side)[:, 0] += -12 * np.sin(w * 2 + ph)
        c.r('forearm_' + side)[:, 0] += -30 - 20 * np.sin(w * 2 + ph)
        c.r('thigh_' + side)[:, 0] += -9 * np.clip(np.sin(w + ph), 0, 1)
        c.r('shin_' + side)[:, 0] += 16 * np.clip(np.sin(w + ph), 0, 1)
    c.r('head')[:, 1] += 8 * np.sin(w)
    c.r('head')[:, 0] += 3 * beat
    add_face(c, t, blinks=(0.4,), talk=1.4)
    return c


def build_sad(P, hair):
    c, t, w = _base(P, hair, 'Sad', 90)
    a = _window(t, 0.0, 1.0, 0.2)
    sob = np.sin(w * 4) * a
    c.r('head')[:, 0] += 18 * a + 1.2 * sob
    c.r('neck')[:, 0] += 8 * a
    c.r('spine')[:, 0] += 9 * a
    c.r('chest')[:, 0] += 4 * a
    c.l('hips')[:, 2] += -0.08 * a
    for side, sg in (('L', 1), ('R', -1)):
        c.r('clavicle_' + side)[:, 1] += -sg * 7 * a
        c.r('upper_arm_' + side)[:, 0] += 10 * a
        c.r('upper_arm_' + side)[:, 1] += sg * 3 * a
        c.r('forearm_' + side)[:, 0] += -4 * a
    add_face(c, t, blinks=(0.3, 0.7), talk=1.0 - 0.35 * a)
    for eye in ('eye_L', 'eye_R'):
        c.s(eye)[:, 2] = 1.0 - 0.45 * a
    return c


def build_shiver(P, hair):
    c, t, w = _base(P, hair, 'Shiver', 30)
    tr = np.sin(w * 8)
    tr2 = np.sin(w * 9 + 1.0)
    for side, sg in (('L', 1), ('R', -1)):
        c.r('upper_arm_' + side)[:, 0] += -34
        c.r('upper_arm_' + side)[:, 1] += sg * 24
        c.r('forearm_' + side)[:, 0] += -112
        c.r('forearm_' + side)[:, 1] += sg * 20
        c.r('clavicle_' + side)[:, 1] += -sg * 6
        c.r('thigh_' + side)[:, 1] += sg * 3
    c.r('spine')[:, 0] += 5 + 1.2 * tr
    c.r('spine')[:, 2] += 1.4 * tr2
    c.r('head')[:, 0] += 5 + 1.6 * tr2
    c.r('head')[:, 2] += 2 * tr
    c.l('hips')[:, 0] += 0.08 * tr
    add_face(c, t, blinks=(), talk=1.0 + 0.5 * np.abs(tr))
    return c


GESTURES = ['Nod', 'Shake', 'Think', 'Laugh', 'Bow', 'Point', 'Sleep', 'Surprised', 'Salute', 'Stretch', 'Dance', 'Sad', 'Shiver']
ONE_SHOT = ['Bow', 'Surprised']


def build_all(P, hair):
    base = [build_idle(P, hair), build_walk(P, hair), build_run(P, hair), build_talk(P, hair), build_wave(P, hair),
            build_cheer(P, hair)]
    extra = [build_nod(P, hair), build_shake(P, hair), build_think(P, hair), build_laugh(P, hair), build_bow(P, hair),
             build_point(P, hair), build_sleep(P, hair), build_surprised(P, hair), build_salute(P, hair),
             build_stretch(P, hair), build_dance(P, hair), build_sad(P, hair), build_shiver(P, hair)]
    return base + extra


# ----------------------------------------------------------------------------- writing
def _quats_local(rot_deg, R):
    from mathutils import Matrix, Euler
    Rm = Matrix(R.tolist())
    Ri = Rm.transposed()
    out = np.zeros((len(rot_deg), 4))
    for i, (a, b, c_) in enumerate(rot_deg):
        M = Euler((math.radians(a), math.radians(b), math.radians(c_)), 'XYZ').to_matrix()
        q = (Ri @ M @ Rm).to_quaternion()
        out[i] = (q.w, q.x, q.y, q.z)
    for i in range(1, len(out)):
        if np.dot(out[i], out[i - 1]) < 0:
            out[i] = -out[i]
    return out


SCALE_BONES = ('chest', 'eye_L', 'eye_R', 'mouth')


def write_actions(arm, clips, bone_names, unit=1.0):
    """One bpy Action per clip, full tracks on every bone (nothing sticks between clips)."""
    import bpy
    acts = []
    rest = {b.name: np.array(b.matrix_local.to_3x3()) for b in arm.data.bones}
    for clip in clips:
        act = bpy.data.actions.new(clip.name)
        act.use_fake_user = True
        ad = arm.animation_data or arm.animation_data_create()
        prev = ad.action
        ad.action = act
        n = clip.n
        frames = list(range(0, n + 1, clip.step))
        if frames[-1] != n:
            frames.append(n)
        zero3 = np.zeros((n + 1, 3))
        for bone in bone_names:
            if bone == 'root':
                continue
            R = rest[bone]
            Ri = R.T
            q = _quats_local(clip.rot.get(bone, zero3), R)
            loc = (Ri @ (clip.loc[bone] * unit).T).T if bone in clip.loc else zero3
            if bone in clip.scl:
                sc = (np.abs(Ri) @ clip.scl[bone].T).T
            else:
                sc = np.ones((n + 1, 3))
            base = 'pose.bones["%s"].' % bone
            chans = [('rotation_quaternion', 4, q)]
            if bone == 'hips':
                chans.append(('location', 3, loc))
            if bone in SCALE_BONES:
                chans.append(('scale', 3, sc))
            for prop, dim, data in chans:
                for k in range(dim):
                    fc = act.fcurve_ensure_for_datablock(arm, base + prop, index=k, group_name=bone)
                    fc.keyframe_points.add(len(frames))
                    co = []
                    for f in frames:
                        co += [float(f), float(data[f][k])]
                    fc.keyframe_points.foreach_set('co', co)
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                    fc.update()
        ad.action = prev
        acts.append(act)
    return acts

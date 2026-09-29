"""The 18 base clips + 3 idle variants, and the catalog builder (base + species signature clips).

`build_catalog(sid, spec, sk, pokedata)` -> OrderedDict name -> Clip(frames, loop, fn) ; `sample(ctx, clip, f)` -> Pose.
"""
import math
from collections import OrderedDict

import numpy as np

import pokemon_arch as A
import pokemon_species as SP
from pokemon_anim import (Ctx, BASE_CLIPS, IDLE_VARIANTS, LOOPING, bump, hold, sm, TAU, OUT, IN, h01, TEMPER)
from pokemon_pose import UP, DOWN, FWD, BACK, LEFT, RIGHT


class Clip:
    def __init__(self, name, frames, loop, fn, kind='base', arch=None):
        self.name, self.frames, self.loop, self.fn, self.kind, self.arch = name, frames, loop, fn, kind, arch


LEN = {'Idle': 64, 'Walk': 36, 'Run': 30, 'Attack': 30, 'Special': 44, 'Hurt': 20, 'Faint': 40, 'Victory': 42, 'Sleep': 80,
       'Roar': 40, 'Dodge': 22, 'Spin': 28, 'Hop': 28, 'Charge': 32, 'Taunt': 40, 'Spawn': 26, 'Hover': 52, 'Talk': 24,
       'IdleLook': 48, 'IdleStretch': 56, 'IdleFidget': 44}


# ------------------------------------------------------------------------------------------------ Idle
def idle(c, P, u):
    r = c.rig
    s = math.sin(TAU * u)
    s2 = math.sin(TAU * 2 * u + c.jit('idle_ph', 0, 6))
    a = c.amp
    calm = c.temper in ('calm', 'dreamy', 'aloof', 'sturdy')
    c.root_move(P, z=0.006 * s * a)
    P.scale(r.root, 1, 1, 1 + 0.012 * s)
    c.spine_pitch(P, 2.2 * s)
    ja, jp = c.jit('idle_amp', 0.8, 1.4), c.jit('idle_ph2', 0, TAU)      # every species idles with its own amplitude and phase
    c.head_look(P, yaw=(3.5 if calm else 6.0) * ja * math.sin(TAU * u + jp), pitch=2.5 * ja * math.sin(TAU * u - 0.9 + jp),
                roll=2.0 * s2 * (0.5 if calm else 1.0))
    if c.temper in ('fierce', 'wild'):
        c.root_move(P, x=0.0025 * math.sin(TAU * 9 * u))
    if c.temper in ('bouncy', 'playful'):
        c.root_move(P, z=0.012 * abs(math.sin(TAU * 2 * u)))
        c.squash(P, 0.02 * math.sin(TAU * 2 * u + 1.5))
    fam = c.fam
    if fam in ('biped', 'rock'):
        for i, arm in enumerate(r.arms):
            P.bend(arm.names[0], FWD, 5 * s + 3 * math.sin(TAU * u + i * 2))
            P.bend(arm.names[0], OUT(arm.sign), 2 + 2 * s)
            if len(arm.names) > 1:
                P.bend(arm.names[1], FWD, 8 + 4 * math.sin(TAU * u - 0.5))
        for leg in r.legs:
            P.bend(leg.names[0], FWD, 2 * s * leg.sign)
        c.tails_sway(P, u, 12, 1.0, 0.7)
        c.spine_roll(P, 1.6 * math.sin(TAU * u + 0.3))
    elif fam == 'quad':
        c.tails_sway(P, u, 16, 1.0, 0.7)
        c.ears_move(P, u, 5, 1.0, phase=0.8)
        for leg in r.legs:
            if leg.fh == 'F':
                P.bend(leg.names[0], FWD, 3 * s * leg.sign)
        c.spine_pitch(P, 1.5 * s2)
    elif fam == 'bird':
        c.head_look(P, yaw=10 * math.sin(TAU * u * 2 + 0.4), pitch=4 * math.sin(TAU * u * 2))
        c.wings_flap(P, u, 4, 1.0)
        c.tails_sway(P, u, 6, 1.0, 0.5, vertical=6)
    elif fam == 'winged':
        c.wings_flap(P, u, 7, 1.0, lag=0.6)
        c.tails_sway(P, u, 12, 1.0, 0.7)
        for arm in r.arms:
            P.bend(arm.names[0], FWD, 4 * s)
        c.extras_sway(P, u, 10, 1.0)
        if not r.legs:
            c.root_move(P, z=0.01 * s2)
    elif fam == 'serpent':
        P.wave(r.body, LEFT, 9 * a, u, 1.0, 0.55, 0.0, taper=(0.5, 1.0))
        c.spine_pitch(P, 4 * s)
        c.mouth(P, 3 + 3 * math.sin(TAU * 2 * u))
        c.extras_sway(P, u, 10, 1.0)
    elif fam == 'fish':
        P.wave((r.spine + r.neck), LEFT, 6, u, 1.0, 0.5)
        c.tails_sway(P, u, 24, 2.0, 0.6)
        c.fins_move(P, u, 16, 2.0)
        c.mouth(P, 5 + 4 * math.sin(TAU * 2 * u))
        c.root_move(P, z=0.008 * s2)
    elif fam == 'blob':
        c.squash(P, 0.05 * s)
        c.sides_wobble(P, u, 0.06, 1.0)
        c.extras_sway(P, u, 14, 1.0)
        for arm in r.arms:
            P.bend(arm.names[0], OUT(arm.sign), 2 + 2 * s)
    elif fam == 'multi':
        for i, leg in enumerate(r.legs):
            P.bend(leg.names[0], FWD, 4 * math.sin(TAU * u + i))
        c.extras_sway(P, u, 12, 1.0, 0.8)
        c.tails_sway(P, u, 8, 1.0)
        for arm in r.arms:
            P.bend(arm.names[0], OUT(arm.sign), 10 + 6 * s)
    elif fam == 'plant':
        c.extras_sway(P, u, 14, 1.0, 0.7)
        c.spine_bend(P, LEFT, 4 * s)
        c.tails_sway(P, u, 8, 1.0)
    elif fam == 'float':
        c.root_move(P, z=0.03 * s + 0.06)
        c.spine_roll(P, 3 * math.sin(TAU * u + 1))
        c.extras_sway(P, u, 18, 1.0, 0.8)
        for arm in r.arms:
            P.bend(arm.names[0], OUT(arm.sign), 10 + 8 * s)
        c.tails_sway(P, u, 14, 1.0)
        c.sides_wobble(P, u, 0.05, 1.0)
    elif fam == 'radial':
        P.yaw(r.root, 4 * math.sin(TAU * u))
        c.extras_sway(P, u, 6, 2.0, 0.0, toward=UP)
        c.root_move(P, z=0.01 * s)
    c.ears_move(P, u, 4, 1.0, phase=0.5)


# ------------------------------------------------------------------------------------------------ Walk / Run
def locomote(c, P, u, run):
    r = c.rig
    k = 1.65 if run else 1.0
    cyc = 2.0 if not run else 4.0
    a = TAU * cyc * u
    fam = c.fam
    bob = abs(math.sin(a))
    if fam in ('biped', 'rock'):
        c.stride(P, u, cyc, 26 * k, 34 * k, 14 * k)
        c.arms_counter(P, u, cyc, 20 * k, 16 * k)
        c.root_move(P, z=(0.02 if run else 0.012) * bob * c.amp)
        c.spine_yaw(P, 8 * k * math.sin(a))
        c.spine_pitch(P, -(10 if run else 2) + 2 * math.cos(2 * a))
        c.head_look(P, yaw=-4 * k * math.sin(a), pitch=3 if run else 0)
        c.tails_sway(P, u, 14 * k, cyc, 0.8, vertical=6 * k)
        c.ears_move(P, u, 8 * k, cyc * 2)
        P.roll(r.hips, 5 * k * math.sin(a)) if r.hips in r.bones else None
        if c.heavy:
            c.squash(P, 0.02 * math.cos(2 * a))
    elif fam == 'quad':
        if run:   # bounding gallop: front pair together, hind pair together, spine flexing
            for l in r.legs:
                ph = 0.0 if l.fh == 'F' else 1.2
                aa = a + ph
                P.bend(l.names[0], FWD, 40 * math.sin(aa))
                if len(l.names) > 1:
                    P.bend(l.names[1], BACK, 45 * max(0, math.sin(aa + 1.0)))
                if len(l.names) > 2:
                    P.bend(l.names[2], FWD, 20 * max(0, math.sin(aa + 0.3)))
            c.spine_pitch(P, 10 * math.sin(a + 0.6))
            c.root_move(P, z=0.05 * abs(math.sin(a * 0.5 * 2)) * c.amp, f=0.0)
            c.head_look(P, pitch=6 * math.sin(a + 1.5))
        else:
            c.stride(P, u, cyc, 26, 32, 12)
            c.spine_yaw(P, 7 * math.sin(a))
            c.root_move(P, z=0.008 * bob * c.amp)
            c.head_look(P, pitch=4 * math.sin(2 * a), yaw=-3 * math.sin(a))
        c.tails_sway(P, u, 20 * k, cyc, 0.7, vertical=8)
        c.ears_move(P, u, 8 * k, cyc * 2, phase=1.0)
        c.extras_sway(P, u, 12 * k, cyc, 0.7)
    elif fam == 'bird':
        c.stride(P, u, cyc, 30 * k, 44 * k, 20 * k)
        for i, n in enumerate(r.neck):
            P.bend(n, FWD, 12 * k * math.sin(a + 1.0))
        P.bend(r.head, FWD, 10 * k * math.sin(a + 1.0)) if r.head in r.bones else None
        c.root_move(P, z=0.014 * bob * c.amp)
        c.wings_flap(P, u, 6 + (40 if run else 0), cyc if not run else cyc * 2, spread=(0 if not run else 40))
        c.tails_sway(P, u, 6, cyc, 0.5, vertical=10 * k)
        c.spine_pitch(P, -6 if run else 0)
    elif fam == 'winged':
        if r.legs:
            c.stride(P, u, cyc, 24 * k, 30 * k, 12 * k)
            c.arms_counter(P, u, cyc, 14 * k, 12 * k)
            c.root_move(P, z=0.012 * bob * c.amp)
            c.wings_flap(P, u, 8 + (32 if run else 0), cyc * (2 if run else 1), spread=(0 if not run else 45), phase=0.6)
            c.spine_pitch(P, -(8 if run else 1))
            c.tails_sway(P, u, 14 * k, cyc, 0.8)
        else:   # bats / moths glide: fast wing beat, body bob
            c.wings_flap(P, u, 45, cyc * 2 * (1.5 if run else 1), spread=30)
            c.root_move(P, z=0.08 + 0.03 * math.sin(a * 1.0) * c.amp)
            c.spine_pitch(P, -10 * k)
            c.extras_sway(P, u, 12, cyc)
            c.tails_sway(P, u, 10, cyc)
    elif fam == 'serpent':
        P.wave(r.body, LEFT, 26 * k * c.amp, u, cyc * 0.5, 0.62, 0.0, taper=(0.5, 1.3))
        c.spine_pitch(P, 6)
        c.root_move(P, x=0.015 * k * math.sin(a * 0.5))
        c.mouth(P, 4 + 3 * math.sin(a))
        c.extras_sway(P, u, 14, cyc * 0.5)
    elif fam == 'fish':
        P.wave((r.spine + r.neck), LEFT, 16 * k, u, cyc, 0.7)
        c.tails_sway(P, u, 38 * k, cyc, 0.6)
        c.fins_move(P, u, 26 * k, cyc * 2)
        c.root_move(P, z=0.02 * math.sin(a) * c.amp + 0.02)
        c.spine_pitch(P, -6 if run else 0)
        P.pitch(r.root, 4 * math.sin(a * 0.5))
        c.mouth(P, 8 + 8 * max(0, math.sin(a)))
    elif fam == 'blob':
        hp = abs(math.sin(a * 0.5))
        c.squash(P, 0.24 * k * math.cos(a) * 0.6)
        c.root_move(P, z=0.10 * k * hp * c.amp, f=0.0)
        P.pitch(r.root, -8 * k * math.sin(a * 0.5))
        c.sides_wobble(P, u, 0.12 * k, cyc)
        c.extras_sway(P, u, 20 * k, cyc, 0.6)
        for arm in r.arms:
            P.bend(arm.names[0], OUT(arm.sign), 20 * k + 12 * math.sin(a))
        c.ears_move(P, u, 12, cyc)
        for l in r.legs:
            P.bend(l.names[0], FWD, 26 * k * math.sin(a + (0 if l.sign > 0 else math.pi)))
    elif fam == 'multi':
        c.stride(P, u, cyc * 1.5, 18 * k, 26 * k, 8 * k, out=8 * k)
        c.root_move(P, z=0.008 * bob)
        c.extras_sway(P, u, 20 * k, cyc, 0.9)
        for i, arm in enumerate(r.arms):
            P.bend(arm.names[0], FWD, 14 * k * math.sin(a + i * math.pi))
        c.spine_yaw(P, 5 * math.sin(a))
        c.tails_sway(P, u, 10, cyc)
        if not r.legs:   # jellyfish: pulse and drift
            c.squash(P, 0.08 * math.sin(a))
            c.root_move(P, z=0.05 + 0.04 * math.sin(a))
    elif fam == 'plant':
        if r.legs:
            c.stride(P, u, cyc, 20 * k, 26 * k, 8 * k)
            c.root_move(P, z=0.01 * bob)
            P.roll(r.hips, 7 * k * math.sin(a)) if r.hips in r.bones else None
        else:
            c.root_move(P, z=0.05 * k * abs(math.sin(a * 0.5)) * c.amp)
            c.squash(P, 0.10 * math.cos(a))
        c.extras_sway(P, u, 22 * k, cyc, 0.8)
        c.spine_bend(P, LEFT, 8 * k * math.sin(a))
        c.tails_sway(P, u, 10, cyc)
    elif fam == 'float':
        c.root_move(P, z=0.07 + 0.02 * math.sin(a * 0.5) , f=0.0)
        P.pitch(r.root, -10 * k)
        c.extras_sway(P, u, 24 * k, cyc * 0.5, 0.9)
        for arm in r.arms:
            P.bend(arm.names[0], BACK, 20 * k)
            P.bend(arm.names[0], OUT(arm.sign), 10 * math.sin(a))
        c.tails_sway(P, u, 20 * k, cyc * 0.5, 0.7)
        c.spine_roll(P, 6 * k * math.sin(a * 0.5))
        c.sides_wobble(P, u, 0.08, cyc * 0.5)
    elif fam == 'radial':
        P.roll(r.root, 20 * k * math.sin(a * 0.5))
        P.yaw(r.root, 360 * u * (1 if run else 0.5))
        c.root_move(P, z=0.04 * abs(math.sin(a * 0.5)))
        c.extras_sway(P, u, 20 * k, cyc, 0.5, toward=UP)


# ------------------------------------------------------------------------------------------------ one-shot base clips
def _attack_arch(c):
    """each species swings a different physical move at Attack, chosen from what its body can do."""
    r = c.rig
    fam = c.fam
    n = c.opt('attack', 3)
    if fam == 'biped':
        return ['strike', 'tackle', 'kick'][n] if r.arms else ['tackle', 'bite', 'headbutt'][n]
    if fam == 'quad':
        return ['bite', 'strike', 'headbutt'][n] if r.legs else 'tackle'
    if fam == 'bird':
        return ['headbutt', 'strike', 'multi_strike'][n]
    if fam == 'winged':
        return ['bite', 'strike', 'whip'][n] if (r.arms or r.tails) else ['bite', 'wing_beat', 'tackle'][n]
    if fam == 'serpent':
        return ['bite', 'whip', 'slam'][n]
    if fam == 'fish':
        return ['bite', 'tackle', 'whip'][n]
    if fam == 'blob':
        return ['slam', 'tackle', 'strike'][n] if r.arms else ['slam', 'tackle', 'headbutt'][n]
    if fam == 'multi':
        return ['strike', 'bite', 'whip'][n] if r.arms else ['whip', 'tackle', 'bind'][n]
    if fam == 'plant':
        return ['whip', 'bite', 'slam'][n]
    if fam == 'float':
        return ['tackle', 'strike', 'bite'][n] if r.arms else ['tackle', 'bite', 'whip'][n]
    if fam == 'rock':
        return ['slam', 'tackle', 'strike'][n] if r.arms else ['tackle', 'slam', 'headbutt'][n]
    return ['spin_attack', 'tackle', 'slam'][n]


def _special_arch(c):
    types = c.spec.get('types', ['NORMAL'])
    base = A_SPECIAL.get(types[0], 'beam')
    alt = A_SPECIAL_ALT.get(types[-1], 'flash')
    return base if c.opt('special', 2) == 0 else alt


A_SPECIAL = {'FIRE': 'burst', 'WATER': 'beam', 'ELECTRIC': 'shock', 'GRASS': 'powder', 'ICE': 'beam', 'POISON': 'burst',
             'GROUND': 'slam', 'PSYCHIC_TYPE': 'psychic', 'GHOST': 'sing', 'DRAGON': 'burst', 'FLYING': 'wing_beat',
             'BUG': 'powder', 'ROCK': 'throw', 'FIGHTING': 'focus', 'NORMAL': 'beam'}
A_SPECIAL_ALT = {'FIRE': 'flash', 'WATER': 'burst', 'ELECTRIC': 'flash', 'GRASS': 'beam', 'ICE': 'burst', 'POISON': 'powder',
                 'GROUND': 'throw', 'PSYCHIC_TYPE': 'flash', 'GHOST': 'psychic', 'DRAGON': 'beam', 'FLYING': 'flash',
                 'BUG': 'beam', 'ROCK': 'slam', 'FIGHTING': 'flash', 'NORMAL': 'flash'}


def attack(c, P, u):
    A.ARCH[_attack_arch(c)](c, P, u, {'side': 1.0 if c.opt('atk_side', 2) == 0 else -1.0, 'power': 1.0 + 0.1 * (c.mass - 3)})


def special(c, P, u):
    arch = _special_arch(c)
    A.ARCH[arch](c, P, u, {'sweep': c.opt('sp_sweep', 2), 'reps': 3, 'open': 1.0, 'side': -1.0 if c.opt('sp_side', 2) else 1.0})


def hurt(c, P, u):
    r = c.rig
    hit = bump(u, 0.0, 0.14, 0.7)
    w = math.sin(TAU * 3 * u) * hit
    dirn = c.jit('hurt_dir', -1, 1)
    c.root_move(P, f=-0.11 * hit * (1.3 - 0.15 * c.mass), z=0.008 * hit, x=0.02 * dirn * hit)
    c.squash(P, 0.10 * bump(u, 0.05, 0.18, 0.45) - 0.04 * bump(u, 0.3, 0.45, 0.7))
    c.spine_pitch(P, 20 * hit)
    c.head_look(P, pitch=22 * hit, yaw=10 * w + 12 * dirn * hit)
    c.mouth(P, 26 * bump(u, 0.02, 0.15, 0.4))
    for a in r.arms:
        P.bend(a.names[0], OUT(a.sign), 35 * hit)
        P.bend(a.names[0], BACK, 20 * hit)
    for wg in r.wings:
        P.bend(wg.names[0], OUT(wg.sign), 45 * hit)
    c.tails_pose(P, UP, 22 * hit)
    c.tails_sway(P, u, 26 * w, 1.0)
    c.ears_move(P, u, 10 * hit, 3.0, flick=30 * hit)
    c.extras_sway(P, u, 20 * hit, 3.0)
    for l in r.legs:
        P.bend(l.names[0], FWD if l.fh != 'H' else BACK, 10 * hit)
    if r.serpent:
        c.spine_bend(P, LEFT, 40 * w)
        c.spine_pitch(P, 25 * hit)
    c.sides_wobble(P, u, 0.15 * hit, 3.0)


def faint(c, P, u):
    r = c.rig
    fall = sm((u - 0.08) / 0.62)
    bounce = bump(u, 0.62, 0.7, 0.82) * 0.02
    fam = c.fam
    dirn = 1.0 if c.opt('faint_side', 2) == 0 else -1.0
    if fam in ('biped', 'rock', 'winged', 'bird', 'plant') and (r.legs or fam == 'plant'):
        # topple backwards (or sideways) and lie down
        style = c.opt('faint', 3)
        if style == 0:      # backwards
            P.pitch(r.root, 84 * fall)
            c.root_move(P, f=-0.30 * fall, z=0.05 * fall + bounce)
        elif style == 1:    # sideways
            P.roll(r.root, dirn * 86 * fall)
            c.root_move(P, x=dirn * -0.26 * fall, z=0.05 * fall + bounce)
        else:               # crumple forward, then flop
            P.pitch(r.root, -70 * fall)
            c.root_move(P, f=0.24 * fall, z=0.04 * fall + bounce)
        c.crouch(P, 0.5 * fall)
        for a in r.arms:
            P.bend(a.names[0], OUT(a.sign), 55 * fall)
        for wg in r.wings:
            P.bend(wg.names[0], OUT(wg.sign), 60 * fall)
    elif fam == 'quad' or fam == 'multi':
        P.roll(r.root, dirn * 90 * fall)
        c.root_move(P, x=-dirn * 0.20 * fall, z=0.03 * fall + bounce)
        for l in r.legs:
            P.bend(l.names[0], OUT(l.sign), 40 * fall)
            if len(l.names) > 1:
                P.bend(l.names[1], BACK, 40 * fall)
    elif fam == 'serpent':
        P.wave(r.body, LEFT, 60 * fall, u, 0.5, 0.5)
        c.spine_pitch(P, -60 * fall)
        c.root_move(P, z=0.0)
    elif fam == 'fish':
        P.roll(r.root, dirn * 92 * fall)
        c.root_move(P, z=0.05 * fall)
        c.tails_sway(P, u, 30 * fall, 1.5)
    elif fam in ('blob', 'radial'):
        P.scale(r.root, 1 + 0.5 * fall, 1 + 0.5 * fall, 1 - 0.55 * fall)
        c.root_move(P, z=-0.03 * fall)
    elif fam in ('float', 'winged', 'bird'):     # airborne bodies without legs to fall on: tumble and sink
        for w in r.wings:
            P.bend(w.names[0], BACK, 50 * fall)
        c.root_move(P, z=-0.05 * fall + 0.05 * (1 - fall))
        P.roll(r.root, dirn * 60 * fall)
        P.pitch(r.root, 30 * fall)
    c.head_look(P, pitch=18 * fall, roll=dirn * 12 * fall)
    c.mouth(P, 12 * fall)
    c.tails_sway(P, u, 26 * fall, 0.5, 0.6)
    c.extras_sway(P, u, 20 * fall, 0.5)
    c.ears_move(P, u, 6, 0.0, flick=-25 * fall)
    c.sides_wobble(P, u, 0.1 * fall, 1.0)


def victory(c, P, u):
    r = c.rig
    style = c.opt('victory', 3)
    hop = abs(math.sin(TAU * 2 * u))
    env = hold(u, 0.0, 0.1, 0.85, 1.0)
    if style == 0:      # bouncy cheer, arms/wings up
        c.root_move(P, z=0.13 * hop * env * c.amp)
        c.squash(P, 0.08 * (1 - hop) * env)
        for a in r.arms:
            c.arm_pose(P, 'up', 0.6 * env * (0.6 + 0.4 * hop), which=[r.arms.index(a)])
        c.wings_flap(P, u, 30 * env, 4.0, spread=40 * env)
        c.ears_move(P, u, 14 * env, 4.0)
        c.tails_sway(P, u, 28 * env, 4.0, 0.5)
        c.spine_pitch(P, 8 * env)
    elif style == 1:    # spin on the spot and strike a pose
        g = sm((u - 0.1) / 0.5)
        P.yaw(r.root, 360 * g)
        c.root_move(P, z=0.06 * math.sin(math.pi * min(1, max(0, (u - 0.1) / 0.5))) * c.amp)
        pose_k = hold(u, 0.55, 0.65, 0.9, 1.0)
        c.spine_pitch(P, 14 * pose_k)
        for a in r.arms:
            c.arm_pose(P, 'out', 0.8 * pose_k, which=[r.arms.index(a)])
        c.head_look(P, pitch=16 * pose_k)
        c.tails_pose(P, UP, 40 * pose_k)
        c.mouth(P, 20 * pose_k)
        c.wings_flap(P, u, 20 * pose_k, 3.0, spread=45 * pose_k)
        c.extras_sway(P, u, 20 * pose_k, 3.0)
    else:               # proud roar + chest thump / tail wag
        pose_k = hold(u, 0.05, 0.25, 0.85, 1.0)
        c.spine_pitch(P, 20 * pose_k)
        c.head_look(P, pitch=26 * pose_k, yaw=8 * math.sin(TAU * 2 * u) * pose_k)
        c.mouth(P, 32 * bump(u, 0.2, 0.3, 0.55) + 20 * bump(u, 0.6, 0.7, 0.8))
        for i, a in enumerate(r.arms):
            P.bend(a.names[0], FWD, 65 * pose_k * (0.5 + 0.5 * math.sin(TAU * 3 * u + i * math.pi)) + 20 * pose_k)
        c.tails_sway(P, u, 24 * pose_k, 3.0, 0.5, vertical=10)
        c.root_move(P, z=0.03 * pose_k)
        c.wings_flap(P, u, 26 * pose_k, 2.0, spread=35 * pose_k)
        c.extras_sway(P, u, 16 * pose_k, 3.0)
    if r.serpent:
        rear_k = hold(u, 0.05, 0.3, 0.85, 1.0)
        c.spine_pitch(P, 40 * rear_k)
        P.wave(r.body, LEFT, 12 * rear_k, u, 2.0, 0.5)
    for l in r.legs:
        P.bend(l.names[0], FWD, 3)
    c.sides_wobble(P, u, 0.1 * env, 4.0)


def sleep(c, P, u):
    r = c.rig
    s = math.sin(TAU * u)
    fam = c.fam
    c.root_move(P, z=-0.06 if r.legs else 0.0)
    P.scale(r.root, 1 + 0.01 * s, 1 + 0.01 * s, 1 + 0.03 * s)
    c.crouch(P, 0.9)
    c.spine_pitch(P, -18)
    c.head_look(P, pitch=-32 + 2 * s, roll=8 * (1 if c.opt('sleep_side', 2) else -1))
    c.mouth(P, 3 + 2 * s)
    for a in r.arms:
        c.arm_pose(P, 'tuck', 0.7, which=[r.arms.index(a)])
        P.bend(a.names[0], FWD, 3 * s)
    for w in r.wings:
        P.bend(w.names[0], BACK, 30)
        P.rotw(w.names[0], FWD, w.sign * 4 * s)
    c.tails_pose(P, LEFT, 40)
    c.tails_sway(P, u, 3, 1.0)
    c.ears_move(P, u, 3, 1.0, flick=-30)
    c.extras_sway(P, u, 3, 1.0)
    if fam == 'serpent':
        n = len(r.body)
        for i, b in enumerate(r.body):
            P.yaw(b, min(32.0, 260.0 / n))
        c.spine_pitch(P, -30)
        P.wave(r.body, LEFT, 3, u, 1.0, 0.3)
    if fam == 'float':
        c.root_move(P, z=0.05 + 0.02 * s)
        P.pitch(r.root, 20)
    if fam in ('blob', 'radial'):
        c.squash(P, 0.10 + 0.04 * s)
    if fam == 'fish':
        P.roll(r.root, 20)
        c.root_move(P, z=0.02 * s)
    if fam == 'bird':
        c.head_look(P, yaw=140 if c.opt('bird_sleep', 2) else 0, pitch=-20)
    if fam == 'plant':
        c.spine_bend(P, FWD, 20)
        c.extras_sway(P, u, 3, 1.0)
    c.sides_wobble(P, u, 0.03, 1.0)


def roar(c, P, u):
    r = c.rig
    rear, shout = bump(u, 0.0, 0.3, 0.55), hold(u, 0.28, 0.4, 0.8, 0.95)
    sh = math.sin(TAU * 8 * u) * shout
    style = c.opt('roar', 2)
    rear_amt = 30 if style == 0 else 14
    A.rear_up(c, P, rear, rear_amt)
    c.head_look(P, pitch=(30 if style == 0 else 8) * rear + 8 * sh, yaw=6 * sh)
    c.mouth(P, 55 * shout * (0.85 + 0.15 * math.sin(TAU * 6 * u)))
    c.root_move(P, z=0.02 * rear + 0.006 * sh, x=0.005 * sh)
    P.scale(r.root, 1 - 0.03 * shout, 1 - 0.03 * shout, 1 + 0.06 * shout)
    for a in r.arms:
        c.arm_pose(P, 'out' if style == 0 else 'guard', 0.6 * rear, which=[r.arms.index(a)])
    for w in r.wings:
        P.bend(w.names[0], OUT(w.sign), 60 * rear)
        P.rotw(w.names[0], FWD, w.sign * 12 * sh)
    c.tails_pose(P, UP, 25 * rear)
    c.tails_sway(P, u, 18 * sh, 1.0)
    c.ears_move(P, u, 8, 0.0, flick=35 * rear)
    c.extras_sway(P, u, 18 * shout, 4.0)
    c.crouch(P, 0.25 * rear)
    c.sides_wobble(P, u, 0.1 * shout, 8.0)


def dodge(c, P, u):
    r = c.rig
    sd = bump(u, 0.0, 0.35, 0.92)
    dirn = 1.0 if c.opt('dodge_side', 2) == 0 else -1.0
    c.root_move(P, x=0.32 * dirn * sd * c.amp, z=0.035 * math.sin(math.pi * u), f=-0.04 * sd)
    P.roll(r.root, -14 * dirn * sd)
    P.yaw(r.root, 10 * dirn * sd)
    c.spine_roll(P, 10 * dirn * sd)
    c.head_look(P, roll=-10 * dirn * sd, yaw=-14 * dirn * sd)
    for l in r.legs:
        P.bend(l.names[0], OUT(l.sign), 18 * sd * dirn * l.sign)
        P.bend(l.names[0], FWD, 18 * sd * (1 if (l.sign * dirn) > 0 else -1))
    for a in r.arms:
        P.bend(a.names[0], OUT(a.sign), 28 * sd)
    for w in r.wings:
        P.bend(w.names[0], OUT(w.sign), 45 * sd)
    c.tails_sway(P, u, 26 * sd * dirn, 0.5)
    if r.serpent:
        P.wave(r.body, LEFT, 34 * sd * dirn, u, 0.5, 0.6)
    c.squash(P, 0.06 * bump(u, 0.05, 0.15, 0.4))
    c.ears_move(P, u, 6, 0.0, flick=20 * sd)


def spin(c, P, u):
    r = c.rig
    g = sm(u)
    k = bump(u, 0.0, 0.5, 1.0)
    turns = 1 + (1 if c.light and c.opt('spin_turns', 2) else 0)
    P.yaw(r.root, 360 * turns * g)
    c.root_move(P, z=0.05 * k * c.amp)
    for a in r.arms:
        c.arm_pose(P, 'out', 0.7 * k, which=[r.arms.index(a)])
    for w in r.wings:
        P.bend(w.names[0], OUT(w.sign), 70 * k)
    c.tails_pose(P, LEFT, 35 * k)
    for t in r.tails:
        P.chain(t.names, OUT(t.sign or 1.0), 45 * k)
    for e in r.extras:
        P.chain(e.names, OUT(e.sign), 40 * k)
    for e in r.ears:
        P.bend(e.names[0], BACK, 30 * k)
    c.spine_roll(P, 8 * k)
    c.squash(P, -0.04 * k)
    if r.serpent:
        c.spine_bend(P, LEFT, 55 * k)
    for l in r.legs:
        P.bend(l.names[0], BACK, 20 * k)


def hop(c, P, u):
    r = c.rig
    sq, air = bump(u, 0.0, 0.14, 0.32), bump(u, 0.22, 0.5, 0.82)
    jump = math.sin(math.pi * min(max((u - 0.25) / 0.5, 0.0), 1.0))
    land = bump(u, 0.72, 0.8, 0.95)
    hh = 0.26 * (1.25 - 0.1 * c.mass)
    c.root_move(P, z=hh * jump * c.amp)
    c.squash(P, 0.10 * sq + 0.07 * land - 0.06 * air)
    c.crouch(P, 0.55 * sq + 0.35 * land)
    for l in r.legs:
        P.bend(l.names[0], BACK if l.fh != 'F' else FWD, 34 * air)
    for a in r.arms:
        P.bend(a.names[0], OUT(a.sign), 32 * air)
        P.bend(a.names[0], FWD, 20 * air)
    c.wings_flap(P, u, 25 * air, 2.0, spread=30 * air)
    c.spine_pitch(P, 8 * air - 6 * sq)
    c.head_look(P, pitch=8 * air)
    c.tails_sway(P, u, 12, 1.0, 0.4, vertical=18 * air)
    c.ears_move(P, u, 10 * air, 2.0)
    c.extras_sway(P, u, 14 * air, 2.0)
    if r.serpent:
        P.wave(r.body, UP, 24 * air, u, 1.0, 0.5)
    c.sides_wobble(P, u, 0.1 * air, 2.0)


def charge(c, P, u):
    r = c.rig
    sh = math.sin(TAU * 6 * u)
    k = 1.0
    c.squash(P, 0.05 + 0.02 * sh)
    c.root_move(P, x=0.008 * sh, z=-0.03 if r.legs else 0.0)
    c.crouch(P, 0.5)
    c.spine_pitch(P, -10 + 3 * sh)
    c.head_look(P, pitch=-12 + 3 * math.sin(TAU * 3 * u))
    for a in r.arms:
        c.arm_pose(P, 'guard', 0.7, which=[r.arms.index(a)], u=u, cycles=3.0)
    for w in r.wings:
        P.bend(w.names[0], OUT(w.sign), 40)
        P.rotw(w.names[0], FWD, w.sign * 10 * sh)
    c.tails_pose(P, UP, 30)
    c.tails_sway(P, u, 14, 3.0, 0.4)
    c.ears_move(P, u, 4, 3.0, flick=25)
    c.extras_sway(P, u, 16, 3.0, 0.3)
    c.sides_wobble(P, u, 0.08, 6.0)
    if r.serpent:
        c.spine_pitch(P, 20)
        P.wave(r.body, LEFT, 10, u, 3.0, 0.3)
    c.mouth(P, 6 + 4 * sh)


def taunt(c, P, u):
    r = c.rig
    style = c.opt('taunt', 3)
    c2 = math.sin(TAU * 2 * u)
    c4 = math.sin(TAU * 4 * u)
    if style == 0:      # side-to-side swagger with waving hands
        P.roll(r.root, 8 * c2)
        c.root_move(P, x=0.03 * c2, z=0.02 * abs(c2))
        c.head_look(P, roll=14 * c4)
        for a in r.arms:
            P.bend(a.names[0], OUT(a.sign), 35 + 25 * c4)
    elif style == 1:    # bounce and beckon
        c.root_move(P, z=0.03 * abs(math.sin(TAU * 4 * u)) * c.amp)
        c.spine_pitch(P, -8 + 6 * c4)
        c.head_look(P, pitch=10 * c4, yaw=12 * c2)
        for i, a in enumerate(r.arms):
            P.bend(a.names[0], FWD, 70 + 35 * math.sin(TAU * 2 * u + i * 1.5))
        c.mouth(P, 14 + 10 * c4)
    else:               # shimmy: tail and hips
        P.yaw(r.root, 14 * c2)
        c.spine_yaw(P, -18 * c2)
        c.head_look(P, yaw=16 * c2)
        c.root_move(P, z=0.015 * abs(c4))
        for a in r.arms:
            P.bend(a.names[0], FWD, 35 * math.sin(TAU * 2 * u + a.sign))
    c.tails_sway(P, u, 34, 4.0, 0.5)
    c.tails_pose(P, UP, 15)
    c.ears_move(P, u, 12, 4.0)
    c.extras_sway(P, u, 22, 4.0)
    for w in r.wings:
        P.rotw(w.names[0], FWD, w.sign * 18 * c4)
        P.bend(w.names[0], OUT(w.sign), 30)
    if r.serpent:
        P.wave(r.body, LEFT, 22, u, 2.0, 0.5)
        c.spine_pitch(P, 20)
    c.sides_wobble(P, u, 0.1, 4.0)
    for l in r.legs:
        P.bend(l.names[0], FWD, 5 * c2 * l.sign)


def spawn(c, P, u):
    r = c.rig
    if u < 0.6:
        sc = 0.05 + 1.10 * sm(u / 0.6)
    else:
        sc = 1.15 - 0.15 * sm((u - 0.6) / 0.4)
    P.scale(r.root, sc, sc, sc)
    style = c.opt('spawn', 2)
    P.yaw(r.root, (180 if style == 0 else -270) * (1 - sm(u / 0.7)))
    c.root_move(P, z=0.10 * math.sin(math.pi * u) + (0.0 if style == 0 else 0.10 * (1 - sm(u / 0.5))))
    c.wings_flap(P, u, 25 * bump(u, 0.2, 0.5, 0.85), 3.0, spread=50 * bump(u, 0.2, 0.5, 0.85))
    for a in r.arms:
        c.arm_pose(P, 'up', 0.5 * bump(u, 0.3, 0.55, 0.9), which=[r.arms.index(a)])
    c.tails_sway(P, u, 20 * bump(u, 0.3, 0.6, 1.0), 2.0)


def hover(c, P, u):
    r = c.rig
    s = math.sin(TAU * u)
    lift = 0.13 if c.fam != 'float' else 0.10
    c.root_move(P, z=lift + 0.03 * s * c.amp)
    fl = math.sin(TAU * 3 * u)
    if r.wings:
        c.wings_flap(P, u, 38, 3.0, spread=42, phase=0.0)
    else:
        for a in r.arms:
            P.bend(a.names[0], OUT(a.sign), 25 + 12 * fl)
    for l in r.legs:
        P.bend(l.names[0], BACK, 22)
        if len(l.names) > 1:
            P.bend(l.names[1], BACK, 25)
    c.spine_pitch(P, 4 * s)
    c.head_look(P, pitch=3 * math.sin(TAU * u - 0.8), yaw=5 * math.sin(TAU * u + 1))
    c.tails_sway(P, u, 18, 1.0, 0.7)
    c.ears_move(P, u, 8, 1.0)
    c.extras_sway(P, u, 20, 1.0, 0.8)
    c.sides_wobble(P, u, 0.05, 1.0)
    if r.serpent:
        P.wave(r.body, UP, 16, u, 1.0, 0.6)
        c.spine_pitch(P, 40)
    if c.fam == 'radial':
        P.yaw(r.root, 360 * u)
    if c.fam in ('blob',):
        c.squash(P, 0.05 * s)
    P.roll(r.root, 3 * math.sin(TAU * u + 1.3))


def talk(c, P, u):
    r = c.rig
    b = math.sin(TAU * 4 * u)
    b2 = math.sin(TAU * 2 * u + c.jit('talk_ph', 0, 6))
    c.head_look(P, pitch=8 * b, yaw=8 * b2, roll=3 * math.sin(TAU * u))
    c.mouth(P, 18 * max(0.0, b) + 4)
    P.scale(r.root, 1, 1, 1 + 0.02 * b)
    style = c.opt('talk', 2)
    for i, a in enumerate(r.arms):
        if style == 0:
            P.bend(a.names[0], FWD, 25 + 18 * math.sin(TAU * 2 * u + i * 2.2))
            P.bend(a.names[0], OUT(a.sign), 10)
        else:
            P.bend(a.names[0], OUT(a.sign), 22 + 12 * b)
    c.tails_sway(P, u, 10, 2.0, 0.6)
    c.ears_move(P, u, 6, 2.0)
    c.extras_sway(P, u, 8, 2.0)
    c.spine_pitch(P, 2 * b)
    for w in r.wings:
        P.rotw(w.names[0], FWD, w.sign * 6 * b)
    if r.serpent:
        P.wave(r.body, LEFT, 8, u, 2.0, 0.5)
        c.spine_pitch(P, 20)
    c.sides_wobble(P, u, 0.04, 4.0)


# ------------------------------------------------------------------------------------------------ idle variants (one-shot, start/end at rest)
def idle_look(c, P, u):
    k = hold(u, 0.05, 0.25, 0.75, 1.0)
    look = math.sin(TAU * u * 1.0) * hold(u, 0.05, 0.2, 0.8, 0.98)
    c.head_look(P, yaw=(38 if c.fam != 'serpent' else 30) * look, pitch=6 * k)
    c.spine_yaw(P, 12 * look)
    c.ears_move(P, u, 10 * k, 2.0, phase=0.3)
    c.tails_sway(P, u, 14 * k, 2.0, 0.6)
    c.extras_sway(P, u, 10 * k, 2.0)
    for w in c.rig.wings:
        P.rotw(w.names[0], FWD, w.sign * 8 * k * math.sin(TAU * 3 * u))
    c.root_move(P, z=0.004 * k)
    P.yaw(c.rig.root, 10 * look)


def idle_stretch(c, P, u):
    k = hold(u, 0.05, 0.35, 0.65, 0.95)
    yawn = bump(u, 0.3, 0.45, 0.7)
    c.spine_pitch(P, 16 * k)
    c.head_look(P, pitch=24 * k)
    c.mouth(P, 40 * yawn)
    for a in c.rig.arms:
        c.arm_pose(P, 'up', 0.6 * k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 55 * k)
    for l in c.rig.legs:
        if l.fh == 'F':
            P.bend(l.names[0], FWD, 40 * k)
        P.bend(l.names[0], FWD, 0)
    if c.rig.legs and c.fam == 'quad':
        c.spine_pitch(P, -30 * k)
        c.root_move(P, z=-0.02 * k)
    c.tails_pose(P, UP, 30 * k)
    c.ears_move(P, u, 5, 0.0, flick=-20 * k)
    c.squash(P, -0.05 * k + 0.02 * yawn)
    c.extras_sway(P, u, 14 * k, 1.0)
    if c.rig.serpent:
        c.spine_pitch(P, 35 * k)
    c.sides_wobble(P, u, 0.06 * k, 1.0)


def idle_fidget(c, P, u):
    k = hold(u, 0.05, 0.2, 0.8, 0.98)
    sh = math.sin(TAU * 5 * u) * k
    n = c.opt('fidget', 3)
    r = c.rig
    if n == 0:      # shake it off
        c.spine_yaw(P, 22 * sh)
        c.head_look(P, yaw=20 * sh)
        c.tails_sway(P, u, 30 * k, 5.0, 0.4)
        c.ears_move(P, u, 20 * k, 5.0)
        c.extras_sway(P, u, 25 * k, 5.0, 0.3)
        P.yaw(r.root, 8 * sh)
    elif n == 1:    # scratch / preen with a limb
        head_dn = -22 * k
        c.head_look(P, pitch=head_dn, yaw=18 * k)
        limb = (r.arms or r.legs or r.wings or r.extras)
        if limb:
            l = limb[0]
            P.bend(l.names[0], FWD, 70 * k + 25 * sh)
            if len(l.names) > 1:
                P.bend(l.names[1], FWD, 60 * k)
        c.root_move(P, z=-0.01 * k)
        c.spine_pitch(P, -8 * k)
    if n != 2:      # every fidget also wriggles the whole body a little (bodies without limbs would barely move otherwise)
        P.roll(r.root, 5 * math.sin(TAU * 2 * u) * k)
        c.head_look(P, yaw=14 * math.sin(TAU * 3 * u) * k, roll=6 * sh)
        c.squash(P, 0.05 * math.sin(TAU * 4 * u) * k)
    else:           # little hop-turn
        c.root_move(P, z=0.06 * bump(u, 0.2, 0.4, 0.6) * c.amp + 0.06 * bump(u, 0.6, 0.8, 0.95) * c.amp)
        P.yaw(r.root, 45 * math.sin(TAU * u))
        c.squash(P, 0.06 * bump(u, 0.05, 0.15, 0.3) + 0.06 * bump(u, 0.5, 0.6, 0.7))
        c.tails_sway(P, u, 20 * k, 3.0)
        c.ears_move(P, u, 10 * k, 3.0)
        c.wings_flap(P, u, 20 * k, 3.0, spread=20 * k)


BASE_FN = {
    'Idle': idle, 'Walk': lambda c, P, u: locomote(c, P, u, False), 'Run': lambda c, P, u: locomote(c, P, u, True),
    'Attack': attack, 'Special': special, 'Hurt': hurt, 'Faint': faint, 'Victory': victory, 'Sleep': sleep, 'Roar': roar,
    'Dodge': dodge, 'Spin': spin, 'Hop': hop, 'Charge': charge, 'Taunt': taunt, 'Spawn': spawn, 'Hover': hover, 'Talk': talk,
    'IdleLook': idle_look, 'IdleStretch': idle_stretch, 'IdleFidget': idle_fidget,
}

# archetype length in frames at tempo 1.0
ARCH_LEN = {'beam': 48, 'burst': 40, 'shock': 40, 'strike': 32, 'multi_strike': 38, 'bite': 32, 'headbutt': 32, 'tackle': 34,
            'slam': 40, 'spin_attack': 36, 'throw': 36, 'whip': 40, 'bind': 48, 'dive': 44, 'fly_up': 48, 'wing_beat': 40,
            'sing': 48, 'powder': 44, 'harden': 44, 'focus': 48, 'menace': 40, 'rest_heal': 56, 'explode': 44, 'morph': 44,
            'psychic': 48, 'flop': 40, 'flash': 36, 'dash': 32, 'kick': 32, 'leech': 44, 'leap_strike': 40}
RENAME = {'FLY': 'FlyUp', 'ROAR': 'RoarCall', 'SPLASH': 'SplashFlop', 'HAZE': 'HazeMist', 'REST': 'RestUp', 'SING': 'SingSong'}


def build_catalog(sid, spec, sk, all_species):
    """OrderedDict name -> Clip: 18 base + 3 idle variants + 6..10 signature clips from the learnset."""
    c = Ctx(sid, spec, sk)
    cat = OrderedDict()
    for name in BASE_CLIPS + IDLE_VARIANTS:
        cat[name] = Clip(name, c.frames(LEN[name]) if name not in ('Idle', 'Sleep', 'Hover') else c.frames(LEN[name], 30), name in LOOPING, BASE_FN[name])
    used = {_attack_arch(c), _special_arch(c)}
    sd = all_species.get(sid) or {'types': spec.get('types', ['NORMAL']), 'learn': [], 'moves1': [], 'tmhm': [], 'evos': []}
    moves = SP.signature_moves(sid, sd, all_species, exclude_arch=used, want=9, minimum=7)
    for m in moves:
        arch, var = SP.MOVE_ARCH[m]
        var = dict(var)
        var.setdefault('side', 1.0 if h01(sid, m, 'side') < 0.5 else -1.0)
        var.setdefault('power', 0.9 + 0.3 * h01(sid, m, 'pw'))
        nm = RENAME.get(m, SP.clip_name(m))
        fn = (lambda a, v: (lambda cc, P, u: A.ARCH[a](cc, P, u, v)))(arch, var)
        cat[nm] = Clip(nm, c.frames(ARCH_LEN[arch], 20), False, fn, 'signature', arch)
        cat[nm].move = m
    cat.ctx = c
    return cat


def sample(ctx, clip, f):
    """the Pose of frame f of a clip; looping clips return to frame 0 on the last frame."""
    n = clip.frames
    if clip.loop and f >= n:
        f = 0
    P = ctx.pose()
    clip.fn(ctx, P, f / n)
    return P

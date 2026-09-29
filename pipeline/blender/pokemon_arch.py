"""Move archetypes: one-shot motions used for the Attack/Special base clips and for the species-signature clips.

Every function is fn(ctx, pose, u, v) with u in [0,1]; v is a dict of per-clip variation (side, reps, power, seed).  All of them
start and end in the rest pose (so they blend into Idle) and degrade gracefully on bodies that lack the limb they prefer
(a striker without arms uses its front legs, tail or head).
"""
import math

import numpy as np

from pokemon_anim import (bump, hold, sm, TAU, OUT, IN, h01)
from pokemon_pose import UP, DOWN, FWD, BACK, LEFT, RIGHT


# ------------------------------------------------------------------------------------------------ helpers
def striker(c, v):
    """(kind, chain) the body uses to hit: arm > front leg > tail > head."""
    r = c.rig
    side = v.get('side', 1.0)
    if r.arms:
        arms = sorted(r.arms, key=lambda a: (a.sign != side, a.gid))
        return 'arm', arms[0]
    if r.wings and c.fam in ('bird', 'winged'):
        ws = sorted(r.wings, key=lambda a: (a.sign != side, a.gid))
        return 'wing', ws[0]
    fl = [l for l in r.legs if l.fh in ('F', '')]
    if fl and c.fam in ('quad', 'multi', 'biped'):
        fl = sorted(fl, key=lambda a: (a.sign != side, a.gid))
        return 'leg', fl[0]
    if r.tails:
        return 'tail', r.tails[0]
    if r.extras:
        return 'extra', r.extras[0]
    return 'head', None


def rear_up(c, P, k, deg=30.0):
    """raise the front of the body (rearing, chest out)."""
    r = c.rig
    if r.serpent:
        c.spine_pitch(P, deg * 1.6 * k)
    else:
        c.spine_pitch(P, deg * k)
        c.head_look(P, pitch=deg * 0.5 * k)


def lunge(c, P, f, dip=0.0):
    c.root_move(P, f=f * c.amp, z=-dip)


def brace(c, P, k):
    if c.rig.legs:
        c.crouch(P, 0.55 * k)
    else:
        c.root_move(P, z=-0.03 * k)


def tail_react(c, P, u, k, amp=18.0):
    c.tails_pose(P, UP, 18 * k)
    c.tails_sway(P, u, amp * abs(k), 2.0)


def shake_body(c, P, u, k, freq=14, amp=0.008):
    c.root_move(P, x=amp * math.sin(TAU * freq * u) * k)


# ------------------------------------------------------------------------------------------------ archetypes
def strike(c, P, u, v):
    kind, ch = striker(c, v)
    wind, hit = bump(u, 0.0, 0.26, 0.42), bump(u, 0.34, 0.5, 0.86)
    s = v.get('side', 1.0)
    pw = v.get('power', 1.0)
    lunge(c, P, 0.10 * hit * pw, 0.02 * wind)
    c.spine_pitch(P, 8 * wind - 12 * hit)
    c.spine_yaw(P, s * (-24 * wind + 30 * hit) * pw)
    c.head_look(P, yaw=s * 10 * hit, pitch=-8 * hit)
    if kind == 'arm':
        n = ch.names
        sg = ch.sign
        P.bend(n[0], FWD, 150 * hit * pw - 100 * wind)
        if v.get('slash'):
            P.bend(n[0], IN(sg), 55 * hit)
        else:
            P.bend(n[0], OUT(sg), 25 * wind)
        if len(n) > 1:
            P.bend(n[1], FWD, 60 * hit + 35 * wind)
        if len(n) > 2:
            P.bend(n[2], FWD, 30 * hit)
        other = [a for a in c.rig.arms if a is not ch]
        for a in other:                       # the other arm counterbalances
            P.bend(a.names[0], FWD, -30 * hit + 20 * wind)
    elif kind == 'wing':
        P.bend(ch.names[0], OUT(ch.sign), 55 * wind)
        P.rotw(ch.names[0], FWD, ch.sign * (70 * hit - 40 * wind))
        for b in ch.names[1:]:
            P.rotw(b, FWD, ch.sign * 30 * hit)
    elif kind == 'leg':
        n = ch.names
        P.bend(n[0], BACK, 40 * wind)
        P.bend(n[0], FWD, 110 * hit)
        if len(n) > 1:
            P.bend(n[1], FWD, 40 * hit)
        c.crouch(P, 0.0)
    elif kind == 'tail':
        for t in c.rig.tails:
            P.chain(t.names, OUT(s), -70 * wind * s + 110 * hit * s)
            P.chain(t.names, UP, 30 * hit)
        c.spine_yaw(P, s * 10 * hit)
    else:
        c.head_look(P, pitch=15 * wind - 30 * hit)
        c.mouth(P, 30 * hit)
    brace(c, P, wind)
    tail_react(c, P, u, hit, 10)


def multi_strike(c, P, u, v):
    kind, ch = striker(c, v)
    reps = int(v.get('reps', 4))
    ph = (u * reps) % 1.0
    k = bump(ph, 0.0, 0.35, 0.8) * bump(u, 0.02, 0.15, 0.98) ** 0.3
    env = hold(u, 0.0, 0.1, 0.85, 1.0)
    k *= env
    s = v.get('side', 1.0)
    lunge(c, P, 0.05 * env)
    c.spine_pitch(P, -8 * env)
    c.spine_yaw(P, s * 14 * math.sin(TAU * reps * u) * env)
    arms = c.rig.arms
    if kind == 'arm':
        for i, a in enumerate(arms):
            alt = (i % 2)
            kk = bump((ph + 0.5 * alt) % 1.0, 0.0, 0.3, 0.7) * env
            P.bend(a.names[0], FWD, 100 * kk + 20 * env)
            if len(a.names) > 1:
                P.bend(a.names[1], FWD, 45 * kk)
    elif kind == 'wing':
        for w in c.rig.wings:
            P.rotw(w.names[0], FWD, w.sign * 60 * k)
    elif kind == 'leg':
        for i, l in enumerate(c.rig.legs):
            if l.fh == 'H':
                continue
            kk = bump((ph + 0.5 * (i % 2)) % 1.0, 0.0, 0.3, 0.7) * env
            P.bend(l.names[0], FWD, 70 * kk)
    else:
        for t in c.rig.tails:
            P.wave(t.names, LEFT, 60 * env, u, reps, 0.4)
        c.head_look(P, pitch=-20 * k)
        c.mouth(P, 25 * k)


def bite(c, P, u, v):
    wind, snap = bump(u, 0.0, 0.3, 0.44), bump(u, 0.4, 0.52, 0.72)
    mouth_open = hold(u, 0.05, 0.3, 0.46, 0.56)
    rear_up(c, P, 0.5 * wind, 24)
    lunge(c, P, 0.16 * snap * v.get('power', 1.0), 0.03 * wind)
    c.spine_pitch(P, -16 * snap)
    c.head_look(P, pitch=16 * wind - 22 * snap)
    c.mouth(P, 52 * mouth_open * (1.0 if v.get('big') else 0.8))
    c.head_look(P, yaw=14 * math.sin(TAU * 3 * u) * bump(u, 0.55, 0.65, 0.95))
    brace(c, P, wind)
    tail_react(c, P, u, snap, 14)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 40 * snap)
    if c.rig.body:
        c.spine_bend(P, LEFT, 30 * snap * v.get('side', 1.0))


def headbutt(c, P, u, v):
    wind, ram, rec = bump(u, 0.0, 0.3, 0.44), bump(u, 0.4, 0.55, 0.78), bump(u, 0.7, 0.85, 1.0)
    brace(c, P, wind)
    c.spine_pitch(P, 14 * wind - 24 * ram)
    c.head_look(P, pitch=18 * wind - 38 * ram + 10 * rec)
    lunge(c, P, 0.32 * ram * v.get('power', 1.0) - 0.04 * wind, 0.02 * ram)
    if v.get('drill'):
        c.head_look(P, yaw=0)
        c.spine_yaw(P, 720 * sm((u - 0.35) / 0.45) * 0.04)
        c.root_move(P, x=0.01 * math.sin(TAU * 12 * u) * ram)
    for a in c.rig.arms:
        P.bend(a.names[0], BACK, 50 * ram)
    for w in c.rig.wings:
        P.bend(w.names[0], BACK, 40 * ram)
    tail_react(c, P, u, ram, 10)
    c.squash(P, 0.05 * bump(u, 0.55, 0.6, 0.7))


def tackle(c, P, u, v):
    wind, run, rec = bump(u, 0.0, 0.25, 0.4), bump(u, 0.32, 0.5, 0.8), bump(u, 0.55, 0.62, 0.95)
    brace(c, P, wind)
    c.spine_pitch(P, 6 * wind - 14 * run)
    c.head_look(P, pitch=-10 * run)
    lunge(c, P, 0.45 * run * v.get('power', 1.0) - 0.05 * wind, 0.01 * run)
    c.squash(P, 0.08 * wind - 0.10 * run + 0.10 * rec)
    P.pitch(c.rig.root, -6 * run)
    c.stride(P, u * 3, 1.0, 34 * run, 25 * run, 10 * run)
    for a in c.rig.arms:
        P.bend(a.names[0], BACK, 55 * run)
    tail_react(c, P, u, run, 12)
    for w in c.rig.wings:
        P.bend(w.names[0], BACK, 30 * run)


def slam(c, P, u, v):
    """rear up / lift, then crash down (body slam, stomp, take down)."""
    rise, fall = bump(u, 0.0, 0.4, 0.5), bump(u, 0.42, 0.55, 0.9)
    rear_up(c, P, 1.0 * rise, 30)
    c.root_move(P, z=0.12 * rise * c.amp - 0.045 * fall * c.amp, f=0.14 * fall)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 155 * rise - 190 * fall * 0.7)
        if len(a.names) > 1:
            P.bend(a.names[1], FWD, 35 * rise)
    for l in c.rig.legs:
        if l.fh == 'F':
            P.bend(l.names[0], FWD, 70 * rise - 20 * fall)
    for w in c.rig.wings:
        P.rotw(w.names[0], FWD, w.sign * 60 * rise)
    c.squash(P, 0.16 * bump(u, 0.55, 0.6, 0.75) - 0.06 * rise)
    tail_react(c, P, u, fall, 22)
    c.spine_pitch(P, -18 * fall)
    tremor = bump(u, 0.55, 0.62, 1.0) * math.sin(TAU * 5 * u)
    c.root_move(P, z=0.008 * tremor)


def beam(c, P, u, v):
    charge, fire = hold(u, 0.0, 0.3, 0.42, 0.5), hold(u, 0.4, 0.5, 0.84, 1.0)
    rear_up(c, P, 0.7 * charge + 0.3 * fire, 28)
    c.head_look(P, pitch=22 * charge - 6 * fire, yaw=v.get('sweep', 0.0) * 22 * math.sin(TAU * u) * fire)
    c.mouth(P, 48 * fire * v.get('open', 1.0) + 10 * charge)
    c.root_move(P, f=-0.05 * fire - 0.02 * charge, x=0.007 * math.sin(TAU * 16 * u) * fire)
    for a in c.rig.arms:
        c.arm_pose(P, 'forward', 0.5 * fire + 0.3 * charge, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 35 * charge)
    for e in c.rig.ears:
        P.bend(e.names[0], BACK, 25 * fire)
    tail_react(c, P, u, fire, 8)
    c.extras_sway(P, u, 10 * fire, 4.0)
    c.squash(P, -0.04 * charge + 0.03 * fire)
    brace(c, P, 0.6 * charge)


def burst(c, P, u, v):
    """three quick exhales (ember, gust, bubble, poison gas, sand attack ...)."""
    reps = int(v.get('reps', 3))
    ph = (u * reps) % 1.0
    k = bump(ph, 0.0, 0.3, 0.75) * hold(u, 0.0, 0.08, 0.9, 1.0)
    rear_up(c, P, 0.4 * hold(u, 0.0, 0.1, 0.9, 1.0), 20)
    c.head_look(P, pitch=-16 * k)
    c.mouth(P, 38 * k)
    lunge(c, P, 0.05 * k)
    c.spine_pitch(P, -8 * k)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 35 * k)
    for w in c.rig.wings:
        P.rotw(w.names[0], FWD, w.sign * 35 * k)
    tail_react(c, P, u, k, 12)
    c.extras_sway(P, u, 12 * k, reps)


def shock(c, P, u, v):
    k = hold(u, 0.0, 0.12, 0.8, 1.0)
    tw = math.sin(TAU * 11 * u) * k
    c.root_move(P, x=0.012 * tw, z=0.02 * k)
    c.squash(P, 0.05 * math.sin(TAU * 7 * u) * k)
    rear_up(c, P, 0.5 * k, 24)
    c.head_look(P, roll=8 * tw, pitch=10 * k)
    for a in c.rig.arms:
        c.arm_pose(P, 'out', 0.8 * k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 60 * k)
        P.rotw(w.names[0], FWD, w.sign * 20 * tw)
    c.tails_pose(P, UP, 40 * k)
    c.tails_sway(P, u, 22 * k, 5.0, 0.3)
    c.ears_move(P, u, 20 * k, 5.0)
    c.extras_sway(P, u, 28 * k, 5.0, 0.3)
    c.mouth(P, 20 * k)
    c.sides_wobble(P, u, 0.12 * k, 5.0)
    brace(c, P, 0.4 * k)


def spin_attack(c, P, u, v):
    g = sm((u - 0.1) / 0.75)
    k = hold(u, 0.0, 0.15, 0.8, 1.0)
    turns = v.get('turns', 2)
    P.yaw(c.rig.root, 360 * turns * g)
    c.root_move(P, z=0.05 * math.sin(math.pi * min(1.0, max(0.0, (u - 0.05) / 0.9))) * c.amp)
    for a in c.rig.arms:
        c.arm_pose(P, 'out', 0.9 * k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 65 * k)
    c.tails_pose(P, LEFT, 40 * k)
    for t in c.rig.tails:
        P.chain(t.names, OUT(t.sign or 1.0), 50 * k)
    for e in c.rig.extras:
        P.chain(e.names, OUT(e.sign), 45 * k)
    c.spine_roll(P, 12 * k)
    if c.rig.serpent:
        c.spine_bend(P, LEFT, 60 * k)
    c.squash(P, -0.05 * k)


def throw(c, P, u, v):
    """wind up an arm (or head/tail) and hurl: rock throw, bonemerang, egg bomb, spike cannon, razor leaf."""
    wind, rel = bump(u, 0.0, 0.32, 0.5), bump(u, 0.42, 0.55, 0.85)
    kind, ch = striker(c, v)
    s = v.get('side', 1.0)
    c.spine_pitch(P, 14 * wind - 14 * rel)
    c.spine_yaw(P, s * (-30 * wind + 36 * rel))
    lunge(c, P, 0.05 * rel)
    if kind == 'arm':
        n = ch.names
        P.bend(n[0], FWD, 160 * wind - 140 * rel * 0.3 - 20 * rel)
        P.bend(n[0], OUT(ch.sign), 30 * wind)
        if len(n) > 1:
            P.bend(n[1], BACK, 55 * wind - 90 * rel)
        for a in c.rig.arms:
            if a is not ch:
                P.bend(a.names[0], FWD, 40 * wind)
    elif kind in ('tail', 'extra'):
        for t in (c.rig.tails if kind == 'tail' else c.rig.extras):
            P.chain(t.names, UP, 70 * wind - 90 * rel)
    else:
        c.head_look(P, pitch=28 * wind - 35 * rel)
        c.mouth(P, 30 * rel)
        for w in c.rig.wings:
            P.rotw(w.names[0], FWD, w.sign * 50 * wind)
    brace(c, P, wind)


def whip(c, P, u, v):
    """tail / vine / tentacle lash (vine whip, tail whip, wrap, lick, string shot ...)."""
    k = hold(u, 0.0, 0.18, 0.75, 1.0)
    reps = v.get('reps', 3)
    sw = math.sin(TAU * reps * u)
    limbs = c.rig.extras + c.rig.tails
    if not limbs and c.rig.arms:
        limbs = c.rig.arms
    for i, t in enumerate(limbs):
        P.chain(t.names, UP, 25 * k)
        P.wave(t.names, LEFT if abs(t.dir[0]) < 0.6 else FWD, 70 * k, u, reps, 0.7, i * 0.8 + (0.0 if t.sign > 0 else math.pi))
    c.spine_yaw(P, 18 * sw * k)
    c.spine_pitch(P, -6 * k)
    lunge(c, P, 0.04 * k)
    c.head_look(P, yaw=-10 * sw * k)
    if v.get('tongue'):
        c.mouth(P, 40 * k)
        c.head_look(P, pitch=-10 * k)
    if c.rig.serpent:
        c.spine_bend(P, LEFT, 26 * sw * k)


def bind(c, P, u, v):
    """coil around the target and squeeze (bind, wrap, constrict, vicegrip, clamp)."""
    k = hold(u, 0.0, 0.3, 0.75, 1.0)
    sq = math.sin(TAU * 3 * u) * k
    if c.rig.serpent:
        n = len(c.rig.body)
        for i, b in enumerate(c.rig.body):
            P.yaw(b, min(34.0 + 8 * sq, 300.0 / n) * k)
            P.pitch(b, -6 * k)
        rear_up(c, P, 0.6 * k, 20)
    else:
        for a in c.rig.arms:
            c.arm_pose(P, 'guard', 1.0 * k, which=[c.rig.arms.index(a)])
            P.bend(a.names[0], IN(a.sign), 40 * k)
        for e in c.rig.extras + c.rig.tails:
            P.chain(e.names, FWD if e in c.rig.extras else LEFT, 80 * k)
        c.spine_pitch(P, -12 * k)
        brace(c, P, 0.5 * k)
    c.squash(P, -0.06 * sq)
    c.mouth(P, 24 * bump(u, 0.35, 0.5, 0.7))
    lunge(c, P, 0.10 * k)


def dive(c, P, u, v):
    """dig / burrow / dive: nose down, sink, shudder, and come back up."""
    sink = hold(u, 0.05, 0.4, 0.58, 0.9)
    c.root_move(P, z=-0.5 * sink, f=0.05 * sink)
    P.pitch(c.rig.root, -30 * sink)
    c.head_look(P, pitch=-20 * sink)
    shake_body(c, P, u, sink, 16, 0.014)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 70 * sink * math.sin(TAU * 4 * u))
    c.tails_pose(P, UP, 35 * sink)
    c.squash(P, -0.05 * sink)


def fly_up(c, P, u, v):
    crouch, rise = bump(u, 0.0, 0.18, 0.3), hold(u, 0.2, 0.42, 0.6, 0.9)
    c.crouch(P, 0.8 * crouch)
    c.root_move(P, z=0.85 * rise * c.amp, f=0.1 * rise)
    P.pitch(c.rig.root, 12 * rise)
    c.wings_flap(P, u, 38 * rise, 5.0, spread=50 * rise)
    c.spine_pitch(P, -10 * rise)
    for l in c.rig.legs:
        P.bend(l.names[0], BACK, 40 * rise)
    for a in c.rig.arms:
        P.bend(a.names[0], BACK, 30 * rise)
    tail_react(c, P, u, rise, 10)
    c.ears_move(P, u, 10 * rise, 3.0)
    c.extras_sway(P, u, 20 * rise, 2.0)


def wing_beat(c, P, u, v):
    k = hold(u, 0.0, 0.18, 0.8, 1.0)
    c.wings_flap(P, u, 42 * k, 4.0, spread=55 * k)
    c.root_move(P, z=0.10 * k * c.amp, f=-0.03 * k)
    rear_up(c, P, 0.5 * k, 22)
    c.ears_move(P, u, 14 * k, 4.0)
    c.extras_sway(P, u, 18 * k, 4.0)
    c.tails_sway(P, u, 20 * k, 4.0)
    for a in c.rig.arms:
        P.bend(a.names[0], OUT(a.sign), 50 * k)
    if not c.rig.wings:
        c.spine_roll(P, 10 * math.sin(TAU * 4 * u) * k)
        for a in c.rig.arms:
            P.bend(a.names[0], UP, 40 * k * math.sin(TAU * 4 * u + a.sign))


def sing(c, P, u, v):
    k = hold(u, 0.0, 0.15, 0.85, 1.0)
    sw = math.sin(TAU * 2 * u)
    c.head_look(P, roll=16 * sw * k, pitch=12 * k)
    c.mouth(P, 26 * (0.5 + 0.5 * math.sin(TAU * 6 * u)) * k)
    rear_up(c, P, 0.3 * k, 18)
    c.spine_roll(P, 6 * sw * k)
    c.ears_move(P, u, 14 * k, 2.0)
    c.extras_sway(P, u, 14 * k, 2.0)
    for a in c.rig.arms:
        c.arm_pose(P, 'out', 0.35 * k, which=[c.rig.arms.index(a)], u=u, cycles=2.0)
    c.tails_sway(P, u, 16 * k, 2.0)
    c.root_move(P, z=0.015 * math.sin(TAU * 4 * u) * k)
    if c.rig.serpent:
        c.spine_bend(P, LEFT, 30 * sw * k)
    c.sides_wobble(P, u, 0.05 * k, 4.0)


def powder(c, P, u, v):
    k = hold(u, 0.0, 0.2, 0.8, 1.0)
    sh = math.sin(TAU * 8 * u) * k
    c.spine_pitch(P, -8 * k)
    c.root_move(P, x=0.01 * sh, z=0.01 * abs(sh))
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 40 * k)
        P.rotw(w.names[0], FWD, w.sign * 25 * sh)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 60 * k + 15 * sh)
    c.extras_sway(P, u, 30 * k, 8.0, 0.3)
    c.tails_sway(P, u, 18 * k, 4.0)
    c.head_look(P, pitch=-10 * k, roll=6 * sh)
    c.mouth(P, 18 * k)
    c.sides_wobble(P, u, 0.08 * k, 8.0)


def harden(c, P, u, v):
    k = hold(u, 0.0, 0.3, 0.7, 0.95)
    pulse = bump(u, 0.35, 0.4, 0.5)
    c.spine_pitch(P, -30 * k)
    c.head_look(P, pitch=-35 * k)
    c.crouch(P, k)
    for a in c.rig.arms:
        c.arm_pose(P, 'tuck', k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], BACK, 45 * k)
    c.tails_pose(P, DOWN, 30 * k)
    c.squash(P, 0.10 * k + 0.06 * pulse)
    if c.rig.serpent:
        c.spine_bend(P, LEFT, 90 * k)
    for e in c.rig.extras:
        P.chain(e.names, IN(e.sign), 40 * k)
    c.mouth(P, 0)


def focus(c, P, u, v):
    k = hold(u, 0.0, 0.25, 0.8, 1.0)
    pulse = math.sin(TAU * 4 * u)
    c.root_move(P, z=0.05 * k)
    c.squash(P, 0.02 * pulse * k)
    c.head_look(P, pitch=-14 * k)
    for a in c.rig.arms:
        c.arm_pose(P, 'guard', 0.7 * k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 30 * k)
    c.tails_pose(P, UP, 25 * k)
    c.extras_sway(P, u, 8 * k, 2.0)
    c.ears_move(P, u, 6 * k, 2.0)
    c.spine_pitch(P, -6 * k)
    if v.get('dance'):
        c.spine_yaw(P, 40 * math.sin(TAU * 2 * u) * k)
        for i, a in enumerate(c.rig.arms):
            P.bend(a.names[0], UP, 0.0)
            P.bend(a.names[0], FWD, 120 * k * (0.5 + 0.5 * math.sin(TAU * 2 * u + i * 2.1)))


def menace(c, P, u, v):
    """growl / leer / glare / roar-lite: lean in, lower the head, shudder."""
    k = hold(u, 0.0, 0.22, 0.8, 1.0)
    sh = math.sin(TAU * 10 * u) * k
    lunge(c, P, 0.08 * k)
    c.spine_pitch(P, -14 * k)
    c.head_look(P, pitch=-18 * k, yaw=6 * sh)
    c.mouth(P, 22 * k + 8 * sh)
    c.root_move(P, x=0.006 * sh)
    for a in c.rig.arms:
        P.bend(a.names[0], BACK, 30 * k)
    for e in c.rig.ears:
        P.bend(e.names[0], BACK, 40 * k)
    c.tails_pose(P, UP, 35 * k)
    c.tails_sway(P, u, 10 * k, 3.0)
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 35 * k)
    c.crouch(P, 0.35 * k)
    c.extras_sway(P, u, 10 * k, 5.0)


def rest_heal(c, P, u, v):
    k = hold(u, 0.0, 0.25, 0.75, 1.0)
    sn = math.sin(TAU * 2 * u)
    c.crouch(P, 0.9 * k)
    c.spine_pitch(P, -16 * k)
    c.head_look(P, pitch=-30 * k, roll=6 * k)
    c.squash(P, 0.02 * sn * k + 0.04 * k)
    for a in c.rig.arms:
        c.arm_pose(P, 'tuck', 0.6 * k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], BACK, 40 * k)
    c.tails_pose(P, LEFT, 30 * k)
    c.extras_sway(P, u, 6 * k, 2.0)
    if c.rig.serpent:
        c.spine_bend(P, LEFT, 70 * k)
    c.root_move(P, z=-0.02 * k)


def explode(c, P, u, v):
    infl = bump(u, 0.0, 0.55, 0.7)
    boom = bump(u, 0.6, 0.66, 1.0)
    wob = math.sin(TAU * 9 * u) * infl
    c.squash(P, -0.30 * infl * (1 - boom) + 0.22 * boom * (1 - sm((u - 0.7) / 0.3)))
    P.scale(c.rig.root, 1 + 0.15 * infl, 1 + 0.15 * infl, 1 + 0.15 * infl)
    c.root_move(P, x=0.012 * wob, z=0.03 * infl)
    for a in c.rig.arms:
        c.arm_pose(P, 'out', 0.6 * boom, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 70 * boom)
    c.extras_sway(P, u, 40 * boom, 3.0)
    c.mouth(P, 30 * infl)
    c.head_look(P, pitch=15 * boom)


def morph(c, P, u, v):
    k = hold(u, 0.0, 0.2, 0.7, 1.0)
    w1 = math.sin(TAU * 3 * u) * k
    w2 = math.sin(TAU * 3 * u + 2.1) * k
    P.scale(c.rig.root, 1 + 0.22 * w1, 1 + 0.22 * w2, 1 - 0.22 * (w1 + w2) * 0.5)
    P.yaw(c.rig.root, 180 * sm(u) * (1 - sm((u - 0.5) / 0.5)) * 2 * 0.5 + 360 * sm((u - 0.15) / 0.6))
    c.head_look(P, roll=12 * w1)
    c.tails_sway(P, u, 20 * k, 3.0)
    c.extras_sway(P, u, 20 * k, 3.0)
    c.sides_wobble(P, u, 0.15 * k, 3.0)


def psychic(c, P, u, v):
    k = hold(u, 0.0, 0.25, 0.8, 1.0)
    c.root_move(P, z=0.10 * k * c.amp + 0.012 * math.sin(TAU * 3 * u) * k)
    c.head_look(P, pitch=16 * k, roll=6 * math.sin(TAU * 2 * u) * k)
    for a in c.rig.arms:
        c.arm_pose(P, 'out', 0.55 * k, which=[c.rig.arms.index(a)], u=u, cycles=2.0)
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 40 * k)
    for l in c.rig.legs:
        P.bend(l.names[0], BACK, 18 * k)
    c.extras_sway(P, u, 26 * k, 2.0, 0.9, toward=UP)
    for t in c.rig.tails:
        P.wave(t.names, UP, 25 * k, u, 2.0, 0.7)
    c.ears_move(P, u, 10 * k, 2.0)
    c.spine_pitch(P, 8 * k)
    c.mouth(P, 8 * k)
    c.squash(P, -0.03 * k)


def flop(c, P, u, v):
    """splash / struggle / bide / counter: flailing hops."""
    reps = int(v.get('reps', 3))
    ph = (u * reps) % 1.0
    k = hold(u, 0.0, 0.08, 0.88, 1.0)
    hopv = math.sin(math.pi * ph) * k
    c.root_move(P, z=0.10 * hopv * c.amp, x=0.03 * math.sin(TAU * reps * u * 0.5) * k)
    P.roll(c.rig.root, 34 * math.sin(TAU * reps * u * 0.5) * k)
    c.spine_bend(P, LEFT, 30 * math.sin(TAU * reps * u) * k)
    c.head_look(P, roll=14 * math.sin(TAU * reps * u + 1) * k)
    for a in c.rig.arms + c.rig.legs:
        P.bend(a.names[0], FWD, 45 * math.sin(TAU * reps * u * 2 + a.sign) * k)
    for f in c.rig.fins:
        P.wave(f.names, LEFT, 40 * k, u, reps * 2, 0.4)
    c.tails_sway(P, u, 40 * k, reps, 0.5)
    c.squash(P, 0.10 * (1 - hopv) * k)
    c.mouth(P, 20 * hopv)


def flash(c, P, u, v):
    k = bump(u, 0.05, 0.4, 0.9)
    pulse = bump(u, 0.35, 0.45, 0.6)
    rear_up(c, P, k, 22)
    for a in c.rig.arms:
        c.arm_pose(P, 'up', 0.8 * k, which=[c.rig.arms.index(a)])
    for w in c.rig.wings:
        P.bend(w.names[0], OUT(w.sign), 70 * k)
    c.tails_pose(P, UP, 30 * k)
    c.extras_sway(P, u, 20 * k, 2.0)
    P.scale(c.rig.root, 1 + 0.12 * pulse, 1 + 0.12 * pulse, 1 + 0.12 * pulse)
    c.root_move(P, z=0.04 * k)
    c.mouth(P, 25 * pulse)
    c.ears_move(P, u, 10 * k, 2.0)


def dash(c, P, u, v):
    """quick attack / agility / swift: shoot forward, return."""
    out = hold(u, 0.08, 0.28, 0.42, 0.62)
    back = bump(u, 0.55, 0.75, 1.0)
    lunge(c, P, 0.7 * out * v.get('power', 1.0))
    c.spine_pitch(P, -18 * out)
    c.head_look(P, pitch=-10 * out)
    c.root_move(P, x=0.05 * v.get('side', 1.0) * (out - back * 0.0))
    c.stride(P, u * 4, 1.0, 40 * (out + back), 30 * (out + back), 12 * out)
    for a in c.rig.arms:
        P.bend(a.names[0], BACK, 70 * out)
    for w in c.rig.wings:
        P.bend(w.names[0], BACK, 40 * out)
    c.tails_pose(P, BACK if not c.rig.horizontal else UP, 25 * out)
    c.ears_move(P, u, 6, 0.0, flick=30 * out)
    if c.rig.serpent:
        c.spine_bend(P, LEFT, 40 * math.sin(TAU * 3 * u) * (out + back))
    c.root_move(P, f=-0.7 * back * 0.0)


def kick(c, P, u, v):
    wind, hit = bump(u, 0.0, 0.28, 0.44), bump(u, 0.38, 0.5, 0.78)
    legs = [l for l in c.rig.legs] or []
    c.spine_pitch(P, 10 * wind - 6 * hit)
    c.spine_yaw(P, v.get('side', 1.0) * (16 * wind - 12 * hit))
    c.root_move(P, z=0.06 * hit * c.amp, f=0.05 * hit)
    if legs:
        pick = sorted(legs, key=lambda l: (l.fh != 'H' and len(legs) > 2, l.sign != v.get('side', 1.0)))[0]
        n = pick.names
        P.bend(n[0], BACK, 45 * wind)
        P.bend(n[0], FWD, 140 * hit)
        if len(n) > 1:
            P.bend(n[1], BACK, 60 * wind)
            P.bend(n[1], FWD, 75 * hit)
        for l in legs:
            if l is not pick and l.fh != 'F':
                P.bend(l.names[0], BACK, 10 * hit)
    else:
        for t in c.rig.tails:
            P.chain(t.names, UP, 60 * wind - 90 * hit)
        lunge(c, P, 0.1 * hit)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 40 * wind - 55 * hit * a.sign * v.get('side', 1.0))
    tail_react(c, P, u, hit, 10)


def leech(c, P, u, v):
    """absorb / mega drain / leech life / dream eater: lunge, latch, pulse, sit back."""
    lat = hold(u, 0.1, 0.3, 0.7, 0.9)
    pulse = math.sin(TAU * 5 * u) * lat
    lunge(c, P, 0.12 * lat)
    c.spine_pitch(P, -14 * lat)
    c.head_look(P, pitch=-18 * lat)
    c.mouth(P, 30 * lat * (0.5 + 0.5 * math.sin(TAU * 5 * u)))
    c.squash(P, -0.05 * pulse)
    c.extras_sway(P, u, 26 * lat, 3.0)
    for a in c.rig.arms:
        c.arm_pose(P, 'forward', 0.6 * lat, which=[c.rig.arms.index(a)])
    tail_react(c, P, u, lat, 8)


def leap_strike(c, P, u, v):
    """pounce from a crouch (hi jump kick, fury swipes, sky attack ...)."""
    crouch, jump = bump(u, 0.0, 0.2, 0.34), hold(u, 0.28, 0.5, 0.62, 0.86)
    c.crouch(P, 0.8 * crouch)
    c.root_move(P, z=0.55 * jump * c.amp, f=0.35 * jump)
    c.spine_pitch(P, -20 * jump)
    P.pitch(c.rig.root, -10 * jump)
    for a in c.rig.arms:
        P.bend(a.names[0], FWD, 120 * jump)
    for l in c.rig.legs:
        P.bend(l.names[0], FWD if l.fh != 'H' else BACK, 40 * jump)
    c.wings_flap(P, u, 30 * jump, 4.0, spread=40 * jump)
    tail_react(c, P, u, jump, 12)
    c.mouth(P, 30 * jump)


ARCH = {
    'strike': strike, 'multi_strike': multi_strike, 'bite': bite, 'headbutt': headbutt, 'tackle': tackle, 'slam': slam,
    'beam': beam, 'burst': burst, 'shock': shock, 'spin_attack': spin_attack, 'throw': throw, 'whip': whip, 'bind': bind,
    'dive': dive, 'fly_up': fly_up, 'wing_beat': wing_beat, 'sing': sing, 'powder': powder, 'harden': harden,
    'focus': focus, 'menace': menace, 'rest_heal': rest_heal, 'explode': explode, 'morph': morph, 'psychic': psychic,
    'flop': flop, 'flash': flash, 'dash': dash, 'kick': kick, 'leech': leech, 'leap_strike': leap_strike,
}

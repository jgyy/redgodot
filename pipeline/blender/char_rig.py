"""Proportions + skeleton for the realistic characters (pure data; bpy only in build_armature).

Units are "sprite rows": a standard adult stands ~23.4 rows to the top of the skull (7.1 heads) and the
exporter scales rows to metres (1.5 m nominal).  The bone names and the hierarchy are the game contract
(OwActor / PlayerModel / CharacterSkin and char_anim.py address bones by name) and did not change when the
chibi bodies were replaced with realistic ones.
"""
import math

import numpy as np

FOOT_LEN_BACK = 1.1       # heel behind the ankle (+Y)
FOOT_LEN_FRONT = 2.75     # toe in front of the ankle (-Y)

AGE_HEAD = {'child': 0.55, 'teen': 0.25, 'adult': 0.0, 'old': 0.0}


class Prop:
    """Body proportions.  Knobs (all come from `build` in character_looks.json):
      sh     overall height of trunk + legs (1.0 = 1.5 m adult; children 0.75-0.9)
      sw     width of shoulders / hips
      hs     head scale (on top of the automatic bigger-head-for-smaller-body rule)
      bulk   limb thickness (muscle / fat)
      belly  torso depth bulge at the waist
      neck   neck length
      stoop  forward hunch of the old (animation only)
      sex    'm' | 'f' (shoulder / hip / bust / jaw / hand size)
      lift   shoe sole height (the foot volume sits on top of it)
    """

    def __init__(self, sh=1.0, sw=1.0, hs=1.0, bulk=1.0, belly=0.0, neck=1.0, stoop=0.0, sex='m', lift=0.3, muscle=0.0,
                 bust=None, jaw=1.0, age='adult'):
        self.sh, self.sw, self.hs, self.bulk, self.belly, self.stoop = sh, sw, hs, bulk, belly, stoop
        self.sex, self.age = sex, age
        s = sh
        self.s = s
        self.ls = s ** 0.8                       # lateral scale (kids are narrower but not as much as they are short)
        self.lift = lift
        f = sex == 'f'
        self.f = f
        self.muscle = muscle
        self.bust = (0.75 if f else 0.0) if bust is None else bust
        self.jaw = jaw
        L = lift
        self.ankle = L + 0.95 * (0.5 + 0.5 * s)
        self.knee = L + 6.4 * s
        self.hip = L + 12.0 * s
        self.crotch = self.hip - 1.15 * s
        self.waist = L + 14.6 * s
        self.chest = L + 16.8 * s
        self.shoulder = L + 18.6 * s                 # glenohumeral joint height
        self.shoulder_top = L + 19.25 * s
        self.neck_base = L + 19.0 * s
        head_k = hs * 1.05 * (1.0 + (1.0 - s) * 0.85)   # small bodies keep proportionally big heads (adults ~6.8 heads tall)
        self.head_h = 3.3 * head_k * (0.97 if f else 1.0)
        self.head_k = head_k
        self.neck_len = 1.0 * neck
        self.chin = L + 19.9 * s + (neck - 1.0) * 0.7 + (0.0 if s > 0.95 else (1 - s) * 1.1)
        self.head_top = self.chin + self.head_h
        self.neck_top = self.chin + self.head_h * 0.36
        self.head_c = np.array([0.0, 0.2 * head_k, self.chin + self.head_h * 0.55])
        # lateral positions
        ls = self.ls
        self.hip_x = 1.42 * ls * (sw ** 0.6) * (1.06 if f else 1.0)
        self.shoulder_x = (2.5 if not f else 2.25) * ls * sw
        self.arm_lean = 0.26                          # A-pose: tan of the outward tilt of the upper arm
        self.forearm_lean = 0.17
        self.upper_arm = 4.35 * s
        self.forearm = 3.35 * s
        self.hand_len = 2.35 * (0.5 + 0.5 * s) * (0.94 if f else 1.0)
        self.elbow_flex = 0.10                        # relaxed elbow, forearm swings forward
        # sprite-row -> named heights the animation module uses
        self.elbow_z = self.shoulder - self.upper_arm / math.sqrt(1 + self.arm_lean ** 2)
        self.wrist_z = self.elbow_z - self.forearm / math.sqrt(1 + self.forearm_lean ** 2)

    def joints(self, side):
        """Named joint positions for a side (+1 = character's left = +X)."""
        s = side
        sx = self.shoulder_x
        sh = np.array([s * sx, 0.0, self.shoulder])
        ua = self.upper_arm
        d1 = np.array([s * self.arm_lean, 0.0, -1.0])
        d1 /= np.linalg.norm(d1)
        el = sh + d1 * ua
        d2 = np.array([s * self.forearm_lean, -self.elbow_flex, -1.0])
        d2 /= np.linalg.norm(d2)
        wr = el + d2 * self.forearm
        d3 = np.array([s * 0.06, -0.20, -1.0])
        d3 /= np.linalg.norm(d3)
        tip = wr + d3 * self.hand_len
        hx = s * self.hip_x
        return {
            'shoulder': sh, 'elbow': el, 'wrist': wr, 'hand_tip': tip,
            'hip': np.array([hx, 0.0, self.hip]),
            'knee': np.array([hx * 1.02, -0.05, self.knee]),
            'ankle': np.array([hx * 1.04, 0.0, self.ankle]),
            'toe': np.array([hx * 1.06, -FOOT_LEN_FRONT, self.lift + 0.35]),
            'arm_dirs': (d1, d2, d3),
        }


# ----------------------------------------------------------------------------- skeleton
def skeleton(P, extra=()):
    """List of (name, parent, head, tail).  `extra` = additional secondary bones."""
    hs = P.head_k
    bones = [
        ('root', None, (0, 0, 0), (0, 0, 0.6)),
        ('hips', 'root', (0, 0, P.hip + 0.3), (0, 0, P.waist)),
        ('spine', 'hips', (0, 0, P.waist), (0, 0, P.chest)),
        ('chest', 'spine', (0, 0, P.chest), (0, 0, P.neck_base)),
        ('neck', 'chest', (0, 0, P.neck_base), (0, 0, P.neck_top)),
        ('head', 'neck', (0, 0, P.neck_top), (0, 0, P.head_top)),
    ]
    for side, sfx in ((1, '_L'), (-1, '_R')):
        j = P.joints(side)
        bones += [
            ('clavicle' + sfx, 'chest', (side * 0.55, 0.0, P.shoulder_top - 0.25 * P.s), tuple(j['shoulder'])),
            ('upper_arm' + sfx, 'clavicle' + sfx, tuple(j['shoulder']), tuple(j['elbow'])),
            ('forearm' + sfx, 'upper_arm' + sfx, tuple(j['elbow']), tuple(j['wrist'])),
            ('hand' + sfx, 'forearm' + sfx, tuple(j['wrist']), tuple(j['hand_tip'])),
            ('thigh' + sfx, 'hips', tuple(j['hip']), tuple(j['knee'])),
            ('shin' + sfx, 'thigh' + sfx, tuple(j['knee']), tuple(j['ankle'])),
            ('foot' + sfx, 'shin' + sfx, tuple(j['ankle']), (j['ankle'][0], -FOOT_LEN_FRONT, P.lift + 0.4)),
        ]
    # facial bones: the eyelids rotate about the eyeball centres (blink), the mouth pulses when talking
    ec = getattr(P, 'eye_c', None)
    if ec is None:
        ez = P.chin + P.head_h * 0.62
        ec = {1: np.array([0.5 * hs, -0.8 * hs, ez]), -1: np.array([-0.5 * hs, -0.8 * hs, ez])}
    mc = getattr(P, 'mouth_c', None)
    if mc is None:
        mc = np.array([0.0, -1.1 * hs, P.chin + P.head_h * 0.24])
    bones += [
        ('eye_L', 'head', tuple(ec[1]), tuple(ec[1] + np.array([0, -0.3, 0]))),
        ('eye_R', 'head', tuple(ec[-1]), tuple(ec[-1] + np.array([0, -0.3, 0]))),
        ('mouth', 'head', tuple(mc), tuple(mc + np.array([0, -0.3, 0]))),
    ]
    bones += list(extra)
    return bones


def build_armature(name, bones):
    """Create the bpy armature.  Bones get real head/tail positions; roll 0."""
    import bpy
    from mathutils import Vector
    arm_data = bpy.data.armatures.new(name + '_armature')
    arm = bpy.data.objects.new(name + '_rig', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    made = {}
    for nm, par, head, tail in bones:
        e = eb.new(nm)
        h, t = Vector(head), Vector(tail)
        if (t - h).length < 1e-3:
            t = h + Vector((0, 0, 0.1))
        e.head, e.tail = h, t
        e.roll = 0.0
        made[nm] = e
    for nm, par, head, tail in bones:
        if par:
            made[nm].parent = made[par]
            made[nm].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm

"""Proportions + skeleton for the chibi characters (pure data; bpy only in build_armature)."""
import math

import numpy as np

# ----------------------------------------------------------------------------- proportions
FOOT_LEN_BACK = 1.3       # heel behind the ankle (+Y)
FOOT_LEN_FRONT = 3.3      # toe in front of the ankle (-Y)


class Prop:
    """Body proportions in "sprite rows" (a full figure is ~24 tall).  Everything the body /
    clothing builders need (joint heights, limb radii) derives from a few knobs:
      sh    height of legs+torso (1.0 = standard adult chibi; kids ~0.86)
      sw    width of shoulders / hips
      hs    head scale
      bulk  limb thickness
      belly torso depth bulge
    """

    def __init__(self, sh=1.0, sw=1.0, hs=1.0, bulk=1.0, belly=0.0, neck=1.0, stoop=0.0):
        self.sh, self.sw, self.hs, self.bulk, self.belly, self.stoop = sh, sw, hs, bulk, belly, stoop
        self.ankle = 1.4
        self.hip = 6.7 * sh
        self.knee = self.ankle + (self.hip - self.ankle) * 0.5
        self.waist = 8.2 * sh
        self.chest = 9.7 * sh
        self.shoulder = 11.0 * sh
        self.neck_base = 11.55 * sh
        self.neck_top = 12.45 * sh + (neck - 1.0) * 0.6
        self.head_rx, self.head_ry, self.head_rz = 5.9 * hs, 5.55 * hs, 5.6 * hs
        self.chin = self.neck_top - 0.7
        self.head_c = np.array([0.0, 0.0, self.chin + self.head_rz * 0.97])
        self.head_top = self.head_c[2] + self.head_rz
        self.leg_x = 1.85 * sw
        self.shoulder_x = 3.75 * sw
        self.elbow_z = self.shoulder - 2.65 * sh
        self.wrist_z = self.shoulder - 5.05 * sh
        self.arm_lean = 0.55 * sw     # outward drift of the hanging arm per bone (A-pose)
        self.hand_len = 1.85

    # -- radii
    def torso_rx(self, z):
        """Half width of the torso at height z."""
        sw = self.sw
        pts = [(self.hip - 0.6, 3.05 * sw), (self.waist, 2.95 * sw), (self.chest, 3.35 * sw),
               (self.shoulder - 0.35, 3.55 * sw), (self.neck_base, 1.9 * sw)]
        zs = [p[0] for p in pts]
        return float(np.interp(z, zs, [p[1] for p in pts]))

    def torso_ry(self, z):
        pts = [(self.hip - 0.6, 2.45), (self.waist, 2.3 + self.belly), (self.chest, 2.5 + self.belly * 0.5),
               (self.shoulder - 0.35, 2.35), (self.neck_base, 1.6)]
        return float(np.interp(z, [p[0] for p in pts], [p[1] for p in pts]))

    def joints(self, side):
        """Named joint positions for a side (+1 = character's left = +X)."""
        s = side
        sx, sh = self.shoulder_x, self.sh
        elbow_x = s * (sx + self.arm_lean * (self.shoulder - self.elbow_z) / 2.65)
        wrist_x = s * (sx + self.arm_lean * (self.shoulder - self.wrist_z) / 2.65)
        return {
            'shoulder': np.array([s * sx, 0.0, self.shoulder]),
            'elbow': np.array([elbow_x, 0.0, self.elbow_z]),
            'wrist': np.array([wrist_x, 0.0, self.wrist_z]),
            'hand_tip': np.array([wrist_x + s * self.arm_lean * 0.3, 0.0, self.wrist_z - self.hand_len]),
            'hip': np.array([s * self.leg_x, 0.0, self.hip]),
            'knee': np.array([s * self.leg_x, 0.0, self.knee]),
            'ankle': np.array([s * self.leg_x, 0.0, self.ankle]),
            'toe': np.array([s * self.leg_x, -FOOT_LEN_FRONT, 0.55]),
        }


# ----------------------------------------------------------------------------- skeleton
def skeleton(P, extra=()):
    """List of (name, parent, head, tail).  `extra` = additional secondary bones."""
    hs = P.hs
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
            ('clavicle' + sfx, 'chest', (side * 0.9, 0, P.shoulder - 0.15), tuple(j['shoulder'])),
            ('upper_arm' + sfx, 'clavicle' + sfx, tuple(j['shoulder']), tuple(j['elbow'])),
            ('forearm' + sfx, 'upper_arm' + sfx, tuple(j['elbow']), tuple(j['wrist'])),
            ('hand' + sfx, 'forearm' + sfx, tuple(j['wrist']), tuple(j['hand_tip'])),
            ('thigh' + sfx, 'hips', tuple(j['hip']), tuple(j['knee'])),
            ('shin' + sfx, 'thigh' + sfx, tuple(j['knee']), tuple(j['ankle'])),
            ('foot' + sfx, 'shin' + sfx, tuple(j['ankle']), (j['ankle'][0], -FOOT_LEN_FRONT, 0.6)),
        ]
    # facial bones: eyes blink by squashing, mouth pulses when talking
    ey = P.head_c[2] - 0.9 * hs
    bones += [
        ('eye_L', 'head', (2.35 * hs, -5.0 * hs, P.head_c[2] - 0.7 * hs), (2.35 * hs, -5.2 * hs, P.head_c[2] - 0.7 * hs)),
        ('eye_R', 'head', (-2.35 * hs, -5.0 * hs, P.head_c[2] - 0.7 * hs), (-2.35 * hs, -5.2 * hs, P.head_c[2] - 0.7 * hs)),
        ('mouth', 'head', (0, -5.0 * hs, P.head_c[2] - 3.4 * hs), (0, -5.3 * hs, P.head_c[2] - 3.4 * hs)),
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

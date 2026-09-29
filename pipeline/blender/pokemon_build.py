"""Glue: mesh -> Rigged (skeleton, weights, natural rest pose, clip catalog) in numpy, and the Blender bake of it.

`prepare()` is pure numpy so the unit tests and the report tools run it without bpy; `bake()` needs bpy.
"""
import json
import os

import numpy as np

import pokemon_rig as R
import pokemon_skin as K
import pokemon_clips as CL
from pokemon_pose import Deformer, qmat

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SPEC_PATH = os.path.join(ROOT, 'pipeline', 'data', 'pokemon_species_rig.json')
FPS = 30


def load_specs():
    with open(SPEC_PATH) as fh:
        return json.load(fh)['species']


def load_species():
    with open(os.path.join(ROOT, 'godot', 'data', 'pokedata.json')) as fh:
        return json.load(fh)['species']


class Rigged:
    pass


def prepare(sid, V, T, spec=None, all_species=None):
    spec = spec or load_specs()[sid]
    all_species = all_species if all_species is not None else load_species()
    rg = Rigged()
    rg.sid, rg.spec = sid, spec
    rg.V0 = np.asarray(V, dtype=float)
    rg.T = T
    sk = R.fit(rg.V0, T, spec)
    rg.report_before = K.limb_report(sk)
    names, W = K.skin(rg.V0, T, sk)
    Vn, log = K.natural_pose(rg.V0, W, names, sk, spec)
    rg.report_after = K.limb_report(sk)
    rg.fixed = log
    rg.sk, rg.names, rg.W, rg.V = sk, names, W, Vn
    rg.catalog = CL.build_catalog(sid, spec, sk, all_species)
    rg.ctx = rg.catalog.ctx
    rg.deformer = Deformer(sk, Vn, names, W)
    return rg


def bone_order(sk):
    return list(sk.bones)


# ------------------------------------------------------------------------------------------------ blender
def bake(rg, obj, C, out_path, export_kw=None):
    """put the fitted rig on `obj` (a mesh object already in Blender): armature, weights, corrected rest pose, actions."""
    import bpy
    from mathutils import Vector
    sk = rg.sk
    me = obj.data
    me.vertices.foreach_set('co', rg.V.reshape(-1).astype(np.float64))
    me.update()
    data = bpy.data.armatures.new('Rig')
    arm = bpy.data.objects.new('Armature', data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    made = {}
    for nm, b in sk.bones.items():
        e = data.edit_bones.new(nm)
        head, tail = Vector(b.head), Vector(b.tail)
        if (tail - head).length < 0.004 * sk.H:
            tail = head + Vector((0, 0, 0.004 * sk.H))
        e.head, e.tail, e.roll = head, tail, 0.0
        made[nm] = e
    for nm, b in sk.bones.items():
        if b.parent:
            made[nm].parent = made[b.parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.select_set(False)
    # weights
    for nm in rg.names:
        obj.vertex_groups.new(name=nm)
    W = rg.W
    for bi, nm in enumerate(rg.names):
        vg = obj.vertex_groups[nm]
        col = W[:, bi]
        idx = np.nonzero(col > 0.0)[0]
        # add in weight buckets: VertexGroup.add takes one weight per call
        for vi in idx:
            vg.add([int(vi)], float(col[vi]), 'REPLACE')
    obj.parent = arm
    md = obj.modifiers.new('Armature', 'ARMATURE')
    md.object = arm
    acts = []
    for name, clip in rg.catalog.items():
        acts.append(write_clip(arm, rg, clip, C))
    C.stash_actions(arm, acts)
    return arm


def write_clip(arm, rg, clip, C):
    import math
    n = clip.frames
    w = pruned_writer(C)(arm, clip.name, n)
    order = bone_order(rg.sk)
    poses = [CL.sample(rg.ctx, clip, f) for f in range(n + 1)]
    # a bone that moves at all is keyed on every frame (the writer interpolates linearly between keys)
    moving = [b for b in order if any((b in P.q or b in P.loc or b in P.scl) for P in poses)]
    for f, P in enumerate(poses):
        for b in moving:
            q = P.q.get(b)
            rot = None
            if q is not None:
                s = math.sqrt(max(0.0, 1 - q[0] * q[0]))
                if s > 1e-9:
                    ang = 2 * math.acos(max(-1.0, min(1.0, q[0])))
                    if ang > math.pi:
                        ang -= math.tau
                    rot = ((q[1] / s, q[2] / s, q[3] / s), ang)
            w.key(b, f, loc=P.loc.get(b), rot=rot, scl=P.scl.get(b))
    return w.write(order)


def pruned_writer(C):
    """common.ActionWriter that only creates F-curves for properties that actually move.

    27+ clips x 30+ bones x 10 channels would put ~9000 channels (and ~1MB of JSON) in every glb; a bone that only
    rotates needs its 4 quaternion curves, not location and scale as well."""
    import bpy
    from mathutils import Vector, Quaternion

    class PrunedWriter(C.ActionWriter):
        def write(self, all_bones):
            act = bpy.data.actions.new(self.name)
            act.use_fake_user = True
            ad = self.arm.animation_data or self.arm.animation_data_create()
            prev = ad.action
            ad.action = act
            ident = {0: (0.0, 0.0, 0.0), 1: (1.0, 0.0, 0.0, 0.0), 2: (1.0, 1.0, 1.0)}
            for bone in all_bones:
                fr = self.keys.get(bone)
                if not fr:
                    continue
                frames = sorted(fr)
                base = 'pose.bones["%s"].' % bone
                for pi, (prop, idx_n) in enumerate((('location', 3), ('rotation_quaternion', 4), ('scale', 3))):
                    vals = [[fr[f][pi][i] for f in frames] for i in range(idx_n)]
                    if all(abs(v - ident[pi][i]) < 1e-6 for i in range(idx_n) for v in vals[i]):
                        continue
                    for i in range(idx_n):
                        fc = act.fcurve_ensure_for_datablock(self.arm, base + prop, index=i, group_name=bone)
                        fc.keyframe_points.add(len(frames))
                        co = []
                        for f, v in zip(frames, vals[i]):
                            co += [float(f), float(v)]
                        fc.keyframe_points.foreach_set('co', co)
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'LINEAR'
                        fc.update()
            ad.action = prev
            return act
    return PrunedWriter

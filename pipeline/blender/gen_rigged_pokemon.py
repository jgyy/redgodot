"""Pokémon models: public glTF -> rigged, animated, Godot-ready glb (headless Blender).

The meshes come from the openly published `Pokemon-3D-api/assets` repository
(https://github.com/Pokemon-3D-api/assets, MIT; models/opt/regular/<dex>.glb, Draco + WebP).
Those files are a mixed bag - some carry a Sketchfab skeleton with one clip, most are
static - and Godot cannot read Draco, so this script takes only the *mesh + textures*
and does the rest itself:

  1. import (Blender decodes Draco), bake the rest pose, drop helper meshes, join
  2. normalise: feet on the ground, centred, facing +Z (glTF), sized to the Pokédex height,
     decimated to a triangle budget, textures capped at 512 px
  3. rig: a 17-bone creature skeleton (root, hips/spine/chest/neck/head, 3-bone tail, four
     2-bone limbs) fitted to each mesh's own proportions, with smooth 4-influence weights
  4. animate: 17 clips baked per Pokémon (Idle Walk Run Attack Special Hurt Faint Victory
     Sleep Roar Dodge Spin Hop Charge Taunt Spawn Hover Talk), Idle/Walk/Run/Sleep/Charge/
     Taunt/Hover/Talk loop seamlessly
  5. export glb + refresh godot/assets/models/pokemon/manifest.json

    python3 pipeline/blender/gen_rigged_pokemon.py -- --all --jobs 4
    python3 pipeline/blender/gen_rigged_pokemon.py -- --only PIKACHU,CHARIZARD
    SRC_ASSETS=/path/to/assets-clone python3 ...   # default: ./pipeline/_assets (git clone of the repo above)
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon')
SRC = os.environ.get('SRC_ASSETS', os.path.join(ROOT, 'pipeline', '_assets'))
MISSINGNO_SRC = os.path.join(ROOT, 'pipeline', 'data', 'MISSINGNO_source.glb')
sys.path.insert(0, HERE)

TRI_BUDGET = 14000
TEX_MAX = 512
FPS = 30

CLIPS = ['Idle', 'Walk', 'Run', 'Attack', 'Special', 'Hurt', 'Faint', 'Victory', 'Sleep', 'Roar',
         'Dodge', 'Spin', 'Hop', 'Charge', 'Taunt', 'Spawn', 'Hover', 'Talk']
LOOPING = ['Idle', 'Walk', 'Run', 'Sleep', 'Charge', 'Taunt', 'Hover', 'Talk']
LENGTHS = {'Idle': 60, 'Walk': 30, 'Run': 20, 'Attack': 24, 'Special': 42, 'Hurt': 18, 'Faint': 36, 'Victory': 36,
           'Sleep': 72, 'Roar': 36, 'Dodge': 20, 'Spin': 24, 'Hop': 24, 'Charge': 30, 'Taunt': 36, 'Spawn': 24,
           'Hover': 48, 'Talk': 24}
BONES = ['Root', 'Hips', 'Spine', 'Chest', 'Neck', 'Head', 'Tail1', 'Tail2', 'Tail3',
         'FL_Upper', 'FL_Lower', 'FR_Upper', 'FR_Lower', 'HL_Upper', 'HL_Lower', 'HR_Upper', 'HR_Lower']


# ---------------------------------------------------------------------------------------------- data
def species_table():
    """[(SPECIES_ID, dex, height_m)] from the extracted upstream data."""
    with open(os.path.join(ROOT, 'godot', 'data', 'pokedata.json')) as fh:
        sp = json.load(fh)['species']
    out = []
    for sid, d in sp.items():
        ft, inch = d.get('ht', [3, 0])
        out.append((sid, int(d['dex']), (ft * 12 + inch) * 0.0254))
    out.append(('MISSINGNO', 0, 1.6))   # glitch: no public model, rigged from pipeline/data/MISSINGNO_source.glb
    return sorted(out, key=lambda r: r[1])


def load_overrides():
    p = os.path.join(ROOT, 'pipeline', 'data', 'pokemon_model_overrides.json')
    return json.load(open(p)) if os.path.exists(p) else {}


# ---------------------------------------------------------------------------------------------- blender part
def build_one(sid, src_path, height_m, ov, out_path):
    import bpy
    import bmesh  # noqa: F401
    import numpy as np
    from mathutils import Matrix, Vector, Euler, Quaternion  # noqa: F401
    import common as C

    C.reset_scene()
    bpy.context.scene.render.fps = FPS
    bpy.ops.import_scene.gltf(filepath=src_path, guess_original_bind_pose=False)

    # -- 1. bake the rest pose into fresh mesh objects, drop everything else --------------------------------
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            o.data.pose_position = 'REST'
            o.animation_data_clear()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    shapes = {pb.custom_shape for o in bpy.data.objects if o.type == 'ARMATURE' for pb in o.pose.bones if pb.custom_shape}
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o not in shapes and not o.name.startswith('Icosphere')]
    solid = [o for o in meshes if not (o.data.materials and all(_is_outline(m) for m in o.data.materials))]
    if solid:
        meshes = solid
    bound = [o for o in meshes if any(m.type == 'ARMATURE' for m in o.modifiers)]
    if bound and len(bound) < len(meshes):
        keep = list(bound)
        # keep unbound parts only if they are a meaningful share of the model (drops stray helper spheres)
        nb = sum(len(o.data.vertices) for o in bound)
        keep += [o for o in meshes if o not in bound and len(o.data.vertices) > 0.25 * nb]
        meshes = keep
    baked = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
        me.transform(ev.matrix_world)
        drop_outline_faces(me)
        n = bpy.data.objects.new(o.name + '_b', me)
        bpy.context.scene.collection.objects.link(n)
        baked.append(n)
    for o in list(bpy.data.objects):
        if o not in baked:
            bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    obj = baked[0]
    if len(baked) > 1:
        with bpy.context.temp_override(active_object=obj, selected_objects=baked, selected_editable_objects=baked):
            bpy.ops.object.join()
    obj.name = sid
    me = obj.data
    me.name = sid
    fold_uvs(me)
    # -- 2. normalise ------------------------------------------------------------------------------------------
    if ov.get('rot_deg'):   # fix models whose source axes are off (degrees about X, Y, Z)
        me.transform(Euler([math.radians(a) for a in ov['rot_deg']], 'XYZ').to_matrix().to_4x4())
    face = float(ov.get('face_deg', 0.0))
    if face:
        me.transform(Matrix.Rotation(math.radians(face), 4, 'Z'))
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    V = co.reshape(-1, 3)
    lo, hi = V.min(0), V.max(0)
    hh = hi[2] - lo[2]
    s = height_m / hh
    ext = max(hi[0] - lo[0], hi[1] - lo[1]) * s
    if ext > 2.3 * height_m:
        s *= 2.3 * height_m / ext
    s *= float(ov.get('scale', 1.0))
    V = (V - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])) * s
    me.vertices.foreach_set('co', V.reshape(-1))
    me.update()
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if tris > TRI_BUDGET:
        mod = obj.modifiers.new('dec', 'DECIMATE')
        mod.ratio = TRI_BUDGET / tris
        with bpy.context.temp_override(active_object=obj, object=obj, selected_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier='dec')
        me = obj.data
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
    for img in bpy.data.images:
        w, h = img.size
        if w > TEX_MAX or h > TEX_MAX:
            k = TEX_MAX / max(w, h)
            img.scale(max(1, int(w * k)), max(1, int(h * k)))
    for mat in me.materials:   # per-species flat colours for materials whose texture is only a mask (flames)
        col = ov.get('material_colors', {}).get(mat.name if mat else '')
        if col and mat.use_nodes:
            bsdf = next(nd for nd in mat.node_tree.nodes if nd.type == 'BSDF_PRINCIPLED')
            for lk in list(bsdf.inputs['Base Color'].links):
                mat.node_tree.links.remove(lk)
            bsdf.inputs['Base Color'].default_value = (*col, 1.0)
    for mat in me.materials:   # the cel shader only reads albedo; keep it deterministic and cheap
        if mat and mat.use_nodes:
            for nd in mat.node_tree.nodes:
                if nd.type == 'BSDF_PRINCIPLED':
                    nd.inputs['Metallic'].default_value = 0.0
                    nd.inputs['Roughness'].default_value = 0.8

    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    V = co.reshape(-1, 3)

    # -- 3. rig ------------------------------------------------------------------------------------------------
    plan = fit_skeleton(V)
    arm = make_armature(plan)
    weights = skin_weights(V, plan)
    for b in BONES[1:]:
        obj.vertex_groups.new(name=b)
    for bi, b in enumerate(BONES[1:]):
        vg = obj.vertex_groups[b]
        col = weights[:, bi]
        for vi in np.nonzero(col > 0.0)[0]:
            vg.add([int(vi)], float(col[vi]), 'REPLACE')
    obj.parent = arm
    md = obj.modifiers.new('Armature', 'ARMATURE')
    md.object = arm

    # -- 4. animate --------------------------------------------------------------------------------------------
    H = float(V[:, 2].max())
    acts = []
    for clip in CLIPS:
        acts.append(write_clip(arm, clip, H, plan))
    C.stash_actions(arm, acts)
    C.export_glb(out_path, export_image_format='JPEG', export_jpeg_quality=88)
    return {'height_m': round(H, 3), 'tris': int(tris), 'bones': len(BONES), 'plan': plan['kind'],
            'animations': CLIPS, 'bytes': os.path.getsize(out_path)}


def fold_uvs(me):
    """Source atlases often tile (UV v in 2..3): fold each polygon back into 0..1 so clamped samplers work."""
    import numpy as np
    if not me.uv_layers:
        return
    uvl = me.uv_layers.active.data
    n = len(uvl)
    a = np.empty(n * 2)
    uvl.foreach_get('uv', a)
    a = a.reshape(-1, 2)
    starts = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get('loop_start', starts)
    totals = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get('loop_total', totals)
    if len(starts) == 0:
        return
    mean = np.add.reduceat(a, starts, axis=0) / totals[:, None]
    shift = np.repeat(np.floor(mean), totals, axis=0)
    uvl.foreach_set('uv', (a - shift).reshape(-1))


def _is_outline(mat):
    """Toon-style source models ship an inverted-hull 'outline' shell: untextured near-black material."""
    if mat is None:
        return False
    if any(k in mat.name.lower() for k in ('outline', 'edge', 'contour')):
        return True
    if not mat.use_nodes:
        return False
    for nd in mat.node_tree.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image is not None:
            return False
        if nd.type == 'BSDF_PRINCIPLED':
            c = nd.inputs['Base Color']
            if c.is_linked:
                return False
            r, g, b, _ = c.default_value
            if max(r, g, b) < 0.02:
                return True
    return False


def drop_outline_faces(me):
    import bmesh
    bad = {i for i, m in enumerate(me.materials) if _is_outline(m)}
    if not bad or len(bad) == len(me.materials):
        return
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bad], context='FACES')
    bm.to_mesh(me)
    bm.free()


# ---------------------------------------------------------------------------------------------- skeleton fitting
def fit_skeleton(V):
    """Bone (head, tail) positions in Blender space (facing -Y) fitted to the vertex cloud."""
    import numpy as np
    x, f, z = V[:, 0], -V[:, 1], V[:, 2]      # f: forward
    H = float(z.max())
    xw = float(np.abs(x).max())
    fmin, fmax = float(f.min()), float(f.max())
    L = max(fmax - fmin, 1e-4)
    cf, cz = float(np.median(f)), float(np.median(z))
    horizontal = L > 1.1 * H

    def P(px, pf, pz):
        return np.array([px, -pf, pz], dtype=float)

    def mean_or(mask, arr, default):
        return float(arr[mask].mean()) if mask.sum() >= 3 else default

    bones = {}
    if not horizontal:
        slab = z > 0.85 * H
        hf = mean_or(slab, f, cf)
        chain = [P(0, cf, .34 * H), P(0, cf, .46 * H), P(0, cf, .58 * H), P(0, cf, .70 * H),
                 P(0, cf + (hf - cf) * .5, .82 * H), P(0, hf, .99 * H)]
        top = P(0, hf, 1.0 * H)
        hips_h = chain[0]
    else:
        slab = f > fmax - 0.14 * L
        hf = mean_or(slab, f, fmax - .05 * L)
        hz = mean_or(slab, z, cz)
        pb = P(0, cf - .28 * L, cz)
        pf = P(0, cf + .16 * L, cz)
        chain = [pb, pb + (pf - pb) * .33, pb + (pf - pb) * .66, pf,
                 P(0, hf - .06 * L, hz), P(0, fmax - .01 * L, hz)]
        hips_h = pb
        top = chain[5]
    names = ['Hips', 'Spine', 'Chest', 'Neck', 'Head']
    for i, nm in enumerate(names):
        bones[nm] = (chain[i], chain[i + 1] if i < 4 else top)
        if i == 4:
            bones[nm] = (chain[4], chain[5])
    # neck bone runs chest-top -> head base: (chain[3], chain[4]); head: (chain[4], chain[5])
    bones['Chest'] = (chain[2], chain[3])
    bones['Neck'] = (chain[3], chain[4])
    bones['Head'] = (chain[4], chain[5])

    # tail: from the hips towards the rearmost cluster
    rear = f < fmin + 0.10 * L
    tip = P(mean_or(rear, x, 0.0), mean_or(rear, f, fmin), mean_or(rear, z, .3 * H))
    t0 = hips_h
    if np.linalg.norm(tip - t0) < 0.2 * H:
        tip = t0 + np.array([0, 0.2 * H, -0.02 * H])
    pts = [t0 + (tip - t0) * k for k in (0, 1 / 3, 2 / 3, 1)]
    for i in range(3):
        bones['Tail%d' % (i + 1)] = (pts[i], pts[i + 1])

    low = z < 0.16 * H
    for side, s in (('L', 1.0), ('R', -1.0)):
        sm = (np.sign(x) == s) if True else None
        if horizontal:
            jz = float(min(max(cz, .45 * H), .7 * H))
            for pre, front in (('F', True), ('H', False)):
                band = low & sm & ((f > cf) if front else (f <= cf))
                fx = mean_or(band, x, s * max(.3 * xw, .05 * H))
                ff = mean_or(band, f, cf + (.18 if front else -.22) * L)
                foot = P(fx, ff, .03 * H)
                hip = P(fx * .6, ff, jz)
                knee = (hip + foot) / 2 + np.array([0, -.04 * H, 0])
                bones['%s%s_Upper' % (pre, side)] = (hip, knee)
                bones['%s%s_Lower' % (pre, side)] = (knee, foot)
        else:
            band = low & sm
            fx = mean_or(band, x, s * .28 * xw)
            ff = mean_or(band, f, cf)
            foot = P(fx, ff, .03 * H)
            hip = P(fx * .6, cf, .36 * H)
            knee = P(fx * .8, cf + (ff - cf) * .5 - .03 * H, .19 * H)
            bones['H%s_Upper' % side] = (hip, knee)
            bones['H%s_Lower' % side] = (knee, foot)
            arm_band = sm & (z > .25 * H) & (z < .85 * H)
            ax = np.abs(x[arm_band]) if arm_band.sum() else np.array([0.0])
            sel = arm_band & (np.abs(x) >= (np.quantile(ax, .97) if arm_band.sum() > 10 else 1e9))
            hx = mean_or(sel, x, s * .6 * xw)
            hf2 = mean_or(sel, f, cf)
            hz2 = mean_or(sel, z, .5 * H)
            sh = P(s * .18 * max(xw, .1 * H), cf, .64 * H)
            hand = P(hx, hf2, hz2)
            if np.linalg.norm(hand - sh) < .12 * H:
                hand = sh + np.array([s * .12 * H, -.03 * H, -.14 * H])
            elb = (sh + hand) / 2 + np.array([0, -.02 * H, 0])
            bones['F%s_Upper' % side] = (sh, elb)
            bones['F%s_Lower' % side] = (elb, hand)
    bones['Root'] = (np.array([0, -cf, 0.0]), np.array([0, -cf, .08 * H]))
    for nm, (a, b) in list(bones.items()):
        if np.linalg.norm(b - a) < .02 * H:
            bones[nm] = (a, a + np.array([0, 0, .02 * H]))
    parent = {'Root': None, 'Hips': 'Root', 'Spine': 'Hips', 'Chest': 'Spine', 'Neck': 'Chest', 'Head': 'Neck',
              'Tail1': 'Hips', 'Tail2': 'Tail1', 'Tail3': 'Tail2'}
    for pre in ('F', 'H'):
        for side in 'LR':
            parent['%s%s_Upper' % (pre, side)] = 'Chest' if pre == 'F' else 'Hips'
            parent['%s%s_Lower' % (pre, side)] = '%s%s_Upper' % (pre, side)
    return {'bones': bones, 'parent': parent, 'kind': 'horizontal' if horizontal else 'upright', 'H': H,
            'xw': xw, 'L': L}


def make_armature(plan):
    import bpy
    from mathutils import Vector
    data = bpy.data.armatures.new('Rig')
    arm = bpy.data.objects.new('Armature', data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    made = {}
    for nm in BONES:
        a, b = plan['bones'][nm]
        e = data.edit_bones.new(nm)
        e.head = Vector(a)
        e.tail = Vector(b)
        e.roll = 0.0
        made[nm] = e
    for nm in BONES:
        p = plan['parent'][nm]
        if p:
            made[nm].parent = made[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.select_set(False)
    return arm


def skin_weights(V, plan, power=3.0, keep=4):
    """Inverse-distance weights to bone segments -> (n, len(BONES)-1), top `keep` per vertex, normalised."""
    import numpy as np
    H = plan['H']
    names = BONES[1:]
    d = np.empty((len(V), len(names)))
    for i, nm in enumerate(names):
        a, b = plan['bones'][nm]
        ab = b - a
        t = np.clip(((V - a) @ ab) / max(float(ab @ ab), 1e-9), 0.0, 1.0)
        d[:, i] = np.linalg.norm(V - (a + t[:, None] * ab), axis=1)
    w = (d + 0.03 * H) ** -power
    if keep < len(names):
        drop = np.argsort(w, axis=1)[:, :-keep]
        np.put_along_axis(w, drop, 0.0, axis=1)
    w /= w.sum(axis=1, keepdims=True)
    w[w < 0.04] = 0.0
    w /= w.sum(axis=1, keepdims=True)
    return w


# ---------------------------------------------------------------------------------------------- animation
TAU = math.tau


def sm(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def bump(u, a, b, c):
    """0 before a, smooth rise to 1 at b, smooth fall to 0 at c."""
    if u <= a or u >= c:
        return 0.0
    return sm((u - a) / (b - a)) if u < b else 1.0 - sm((u - b) / (c - b))


class Pose:
    def __init__(self, H, xw):
        self.H, self.xw = H, xw
        self.r, self.m, self.s = {}, {}, {}

    def rot(self, bone, rx=0.0, ry=0.0, rz=0.0):
        o = self.r.get(bone, (0.0, 0.0, 0.0))
        self.r[bone] = (o[0] + rx, o[1] + ry, o[2] + rz)

    def side(self, pre, rx=0.0, ry=0.0, rz=0.0, part='Upper'):
        """rotate the L/R pair, mirroring the lateral (ry/rz) components."""
        self.rot('%sL_%s' % (pre, part), rx, ry, rz)
        self.rot('%sR_%s' % (pre, part), rx, -ry, -rz)

    def move(self, bone, dx=0.0, df=0.0, dz=0.0):
        """translate in units of body height; df is forward."""
        o = self.m.get(bone, (0.0, 0.0, 0.0))
        self.m[bone] = (o[0] + dx * self.H, o[1] - df * self.H, o[2] + dz * self.H)

    def scale(self, bone, sx=1.0, sy=1.0, sz=1.0):
        o = self.s.get(bone, (1.0, 1.0, 1.0))
        self.s[bone] = (o[0] * sx, o[1] * sy, o[2] * sz)


def _tail(P, u, amp, cycles=1.0, lag=0.6, pitch=0.0):
    for i, b in enumerate(('Tail1', 'Tail2', 'Tail3')):
        P.rot(b, rx=pitch, rz=amp * (i + 1) / 3 * math.sin(TAU * cycles * u - lag * i))


def clip_pose(name, u, H, xw):
    P = Pose(H, xw)
    s = math.sin(TAU * u)
    if name == 'Idle':
        P.move('Root', dz=0.006 * s)
        P.scale('Root', 1, 1, 1 + 0.012 * s)
        P.rot('Hips', rx=1.2 * s)
        P.rot('Spine', rx=1.6 * math.sin(TAU * u - .4))
        P.rot('Chest', rx=2.0 * math.sin(TAU * u - .7))
        P.rot('Neck', rx=3.0 * math.sin(TAU * u - 1.0))
        P.rot('Head', rx=2.0 * math.sin(TAU * u - 1.3), rz=3.5 * math.sin(TAU * u * 2 + .5))
        P.side('F', ry=4.0 * s, rx=2 * s)
        P.side('F', rx=3 * math.sin(TAU * u - .5), part='Lower')
        _tail(P, u, 14, 1, .7)
    elif name in ('Walk', 'Run'):
        run = name == 'Run'
        k = 1.7 if run else 1.0
        c = TAU * u
        for pre, ph in (('FL', 0), ('FR', math.pi), ('HL', math.pi), ('HR', 0)):
            up, lo = 'Upper', 'Lower'
            sw = 26 * k * math.sin(c + ph)
            bend = 24 * k * max(0.0, math.sin(c + ph + 1.4))
            P.rot('%s_%s' % (pre, up), rx=sw if pre[0] == 'H' else -sw * .8)
            P.rot('%s_%s' % (pre, lo), rx=bend)
        P.move('Root', dz=(0.03 if run else 0.016) * math.cos(2 * c))
        P.rot('Hips', rz=4.5 * k * s, ry=2 * s)
        P.rot('Spine', rz=-3 * k * s, rx=(9 if run else 2) + 2 * math.cos(2 * c))
        P.rot('Chest', rz=-3 * k * s)
        P.rot('Head', rz=3 * k * s, rx=(-6 if run else -1))
        _tail(P, u, 16 * k, 1, .8, pitch=8 if run else 0)
    elif name == 'Attack':
        wind, lunge = bump(u, 0, .22, .4), bump(u, .3, .5, .88)
        P.move('Root', df=-0.08 * wind + 0.42 * lunge, dz=-0.05 * wind + 0.05 * lunge)
        P.rot('Hips', rx=-8 * wind + 6 * lunge)
        P.rot('Spine', rx=-10 * wind + 22 * lunge)
        P.rot('Head', rx=-12 * wind + 26 * lunge)
        P.side('F', ry=22 * wind, rx=-55 * lunge)
        P.side('F', rx=-30 * lunge, part='Lower')
        P.side('H', rx=18 * wind - 14 * lunge)
        _tail(P, u, 8, 1, .5, pitch=20 * lunge)
    elif name == 'Special':
        ch, th = bump(u, 0, .35, .62), bump(u, .5, .66, .96)
        sh = math.sin(TAU * u * 9) * ch
        P.move('Root', dx=0.012 * sh, dz=-0.02 * ch + 0.03 * th, df=0.14 * th)
        P.scale('Root', 1 + .02 * ch, 1 + .02 * ch, 1 - 0.05 * ch + 0.05 * th)
        P.rot('Spine', rx=-18 * ch + 14 * th)
        P.rot('Chest', rx=-8 * ch + 8 * th)
        P.rot('Head', rx=-28 * ch + 32 * th)
        P.side('F', ry=55 * ch, rx=-40 * th)
        P.side('F', ry=20 * ch, part='Lower')
        P.side('H', rx=-8 * ch)
        _tail(P, u, 22 * sh, 1, .5, pitch=-25 * ch + 10 * th)
    elif name == 'Hurt':
        hit = bump(u, 0, .15, .65)
        w = math.sin(TAU * 3 * u) * hit
        P.move('Root', df=-0.16 * hit, dz=0.01 * hit)
        P.rot('Root', ry=6 * w)
        P.scale('Root', 1 + .04 * hit, 1 + .04 * hit, 1 - .06 * hit)
        P.rot('Spine', rx=-16 * hit)
        P.rot('Head', rx=-25 * hit, rz=12 * w)
        P.side('F', ry=35 * hit, rx=15 * hit)
        P.side('H', rx=-10 * hit)
        _tail(P, u, 26 * w, 1, .4, pitch=15 * hit)
    elif name == 'Faint':
        fall = sm((u - .1) / .65)
        bounce = bump(u, .7, .78, .9) * .03
        P.rot('Root', ry=88 * fall)
        P.move('Root', dx=-0.45 * fall * 1.0, dz=(xw / H) * fall + bounce)
        P.rot('Head', rx=14 * fall, rz=10 * fall)
        P.rot('Spine', rx=-6 * fall)
        P.side('F', ry=28 * fall, rx=20 * fall)
        P.side('H', ry=10 * fall, rx=-12 * fall)
        P.side('F', rx=25 * fall, part='Lower')
        _tail(P, u, 22 * fall, .5, .6)
    elif name == 'Victory':
        hop = abs(math.sin(TAU * 2 * u))
        P.move('Root', dz=0.16 * hop)
        P.scale('Root', 1 + .03 * (1 - hop), 1 + .03 * (1 - hop), 1 - .06 * (1 - hop))
        P.side('F', ry=60 * hop + 15, rx=-20)
        P.side('F', ry=15 * hop, part='Lower')
        P.rot('Head', rx=-12)
        P.rot('Spine', rx=-6)
        P.side('H', rx=-18 * hop)
        _tail(P, u, 25, 4, .5)
    elif name == 'Sleep':
        P.move('Root', dz=-0.07)
        P.scale('Root', 1, 1, 1 + 0.02 * s)
        P.rot('Spine', rx=14)
        P.rot('Chest', rx=8)
        P.rot('Neck', rx=28)
        P.rot('Head', rx=22 + 2 * s)
        P.side('F', ry=8 + 3 * s, rx=8)
        P.side('H', rx=-25)
        P.side('H', rx=50, part='Lower')
        P.rot('Root', ry=3 * math.sin(TAU * u * 2))
        _tail(P, u, 5, 1, .8, pitch=-6)
    elif name == 'Roar':
        rear, shout = bump(u, 0, .3, .55), bump(u, .3, .45, .9)
        sh = math.sin(TAU * u * 8) * shout
        P.rot('Spine', rx=-14 * rear)
        P.rot('Chest', rx=-8 * rear)
        P.rot('Head', rx=-38 * rear + 10 * shout + 6 * sh)
        P.scale('Root', 1 - .03 * shout, 1 - .03 * shout, 1 + .08 * shout)
        P.move('Root', dz=0.02 * rear)
        P.side('F', ry=35 * rear, rx=-10 * shout)
        _tail(P, u, 20 * sh, 1, .5, pitch=-15 * rear)
    elif name == 'Dodge':
        sd = bump(u, 0, .35, .9)
        P.move('Root', dx=0.5 * sd, dz=0.03 * math.sin(math.pi * u))
        P.rot('Root', ry=-14 * sd)
        P.rot('Hips', rz=15 * sd)
        P.rot('Head', rz=-12 * sd)
        P.side('H', rx=25 * sd)
        P.side('F', ry=25 * sd)
        _tail(P, u, 20 * sd, .5)
    elif name == 'Spin':
        g = sm(u)
        P.rot('Root', rz=360 * g)
        P.move('Root', dz=0.04 * math.sin(math.pi * u))
        P.side('F', ry=40 * math.sin(math.pi * u))
        _tail(P, u, 18 * math.sin(math.pi * u), .5)
    elif name == 'Hop':
        sq, air = bump(u, 0, .14, .3), bump(u, .2, .5, .8)
        jump = math.sin(math.pi * min(max((u - .25) / .5, 0.0), 1.0))
        P.move('Root', dz=0.28 * jump)
        P.scale('Root', 1 + .05 * sq, 1 + .05 * sq, 1 - .12 * sq + .06 * air)
        P.side('H', rx=-30 * air)
        P.side('H', rx=40 * air, part='Lower')
        P.side('F', ry=30 * air, rx=-15 * air)
        P.rot('Head', rx=-8 * air)
        _tail(P, u, 10, 1, .4, pitch=15 * air)
    elif name == 'Charge':
        sh = math.sin(TAU * u * 6)
        P.scale('Root', 1.04, 1.04, .92)
        P.move('Root', dx=0.01 * sh, dz=-0.04)
        P.rot('Spine', rx=10)
        P.rot('Head', rx=12)
        P.side('F', ry=20, rx=-20)
        P.side('H', rx=-15)
        P.side('H', rx=30, part='Lower')
        _tail(P, u, 20, 3, .6)
    elif name == 'Taunt':
        c2 = math.sin(TAU * u * 2)
        P.rot('Root', ry=9 * c2, rz=8 * math.sin(TAU * u * 2 + .6))
        P.move('Root', dx=0.03 * c2, dz=0.02 * abs(c2))
        P.rot('Head', rz=15 * math.sin(TAU * u * 4))
        P.side('F', ry=30 + 25 * math.sin(TAU * u * 4))
        _tail(P, u, 30, 4, .5)
    elif name == 'Spawn':
        if u < .6:
            sc = 0.05 + 1.10 * sm(u / .6)
        else:
            sc = 1.15 - .15 * sm((u - .6) / .4)
        P.scale('Root', sc, sc, sc)
        P.rot('Root', rz=180 * (1 - sm(u / .7)))
        P.move('Root', dz=0.1 * math.sin(math.pi * u))
    elif name == 'Hover':
        P.move('Root', dz=0.12 + 0.03 * s)
        fl = math.sin(TAU * u * 3)
        P.side('F', ry=35 * fl + 10, rx=0)
        P.side('F', ry=15 * math.sin(TAU * u * 3 - .8), part='Lower')
        P.rot('Spine', rx=4 * s)
        P.rot('Head', rx=3 * math.sin(TAU * u - .8))
        P.side('H', rx=-12)
        _tail(P, u, 15, 1, .7)
    elif name == 'Talk':
        b = math.sin(TAU * u * 4)
        P.rot('Head', rx=10 * b, rz=3 * s)
        P.rot('Neck', rx=4 * b)
        P.scale('Root', 1, 1, 1 + .02 * b)
        P.side('F', ry=8 + 6 * b)
        _tail(P, u, 10, 2, .6)
    return P


def write_clip(arm, name, H, plan):
    from mathutils import Euler, Vector
    import common as C
    n = LENGTHS[name]
    w = C.ActionWriter(arm, name, n)
    for f in range(n + 1):
        u = f / n
        P = clip_pose(name, u, H, plan['xw'])
        if name in LOOPING and f == n:   # last frame == first frame
            P = clip_pose(name, 0.0, H, plan['xw'])
        for b in BONES:
            r = P.r.get(b)
            q = Euler([math.radians(a) for a in r], 'XYZ').to_quaternion() if r else None
            rot = None
            if q is not None:
                axis, ang = q.to_axis_angle()
                rot = (axis, ang)
            w.key(b, f, loc=P.m.get(b), rot=rot, scl=P.s.get(b))
    return w.write(BONES)


# ---------------------------------------------------------------------------------------------- driver
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--out', default=OUT_DIR)
    ap.add_argument('--no-manifest', action='store_true')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    table = species_table()
    want = [t.strip().upper() for t in a.only.split(',') if t.strip()]
    todo = [t for t in table if (a.all or t[0] in want)]
    todo_ids = [t[0] for t in todo]
    if a.jobs > 1 and len(todo) > 1:
        chunks = [todo_ids[i::a.jobs] for i in range(a.jobs)]
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), '--only', ','.join(c), '--no-manifest',
                                   '--out', a.out]) for c in chunks if c]
        rc = [p.wait() for p in procs]
        if any(rc):
            sys.exit(1)
    else:
        os.makedirs(a.out, exist_ok=True)
        ov = load_overrides()
        for sid, dex, h in todo:
            out = os.path.join(a.out, sid + '.glb')
            src = MISSINGNO_SRC if dex == 0 else os.path.join(SRC, 'models', 'opt', 'regular', '%d.glb' % dex)
            info = build_one(sid, src, h, ov.get(sid, {}), out)
            with open(os.path.join(a.out, '_%s.json' % sid), 'w') as fh:
                json.dump(info, fh)
            print('%-12s dex %3d  %s' % (sid, dex, info), flush=True)
    if not a.no_manifest and (a.all or want):
        write_manifest(a.out, todo_ids)


def write_manifest(out, ids):
    mp = os.path.join(out, 'manifest.json')
    old = json.load(open(mp)) if os.path.exists(mp) else {}
    species = old.get('species', {})
    for sid in ids:
        p = os.path.join(out, '_%s.json' % sid)
        if not os.path.exists(p):
            continue
        info = json.load(open(p))
        prev = species.get(sid, {})
        rec = {'height_m': info['height_m'], 'px_height': prev.get('px_height', 0.0), 'tris': info['tris'],
               'bones': info['bones'], 'file': sid + '.glb', 'bytes': info['bytes'], 'status': 'generated'}
        species[sid] = rec
        os.remove(p)
    man = {'generated': sorted(species), 'species': species, 'animations': CLIPS, 'looping': LOOPING,
           'source': 'Pokemon-3D-api/assets models/opt/regular (MIT), rigged + animated by gen_rigged_pokemon.py'}
    with open(mp, 'w') as fh:
        json.dump(man, fh, indent=1)


if __name__ == '__main__':
    main()

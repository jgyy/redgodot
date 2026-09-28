"""Shared helpers for the headless Blender asset pipeline (Blender 4.0, bpy + bmesh).

Conventions used by every gen_*.py script
-----------------------------------------
* Blender is Z-up.  The model's FRONT faces Blender -Y, which the glTF exporter turns
  into +Z -- Godot's MODEL_FRONT convention.  (Placing the image-plane "toward the
  viewer" direction on -Y also keeps image X == world X, i.e. the 2D art is not mirrored.)
* Geometry is built into one bmesh with an int vertex layer "grp" (rigid-skin group index)
  and face material indices into a per-model material list, then turned into ONE skinned
  mesh object parented to an Armature (glTF skin).
* Animations are written straight into Actions as F-curves and stashed on NLA tracks,
  then exported by the glTF exporter in ACTIONS mode (one glTF animation per action).
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion
from mathutils.geometry import tessellate_polygon

FPS = 30


# ----------------------------------------------------------------------------- scene
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    return sc


def parse_args(argv=None):
    argv = sys.argv if argv is None else argv
    return argv[argv.index('--') + 1:] if '--' in argv else []


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


# ----------------------------------------------------------------------------- colour/material
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h):
    h = (h or '#888888').strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        r, g, b = 0.5, 0.5, 0.5
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), 1.0)


def make_material(name, hex_color='#888888', roughness=0.55, specular=0.35, metallic=0.0,
                  emission=None, emission_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    col = hex_to_linear(hex_color)
    ins = bsdf.inputs
    ins['Base Color'].default_value = col
    ins['Roughness'].default_value = roughness
    ins['Metallic'].default_value = metallic
    if 'Specular IOR Level' in ins:
        ins['Specular IOR Level'].default_value = specular
    if emission is not None and emission_strength > 0:
        key = 'Emission Color' if 'Emission Color' in ins else 'Emission'
        ins[key].default_value = hex_to_linear(emission)
        ins['Emission Strength'].default_value = emission_strength
    if alpha < 1.0:
        ins['Alpha'].default_value = alpha
        if hasattr(m, 'blend_method'):
            m.blend_method = 'BLEND'
        if hasattr(m, 'shadow_method'):
            # Removed in Blender 4.2+ (EEVEE Next handles transparent shadows itself).
            m.shadow_method = 'HASHED'
    m.diffuse_color = (col[0], col[1], col[2], alpha)
    return m


class MaterialCache:
    """One material per unique hex colour, in stable slot order for a single mesh."""

    def __init__(self, prefix='mat'):
        self.prefix = prefix
        self.index = {}
        self.mats = []

    def get(self, hex_color, **kw):
        key = (hex_color or '#888888').lower()
        if key not in self.index:
            name = '%s_%s' % (self.prefix, key.lstrip('#'))
            self.index[key] = len(self.mats)
            self.mats.append(make_material(name, key, **kw))
        return self.index[key]

    def add_named(self, name, hex_color, **kw):
        key = 'named:' + name
        if key not in self.index:
            self.index[key] = len(self.mats)
            self.mats.append(make_material(name, hex_color, **kw))
        return self.index[key]


# ----------------------------------------------------------------------------- bmesh primitives
class MeshBuilder:
    """Accumulates primitives into a single bmesh, tagging verts with a group index."""

    def __init__(self):
        self.bm = bmesh.new()
        self.grp = self.bm.verts.layers.int.new('grp')
        self.groups = []          # index -> name
        self._gidx = {}

    def group_index(self, name):
        if name not in self._gidx:
            self._gidx[name] = len(self.groups)
            self.groups.append(name)
        return self._gidx[name]

    def _tag(self, verts, faces, mat, gname, smooth=True):
        gi = self.group_index(gname)
        for v in verts:
            v[self.grp] = gi
        for f in faces:
            f.material_index = mat
            f.smooth = smooth
        return faces

    # --- ellipsoid ------------------------------------------------------------
    def ellipsoid(self, center, radii, mat, gname, rot_y=0.0, orient=None, segs=None):
        """radii = (rx, ry_depth, rz). orient: optional 3x3 Matrix applied after rot_y."""
        rx, ry, rz = (max(1e-4, r) for r in radii)
        if segs is None:
            big = max(rx, rz)
            u = int(max(10, min(28, round(2 * math.pi * big / 2.4))))
            v = int(max(6, min(18, round(u * 0.6))))
        else:
            u, v = segs
        M = Matrix.Translation(Vector(center))
        R = Matrix.Rotation(rot_y, 4, 'Y')
        if orient is not None:
            R = orient.to_4x4() @ R
        M = M @ R @ Matrix.Diagonal((rx, ry, rz, 1.0))
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=1.0, matrix=M)
        verts = res['verts']
        faces = {f for vv in verts for f in vv.link_faces}
        return self._tag(verts, faces, mat, gname)

    # --- tube along a 3D path with hemispherical caps -------------------------
    def tube(self, pts, radii, mat, gname, nseg=None, caps=True, smooth=True):
        pts = [Vector(p) for p in pts]
        # drop coincident points
        P, Rr = [pts[0]], [radii[0]]
        for p, r in zip(pts[1:], radii[1:]):
            if (p - P[-1]).length > 1e-5:
                P.append(p)
                Rr.append(r)
        if len(P) < 2:
            # degenerate -> sphere
            r = max(radii)
            return self.ellipsoid(pts[0], (r, r, r), mat, gname)
        rmax = max(Rr)
        if nseg is None:
            nseg = int(max(8, min(18, round(2 * math.pi * rmax / 1.6))))
        tans = []
        for i in range(len(P)):
            a = P[max(0, i - 1)]
            b = P[min(len(P) - 1, i + 1)]
            t = b - a
            tans.append(t.normalized() if t.length > 1e-8 else Vector((0, 0, 1)))

        def frame(t):
            ref = Vector((0, 1, 0))
            n = ref - t * ref.dot(t)
            if n.length < 1e-4:
                ref = Vector((1, 0, 0))
                n = ref - t * ref.dot(t)
            n.normalize()
            b = t.cross(n).normalized()
            return n, b

        rings = []  # list of (center, radius, tangent)
        if caps:
            c0, r0, t0 = P[0], Rr[0], tans[0]
            for phi in (60, 30):
                a = math.radians(phi)
                rings.append((c0 - t0 * r0 * math.sin(a), r0 * math.cos(a), t0))
        for c, r, t in zip(P, Rr, tans):
            rings.append((c, r, t))
        if caps:
            c1, r1, t1 = P[-1], Rr[-1], tans[-1]
            for phi in (30, 60):
                a = math.radians(phi)
                rings.append((c1 + t1 * r1 * math.sin(a), r1 * math.cos(a), t1))
        bm = self.bm
        ring_verts = []
        for c, r, t in rings:
            n, b = frame(t)
            rv = []
            for k in range(nseg):
                ang = 2 * math.pi * k / nseg
                rv.append(bm.verts.new(c + (n * math.cos(ang) + b * math.sin(ang)) * max(r, 1e-4)))
            ring_verts.append(rv)
        faces = []
        for i in range(len(ring_verts) - 1):
            A, B = ring_verts[i], ring_verts[i + 1]
            for k in range(nseg):
                k2 = (k + 1) % nseg
                faces.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
        allv = [v for rv in ring_verts for v in rv]
        if caps:
            p0 = bm.verts.new(P[0] - tans[0] * Rr[0])
            p1 = bm.verts.new(P[-1] + tans[-1] * Rr[-1])
            A, B = ring_verts[0], ring_verts[-1]
            for k in range(nseg):
                k2 = (k + 1) % nseg
                faces.append(bm.faces.new((p0, A[k2], A[k])))
                faces.append(bm.faces.new((p1, B[k], B[k2])))
            allv += [p0, p1]
        else:
            faces.append(bm.faces.new(list(reversed(ring_verts[0]))))
            faces.append(bm.faces.new(ring_verts[-1]))
        return self._tag(allv, faces, mat, gname, smooth)

    # --- extruded / pillowed polygon plate in the XZ plane ------------------
    def plate(self, pts_xz, y_center, thickness, mat, gname, target_edge=3.0, max_levels=3,
              bulge=True):
        """pts_xz: [(X,Z),...] polygon in the XZ plane; extruded along Y."""
        pts = []
        for p in pts_xz:
            if not pts or (Vector(p) - Vector(pts[-1])).length > 1e-6:
                pts.append(tuple(p))
        if len(pts) > 2 and (Vector(pts[0]) - Vector(pts[-1])).length < 1e-6:
            pts.pop()
        if len(pts) < 3:
            raise ValueError('degenerate polygon')
        tris = tessellate_polygon([[Vector((x, z, 0.0)) for x, z in pts]])
        if not tris:
            raise ValueError('polygon tessellation failed')
        V = [Vector((x, z)) for x, z in pts]
        T = [tuple(t) for t in tris]
        # uniform 4-way subdivision (no T-junctions)
        maxe = max((V[a] - V[b]).length for t in T for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])))
        levels = 0
        while maxe > target_edge and levels < max_levels:
            maxe *= 0.5
            levels += 1
        for _ in range(levels):
            mid = {}

            def m(a, b):
                k = (a, b) if a < b else (b, a)
                if k not in mid:
                    mid[k] = len(V)
                    V.append((V[a] + V[b]) * 0.5)
                return mid[k]
            NT = []
            for a, b, c in T:
                ab, bc, ca = m(a, b), m(b, c), m(c, a)
                NT += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
            T = NT
        # boundary edges
        ecount = {}
        for a, b, c in T:
            for e in ((a, b), (b, c), (c, a)):
                k = (min(e), max(e))
                ecount[k] = ecount.get(k, 0) + 1
        bedges = [e for e, n in ecount.items() if n == 1]
        bverts = {i for e in bedges for i in e}
        h = thickness * 0.5
        bm = self.bm
        fv, bv = [], []
        for i, p in enumerate(V):
            hh = h * (0.55 if (bulge and i in bverts) else 1.0)
            fv.append(bm.verts.new((p.x, y_center - hh, p.y)))
            bv.append(bm.verts.new((p.x, y_center + hh, p.y)))
        faces_s, faces_f = [], []
        for a, b, c in T:
            faces_s.append(bm.faces.new((fv[a], fv[b], fv[c])))
            faces_s.append(bm.faces.new((bv[c], bv[b], bv[a])))
        for a, b in bedges:
            try:
                faces_f.append(bm.faces.new((fv[a], bv[a], bv[b], fv[b])))
            except ValueError:
                pass
        self._tag(fv + bv, faces_s, mat, gname, smooth=True)
        self._tag([], faces_f, mat, gname, smooth=False)
        return faces_s + faces_f

    # --- axis aligned box ------------------------------------------------------
    def box(self, lo, hi, mat, gname, smooth=False):
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        lo, hi = Vector(lo), Vector(hi)
        c = (lo + hi) * 0.5
        s = hi - lo
        for v in res['verts']:
            v.co = Vector((c.x + v.co.x * s.x, c.y + v.co.y * s.y, c.z + v.co.z * s.z))
        faces = {f for v in res['verts'] for f in v.link_faces}
        return self._tag(res['verts'], faces, mat, gname, smooth)

    def finish(self):
        bm = self.bm
        bm.normal_update()
        try:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        except Exception:
            pass
        bm.normal_update()

    def transform(self, fn):
        for v in self.bm.verts:
            v.co = fn(v.co)

    def bbox(self):
        xs = [v.co for v in self.bm.verts]
        lo = Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs)))
        hi = Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs)))
        return lo, hi

    def to_object(self, name, materials, with_vgroups=True):
        me = bpy.data.meshes.new(name)
        self.bm.verts.index_update()
        per_group = {}
        if with_vgroups:
            for v in self.bm.verts:
                per_group.setdefault(v[self.grp], []).append(v.index)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in materials:
            me.materials.append(m)
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        if with_vgroups:
            for gi, gname in enumerate(self.groups):
                vg = obj.vertex_groups.new(name=gname)
                if gi in per_group:
                    vg.add(per_group[gi], 1.0, 'REPLACE')
        return obj


# ----------------------------------------------------------------------------- rig + animation
def build_armature(name, bones, root_name='root', root_len=0.3):
    """bones: list of dicts {name, head(Vector), parent(str|None), length}. All bones point +Z."""
    arm_data = bpy.data.armatures.new(name + '_armature')
    arm = bpy.data.objects.new(name + '_rig', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    r = eb.new(root_name)
    r.head = (0, 0, 0)
    r.tail = (0, 0, max(root_len, 1e-3))
    r.roll = 0
    made = {root_name: r}
    for b in bones:
        e = eb.new(b['name'])
        h = Vector(b['head'])
        e.head = h
        e.tail = h + Vector((0, 0, max(b.get('length', 0.1), 1e-3)))
        e.roll = 0
        made[b['name']] = e
    for b in bones:
        par = b.get('parent') or root_name
        made[b['name']].parent = made.get(par, r)
        made[b['name']].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm


def skin_to_armature(mesh_obj, arm):
    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm


class ActionWriter:
    """Collects per-bone keyframes expressed in ARMATURE (world) space deltas and writes
    them as local pose F-curves.  loc: world-space offset; rot: (axis Vector, angle) about
    the bone head; scl: world-axis scale (sx, sy, sz)."""

    def __init__(self, arm, name, length_frames):
        self.arm = arm
        self.name = name
        self.n = length_frames
        self.keys = {}  # bone -> {frame: (loc, quat, scale)}

    def key(self, bone, frame, loc=None, rot=None, scl=None):
        b = self.arm.data.bones[bone]
        R = b.matrix_local.to_3x3()
        Ri = R.transposed()
        lv = Ri @ Vector(loc) if loc is not None else Vector((0, 0, 0))
        if rot is not None:
            q = Quaternion(Ri @ Vector(rot[0]), rot[1])
        else:
            q = Quaternion()
        if scl is not None:
            s = Vector(scl)
            ls = Vector([sum(abs(Ri[i][j]) * s[j] for j in range(3)) for i in range(3)])
        else:
            ls = Vector((1, 1, 1))
        self.keys.setdefault(bone, {})[frame] = (lv, q, ls)

    def write(self, all_bones):
        # Blender 4.4+ replaced the old single-layer Action (Action.fcurves /
        # Action.id_root) with slotted/layered actions. fcurve_ensure_for_datablock
        # requires the action to already be the datablock's *active* action, so we
        # assign it temporarily and detach afterwards (stash_actions() puts the
        # finished action into its own NLA strip, it doesn't need to stay active).
        act = bpy.data.actions.new(self.name)
        act.use_fake_user = True
        ad = self.arm.animation_data or self.arm.animation_data_create()
        prev_action = ad.action
        ad.action = act
        for bone in all_bones:
            fr = self.keys.get(bone, {})
            if 0 not in fr:
                fr[0] = (Vector((0, 0, 0)), Quaternion(), Vector((1, 1, 1)))
            if self.n not in fr:
                fr[self.n] = fr[0] if self.name in ('Idle', 'Walk') else (Vector((0, 0, 0)), Quaternion(), Vector((1, 1, 1)))
            frames = sorted(fr)
            base = 'pose.bones["%s"].' % bone
            for prop, idx_n, getter in (('location', 3, lambda k: k[0]),
                                        ('rotation_quaternion', 4, lambda k: k[1]),
                                        ('scale', 3, lambda k: k[2])):
                for i in range(idx_n):
                    fc = act.fcurve_ensure_for_datablock(self.arm, base + prop, index=i, group_name=bone)
                    fc.keyframe_points.add(len(frames))
                    co = []
                    for f in frames:
                        co += [float(f), float(getter(fr[f])[i])]
                    fc.keyframe_points.foreach_set('co', co)
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                    fc.update()
        ad.action = prev_action
        return act


def stash_actions(arm, actions):
    ad = arm.animation_data or arm.animation_data_create()
    for act in actions:
        tr = ad.nla_tracks.new()
        tr.name = act.name
        st = tr.strips.new(act.name, 0, act)
        st.name = act.name
        tr.mute = False
    ad.action = None


def export_glb(path, animations=True):
    ensure_dir(os.path.dirname(path))
    kw = dict(filepath=path, export_format='GLB', check_existing=False, use_selection=False,
              export_apply=False, export_yup=True, export_materials='EXPORT',
              export_animations=animations)
    if animations:
        kw.update(export_animation_mode='ACTIONS', export_skins=True, export_force_sampling=True,
                  export_reset_pose_bones=True, export_anim_slide_to_zero=True,
                  export_optimize_animation_size=True)
    bpy.ops.export_scene.gltf(**kw)


# ----------------------------------------------------------------------------- generic creature animation
def _has(name, *subs):
    n = name.lower()
    return any(s in n for s in subs)


def is_leg(name):
    return _has(name, 'leg', 'foot', 'feet', 'paw')


def is_arm(name):
    return _has(name, 'arm', 'hand') and not is_leg(name)


def is_wing(name):
    return _has(name, 'wing')


def is_tail(name):
    return _has(name, 'tail')


def limb_phase(name, idx_fallback=0):
    """Parity of 'B'/'R'/'2' markers in the suffix after leg/foot/arm -> alternate gait."""
    low = name.lower()
    for pre in ('legs', 'leg', 'foot', 'feet', 'paw', 'arm', 'hand'):
        if pre in low:
            suffix = name[low.index(pre) + len(pre):]
            break
    else:
        suffix = name
    n = sum(suffix.count(ch) for ch in ('B', 'R', '2', 'b', 'r'))
    return math.pi * (n % 2)


def animate_generic(arm, group_bones, height, has_head=None, root='root', loop_idle=60,
                    loop_walk=24, attack_len=18, body=None, flier=False, hovering=False):
    """Bake Idle / Walk / Attack / Hurt / Faint / Special on a group-per-bone rig.

    group_bones: {bone_name: {'pivot': Vector, 'x': float}}  (pivot in metres).
    Axes: front = -Y, up = +Z; rotations are (world axis, angle) about each bone's head.
    Wings flap and tails wag in the sprite (XZ) plane so it reads from the front (foe)
    and from behind (the player's Pokemon)."""
    h = max(height, 0.05)
    names = list(group_bones)
    all_bones = [root] + names
    legs = [n for n in names if is_leg(n)]
    arms = [n for n in names if is_arm(n)]
    wings = [n for n in names if is_wing(n)]
    tails = [n for n in names if is_tail(n)]
    ears = [n for n in names if _has(n, 'ear', 'antenna', 'horn', 'crest', 'leaf', 'petal', 'frond')
            and not is_tail(n)]
    heads = [n for n in names if _has(n, 'head') or n.lower() in ('mouth', 'jaw', 'beak', 'face', 'skull')]
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    floaty = flier or hovering or not legs
    TAU = 2 * math.pi

    phases = {n: limb_phase(n) for n in legs}
    if len(legs) > 1 and len({round(p, 3) for p in phases.values()}) == 1:
        for i, n in enumerate(sorted(legs, key=lambda k: group_bones[k]['x'])):
            phases[n] = math.pi * (i % 2)
    aph = {n: limb_phase(n) + math.pi for n in arms}
    if len(arms) > 1 and len({round(p, 3) for p in aph.values()}) == 1:
        for i, n in enumerate(sorted(arms, key=lambda k: group_bones[k]['x'])):
            aph[n] = math.pi * (i % 2)

    def side(n):
        return 1.0 if group_bones[n]['x'] >= 0 else -1.0

    def wing_flap(act, f, t, amp, cycles=1):
        for n in wings:
            act.key(n, f, rot=(Y, -side(n) * math.radians(amp) * math.sin(TAU * cycles * t)))

    def idle_extras(act, f, t, k=1.0):
        for i, n in enumerate(tails):
            act.key(n, f, rot=(Y, k * math.radians(9) * math.sin(TAU * 2 * t + i * 0.7)))
        for i, n in enumerate(ears):
            act.key(n, f, rot=(Y, k * math.radians(3.5) * math.sin(TAU * t + 1.3 + i)))
        for n in heads:
            act.key(n, f, rot=(X, k * math.radians(3) * math.sin(TAU * t + 0.6)))
        for n in arms:
            act.key(n, f, rot=(Y, -side(n) * k * math.radians(4) * math.sin(TAU * t + 0.4)))

    # ---------- Idle: breathing squash + gentle bob (bigger float for hoverers), tail wag, wing beat
    idle = ActionWriter(arm, 'Idle', loop_idle)
    for f in range(0, loop_idle + 1, 2):
        t = f / loop_idle
        s = math.sin(TAU * t)
        bob = (0.06 if floaty else 0.018) * h * (0.5 - 0.5 * math.cos(TAU * t))
        idle.key(root, f, loc=(0, 0, bob), scl=(1 - 0.012 * s, 1 - 0.012 * s, 1 + 0.028 * s))
        idle_extras(idle, f, t)
        wing_flap(idle, f, t, 24 if flier else 7, 2 if flier else 1)
    # ---------- Walk
    walk = ActionWriter(arm, 'Walk', loop_walk)
    for f in range(0, loop_walk + 1):
        t = f / loop_walk
        w = TAU * t
        if legs:
            walk.key(root, f, loc=(0, 0, 0.035 * h * (0.5 - 0.5 * math.cos(2 * w))),
                     rot=(Y, math.radians(3) * math.sin(w)))
        else:
            walk.key(root, f, loc=(0.02 * h * math.sin(w), 0, 0.05 * h * (0.5 - 0.5 * math.cos(2 * w))),
                     rot=(Y, math.radians(7) * math.sin(w)))
        for n in legs:
            walk.key(n, f, rot=(X, math.radians(28) * math.sin(w + phases[n])))
        for n in arms:
            walk.key(n, f, rot=(X, math.radians(18) * math.sin(w + aph[n])))
        for n in tails:
            walk.key(n, f, rot=(Y, math.radians(14) * math.sin(w)))
        for n in heads:
            walk.key(n, f, rot=(X, math.radians(3) * math.sin(2 * w)))
        wing_flap(walk, f, t, 28, 2)

    # ---------- Attack (one-shot): anticipation, lunge toward the foe (-Y), recoil, settle
    atk = ActionWriter(arm, 'Attack', attack_len)
    poses = [  # frame, forward (fraction of h), squash xy, z, lean (deg, + = forward)
        (0, 0.0, 1.0, 1.0, 0),
        (4, -0.08, 1.08, 0.88, -8),
        (8, 0.34, 0.92, 1.12, 14),
        (11, 0.26, 1.04, 0.97, 10),
        (14, 0.06, 1.0, 1.02, 2),
        (attack_len, 0.0, 1.0, 1.0, 0),
    ]
    for f, fwd, sxy, sz, lean in poses:
        atk.key(root, f, loc=(0, -fwd * h, 0.04 * h * max(0.0, fwd) / 0.34), scl=(sxy, sxy, sz),
                rot=(X, math.radians(lean)))
        k = max(0.0, fwd) / 0.34
        for n in heads:
            atk.key(n, f, loc=(0, -0.06 * h * k, 0), rot=(X, math.radians(10) * k))
        for n in arms:
            atk.key(n, f, rot=(X, -math.radians(50) * k))
        for n in tails:
            atk.key(n, f, rot=(Y, math.radians(-18) * k))
        for n in wings:
            atk.key(n, f, rot=(Y, -side(n) * math.radians(35) * (k - 0.4)))
    # ---------- Hurt (one-shot): knocked back (+Y) with a shudder, then recover
    hurt_len = 15
    hurt = ActionWriter(arm, 'Hurt', hurt_len)
    for f in range(0, hurt_len + 1):
        t = f / hurt_len
        env = math.sin(math.pi * min(1.0, t * 1.25)) if t < 0.8 else 0.0
        shake = math.sin(t * TAU * 4) * (1 - t)
        hurt.key(root, f, loc=(0.03 * h * shake, 0.12 * h * env, 0), rot=(X, -math.radians(12) * env),
                 scl=(1 + 0.05 * env, 1 + 0.05 * env, 1 - 0.07 * env))
        for n in heads:
            hurt.key(n, f, rot=(X, -math.radians(10) * env))
        for n in arms + wings:
            hurt.key(n, f, rot=(Y, side(n) * math.radians(20) * env))
    # ---------- Faint (one-shot, holds last frame): a weak hop, then crumple down and sink
    faint_len = 30
    faint = ActionWriter(arm, 'Faint', faint_len)
    for f in range(0, faint_len + 1):
        t = f / faint_len
        hop = 0.06 * h * math.sin(math.pi * min(1.0, t / 0.25)) if t < 0.25 else 0.0
        d = max(0.0, (t - 0.25) / 0.75)
        d = d * d
        faint.key(root, f, loc=(0, 0.05 * h * d, hop - 0.35 * h * d), rot=(Y, math.radians(-20) * d),
                  scl=(1 + 0.12 * d, 1 + 0.12 * d, max(0.05, 1 - 0.7 * d)))
        for n in heads:
            faint.key(n, f, rot=(X, math.radians(25) * d))
        for n in arms + wings + ears + tails:
            faint.key(n, f, rot=(Y, -side(n) * math.radians(25) * d))
    # ---------- Special (one-shot): hop + full spin, e.g. status / stat moves
    sp_len = 30
    spec = ActionWriter(arm, 'Special', sp_len)
    for f in range(0, sp_len + 1):
        t = f / sp_len
        e = 0.5 - 0.5 * math.cos(math.pi * t)
        spec.key(root, f, loc=(0, 0, 0.18 * h * math.sin(math.pi * t)), rot=(Z, TAU * e * 0.999))
        wing_flap(spec, f, t, 30, 3)
    acts = [idle.write(all_bones), walk.write(all_bones), atk.write(all_bones), hurt.write(all_bones),
            faint.write(all_bones), spec.write(all_bones)]
    stash_actions(arm, acts)
    return acts

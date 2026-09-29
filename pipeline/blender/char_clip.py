"""Automated clipping test for the generated characters.

For every character it poses the skinned mesh (Blender's own armature deformation, the same linear-blend skinning
glTF / Godot use) at rest and at several frames of all 19 clips and counts vertices that poke through something:

  cloth_in_body  outfit / hair / hat / shoe vertices that end up INSIDE the (full, unclipped) body
  skin_poke      body vertices hidden under clothing that come out OUTSIDE the cloth
  limb_vs_rest   vertices of an arm / leg (skin or cloth) that go inside the trunk or another limb (only vertices that were
                 clear of it at rest, so the welded joints and cloth seams do not count)

A vertex counts once per category however many frames it penetrates; the depth is the worst over all frames, in mm at the
nominal 1.5 m height.  Depths below TOL_MM are contact, not clipping.

  python3 pipeline/blender/char_clip.py --only blue,brock [--frames 4] [--max 0]     (CI-style: exits 1 above --max)
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TOL_MM = 6.0
HAIR_TOL_MM = 16.0
SKIP_PREFIX = ('eye_', 'brow', 'lip_', 'mouthline')
SKIP_SUFFIX = ('_lid', '_lash', '_liner')

GROUP_BONES = {
    'armL': ('upper_arm_L', 'forearm_L', 'hand_L'), 'armR': ('upper_arm_R', 'forearm_R', 'hand_R'),
    'legL': ('thigh_L', 'shin_L', 'foot_L'), 'legR': ('thigh_R', 'shin_R', 'foot_R'),
}


def _eval_positions(obj, dg):
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3).astype(np.float64)


def _signed(tree, pts, idx=None):
    """Signed distance (>0 outside) of points to a closed surface via the nearest face normal."""
    from mathutils import Vector
    out = np.zeros(len(pts))
    dist = np.zeros(len(pts))
    for k, p in enumerate(pts):
        l, n, ix, d = tree.find_nearest(Vector((float(p[0]), float(p[1]), float(p[2]))))
        if l is None:
            out[k] = 1e9
            continue
        s = (p[0] - l.x) * n.x + (p[1] - l.y) * n.y + (p[2] - l.z) * n.z
        out[k] = s
        dist[k] = d
    return out, dist


def _bvh(V, F):
    from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons([tuple(map(float, v)) for v in V], [tuple(int(i) for i in f) for f in F], epsilon=0.0)


def run(ctx, obj, arm, acts, names, K, frames=4, log=print, clips=None):
    import bpy
    import char_geo as G
    import char_mesh as M
    B = ctx.body
    bone_index = {n: i for i, n in enumerate(names)}
    sc = bpy.context.scene
    # ---- reference body (full, unclipped) skinned to the same armature
    ref_part = G.Part('ref', B.V * K, B.F, 'skin')
    ref_part.w = dict(B.w)
    Jr, Wr = G.finalize_weights(ref_part, bone_index)
    me = M.to_bpy_mesh('ref_body', B.V * K, B.F)
    ref = bpy.data.objects.new('ref_body', me)
    sc.collection.objects.link(ref)
    vgs = [ref.vertex_groups.new(name=n) for n in names]
    for k in range(4):
        for v in range(len(B.V)):
            if Wr[v, k] > 0:
                vgs[Jr[v, k]].add([v], float(Wr[v, k]), 'ADD')
    ref.parent = arm
    md = ref.modifiers.new('Armature', 'ARMATURE')
    md.object = arm
    ref.hide_render = True

    # ---- exported mesh bookkeeping
    ranges = ctx.part_ranges
    nv = sum(e - s for _, s, e in ranges)
    Vexp_rest = None
    part_of = np.empty(nv, object)
    for nm, s, e in ranges:
        part_of[s:e] = nm
    F = np.array([tuple(int(i) for i in p.vertices) for p in obj.data.polygons])
    is_patch = np.array([nm.startswith(SKIP_PREFIX) or nm.endswith(SKIP_SUFFIX) for nm in part_of])
    is_skin = np.array([nm == 'body' for nm in part_of])
    is_cloth = ~is_patch & ~is_skin
    # dominant group of every exported vertex (from the mesh's vertex groups) -> arm / leg / trunk
    grp = _groups_from_mesh(obj, names)
    covered = np.where(ctx.covered)[0]
    # body vertex groups
    gref = _groups_from_weights(B.w, len(B.V))

    dg0 = bpy.context.evaluated_depsgraph_get()
    ad = arm.animation_data
    ad.use_nla = False           # the stashed NLA tracks would otherwise pose the "rest" evaluation
    ad.action = None
    arm.data.pose_position = 'REST'
    sc.frame_set(0)
    dg0.update()
    rest_exp = _eval_positions(obj, dg0)
    rest_ref = _eval_positions(ref, dg0)
    arm.data.pose_position = 'POSE'

    # rest-pose clearance to other limbs: only vertices that were clear of the other groups count for limb_vs_rest
    arm.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    bm0 = _deform_matrices(arm, names)
    arm.data.pose_position = 'POSE'
    clear_exp_t, clear_ref_t = {}, {}
    for tag in VICTIMS:
        de = _tag_dist_posed(B.field, arm, bm0, tag, rest_exp, K)
        dr = _tag_dist_posed(B.field, arm, bm0, tag, rest_ref, K)
        clear_exp_t[tag] = de > 0.3
        clear_ref_t[tag] = dr > 0.3

    hairish = np.array([str(nm).startswith(('hair', 'tuft', 'fringe', 'temple', 'side_lock', 'twin', 'strand', 'mohawk', 'loop', 'bun', 'tie', 'beard', 'moustache', 'cap', 'visor',
                                            'beanie', 'crown', 'brim', 'band', 'sailor', 'chef', 'nurse', 'logo', 'headband')) for nm in part_of])
    garment = is_cloth & ~hairish
    cl_faces = F[garment[F[:, 0]] & garment[F[:, 1]] & garment[F[:, 2]]]
    # vertices next to the limb's own root joint deform with the joint (armpit / groin candy-wrapper): not counted
    joint_rest = {}
    for sd, sfx in ((1, 'L'), (-1, 'R')):
        j = ctx.P.joints(sd)
        joint_rest['arm' + sfx] = j['shoulder'] * K
        joint_rest['leg' + sfx] = j['hip'] * K
    near_root_exp = np.zeros(nv, bool)
    near_root_ref = np.zeros(len(B.V), bool)
    for g, jp in joint_rest.items():
        near_root_exp |= (grp == g) & (np.linalg.norm(rest_exp - jp, axis=1) < ROOT_RADIUS * K)
        near_root_ref |= (gref == g) & (np.linalg.norm(rest_ref - jp, axis=1) < ROOT_RADIUS * K)
    for tag in VICTIMS:
        clear_exp_t[tag] &= ~near_root_exp
        clear_ref_t[tag] &= ~near_root_ref
        root = joint_rest.get({'upper_arm_L': 'armL', 'upper_arm_R': 'armR', 'thigh_L': 'legL', 'thigh_R': 'legR'}.get(tag, ''))
        if root is not None:          # the other side's vertices next to this limb's root joint belong to the joint blend as well
            clear_exp_t[tag] &= np.linalg.norm(rest_exp - root, axis=1) > ROOT_RADIUS * K
            clear_ref_t[tag] &= np.linalg.norm(rest_ref - root, axis=1) > ROOT_RADIUS * K
    tol = TOL_MM / 1000.0
    flagged = {'cloth_in_body': {}, 'skin_poke': {}, 'limb_vs_rest': {}}
    worst = {k: 0.0 for k in flagged}
    culprit = {k: {} for k in flagged}
    where = {}
    debug = ctx.clip_debug = []
    cib = ctx.clip_cib = []

    def check(label, pos_exp, pos_ref):
        ref_tree = _bvh(pos_ref, B.F)
        # 1. cloth inside the body
        ci = np.where(is_cloth)[0]
        s, d = _signed(ref_tree, pos_exp[ci])
        tolv = np.where(hairish[ci], HAIR_TOL_MM / 1000.0, tol)      # hair / beard roots are embedded in the scalp on purpose
        bad = (s < -tolv) & (d < 0.6 * K * 4)
        for v, depth in zip(ci[bad], -s[bad]):
            cib.append((label, part_of[v], rest_exp[v] / K, depth))
            flagged['cloth_in_body'][v] = max(flagged['cloth_in_body'].get(v, 0.0), depth)
            culprit['cloth_in_body'][part_of[v]] = culprit['cloth_in_body'].get(part_of[v], 0) + 1
        # 2. covered skin poking out of the cloth
        if len(covered):
            if len(cl_faces):
                ct = _bvh(pos_exp, cl_faces)
                s2, d2 = _signed(ct, pos_ref[covered])
                bad2 = (s2 > tol + 0.003) & (d2 < 0.35 * K * 4)
                for v, depth in zip(covered[bad2], s2[bad2]):
                    flagged['skin_poke'][v] = max(flagged['skin_poke'].get(v, 0.0), depth)
        # 3. limbs / trunk / head against each other, measured in the rest space of the victim's bone with the anatomy field
        bm = _deform_matrices(arm, names)
        for tag in VICTIMS:
            for label_, pos, gr, clear, cloth_mask in (('skin', pos_ref, gref, clear_ref_t[tag], None), ('exp', pos_exp, grp, clear_exp_t[tag], is_cloth)):
                cand = np.where((gr != tag_group(tag)) & clear)[0]
                if label_ == 'exp':
                    cand = cand[~is_patch[cand]]
                if len(cand) == 0:
                    continue
                d = _tag_dist_posed(B.field, arm, bm, tag, pos[cand], K)
                layer = LAYER_ROWS if (label_ == 'exp' and is_cloth[cand].any()) else 0.0
                thr = np.where(is_cloth[cand], LAYER_ROWS, 0.0) if label_ == 'exp' else 0.0
                bad3 = d < (thr - tol / K)
                if bad3.any():
                    debug.append((label, tag, label_, pos[cand[bad3]].copy(), pos_ref.copy() if label_ == 'skin' else pos_exp.copy()))
                for v, dd in zip(cand[bad3], d[bad3]):
                    key = (label_, v)
                    depth = (float(np.asarray(thr)[list(cand).index(v)] if label_ == 'exp' else 0.0) - dd) * K
                    flagged['limb_vs_rest'][key] = max(flagged['limb_vs_rest'].get(key, 0.0), depth)
                    nm = (part_of[v] if label_ == 'exp' else 'body') + '>' + tag
                    culprit['limb_vs_rest'][nm] = culprit['limb_vs_rest'].get(nm, 0) + 1
                    where['%s %s' % (label, nm)] = where.get('%s %s' % (label, nm), 0) + 1

    check('rest', rest_exp, rest_ref)
    rest_counts = {k: len(v) for k, v in flagged.items()}
    rest_flagged = {k: dict(v) for k, v in flagged.items()}
    per_clip = {}
    for act in acts:
        if (clips and act.name not in clips) or (not clips and act.name == 'Surf'):     # Surf (seated) is not one of the 19 gameplay clips
            continue
        arm.animation_data.action = act
        f0, f1 = act.frame_range
        fr = sorted(set(int(round(x)) for x in np.linspace(f0, f1, frames + 1)[:-1]))
        before = {k: len(v) for k, v in flagged.items()}
        for f in fr:
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            check('%s@%d' % (act.name, f), _eval_positions(obj, dg), _eval_positions(ref, dg))
        per_clip[act.name] = {k: len(v) - before[k] for k, v in flagged.items()}
    arm.animation_data.action = None
    bpy.data.objects.remove(ref)
    out = {
        'rest': rest_counts,
        'animated': {k: len(v) for k, v in flagged.items()},
        'worst_mm': {k: round(max(v.values()) * 1000.0 / 1.0, 1) if v else 0.0 for k, v in flagged.items()},
        'total': int(sum(len(v) for v in flagged.values())),
        'per_clip_new': {c: v for c, v in per_clip.items() if sum(v.values())},
        'where': dict(sorted(where.items(), key=lambda kv: -kv[1])[:14]),
        'culprits': {k: dict(sorted(v.items(), key=lambda kv: -kv[1])[:6]) for k, v in culprit.items() if v},
    }
    return out


VICTIMS = ['trunk', 'upper_arm_L', 'forearm_L', 'hand_L', 'upper_arm_R', 'forearm_R', 'hand_R', 'thigh_L', 'shin_L', 'thigh_R', 'shin_R', 'head']
ROOT_RADIUS = 1.9       # rows round the shoulder / hip joint where linear-blend skinning inevitably folds
LAYER_ROWS = 0.0       # cloth only has to stay outside the other limb's skin (cloth layers may touch)
TRUNK_BONES = ('hips', 'spine', 'chest')


def tag_group(tag):
    return 'trunk' if tag in ('trunk', 'neck', 'head') or tag.startswith('clavicle') else {
        'upper_arm_L': 'armL', 'forearm_L': 'armL', 'hand_L': 'armL', 'upper_arm_R': 'armR', 'forearm_R': 'armR', 'hand_R': 'armR',
        'thigh_L': 'legL', 'shin_L': 'legL', 'foot_L': 'legL', 'thigh_R': 'legR', 'shin_R': 'legR', 'foot_R': 'legR'}[tag]


def _deform_matrices(arm, names):
    """rest -> pose matrix of every bone in armature space (numpy 4x4)."""
    out = {}
    for pb in arm.pose.bones:
        M = pb.matrix @ arm.data.bones[pb.name].matrix_local.inverted()
        out[pb.name] = np.array(M)
    return out


def _tag_dist_posed(field, arm, bm, tag, pts_m, K):
    """Distance (rows) of posed points (metres) to the tag's anatomy, evaluated in the bone's rest frame.  The trunk is one
    stack of primitives skinned to hips / spine / chest, so its points use the chest bone above the waist and the hips below."""
    if tag == 'trunk':
        out = np.full(len(pts_m), 9.0)
        zsplit = np.median(pts_m[:, 2]) * 0 + arm.pose.bones['spine'].head[2]
        for bone, sel in (('chest', pts_m[:, 2] >= zsplit), ('hips', pts_m[:, 2] < zsplit)):
            if sel.any():
                Mi = np.linalg.inv(bm[bone])
                p = np.c_[pts_m[sel], np.ones(sel.sum())] @ Mi.T
                out[sel] = field.tag_dist(p[:, :3] / K, tag)
        return out
    Mi = np.linalg.inv(bm[tag])
    p = np.c_[pts_m, np.ones(len(pts_m))] @ Mi.T
    return field.tag_dist(p[:, :3] / K, tag)


def _groups_from_weights(w, n):
    dom = np.full(n, 'trunk', object)
    tot = {g: sum((w.get(b, 0) for b in bs), np.zeros(n)) for g, bs in GROUP_BONES.items()}
    best = np.zeros(n)
    for g, a in tot.items():
        m = a > np.maximum(best, 0.5)
        dom[m] = g
        best = np.where(m, a, best)
    return dom


def _groups_from_mesh(obj, names):
    n = len(obj.data.vertices)
    idx = {g.index: g.name for g in obj.vertex_groups}
    w = {}
    for v in obj.data.vertices:
        for g in v.groups:
            w.setdefault(idx[g.group], np.zeros(n))[v.index] += g.weight
    return _groups_from_weights(w, n)


def _group_trees(V, F, grp):
    """BVH per group of the faces whose three vertices all belong to that group."""
    trees = {}
    for g in ('trunk', 'armL', 'armR', 'legL', 'legR'):
        m = (grp[F[:, 0]] == g) & (grp[F[:, 1]] == g) & (grp[F[:, 2]] == g)
        trees[g] = _bvh(V, F[m]) if m.sum() >= 4 else None
    return trees


def _rest_clear(V, grp, trees, min_dist):
    from mathutils import Vector
    clear = np.ones(len(V), bool)
    for i, p in enumerate(V):
        g = grp[i]
        if g == 'trunk':
            continue
        for og, t in trees.items():
            if og == g or t is None:
                continue
            l, n, ix, d = t.find_nearest(Vector((float(p[0]), float(p[1]), float(p[2]))))
            if l is not None and d < min_dist:
                clear[i] = False
                break
    return clear


# ----------------------------------------------------------------------------- CLI
def test_one(key, d, looks, frames, tmp):
    import time
    import char_build as CB
    import char_asm as AS
    t0 = time.time()
    look = CB.resolve_look(key, d, looks)
    ctx = CB.build(key, d, look)
    holder = {}

    def hook(obj, arm, acts, names, K):
        holder['r'] = run(ctx, obj, arm, acts, names, K, frames=frames, log=print)
    ctx.clip_test = hook
    AS.build_and_export(ctx, None, tmp_dir=tmp, log=print, dry=True)
    r = holder['r']
    r['seconds'] = round(time.time() - t0, 1)
    return r


def main():
    import subprocess
    import gen_characters as GC
    args = sys.argv[1:]
    only = args[args.index('--only') + 1].split(',') if '--only' in args else None
    frames = int(args[args.index('--frames') + 1]) if '--frames' in args else 4
    limit = int(args[args.index('--max') + 1]) if '--max' in args else None
    out_json = args[args.index('--json') + 1] if '--json' in args else None
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 1
    part_out = args[args.index('--part-out') + 1] if '--part-out' in args else None
    tmp = os.environ.get('TMPDIR', '/tmp')
    cast = json.load(open(os.path.join(GC.EXTRACTED, 'cast.json')))['cast']
    looks = GC.load_looks().get('characters', {})
    keys = GC.sprite_keys(cast, only)
    results = {}
    if jobs > 1 and len(keys) > 1:
        procs = []
        for i in range(jobs):
            part = keys[i::jobs]
            if part:
                out = os.path.join(tmp, 'char_clip_%d.json' % i)
                procs.append((subprocess.Popen([sys.executable, os.path.abspath(__file__), '--only', ','.join(part), '--frames', str(frames), '--part-out', out]), out))
        for p, _ in procs:
            p.wait()
        for _, out in procs:
            results.update(json.load(open(out)))
    else:
        for key in keys:
            r = test_one(key, cast[key], looks, frames, tmp)
            results[key] = r
            print('%-18s rest=%s anim=%s worst_mm=%s total=%d  (%.0fs)' % (key, r['rest'], r['animated'], r['worst_mm'], r['total'], r['seconds']), flush=True)
            if r['culprits']:
                print('    culprits:', r['culprits'])
            if '--where' in args:
                print('    where:', r['where'])
            if r['per_clip_new'] and '--verbose' in args:
                print('    per clip (new offenders):', r['per_clip_new'])
    if part_out:
        json.dump(results, open(part_out, 'w'))
        return
    worst_total = max((r['total'] for r in results.values()), default=0)
    static_total = sum(sum(r['rest'].values()) for r in results.values())
    print('SUMMARY characters=%d static_penetrations=%d animated: total=%d worst_character=%d' % (
        len(results), static_total, sum(r['total'] for r in results.values()), worst_total))
    if out_json:
        budget = int(args[args.index('--budget') + 1]) if '--budget' in args else 60
        for r in results.values():
            r.pop('where', None)
        with open(out_json, 'w') as fh:
            json.dump({'tolerance_mm': TOL_MM, 'frames_per_clip': frames, 'clips': '19 gameplay clips (Surf excluded)',
                       'root_exclusion_rows': ROOT_RADIUS, 'budget': {'animated_per_character': budget}, 'characters': results}, fh, indent=1)
    if limit is not None and worst_total > limit:
        print('FAIL: penetration count %d > %d' % (worst_total, limit))
        sys.exit(1)


if __name__ == '__main__':
    main()

"""Pokémon models: public glTF -> rigged, animated, Godot-ready glb (headless Blender).

The meshes come from the openly published `Pokemon-3D-api/assets` repository
(https://github.com/Pokemon-3D-api/assets, MIT; models/opt/regular/<dex>.glb, Draco + WebP).
Those files are a mixed bag - some carry a Sketchfab skeleton with one clip, most are
static - and Godot cannot read Draco, so this script takes only the *mesh + textures*
and does the rest itself:

  1. import (Blender decodes Draco), bake the rest pose, drop helper meshes, join
  2. normalise: feet on the ground, centred, facing +Z (glTF), sized to the Pokédex height,
     decimated to a triangle budget, textures capped at 512 px
  3. rig: a species-specific skeleton (pokemon_rig.py: trunk + a chain per limb/ear/tail/wing/tentacle found on the
     mesh; bone count and names differ per species, table in pipeline/data/pokemon_species_rig.json), radius-aware
     smooth weights, and a corrective natural rest pose baked into the mesh (pokemon_skin.py) so nothing is T-posed
  4. animate: the 18 clips the game plays (Idle Walk Run Attack Special Hurt Faint Victory Sleep Roar Dodge Spin Hop
     Charge Taunt Spawn Hover Talk), 3 idle variants and 6-10 signature clips per species named after its own moves,
     all authored from the species' rig/body plan/mass/tempo (pokemon_clips.py, pokemon_arch.py, pokemon_anim.py)
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
import pokemon_mesh_fix   # noqa: E402  (mesh/eye branch hook)

TRI_BUDGET = 14000
TEX_MAX = 512
FPS = 30

# the 18 clips every species carries (the names the game plays); pokemon_clips.py adds idle variants and
# 6-10 signature clips named after each species' own moves
CLIPS = ['Idle', 'Walk', 'Run', 'Attack', 'Special', 'Hurt', 'Faint', 'Victory', 'Sleep', 'Roar',
         'Dodge', 'Spin', 'Hop', 'Charge', 'Taunt', 'Spawn', 'Hover', 'Talk']
LOOPING = ['Idle', 'Walk', 'Run', 'Sleep', 'Charge', 'Taunt', 'Hover', 'Talk']
IDLE_VARIANTS = ['IdleLook', 'IdleStretch', 'IdleFidget']


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
    eyes_rec = pokemon_mesh_fix.cleanup(sid, obj, ov)   # mesh/eye branch hook (before normalising)
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

    # >>> pokemon_mesh_fix hook (owned by the mesh/eye branch): materials, stray pieces, eyes
    eyes_rec = pokemon_mesh_fix.prepare(sid, obj, ov, eyes_rec)
    me = obj.data
    # <<< pokemon_mesh_fix hook
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    V = co.reshape(-1, 3)

    # -- 3+4. rig + animate: species-specific skeleton, natural rest pose, 24+ authored clips (pokemon_build.py) ---------
    import pokemon_build as PB
    tri = np.array([t.vertices[:] for t in (me.calc_loop_triangles() or me.loop_triangles)], dtype=np.int32)
    rg = PB.prepare(sid, V, tri)
    arm = PB.bake(rg, obj, C, out_path)
    C.export_glb(out_path, export_image_format='JPEG', export_jpeg_quality=88, export_frame_step=2)
    import pokemon_glb
    pokemon_glb.prune(out_path)
    H = float(V[:, 2].max())
    pokemon_mesh_fix.dump_record(os.path.dirname(out_path), sid, eyes_rec)   # mesh/eye branch hook
    return {'height_m': round(H, 3), 'tris': int(tris), 'bones': len(rg.sk.bones), 'plan': rg.spec['plan'],
            'animations': list(rg.catalog), 'signature': [k for k, c in rg.catalog.items() if c.kind == 'signature'],
            'bone_names': list(rg.sk.bones), 'tpose_fixed': sorted(rg.fixed), 'bytes': os.path.getsize(out_path)}


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
        pokemon_mesh_fix.write_index(a.out, todo_ids)   # mesh/eye branch hook


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
               'bones': info['bones'], 'file': sid + '.glb', 'bytes': info['bytes'], 'status': 'generated',
               'plan': info['plan'], 'signature': info['signature'], 'clips': len(info['animations']),
               'idle_variants': IDLE_VARIANTS}
        species[sid] = rec
        os.remove(p)
    man = {'generated': sorted(species), 'species': species, 'animations': CLIPS, 'looping': LOOPING, 'idle_variants': IDLE_VARIANTS,
           'source': 'Pokemon-3D-api/assets models/opt/regular (MIT), rigged + animated by gen_rigged_pokemon.py'}
    with open(mp, 'w') as fh:
        json.dump(man, fh, indent=1)


if __name__ == '__main__':
    main()

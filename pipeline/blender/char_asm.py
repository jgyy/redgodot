"""Turn a finished Ctx (parts + atlas + rig) into a skinned, textured, animated .glb via bpy."""
import os
import time

import numpy as np

import bpy
import common as C
import char_geo as G
import char_rig as R
import char_anim as A

FPS = 60
UNIT = 1.5 / 24.0      # model units (sprite rows) -> metres


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    return sc


def assemble_mesh(ctx, bones):
    """Concatenate parts -> arrays: V, F, N, UV, J (n,4), W (n,4), plus per-vertex AO."""
    bone_index = {b[0]: i for i, b in enumerate(bones)}
    ctx.atlas._pack()
    Vs, Fs, Ns, Js, Ws, gs, cells, uvs, gains, consts = [], [], [], [], [], [], [], [], [], []
    off = 0
    ctx.part_ranges = []
    for p in ctx.parts:
        if len(p.V) == 0 or len(p.F) == 0:
            continue
        ctx.part_ranges.append((p.name, off, off + len(p.V)))
        N = p.N if p.N is not None else G.vertex_normals(p.V, p.F)
        J, W = G.finalize_weights(p, bone_index)
        Vs.append(p.V)
        Fs.append(p.F + off)
        Ns.append(N)
        Js.append(J)
        Ws.append(W)
        gs.append(p.g)
        cells.extend([p.cell] * len(p.V))
        uvs.append(p.uv if p.uv is not None else np.zeros((len(p.V), 2)))
        gains.append(np.full(len(p.V), p.ao_gain))
        consts.append(np.full(len(p.V), np.nan if p.ao_const is None else p.ao_const))
        off += len(p.V)
    V = np.vstack(Vs)
    F = np.vstack(Fs)
    N = np.vstack(Ns)
    J = np.vstack(Js)
    W = np.vstack(Ws)
    g = np.concatenate(gs)
    gain = np.concatenate(gains)
    uv_d = np.vstack(uvs)
    ao = G.bake_ao(V, F, N, samples=18, max_dist=1.7, extra=getattr(ctx, 'ao_extra', None))
    ao = 1.0 - (1.0 - ao) * gain
    const = np.concatenate(consts)
    ao = np.where(np.isnan(const), ao, const)
    UV = np.zeros((len(V), 2))
    cells = np.array(cells)
    for name in np.unique(cells):
        m = cells == name
        UV[m] = ctx.atlas.uv(name, ao=ao[m], g=g[m], uv=uv_d[m])
    return V, F, N, UV, J, W, ao


def export_glb(path, anims=True):
    C.ensure_dir(os.path.dirname(path))
    kw = dict(filepath=path, export_format='GLB', check_existing=False, use_selection=False, export_apply=False,
              export_yup=True, export_materials='EXPORT', export_animations=anims, export_skins=True)
    if anims:
        kw.update(export_animation_mode='ACTIONS', export_force_sampling=FORCE_SAMPLING, export_reset_pose_bones=True,
                  export_anim_slide_to_zero=True, export_optimize_animation_size=True)
    bpy.ops.export_scene.gltf(**kw)


FORCE_SAMPLING = os.environ.get('CHAR_FORCE_SAMPLING', '1') == '1'


def build_and_export(ctx, out_path, hair_hint=None, tmp_dir='/tmp', log=None, dry=False, white_material=False, anims=True):
    t0 = time.time()
    reset_scene()
    P = ctx.P
    bones = R.skeleton(P, ctx.extra_bones)
    V, F, N, UV, J, W, ao = assemble_mesh(ctx, bones)
    K = UNIT
    V = V * K
    bones = [(n_, p_, tuple(np.array(h_) * K), tuple(np.array(t_) * K)) for n_, p_, h_, t_ in bones]
    # ---- texture
    mat = bpy.data.materials.new('mat_atlas')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    if white_material:          # modular player parts: the recolourable atlas ships as a separate RGBA png
        bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)
    else:
        png = os.path.join(tmp_dir, '%s_atlas.png' % ctx.key)
        ctx.atlas.save(png)
        img = bpy.data.images.load(png)
        img.pack()
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.interpolation = 'Linear'
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.05
    # ---- mesh
    me = bpy.data.meshes.new(ctx.key)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.update()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', UV[F.reshape(-1)].reshape(-1).astype(np.float32))
    try:
        me.normals_split_custom_set_from_vertices([tuple(map(float, n)) for n in N])
    except Exception as e:      # older API: fall back to auto normals
        if log:
            log('custom normals failed: %s' % e)
    me.materials.append(mat)
    obj = bpy.data.objects.new(ctx.key, me)
    bpy.context.scene.collection.objects.link(obj)
    # ---- armature + skin
    arm = R.build_armature(ctx.key, bones)
    names = [b[0] for b in bones]
    vgs = [obj.vertex_groups.new(name=nm) for nm in names]
    for bi in range(len(names)):
        sel = np.where((J == bi) & (W > 0))
        if len(sel[0]) == 0:
            continue
        vs, ks = sel
        for v, k in zip(vs.tolist(), ks.tolist()):
            vgs[bi].add([v], float(W[v, k]), 'ADD')
    obj.parent = arm
    mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    # ---- animation
    hair = ctx.anim_hints
    clips = A.build_all(P, hair)
    acts = A.write_actions(arm, clips, names, unit=K)
    if anims or getattr(ctx, 'clip_test', None):
        C.stash_actions(arm, acts)
    if getattr(ctx, 'clip_test', None):
        ctx.clip_test(obj, arm, acts, names, K)
    if dry:
        return {}
    export_glb(out_path, anims=anims)
    info = {'verts': len(V), 'tris': len(F), 'bytes': os.path.getsize(out_path), 'bones': len(names),
            'clips': {c.name: {'frames': c.n, 'seconds': round(c.n / float(FPS), 4)} for c in clips},
            'seconds': round(time.time() - t0, 1)}
    return info

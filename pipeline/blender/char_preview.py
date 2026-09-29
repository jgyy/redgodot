"""Quick look-dev renders of the generated geometry (Blender Cycles on the CPU, no GPU / display needed).

  import char_preview as PV
  PV.render(items, '/tmp/x.png', views=[(0, 8), (90, 8), (180, 8)], size=360)
  PV.render(items, '/tmp/head.png', views=[(0, 0), (35, 5), (90, 0)], size=420, focus=(0, 0, 21.5), span=5.0)

items: list of (V, F, colors) with colors either an (n,3) per-vertex array (linear 0..1) or one rgb triple;
optionally a 4th element N (n,3) of smooth vertex normals.  The truth is the Godot render; this only gives
fast, honest shape feedback while iterating on the generators.
"""
import math

import numpy as np


def _mesh_obj(name, V, F, col, N=None):
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.update()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if N is not None:
        try:
            me.normals_split_custom_set_from_vertices([tuple(map(float, n)) for n in N])
        except Exception:
            pass
    col = np.asarray(col, float)
    at = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    cc = np.tile(col, (len(V), 1)) if col.ndim == 1 else col
    rgba = np.concatenate([cc, np.ones((len(V), 1))], 1)
    at.data.foreach_set('color', rgba.astype(np.float32).reshape(-1))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    vc = nt.nodes.new('ShaderNodeVertexColor')
    vc.layer_name = 'Col'
    nt.links.new(vc.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.75
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    me.materials.append(mat)
    return ob


def render(items, path, views=((0, 8), (90, 8), (180, 8)), size=360, focus=None, span=None, samples=12, bg=(0.87, 0.91, 0.95)):
    import bpy
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes['Background']
    bgn.inputs['Color'].default_value = (bg[0], bg[1], bg[2], 1)
    bgn.inputs['Strength'].default_value = 0.85
    sc.view_settings.view_transform = 'Standard'
    objs = [_mesh_obj('m%d' % i, it[0], it[1], it[2], it[3] if len(it) > 3 else None) for i, it in enumerate(items)]
    allv = np.vstack([it[0] for it in items])
    lo, hi = allv.min(0), allv.max(0)
    c = (lo + hi) / 2 if focus is None else np.asarray(focus, float)
    sp = max(hi[2] - lo[2], hi[0] - lo[0]) * 1.06 if span is None else span
    cam_d = bpy.data.cameras.new('cam')
    cam_d.type = 'ORTHO'
    cam_d.ortho_scale = sp
    cam = bpy.data.objects.new('cam', cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy = 2.6
    sun.angle = math.radians(25)
    so = bpy.data.objects.new('sun', sun)
    sc.collection.objects.link(so)
    tiles = []
    import tempfile
    import os
    from PIL import Image
    for yaw, pitch in views:
        # camera orbits the figure: yaw 0 = looking at the front (figure faces -Y so the camera sits at -Y)
        yy, pp = math.radians(yaw), math.radians(pitch)
        d = 60.0
        pos = Vector(c.tolist()) + Vector((d * math.sin(yy) * math.cos(pp), -d * math.cos(yy) * math.cos(pp), d * math.sin(pp)))
        cam.location = pos
        look = (Vector(c) - pos).normalized()
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        # key light from the camera's upper left
        kd = Vector((math.sin(yy - 0.7) * 0.6, -math.cos(yy - 0.7) * 0.6, 0.75))
        so.rotation_euler = (-kd).to_track_quat('-Z', 'Y').to_euler()
        tmp = os.path.join(tempfile.gettempdir(), 'pv_%d.png' % os.getpid())
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        tiles.append(np.asarray(Image.open(tmp).convert('RGB')))
    Image.fromarray(np.hstack(tiles)).save(path)
    return path

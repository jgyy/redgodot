"""Low-poly prop builder shared by gen_tiles.py / gen_world.py / gen_battlebg.py (headless Blender, bmesh).

A `Prop` collects primitives (bevelled boxes, prisms, cylinders, lathes, jagged blobs, blades ...) into one bmesh and
paints every face from a material *ramp* (upstream's palette.js ramps, dark -> light) chosen by a Lambert term against
the same light the 2D art is drawn with (from the upper left / front), with soft ground-contact ambient occlusion
baked into the vertex colours. Two output styles from the same geometry:

  style 'vcol'  in-game props (godot/assets/models/world): vertex colour = ramp colour, vertex alpha = detail-tile id
                (0..10 -> overlaid by prop.gdshader from the env_detail atlas, 1.0 = none)
  style 'tex'   viewable kit (godot/assets/models/tiles): every material gets its seamless PBR-less texture from
                pipeline/data/env_tex (env_textures.py), vertex colour = grey lighting/AO factor

Units are "sprite units" (1 = one map cell = 16 px of 2D art, horizontally and vertically), pivot = bottom centre of the
prop's footprint, front (toward the camera) = Blender -Y = glTF/Godot +Z.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
import env_textures as ET  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# Lambert light in Blender space (x right, -y toward the camera, z up): from the upper left and the front
LIGHT = Vector((-0.5, -0.45, 0.74)).normalized()
AO_H = 0.22          # ground contact AO height
AO_K = 0.30          # ground contact AO strength


def hx(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def ramp_of(name):
    return [hx(c) for c in ET.PAL[name]]


def _r5(name):
    r = ET.PAL[name]
    if len(r) == 5:
        return [hx(c) for c in r]
    pick = [0, len(r) // 4, len(r) // 2, (3 * len(r)) // 4, len(r) - 1]
    return [hx(r[i]) for i in pick]


# name -> (ramp, texture, detail tile id). detail ids follow env_textures.DETAIL_TILES
MATS = {
    'wood': (_r5('wood'), 'wood', 7),
    'wood_dark': ([hx(c) for c in ('#2a1810', '#3e2418', '#54331f', '#6e4228', '#8e5a3a')], 'wood', 7),
    'paint': ([hx(c) for c in ('#7c7f98', '#a4a7be', '#cfd1de', '#eceaf2', '#ffffff')], None, 255),
    'cream': (_r5('cream'), 'plaster', 255),
    'leaf': (_r5('leaf'), 'turf', 0),
    'leaf_light': ([hx(c) for c in ('#1d5433', '#2a723a', '#3c9142', '#5bb04d', '#8bcf5f')], 'turf', 0),
    'moss': ([hx(c) for c in ('#173d2f', '#1f5634', '#2f7a3a', '#48a043', '#6cbf4c')], 'turf', 0),
    'grass': (_r5('grass'), 'turf', 0),
    'tallgrass': ([hx(c) for c in ('#1a4f33', '#26703a', '#389040', '#58b04a', '#86cf58')], 'turf', 255),
    'terracotta': ([hx(c) for c in ('#5e2c28', '#7c3a30', '#a24a36', '#c2643f', '#d98458')], None, 255),
    'stone': (_r5('stone'), 'stone', 3),
    'pave': (_r5('pave'), 'cobble', 3),
    'rock': ([hx(c) for c in ('#3a302e', '#54443a', '#786454', '#a08c78', '#c8b8a4')], 'cave', 4),
    'cliff': ([hx(c) for c in ('#3a302e', '#54443a', '#786454', '#a08c78', '#c8b8a4')], 'cave', 10),
    'metal': (_r5('metal'), 'metal', 255),
    'gold': ([hx(c) for c in ('#8a6a1c', '#b98f2a', '#e0b83a', '#f4d046', '#fff0a0')], None, 255),
    'bark': (_r5('trunk'), 'bark', 255),
    'soil': ([hx(c) for c in ('#2a1a12', '#3e2a1c', '#54382a', '#6b4d3a', '#8f6a48')], 'dirt', 1),
    'path': (_r5('path'), 'dirt', 1),
    'sand': (_r5('sand'), 'sand', 2),
    'brick': (_r5('brick'), 'brick', 255),
    'plaster': (_r5('cream'), 'plaster', 255),
    'roof_red': (_r5('roof_red'), 'shingle_red', 255),
    'roof_blue': (_r5('roof_blue'), 'shingle_blue', 255),
    'roof_brown': (_r5('roof_brown'), 'shingle_brown', 255),
    'glass': ([hx(c) for c in ('#1b3582', '#2552ad', '#3176d0', '#4d9be6', '#bde6ff')], None, 255),
    'water': (_r5('water'), 'water', 9),
    'foam': ([hx(c) for c in ('#7fc3f3', '#bde6ff', '#e6f6ff', '#f4fbff', '#ffffff')], None, 255),
    'red': ([hx(c) for c in ('#5c1c22', '#8f2a2c', '#bb4034', '#dc6244', '#f08a70')], None, 255),
    'blue': ([hx(c) for c in ('#1c2c58', '#2c4a90', '#3e6cc0', '#6a98de', '#9cc0f0')], None, 255),
    'yellow': ([hx(c) for c in ('#8a6a1c', '#c89a24', '#e8c040', '#f8dc60', '#fff0a8')], None, 255),
    'pink': ([hx(c) for c in ('#8a2a4a', '#c04070', '#e86090', '#f890b0', '#ffc0d4')], None, 255),
    'white': ([hx(c) for c in ('#9a9ab0', '#c0c0d4', '#dcdce8', '#f0f0f8', '#ffffff')], None, 255),
    'tower': (_r5('tower'), 'stone', 8),
    'boulder': ([hx(c) for c in ('#56463c', '#786454', '#a08c78', '#c8b8a4', '#e8dccc')], None, 255),
    'ball_red': ([hx(c) for c in ('#7a1c28', '#a82838', '#e04848', '#f06a5c', '#ff9a8a')], None, 255),
    'ball_white': ([hx(c) for c in ('#8c8ca8', '#c8c8d8', '#e6e6f0', '#f8f8f8', '#ffffff')], None, 255),
    'ball_ink': ([hx(c) for c in ('#0e0d1a', '#1b1a2e', '#262540', '#34335a', '#4a4a78')], None, 255),
    'dark': ([hx(c) for c in ('#0c0c14', '#181824', '#242434', '#343448', '#4a4a60')], None, 255),
    'screen': ([hx(c) for c in ('#0e3a2c', '#1a6a4a', '#2a9a68', '#5ad090', '#b8f8d0')], None, 255),
}


def lit_index(n, levels=5):
    lit = n.dot(LIGHT)
    if lit > 0.85:
        return levels - 1
    if lit > 0.52:
        return levels - 2
    if lit > 0.22:
        return levels - 3
    if lit > -0.18:
        return levels - 4
    return 0


class Prop:
    def __init__(self, name, style='vcol', seed=1):
        self.name = name
        self.style = style
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.color.new('Col')
        self.uv = self.bm.loops.layers.uv.new('UVMap') if style == 'tex' else None
        self.mat_names = []
        self.rnd = random.Random(seed)
        self.vcol_name = 'prop'     # material name of the single vertex-colour material (battle uses 'unlit_*')
        self.tex_scale = 2.0     # texture repeats per unit (0.5 unit / tile)

    # ---------------------------------------------------------------- painting
    def mi(self, mat):
        if self.style == 'vcol':
            mat = 'vcol'
        if mat not in self.mat_names:
            self.mat_names.append(mat)
        return self.mat_names.index(mat)

    def paint(self, faces, mat, ao=True, k=1.0, jitter=0.03, levels=5, flat_idx=None, dark_below=None, bias=0):
        """Colour faces from material `mat`. flat_idx forces a ramp index; dark_below=(z, amount) darkens loops under z."""
        ramp, tex, detail = MATS[mat]
        mi = self.mi(mat)
        for f in faces:
            if not f.is_valid:
                continue
            n = f.normal.copy()
            if n.length < 1e-6:
                f.normal_update()
                n = f.normal.copy()
            n.normalize()
            idx = flat_idx if flat_idx is not None else max(0, min(levels - 1, lit_index(n, levels) + bias))
            f.material_index = mi
            jit = 1.0 + (self.rnd.random() - 0.5) * 2 * jitter
            for loop in f.loops:
                p = loop.vert.co
                g = jit * k
                if ao and abs(n.z) < 0.85:
                    g *= 1.0 - AO_K * max(0.0, 1.0 - max(0.0, p.z) / AO_H)
                if dark_below is not None and p.z < dark_below[0]:
                    g *= 1.0 - dark_below[1] * (1.0 - max(0.0, p.z) / dark_below[0])
                if self.style == 'tex' and tex:
                    base = ramp[2]
                    lum = ramp[idx]
                    # grey lighting factor relative to the mid tone
                    s = (lum[0] * 0.3 + lum[1] * 0.59 + lum[2] * 0.11) / max(1e-3, base[0] * 0.3 + base[1] * 0.59 + base[2] * 0.11)
                    s = max(0.35, min(1.35, s)) * g
                    loop[self.col] = (min(1.0, s * 0.92), min(1.0, s * 0.92), min(1.0, s * 0.92), 1.0)
                else:
                    c = ramp[idx]
                    a = 1.0 if self.style == 'tex' else (1.0 if detail == 255 else (detail + 0.5) / 16.0)
                    loop[self.col] = (min(1.0, c[0] * g), min(1.0, c[1] * g), min(1.0, c[2] * g), a)
                if self.uv is None:
                    continue
                # box projection UV
                ax = max(range(3), key=lambda i: abs(n[i]))
                if ax == 2:
                    uv = (p.x, p.y)
                elif ax == 1:
                    uv = (p.x, p.z)
                else:
                    uv = (p.y, p.z)
                loop[self.uv].uv = (uv[0] * self.tex_scale, uv[1] * self.tex_scale)
            f.smooth = False

    def _new_faces(self, before):
        return [f for f in self.bm.faces if f not in before]

    # ---------------------------------------------------------------- primitives
    def box(self, lo, hi, mat, bevel=0.0, **kw):
        before = set(self.bm.faces)
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        lo, hi = Vector(lo), Vector(hi)
        c = (lo + hi) * 0.5
        s = hi - lo
        for v in res['verts']:
            v.co = Vector((c.x + v.co.x * s.x, c.y + v.co.y * s.y, c.z + v.co.z * s.z))
        if bevel > 0:
            edges = list({e for v in res['verts'] for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=edges, offset=min(bevel, min(s) * 0.45), segments=1, affect='EDGES')
        faces = self._new_faces(before)
        for f in faces:
            f.normal_update()
        self.paint(faces, mat, **kw)
        return faces

    def prism(self, x0, x1, y0, y1, z0, zr, mat, ridge_y=None, **kw):
        """Gable prism: rectangle footprint [x0,x1]x[y0,y1] at z0, ridge along X at height zr (over ridge_y)."""
        ry = (y0 + y1) / 2 if ridge_y is None else ridge_y
        b = self.bm
        v = [b.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, ry, zr), (x1, ry, zr))]
        fs = [b.faces.new((v[0], v[1], v[5], v[4])), b.faces.new((v[2], v[3], v[4], v[5])),
              b.faces.new((v[0], v[4], v[3])), b.faces.new((v[1], v[2], v[5])), b.faces.new((v[3], v[2], v[1], v[0]))]
        for f in fs:
            f.normal_update()
        bmesh.ops.recalc_face_normals(b, faces=fs)
        self.paint(fs, mat, **kw)
        return fs

    def cyl(self, cx, cy, z0, z1, r0, r1, mat, seg=8, cap_top=True, cap_bottom=False, rx_scale=1.0, ry_scale=1.0, rot=0.0, **kw):
        b = self.bm
        rings = []
        for z, r in ((z0, r0), (z1, r1)):
            ring = []
            for i in range(seg):
                a = 2 * math.pi * i / seg + rot
                ring.append(b.verts.new((cx + math.cos(a) * r * rx_scale, cy + math.sin(a) * r * ry_scale, z)))
            rings.append(ring)
        fs = []
        for i in range(seg):
            j = (i + 1) % seg
            fs.append(b.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i])))
        if cap_top and r1 > 1e-5:
            fs.append(b.faces.new(list(reversed(rings[1]))))
        elif r1 <= 1e-5:
            pass
        if cap_bottom:
            fs.append(b.faces.new(rings[0]))
        bmesh.ops.recalc_face_normals(b, faces=fs)
        self.paint(fs, mat, **kw)
        return fs

    def cone(self, cx, cy, z0, z1, r, mat, seg=6, **kw):
        b = self.bm
        ring = [b.verts.new((cx + math.cos(2 * math.pi * i / seg) * r, cy + math.sin(2 * math.pi * i / seg) * r, z0)) for i in range(seg)]
        tip = b.verts.new((cx, cy, z1))
        fs = [b.faces.new((ring[i], ring[(i + 1) % seg], tip)) for i in range(seg)]
        fs.append(b.faces.new(list(reversed(ring))))
        bmesh.ops.recalc_face_normals(b, faces=fs)
        self.paint(fs, mat, **kw)
        return fs

    def lathe(self, cx, cy, profile, mat, seg=10, rot=0.0, **kw):
        """profile: [(radius, z), ...] bottom -> top; closes the top with a fan if the last radius > 0."""
        b = self.bm
        rings = []
        for r, z in profile:
            ring = []
            for i in range(seg):
                a = 2 * math.pi * i / seg + rot
                ring.append(b.verts.new((cx + math.cos(a) * r, cy + math.sin(a) * r, z)))
            rings.append(ring)
        fs = []
        for k in range(len(rings) - 1):
            for i in range(seg):
                j = (i + 1) % seg
                fs.append(b.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i])))
        if profile[-1][0] > 1e-5:
            fs.append(b.faces.new(list(reversed(rings[-1]))))
        if profile[0][0] > 1e-5:
            fs.append(b.faces.new(rings[0]))
        bmesh.ops.recalc_face_normals(b, faces=fs)
        self.paint(fs, mat, **kw)
        return fs

    def blob(self, center, radii, mat, subdiv=1, jag=0.0, seed=0, squash_below=None, rot_z=0.0, mats_by_height=None, **kw):
        """Faceted ellipsoid. squash_below: z (absolute) under which vertices are flattened to it."""
        before = set(self.bm.faces)
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=1.0)
        rs = random.Random(seed * 7919 + 13)
        cx, cy, cz = center
        rx, ry, rz = radii
        cache = {}
        for v in res['verts']:
            n = v.co.copy()
            key = (round(n.x, 3), round(n.y, 3), round(n.z, 3))
            if key not in cache:
                cache[key] = 1.0 + (rs.random() - 0.5) * 2 * jag
            j = cache[key]
            x, y = n.x * rx * j, n.y * ry * j
            if rot_z:
                x, y = x * math.cos(rot_z) - y * math.sin(rot_z), x * math.sin(rot_z) + y * math.cos(rot_z)
            v.co = Vector((cx + x, cy + y, cz + n.z * rz * j))
            if squash_below is not None and v.co.z < squash_below:
                v.co.z = squash_below
        faces = self._new_faces(before)
        for f in faces:
            f.normal_update()
        self.paint(faces, mat, **kw)
        return faces

    def quad(self, p0, p1, p2, p3, mat, **kw):
        b = self.bm
        f = b.faces.new([b.verts.new(p) for p in (p0, p1, p2, p3)])
        f.normal_update()
        self.paint([f], mat, **kw)
        return f

    def tri(self, p0, p1, p2, mat, **kw):
        b = self.bm
        f = b.faces.new([b.verts.new(p) for p in (p0, p1, p2)])
        f.normal_update()
        self.paint([f], mat, **kw)
        return f

    def blade(self, x, y, h, w, lean, mat, lean_y=0.0, **kw):
        """A tapered grass blade: 3 tris front and back (double sided)."""
        b = self.bm
        fs_all = []
        for side in (0, 1):
            v0 = b.verts.new((x - w / 2, y, 0))
            v1 = b.verts.new((x + w / 2, y, 0))
            v2 = b.verts.new((x - w * 0.28 + lean * 0.5, y + lean_y * 0.5, h * 0.62))
            v3 = b.verts.new((x + w * 0.28 + lean * 0.5, y + lean_y * 0.5, h * 0.62))
            v4 = b.verts.new((x + lean, y + lean_y, h))
            if side == 0:
                fs = [b.faces.new((v0, v1, v3, v2)), b.faces.new((v2, v3, v4))]
            else:
                fs = [b.faces.new((v1, v0, v2, v3)), b.faces.new((v3, v2, v4))]
            for f in fs:
                f.normal_update()
            fs_all += fs
        self.paint(fs_all, mat, **kw)
        return fs_all

    def poly_prism(self, pts_xz, y0, y1, mat, **kw):
        """Polygon in the XZ plane (list of (x,z)) extruded from y0 to y1 along Y (y0 = front)."""
        b = self.bm
        f0 = [b.verts.new((x, y0, z)) for x, z in pts_xz]
        f1 = [b.verts.new((x, y1, z)) for x, z in pts_xz]
        n = len(pts_xz)
        fs = [b.faces.new(f0), b.faces.new(list(reversed(f1)))]
        for i in range(n):
            j = (i + 1) % n
            fs.append(b.faces.new((f0[i], f0[j], f1[j], f1[i])))
        bmesh.ops.recalc_face_normals(b, faces=fs)
        self.paint(fs, mat, **kw)
        return fs

    # ---------------------------------------------------------------- transforms
    def transform_all(self, M):
        bmesh.ops.transform(self.bm, matrix=M, verts=list(self.bm.verts))

    def merge_dupes(self, dist=1e-5):
        bmesh.ops.remove_doubles(self.bm, verts=list(self.bm.verts), dist=dist)

    def absorb(self, other):
        """Append every face of another (vcol) Prop, colours included, and free it."""
        bm = self.bm
        self.mi('vcol')
        other.bm.verts.index_update()
        vmap = {}
        for f in other.bm.faces:
            vs = []
            for v in f.verts:
                if v.index not in vmap:
                    vmap[v.index] = bm.verts.new(v.co)
                vs.append(vmap[v.index])
            try:
                nf = bm.faces.new(vs)
            except ValueError:
                continue
            nf.material_index = 0
            for la, lb in zip(f.loops, nf.loops):
                lb[self.col] = la[other.col]
        other.bm.free()

    def tri_count(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    # ---------------------------------------------------------------- output
    def to_object(self):
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for nm in self.mat_names or ['dark']:
            me.materials.append(_material(nm, self.style, self.vcol_name))
        for a in list(me.color_attributes):
            if a.name != 'Col':
                me.color_attributes.remove(a)
        me.color_attributes.active_color = me.color_attributes['Col']
        for p in me.polygons:
            p.use_smooth = False
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


_MAT_CACHE = {}


def _material(name, style, vname='prop'):
    if name == 'vcol':
        m = bpy.data.materials.new(vname)
        m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        b.inputs['Roughness'].default_value = 0.95
        return m
    key = (name, style)
    if key in _MAT_CACHE and _MAT_CACHE[key].name in bpy.data.materials:
        return _MAT_CACHE[key]
    ramp, tex, detail = MATS[name]
    m = bpy.data.materials.new('%s_%s' % (style, name))
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = 0.9
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.1
    if style == 'tex' and tex:
        img = bpy.data.images.load(ET.tex_path(tex))
        img.pack()
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = img
        tn.interpolation = 'Linear'
        tn.extension = 'REPEAT'
        nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        c = ramp[2]
        bsdf.inputs['Base Color'].default_value = (c[0] ** 2.2, c[1] ** 2.2, c[2] ** 2.2, 1.0)
    if name in ('glass', 'water', 'screen'):
        bsdf.inputs['Roughness'].default_value = 0.15
    if name in ('gold', 'metal'):
        bsdf.inputs['Metallic'].default_value = 0.6
        bsdf.inputs['Roughness'].default_value = 0.4
    _MAT_CACHE[key] = m
    return m


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MAT_CACHE.clear()


def export(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', check_existing=False, use_selection=False,
                              export_apply=True, export_yup=True, export_materials='EXPORT', export_animations=False,
                              export_vertex_color='NAME', export_vertex_color_name='Col',
                              export_all_vertex_colors=False, export_normals=True)
    return os.path.getsize(path)

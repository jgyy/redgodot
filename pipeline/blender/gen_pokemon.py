"""Generate rigged, animated, textured 3D Pokemon (.glb) from upstream's 2D sprite definitions.

Usage (headless Blender via the bpy wheel, or `blender --background --python ... --`):
  python3 pipeline/blender/gen_pokemon.py -- --all            # all 151 (+ MISSINGNO)
  python3 pipeline/blender/gen_pokemon.py -- --only PIKACHU,CHARIZARD
  python3 pipeline/blender/gen_pokemon.py -- --all --jobs 3   # parallel worker processes
  add --noanim for a quick geometry-only export, --out DIR to write elsewhere.

Input : pipeline/extracted/mons.json (upstream src/data/mons/*.js), pokedata.json,
        pipeline/data/species_looks.json (researched look of every species: archetype, gait,
        official colours, key features), pipeline/blender/species_fixes.py (per-species patches)
Output: godot/assets/models/pokemon/<SPECIES>.glb + manifest.json

How a 2D definition becomes a model
-----------------------------------
* Geometry lives in upstream's own 64x64 sprite space (x right, y down, ground ~ y 60)
  plus a depth axis, so every part lines up exactly with the sprite.
  Blender: X = x - 32, Z = 60 - y, Y = depth (front = -Y = glTF/Godot +Z).
* species_fixes.py first patches the definition where the sprite is anatomically off or
  unappealing (extra limbs, thicker necks, better ears, ...), driven by species_looks.json.
* Each art group (`g`) is a smooth-union SDF of its ellipsoids, tapered capsules, strokes
  and bevelled polygon plates (monparts.py).  All groups share one grid and are smooth-unioned
  into ONE watertight surface with filleted joints; sibling limbs (left/right legs...) are joined
  with a hard min so they never web (monfield.py).  The surface is polygonised with surface
  nets, snapped to the field, decimated, and given smooth normals from the field gradient.
* Ambient occlusion is marched through the same field and exported as vertex colour (COLOR_0);
  the toon shader multiplies it in (`use_vertex_ao`).
* Depth: paint order (z, then array order) becomes front-to-back placement (solve_depth).
* Texture: an anti-aliased albedo atlas (3x3 supersampled, 5 texels per sprite pixel) holds per
  group a front and a back layer rasterised from the definition itself (monraster.py): palette
  colours, spots, stripes, eyes, mouths, shines, plus subtle fur / scale / rock micro detail.
* Rig: one bone per art group arranged in a parent tree, plus secondary chains along tails, necks
  and serpent bodies; skin weights blend smoothly where groups meet (monrig.py).
* Animation: archetype-specific gaits, idles, attacks, hurt/faint/special clips (monanim.py).
* Lighting / outline happen in Godot (assets/shaders/toon.gdshader).
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402
import monfield as MF  # noqa: E402
import monparts as MP  # noqa: E402
import monraster as RS  # noqa: E402
import monrig as RG  # noqa: E402
import glbtools as GT  # noqa: E402

try:
    import species_fixes as FX  # noqa: E402
except ImportError:          # pragma: no cover
    FX = None

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXTRACTED = os.path.join(ROOT, 'pipeline', 'extracted')
DATA_DIR = os.path.join(ROOT, 'pipeline', 'data')
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon')

FEATURE_TYPES = MP.FEATURE_TYPES
TEX_S = 5.0            # atlas texels per sprite pixel (final)
TEX_SS = 3             # supersampling factor per axis for anti-aliasing
GRID_H = 0.26          # SDF grid spacing in sprite px
MIN_TRIS, MAX_TRIS = 5000, 11000
AO_STRENGTH = 0.9
TEX_WEBP_Q = 95        # lossy WebP quality of the atlas (smooth palette art: keeps glb + texture small)


def load_looks():
    p = os.path.join(DATA_DIR, 'species_looks.json')
    if os.path.exists(p):
        return json.load(open(p))
    return {}


LOOKS = load_looks()


# ============================================================================ texture atlas
def build_layers(defn, groups, decals, pal, micro_kind, seed):
    """Per group, front + back albedo layers.  Returns {(g, side): (Region, rgb[h,w,3])}."""
    parts = defn.get('parts', []) or []
    part_group = {}
    for G in groups:
        for q in G.parts:
            part_group[q.order] = G.name
    S, SS = TEX_S, TEX_SS
    # front composite (for deciding which group a face feature / decal sits on)
    R = RS.Region(-8, -8, 72, 72, 2.0)
    zb = np.full(R.X.shape, -1e18)
    gid = np.full(R.X.shape, '', dtype=object)
    for order, p in enumerate(parts):
        if order in part_group and not p.get('backOnly'):
            key = MP.fnum(p, 'z', 0) * 1000 + order
            m = RS.part_mask(R, p) & (key >= zb)
            zb[m] = key
            gid[m] = part_group[order]
    covered = np.argwhere(gid != '')

    def group_at(x, y):
        i = int((x + 8) * 2.0)
        j = int((y + 8) * 2.0)
        if 0 <= j < gid.shape[0] and 0 <= i < gid.shape[1] and gid[j, i]:
            return gid[j, i]
        if len(covered) == 0:
            return None
        k = int(np.argmin((covered[:, 1] - i) ** 2 + (covered[:, 0] - j) ** 2))
        return gid[covered[k][0], covered[k][1]]

    # who paints each non-solid / decal part
    target = {}
    for order, p in enumerate(parts):
        t = p.get('t')
        if t in FEATURE_TYPES:
            g = group_at(MP.fnum(p, 'x'), MP.fnum(p, 'y'))
            if g:
                target[order] = ('feat', g)
        elif p.get('g') in decals and t in MP.SOLID_TYPES:
            x0, y0, x1, y1 = RS.part_bbox(p)
            g = group_at((x0 + x1) * 0.5, (y0 + y1) * 0.5)
            if g:
                target[order] = ('decal', g)
        elif p.get('on') is not None and t not in FEATURE_TYPES and order not in part_group:
            target[order] = ('on', p.get('on'))

    layers = {}
    for G in groups:
        x0 = min(q.bx0 for q in G.parts) - 2.5
        y0 = min(q.by0 for q in G.parts) - 2.5
        x1 = max(q.bx1 for q in G.parts) + 2.5
        y1 = max(q.by1 for q in G.parts) + 2.5
        for side in ('front', 'back'):
            Rg = RS.Region(x0, y0, x1, y1, S * SS, mult=SS)
            L = RS.Layer(Rg)
            cov_all = np.zeros(L.cov.shape, dtype=bool)      # everything this group paints on this side
            for order, p in enumerate(parts):
                if order in part_group and part_group[order] == G.name:
                    if (side == 'front' and p.get('backOnly')) or \
                            (side == 'back' and (p.get('face') or p.get('frontOnly') or p.get('belly'))):
                        continue
                    cov_all |= RS.part_mask(Rg, p)
            # solids first (z-buffered), then the spots / stripes / decals that sit on them, in list order
            for pass_on in (False, True):
                for order, p in enumerate(parts):
                    if side == 'front' and p.get('backOnly'):
                        continue
                    if side == 'back' and (p.get('face') or p.get('frontOnly') or p.get('belly')):
                        continue
                    if order in part_group and not pass_on:
                        if part_group[order] != G.name:
                            continue
                        z = MP.fnum(p, 'bz', MP.fnum(p, 'z', 0)) if side == 'back' else MP.fnum(p, 'z', 0)
                        key = z * 1000 + order
                        m = RS.part_mask(Rg, p) & (key >= L.z)
                        L.z[m] = key
                        L.cov |= m
                        L.put(m, MP.resolve_color(p.get('c'), pal))
                    elif pass_on and order not in part_group and order in target \
                            and target[order][0] in ('on', 'decal'):
                        if target[order][1] != G.name:
                            continue
                        m = RS.part_mask(Rg, p) & cov_all
                        L.put(m, MP.resolve_color(p.get('c'), pal))
            before = L.rgb.copy()
            if side == 'front':
                for order, p in enumerate(parts):
                    if order in target and target[order][0] == 'feat' and target[order][1] == G.name:
                        L.draw_feature(p, pal)
            painted = L.cov | (L.rgb.sum(-1) > 0)
            featmask = (np.abs(L.rgb - before).sum(-1) > 1e-6)
            # face detail (decals, features) is not textured with fur / scales
            main = max(G.parts, key=lambda q: q.area).color
            rgb, alpha = RS.box_down(L.rgb, painted, SS)
            hh, ww = featmask.shape[0] // SS, featmask.shape[1] // SS
            fa = featmask.reshape(hh, SS, ww, SS).mean(axis=(1, 3))
            weight = np.clip(1.0 - fa * 1.5, 0.0, 1.0)
            rgb = _bleed(rgb, alpha, main, S)
            rgb = RS.micro_detail(rgb, weight, micro_kind, S, seed + (7 if side == 'back' else 0))
            layers[(G.name, side)] = (Rg, rgb)
    return layers


def _bleed(rgb, alpha, fill_color, S):
    """Bleed colours outward from covered texels (so seams / mip levels never show black)."""
    known = alpha > 0.02
    rgb = rgb.copy()
    if not known.any():
        rgb[:] = RS.hex_rgb(fill_color)
        return rgb
    iters = int(max(6, S * 3.5))
    for _ in range(iters):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            k = np.roll(known, (dy, dx), axis=(0, 1))
            c = np.roll(rgb, (dy, dx), axis=(0, 1))
            acc += c * k[..., None]
            cnt += k
        new = (~known) & (cnt > 0)
        if not new.any():
            break
        rgb[new] = acc[new] / cnt[new][:, None]
        known = known | new
    if (~known).any():
        rgb[~known] = rgb[known].mean(axis=0)
    return rgb


def pack_atlas(layers):
    """Shelf-pack layers into one image.  Returns (atlas[H,W,3], {key: (ax, ay)}, W, H)."""
    items = sorted(layers.items(), key=lambda kv: -kv[1][1].shape[0])
    total = sum(img.shape[0] * img.shape[1] for _, (Rg, img) in items)
    W = 1024 if total < 0.62 * 1024 * 1400 else 2048
    pad = 3
    x = y = shelf = 0
    pos = {}
    for key, (Rg, img) in items:
        h, w = img.shape[:2]
        if x + w + pad > W:
            x = 0
            y += shelf + pad
            shelf = 0
        pos[key] = (x, y)
        x += w + pad
        shelf = max(shelf, h)
    H = y + shelf
    H = int(math.ceil(H / 64.0) * 64)
    atlas = np.zeros((H, W, 3))
    for key, (Rg, img) in items:
        ax, ay = pos[key]
        h, w = img.shape[:2]
        atlas[ay:ay + h, ax:ax + w] = img
    return atlas, pos, W, H


def save_png(rgb, path):
    from PIL import Image
    img = Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8), 'RGB')
    img.save(path, optimize=True)


def make_textured_material(name, png_path):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    img = bpy.data.images.load(png_path)
    img.pack()
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    ca = nt.nodes.new('ShaderNodeVertexColor')
    ca.layer_name = 'Color'
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(tex.outputs['Color'], mix.inputs['A'])
    nt.links.new(ca.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.1
    return m


# ============================================================================ geometry
def polygonise(model, warnings):
    """Surface nets on the unified field -> decimated triangle mesh in sprite space.
    Returns (P[n,3] (x, y, d), tris[m,3])."""
    v, q = MF.surface_nets_sparse(model.F, model.grid.o, model.h)
    if len(q) == 0:
        raise RuntimeError('empty surface')
    v = model.project(v, 2)
    area = len(q) * model.h * model.h
    budget = int(np.clip(area * 1.15, MIN_TRIS, MAX_TRIS))
    # to Blender frame for the decimator
    B = np.stack([v[:, 0] - 32.0, v[:, 2], 60.0 - v[:, 1]], axis=1)
    me = bpy.data.meshes.new('raw')
    me.from_pydata(B.tolist(), [], q.tolist())
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='SHORT_EDGE')
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new('raw', me)
    bpy.context.scene.collection.objects.link(obj)
    tris0 = len(me.polygons)
    if tris0 > budget:
        mod = obj.modifiers.new('dec', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.01, budget / float(tris0))
        mod.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me2 = bpy.data.meshes.new_from_object(ev)
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(me)
        me = me2
    else:
        bpy.data.objects.remove(obj)
    nv = len(me.vertices)
    co = np.zeros(nv * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    me.calc_loop_triangles()
    lt = np.zeros(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get('vertices', lt)
    tris = lt.reshape(-1, 3)
    bpy.data.meshes.remove(me)
    # back to sprite space, snap onto the true surface
    P = np.stack([co[:, 0] + 32.0, 60.0 - co[:, 2], co[:, 1]], axis=1)
    P = model.project(P, 2)
    # drop unreferenced vertices
    used = np.zeros(nv, dtype=bool)
    used[tris.ravel()] = True
    remap = -np.ones(nv, dtype=np.int64)
    remap[used] = np.arange(int(used.sum()))
    P, tris = P[used], remap[tris]
    # drop degenerate / duplicate triangles (mesh.validate() would silently drop them and shift the UVs)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    ok = (a != b) & (b != c) & (a != c)
    ar = np.linalg.norm(np.cross(P[b] - P[a], P[c] - P[a]), axis=1)
    ok &= ar > 1e-7
    tris = tris[ok]
    srt = np.sort(tris, axis=1)
    _, first = np.unique(srt, axis=0, return_index=True)
    tris = tris[np.sort(first)]
    # outward winding: signed volume must be positive in the Blender frame
    Bq = np.stack([P[:, 0] - 32.0, P[:, 2], 60.0 - P[:, 1]], axis=1)
    vol = np.einsum('ij,ij->i', Bq[tris[:, 0]], np.cross(Bq[tris[:, 1]], Bq[tris[:, 2]])).sum()
    if vol < 0:
        tris = tris[:, ::-1].copy()
    return P, tris


def face_owners(FM, tris, groups, nsum_y):
    """Which group's atlas layer and which side (front/back projection) paints each triangle.
    Returns (group index[m], front[m]).  Ties (coincident surfaces such as belly plates lying on the
    body) go to the group nearest the viewer for front faces / the rear for back faces; neighbour
    majority passes then remove isolated specks so texture seams form clean loops (few split
    vertices in the exported mesh)."""
    cd = np.array([G.cd for G in groups])
    n = len(tris)
    G = len(groups)
    front = nsum_y <= 0.6            # avg normal.y <= 0.2: side-on faces take the front (face) layer
    # a vertex belongs to the group whose own surface it lies on (smallest field value); exact ties
    # (coincident surfaces) go to the group nearest the viewing side
    fm = FM[tris].sum(axis=1) / 3.0                                # (m, G)
    depth = np.where(front[:, None], -cd[None, :], cd[None, :])
    fg = (fm - 0.004 * depth).argmin(axis=1)
    label = fg * 2 + (~front).astype(np.int64)
    # face adjacency over shared edges
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]], axis=0)
    fid = np.tile(np.arange(n), 3)
    e = np.sort(e, axis=1)
    key = e[:, 0].astype(np.int64) * (int(tris.max()) + 1) + e[:, 1]
    order = np.argsort(key, kind='stable')
    ks, fs = key[order], fid[order]
    same = ks[1:] == ks[:-1]
    a, b = fs[:-1][same], fs[1:][same]
    for _ in range(4):
        votes = np.zeros((n, 2 * G))
        np.add.at(votes, (a, label[b]), 1.0)
        np.add.at(votes, (b, label[a]), 1.0)
        best = votes.argmax(axis=1)
        vb = votes[np.arange(n), best]
        # a face flips only when at least two neighbours agree on another label and none share its own
        vs = votes[np.arange(n), label]
        label = np.where((best != label) & (vb >= 2) & (vs <= 1), best, label)
    return label // 2, (label % 2) == 0


def group_weights(model, groups, P):
    """Soft per-group membership of each vertex from the group fields, and the raw field values."""
    cols, raw = [], []
    for G in groups:
        F = model.sample_group(G.name, P)
        tau = float(np.clip(0.32 * MF.blend_k(G) + 0.35, 0.55, 1.6))
        cols.append(np.exp(-np.maximum(F, 0.0) / tau))
        raw.append(F)
    return np.stack(cols, axis=1), np.stack(raw, axis=1)


# ============================================================================ species
def build_species(name, defn, sp, warnings, tmpdir, look):
    pal = defn.get('pal', {}) or {}
    groups, decals = MP.collect_groups(defn, warnings)
    if not groups:
        raise RuntimeError('no solid parts')
    anchor = MP.solve_depth(groups)
    lens = [G for G in groups if G.lens and G is not anchor]
    if lens:                                   # belly plates, cheeks...: texture on the host group, no geometry
        decals = set(decals) | {G.name for G in lens}
        groups = [G for G in groups if G not in lens]
    MP.add_connectors(groups, anchor)
    kscale = float((look or {}).get('blend', 1.0))
    model = MF.Model(groups, GRID_H, k_scale=kscale)
    P, tris = polygonise(model, warnings)
    N = model.normals(P)
    # ambient occlusion: shell radius ~ 7% of the model height
    hgt = float(P[:, 1].max() - P[:, 1].min())
    ao = 1.0 - AO_STRENGTH * model.ambient_occlusion(P + N * 0.15, N, radius=max(2.5, 0.075 * hgt), samples=7)
    Wg, Fmat = group_weights(model, groups, P)
    gnames = [G.name for G in groups]
    ginfo = {G.name: dict(area=G.area, cd=G.cd, anchor=(G is anchor)) for G in groups}
    # Blender-frame vertices (px, x centred)
    B = np.stack([P[:, 0] - 32.0, P[:, 2], 60.0 - P[:, 1]], axis=1)
    NB = np.stack([N[:, 0], N[:, 2], -N[:, 1]], axis=1)
    rig = RG.build(gnames, B, tris, Wg, ginfo, chain_hint=(look or {}).get('chains'),
                   role_hint=(look or {}).get('roles'))

    # ---- texture
    micro = (look or {}).get('surface', 'smooth')
    layers = build_layers(defn, groups, decals, pal, micro, seed=abs(hash(name)) % 100000)
    atlas, pos, W, H = pack_atlas(layers)
    png = os.path.join(tmpdir, name + '.png')
    save_png(atlas, png)
    # ---- per-face group + UVs (planar sprite projection of the owning group's layer)
    gcol = {g: i for i, g in enumerate(gnames)}
    nsum = NB[tris].sum(axis=1)
    fg, front = face_owners(Fmat, tris, groups, nsum[:, 1])
    uv = np.zeros((len(tris), 3, 2))
    for gi, g in enumerate(gnames):
        for side, sel in (('front', (fg == gi) & front), ('back', (fg == gi) & ~front)):
            if not sel.any():
                continue
            Rg, img = layers[(g, side)]
            ax, ay = pos[(g, side)]
            sx = np.clip(P[tris[sel], 0], Rg.x0 + 0.4, Rg.x1 - 0.4)
            sy = np.clip(P[tris[sel], 1], Rg.y0 + 0.4, Rg.y1 - 0.4)
            uv[sel, :, 0] = (ax + (sx - Rg.x0) * TEX_S) / W
            uv[sel, :, 1] = 1.0 - (ay + (sy - Rg.y0) * TEX_S) / H
    mat = make_textured_material('mon_' + name.lower(), png)
    return dict(B=B, NB=NB, tris=tris, ao=ao, uv=uv, rig=rig, mat=mat, tex=(W, H), groups=gnames, model=model,
                P=P)


# ============================================================================ rig + export
def ht_metres(sp):
    ht = sp.get('ht') or [1, 0]
    try:
        m = float(ht[0]) * 0.3048 + float(ht[1]) * 0.0254
    except Exception:  # noqa: BLE001
        m = 0.5
    return max(0.15, m)


def make_object(name, B, NB, tris, uv, ao, rig, mat, bone_names, smooth=True):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(B))
    me.vertices.foreach_set('co', B.astype(np.float32).ravel())
    nt = len(tris)
    me.loops.add(nt * 3)
    me.polygons.add(nt)
    me.loops.foreach_set('vertex_index', tris.astype(np.int32).ravel())
    me.polygons.foreach_set('loop_start', (np.arange(nt) * 3).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(nt, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', uv.reshape(-1, 2).astype(np.float32).ravel())
    me.polygons.foreach_set('use_smooth', np.full(nt, bool(smooth), dtype=bool))
    if smooth:
        try:
            me.normals_split_custom_set_from_vertices([tuple(n) for n in NB])
        except Exception:  # noqa: BLE001
            pass
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'POINT')
    col = np.stack([ao, ao, ao, np.ones_like(ao)], axis=1).astype(np.float32)
    ca.data.foreach_set('color', col.ravel())
    me.color_attributes.active_color = ca
    me.materials.append(mat)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    vgs = {}
    for bn in bone_names:
        vgs[bn] = obj.vertex_groups.new(name=bn)
    for k in range(4):
        idx = rig.influence_idx[:, k]
        w = rig.influence_w[:, k]
        for bi in np.unique(idx):
            sel = np.nonzero((idx == bi) & (w > 0))[0]
            if len(sel) == 0:
                continue
            # group vertices by weight to keep the python loop short
            for wv in np.unique(np.round(w[sel], 3)):
                ss = sel[np.round(w[sel], 3) == wv]
                vgs[bone_names[bi]].add(ss.tolist(), float(wv), 'ADD')
    return obj


def _to_webp(raw):
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=TEX_WEBP_Q, method=6)
    return buf.getvalue(), 'webp', 'image/webp'


def finalize(name, sp, built, out_path, look, animate=True):
    B, NB, tris, ao, uv, rig, mat = (built[k] for k in ('B', 'NB', 'tris', 'ao', 'uv', 'rig', 'mat'))
    lo, hi = B.min(axis=0), B.max(axis=0)
    H_px = max(hi[2] - lo[2], 1e-3)
    target = ht_metres(sp)
    k = target / H_px
    cx, cy = (lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5
    zshift = lo[2] if lo[2] < 4.0 else 0.0          # keep genuine hovering (ghosts, floaters)
    hovering = zshift == 0.0 and lo[2] >= 4.0

    def xf(P):
        return (P - np.array([cx, cy, zshift])) * k

    Bm = xf(B)
    bones = []
    bname = {}
    for b in rig.bones:
        nm = b['name'] if b['name'] != 'root' else 'root_grp'
        bname[b['name']] = nm
    for b in rig.bones:
        par = b['parent']
        bones.append({'name': bname[b['name']], 'head': Vector(xf(np.asarray(b['head'])[None, :])[0]),
                      'parent': bname.get(par) if par else None, 'length': target * 0.1})
    bone_names = [bn['name'] for bn in bones]
    obj = make_object(name, Bm, NB, tris, uv, ao, rig, mat, bone_names)
    arm = C.build_armature(name, bones, root_len=target * 0.25)
    C.skin_to_armature(obj, arm)
    info = {'height_m': round(target, 3), 'px_height': round(H_px, 2), 'groups': len(built['groups']),
            'tris': int(len(tris)), 'bones': len(bones), 'materials': 1}
    if animate:
        import monanim as MA
        MA.animate(arm, name, sp, look, rig, bones, xf, target, hovering, verts_m=Bm)
    C.export_glb(out_path, animations=animate)
    # the atlas lives next to the glb (referenced by uri, lossy WebP) instead of being embedded, so Godot
    # does not extract a second copy of it on import; vertex colour / weights are stored as bytes
    GT.externalize_images(out_path, lambda i, mime: name + '_tex', transcode=_to_webp)
    GT.quantize_attributes(out_path)
    d = os.path.dirname(out_path)
    for stale in (name + '_' + name + '.png', name + '_' + name + '.png.import', name + '_tex.png',
                  name + '_tex.png.import'):
        if os.path.exists(os.path.join(d, stale)):
            os.remove(os.path.join(d, stale))
    info['bytes_tex'] = os.path.getsize(os.path.join(d, name + '_tex.webp'))
    return info


# ============================================================================ main
def run_one(name, defn, sp, out_dir, tmpdir, animate=True):
    warnings = []
    t0 = time.time()
    out_path = os.path.join(out_dir, name + '.glb')
    C.reset_scene()
    look = LOOKS.get(name)
    if FX is not None:
        defn = FX.apply(name, defn, look)
    built = build_species(name, defn, sp, warnings, tmpdir, look)
    info = finalize(name, sp, built, out_path, look, animate=animate)
    info['file'] = name + '.glb'
    info['bytes'] = os.path.getsize(out_path)
    info['status'] = 'generated'
    info['texture'] = '%dx%d' % built['tex']
    print('%-12s %5.2fs h=%.2fm groups=%d bones=%d tris=%d tex=%s %dKB %s' % (
        name, time.time() - t0, info['height_m'], info['groups'], info['bones'], info['tris'], info['texture'],
        info['bytes'] // 1024, ('warn=%d' % len(warnings)) if warnings else ''), flush=True)
    return info, warnings


def species_list(mons, pdata):
    species = [s for s in mons if s in pdata]
    species.sort(key=lambda s: pdata[s].get('dex', 999))
    return species


def main():
    args = C.parse_args()
    only = None
    if '--only' in args:
        only = [s for s in args[args.index('--only') + 1].split(',') if s]
    out_dir = args[args.index('--out') + 1] if '--out' in args else OUT_DIR
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 1
    animate = '--noanim' not in args
    C.ensure_dir(out_dir)
    mons = json.load(open(os.path.join(EXTRACTED, 'mons.json')))
    pdata = json.load(open(os.path.join(EXTRACTED, 'pokedata.json')))['species']
    species = species_list(mons, pdata)
    if only is not None:
        species = [s for s in species if s in only]
    t_all = time.time()

    if jobs > 1 and len(species) > 1:
        # fan out to worker processes (each is its own headless Blender), then merge
        chunks = [species[i::jobs] for i in range(jobs)]
        procs = []
        for i, ch in enumerate(chunks):
            if not ch:
                continue
            res = os.path.join(tempfile.gettempdir(), 'genmon_part%d.json' % i)
            cmd = [sys.executable, os.path.abspath(__file__), '--', '--only', ','.join(ch), '--out', out_dir,
                   '--result', res] + (['--noanim'] if not animate else [])
            procs.append((subprocess.Popen(cmd), res))
        results = {'species': {}, 'warnings': {}, 'errors': {}}
        for p, res in procs:
            p.wait()
            if os.path.exists(res):
                r = json.load(open(res))
                for k in results:
                    results[k].update(r.get(k, {}))
    else:
        results = {'species': {}, 'warnings': {}, 'errors': {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, name in enumerate(species):
                try:
                    info, warnings = run_one(name, mons[name], pdata[name], out_dir, tmpdir, animate)
                    results['species'][name] = info
                    if warnings:
                        results['warnings'][name] = warnings
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    results['errors'][name] = '%s: %s' % (type(e).__name__, e)
        if '--result' in args:
            with open(args[args.index('--result') + 1], 'w') as fh:
                json.dump(results, fh)
            return

    if only is None:
        extra = {}
        try:
            import gen_missingno
            extra = gen_missingno.build(out_dir)
            results['species'].update(extra)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            results['errors']['MISSINGNO'] = '%s: %s' % (type(e).__name__, e)
        import monanim as MA
        manifest = {
            'generated': [s for s in species if s in results['species']] + sorted(extra),
            'fallback': [], 'errors': results['errors'], 'warnings': results['warnings'],
            'species': results['species'],
            'animations': MA.CLIP_INFO,
            'conventions': {
                'units': 'metres; model height == Pokedex height (min 0.15 m)',
                'front': 'Blender -Y == glTF/Godot +Z (MODEL_FRONT)',
                'origin': 'bottom centre; hovering species keep their hover gap',
                'rig': "one bone per 2D art group in a parent tree under 'root', plus chains along tails / "
                       "necks / serpent bodies (<group>_1, <group>_2 ...); smooth skin weights",
                'texture': 'one anti-aliased albedo atlas per species (front/back sprite projections per art '
                           'group); vertex colour COLOR_0 = baked ambient occlusion; shade with '
                           'assets/shaders/toon.gdshader',
            },
            'elapsed_seconds': round(time.time() - t_all, 1),
        }
        with open(os.path.join(out_dir, 'manifest.json'), 'w') as fh:
            json.dump(manifest, fh, indent=1, sort_keys=False)
    print('DONE generated=%d errors=%d in %.1fs' % (len(results['species']), len(results['errors']),
                                                  time.time() - t_all))


if __name__ == '__main__':
    main()

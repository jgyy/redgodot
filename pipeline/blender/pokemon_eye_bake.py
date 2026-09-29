"""Texture-level fixes for the Pokemon eyes and alpha layers (headless Blender, used by pokemon_mesh_fix).

The source models are game extractions where an eye is two stacked meshes: `Eye` (a sclera/lid atlas with several
expression cells) and a slightly larger alpha-blended `Iris` overlay.  Godot's cel shader ignores alpha, so the
overlay rendered as an opaque black box (the 'visor' look on Squirtle, Psyduck, Mr. Mime ...).  Everything here
turns those layers into one opaque, correctly coloured material.
"""
import os

import numpy as np

EYE_WORDS = ('eye', 'iris', 'pupil', 'sclera', 'hitomi', 'mabuta')


# ------------------------------------------------------------------------------------------ helpers
def verts(me):
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


def mat_image(mat):
    """The base-colour image of a material (first TEX_IMAGE node), or None."""
    if mat is None or not mat.use_nodes:
        return None
    for nd in mat.node_tree.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image is not None:
            return nd.image
    return None


def read_px(img):
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def write_px(img, arr):
    img.pixels.foreach_set(arr.reshape(-1).astype(np.float32))
    img.update()


def loop_tris(me):
    """(tri_material (T,), tri_vertex_ids (T,3), tri_loop_ids (T,3), tri_polygon (T,))."""
    me.calc_loop_triangles()
    t = len(me.loop_triangles)
    mi = np.empty(t, dtype=np.int64)
    pi = np.empty(t, dtype=np.int64)
    vi = np.empty(t * 3, dtype=np.int64)
    li = np.empty(t * 3, dtype=np.int64)
    me.loop_triangles.foreach_get('material_index', mi)
    me.loop_triangles.foreach_get('polygon_index', pi)
    me.loop_triangles.foreach_get('vertices', vi)
    me.loop_triangles.foreach_get('loops', li)
    return mi, vi.reshape(-1, 3), li.reshape(-1, 3), pi


def uv_array(me):
    n = len(me.uv_layers.active.data)
    a = np.empty(n * 2)
    me.uv_layers.active.data.foreach_get('uv', a)
    return a.reshape(-1, 2)


def is_iris(m):
    if m is None:
        return False
    img = mat_image(m)
    return 'iris' in m.name.lower() or (img is not None and 'iris' in img.name.lower())


def is_eye(m):
    if m is None:
        return False
    img = mat_image(m)
    names = [m.name.lower()] + ([img.name.lower()] if img is not None else [])
    return any(w in n for n in names for w in EYE_WORDS)


def delete_faces(me, poly_ids):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in poly_ids], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    me.update()


def delete_slots(me, slots):
    ids = [p.index for p in me.polygons if p.material_index in slots]
    if ids:
        delete_faces(me, ids)


# ------------------------------------------------------------------------------------------ iris bake
def _project_uv(pos, layer_t, tv, tl, V, UV):
    """For surface points `pos` (N,3) find the overlay triangle covering them as seen from the front (x, z) and return
    its interpolated UV plus a hit mask."""
    A, B, C = (V[tv[layer_t, k]][:, [0, 2]] for k in range(3))
    UA, UB, UC = (UV[tl[layer_t, k]] for k in range(3))
    P = pos[:, [0, 2]][:, None, :]
    v0, v1, v2 = (B - A)[None], (C - A)[None], P - A[None]
    d00, d01, d11 = (v0 * v0).sum(-1), (v0 * v1).sum(-1), (v1 * v1).sum(-1)
    d20, d21 = (v2 * v0).sum(-1), (v2 * v1).sum(-1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) < 1e-18, 1e-18, den)
    b1 = (d11 * d20 - d01 * d21) / den
    b2 = (d00 * d21 - d01 * d20) / den
    b0 = 1 - b1 - b2
    ok = (b0 >= -1e-3) & (b1 >= -1e-3) & (b2 >= -1e-3)
    hit = ok.any(1)
    k = ok.argmax(1)
    r = np.arange(len(pos))
    uv = b0[r, k][:, None] * UA[k] + b1[r, k][:, None] * UB[k] + b2[r, k][:, None] * UC[k]
    return uv, hit


def _match(lcen, c, H):
    """Index of the overlay triangle sitting on the surface triangle centred at `c`: nearest in 3D, else nearest as
    seen from the front (x, z) when the overlay floats a bit in front of a thicker surface."""
    d = np.linalg.norm(lcen - c, axis=1)
    k = int(d.argmin())
    if d[k] < 0.05 * H:
        return k, d[k]
    d2 = np.hypot(lcen[:, 0] - c[0], lcen[:, 2] - c[2])
    k = int(d2.argmin())
    if d2[k] < 0.02 * H and abs(lcen[k, 1] - c[1]) < 0.15 * H:
        return k, d2[k]
    return None, None


def bake_iris_layers(me, extra_layers=(), skip=False):
    """Rasterise each alpha overlay (the Iris layers, plus any material named in `extra_layers`) into the surface right
    under it through that surface's UVs, then delete the overlay.  Returns the number of triangles that received paint."""
    if skip or not me.uv_layers:
        return 0
    iris_slots = [i for i, m in enumerate(me.materials) if is_iris(m)]
    extra = [i for i, m in enumerate(me.materials) if m and m.name in extra_layers]
    layers = [[i] for i in extra] + ([iris_slots] if iris_slots else [])
    if not layers:
        return 0
    all_layer = {i for grp in layers for i in grp}
    V = verts(me)
    UV = uv_array(me)
    tmat, tv, tl, _ = loop_tris(me)
    H = 0.5 * float(np.linalg.norm(V.max(0) - V.min(0)))   # orientation-free size (this runs before normalising)
    tcen = V[tv].mean(1)
    cache, touched, baked, tot_alpha = {}, {}, 0, 0.0
    # overlays that do not duplicate the surface's topology (Farfetch'd) are sampled by projecting along the view axis
    projected = [g for g in layers if g is not layers[-1] or not iris_slots or not [
        i for i, m in enumerate(me.materials) if i not in all_layer and is_eye(m) and mat_image(m)]]
    for grp in layers:
        layer_t = np.nonzero(np.isin(tmat, grp))[0]
        if not len(layer_t):
            continue
        lcen = tcen[layer_t]
        eye_slots = [i for i, m in enumerate(me.materials) if i not in all_layer and is_eye(m) and mat_image(m)]
        if eye_slots and grp is layers[-1]:
            cand = np.nonzero(np.isin(tmat, eye_slots))[0]
        else:
            # no material is called "eye" (Farfetch'd): paint onto whatever textured surface is right under it
            ok = [i for i, m in enumerate(me.materials) if i not in all_layer and mat_image(m)]
            cand = np.nonzero(np.isin(tmat, ok))[0]
            near = np.array([_match(lcen, tcen[t], H)[0] is not None for t in cand]) if len(cand) else []
            cand = cand[near] if len(cand) else cand
        if os.environ.get('POKE_DEBUG'):
            print('bake layer', [me.materials[i].name for i in grp], 'layer tris', len(layer_t), 'cand', len(cand),
                  'cand slots', sorted({int(tmat[t]) for t in cand}))
        for t in cand:
            slot = int(tmat[t])
            img = mat_image(me.materials[slot])
            if img.name not in cache:
                w0, h0 = img.size
                if max(w0, h0) <= 256:   # more texels per eye for the composite; still <= 512
                    img.scale(w0 * 2, h0 * 2)
                cache[img.name] = read_px(img)
            dst = cache[img.name]
            touched[img.name] = img
            h, w = dst.shape[:2]
            k, _ = _match(lcen, tcen[t], H)
            if k is None:
                continue
            it = layer_t[k]
            src_img = mat_image(me.materials[int(tmat[it])])
            if src_img is None:
                continue
            if src_img.name not in cache:
                cache[src_img.name] = read_px(src_img)
            src = cache[src_img.name]
            sh, sw = src.shape[:2]
            project = grp in projected
            iuv = None if project else UV[tl[it][[int(np.linalg.norm(V[tv[it]] - V[v], axis=1).argmin()) for v in tv[t]]]]
            px = UV[tl[t]] * np.array([w, h])
            x0, x1 = max(int(np.floor(px[:, 0].min())), 0), min(int(np.ceil(px[:, 0].max())), w - 1)
            y0, y1 = max(int(np.floor(px[:, 1].min())), 0), min(int(np.ceil(px[:, 1].max())), h - 1)
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            a, b, c3 = px
            den = (b[1] - c3[1]) * (a[0] - c3[0]) + (c3[0] - b[0]) * (a[1] - c3[1])
            if abs(den) < 1e-9:
                continue
            l1 = ((b[1] - c3[1]) * (gx - c3[0]) + (c3[0] - b[0]) * (gy - c3[1])) / den
            l2 = ((c3[1] - a[1]) * (gx - c3[0]) + (a[0] - c3[0]) * (gy - c3[1])) / den
            l3 = 1 - l1 - l2
            inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
            if not inside.any():
                continue
            if project:
                pos = l1[..., None] * V[tv[t, 0]] + l2[..., None] * V[tv[t, 1]] + l3[..., None] * V[tv[t, 2]]
                suv, hit = _project_uv(pos[inside], layer_t, tv, tl, V, UV)
                full = np.zeros(inside.shape + (2,))
                full[inside] = suv
                inside = inside.copy()
                inside[inside] = hit
                suv = full
            else:
                suv = l1[..., None] * iuv[0] + l2[..., None] * iuv[1] + l3[..., None] * iuv[2]
            sx = np.clip((suv[..., 0] * sw).astype(int), 0, sw - 1)
            sy = np.clip((suv[..., 1] * sh).astype(int), 0, sh - 1)
            sm = src[sy, sx]
            al = sm[..., 3:4] * inside[..., None]
            if os.environ.get('POKE_DEBUG') and baked < 3:
                print('  tri', t, 'px box', x0, x1, y0, y1, 'inside', int(inside.sum()), 'alpha sum', float(al.sum()),
                      'src size', sw, sh, 'suv', suv.min(), suv.max())
            reg = dst[y0:y1 + 1, x0:x1 + 1]
            reg[..., :3] = reg[..., :3] * (1 - al) + sm[..., :3] * al
            baked += 1
            tot_alpha += float(al.sum())
        if os.environ.get('POKE_DEBUG'):
            print('  layer total painted alpha', tot_alpha)
    for name, img in touched.items():
        write_px(img, cache[name])
    delete_slots(me, sorted(all_layer))
    return baked


# ------------------------------------------------------------------------------------------ other alpha layers
def make_opaque(m):
    for nd in m.node_tree.nodes:
        if nd.type == 'BSDF_PRINCIPLED':
            for lk in list(nd.inputs['Alpha'].links):
                m.node_tree.links.remove(lk)
            nd.inputs['Alpha'].default_value = 1.0
    m.blend_method = 'OPAQUE'


def resolve_alpha(me):
    """Other alpha-blended materials (wings, cheek decals, gas): cut the faces whose texture alpha at the face centre is
    below 0.5 out of the mesh and make the material opaque.  Returns {material: faces removed}."""
    out = {}
    if not me.uv_layers:
        return out
    UV = uv_array(me)
    tmat, tv, tl, tpoly = loop_tris(me)
    cut_polys = set()
    drop_slots = []
    for i, m in enumerate(me.materials):
        if m is None or not m.use_nodes or m.blend_method == 'OPAQUE':
            continue
        img = mat_image(m)
        if img is None or img.size[0] == 0 or img.size[1] == 0:
            make_opaque(m)
            continue
        px = read_px(img)
        h, w = px.shape[:2]
        sel = np.nonzero(tmat == i)[0]
        # palette atlases (Gastly's gas, Koffing) carry alpha per colour row, not per face: keep the faces
        if len(sel) and px[..., 3].min() < 0.999 and 'palette' not in img.name.lower():
            cuv = UV[tl[sel]].mean(1)
            cuv = cuv - np.floor(cuv)
            a = px[np.clip((cuv[:, 1] * h).astype(int), 0, h - 1), np.clip((cuv[:, 0] * w).astype(int), 0, w - 1), 3]
            cut = a < 0.5
            out[m.name] = int(cut.sum())
            if cut.all():
                drop_slots.append(i)
            else:
                cut_polys.update(int(p) for p in tpoly[sel[cut]])
        make_opaque(m)
    if cut_polys:
        delete_faces(me, sorted(cut_polys))
    if drop_slots:
        delete_slots(me, drop_slots)
    return out


def matte(me):
    """Cel shading only reads albedo: keep every material non-metallic, dry and unemissive so the GLB reads the same
    in any viewer (several Sketchfab sources ship metallic 0.4-1.0 and KHR specular)."""
    for m in me.materials:
        if m is None or not m.use_nodes:
            continue
        for nd in m.node_tree.nodes:
            if nd.type != 'BSDF_PRINCIPLED':
                continue
            for name in ('Metallic', 'Roughness'):
                for lk in list(nd.inputs[name].links):
                    m.node_tree.links.remove(lk)
            nd.inputs['Metallic'].default_value = 0.0
            nd.inputs['Roughness'].default_value = 0.85
            for name in ('Specular IOR Level', 'Emission Strength', 'Coat Weight', 'Sheen Weight'):
                if name in nd.inputs:
                    nd.inputs[name].default_value = 0.0


# ------------------------------------------------------------------------------------------ normals
def smooth_normals(me, merge=0.0008, angle_deg=60.0):
    """Weld duplicate vertices, make face winding consistent and shade smooth with an angle limit: several
    Sketchfab sources ship split/flipped normals that the cel ramp turns into brown or gold blotches."""
    import math
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    H = max(v.co.z for v in bm.verts) if bm.verts else 1.0
    if merge > 0:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge * H)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()
    if hasattr(me, 'has_custom_normals') and me.has_custom_normals:
        me.free_normals_split() if hasattr(me, 'free_normals_split') else None


def relaxed_normals(me, iters=12, lam=0.5):
    """Custom vertex normals taken from a Laplacian-smoothed copy of the surface, so lumpy low-quality meshes
    (Pikachu) light as one smooth form instead of blotches.  Geometry itself is untouched."""
    V = verts(me)
    n = len(V)
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', e)
    e = e.reshape(-1, 2)
    P = V.copy()
    deg = np.bincount(np.concatenate([e[:, 0], e[:, 1]]), minlength=n).astype(float)
    deg[deg == 0] = 1
    for _ in range(iters):
        acc = np.zeros_like(P)
        np.add.at(acc, e[:, 0], P[e[:, 1]])
        np.add.at(acc, e[:, 1], P[e[:, 0]])
        P = P + lam * (acc / deg[:, None] - P)
    _, tv, _, _ = loop_tris(me)
    a, b, c = P[tv[:, 0]], P[tv[:, 1]], P[tv[:, 2]]
    fn = np.cross(b - a, c - a)          # area-weighted
    vn = np.zeros_like(P)
    for k in range(3):
        np.add.at(vn, tv[:, k], fn)
    ln = np.linalg.norm(vn, axis=1, keepdims=True)
    ln[ln == 0] = 1
    vn /= ln
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.normals_split_custom_set_from_vertices([tuple(x) for x in vn])


# ------------------------------------------------------------------------------------------ stray pieces
def island_labels(me):
    """Connected-component id per vertex (edge connectivity)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(me.vertices)
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', e)
    e = e.reshape(-1, 2)
    g = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    return connected_components(g, directed=False)[1]


def island_report(me, far=1.5, small=0.04):
    """Islands that float away from the body: [(island, vertex_count, tri_share, dist_over_R)].  The body centre
    and radius R are robust (median / 85th percentile of the vertices), so one far-away prop cannot drag them."""
    V = verts(me)
    lab = island_labels(me)
    c = np.median(V, axis=0)
    R = float(np.percentile(np.linalg.norm(V - c, axis=1), 85)) + 1e-6
    out = []
    total = len(V)
    for i in np.unique(lab):
        m = lab == i
        d = float(np.linalg.norm(V[m] - c, axis=1).min()) / R
        share = m.sum() / total
        if d > far and share < small:
            out.append((int(i), int(m.sum()), round(share, 4), round(d, 2)))
    return out, lab


def remove_strays(me, far=1.5, small=0.04):
    """Delete small islands that sit far outside the body (helper props, detached debris such as Alakazam's two
    spoons floating a body-length away).  Returns the number of vertices removed."""
    import bmesh
    rep, lab = island_report(me, far, small)
    if not rep:
        return 0
    kill = {r[0] for r in rep}
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if int(lab[v.index]) in kill], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    me.update()
    return sum(r[1] for r in rep)


def outlier_ratio(me):
    """Full bounding-box diagonal over the 0.5-99.5 percentile diagonal: ~1.0 for a compact body, well above 1.2
    when a few vertices (floating props) stretch the box."""
    V = verts(me)
    full = np.linalg.norm(V.max(0) - V.min(0))
    core = np.linalg.norm(np.percentile(V, 99.5, axis=0) - np.percentile(V, 0.5, axis=0))
    return round(float(full / max(core, 1e-6)), 3)


def fill_transparent(me, mat_name, rgb):
    """Replace the transparent texels of one material's atlas by a solid colour and make the atlas fully opaque."""
    for m in me.materials:
        if m is None or m.name != mat_name:
            continue
        img = mat_image(m)
        if img is None or img.size[0] == 0:
            continue
        px = read_px(img)
        hole = px[..., 3] < 0.5
        px[hole, :3] = np.array(rgb, dtype=np.float32)
        px[..., 3] = 1.0
        write_px(img, px)


# ------------------------------------------------------------------------------------------ colour match
def _rgb2hls(a):
    mx, mn = a.max(-1), a.min(-1)
    l = (mx + mn) / 2
    d = mx - mn
    s = np.where(d < 1e-6, 0, d / np.maximum(1e-6, np.where(l > 0.5, 2 - mx - mn, mx + mn)))
    dd = np.maximum(d, 1e-6)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) / 6
    return np.stack([np.where(d < 1e-6, 0, h), l, s], -1)


def _hls2rgb(hls):
    h, l, s = hls[..., 0], hls[..., 1], hls[..., 2]
    q = np.where(l < 0.5, l * (1 + s), l + s - l * s)
    p = 2 * l - q

    def f(t):
        t = t % 1.0
        return np.where(t < 1 / 6, p + (q - p) * 6 * t, np.where(t < 0.5, q, np.where(t < 2 / 3, p + (q - p) * (2 / 3 - t) * 6, p)))
    return np.stack([f(h + 1 / 3), f(h), f(h - 1 / 3)], -1)


def retint(me, mat_name, target_rgb, max_hue_deg=25.0):
    """Pull a material's atlas toward the species' upstream sprite colour (mons.json palette): same hue family, the
    sprite's saturation and lightness.  Sketchfab sources are often far more saturated than the Pokedex colour, which
    the cel ramp turns into gold/brown blotches."""
    for m in me.materials:
        if m is None or m.name != mat_name:
            continue
        img = mat_image(m)
        if img is None or img.size[0] == 0:
            continue
        px = read_px(img)
        hls = _rgb2hls(px[..., :3])
        keep = (hls[..., 1] > 0.15) & (hls[..., 1] < 0.95) & (hls[..., 2] > 0.35)   # the body colour, not eyes/lines
        if keep.sum() < 50:
            continue
        cur = np.array([np.median(hls[..., 0][keep]), np.median(hls[..., 1][keep]), np.median(hls[..., 2][keep])])
        tgt = _rgb2hls(np.array(target_rgb, dtype=np.float32)[None])[0]
        dh = ((tgt[0] - cur[0] + 0.5) % 1.0) - 0.5
        dh = float(np.clip(dh, -max_hue_deg / 360.0, max_hue_deg / 360.0))
        out = hls.copy()
        w = keep[..., None]
        out[..., 0] = np.where(keep, (hls[..., 0] + dh) % 1.0, hls[..., 0])
        out[..., 1] = np.where(keep, np.clip(hls[..., 1] * tgt[1] / max(cur[1], 1e-3), 0, 1), hls[..., 1])
        out[..., 2] = np.where(keep, np.clip(hls[..., 2] * tgt[2] / max(cur[2], 1e-3), 0, 1), hls[..., 2])
        px[..., :3] = _hls2rgb(out)
        write_px(img, px)

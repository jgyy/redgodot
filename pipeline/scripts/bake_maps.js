// Bakes every map of the upstream game into the data the Godot 3D overworld builds itself from:
//
//   godot/assets/maps/<Map>.json        label grid (with margin), trees, tall grass, flowers, 3D blocks, lights
//   godot/assets/maps/<Map>_ground.png  the flat ground layer: upstream's own ground painter + every flat decal
//                                       (paths, curbs, ledges, cliffs, water, bridges, floors, mats, stairs...) and
//                                       the soft shadows objects cast, but WITHOUT anything modelled in 3D
//   godot/assets/maps/<Map>_atlas.png   every 3D-modelled object (buildings, walls, furniture, fences, signs...)
//                                       painted in isolation by upstream's own painters and packed into an atlas;
//                                       the Godot side extrudes them into boxes / roofs / cards whose UVs are the
//                                       oblique projection of the 2D art, so from the game camera each object reads
//                                       exactly like the 2D game while being real geometry.
//   godot/assets/maps/<Map>_water.png   (outdoor maps with water) R = animated-water mask, G = distance to shore
//                                       (0..9 scaled x25), B = the static "deep patch" bit of waterColor()
//   godot/assets/maps/noise_water.png   upstream's N.water noise texture (for the water shader)
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/bake_maps.js [MapName ...]
'use strict';
const path = require('path');
const fs = require('fs');
const U = require('./lib/upstream');
const { G } = U.load();
const { Surface, hash2 } = G.gfx;
const T = G.terrain, P = G.PAL;

const OUT = path.join(__dirname, '..', '..', 'godot', 'assets', 'maps');
fs.mkdirSync(OUT, { recursive: true });

// margins (cells) baked around outdoor maps: the 3D camera sees further up/sideways than the 2D 320x180 view
const OMX = 14, OMY = 10;
// interiors: upstream draws void (black) around the room
const IMX = 2, IMY = 2;

const MATOF = { grass: 1, path: 2, sand: 3, pave: 4, water: 5, rock: 6, floor: 7 };
const DEFAULT_GROUND = {
  tree: 'grass', tree2: 'grass', cut_tree: 'grass', fence: 'path', sign: 'path', ledge_d: 'grass', ledge_l: 'grass', ledge_r: 'grass',
  cliff: 'rock', cave_door: 'rock', roof_house: 'path', roof_flat: 'path', wall: 'path', window: 'path', door: 'path',
  sign_poke: 'path', sign_mart: 'path', sign_gym: 'path',
};
const FLOWER_COLORS = ['red', 'yellow', 'white', 'pink'];

// ---------------------------------------------------------------- isolation helpers
// An object is painted twice: onto the real ground (so the shadows it casts land there) and onto transparent
// scratch layers (to get its own pixels). Wherever the object has pixels, the ground is put back as it was.
class Iso {
  constructor(W, H) { this.W = W; this.H = H; this.s = new Surface(W, H); this.up = new Surface(W, H); }
  // run painter(sTarget, upTarget) for both targets; region = [x0,y0,x1,y1] px window the painter may touch
  paint(ground, groundUp, region, painter) {
    const [rx0, ry0, rx1, ry1] = clampR(region, this.W, this.H);
    const snap = copyRegion(ground, rx0, ry0, rx1, ry1);
    painter(ground, groundUp || new NullSurf());
    painter(this.s, this.up);
    // collect
    let bx0 = 1e9, by0 = 1e9, bx1 = -1, by1 = -1;
    const W = this.W;
    for (let y = ry0; y < ry1; y++) for (let x = rx0; x < rx1; x++) {
      const i = y * W + x;
      if ((this.s.data[i] >>> 24) || (this.up.data[i] >>> 24)) { if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; if (y < by0) by0 = y; if (y > by1) by1 = y; }
    }
    if (bx1 < 0) return null;
    const w = bx1 - bx0 + 1, h = by1 - by0 + 1, spr = new Surface(w, h);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = (by0 + y) * W + bx0 + x;
      let c = this.up.data[i]; if (!(c >>> 24)) c = this.s.data[i];
      spr.data[y * w + x] = c;
      if (c >>> 24) ground.data[i] = snap.data[(by0 + y - ry0) * snap.w + (bx0 + x - rx0)];
    }
    // clear scratch
    for (let y = ry0; y < ry1; y++) { this.s.data.fill(0, y * W + rx0, y * W + rx1); this.up.data.fill(0, y * W + rx0, y * W + rx1); }
    return { spr, x: bx0, y: by0 };
  }
}
class NullSurf { constructor() { this.w = 1e6; this.h = 1e6; this.data = { set() {} }; } pset() {} pmul() {} blit() {} rect() {} pblend() {} ellipse() {} ellipseMul() {} ellipseBlend() {} disc() {} hline() {} vline() {} line() {} }
function clampR(r, W, H) { return [Math.max(0, r[0] | 0), Math.max(0, r[1] | 0), Math.min(W, r[2] | 0), Math.min(H, r[3] | 0)]; }
function copyRegion(s, x0, y0, x1, y1) {
  const o = new Surface(Math.max(1, x1 - x0), Math.max(1, y1 - y0));
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) o.data[(y - y0) * o.w + (x - x0)] = s.data[y * s.w + x];
  return o;
}

// ---------------------------------------------------------------- atlas
class Atlas {
  constructor() { this.items = []; }
  add(spr) { const it = { spr, ax: 0, ay: 0 }; this.items.push(it); return it; }
  pack() {
    const PAD = 2;
    const maxW = this.items.reduce((m, it) => Math.max(m, it.spr.w + PAD), 0);
    const area = this.items.reduce((a, it) => a + (it.spr.w + PAD) * (it.spr.h + PAD), 0);
    let W = 256; while (W < maxW || W * W < area * 1.3) W *= 2; W = Math.min(Math.max(W, maxW), 4096);
    const order = this.items.slice().sort((a, b) => b.spr.h - a.spr.h);
    let x = 0, y = 0, rowH = 0;
    for (const it of order) {
      if (x + it.spr.w + PAD > W) { x = 0; y += rowH; rowH = 0; }
      it.ax = x + 1; it.ay = y + 1; x += it.spr.w + PAD; rowH = Math.max(rowH, it.spr.h + PAD);
    }
    const H = Math.max(4, y + rowH);
    const s = new Surface(W, H);
    for (const it of this.items) s.blit(it.spr, it.ax, it.ay);
    this.surf = s; this.W = W; this.H = H;
    return s;
  }
}

// ---------------------------------------------------------------- shared
function labelGrid(L, cw, ch, MX, MY) {
  const legend = [], idx = {}, grid = [];
  for (let y = 0; y < ch; y++) for (let x = 0; x < cw; x++) {
    const l = L(x - MX, y - MY) || 'void';
    if (!(l in idx)) { idx[l] = legend.length; legend.push(l); }
    grid.push(idx[l]);
  }
  return { legend, grid };
}
function objEntry(atlas, iso, shape) {
  if (!iso) return null;
  const it = atlas.add(iso.spr);
  return Object.assign({ sx: iso.x, sy: iso.y, w: iso.spr.w, h: iso.spr.h, _it: it }, shape);
}
function finishBlocks(blocks) {
  return blocks.filter(Boolean).map(b => { const it = b._it; delete b._it; b.ax = it.ax; b.ay = it.ay; return b; });
}

// ---------------------------------------------------------------- outdoor (overworld / plateau / forest / port)
function bakeOutdoor(map) {
  const MX = OMX, MY = OMY;
  const cw = map.w + MX * 2, ch = map.h + MY * 2, W = cw * 16, H = ch * 16;
  const s = new Surface(W, H), up = new Surface(W, H);
  const Lraw = (cx, cy) => map.labelAt(cx, cy);
  const lab = [];
  for (let y = -1; y <= ch; y++) { const row = []; for (let x = -1; x <= cw; x++) row.push(Lraw(x - MX, y - MY)); lab.push(row); }
  const L = (cx, cy) => { const r = lab[cy + MY + 1]; if (!r) return Lraw(cx, cy); const v = r[cx + MX + 1]; return v === undefined ? Lraw(cx, cy) : v; };
  const gk = new Array((cw + 2) * (ch + 2)).fill(null);
  const GI = (x, y) => (y + 1) * (cw + 2) + (x + 1);
  for (let y = -1; y <= ch; y++) for (let x = -1; x <= cw; x++) gk[GI(x, y)] = G.GROUND[L(x - MX, y - MY)] || null;
  for (let pass = 0; pass < 3; pass++) {
    const nx = gk.slice();
    for (let y = -1; y <= ch; y++) for (let x = -1; x <= cw; x++) {
      if (gk[GI(x, y)]) continue;
      const votes = {};
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dy) continue; const xx = x + dx, yy = y + dy;
        if (xx < -1 || yy < -1 || xx > cw || yy > ch) continue;
        const k = gk[GI(xx, yy)]; if (k && k !== 'water') votes[k] = (votes[k] || 0) + (dx && dy ? 1 : 2);
      }
      let best = null, bv = 0; for (const k in votes) if (votes[k] > bv) { bv = votes[k]; best = k; }
      if (best) nx[GI(x, y)] = best;
    }
    for (let i = 0; i < gk.length; i++) gk[i] = nx[i];
  }
  for (let y = -1; y <= ch; y++) for (let x = -1; x <= cw; x++) if (!gk[GI(x, y)]) gk[GI(x, y)] = DEFAULT_GROUND[L(x - MX, y - MY)] || 'grass';
  const kind = (x, y) => { if (x < -1 || y < -1 || x > cw || y > ch) return MATOF.grass; return MATOF[gk[GI(x, y)]] || MATOF.grass; };
  const worldX = map.world ? map.world.x : 0, worldY = map.world ? map.world.y : 0;
  const wx0 = worldX * 16 - MX * 16, wy0 = worldY * 16 - MY * 16;
  const ground = T.paintGround(s, { kind, theme: map.tsFile === 'forest' && !/Safari/.test(map.name) ? 'forest' : null }, wx0, wy0);

  const iso = new Iso(W, H), atlas = new Atlas();
  const blocks = [], trees = [], grass = [], flowers = [], lights = [], fires = [];
  const Lsurf = (x, y) => L(x - MX, y - MY);

  // ---- buildings
  const blds = G.buildings.findBuildings(cw, ch, Lsurf).map(c => G.buildings.describe(c, Lsurf));
  for (const b of blds) {
    const opts = { wx: worldX - MX, wy: worldY - MY, isDoor: (x, y) => map.isDoorTile(x - MX, y - MY) && G.buildings.BLD.has(Lsurf(x, y)) && Lsurf(x, y + 1) !== Lsurf(x, y) };
    const ov = G.buildingStyles && G.buildingStyles(map, b, MX, MY);
    if (ov) Object.assign(opts, ov);
    const region = [b.x0 * 16 - 8, b.y0 * 16 - 24, (b.x1 + 1) * 16 + 8, (b.y1 + 1) * 16 + 8];
    const r = iso.paint(s, up, region, (S, UP) => G.buildings.paintBuilding(S, UP, b, Lsurf, 0, 0, opts));
    const px0 = b.x0 * 16, py0 = b.y0 * 16, Wb = (b.x1 - b.x0 + 1) * 16, Hb = (b.y1 - b.y0 + 1) * 16;
    const wallRows = b.y1 - b.y0 + 1 - b.roofRows;
    if (b.type === 'terrace') {
      blocks.push(objEntry(atlas, r, { t: 'terrace', cells: b.cells.map(([x, y]) => [x, y]) }));
    } else {
      const roofTop = py0 - 5, roofBottom = py0 + b.roofRows * 16 + (wallRows >= 2 ? 5 : 1);
      const seed = hash2(b.x0 + opts.wx, b.y0 + opts.wy, 7);
      const e = { t: 'house', x0: px0, x1: px0 + Wb, roofTop, wallTop: roofBottom, wallBottom: py0 + Hb, flat: b.type === 'big' && !opts.pitched, type: b.type };
      if (b.type === 'house' && Wb >= 48) e.chimney = [px0 + Math.floor(Wb * (seed < 0.5 ? 0.72 : 0.22)), roofTop - 5];
      blocks.push(objEntry(atlas, r, e));
    }
    if (b.type !== 'terrace') for (const [bx, by] of b.cells) { const l = Lsurf(bx, by); if (l === 'window' || l === 'door' || l === 'sign_poke' || l === 'sign_mart') lights.push([bx * 16 + 8, by * 16 + 9, l]); }
  }
  // ---- ships (flat: drawn straight onto the ground, upper layer included)
  {
    const seen = new Set();
    for (let y = 0; y < ch; y++) for (let x = 0; x < cw; x++) {
      const l = L(x - MX, y - MY); if ((l !== 'deck' && l !== 'ship_wall') || seen.has(x + ',' + y)) continue;
      const st = [[x, y]], cells = []; seen.add(x + ',' + y);
      while (st.length) { const [a, b2] = st.pop(); cells.push([a, b2]); for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const k = (a + dx) + ',' + (b2 + dy); const l2 = L(a + dx - MX, b2 + dy - MY); if (!seen.has(k) && (l2 === 'deck' || l2 === 'ship_wall')) { seen.add(k); st.push([a + dx, b2 + dy]); } } }
      if (cells.length >= 6) T.paintShip(s, s, cells, 0, 0);
    }
  }
  // ---- cell objects, top to bottom
  for (let y = -1; y < ch; y++) for (let x = 0; x < cw; x++) {
    const l = L(x - MX, y - MY), px = x * 16, py = y * 16;
    const LL = (cx, cy) => L(cx - MX, cy - MY);
    // upstream hashes variants with its own surface coords (margin 11 x 7): keep them identical
    const ux = x - MX + 11, uy = y - MY + 7;
    const LU = (cx, cy) => L(cx - 11, cy - 7);
    const win = [px - 16, py - 32, px + 32, py + 32];
    switch (l) {
      case 'tree': case 'tree2': {
        const v = Math.floor(hash2(ux + worldX, uy + worldY, 3) * 6);
        T.drawShadowEllipse(s, px + 9, py + 14, 7, 2.5, 0.8);
        trees.push([x, y, l === 'tree2' ? 1 : 0, v]);
        break;
      }
      case 'cut_tree': {
        const v = Math.floor(hash2(ux, uy, 5) * 3);
        const r = iso.paint(s, up, win, (S, UP) => { T.drawShadowEllipse(S, px + 9, py + 14, 6, 2, 0.7); const spr = T.cutTreeSprite(v); S.blit(spr, px, py - 2, { sy: 2 }); UP.blit(spr, px, py - 2, { sh: 2 }); });
        blocks.push(objEntry(atlas, r, { t: 'card', z: py + 15, lbl: l }));
        break;
      }
      case 'fence': {
        const vert = LL(x - 1, y) !== 'fence' && LL(x + 1, y) !== 'fence' && (LL(x, y - 1) === 'fence' || LL(x, y + 1) === 'fence');
        const r = iso.paint(s, up, win, (S) => T.paintFence(S, px, py, LU, ux, uy));
        blocks.push(objEntry(atlas, r, vert ? { t: 'box', hgt: 5, lbl: l } : { t: 'card', z: py + 16, lbl: l }));
        break;
      }
      case 'sign': {
        const r = iso.paint(s, up, win, (S) => T.paintSign(S, px, py));
        blocks.push(objEntry(atlas, r, { t: 'card', z: py + 15, lbl: l }));
        break;
      }
      case 'ledge_d': T.paintLedge(s, px, py, LU, ux, uy, 'd'); break;
      case 'ledge_l': T.paintLedge(s, px, py, LU, ux, uy, 'l'); break;
      case 'ledge_r': T.paintLedge(s, px, py, LU, ux, uy, 'r'); break;
      case 'cliff': T.paintCliff(s, px, py, LU, ux, uy); break;
      case 'cliff_top': T.paintCliffTopEdges(s, px, py, LU, ux, uy); break;
      case 'cave_door': T.paintCaveDoor(s, px, py, LU, ux, uy); break;
      case 'bridge': T.paintBridge(s, px, py, LU, ux, uy); break;
      case 'stairs_wood': T.paintStairs(s, px, py); break;
      case 'curb': { const q = map.inside(x - MX, y - MY) ? map.quad(x - MX, y - MY) : null; if (q) T.paintCurb(s, px, py, q); break; }
      case 'flowers': {
        const c = Math.floor(hash2(ux + worldX, uy + worldY, 8) * 4);
        // drawn as animated decor cards in 3D (TileKit), not into the ground
        flowers.push([x, y, c, (x + y) % 2]);
        break;
      }
      case 'tall_grass': grass.push([x, y, Math.floor(hash2(ux + worldX, uy + worldY, 9) * 4)]); break;
      case 'unknown': break;
      case 'pillar': {
        const r = iso.paint(s, up, win, (S, UP) => T.paintPillar(S, UP, px, py, LU, ux, uy));
        blocks.push(objEntry(atlas, r, { t: 'box', hgt: 16, lbl: l }));
        break;
      }
      case 'statue':
        if (map.tsFile === 'plateau') {
          const r = iso.paint(s, up, win, (S, UP) => T.paintBrazier(S, UP, px, py));
          blocks.push(objEntry(atlas, r, { t: 'box', hgt: 9, lbl: 'brazier' }));
          if (y >= 0) { fires.push([px + 8, py + 2, ux * 7 + uy * 3]); lights.push([px + 8, py - 2, 'fire']); }
        } else {
          const r = iso.paint(s, up, [px - 16, py - 48, px + 32, py + 48], (S, UP) => T.paintStatue(S, UP, px, py, LU, ux, uy, map.name, worldX, worldY));
          if (r) blocks.push(objEntry(atlas, r, { t: 'card', z: r.y + r.spr.h - 1, lbl: l }));
        }
        break;
      case 'crate': {
        const r = iso.paint(s, up, win, (S) => T.paintCrate(S, px, py));
        blocks.push(objEntry(atlas, r, { t: 'box', hgt: 10, lbl: l }));
        break;
      }
      case 'machine': {
        const r = iso.paint(s, up, [px - 8, py - 16, px + 48, py + 32], (S, UP) => T.paintTruck(S, UP, px, py, LU, ux, uy));
        if (r) blocks.push(objEntry(atlas, r, { t: 'box', hgt: 14, lbl: 'truck' }));
        break;
      }
    }
  }
  G.mapRender.elevationEdges(s, map, MX * 16, MY * 16);
  // water mask (pixels still showing base water)
  let anyWater = false;
  const wtex = new Surface(W, H); wtex.clear(G.gfx.rgb(0, 0, 0, 255));  // opaque: the importer bleeds colour into transparent px
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    if (ground.mat[i] === MATOF.water && s.data[i] === T.waterColor(wx0 + x, wy0 + y, ground.wdist[i], 0)) {
      anyWater = true;
      const deep = G.noise.big.at((wx0 + x) >> 1, (wy0 + y) >> 1) < 0.4 ? 255 : 0;
      wtex.data[i] = G.gfx.rgb(255, ground.wdist[i] * 25, deep, 255);
    }
  }
  return finish(map, { MX, MY, cw, ch, s, atlas, blocks, trees, grass, flowers, lights, fires, L, wtex: anyWater ? wtex : null, kind: map.outdoor ? 'outdoor' : 'field', wx0, wy0 });
}

// ---------------------------------------------------------------- interiors & dungeons
const WALLISH = new Set(['wall', 'levy_sign', 'wall_surf', 'wall_window', 'wall_deco', 'cave_wall', 'ship_wall', 'porthole', 'window_big', 'board', 'door']);
const FLAT_INT = new Set(['void', 'unknown', 'mat', 'stairs_up', 'stairs_down', 'ladder_up', 'ladder_down', 'hole', 'spinner_up', 'spinner_down', 'spinner_left', 'spinner_right', 'spinner_stop', 'teleport', 'barrier', 'water', 'cave_ledge', 'flowers', 'glass', 'railing']);
// extrusion height (px of front face) for furniture boxes; 'card' = stands up as a vertical sprite
const FURN_H = {
  table: 5, desk: 5, counter: 9, bookshelf: 'full', shelf: 'full', cabinet: 12, pc: 8, pc_claude: 8, heal_machine: 7, tv: 6, tv_woc: 6,
  console: 3, display: 6, fossil: 5, sink: 6, stove: 8, fridge: 12, machine: 8, trash: 9, crate: 8, vending: 12, slots: 12, chair: 4,
  bench: 4, bed: 3, laptop: 'card', plant: 'card', lamp: 'card', barrel: 'card', grave: 6, statue: 'card', gym_statue: 'card',
  cave_rock: 6, cut_tree: 'card', sign: 'card', pillar: 'full',
};
function bakeInterior(map) {
  const MX = IMX, MY = IMY;
  const cw = map.w + MX * 2, ch = map.h + MY * 2, W = cw * 16, H = ch * 16;
  const s = new Surface(W, H); s.clear(P.black);
  const up = new Surface(W, H);
  const I = G.interior;
  const th = I.themeFor(map.name, map.tsFile);
  const L = (x, y) => map.inside(x, y) ? map.label(x, y) : 'void';
  const FLOORS = new Set(['floor', 'floor_tile', 'floor_carpet', 'floor_stone', 'floor_dojo', 'floor_tower', 'ship_floor', 'deck', 'cave_floor', 'cave_floor2', 'cave_high', 'grass']);
  const isWallish = l => l === 'wall' || l === 'levy_sign' || l === 'wall_surf' || l === 'wall_window' || l === 'wall_deco' || l === 'void' || l === 'cave_wall' || l === 'ship_wall' || l === 'porthole' || l === 'window_big' || l === 'pillar';
  const floorAt = (x, y) => {
    const l = L(x, y); if (FLOORS.has(l)) return l;
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0], [1, 1], [-1, 1]]) { const k = L(x + dx, y + dy); if (FLOORS.has(k)) return k; }
    return map.tsFile === 'cavern' ? 'cave_floor' : map.tsFile === 'ship' ? 'ship_floor' : th.tile ? 'floor_tile' : 'floor';
  };
  const ox = MX * 16, oy = MY * 16;
  for (let y = 0; y < map.h; y++) for (let x = 0; x < map.w; x++) {
    const l = L(x, y);
    if (l === 'void' || l === 'unknown') continue;
    if (isWallish(l) && !FLOORS.has(l) && l !== 'pillar') continue;
    const fk = floorAt(x, y);
    const px = ox + x * 16, py = oy + y * 16;
    for (let yy = 0; yy < 16; yy++) for (let xx = 0; xx < 16; xx++) s.pset(px + xx, py + yy, I.floorPixel(fk, x * 16 + xx, y * 16 + yy, th));
    if (fk === 'floor_carpet') carpetEdges(s, px, py, x, y, L, th);
  }
  G.mapRender.elevationEdges(s, map, ox, oy);
  const iso = new Iso(W, H), atlas = new Atlas();
  const blocks = [], trees = [], lights = [], fx = [];
  const done = new Set();
  const anim = [];
  const PAINT = I.PAINT;
  const paintCells = (cells, S, UP) => { for (const [x, y] of cells) { const l = L(x, y), P2 = PAINT[l]; if (P2) P2(S, UP, ox + x * 16, oy + y * 16, x, y, L, th, anim, map); } };
  const comp = (x0, y0, pred) => { // 4-connected component of cells satisfying pred
    const st = [[x0, y0]], out = []; done.add(x0 + ',' + y0);
    while (st.length) { const [x, y] = st.pop(); out.push([x, y]); for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const k = (x + dx) + ',' + (y + dy); if (!done.has(k) && map.inside(x + dx, y + dy) && pred(L(x + dx, y + dy))) { done.add(k); st.push([x + dx, y + dy]); } } }
    return out;
  };
  for (let y = 0; y < map.h; y++) for (let x = 0; x < map.w; x++) {
    const l = L(x, y), px = ox + x * 16, py = oy + y * 16;
    if (done.has(x + ',' + y)) continue;
    if (l === 'tree' || l === 'tree2') { done.add(x + ',' + y); T.drawShadowEllipse(s, px + 9, py + 14, 7, 2.5, 0.8); trees.push([x + MX, y + MY, l === 'tree2' ? 1 : 0, Math.floor(hash2(x, y, 3) * 6)]); continue; }
    if (l === 'barrier' || l === 'teleport') fx.push([x + MX, y + MY, l]);
    if (FLAT_INT.has(l) || FLOORS.has(l) || !PAINT[l]) { done.add(x + ',' + y); if (PAINT[l] && !FLOORS.has(l)) PAINT[l](s, s, px, py, x, y, L, th, anim, map); continue; }
    if (WALLISH.has(l)) {
      // a wall region: every column's run of wall cells becomes one extruded block (front face at the bottom)
      const cells = comp(x, y, k => WALLISH.has(k));
      const cave = l === 'cave_wall';
      const xs = [...new Set(cells.map(c => c[0]))];
      const r = iso.paint(s, up, regionOf(cells, ox, oy, 16), (S, UP) => paintCells(cells, S, UP));
      const set = new Set(cells.map(c => c[0] + ',' + c[1]));
      const runs = [];
      for (const cx of xs) {
        const ys = cells.filter(c => c[0] === cx).map(c => c[1]).sort((a, b) => a - b);
        let a = ys[0], prev = ys[0];
        for (let i = 1; i <= ys.length; i++) {
          if (i < ys.length && ys[i] === prev + 1) { prev = ys[i]; continue; }
          runs.push([cx, a, prev]); if (i < ys.length) { a = ys[i]; prev = ys[i]; }
        }
      }
      // merge horizontally adjacent runs with the same extent into one box
      runs.sort((p, q) => p[1] - q[1] || p[2] - q[2] || p[0] - q[0]);
      const boxes = [];
      for (const [cx, a, b2] of runs) {
        const last = boxes[boxes.length - 1];
        if (last && last.a === a && last.b === b2 && last.x1 === cx) last.x1 = cx + 1; else boxes.push({ x0: cx, x1: cx + 1, a, b: b2 });
      }
      const e = objEntry(atlas, r, { t: 'walls', cave, boxes: boxes.map(bx => {
        const run = (bx.b - bx.a + 1) * 16;
        // tall walls lean in perspective: keep them low (thin wall runs lower still), the rest of the art lies on top
        const hgt = Math.min(run, cave ? 18 : 24, run > 32 ? (bx.x1 - bx.x0) * 16 : 99);
        const openBelow = !set.has(bx.x0 + ',' + (bx.b + 1));
        return [ox + bx.x0 * 16, oy + bx.a * 16, ox + bx.x1 * 16, oy + (bx.b + 1) * 16 + (openBelow && cave ? 2 : 0), hgt];
      }) });
      blocks.push(e);
      for (const [cx, cy] of cells) { const k = L(cx, cy); if (k === 'wall_window' || k === 'window_big') lights.push([ox + cx * 16 + 8, oy + cy * 16 + 8, 'window']); }
      continue;
    }
    // furniture: a component of same-label cells
    const cells = comp(x, y, k => k === l);
    const r = iso.paint(s, up, regionOf(cells, ox, oy, 24), (S, UP) => paintCells(cells, S, UP));
    if (!r) continue;
    let hgt = FURN_H[l] === undefined ? 6 : FURN_H[l];
    const e = { lbl: l };
    if (hgt === 'card') Object.assign(e, { t: 'card', z: r.y + r.spr.h });
    else {
      if (hgt === 'full') hgt = Math.max(4, Math.min(24, r.spr.h - 3));
      const rect = isRect(cells);
      Object.assign(e, rect ? { t: 'box', hgt: Math.min(hgt, r.spr.h - 1) } : { t: 'cellboxes', hgt: Math.min(hgt, 15), cells: cells.map(([cx, cy]) => [ox + cx * 16, oy + cy * 16]) });
    }
    blocks.push(objEntry(atlas, r, e));
    if (l === 'lamp') lights.push([ox + x * 16 + 8, oy + y * 16 + 4, 'lamp']);
  }
  // contact shadows under furniture onto floor
  const FURN = new Set(['table', 'chair', 'bed', 'tv', 'tv_woc', 'laptop', 'pc_claude', 'console', 'pc', 'bookshelf', 'shelf', 'cabinet', 'plant', 'counter', 'heal_machine', 'display', 'desk', 'sink', 'stove', 'fridge', 'machine', 'statue', 'gym_statue', 'trash', 'crate', 'barrel', 'board', 'vending', 'slots', 'lamp', 'bench', 'fossil', 'grave', 'cave_rock']);
  const SH = G.gfx.rgb(150, 150, 185);
  for (let y = 0; y < map.h; y++) for (let x = 0; x < map.w; x++) {
    if (!FURN.has(L(x, y))) continue;
    if (FLOORS.has(L(x, y + 1)) || L(x, y + 1) === 'mat') for (let xx = 1; xx < 16; xx++) { s.pmul(ox + x * 16 + xx, oy + (y + 1) * 16, SH); if (xx % 2) s.pmul(ox + x * 16 + xx, oy + (y + 1) * 16 + 1, SH); }
    if (FLOORS.has(L(x + 1, y))) for (let yy = 2; yy < 16; yy++) s.pmul(ox + (x + 1) * 16, oy + y * 16 + yy, SH);
  }
  const Lm = (x, y) => L(x, y);
  return finish(map, { MX, MY, cw, ch, s, atlas, blocks, trees, grass: [], flowers: [], lights, fires: [], fx, L: Lm, wtex: null, kind: 'interior', wx0: 0, wy0: 0 });
}
function regionOf(cells, ox, oy, pad) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const [x, y] of cells) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return [ox + x0 * 16 - pad, oy + y0 * 16 - pad - 16, ox + (x1 + 1) * 16 + pad, oy + (y1 + 1) * 16 + pad];
}
function isRect(cells) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const [x, y] of cells) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return (x1 - x0 + 1) * (y1 - y0 + 1) === cells.length;
}
function carpetEdges(s, px, py, x, y, L, th) {
  const { hex, shade } = G.gfx;
  const c = hex(th.carpet), e = shade(c, -0.3), hi = shade(c, 0.25);
  const not = (dx, dy) => { const k = L(x + dx, y + dy); return k !== 'floor_carpet' && k !== 'mat'; };
  if (not(0, -1)) for (let i = 0; i < 16; i++) { s.pset(px + i, py, e); s.pset(px + i, py + 1, hi); }
  if (not(0, 1)) for (let i = 0; i < 16; i++) { s.pset(px + i, py + 15, e); s.pset(px + i, py + 14, shade(c, -0.12)); }
  if (not(-1, 0)) for (let i = 0; i < 16; i++) { s.pset(px, py + i, e); s.pset(px + 1, py + i, hi); }
  if (not(1, 0)) for (let i = 0; i < 16; i++) s.pset(px + 15, py + i, e);
}

// ---------------------------------------------------------------- output
function finish(map, R) {
  const name = map.name;
  const lg = labelGrid(R.L, R.cw, R.ch, R.MX, R.MY);
  const blocks = R.blocks.filter(Boolean);
  const atlasSurf = R.atlas.items.length ? R.atlas.pack() : new Surface(4, 4);
  const json = {
    map: name, kind: R.kind, w: map.w, h: map.h, mx: R.MX, my: R.MY, cw: R.cw, ch: R.ch,
    world: map.world ? [map.world.x, map.world.y] : null, wx0: R.wx0, wy0: R.wy0,
    legend: lg.legend, labels: lg.grid,
    blocks: finishBlocks(blocks), trees: R.trees, grass: R.grass, flowers: R.flowers, lights: R.lights, fires: R.fires, fx: R.fx || [],
    atlas: [R.atlas.W || 4, R.atlas.H || 4], water: !!R.wtex,
  };
  fs.writeFileSync(path.join(OUT, name + '.json'), JSON.stringify(json));
  U.savePNG(R.s, path.join(OUT, name + '_ground.png'));
  U.savePNG(atlasSurf, path.join(OUT, name + '_atlas.png'));
  if (R.wtex) U.savePNG(R.wtex, path.join(OUT, name + '_water.png'));
  return json;
}

function bakeNoise() {
  const N = G.noise.water, s = new Surface(N.size, N.size);
  for (let y = 0; y < N.size; y++) for (let x = 0; x < N.size; x++) { const v = Math.round(N.data[y * N.size + x] * 255); s.data[y * N.size + x] = G.gfx.rgb(v, v, v, 255); }
  U.savePNG(s, path.join(OUT, 'noise_water.png'));
  const B = G.noise.big, sb = new Surface(B.size, B.size);
  for (let i = 0; i < B.size * B.size; i++) { const v = Math.round(B.data[i] * 255); sb.data[i] = G.gfx.rgb(v, v, v, 255); }
  U.savePNG(sb, path.join(OUT, 'noise_big.png'));   // ambient.js cloud shadows
  // the palettes the Godot shaders quantise to
  const pal = {};
  for (const k of ['grass', 'tallgrass', 'path', 'water', 'leaf', 'leaf2', 'trunk', 'rock', 'stone', 'wood', 'cream', 'mtn', 'pave', 'sand', 'moss']) pal[k] = P[k].map(hexOf);
  pal.outline = hexOf(P.outline); pal.black = hexOf(P.black);
  pal.flower = {}; for (const k in P.flower) pal.flower[k] = P.flower[k].map(hexOf);
  fs.writeFileSync(path.join(OUT, 'palette.json'), JSON.stringify(pal, null, 1));
}
// Shape data for the Blender world-prop generator (pipeline/blender/gen_world.py): upstream's tree clump layouts
// (terrain.js treeSprite, 2 kinds x 6 variants), cut-tree clumps and the tall-grass tuft offsets (4 variants),
// evaluated here with upstream's own hash so every variant matches its 2D sprite.
function bakeWorldDefs() {
  const rnd = (x, y, s) => hash2(x, y, s || 0);
  const trees = {};
  for (const kind of ['tree', 'tree2']) for (let v = 0; v < 6; v++) {
    const seed = v * 31 + (kind === 'tree2' ? 7 : 0);
    const j = (k) => (rnd(v, k, seed) - 0.5);
    const clumps = kind === 'tree2' ? [
      { x: 8 + j(1), y: 8 + j(2), r: 6.5 }, { x: 4 + j(3), y: 12 + j(4), r: 4.6 }, { x: 12 + j(5), y: 12 + j(6), r: 4.6 },
      { x: 8 + j(7), y: 15.5 + j(8), r: 5.4 }, { x: 5 + j(9), y: 6, r: 3.5, lit: 0.1 }, { x: 11 + j(10), y: 6.5, r: 3.4, lit: 0.08 },
    ] : [
      { x: 8 + j(1), y: 6 + j(2), r: 5.5 }, { x: 3.8 + j(3), y: 10 + j(4), r: 3.9 }, { x: 12.2 + j(5), y: 10 + j(6), r: 3.9 },
      { x: 8, y: 13 + j(7), r: 5 }, { x: 5.5 + j(8), y: 4 + j(9), r: 3, lit: 0.12 }, { x: 10.5 + j(10), y: 3.6 + j(11), r: 3, lit: 0.1 },
      { x: 3.6, y: 15 + j(12), r: 2.6 }, { x: 12.4, y: 15 + j(13), r: 2.6 },
    ];
    trees[kind + v] = { kind, v, clumps, trunk: kind === 'tree2' ? [6, 20, 10, 26] : [6, 17, 10, 26], seed };
  }
  const grass = [];
  for (let v = 0; v < 4; v++) {
    const j = k => Math.floor(rnd(v, k, 77) * 3) - 1;
    grass.push([[-2 + j(1), -1 + j(2), 0], [7 + j(3), 1 + j(4), 1], [2 + j(5), 6 + j(6), 1], [10 + j(7), 7 + j(8), 0]]);
  }
  // tall grass (v x frame) and flower (colour x frame) sprites, one 16x16 tile each, for the animated decor cards
  const deco = new Surface(16 * 16, 16);
  for (let v = 0; v < 4; v++) for (let f = 0; f < 2; f++) deco.blit(T.tallGrassSprite(v, f), (v * 2 + f) * 16, 0);
  FLOWER_COLORS.forEach((c, i) => { for (let f = 0; f < 2; f++) deco.blit(T.flowerSprite(c, f), (8 + i * 2 + f) * 16, 0); });
  U.savePNG(deco, path.join(OUT, 'decor_atlas.png'));
  // small object sprites (objsprites.js ART, bottom 16x16 of the 16x24 overworld frame) for 3D cards
  const OBJ = ['poke_ball', 'boulder', 'pokedex', 'clipboard', 'paper', 'fossil', 'old_amber'];
  const os = new Surface(16 * OBJ.length, 16);
  OBJ.forEach((n, i) => { const f = G.objSprites(n, {}).down[0]; os.blit(f, i * 16, 16 - f.h); });
  U.savePNG(os, path.join(OUT, 'objects_atlas.png'));
  const tuft = ['...6....6...', '..65...654..', '..54..6544.6', '.6544.5443.5', '.5443.4433.4', '65433543323.', '54332433322.', '43322332221.', '3322122211..', '.21111111...'];
  const dir = path.join(__dirname, '..', 'blender');
  fs.writeFileSync(path.join(dir, 'world_defs.json'), JSON.stringify({ trees, grass, tuft, pal: {
    leaf: P.leaf.map(hexOf), leaf2: P.leaf2.map(hexOf), trunk: P.trunk.map(hexOf), tallgrass: P.tallgrass.map(hexOf), outline: hexOf(P.outline) } }, null, 1));
}

function hexOf(c) { return '#' + [c & 255, (c >>> 8) & 255, (c >>> 16) & 255].map(v => v.toString(16).padStart(2, '0')).join(''); }

// ---------------------------------------------------------------- main
const only = process.argv.slice(2);
const names = only.length ? only : Object.keys(G.MAPDATA.maps);
bakeNoise();
bakeWorldDefs();
let n = 0; const t0 = Date.now();
for (const name of names) {
  const map = G.maps.getMap(name);
  const j = map.interior ? bakeInterior(map) : bakeOutdoor(map);
  n++;
  if (only.length || n % 20 === 0) console.log(`[bake_maps] ${n}/${names.length} ${name} ${j.kind} ${j.cw}x${j.ch} blocks=${j.blocks.length} trees=${j.trees.length}`);
}
console.log(`[bake_maps] baked ${n} maps in ${((Date.now() - t0) / 1000).toFixed(1)}s -> ${OUT}`);

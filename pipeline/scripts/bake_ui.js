// Bakes the upstream-drawn 2D UI art that the Godot Px screens blit as textures
// (everything that is UI chrome/lettering rather than world, Pokémon or people):
//   title_logo_big.png / title_logo_red.png  logo.js G.titleLogo() (POKéMON / CLAUDE RED)
//   levy_mark.png / levy_word.png            intro.js "LEVY ST. GAMES presents" card (maskSurface)
//   townmap.png + townmap.json               townmap.js build(): Kanto minimap from every outdoor
//                                            map's real terrain, + map-centre pixels & display names
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/bake_ui.js [outdir]
'use strict';
const path = require('path');
const fs = require('fs');
const { load, savePNG } = require('./lib/upstream');

const OUT = process.argv[2] || path.join(__dirname, '..', '..', 'godot', 'assets', 'ui');
const { G } = load();
const { Surface, hex, mix, shade } = G.gfx;

// ---- title logo
const L = G.titleLogo();
savePNG(L.big, path.join(OUT, 'title_logo_big.png'));
savePNG(L.red, path.join(OUT, 'title_logo_red.png'));

// ---- LEVY ST. card (intro.js maskSurface: alpha 0-9 -> ivory on navy, one AA step)
const NAVY = hex('#141a2e'), IVORY = hex('#f3f0e9');
function maskSurface(rows) {
  const w = rows[0].length, h = rows.length, s = new Surface(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const a = +rows[y][x];
    if (a >= 6) s.data[y * w + x] = IVORY; else if (a >= 3) s.data[y * w + x] = mix(NAVY, IVORY, 0.5);
  }
  return s;
}
savePNG(maskSurface(G.LEVY_LOGO.mark), path.join(OUT, 'levy_mark.png'));
savePNG(maskSurface(G.LEVY_LOGO.word), path.join(OUT, 'levy_word.png'));

// ---- town map (verbatim port of townmap.js build())
if (G.maps.layoutWorld) G.maps.layoutWorld();
const outs = Object.keys(G.MAPDATA.maps).filter(n => ['overworld', 'plateau'].includes(G.MAPDATA.maps[n].ts)).map(n => G.maps.getMap(n)).filter(m => m.world);
let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
for (const m of outs) { x0 = Math.min(x0, m.world.x); y0 = Math.min(y0, m.world.y); x1 = Math.max(x1, m.world.x + m.w); y1 = Math.max(y1, m.world.y + m.h); }
const SC = (y1 - y0) / 158;
const W = Math.ceil((x1 - x0) / SC) + 8, H = Math.ceil((y1 - y0) / SC) + 8;
const kind = new Uint8Array(W * H);
const K = { water: 1, bridge: 1, tree: 2, tree2: 2, cut_tree: 2, grass: 3, tall_grass: 3, flowers: 3, path: 4, path_t: 4, path_tufts: 4, sand: 4, pavement: 4, curb: 4, stairs_wood: 4, fence: 4, sign: 4,
  roof_house: 5, roof_flat: 5, wall: 5, window: 5, door: 5, sign_poke: 5, sign_mart: 5, sign_gym: 5, cliff: 6, cliff_top: 6, ledge_d: 3, ledge_l: 3, ledge_r: 3, cave_door: 6, pillar: 5, statue: 5 };
const where = {};
for (const m of outs) {
  const votes = {};
  for (let y = 0; y < m.h; y++) for (let x = 0; x < m.w; x++) {
    const k = K[m.label(x, y)] || 3;
    const mx = Math.floor((m.world.x + x - x0) / SC) + 4, my = Math.floor((m.world.y + y - y0) / SC) + 4;
    const key = mx + ',' + my;
    (votes[key] = votes[key] || [0, 0, 0, 0, 0, 0, 0])[k] += k === 5 ? 3 : 1;
  }
  for (const key in votes) {
    const [mx, my] = key.split(',').map(Number), v = votes[key];
    let best = 0; for (let k = 1; k < 7; k++) if (v[k] > v[best]) best = k;
    kind[my * W + mx] = best;
  }
  where[m.name] = { x: Math.floor((m.world.x + m.w / 2 - x0) / SC) + 4, y: Math.floor((m.world.y + m.h / 2 - y0) / SC) + 4, name: G.mapDisplayName(m) };
}
const land = new Uint8Array(kind);
const q = [];
for (let i = 0; i < land.length; i++) if (land[i]) q.push(i);
const cls = new Uint8Array(W * H); for (let i = 0; i < land.length; i++) cls[i] = land[i] === 1 ? 1 : land[i] ? 7 : 0;
for (let qi = 0; qi < q.length; qi++) {
  const i = q[qi], x = i % W, y = (i / W) | 0;
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    const nx = x + dx, ny = y + dy; if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
    const j = ny * W + nx; if (cls[j]) continue;
    cls[j] = cls[i]; q.push(j);
  }
}
for (let i = 0; i < land.length; i++) if (!land[i]) land[i] = cls[i] || 1;
const s = new Surface(W, H);
const COL = [0, hex('#3c78c8'), hex('#2e6a3e'), hex('#62a852'), hex('#d8c08a'), hex('#e05a4a'), hex('#9a7a5a'), hex('#4e8a4a')];
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const k = land[y * W + x];
  let c = COL[k];
  if (k === 1) { if ((x + y * 3) % 11 === 0) c = hex('#5a98e0'); }
  else { const up = land[(y - 1) * W + x] || 1; if (up === 1) c = shade(c, 0.2); }
  if (k !== 1) for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { if ((land[(y + dy) * W + x + dx] || 1) === 1) { c = mix(c, hex('#f0e0b0'), 0.55); break; } }
  s.pset(x, y, c);
}
savePNG(s, path.join(OUT, 'townmap.png'));
const TOWNS = ['PalletTown', 'ViridianCity', 'PewterCity', 'CeruleanCity', 'LavenderTown', 'VermilionCity', 'CeladonCity', 'FuchsiaCity', 'CinnabarIsland', 'IndigoPlateau', 'SaffronCity'];
fs.writeFileSync(path.join(OUT, 'townmap.json'), JSON.stringify({ W, H, towns: TOWNS, where }, null, 1) + '\n');
console.log(`[bake_ui] logo ${L.big.w}x${L.big.h}/${L.red.w}x${L.red.h}, town map ${W}x${H} (${Object.keys(where).length} outdoor maps) -> ${OUT}`);

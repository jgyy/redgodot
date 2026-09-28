// Renders upstream's own Pokemon sprites (front + back, exactly as the 2D game draws them)
// to PNGs, as the reference for the 3D model contact sheets (pipeline/scripts/model_sheets.sh).
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/bake_monsprites.js OUT_DIR [SIZE] [SPECIES,...]
//
// Writes OUT_DIR/<SPECIES>_front.png and OUT_DIR/<SPECIES>_back.png (SIZE px, default 64;
// integer-upscaled x2 copies are handy for sheets: pass SIZE=64 and scale in the composer).
'use strict';
const path = require('path');
const { load, savePNG } = require('./lib/upstream');

const out = process.argv[2] || 'sprites';
const size = parseInt(process.argv[3] || '64', 10);
const only = process.argv[4] ? process.argv[4].split(',') : null;
const { G } = load();
let names = Object.keys(G.DATA.species).filter(s => G.DATA.species[s].dex >= 1 && G.DATA.species[s].dex <= 151);
names.sort((a, b) => G.DATA.species[a].dex - G.DATA.species[b].dex);
names.push('MISSINGNO');
if (only) names = names.filter(n => only.includes(n));
for (const sp of names) {
  for (const view of ['front', 'back']) {
    const s = G.pokeSprite(sp, view, size);
    savePNG(s, path.join(out, `${sp}_${view}.png`));
  }
}
console.log(`baked ${names.length} species x2 views -> ${out}`);

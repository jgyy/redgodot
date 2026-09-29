// Renders upstream's overworld character sprites (src/art/chars.js makeCharacter) for every
// humanoid cast entry: <key>_front.png (facing down) and <key>_back.png (facing up), padded
// to 24x24, as the reference column of the character contact sheet.
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/bake_charsprites.js OUT_DIR
'use strict';
const path = require('path');
const { load, savePNG } = require('./lib/upstream');

const out = process.argv[2] || 'charsprites';
const { G } = load();
let n = 0;
for (const key of Object.keys(G.CAST)) {
  const d = G.CAST[key];
  if (d.creature || d.object) continue;
  const fr = G.chars.makeCharacter(d);
  for (const [dir, view] of [['down', 'front'], ['up', 'back']]) {
    const s = new G.gfx.Surface(24, 24);
    s.blit(fr[dir][0], 4, 0);
    savePNG(s, path.join(out, `${key}_${view}.png`));
  }
  n++;
}
console.log(`baked ${n} characters -> ${out}`);

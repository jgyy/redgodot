// Shared helper for every bake_*.js script: loads the upstream pokemon-claude-red
// game headlessly (its own tools/headless.js VM loader, no browser) so the bakes
// call the *same* procedural painters the 2D game draws with.
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/bake_xxx.js
'use strict';
const path = require('path');
const fs = require('fs');

function upstreamRoot() {
  const cands = [process.env.UPSTREAM, path.join(__dirname, '..', '..', '..', '..', 'pokemon-claude-red'),
    path.join(__dirname, '..', '..', '..', 'pokemon-claude-red')].filter(Boolean);
  for (const c of cands) if (fs.existsSync(path.join(c, 'tools', 'headless.js'))) return path.resolve(c);
  throw new Error('pokemon-claude-red checkout not found: set UPSTREAM=/path/to/pokemon-claude-red');
}

let cached = null;
function load() {
  if (cached) return cached;
  const root = upstreamRoot();
  const H = require(path.join(root, 'tools', 'headless.js'));
  const ctx = H.loadGame();
  const G = ctx.G;
  G.boot();
  cached = { G, H, ctx, root };
  return cached;
}

// Surface -> PNG (RGBA, straight alpha), optional integer upscale.
function savePNG(surf, file, scale) {
  const { H } = load();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  H.savePNG(surf, file, scale || 1);
}

module.exports = { load, savePNG, upstreamRoot };

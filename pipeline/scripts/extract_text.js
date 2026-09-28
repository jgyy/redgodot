// Extracts ALL of upstream's text tables (src/data/text/{general,maps_a,maps_b,dex,aliases}.js)
// into one JSON file for the Godot port, keyed exactly like upstream:
//   text      -> G.TEXT      (pokered label without leading underscore -> string; '\f' = page break,
//                             {PLAYER}/{RIVAL}/... placeholders kept verbatim, resolved at runtime)
//   dex       -> G.DEX_TEXT  (SPECIES_ID -> Pokédex flavour text)
//   aliases   -> label -> label it points at (already applied into `text`, kept for reference)
//   files     -> source file -> [labels defined there]   (so story/map code can find map texts)
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/extract_text.js [out.json]
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { upstreamRoot } = require('./lib/upstream');

const root = upstreamRoot();
const out = process.argv[2] || path.join(__dirname, '..', '..', 'godot', 'data', 'text.json');
const FILES = ['general', 'maps_a', 'maps_b', 'dex', 'aliases'];

const G = { TEXT: {}, DEX_TEXT: {} };
const ctx = { G, window: { G }, console };
vm.createContext(ctx);
const files = {};
let aliases = {};
for (const f of FILES) {
  const src = fs.readFileSync(path.join(root, 'src', 'data', 'text', f + '.js'), 'utf8');
  const before = new Set(Object.keys(G.TEXT));
  if (f === 'aliases') {
    const m = src.match(/const A = (\{[\s\S]*?\});/);
    if (m) aliases = JSON.parse(m[1]);
  }
  vm.runInContext(src, ctx, { filename: f + '.js' });
  files[f] = f === 'dex' ? Object.keys(G.DEX_TEXT) : Object.keys(G.TEXT).filter(k => !before.has(k));
}
const sortObj = o => Object.fromEntries(Object.keys(o).sort().map(k => [k, o[k]]));
const data = { source: 'pokemon-claude-red src/data/text/*.js', text: sortObj(G.TEXT), dex: sortObj(G.DEX_TEXT), aliases, files };
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(data, null, 1) + '\n');
console.log(`[extract_text] ${Object.keys(G.TEXT).length} text labels, ${Object.keys(G.DEX_TEXT).length} dex entries, ${Object.keys(aliases).length} aliases -> ${out}`);

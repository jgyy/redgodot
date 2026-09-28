// Extracts all Pokemon vector-art definitions (species -> {pal, parts}) from the
// pokemon-claude-red source (src/data/mons/*.js) by stubbing G.defMon and evaluating
// the files with Node (they are plain IIFEs with no DOM dependency for this part).
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = process.argv[2];
const OUT = process.argv[3];

const MONS = {};
global.G = { defMon: (name, def) => { MONS[name] = def; } };

const dir = path.join(SRC, 'src/data/mons');
const files = fs.readdirSync(dir).filter(f => f.endsWith('.js')).sort();
for (const f of files) {
  const code = fs.readFileSync(path.join(dir, f), 'utf8');
  vm.runInThisContext(code, { filename: f });
}

fs.writeFileSync(OUT, JSON.stringify(MONS));
console.log(`extracted ${Object.keys(MONS).length} species -> ${OUT}`);

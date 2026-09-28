const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = process.argv[2];
const OUTDIR = process.argv[3];

// --- cast.js: plain object literal assigned to G.CAST / G.OBJ_SPRITE_OVERRIDE / G.OBJ_SPECIES_OVERRIDE
{
  global.G = {};
  const code = fs.readFileSync(path.join(SRC, 'src/data/cast.js'), 'utf8');
  vm.runInThisContext(code, { filename: 'cast.js' });
  fs.writeFileSync(path.join(OUTDIR, 'cast.json'), JSON.stringify({
    cast: global.G.CAST,
    spriteOverride: global.G.OBJ_SPRITE_OVERRIDE,
    speciesOverride: global.G.OBJ_SPECIES_OVERRIDE,
  }));
  console.log('cast entries:', Object.keys(global.G.CAST).length);
}

// --- chars.js: (function (G) { ... G.chars = {HEADS, BODY, ...} })(window.G)
{
  const gfxStub = {
    hex: (s) => (typeof s === 'string' ? s : '#ff00ff'),
    shade: (c) => c,
    mix: (a) => a,
    rgb: (r, g, b) => `rgb(${r},${g},${b})`,
    Surface: function Surface(w, h) { this.w = w; this.h = h; this.data = new Array(w * h).fill(0);
      this.pset = () => {}; this.flipped = () => this; this.clone = () => this; },
    bayer: () => 0,
    lum: () => 0.5,
  };
  const Gobj = { gfx: gfxStub, PAL: {}, font: { draw: () => {} } };
  global.window = { G: Gobj };
  global.G = Gobj;
  const code = fs.readFileSync(path.join(SRC, 'src/art/chars.js'), 'utf8');
  vm.runInThisContext(code, { filename: 'chars.js' });
  const { HEADS, BODY } = Gobj.chars;
  fs.writeFileSync(path.join(OUTDIR, 'chars.json'), JSON.stringify({ HEADS, BODY }));
  console.log('head styles:', Object.keys(HEADS).length, 'body styles:', Object.keys(BODY).length);
}

// Bakes upstream's hand-drawn variable-width pixel font (src/core/font.js) and its
// compact 3x5 digit font into BMFont text files (.fnt + .png) that Godot imports
// natively as FontFile. Glyphs are white; Px.gd tints them and draws the
// upstream 3-pixel drop shadow itself, exactly like font.draw().
'use strict';
const path = require('path');
const fs = require('fs');
const { load, savePNG } = require('./lib/upstream');

const OUT = process.argv[2] || path.join(__dirname, '..', '..', 'godot', 'assets', 'ui');
const { G } = load();
const { Surface, rgb } = G.gfx;
const WHITE = rgb(255, 255, 255);

function bake(name, chars, glyphOf, lineH, base, cellH) {
  const pad = 1, cols = 16;
  const cellW = 10;
  const rows = Math.ceil(chars.length / cols);
  const W = 256, Hh = Math.max(16, Math.pow(2, Math.ceil(Math.log2(rows * (cellH + pad) + 1))));
  const s = new Surface(W, Hh);
  const lines = [];
  chars.forEach((ch, i) => {
    const g = glyphOf(ch);
    const x0 = (i % cols) * (cellW + pad), y0 = Math.floor(i / cols) * (cellH + pad);
    for (const [x, y] of g.px) s.pset(x0 + x, y0 + y, WHITE);
    lines.push(`char id=${ch.codePointAt(0)} x=${x0} y=${y0} width=${Math.max(1, g.w)} height=${cellH} xoffset=0 yoffset=0 xadvance=${g.w + 1} page=0 chnl=15`);
  });
  savePNG(s, path.join(OUT, name + '.png'));
  const fnt = [
    `info face="${name}" size=${cellH} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 padding=0,0,0,0 spacing=1,1 outline=0`,
    `common lineHeight=${lineH} base=${base} scaleW=${W} scaleH=${Hh} pages=1 packed=0 alphaChnl=0 redChnl=4 greenChnl=4 blueChnl=4`,
    `page id=0 file="${name}.png"`,
    `chars count=${lines.length}`,
    ...lines, '',
  ].join('\n');
  fs.writeFileSync(path.join(OUT, name + '.fnt'), fnt);
  console.log('baked', name, chars.length, 'glyphs');
}

// --- main font: reach into font.js's private glyph table by rendering each char once
const F = G.font;
function probe(ch) {
  const w = F.measure(ch);
  const t = new Surface(16, 12);
  F.draw(t, ch, 0, 0, WHITE);
  const px = [];
  for (let y = 0; y < 12; y++) for (let x = 0; x < 16; x++) if (t.data[y * 16 + x] >>> 24) px.push([x, y]);
  return { w, px };
}
const main = [];
for (let c = 32; c < 127; c++) main.push(String.fromCharCode(c));
main.push(...'éÉ♂♀▶▷▼▲…×·—♪№’“”¥'.split(''));
bake('pxfont', main, probe, 14, 8, 10);

// --- small 3x5 font (levels / HP numbers)
function probeSmall(ch) {
  const t = new Surface(8, 8);
  const end = F.drawSmall(t, ch, 0, 0, WHITE);
  const px = [];
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) if (t.data[y * 8 + x] >>> 24) px.push([x, y]);
  let w = 0; for (const [x] of px) w = Math.max(w, x + 1);
  if (ch === ' ') w = 2;
  return { w: typeof end === 'number' && end > 0 ? end - 1 : w, px };
}
const small = '0123456789/ LvHP:-EXNo.ABCDFGIJKMOQRSTUVWYZ%$+\''.split('').filter((c, i, a) => a.indexOf(c) === i);
bake('pxfont_small', small, probeSmall, 7, 5, 6);

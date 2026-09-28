// Extracts upstream's music data (src/data/music.js: the pokered note data of all 52
// songs + jingles, GB wave-channel samples, noise-drum kits, per-map song table and
// encounter-theme classes) into godot/data/music.json for the Godot sequencer
// (godot/scripts/audio/GBMusic.gd). Pure data copy — no rendering.
//
//   UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/extract_music.js [out.json]
'use strict';
const fs = require('fs');
const path = require('path');
const { upstreamRoot } = require('./lib/upstream');

const root = upstreamRoot();
const out = process.argv[2] || path.join(__dirname, '..', '..', 'godot', 'data', 'music.json');
global.window = { G: {} };
require(path.join(root, 'src', 'data', 'music.js'));
const M = global.window.G.MUSIC;
fs.writeFileSync(out, JSON.stringify(M));
console.log('music.json:', Object.keys(M.songs).length, 'songs,', Object.keys(M.mapSongs).length, 'map entries ->', out);

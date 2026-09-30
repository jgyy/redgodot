# Content audit: POKéMON RED, BLUE and YELLOW (Generation 1)

What the Godot port implements against the complete Gen 1 checklist. "Before" is the project as merged in `54d228f`
(the upstream *Pokemon Claude Red* remake, RED only); "After" is this branch. Every row has evidence: a file (and line
at the time of writing), a data file, or a unit test that fails if the row stops being true.

Status words: **done** (matches the cartridges), **partial** (works, with a stated difference), **missing**.
The reference for RED and BLUE is [pret/pokered](https://github.com/pret/pokered), for YELLOW
[pret/pokeyellow](https://github.com/pret/pokeyellow); `pipeline/scripts/extract_versions.py` reads them,
`pipeline/scripts/content_audit.py` prints the totals quoted below, `pipeline/scripts/audit_summary.py` counts this table.

## Summary

<!-- SUMMARY:START -->
| | done | partial | missing | rows |
| --- | ---: | ---: | ---: | ---: |
| Before | 57 | 12 | 38 | 107 |
| After | 97 | 5 | 5 | 107 |
<!-- SUMMARY:END -->

Measured totals (from `content_audit.py`, `VersionTests`, `MechanicsTests`):

| | game (RED data) | pokered | pokeyellow |
| --- | ---: | ---: | ---: |
| maps | 223 | 223 | 222 shared + 2 of its own (`CeruleanMelaniesHouse` replaces `CeruleanTradeHouse`; `SummerBeachHouse`) |
| warps | 805 | 805 | 809 |
| NPC / object events | 918 | 918 | 937 |
| trainer objects | 334 | 334 | 329 |
| item balls | 104 (TM 27) | 104 (TM 27) | 108 (TM 27) |
| signs (`bg_event`s) | 201 | 201 | 199 |
| hidden items / coins / PCs | 216 (`hidden_events.asm`) | | |
| trainer parties | 391 | 391 | 396 |
| wild maps with grass or water | 57 | 57 | 57 |

Unit tests: 355 before, 673 after (`=== 673 passed, 0 failed ===`); 3 playtests (RED, BLUE, YELLOW new game to the first rival fight).

## How the three versions work

`data/versions.json` (generated) holds only what differs; `GameData.apply_version()` lays it over the RED base data
(`pokedata.json`, `mapdata.json`, `text.json`) when `GameState.set_version()` runs (NEW GAME, loading a save, `--version=`).

* BLUE differs from RED in wild encounters, Game Corner prizes and their levels, and nothing else that the disassembly
  contains (the rival, the marts, the trades and every trainer team are identical); the port is therefore the RED game with
  BLUE's tables.
* YELLOW differs in almost everything: wild tables, all trainer teams and custom movesets, 34 species' learnsets / start moves /
  TM lists / catch rates, three marts, the ten trades, Game Corner prizes, 41 maps' NPCs and items, 326 lines of dialogue, the
  starter and the rival, PIKACHU following the player.

## 1. Version support

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| Version choice on NEW GAME (RED / BLUE / YELLOW) | missing | done | `TitleScene.gd` `_open_menu` + `VERSION_CHOICES`; `docs/showcase/versions-title-menu.png` |
| Version stored in the save; saves without one load as RED | missing | done | `GameState.gd` `set_version`, `save()`; `VersionTests._save` (round trip, old-save case) |
| Version label and colour (title, trainer card) | missing | done | `TitleOverlay.gd`, `TrainerCard.gd`, `GameState.version_color` |
| Version selectable in tools, playtests and CI | missing | done | `Main.gd` `--version=`, `PlayTest.gd`, `.github/workflows/ci.yml` |
| All version data reproducible from the disassemblies | missing | done | `pipeline/scripts/extract_versions.py`, `pipeline/README.md` section 1b |
| Prof. Oak introduces NIDORINO (RED, BLUE) or PIKACHU (YELLOW) | missing | done | `OakSpeech._intro_mon` |
| BLUE rival name / text differences | done | done | there are none in pokered (both use BLUE / GARY / JOHN); nothing to port |
| Data extractor verified against the upstream data | missing | done | `VersionTests._load`: pokered's parsed wild tables, trades, rods and all 391 parties equal the base Red data |

## 2. POKéMON data

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| 151 species: stats, types, learnsets, evolutions, catch rate, base exp, growth | done | done | `pokedata.json`; `TestSuite` (151 species) |
| YELLOW species deltas (23 learnsets, 13 start-move lists, 9 TM/HM lists, DRAGONAIR / DRAGONITE catch rate) | missing | done | `versions.json` `species.YELLOW`; `VersionTests._yellow_data` (PIKACHU learnset, KADABRA start moves) |
| Evolutions by level, stone, trade | done | done | data in `species[].evos`; stones: `FieldItems` tests; level: `BattleTests._level_up` |
| Evolution animation | done | done | `EvolutionStage.gd`, `BattleScene.evolve`; stones and trades use messages + cry only (partial for those two paths, see rows in section 4) |
| 165 moves with effects | done | done | `pokedata.json`; `BattleTests._env_and_vfx` (every move has an animation) |
| Type chart including Gen 1 quirks (GHOST vs PSYCHIC 0, BUG <-> POISON, ICE vs FIRE neutral) | done | done | `MechanicsTests._type_chart` |
| Pokédex entries, categories, height / weight | done | done | `text.json` dex (`TestSuite`) |
| Pokédex DATA / CRY / AREA menu | missing | done | `PokedexMenu.gd` `_species_menu`, `GameData.habitats`; `VersionTests._wild` (AREA per version) |
| Cries | done | done | `SfxSynth.cry`, `AudioTests` |
| Pokédex numbers / order | done | done | `dexOrder` |

## 3. Wild POKéMON

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| Grass and surf tables, RED | done | done | `pokedata.json` `wild`; equals the parsed pokered tables (`VersionTests._load`) |
| Grass and surf tables, BLUE | missing | done | `versions.json` `wild.BLUE`; `VersionTests._wild` |
| Grass and surf tables, YELLOW | missing | done | `versions.json` `wild.YELLOW`; Route 2 has NIDORANs, Viridian Forest PIDGEOTTO |
| RED-only: EKANS, ARBOK, ODDISH, GLOOM, MANKEY, GROWLITHE, SCYTHER, ELECTABUZZ | missing | done | exact set asserted in `VersionTests._wild` |
| BLUE-only: SANDSHREW, SANDSLASH, VULPIX, MEOWTH, BELLSPROUT, WEEPINBELL, MAGMAR, PINSIR | missing | done | same |
| Route 2 / Viridian Forest slots (WEEDLE vs CATERPIE line) | missing | done | `VersionTests._wild` (EncounterSystem rolls) |
| Old rod (MAGIKARP), good rod, super rod per map and version | partial | done | `versions.json` `goodRod`, `superRod`; `Story.fish` |
| Encounter rate, slot probabilities, REPEL, tall-grass rule | done | done | `EncounterSystem.gd`, `OverworldScene` |
| Safari Zone: 500 fee, 30 BALLs, ~500 steps, BAIT / ROCK, per-version tables | partial | done | `Late.gd` (fee, balls, steps), `BattleEngine.safari_action`, `BattleTests._special_battles`, wild tables per version |
| Static encounters: SNORLAX x2, ZAPDOS, MOLTRES, ARTICUNO, MEWTWO, VOLTORB / ELECTRODE x9 | done | done | `mapdata.json` `mon` objects, `Late.gd static_mon`, `Story.static_encounter` |
| Pokémon Tower ghosts, SILPH SCOPE, ghost MAROWAK | done | done | `BattleEngine` ghost flag, `Mid.gd` |
| Every one of the 151 species can be obtained in some version | partial | done (150) | `VersionTests._species_obtainable` (wild, rods, gifts, trades, prizes, static, evolution closure) |
| MEW | missing | missing | never on a cartridge except by Nintendo event or glitch; `VersionTests` pins `missing == [MEW]` |
| MISSINGNO. (Old Man glitch on Cinnabar's east coast) and its item glitch | partial | done | `EncounterSystem.glitch_roll`, `BattleEngine._init`, `MechanicsTests._missingno`; battle model `MissingNoBlock.gd` |
| Other glitches (trainer-fly, Mew glitch, Hall of Fame corruption) | missing | missing | not implemented |

## 4. Getting POKéMON: starters, gifts, trades, prizes

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| RED / BLUE starters BULBASAUR, CHARMANDER, SQUIRTLE and the rival's counter-pick | done | done | `Pallet.gd _pick_ball`, `StoryTests._pallet` |
| YELLOW: no choice, Oak gives a Lv5 PIKACHU; the rival snatches EEVEE | missing | done | `Yellow.gd _eevee_ball`, `give_pikachu`; `VersionTests._yellow_story` |
| YELLOW rival branch: EEVEE becomes JOLTEON / FLAREON / VAPOREON (lost lab fight: VAPOREON; won: FLAREON; won Route 22: JOLTEON) | missing | done | `Yellow.after_lab_battle`, `Story.yellow_rival_party`; tests for every party number and the champion's last mon |
| PIKACHU follows, has friendship 0-255 (start 90) with pret's HappinessChangeTable, cries and emotes | missing | done | `PikachuBuddy.gd`, `OverworldScene._lead_species`; `VersionTests._rival_and_buddy`, `_yellow_story` |
| PIKACHU dislikes POKé BALLs (Oak's remark), sad in the PC, no nickname prompt | missing | done | `Yellow.pikachu_dislikes_balls`, `PCMenu.gd` |
| YELLOW gifts: BULBASAUR (Melanie, friendship >= 147), SQUIRTLE (Officer Jenny, THUNDERBADGE + friendship), CHARMANDER (Damian, Route 24), all Lv10 | missing | done | `Yellow.gd _melanie / _jenny / _damian`; tests incl. the friendship gate |
| EEVEE (Celadon Mansion), LAPRAS (Silph Co.), HITMONLEE / HITMONCHAN (Dojo), fossils (Cinnabar lab), MAGIKARP (Mt. Moon) | done | done | `Mid.gd`, `Late.gd`, `Early.gd`; same in YELLOW (pokeyellow scripts) |
| Ten NPC trades, RED and BLUE | done | done | `pokedata.json` `trades` |
| Ten NPC trades, YELLOW (LICKITUNG -> DUGTRIO, CLEFAIRY -> MR. MIME, ...) | missing | done | `versions.json`; `VersionTests._trades_prizes_marts` |
| Game Corner prizes and levels: RED, BLUE, YELLOW | partial | done | `versions.json` `prizes`; `Mid.gd prize_menu`; tests for all three windows |
| Trade evolution (KADABRA, MACHOKE, GRAVELER, HAUNTER) | missing | partial | needs a second Game Boy on the cartridge; port extension: the Cable Club receptionist offers a solo TRADE CENTER (`Story.solo_trade_center`, `FieldItems.trade_target`); tests |
| Daycare | done | done | `Extra.gd` |
| Bill / SS Anne / Silph gift items | done | done | `Early.gd`, `Mid.gd` |

## 5. Items and the bag

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| 153 item ids with prices; buy and sell in every mart | done | done | `pokedata.json`, `Story.mart` |
| YELLOW mart stock (Viridian POTION, Cerulean ESCAPE ROPE, Fuchsia HYPER POTION) | missing | done | `versions.json` `marts.YELLOW`; test |
| POTIONs, status cures, REVIVE, RARE CANDY from the bag | done | done | `BagMenu.apply_to_mon` |
| TMs and HMs from the bag (compatibility, replace-a-move prompt, HM never used up) | missing | done | `FieldItems.teach`; `MechanicsTests._field_items` |
| Evolution stones (FIRE, WATER, THUNDER, LEAF, MOON) | missing | done | `FieldItems.stone`; 14 evolutions tested |
| Vitamins HP UP, PROTEIN, IRON, CARBOS, CALCIUM (+2560 stat exp, cap 25600) | missing | done | `FieldItems.vitamin`; test |
| PP UP (+1/5, three times), ETHER, MAX ETHER, ELIXER, MAX ELIXER out of battle | partial | done | `FieldItems.pp_item`; test |
| All 50 TMs and 5 HMs have a source (27 TM balls, gyms, gifts, Celadon Dept. Store, Game Corner) | done | done | checked mechanically against `mapdata.json`, `Early/Mid/Late.gd`, marts, prizes |
| Key items: BICYCLE, TOWN MAP, rods, ITEMFINDER, POKé FLUTE, COIN CASE, CARD KEY, LIFT KEY, SILPH SCOPE, S.S. TICKET, GOLD TEETH, BIKE VOUCHER, SECRET KEY, OAK's PARCEL | done | done | `Story.use_field_item`, `BagMenu` |
| 104 item balls (27 TMs) and 216 hidden events match pokered | done | done | `content_audit.py` |
| REPEL, SUPER / MAX REPEL, ESCAPE ROPE, POKé DOLL, X items, GUARD SPEC., DIRE HIT, EXP. ALL | done | done | `Story.use_field_item`, `BattleEngine.use_item` |
| PC item storage, 12 boxes x 20 POKéMON | done | done | `PCMenu.gd`, `GameState.box` |

## 6. Maps, warps, NPCs

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| 223 maps with tilesets, connections, warps (805) | done | done | `mapdata.json` = pokered totals |
| 918 NPC / object events, 334 trainers, 201 signs, 216 hidden events | done | done | `content_audit.py` (equal to pokered; the game also has two Daisy objects tagged `item: "0"` upstream) |
| YELLOW NPC / trainer / item placement: 41 maps (31 patched, 43 added, 24 removed; renamed trainers matched by position) | missing | done | `versions.json` `objects.YELLOW`, `GameData._apply_object_overlay`; `VersionTests._trainer_objects` |
| YELLOW's Melanie's House in place of the Cerulean trade house | missing | done | overlay alias `CeruleanTradeHouse` -> `CeruleanMelaniesHouse`; `docs/showcase/versions-yellow-melanie-house.png` |
| YELLOW's CHANSEY at every POKéMON CENTER, JENNY x2 in Cerulean, ELECTRODE, CLEFAIRY fan | missing | done | `Yellow.gd`; tests |
| JESSIE & JAMES x4 (Mt. Moon, Rocket Hideout B4F, Pokémon Tower 7F, Silph Co. 11F) with their four teams | missing | done | `Yellow.gd _jessie_james`, `jessieJames`; test |
| PIKACHU-aware NPCs (Museum hiker, Celadon Mansion granny) | missing | done | `Yellow.gd`; tests |
| YELLOW's Pokémon Fan Club (CLEFAIRY fan) | missing | done | `Yellow.gd _clefairy_fan` |
| YELLOW dialogue that differs from RED (326 lines) | missing | done | `versions.json` `text.YELLOW`, `GameText.get_text` |
| YELLOW map tile / block changes (27 maps: Cerulean Cave x3, Route 19, Route 4, counters) | missing | missing | only the object layer is ported; Cerulean Cave keeps RED's layout **and** items |
| YELLOW's Summer Beach House (Pikachu's Beach) and Surfing PIKACHU | missing | missing | optional in the brief; not implemented |
| YELLOW gate-map warp numbering (Route 11/12/15/16/18 gates) | missing | partial | the RED gate maps and warps are kept (their indices are consistent with them) |
| Scripted events: Oak's Parcel, Pokédex, Bill, SS Anne, Rocket Hideout, Silph Co., Fuji, Saffron guards, Cinnabar, Fossils | done | done | `Pallet/Early/Mid/Late.gd`, `StoryTests` |
| Cinnabar Gym quiz, Pokémon Mansion switches, Victory Road boulders, Seafoam currents, Cycling Road | done | done | `Late.gd`, `Mid.gd` |

## 7. Trainers and battles

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| Exact teams for all 391 RED / BLUE parties | done | done | `pokedata.json` `parties` = pokered (asserted) |
| Exact teams for YELLOW's 396 parties | missing | done | `versions.json` `parties.YELLOW`; every trainer object resolves to a party and has its battle text (`VersionTests._trainer_objects`) |
| Gym leaders per version (BROCK Lv10/12 in YELLOW ...) | partial | done | `VersionTests._yellow_data` (BROCK, MISTY, LT.SURGE, ERIKA, KOGA, SABRINA, BLAINE, GIOVANNI) |
| Elite Four and Champion per version | partial | done | same (LORELEI, BRUNO, AGATHA, LANCE; champion's last mon per branch) |
| Custom movesets: RED lone / team moves, YELLOW special_moves.asm (BROCK's ONIX has BIND + BIDE ...) | partial | done | `BattleEngine.make_trainer_party`; tests |
| Trainer AI: item use at low HP, move scoring | partial | partial | `BattleEngine.enemy_action` approximates pret's per-class move-choice modifications; no AI switching |
| Prize money, badges, TM rewards | done | done | `BattleEngine.prize_money`, `Story.award_badge` |
| Hall of Fame, credits, restart after the League | done | done | `Late.gd hall_of_fame` |
| POKéDEX diploma at 150 owned, OAK's rating | done | done | `Mid.gd diploma`, `Pallet.oak_rating` |

## 8. Field moves and travel

| Item | Before | After | Evidence |
| --- | --- | --- | --- |
| CUT, SURF, STRENGTH, FLASH, FLY, TELEPORT, DIG, SOFTBOILED with badge checks | done | done | `Story.use_field_move`, `PartyMenu.FIELD_MOVES` |
| Bicycle, forced bike on Cycling Road | done | done | `Story.use_field_item`, `bike_allowed` |
| Fishing | done | done | `Story.fish` |
| Badge stat boosts (BOULDER attack, THUNDER defence, SOUL speed, VOLCANO special) | done | done | `BattleEngine.stat`; `MechanicsTests._badges_and_special` |
| Save / continue, options, PC, name rater | done | done | `GameState.save`, `OptionsMenu`, `Mid.gd` |

## 9. Battle engine (Gen 1 rules)

Each row is asserted in `godot/scripts/battle/MechanicsTests.gd`.

| Mechanic | Before | After | Note |
| --- | --- | --- | --- |
| Critical hit = base Speed / 2 out of 256; x8 for high-crit moves; ignores stat stages | done | done | rate sampled |
| FOCUS ENERGY | done | partial | ported as x4 (the intended effect); the cartridge's bug divides the rate by 4. Kept as upstream ships it |
| Miss on 255/256 ("1/256 bug") | done | partial | 100% moves never miss (deliberate, as upstream) |
| Single SPECIAL stat (attack and defence) | done | done | no split stats in data or formula |
| Badge boosts | done | done | |
| Stat stages 25/100 .. 400/100, +-6 cap, "Nothing happened!" | done | done | |
| Trapping: BIND, WRAP, FIRE SPIN, CLAMP | done | done | target loses its turns |
| MIRROR MOVE, METRONOME, MIMIC, TRANSFORM, CONVERSION | done | done | |
| SUBSTITUTE, HAZE, MIST, REFLECT, LIGHT SCREEN | done | done | |
| LEECH SEED, TOXIC growth, burn / poison damage | done | done | |
| RAGE, COUNTER (priority -1, physical only, x2), BIDE (x2), DISABLE, THRASH confusion | done | done | |
| EXPLOSION / SELFDESTRUCT, DREAM EATER, MEGA DRAIN, PSYWAVE (1..1.5 x level), fixed-damage moves, SUPER FANG | done | done | |
| OHKO speed rule, multi-hit distribution 3/8 3/8 1/8 1/8, TWINEEDLE, PAY DAY | done | done | |
| FLY / DIG invulnerability, SOLARBEAM charge, HYPER BEAM recharge | done | done | |
| JUMP KICK crash on a miss or an immune target | partial | done | immune-target crash added |
| Sleep 1-7 turns, freeze never thaws (FIRE thaws), full paralysis 25%, confusion 2-5 | done | done | |
| Catch formula (ball, status, HP), MASTER BALL, no catching trainers' POKéMON | done | done | `BattleTests._catching`, `MechanicsTests._misc` |
| Experience curves, traded-mon 1.5x, EXP. ALL, level-up moves, evolution after battle | done | done | |
| Order of moves: speed, QUICK ATTACK +1, ties | done | done | |
| Struggle, wild fleeing / TELEPORT / ROAR | done | done | |

## Not covered (honest list)

1. **MEW**: no in-game source exists on the cartridges (event / glitch only).
2. **YELLOW map block changes**: 27 maps differ in tile data (Cerulean Cave x3 substantially, Route 19, Route 4, the CHANSEY counter in POKéMON CENTERS, mart shelves). Only NPC / item / trainer placement is ported; Cerulean Cave keeps RED's layout and RED's items.
3. **YELLOW extras**: Pikachu's Beach (Summer Beach House) and Surfing PIKACHU minigame; PIKACHU's animated portraits and the special PIKACHU battle entrance; NPC lines that read the PIKACHU mood beyond the Museum, Celadon Mansion, Melanie / Jenny and the centre reactions; Yellow-only Pokémon Center nurse texts.
4. **Trade evolution** needs the port's solo TRADE CENTER (an extension): there is no second Game Boy. Link battles / trades with other players are not implemented.
5. **Glitches** other than MISSINGNO. via the Old Man glitch (trainer-fly, Mew glitch, corrupted Hall of Fame).
6. **FOCUS ENERGY bug and the 1/256 accuracy bug** are not reproduced (kept as the upstream remake has them).
7. **Trainer AI** approximates pret's move-choice modifiers; trainers never switch POKéMON.
8. **Evolution by stone / trade** shows messages and the cry instead of the animated 3D sequence (that only plays after a battle level-up).
9. **YELLOW's Yellow-only NPCs** without a script (a Pewter POKéMON CENTER cooltrainer, a Viridian second old man, the Route 18 gate cook, Vermilion trade house gentleman) speak `...` or the RED line of the object they replace.

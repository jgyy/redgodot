"""Species data: move -> animation archetype and the choice of each species' signature clips (from its own learnset)."""
import json
import os

# every Gen-1 move used by the game -> (archetype, variation).  Variation keys are read by pokemon_arch.py.
MOVE_ARCH = {
    'ABSORB': ('leech', {}), 'ACID': ('beam', {'sweep': 1, 'open': 0.7}), 'ACID_ARMOR': ('harden', {}),
    'AGILITY': ('dash', {'power': 0.6}), 'AMNESIA': ('focus', {}), 'AURORA_BEAM': ('beam', {'sweep': 1}),
    'BARRAGE': ('throw', {}), 'BARRIER': ('harden', {}), 'BIDE': ('flop', {'reps': 2}), 'BIND': ('bind', {}),
    'BITE': ('bite', {}), 'BLIZZARD': ('burst', {'reps': 4}), 'BODY_SLAM': ('slam', {}), 'BONEMERANG': ('throw', {'side': -1.0}),
    'BONE_CLUB': ('slam', {}), 'BUBBLE': ('burst', {'reps': 5}), 'BUBBLEBEAM': ('beam', {'sweep': 1, 'open': 0.6}),
    'CLAMP': ('bind', {}), 'COMET_PUNCH': ('multi_strike', {'reps': 5}), 'CONFUSE_RAY': ('sing', {}),
    'CONFUSION': ('psychic', {}), 'CONSTRICT': ('bind', {}), 'CONVERSION': ('morph', {}), 'COUNTER': ('flop', {'reps': 2}),
    'CRABHAMMER': ('slam', {}), 'CUT': ('strike', {'slash': True}), 'DEFENSE_CURL': ('harden', {}), 'DIG': ('dive', {}),
    'DISABLE': ('menace', {}), 'DIZZY_PUNCH': ('strike', {'side': -1.0}), 'DOUBLESLAP': ('multi_strike', {'reps': 2}),
    'DOUBLE_EDGE': ('tackle', {'power': 1.2}), 'DOUBLE_KICK': ('kick', {'double': True}), 'DOUBLE_TEAM': ('dash', {'side': -1.0}),
    'DRAGON_RAGE': ('burst', {'reps': 2}), 'DREAM_EATER': ('leech', {'side': -1.0}), 'DRILL_PECK': ('headbutt', {'drill': True}),
    'EARTHQUAKE': ('slam', {'power': 1.3}), 'EGG_BOMB': ('throw', {}), 'EMBER': ('burst', {}), 'EXPLOSION': ('explode', {}),
    'FIRE_BLAST': ('burst', {'reps': 2}), 'FIRE_PUNCH': ('strike', {'power': 1.1}), 'FIRE_SPIN': ('spin_attack', {'turns': 3}),
    'FISSURE': ('slam', {'power': 1.2}), 'FLAMETHROWER': ('beam', {'sweep': 1}), 'FLASH': ('flash', {}), 'FLY': ('fly_up', {}),
    'FOCUS_ENERGY': ('focus', {}), 'FURY_ATTACK': ('multi_strike', {'reps': 6}), 'FURY_SWIPES': ('multi_strike', {'reps': 4, 'side': -1.0}),
    'GLARE': ('menace', {}), 'GROWL': ('menace', {}), 'GROWTH': ('focus', {}), 'GUILLOTINE': ('bite', {'big': True}),
    'GUST': ('wing_beat', {}), 'HARDEN': ('harden', {}), 'HAZE': ('flash', {}), 'HEADBUTT': ('headbutt', {}),
    'HI_JUMP_KICK': ('leap_strike', {}), 'HORN_ATTACK': ('headbutt', {'power': 1.2}), 'HORN_DRILL': ('headbutt', {'drill': True, 'power': 1.3}),
    'HYDRO_PUMP': ('beam', {'open': 1.0}), 'HYPER_BEAM': ('beam', {'open': 1.0}), 'HYPER_FANG': ('bite', {'big': True}),
    'HYPNOSIS': ('sing', {}), 'ICE_BEAM': ('beam', {'sweep': 0}), 'ICE_PUNCH': ('strike', {'slash': True}),
    'JUMP_KICK': ('kick', {}), 'KARATE_CHOP': ('strike', {'slash': True}), 'KINESIS': ('psychic', {}),
    'LEECH_LIFE': ('leech', {}), 'LEECH_SEED': ('throw', {'side': -1.0}), 'LEER': ('menace', {}), 'LICK': ('whip', {'tongue': True}),
    'LIGHT_SCREEN': ('flash', {}), 'LOVELY_KISS': ('sing', {}), 'LOW_KICK': ('kick', {'side': -1.0}),
    'MEDITATE': ('focus', {}), 'MEGA_DRAIN': ('leech', {}), 'MEGA_KICK': ('kick', {'power': 1.2}), 'MEGA_PUNCH': ('strike', {'power': 1.3}),
    'METRONOME': ('morph', {}), 'MIMIC': ('morph', {}), 'MINIMIZE': ('harden', {}), 'MIRROR_MOVE': ('morph', {}), 'MIST': ('flash', {}),
    'NIGHT_SHADE': ('psychic', {}), 'PAY_DAY': ('throw', {}), 'PECK': ('headbutt', {}), 'PETAL_DANCE': ('spin_attack', {'turns': 2}),
    'PIN_MISSILE': ('multi_strike', {'reps': 5}), 'POISONPOWDER': ('powder', {}), 'POISON_GAS': ('burst', {'reps': 2}),
    'POISON_STING': ('multi_strike', {'reps': 3}), 'POUND': ('strike', {}), 'PSYBEAM': ('beam', {'sweep': 1}), 'PSYCHIC_M': ('psychic', {}),
    'PSYWAVE': ('psychic', {}), 'QUICK_ATTACK': ('dash', {}), 'RAGE': ('flop', {'reps': 4}), 'RAZOR_LEAF': ('throw', {'side': -1.0}),
    'RAZOR_WIND': ('wing_beat', {}), 'RECOVER': ('rest_heal', {}), 'REFLECT': ('flash', {}), 'REST': ('rest_heal', {}),
    'ROAR': ('menace', {}), 'ROCK_SLIDE': ('slam', {}), 'ROCK_THROW': ('throw', {}), 'ROLLING_KICK': ('kick', {'power': 1.1}),
    'SAND_ATTACK': ('burst', {'reps': 3}), 'SCRATCH': ('strike', {'slash': True}), 'SCREECH': ('sing', {}),
    'SEISMIC_TOSS': ('slam', {}), 'SELFDESTRUCT': ('explode', {}), 'SHARPEN': ('focus', {}), 'SING': ('sing', {}),
    'SKULL_BASH': ('headbutt', {'power': 1.3}), 'SKY_ATTACK': ('leap_strike', {}), 'SLAM': ('slam', {}), 'SLASH': ('strike', {'slash': True, 'power': 1.2}),
    'SLEEP_POWDER': ('powder', {}), 'SLUDGE': ('beam', {'open': 0.8}), 'SMOG': ('burst', {'reps': 3}), 'SMOKESCREEN': ('burst', {'reps': 2}),
    'SOFTBOILED': ('rest_heal', {}), 'SOLARBEAM': ('beam', {'open': 1.0}), 'SONICBOOM': ('burst', {'reps': 2}),
    'SPIKE_CANNON': ('multi_strike', {'reps': 5}), 'SPLASH': ('flop', {'reps': 3}), 'SPORE': ('powder', {}), 'STOMP': ('slam', {}),
    'STRENGTH': ('strike', {'power': 1.3}), 'STRING_SHOT': ('whip', {'reps': 2}), 'STRUGGLE': ('flop', {'reps': 3}),
    'STUN_SPORE': ('powder', {}), 'SUBMISSION': ('tackle', {}), 'SUBSTITUTE': ('morph', {}), 'SUPERSONIC': ('sing', {}),
    'SUPER_FANG': ('bite', {'big': True}), 'SURF': ('dive', {}), 'SWIFT': ('dash', {}), 'SWORDS_DANCE': ('focus', {'dance': True}),
    'TACKLE': ('tackle', {}), 'TAIL_WHIP': ('whip', {}), 'TAKE_DOWN': ('tackle', {}), 'TELEPORT': ('dash', {'power': 0.4}),
    'THRASH': ('flop', {'reps': 4}), 'THUNDER': ('shock', {}), 'THUNDERBOLT': ('shock', {}), 'THUNDERPUNCH': ('strike', {'slash': True}),
    'THUNDERSHOCK': ('shock', {}), 'THUNDER_WAVE': ('shock', {}), 'TOXIC': ('powder', {}), 'TRANSFORM': ('morph', {}),
    'TRI_ATTACK': ('beam', {'sweep': 1}), 'TWINEEDLE': ('multi_strike', {'reps': 2}), 'VICEGRIP': ('bind', {}),
    'VINE_WHIP': ('whip', {'reps': 3}), 'WATERFALL': ('leap_strike', {}), 'WATER_GUN': ('burst', {'reps': 4}),
    'WHIRLWIND': ('spin_attack', {'turns': 2}), 'WING_ATTACK': ('wing_beat', {}), 'WITHDRAW': ('harden', {}), 'WRAP': ('bind', {}),
}

# moves that read best with a particular archetype for a given type when the learnset is short
TYPE_DEFAULTS = {
    'NORMAL': ['TACKLE', 'HYPER_BEAM', 'SLAM', 'HEADBUTT'], 'FIRE': ['EMBER', 'FLAMETHROWER', 'FIRE_SPIN', 'FIRE_PUNCH'],
    'WATER': ['WATER_GUN', 'BUBBLEBEAM', 'SURF', 'HYDRO_PUMP'], 'ELECTRIC': ['THUNDERSHOCK', 'THUNDER_WAVE', 'SWIFT', 'THUNDERBOLT'],
    'GRASS': ['VINE_WHIP', 'RAZOR_LEAF', 'SLEEP_POWDER', 'SOLARBEAM'], 'ICE': ['ICE_BEAM', 'BLIZZARD', 'AURORA_BEAM', 'MIST'],
    'FIGHTING': ['KARATE_CHOP', 'LOW_KICK', 'SEISMIC_TOSS', 'SUBMISSION'], 'POISON': ['POISON_STING', 'ACID', 'SLUDGE', 'SMOG'],
    'GROUND': ['DIG', 'EARTHQUAKE', 'SAND_ATTACK', 'BONE_CLUB'], 'FLYING': ['GUST', 'WING_ATTACK', 'FLY', 'PECK'],
    'PSYCHIC_TYPE': ['CONFUSION', 'PSYWAVE', 'PSYCHIC_M', 'MEDITATE'], 'BUG': ['STRING_SHOT', 'PIN_MISSILE', 'TWINEEDLE', 'LEECH_LIFE'],
    'ROCK': ['ROCK_THROW', 'ROCK_SLIDE', 'HARDEN', 'STOMP'], 'GHOST': ['NIGHT_SHADE', 'LICK', 'CONFUSE_RAY', 'HYPNOSIS'],
    'DRAGON': ['DRAGON_RAGE', 'SLAM', 'BITE', 'WRAP'],
}

# what Attack and Special of each body plan / type use (kept out of the signature pool so every clip is different)
SPECIAL_BY_TYPE = {
    'FIRE': 'burst', 'WATER': 'beam', 'ELECTRIC': 'shock', 'GRASS': 'powder', 'ICE': 'beam', 'POISON': 'burst', 'GROUND': 'slam',
    'PSYCHIC_TYPE': 'psychic', 'GHOST': 'sing', 'DRAGON': 'burst', 'FLYING': 'wing_beat', 'BUG': 'powder', 'ROCK': 'throw',
    'FIGHTING': 'focus', 'NORMAL': 'beam',
}


def clip_name(move_id):
    return ''.join(p.capitalize() for p in move_id.replace('PSYCHIC_M', 'PSYCHIC').split('_'))


def learnset(sd, all_species):
    """ordered distinct moves a species can use: its own level-up moves, its evolutions' (a preview), then TM/HM."""
    out = []

    def add(m):
        if m in MOVE_ARCH and m not in out:
            out.append(m)
    for m in sd.get('moves1', []):
        add(m)
    for lv, m in sd.get('learn', []):
        add(m)
    for ev in sd.get('evos', []):
        to = all_species.get(ev.get('to'))
        if to:
            for lv, m in to.get('learn', []):
                add(m)
    for m in sd.get('tmhm', []):
        add(m)
    return out


def signature_moves(sid, sd, all_species, exclude_arch=(), want=8, minimum=6):
    """6-10 distinct-archetype moves from the species' own learnset (falls back to its types' classics)."""
    pool = learnset(sd, all_species)
    chosen, used = [], set(exclude_arch)
    own = [m for m in pool if m in set(x for _, x in sd.get('learn', [])) | set(sd.get('moves1', []))]
    # prefer: own moves, then preview/evolved moves, then TM/HM, then type classics
    tiers = [own, [m for m in pool if m not in own], [m for t in sd.get('types', []) for m in TYPE_DEFAULTS.get(t, [])],
             [m for ts in TYPE_DEFAULTS.values() for m in ts]]
    for tier in tiers:
        for m in tier:
            arch = MOVE_ARCH[m][0]
            if arch in used or m in chosen:
                continue
            chosen.append(m)
            used.add(arch)
            if len(chosen) >= want:
                return chosen
        if len(chosen) >= minimum and tier is tiers[1]:
            break
    return chosen

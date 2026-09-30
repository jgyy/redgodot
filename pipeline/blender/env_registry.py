"""Registry of the extended prop sets (furniture / nature / town / building modules) for gen_world.py and gen_tiles.py.

GROUPS: [(set name, {prop name: (builder(style) -> Prop, note)})]   one glb per prop
SETS:   [(set name, {glb name: ([(piece name, arg)], builder(style, arg) -> Prop)})]   one glb holding several meshes
"""
import importlib

GROUPS = []
SETS = []
for _mod, _label in (('env_furn', 'furniture'), ('env_nature', 'nature'), ('env_town', 'town'), ('env_mods', 'building')):
    try:
        m = importlib.import_module(_mod)
    except ModuleNotFoundError as e:       # a set that is not written yet
        if e.name != _mod:
            raise
        continue
    for attr in ('FURN', 'NATURE', 'TOWN', 'MODS'):
        if hasattr(m, attr):
            GROUPS.append((_label, getattr(m, attr)))
    if hasattr(m, 'SETS'):
        SETS.append((_label, m.SETS))

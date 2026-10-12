"""Pants catalogue for the holster picker: groups of forge entries (male CP_ / female FCP_, all LODs)."""
import re

# female/alternate entry names that belong to another item
ALIASES = {
    'Marines_Pants': 'Marine_Pants',
    'RebellionLeader_Pants': 'Outfit_RebellionLeader_Pants',
    'Legs_PantsD_Holster_KneePadsA': 'Legs_PantsD_KneePads',
    'Legs_PantsD_Holster_KneePadsB': 'Legs_PantsD_KneePadsB',
}
# in-game names we know for sure (confirmed in game); everything else gets a cleaned-up file name
KNOWN_NAMES = {
    'Casual_JeansA_LegHolster': '70s Denim Jeans',
    'Tank_Pants': 'Tank Pants',
    'Apex_Pants_Holster': '5.11 APEX',
    'Apex_Pants_Holster_KneepadsA': '5.11 APEX (kneepads A)',
    'Apex_Pants_Holster_KneepadsB': '5.11 APEX (kneepads B)',
}
DEFAULT_SELECTION = ['Apex_Pants_Holster']

def group_of(entry_name):
    k = re.sub(r'_LOD\d$', '', entry_name)
    k = re.sub(r'^F?CP_', '', k)
    return ALIASES.get(k, k)

def display_name(group):
    if group in KNOWN_NAMES: return KNOWN_NAMES[group]
    s = re.sub(r'^(Legs_|Outfits?_)', '', group)
    s = s.replace('_Holster', '').replace('Holster_', '').replace('_', ' ').replace('-', ' ')
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', s)          # CamelCase -> words
    s = re.sub(r'\bKnee ?[Pp]ads\b', 'kneepads', s)
    return re.sub(r'\s+', ' ', s).strip()

def groups_from_cache(cache):
    """{group: set(entry names)} from a holster cache {forge: [names]}."""
    g = {}
    for names in cache.values():
        for n in names: g.setdefault(group_of(n), set()).add(n)
    return g

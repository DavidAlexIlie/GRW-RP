"""GRWRP core - Ghost Recon Wildlands roleplay mod: make chosen meshes (or parts of meshes) invisible.

Modified entries are appended to the end of the forge and the index/name table is re-pointed at
them; each profile keeps an undo file next to the forge with the original bytes.

Profiles (each an independent on/off toggle): weapons, backpack, earpiece, holster.
All functions work on the current directory = the game folder.
"""
import sys, os, re, json, struct, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anvildata as A, forgelist as FL, pants

MESHY = {0x415d9568, 0x51dc6b80}  # Mesh, LOD selector (holds LOD1..n meshes)
HOLSTER_MAT = re.compile(r'CP_Legs_LegHolster\w*')   # leg strap / platform
HOLSTER_SHEATH = 0x5a633ffab9                          # pistol sheath (material lives outside the pants entry)

def is_holster(mat_id, mat_name):
    return mat_id == HOLSTER_SHEATH or bool(HOLSTER_MAT.fullmatch(mat_name))

# Built-in model lists; a same-named .txt in <game>/civmod overrides them.
DEFAULT_LISTS = {
    'weapons_primary.txt': [r'WG?_SHG_SHORTY\w*'],
    'weapons_pistol.txt': [r'WG?_(HDG|AT)_Deagle\w*'],
    'backpack.txt': [r'CP_Backpack_Hydra(_LOD\d)?'],
    'earpiece.txt': [r'F?CP_Head_CivHeadSet\w*', r'F?CP_Head_HeadSet\w*'],
}
WEAPON_NAMES = {'primary': 'Super Shorty (all variants)', 'pistol': 'D-50 pistol'}
PROFILES = ('weapons', 'backpack', 'earpiece', 'holster')
LEGACY = 'main'  # old combined weapons+backpack profile

def nolog(*a): pass
def noprogress(frac, text=''): pass

def data_dir():
    d = os.path.join(os.getcwd(), 'civmod'); os.makedirs(d, exist_ok=True); return d

def undo_path(forge, profile):
    return forge + ('.civmod_undo.json' if profile == LEGACY else '.civmod_%s_undo.json' % profile)

def other_undos(forge, profile):
    me = os.path.normcase(undo_path(forge, profile))
    return [p for p in glob.glob(glob.escape(forge) + '.civmod*undo.json') if os.path.normcase(p) != me]

def all_forges():
    return sorted(glob.glob('*.forge') + glob.glob(os.path.join('dlc_*', '*.forge')))

def key(forge): return forge.replace('\\', '/')

def read_list(fname):
    p = os.path.join(data_dir(), fname)
    if os.path.exists(p):
        lines = [l.strip() for l in open(p) if l.strip() and not l.lstrip().startswith('#')]
    else:
        lines = DEFAULT_LISTS[fname]
    return '|'.join('(?:%s)' % l for l in lines) or r'(?!)'

# ---------------------------------------------------------------- patch / restore
def apply_rows(forge, rows, profile, transform, tick=noprogress):
    """Patch the given index rows of one forge; tick() is called once per row."""
    up = undo_path(forge, profile)
    if os.path.exists(up) or not rows:
        for _ in rows: tick()
        return 0
    undo = {'size': os.path.getsize(forge), 'patches': []}
    plans = []
    with open(forge, 'rb') as f:
        for ipos, off, sz, fid, typ, name, npos in rows:
            f.seek(off); d = f.read(sz)
            new, n = transform(d)
            tick()
            if not n: continue
            f.seek(ipos); old_i = f.read(20); f.seek(npos); old_n = f.read(4)
            undo['patches'] += [[ipos, old_i.hex()], [npos, old_n.hex()]]
            plans.append((ipos, npos, fid, new))
    if not plans: return 0
    with open(up, 'w') as u: json.dump(undo, u)  # written first so a crash mid-patch is still revertible
    with open(forge, 'r+b') as f:
        for ipos, npos, fid, new in plans:
            f.seek(0, 2); off = f.tell(); f.write(new)
            f.seek(ipos); f.write(struct.pack('<QQI', off, fid, len(new)))
            f.seek(npos); f.write(struct.pack('<I', len(new)))
        f.seek(0, 2); undo['end'] = f.tell()
    with open(up, 'w') as u: json.dump(undo, u)
    return len(plans)

def revert(forge, profile):
    up = undo_path(forge, profile)
    if not os.path.exists(up): return 0
    undo = json.load(open(up))
    with open(forge, 'r+b') as f:
        for pos, hx in undo['patches']:
            f.seek(pos); f.write(bytes.fromhex(hx))
        f.seek(0, 2)
        # cut our appended data off only if it is the last thing in the file and no other profile is active
        if f.tell() == undo.get('end', -1) and not other_undos(forge, profile):
            f.truncate(undo['size'])
    os.remove(up)
    return 1

def select_rows(rx_or_names):
    """[(forge, rows)] for MESHY entries whose name matches a regex or is in a name set."""
    out = []
    for fg in all_forges():
        if isinstance(rx_or_names, (set, frozenset)):
            rows = [r for r in FL.tables(fg) if r[4] in MESHY and r[5] in rx_or_names]
        else:
            rows = [r for r in FL.tables(fg) if r[4] in MESHY and rx_or_names.fullmatch(r[5])]
        if rows: out.append((fg, rows))
    return out

def run_rows(plan, profile, transform, progress, label):
    total = sum(len(r) for _, r in plan) or 1
    done = [0]
    def tick():
        done[0] += 1
        if done[0] % 4 == 0 or done[0] == total: progress(done[0] / total, label)
    return sum(apply_rows(fg, rows, profile, transform, tick) for fg, rows in plan)

# ---------------------------------------------------------------- holster cache
def cache_path(): return os.path.join(data_dir(), 'holster_cache.json')
def builtin_cache_path(): return os.path.join(getattr(sys, '_MEIPASS', HERE), 'holster_cache.json')

def _load(p):
    try: return {key(k): v for k, v in json.load(open(p)).items()}
    except Exception: return None

def cache_valid(cache):
    """The cache matches this install if (nearly) all its names exist in the local forges."""
    if not cache: return False
    have = want = 0
    for fg in all_forges():
        names = cache.get(key(fg))
        if not names: continue
        present = {r[5] for r in FL.tables(fg)}
        want += len(names); have += sum(1 for n in names if n in present)
    return want > 0 and have >= 0.9 * want

def scan_holster_cache(progress=noprogress):
    """Slow path: find every player model that has a holster (read-only)."""
    rx = re.compile(r'F?CP_\w*')
    plan = select_rows(rx); total = sum(len(r) for _, r in plan) or 1; done = 0
    cache = {}
    for fg, rows in plan:
        hits = []
        with open(fg, 'rb') as f:
            for r in rows:
                f.seek(r[1]); d = f.read(r[2])
                try:
                    if A.hide_submeshes(d, is_holster, log=nolog)[1]: hits.append(r[5])
                except Exception:
                    pass
                done += 1
                if done % 8 == 0: progress(done / total, 'Building pants list (first time only, 10-20 min)')
        if hits: cache[key(fg)] = sorted(hits)
    json.dump(cache, open(cache_path(), 'w'), indent=1)
    return cache

def holster_cache(progress=noprogress, allow_scan=True):
    for p in (cache_path(), builtin_cache_path()):
        c = _load(p)
        if c and cache_valid(c): return c
    return scan_holster_cache(progress) if allow_scan else None

def pants_catalogue(cache):
    """{group: set(entry names)} for the picker."""
    g = pants.groups_from_cache(cache)
    g.pop('PVP_ElWey_Body', None)
    return g

# ---------------------------------------------------------------- profiles
def is_on(profile):
    return any(os.path.exists(undo_path(fg, profile)) for fg in all_forges())

def status():
    return {p: is_on(p) for p in PROFILES}

def weapons_rx(mode):
    parts = []
    if mode in ('both', 'primary'): parts.append(read_list('weapons_primary.txt'))
    if mode in ('both', 'pistol'): parts.append(read_list('weapons_pistol.txt'))
    return re.compile('|'.join(parts) or r'(?!)')

def turn_on(profile, settings, progress=noprogress):
    whole = lambda d: A.hide_meshes(d, log=nolog)
    progress(0, 'Preparing')
    if profile == 'weapons':
        plan = select_rows(weapons_rx(settings.get('weapons_mode', 'both')))
        return run_rows(plan, profile, whole, progress, 'Patching')
    if profile in ('backpack', 'earpiece'):
        plan = select_rows(re.compile(read_list(profile + '.txt')))
        return run_rows(plan, profile, whole, progress, 'Patching')
    if profile == 'holster':
        cache = holster_cache(progress)
        cat = pants_catalogue(cache)
        sel = settings.get('holster_pants', pants.DEFAULT_SELECTION)
        groups = cat.keys() if sel == 'all' else [g for g in sel if g in cat]
        names = set().union(*[cat[g] for g in groups]) if groups else set()
        plan = select_rows(frozenset(names))
        tf = lambda d: A.hide_submeshes(d, is_holster, log=nolog)
        return run_rows(plan, profile, tf, progress, 'Patching')
    raise ValueError(profile)

def turn_off(profile, settings=None, progress=noprogress):
    fgs = [fg for fg in all_forges() if os.path.exists(undo_path(fg, profile))]
    for i, fg in enumerate(fgs):
        revert(fg, profile); progress((i + 1) / len(fgs), 'Restoring')
    return len(fgs)

def migrate_legacy():
    """Split the old combined 'main' undo into 'weapons' and 'backpack' undo files (no forge writes)."""
    bp = re.compile(read_list('backpack.txt'))
    moved = 0
    for fg in all_forges():
        up = undo_path(fg, LEGACY)
        if not os.path.exists(up): continue
        undo = json.load(open(up))
        parts = {'weapons': [], 'backpack': []}
        with open(fg, 'rb') as f:
            pairs = undo['patches']
            for i in range(0, len(pairs), 2):
                f.seek(pairs[i + 1][0] + 0x2c); name = f.read(128).split(b'\0')[0].decode('latin1')
                parts['backpack' if bp.fullmatch(name) else 'weapons'] += [pairs[i], pairs[i + 1]]
        for prof, pp in parts.items():
            if not pp: continue
            if os.path.exists(undo_path(fg, prof)): raise RuntimeError('both legacy and %s undo exist for %s' % (prof, fg))
            json.dump({'size': undo['size'], 'end': -1, 'patches': pp}, open(undo_path(fg, prof), 'w'))
        os.remove(up); moved += 1
    return moved

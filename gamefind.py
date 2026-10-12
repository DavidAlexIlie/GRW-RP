"""Locate a Ghost Recon Wildlands install, and detect whether the game is running."""
import os, re, json, glob, string, ctypes
from ctypes import wintypes

FOLDER_NAMES = ('Wildlands', "Tom Clancy's Ghost Recon Wildlands", 'Ghost Recon Wildlands', 'GhostReconWildlands')

def is_game_dir(d):
    return bool(d) and os.path.isfile(os.path.join(d, 'GRW.exe')) and os.path.isfile(os.path.join(d, 'DataPC.forge'))

def _reg(root, path, value):
    try:
        import winreg
        with winreg.OpenKey(root, path) as k: return winreg.QueryValueEx(k, value)[0]
    except Exception:
        return None

def _reg_subkeys(root, path):
    try:
        import winreg
        with winreg.OpenKey(root, path) as k:
            i = 0
            while True:
                try: yield winreg.EnumKey(k, i); i += 1
                except OSError: return
    except Exception:
        return

def steam_candidates():
    import winreg
    roots = {_reg(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
             _reg(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')}
    libs = set()
    for r in filter(None, roots):
        libs.add(os.path.normpath(r))
        vdf = os.path.join(r, 'steamapps', 'libraryfolders.vdf')
        try:
            for p in re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='ignore').read()):
                libs.add(os.path.normpath(p.replace('\\\\', '\\')))
        except Exception:
            pass
    for lib in libs:
        for n in FOLDER_NAMES: yield os.path.join(lib, 'steamapps', 'common', n)

def ubisoft_candidates():
    import winreg
    base = r'SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs'
    for sub in _reg_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        d = _reg(winreg.HKEY_LOCAL_MACHINE, base + '\\' + sub, 'InstallDir')
        if d: yield os.path.normpath(d)
    launcher = _reg(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Ubisoft\Launcher', 'InstallDir')
    if launcher:
        for n in FOLDER_NAMES: yield os.path.join(launcher, 'games', n)

def epic_candidates():
    for item in glob.glob(r'C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item'):
        try: yield os.path.normpath(json.load(open(item, encoding='utf-8'))['InstallLocation'])
        except Exception: pass

def drive_candidates():
    for dl in string.ascii_uppercase:
        drive = dl + ':\\'
        if not os.path.exists(drive): continue
        for base in ('SteamLibrary\\steamapps\\common', 'Steam\\steamapps\\common',
                     'Program Files (x86)\\Steam\\steamapps\\common', 'Program Files\\Steam\\steamapps\\common',
                     'Games', 'Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\games',
                     'Program Files\\Epic Games', 'Epic Games', ''):
            for n in FOLDER_NAMES: yield os.path.join(drive, base, n)

STEAM_APPID = '460930'

def _rank(d):
    """Prefer an install we already modded, then one Steam actually tracks, then the newest exe."""
    modded = bool(glob.glob(os.path.join(glob.escape(d), '*.civmod*undo.json')))
    steamapps = os.path.dirname(os.path.dirname(d))
    tracked = os.path.isfile(os.path.join(steamapps, 'appmanifest_%s.acf' % STEAM_APPID))
    try: mtime = os.path.getmtime(os.path.join(d, 'GRW.exe'))
    except OSError: mtime = 0
    return (modded, tracked, mtime)

def find_all():
    """[(folder, source)] for every install found, best first."""
    found = {}
    for source, gen in (('Steam library', steam_candidates), ('Ubisoft Connect', ubisoft_candidates),
                        ('Epic Games', epic_candidates), ('disk', drive_candidates)):
        try:
            for d in gen():
                k = os.path.normcase(os.path.normpath(d))
                if k not in found and is_game_dir(d): found[k] = (os.path.normpath(d), source)
        except Exception:
            pass
    return sorted(found.values(), key=lambda x: _rank(x[0]), reverse=True)

def find_game():
    """(folder, source) or (None, None). A copy of GRWRP placed inside the game folder wins."""
    import sys
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    for d in (here, os.path.dirname(here)):
        if is_game_dir(d): return os.path.normpath(d), 'this folder'
    allf = find_all()
    return allf[0] if allf else (None, None)

# ---- running-process check without spawning a console (Toolhelp32 snapshot)
class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]

def process_running(exe='GRW.exe'):
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if snap in (None, wintypes.HANDLE(-1).value): return False
    try:
        e = PROCESSENTRY32W(); e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == exe.lower(): return True
            ok = k32.Process32NextW(snap, ctypes.byref(e))
        return False
    finally:
        k32.CloseHandle(snap)

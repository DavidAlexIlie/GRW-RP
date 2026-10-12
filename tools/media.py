"""Make Nexus media images: a 1300x372 header and app screenshots (rendered at 2x).
Run from the game folder:  python tools/media.py <src_dir> <out_dir>
Uses a temporary config, so your real GRWRP settings are not touched. No game files are modified."""
import os, sys, tempfile, time
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
os.environ['QT_SCALE_FACTOR'] = '2'
os.environ['APPDATA'] = tempfile.mkdtemp()
os.environ['LOCALAPPDATA'] = os.path.join(out, '_cache')
sys.path.insert(0, src)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
import app as A
from PIL import Image, ImageDraw, ImageFont, ImageFilter

qa = QApplication([]); qa.setFont(QFont('Segoe UI', 10)); qa.setStyleSheet(A.QSS)
def pump(n=40):
    for _ in range(n): qa.processEvents()
A.Main.start_job = lambda self, op, prof: None          # never patch anything from here

w = A.Main(); w.setAttribute(Qt.WA_DontShowOnScreen); w.show(); pump()
t0 = time.time()
while w.prep is None and time.time() - t0 < 30: pump(5); time.sleep(0.05)     # game found, prep started
while w.prep is not None and w.prep.isRunning(): pump(5); time.sleep(0.05)   # previews ready
w.cfg['coach_seen'] = True; w.toast.hide(); w.refresh(animate=False); pump()
shots = {}
def grab(widget, name):
    pump(); p = os.path.join(out, '_' + name + '.png'); widget.grab().save(p); shots[name] = p

grab(w, 'main')
dlg = A.PantsPicker(w, A.G.pants_catalogue(w.prep.cache), ['Apex_Pants_Holster', 'Tank_Pants', 'Casual_JeansA_LegHolster',
                    'Outfit_Survivor_Jeans', 'Gorka_Pants'], None)
dlg.setAttribute(Qt.WA_DontShowOnScreen); dlg.show(); pump(); grab(dlg, 'picker')
A.F.process_running = lambda exe='GRW.exe': True; w.check_game(); w.lock.anim.stop(); w.lock.fx.setOpacity(1.0); grab(w, 'locked')
A.F.process_running = lambda exe='GRW.exe': False; w.check_game(); pump(60); w.lock.hide()
s = A.SettingsDialog(w); s.setAttribute(Qt.WA_DontShowOnScreen); s.show(); grab(s, 'settings')

# ---------------------------------------------------------------- compose
BG, ACC, TEXT, MUTED = (18, 21, 24), (212, 162, 76), (232, 234, 236), (138, 147, 157)
FONTS = r'C:\Windows\Fonts'
def bahn(size):
    f = ImageFont.truetype(os.path.join(FONTS, 'bahnschrift.ttf'), size); f.set_variation_by_name('SemiBold SemiCondensed'); return f
def segoe(size): return ImageFont.truetype(os.path.join(FONTS, 'segoeui.ttf'), size)

def backdrop(size):
    im = Image.new('RGB', size, BG); d = ImageDraw.Draw(im)
    for i in range(0, size[0] + size[1], 40):  # faint diagonal texture
        d.line([(i, 0), (i - size[1], size[1])], fill=(22, 25, 29), width=2)
    return im

def shadowed(im, shot, xy):
    sh = Image.new('RGBA', (shot.width + 80, shot.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 50, shot.width + 40, shot.height + 50), 20, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(18)); im.paste(sh, (xy[0] - 40, xy[1] - 40), sh); im.paste(shot, xy)

def card(name, caption, sub, size=(1920, 1080)):
    im = backdrop(size); d = ImageDraw.Draw(im)
    shot = Image.open(shots[name]).convert('RGB')
    scale = min(1, (size[1] - 120) / shot.height, (size[0] * 0.55) / shot.width)
    shot = shot.resize((int(shot.width * scale), int(shot.height * scale)), Image.LANCZOS)
    shadowed(im, shot, (size[0] - shot.width - 140, (size[1] - shot.height) // 2))
    d.text((120, size[1] // 2 - 110), caption, font=bahn(56), fill=TEXT)
    d.rectangle((120, size[1] // 2 - 12, 220, size[1] // 2 - 6), fill=ACC)
    yy = size[1] // 2 + 30
    for line in sub:
        d.text((120, yy), line, font=segoe(30), fill=MUTED); yy += 44
    return im

card('main', 'Four switches.', ['Hide weapons, backpack, earpiece', 'and pants holsters.', 'Changes apply next time you start the game.']).save(os.path.join(out, '02_app.png'))
card('picker', 'Pick your pants.', ['Choose exactly which pants lose', 'their leg holster. Previews are', 'rendered from your own game files.']).save(os.path.join(out, '03_pants_picker.png'))
card('settings', 'Choose what "weapons" means.', ['Primary only, pistol only, or both.']).save(os.path.join(out, '04_settings.png'))
card('locked', 'Safe by design.', ['Locks itself while the game runs.', 'Every change can be switched off', 'and restored.']).save(os.path.join(out, '05_locked.png'))

# ---------------------------------------------------------------- header 1300x372
HW, HH = 1300, 372
H = backdrop((HW, HH)); d = ImageDraw.Draw(H)
icon = Image.open(os.path.join(src, 'icon.ico')).convert('RGBA').resize((150, 150), Image.LANCZOS)
H.paste(icon, (56, (HH - 150) // 2), icon)
tx = 236
TW, TH, GAP = 140, 120, 10                       # preview tiles, right-aligned
tiles_x = HW - 48 - 3 * TW - 2 * GAP
size = 64                                        # shrink the title until it clears the tiles
while d.textlength('HIDE WEAPONS AND GEAR', font=bahn(size)) > tiles_x - tx - 36: size -= 2
d.text((tx, 100), 'HIDE WEAPONS AND GEAR', font=bahn(size), fill=TEXT)
d.text((tx + 2, 100 + size + 14), 'CIVILIAN ROLEPLAY  ·  GRWRP', font=bahn(32), fill=ACC)
d.text((tx + 3, 100 + size + 66), 'Ghost Recon Wildlands', font=segoe(20), fill=MUTED)
d.text((tx + 3, 100 + size + 94), 'weapons · backpack · earpiece · holsters', font=segoe(20), fill=MUTED)
thumbs = os.path.join(os.environ['LOCALAPPDATA'], 'GRWRP', 'thumbs')
for i, g in enumerate(['Apex_Pants_Holster', 'Casual_JeansA_LegHolster', 'Tank_Pants']):
    p = os.path.join(thumbs, g + '.png')
    if os.path.exists(p):
        t = Image.open(p).convert('RGB').resize((TW, TH), Image.LANCZOS)
        mask = Image.new('L', t.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, TW - 1, TH - 1), 12, fill=255)
        H.paste(t, (tiles_x + i * (TW + GAP), (HH - TH) // 2 - 18 + (i % 2) * 36), mask)
H.save(os.path.join(out, '00_header.png'))
for p in shots.values(): os.remove(p)
print('written:', sorted(f for f in os.listdir(out) if f.endswith('.png')))

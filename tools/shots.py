"""Render every GRWRP screen off-screen to PNGs (no window appears, no game files are modified)."""
import os, sys, tempfile
out = sys.argv[2]; os.makedirs(out, exist_ok=True)
os.environ['APPDATA'] = tempfile.mkdtemp(); os.environ['LOCALAPPDATA'] = tempfile.mkdtemp()
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QFont, QIcon
import app as A

qa = QApplication([]); qa.setFont(QFont('Segoe UI', 10)); qa.setStyleSheet(A.QSS)
def pump(n=30):
    for _ in range(n): qa.processEvents()
def shot(w, name): pump(); w.grab().save(os.path.join(out, name + '.png'))

# never start real jobs from this script
A.Main.start_job = lambda self, op, prof: None

w = A.Main(); w.setAttribute(Qt.WA_DontShowOnScreen); w.show(); pump()
w.stack.setCurrentIndex(0); shot(w, '1_searching')
w.stack.setCurrentIndex(1); w.nf_err.setText("GRW.exe isn't in this folder."); shot(w, '2_notfound')
w.search(); pump(); w.show_coach(); shot(w, '3_main_first_run')
w.coach.dismiss(); w.toast.hide()
c = w.cards['holster']; c.set_running(True); c.set_progress(0.58, 'Patching')
for p, o in w.cards.items():
    if p != 'holster': o.set_dimmed(True)
shot(w, '4_running')
for o in w.cards.values(): o.set_running(False); o.set_dimmed(False)
w.cards['earpiece'].set_error(True)
w.cards['earpiece'].set_subtitle('<span style="color:%s">Couldn\'t apply. Click the switch to retry.</span> <a href="#" style="color:%s">Details</a>' % (A.ERR, A.MUTED))
shot(w, '5_error')
w.cards['earpiece'].set_error(False); w.refresh()
A.F.process_running = lambda exe='GRW.exe': True; w.check_game(); pump(60)
w.lock.anim.stop(); w.lock.fx.setOpacity(1.0); pump(); shot(w, '6_locked')
A.F.process_running = lambda exe='GRW.exe': False; w.check_game(); pump(60)

cache = A.G.holster_cache(allow_scan=False)
dlg = A.PantsPicker(w, A.G.pants_catalogue(cache), ['Apex_Pants_Holster', 'Tank_Pants', 'Casual_JeansA_LegHolster', 'SPETSNAZ_TACHANKA_Holster', 'FBI_CASTLE_Holster'])
dlg.setAttribute(Qt.WA_DontShowOnScreen); dlg.show(); pump(); shot(dlg, '7a_picker_generating')
import time; t0=time.time()
while dlg.thumbs and dlg.thumbs.isRunning(): pump(5); time.sleep(0.05)
print('thumbs took %.1fs' % (time.time()-t0)); pump(); shot(dlg, '7_picker')
for c in dlg.cards: c.setVisible(c.group in ('SPETSNAZ_TACHANKA_Holster','FBI_CASTLE_Holster','GIGN_DOC_Holster','Kozack_Pants','Gorka_Pants'))
dlg.flow.invalidate(); pump(); shot(dlg, '7b_picker_filtered')
s = A.SettingsDialog(w); s.setAttribute(Qt.WA_DontShowOnScreen); s.show(); pump(); shot(s, '8_settings')
print('ok')

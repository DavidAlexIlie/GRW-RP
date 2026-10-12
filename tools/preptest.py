"""Start GRWRP off-screen with empty app data and check that previews get rendered with no clicks."""
import os, sys, tempfile, time
os.environ['APPDATA'] = tempfile.mkdtemp(); os.environ['LOCALAPPDATA'] = tempfile.mkdtemp()
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
import app as A
qa = QApplication([]); qa.setFont(QFont('Segoe UI', 10)); qa.setStyleSheet(A.QSS)
A.Main.start_job = lambda self, op, prof: None
w = A.Main(); w.setAttribute(Qt.WA_DontShowOnScreen); w.show()
t0 = time.time()
while time.time() - t0 < 5: qa.processEvents(); time.sleep(0.02)
print('prep started:', w.prep is not None and w.prep.isRunning(), '| cache ok after 5s:', w.cache_ok)
while w.prep is not None and w.prep.isRunning(): qa.processEvents(); time.sleep(0.05)
n = len([f for f in os.listdir(A.THUMBS) if f.endswith('.png')]) if os.path.isdir(A.THUMBS) else 0
print('prep done in %.0fs, thumbnails: %d' % (time.time() - t0, n))

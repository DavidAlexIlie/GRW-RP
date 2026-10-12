"""GRWRP - Ghost Recon Wildlands RolePlay (PySide6 UI)."""
import os, sys, json, traceback

from PySide6.QtCore import (Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve, QRectF, QPoint,
                            QSize, QRect, Property)
from PySide6.QtGui import QIcon, QPainter, QColor, QPen, QFont, QPixmap, QPainterPath, QCursor, QBrush
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
                               QPushButton, QToolButton, QProgressBar, QStackedWidget, QGraphicsBlurEffect,
                               QGraphicsOpacityEffect, QDialog, QLineEdit, QScrollArea, QRadioButton, QButtonGroup,
                               QFileDialog, QMessageBox, QLayout, QSizePolicy, QToolTip)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ghostcivmod as G, gamefind as F, pants

# Picker previews are rendered locally from the user's own game files (nothing from the game ships in the exe).
THUMBS = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'GRWRP', 'thumbs')
def thumb_path(group): return os.path.join(THUMBS, group + '.png')

APP = 'GRWRP'
RES = getattr(sys, '_MEIPASS', HERE)
def res(*p): return os.path.join(RES, *p)

# ------------------------------------------------------------------ palette / type
BG, SURF, SURF_H, BORDER = '#121518', '#1B1F24', '#232830', '#2E343C'
TEXT, MUTED = '#E8EAEC', '#8A939D'
ACC, ACC_P, OK, ERR, INFO = '#D4A24C', '#B8873A', '#6FAE5E', '#D65A4F', '#5E9BD6'
def tfont(pt):
    """Bahnschrift SemiBold SemiCondensed: ships with Windows 10/11, condensed DIN look."""
    from PySide6.QtGui import QFontDatabase
    f = QFontDatabase.font('Bahnschrift', 'SemiBold SemiCondensed', pt)
    if f.family() != 'Bahnschrift': f = QFont('Segoe UI', pt, QFont.DemiBold)
    f.setPointSize(pt); return f

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT}; }}
QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {MUTED}; font-size: 9pt; }}
QFrame#card {{ background: {SURF}; border: 1px solid {BORDER}; border-radius: 8px; }}
QFrame#card QWidget {{ background: transparent; }}
QFrame#card[error="true"] {{ border-left: 2px solid {ERR}; }}
QFrame#banner {{ background: {SURF}; border-top: 1px solid {BORDER}; }}
QPushButton {{ background: {SURF_H}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 16px; }}
QPushButton:hover {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; background: {SURF}; }}
QPushButton#primary {{ background: {ACC}; color: {BG}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACC_P}; }}
QPushButton#primary:disabled {{ background: {BORDER}; color: {MUTED}; }}
QPushButton#link {{ background: transparent; border: none; color: {ACC}; padding: 0; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QToolButton {{ background: transparent; border: none; border-radius: 6px; }}
QToolButton:hover {{ background: {SURF_H}; }}
QProgressBar {{ background: {BORDER}; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }}
QProgressBar::chunk {{ background: {ACC}; border-radius: 2px; }}
QLineEdit {{ background: {SURF}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px; }}
QLineEdit:focus {{ border-color: {ACC}; }}
QRadioButton {{ background: transparent; spacing: 8px; }}
QRadioButton::indicator {{ width: 14px; height: 14px; border-radius: 8px; border: 2px solid {MUTED}; }}
QRadioButton::indicator:checked {{ border: 2px solid {ACC}; background: qradialgradient(cx:.5, cy:.5, radius:.5,
    fx:.5, fy:.5, stop:0 {ACC}, stop:.55 {ACC}, stop:.6 transparent); }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: {BG}; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QToolTip {{ background: {SURF_H}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px 8px; }}
QMessageBox {{ background: {BG}; }}
"""

# ------------------------------------------------------------------ config
CONFIG = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP, 'config.json')

def load_config():
    try: return json.load(open(CONFIG))
    except Exception: return {}

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    json.dump(cfg, open(CONFIG, 'w'), indent=1)

# ------------------------------------------------------------------ small painted widgets
class Switch(QWidget):
    toggled = Signal()
    def __init__(self):
        super().__init__(); self.setFixedSize(44, 24); self.setCursor(Qt.PointingHandCursor)
        self._on = False; self._pos = 0.0
        self.anim = QPropertyAnimation(self, b'knob', self); self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
    def getKnob(self): return self._pos
    def setKnob(self, v): self._pos = v; self.update()
    knob = Property(float, getKnob, setKnob)
    def set_on(self, on, animate=True):
        self._on = on
        if animate: self.anim.stop(); self.anim.setEndValue(1.0 if on else 0.0); self.anim.start()
        else: self.setKnob(1.0 if on else 0.0)
    def mouseReleaseEvent(self, e):
        if self.isEnabled() and e.button() == Qt.LeftButton: self.toggled.emit()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
        t = self._pos
        off, on = QColor(BORDER), QColor(ACC)
        track = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                       int(off.blue() + (on.blue() - off.blue()) * t))
        p.setBrush(track); p.drawRoundedRect(QRectF(0, 2, 44, 20), 10, 10)
        p.setBrush(QColor(BG) if t > .5 else QColor(MUTED))
        x = 4 + t * 20; p.drawEllipse(QRectF(x, 6, 16, 12).adjusted(0, -2, 0, 2))

class Spinner(QWidget):
    def __init__(self, size=20, color=ACC):
        super().__init__(); self.setFixedSize(size, size); self.a = 0; self.color = color
        self.t = QTimer(self); self.t.timeout.connect(self._step); self.t.start(16)
    def _step(self): self.a = (self.a + 6) % 360; self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(self.color), max(2, self.width() // 9)); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
        m = pen.width(); r = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        p.drawArc(r, -self.a * 16, 270 * 16)

def glyph_pixmap(kind, size=18, color=MUTED):
    """Tiny line icons drawn in code: 'pants', 'info', 'cog', 'lock', 'warn'."""
    pm = QPixmap(size * 2, size * 2); pm.fill(Qt.transparent); pm.setDevicePixelRatio(2)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    s = size; c = QColor(color)
    if kind == 'pants':
        path = QPainterPath(); path.moveTo(s*.25, s*.12); path.lineTo(s*.75, s*.12); path.lineTo(s*.82, s*.88)
        path.lineTo(s*.6, s*.88); path.lineTo(s*.5, s*.4); path.lineTo(s*.4, s*.88); path.lineTo(s*.18, s*.88)
        path.closeSubpath(); p.setPen(Qt.NoPen); p.setBrush(c); p.drawPath(path)
    elif kind == 'info':
        p.setPen(QPen(c, 1.4)); p.drawEllipse(QRectF(s*.12, s*.12, s*.76, s*.76))
        f = QFont('Segoe UI', max(6, int(s * .42))); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, 'i')
    elif kind == 'cog':
        p.setPen(QPen(c, 1.6)); p.setBrush(Qt.NoBrush)
        p.translate(s / 2, s / 2)
        for i in range(8):
            p.save(); p.rotate(i * 45); p.drawLine(QPoint(0, int(-s*.32)), QPoint(0, int(-s*.44))); p.restore()
        p.drawEllipse(QRectF(-s*.3, -s*.3, s*.6, s*.6)); p.drawEllipse(QRectF(-s*.11, -s*.11, s*.22, s*.22))
    elif kind == 'lock':
        p.setPen(QPen(c, s * .07)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(s*.3, s*.12, s*.4, s*.46), 0, 180 * 16)
        p.drawLine(QPoint(int(s*.3), int(s*.35)), QPoint(int(s*.3), int(s*.45)))
        p.drawLine(QPoint(int(s*.7), int(s*.35)), QPoint(int(s*.7), int(s*.45)))
        p.setPen(Qt.NoPen); p.setBrush(c); p.drawRoundedRect(QRectF(s*.2, s*.44, s*.6, s*.44), s*.06, s*.06)
        p.setBrush(QColor(BG)); p.drawEllipse(QRectF(s*.45, s*.56, s*.1, s*.1)); p.drawRect(QRectF(s*.48, s*.62, s*.04, s*.12))
    elif kind == 'warn':
        path = QPainterPath(); path.moveTo(s*.5, s*.1); path.lineTo(s*.92, s*.86); path.lineTo(s*.08, s*.86)
        path.closeSubpath(); p.setPen(Qt.NoPen); p.setBrush(c); p.drawPath(path)
        p.setBrush(QColor(BG)); p.drawRect(QRectF(s*.46, s*.36, s*.08, s*.28)); p.drawEllipse(QRectF(s*.455, s*.7, s*.09, s*.09))
    elif kind == 'check':
        p.setPen(Qt.NoPen); p.setBrush(QColor(ACC)); p.drawEllipse(QRectF(0, 0, s, s))
        pen = QPen(QColor(BG), s * .14); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
        p.drawPolyline([QPoint(int(s*.28), int(s*.52)), QPoint(int(s*.44), int(s*.68)), QPoint(int(s*.72), int(s*.36))])
    p.end(); return pm

class HoverInfo(QLabel):
    """'i' icon that shows a popover as soon as the mouse is over it."""
    def __init__(self, text_fn):
        super().__init__(); self.text_fn = text_fn
        self.setPixmap(glyph_pixmap('info', 16)); self.setCursor(Qt.WhatsThisCursor)
    def enterEvent(self, e):
        QToolTip.showText(QCursor.pos() + QPoint(10, 12), '<div style="max-width:240px">%s</div>' % self.text_fn(), self)
    def leaveEvent(self, e): QToolTip.hideText()

# ------------------------------------------------------------------ toggle card
class Card(QFrame):
    def __init__(self, title, subtitle, info_fn=None, picker=None):
        super().__init__(); self.setObjectName('card'); self.base_sub = subtitle
        v = QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(2)
        row = QHBoxLayout(); row.setSpacing(6)
        self.title = QLabel(title); self.title.setStyleSheet('font-size: 11pt; font-weight: 600;')
        row.addWidget(self.title)
        if info_fn: row.addWidget(HoverInfo(info_fn))
        if picker:
            b = QToolButton(); b.setIcon(QIcon(glyph_pixmap('pants', 18, TEXT))); b.setIconSize(QSize(18, 18))
            b.setFixedSize(28, 28); b.setToolTip('Choose which pants'); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(picker); row.addWidget(b); self.picker_btn = b
        row.addStretch(1)
        self.switch = Switch(); self.spinner = Spinner(); self.spinner.hide()
        row.addWidget(self.spinner); row.addWidget(self.switch)
        v.addLayout(row)
        self.sub = QLabel(subtitle); self.sub.setProperty('muted', True); self.sub.setWordWrap(True)
        self.sub.setTextFormat(Qt.RichText); self.sub.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        v.addWidget(self.sub)
        self.prog_box = QWidget(); pv = QVBoxLayout(self.prog_box); pv.setContentsMargins(0, 6, 0, 0); pv.setSpacing(3)
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.setTextVisible(False)
        self.prog_lbl = QLabel(''); self.prog_lbl.setProperty('muted', True)
        pv.addWidget(self.bar); pv.addWidget(self.prog_lbl); self.prog_box.hide(); v.addWidget(self.prog_box)
        self.opacity = QGraphicsOpacityEffect(self); self.opacity.setOpacity(1.0); self.setGraphicsEffect(self.opacity)

    def set_subtitle(self, html=None): self.sub.setText(html or self.base_sub)
    def set_error(self, on):
        self.setProperty('error', on); self.style().unpolish(self); self.style().polish(self)
    def set_running(self, running, show_progress=True):
        self.switch.setVisible(not running); self.spinner.setVisible(running)
        self.prog_box.setVisible(running and show_progress)
        if running: self.bar.setValue(0); self.prog_lbl.setText('Starting…')
    def set_progress(self, frac, text):
        self.bar.setValue(int(frac * 1000)); self.prog_lbl.setText('%s… %d%%' % (text, frac * 100))
    def set_dimmed(self, dim):
        self.opacity.setOpacity(0.5 if dim else 1.0); self.setEnabled(not dim)
        self.setToolTip('Wait for the current task to finish' if dim else '')

# ------------------------------------------------------------------ worker
class Worker(QThread):
    progress = Signal(float, str)
    done = Signal(bool, str)
    def __init__(self, op, profile, settings):
        super().__init__(); self.op, self.profile, self.settings = op, profile, settings
    def run(self):
        cb = lambda f, t='': self.progress.emit(float(f), t)
        try:
            if self.op in ('off', 'reapply'): G.turn_off(self.profile, self.settings, cb)
            if self.op in ('on', 'reapply'): G.turn_on(self.profile, self.settings, cb)
            if self.op == 'scan': G.holster_cache(cb)
            self.done.emit(True, '')
        except Exception:
            self.done.emit(False, traceback.format_exc())

# ------------------------------------------------------------------ overlays
class LockOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.setAttribute(Qt.WA_StyledBackground, False)
        v = QVBoxLayout(self); v.setAlignment(Qt.AlignCenter); v.setSpacing(6)
        icon = QLabel(); icon.setPixmap(glyph_pixmap('lock', 48, ACC)); icon.setAlignment(Qt.AlignCenter)
        t = QLabel('Game is running'); t.setAlignment(Qt.AlignCenter)
        t.setFont(tfont(16))
        s = QLabel('Close Ghost Recon Wildlands to\nchange settings.'); s.setAlignment(Qt.AlignCenter)
        m = QLabel('Unlocks automatically.'); m.setProperty('muted', True); m.setAlignment(Qt.AlignCenter)
        for w in (icon, t, s, m): v.addWidget(w)
        self.fx = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self.fx)
        self.anim = QPropertyAnimation(self.fx, b'opacity', self); self.anim.setDuration(200)
        self.anim.finished.connect(self._after); self.hide()
    snapshot = None
    def set_background(self, widget):
        img = widget.grab().toImage()
        small = img.scaled(max(1, img.width() // 10), max(1, img.height() // 10),
                           Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        small = small.scaled(max(1, img.width() // 4), max(1, img.height() // 4),
                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.snapshot = QPixmap.fromImage(small)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.snapshot: p.drawPixmap(self.rect(), self.snapshot)
        c = QColor(BG); c.setAlphaF(0.72); p.fillRect(self.rect(), c)
    def mousePressEvent(self, e): e.accept()
    def fade(self, show):
        self._showing = show; self.anim.stop()
        self.anim.setStartValue(self.fx.opacity() if self.isVisible() else 0.0)
        self.anim.setEndValue(1.0 if show else 0.0)
        if show: self.show(); self.raise_()
        self.anim.start()
    def _after(self):
        if not self._showing: self.hide()

class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent); self.hide()
        self.setStyleSheet(f'background: {SURF_H}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px 14px;')
        self.fx = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self.fx)
        self.anim = QPropertyAnimation(self.fx, b'opacity', self); self.anim.setDuration(250)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self._out)
        self.anim.finished.connect(lambda: self.fx.opacity() < .05 and self.hide())
    def show_msg(self, text, ms=3000):
        self.setText(text); self.adjustSize(); p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 70)
        self.show(); self.raise_(); self.anim.stop(); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0)
        self.anim.start(); self.timer.start(ms)
    def _out(self):
        self.anim.stop(); self.anim.setStartValue(1.0); self.anim.setEndValue(0.0); self.anim.start()

class CoachMark(QLabel):
    def __init__(self, parent, text, on_dismiss):
        super().__init__(text, parent); self.on_dismiss = on_dismiss
        self.setStyleSheet(f'background: {ACC}; color: {BG}; border-radius: 6px; padding: 8px 12px; font-weight: 600;')
        self.setCursor(Qt.PointingHandCursor); self.adjustSize()
    def mousePressEvent(self, e): self.dismiss()
    def dismiss(self):
        if self.isVisible(): self.hide(); self.on_dismiss()

# ------------------------------------------------------------------ flow layout (for the pants grid)
class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=8):
        super().__init__(parent); self.items = []; self.sp = spacing
    def addItem(self, it): self.items.append(it)
    def count(self): return len(self.items)
    def itemAt(self, i): return self.items[i] if 0 <= i < len(self.items) else None
    def takeAt(self, i): return self.items.pop(i) if 0 <= i < len(self.items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QRect(0, 0, w, 0), True)
    def setGeometry(self, r): super().setGeometry(r); self._do(r, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self.items: s = s.expandedTo(it.minimumSize())
        return s + QSize(16, 16)
    def _do(self, r, test):
        x, y, line = r.x() + 8, r.y() + 8, 0
        for it in self.items:
            if it.widget().isHidden():
                if not test: it.setGeometry(QRect())
                continue
            w, h = it.sizeHint().width(), it.sizeHint().height()
            if x + w > r.right() - 8 and line > 0: x = r.x() + 8; y += line + self.sp; line = 0
            if not test: it.setGeometry(QRect(QPoint(x, y), it.sizeHint()))
            x += w + self.sp; line = max(line, h)
        return y + line + 8 - r.y()

# ------------------------------------------------------------------ pants picker
class PrepWorker(QThread):
    """Runs right after the game folder is known: makes sure the pants list matches this install (builds it
    once if it doesn't) and renders every missing picker preview. Pauses while a patch job writes the archives."""
    status = Signal(str)                 # progress text while the pants list is being built, '' when ready
    cache_ready = Signal()
    thumb_ready = Signal(str, int, int)
    def __init__(self):
        super().__init__(); self.paused = False; self.stop = False; self.cache = None; self.thumbs_left = 0
    def _gate(self):
        while self.paused and not self.stop: self.msleep(200)
    def run(self):
        try:
            self.cache = G.holster_cache(allow_scan=False)
            if not self.cache:
                def cb(f, t=''):
                    self._gate(); self.status.emit('Preparing pants list (first run only)… %d%%' % (f * 100))
                self.cache = G.scan_holster_cache(cb)
            self.status.emit(''); self.cache_ready.emit()
            cat = G.pants_catalogue(self.cache)
            missing = sorted(g for g in cat if not os.path.exists(thumb_path(g)))
            self.thumbs_left = len(missing)
            if not missing or self.stop: return
            import render_thumbs as R
            os.makedirs(THUMBS, exist_ok=True); fx = R.Forges()
            for k, g in enumerate(missing, 1):
                self._gate()
                if self.stop: return
                try: R.render_group(fx, g, cat[g], thumb_path(g), res('logos'))
                except Exception: pass
                self.thumbs_left = len(missing) - k
                self.thumb_ready.emit(g, k, len(missing))
        except Exception:
            traceback.print_exc()

class PantsCard(QFrame):
    changed = Signal()
    def __init__(self, group, name):
        super().__init__(); self.group, self.selected = group, False
        self.setFixedSize(116, 140); self.setCursor(Qt.PointingHandCursor); self.setToolTip(group)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 2); v.setSpacing(2)  # the 2px QSS border already insets the contents
        img = QLabel(); img.setFixedSize(112, 96); img.setAlignment(Qt.AlignCenter); self.img = img
        self.set_thumb()
        img.setStyleSheet(f'background: {SURF_H}; border: none; border-top-left-radius: 6px; border-top-right-radius: 6px;')
        t = QLabel(name); t.setWordWrap(True); t.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        t.setStyleSheet('font-size: 8.5pt; padding: 0 4px; border: none;'); t.setFixedHeight(34)
        v.addWidget(img); v.addWidget(t)
        self.badge = QLabel(self); self.badge.setPixmap(glyph_pixmap('check', 18)); self.badge.move(92, 8)
        self.hover = False; self.refresh()
    def set_thumb(self):
        p = thumb_path(self.group)
        if os.path.exists(p):
            pm = QPixmap(p); pm.setDevicePixelRatio(2); self.img.setPixmap(pm)
        else:
            self.img.setPixmap(glyph_pixmap('pants', 40, MUTED))
    def refresh(self):
        self.badge.setVisible(self.selected)
        bg = SURF_H if self.hover else SURF
        bd = f'2px solid {ACC}' if self.selected else f'2px solid {BORDER}'
        self.setStyleSheet(f'PantsCard {{ background: {bg}; border: {bd}; border-radius: 8px; }}')
    def enterEvent(self, e): self.hover = True; self.refresh()
    def leaveEvent(self, e): self.hover = False; self.refresh()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton: self.selected = not self.selected; self.refresh(); self.changed.emit()

class PantsPicker(QDialog):
    def __init__(self, parent, catalogue, selection, prep=None):
        super().__init__(parent); self.setWindowTitle('Choose pants'); self.resize(680, 560)
        v = QVBoxLayout(self); v.setContentsMargins(16, 14, 16, 14); v.setSpacing(10)
        top = QHBoxLayout()
        h = QLabel('Holsters will be removed from the selected pants.'); h.setProperty('muted', True)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search…'); self.search.setFixedWidth(170)
        self.search.textChanged.connect(self.filter)
        a = QPushButton('Select all'); a.setObjectName('link'); a.clicked.connect(lambda: self.set_all(True))
        n = QPushButton('None'); n.setObjectName('link'); n.clicked.connect(lambda: self.set_all(False))
        top.addWidget(h, 1); top.addWidget(self.search); top.addSpacing(8); top.addWidget(a)
        dot = QLabel('·'); dot.setProperty('muted', True); top.addWidget(dot); top.addWidget(n)
        v.addLayout(top)
        inner = QWidget(); self.flow = FlowLayout(inner); self.cards = []
        items = sorted(catalogue, key=lambda g: (g not in pants.KNOWN_NAMES, pants.display_name(g).lower()))
        for g in items:
            c = PantsCard(g, pants.display_name(g))
            c.selected = selection == 'all' or g in selection; c.refresh()
            c.changed.connect(self.update_count); self.flow.addWidget(c); self.cards.append(c)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(inner); v.addWidget(sc, 1)
        bot = QHBoxLayout()
        self.count = QLabel(); self.count.setProperty('muted', True); bot.addWidget(self.count, 1)
        cancel = QPushButton('Cancel'); cancel.clicked.connect(self.reject)
        self.finish = QPushButton('Finish'); self.finish.setObjectName('primary'); self.finish.clicked.connect(self.accept)
        bot.addWidget(cancel); bot.addWidget(self.finish); v.addLayout(bot)
        self.update_count()
        # previews are rendered by the background PrepWorker started at launch; show them as they arrive
        self.prep = prep
        self.gen = QLabel(''); self.gen.setProperty('muted', True); top.insertWidget(1, self.gen); self.gen.hide()
        if prep is not None and prep.isRunning() and prep.thumbs_left:
            self.gen.setText('Generating previews…'); self.gen.show()
            prep.thumb_ready.connect(self.thumb_ready)
    def thumb_ready(self, group, n, total):
        for c in self.cards:
            if c.group == group: c.set_thumb()
        self.gen.setText('Generating previews… %d/%d' % (n, total)); self.gen.setVisible(n < total)
    def done(self, r):
        if self.prep is not None:
            try: self.prep.thumb_ready.disconnect(self.thumb_ready)
            except Exception: pass
        super().done(r)
    def filter(self, text):
        t = text.lower().strip()
        for c in self.cards: c.setVisible(not t or t in pants.display_name(c.group).lower() or t in c.group.lower())
        self.flow.invalidate()
    def set_all(self, on):
        for c in self.cards:
            if c.isVisible(): c.selected = on; c.refresh()
        self.update_count()
    def update_count(self):
        n = sum(c.selected for c in self.cards)
        self.count.setText('%d of %d selected' % (n, len(self.cards)))
        self.finish.setEnabled(n > 0); self.finish.setToolTip('' if n else 'Select at least one')
    def selection(self):
        sel = [c.group for c in self.cards if c.selected]
        return 'all' if len(sel) == len(self.cards) else sel

# ------------------------------------------------------------------ settings
class SettingsDialog(QDialog):
    def __init__(self, win):
        super().__init__(win); self.win = win; self.setWindowTitle('Settings'); self.setFixedSize(440, 420)
        v = QVBoxLayout(self); v.setContentsMargins(20, 18, 20, 18); v.setSpacing(8)
        v.addWidget(self._h('Game folder'))
        row = QHBoxLayout()
        self.path = QLineEdit(win.cfg.get('game_dir', '')); self.path.setReadOnly(True)
        ch = QPushButton('Change'); ch.clicked.connect(self.change_dir)
        row.addWidget(self.path, 1); row.addWidget(ch); v.addLayout(row)
        self.err = QLabel(''); self.err.setStyleSheet(f'color: {ERR}; font-size: 9pt;'); v.addWidget(self.err)
        v.addSpacing(6); v.addWidget(self._h('Hide weapons affects'))
        self.grp = QButtonGroup(self)
        for mode, label in (('primary', 'Primary weapons only'), ('pistol', 'Pistol only'), ('both', 'Both')):
            r = QRadioButton(label); r.setChecked(win.cfg.get('weapons_mode', 'both') == mode)
            r.toggled.connect(lambda on, m=mode: on and self.set_mode(m)); self.grp.addButton(r); v.addWidget(r)
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet(f'background: {BORDER};'); v.addSpacing(8); v.addWidget(line)
        more = QLabel('More options will appear here.'); more.setProperty('muted', True); v.addWidget(more)
        v.addStretch(1)
        b = QHBoxLayout(); b.addStretch(1); c = QPushButton('Close'); c.clicked.connect(self.accept); b.addWidget(c)
        v.addLayout(b)
    def _h(self, t):
        l = QLabel(t); l.setFont(tfont(11)); l.setStyleSheet(f'color: {MUTED};'); return l
    def set_mode(self, m):
        self.win.cfg['weapons_mode'] = m; save_config(self.win.cfg); self.win.refresh()
    def change_dir(self):
        if any(self.win.status.values()):
            self.err.setText('Turn every toggle OFF before switching to another game folder.'); return
        d = QFileDialog.getExistingDirectory(self, 'Select the folder that contains GRW.exe')
        if not d: return
        if not F.is_game_dir(d): self.err.setText("GRW.exe isn't in this folder."); return
        self.err.setText(''); self.path.setText(os.path.normpath(d)); self.win.open_game(os.path.normpath(d))

# ------------------------------------------------------------------ main window
class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP); self.setFixedSize(440, 560); self.setWindowIcon(QIcon(res('icon.ico')))
        self.cfg = load_config(); self.worker = None; self.prep = None; self.cache_ok = False; self.status = {}; self.game_on = False; self.errors = {}
        self.stack = QStackedWidget(); self.setCentralWidget(self.stack)
        self.stack.addWidget(self._searching_page()); self.stack.addWidget(self._notfound_page())
        self.stack.addWidget(self._main_page())
        self.lock = LockOverlay(self); self.toast = Toast(self); self.coach = None
        self.watch = QTimer(self); self.watch.timeout.connect(self.check_game); self.watch.start(1500)
        QTimer.singleShot(0, self.startup)

    # pages ---------------------------------------------------------
    def _searching_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setAlignment(Qt.AlignCenter); v.setSpacing(14)
        sp = Spinner(36); h = QHBoxLayout(); h.addStretch(); h.addWidget(sp); h.addStretch(); v.addLayout(h)
        l = QLabel('Looking for Ghost Recon Wildlands…'); l.setAlignment(Qt.AlignCenter); v.addWidget(l)
        return w

    def _notfound_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setAlignment(Qt.AlignCenter); v.setSpacing(10)
        ic = QLabel(); ic.setPixmap(glyph_pixmap('warn', 40, ACC)); ic.setAlignment(Qt.AlignCenter); v.addWidget(ic)
        t = QLabel('No copy of Ghost Recon Wildlands\nwas found.'); t.setAlignment(Qt.AlignCenter)
        t.setFont(tfont(14)); v.addWidget(t)
        s = QLabel('Select the folder that contains GRW.exe.'); s.setProperty('muted', True); s.setAlignment(Qt.AlignCenter)
        v.addWidget(s); v.addSpacing(8)
        b = QPushButton('Browse…'); b.setObjectName('primary'); b.setFixedWidth(160); b.clicked.connect(self.browse)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(b); h.addStretch(); v.addLayout(h)
        self.nf_err = QLabel(''); self.nf_err.setStyleSheet(f'color: {ERR};'); self.nf_err.setAlignment(Qt.AlignCenter)
        v.addWidget(self.nf_err)
        link = QLabel('Where is it usually?'); link.setAlignment(Qt.AlignCenter)
        link.setStyleSheet(f'color: {ACC}; text-decoration: underline;'); link.setCursor(Qt.WhatsThisCursor)
        link.setToolTip('Steam: …\\steamapps\\common\\Wildlands\n'
                        "Ubisoft: …\\Ubisoft Game Launcher\\games\\Tom Clancy's Ghost Recon Wildlands\n"
                        'Epic: …\\Epic Games\\GhostReconWildlands')
        v.addWidget(link)
        return w

    def _main_page(self):
        w = QWidget(); outer = QVBoxLayout(w); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        head = QWidget(); head.setFixedHeight(64); hl = QHBoxLayout(head); hl.setContentsMargins(20, 10, 12, 4)
        tv = QVBoxLayout(); tv.setSpacing(0)
        t = QLabel('GRWRP'); f = tfont(18); f.setLetterSpacing(QFont.AbsoluteSpacing, 1); t.setFont(f)
        s = QLabel('Ghost Recon Wildlands · RolePlay'); s.setProperty('muted', True)
        tv.addWidget(t); tv.addWidget(s); hl.addLayout(tv); hl.addStretch(1)
        cog = QToolButton(); cog.setIcon(QIcon(glyph_pixmap('cog', 20, MUTED))); cog.setIconSize(QSize(20, 20))
        cog.setFixedSize(34, 34); cog.setToolTip('Settings'); cog.setCursor(Qt.PointingHandCursor)
        cog.clicked.connect(self.open_settings); hl.addWidget(cog, 0, Qt.AlignTop)
        outer.addWidget(head)
        body = QWidget(); bv = QVBoxLayout(body); bv.setContentsMargins(16, 8, 16, 12); bv.setSpacing(8)
        self.cards = {
            'weapons': Card('Hide weapons', "Your guns won't show on your character.", self.weapons_info),
            'backpack': Card('Hide backpack', 'Removes the backpack from your character.',
                             lambda: 'Hidden: Hydra (CamelBak) backpack. Inventory is unaffected.'),
            'earpiece': Card('Hide earpiece', 'Removes the radio earpiece / headset.'),
            'holster': Card('Hide pants holster', 'Removes leg holsters from selected pants.', picker=self.open_picker),
        }
        for prof, c in self.cards.items():
            c.switch.toggled.connect(lambda p=prof: self.clicked(p)); bv.addWidget(c)
        bv.addStretch(1); outer.addWidget(body, 1)
        self.banner = QFrame(); self.banner.setObjectName('banner'); bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(16, 10, 16, 10)
        bi = QLabel(); bi.setPixmap(glyph_pixmap('info', 16, INFO))
        self.banner_lbl = QLabel('Changes apply the next time you start the game.'); self.banner_lbl.setProperty('muted', True)
        bl.addWidget(bi); bl.addWidget(self.banner_lbl, 1); outer.addWidget(self.banner)
        self.content = w
        return w

    # startup / game folder --------------------------------------------
    def startup(self):
        d = self.cfg.get('game_dir')
        if F.is_game_dir(d): self.open_game(d); return
        self.stack.setCurrentIndex(0)
        QTimer.singleShot(350, self.search)

    def search(self):
        d, src = F.find_game()
        if d: self.open_game(d); self.toast.show_msg('Found game in %s' % src)
        else: self.stack.setCurrentIndex(1)

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, 'Select the folder that contains GRW.exe')
        if not d: return
        if not F.is_game_dir(d): self.nf_err.setText("GRW.exe isn't in this folder."); return
        self.nf_err.setText(''); self.open_game(os.path.normpath(d))

    def open_game(self, d):
        self.cfg['game_dir'] = d; save_config(self.cfg); os.chdir(d)
        try: G.migrate_legacy()
        except Exception as e: QMessageBox.warning(self, APP, 'Could not migrate the old mod version:\n%s' % e)
        # a game update / file verification replaces archives: forget undo data that no longer applies
        try: reset = G.prune_stale()
        except Exception: reset = set()
        st = G.status()
        for p in G.PROFILES:
            if not st[p]: self.cfg.pop(p + '_applied', None)
        if reset:
            QTimer.singleShot(600, lambda: self.toast.show_msg(
                'The game was updated or verified, so your switches were reset. Turn them on again.', 6000))
        # adopt what is already applied on disk (older versions of this tool)
        if st['holster'] and 'holster_applied' not in self.cfg: self.cfg['holster_applied'] = self.cfg.setdefault('holster_pants', 'all')
        if st['weapons'] and 'weapons_applied' not in self.cfg: self.cfg['weapons_applied'] = self.cfg.setdefault('weapons_mode', 'both')
        save_config(self.cfg)
        self.stack.setCurrentIndex(2); self.refresh(animate=False); self.check_game()
        if not self.cfg.get('coach_seen'): QTimer.singleShot(400, self.show_coach)
        self.start_prep()

    def start_prep(self):
        if self.prep is not None:
            self.prep.stop = True; self.prep.wait(5000)
        self.cache_ok = False
        self.prep = PrepWorker()
        self.prep.status.connect(self.prep_status); self.prep.cache_ready.connect(self.prep_cache_ready)
        self.prep.start()

    def prep_status(self, text):
        h = self.cards['holster']
        if text:
            h.switch.setEnabled(False); h.picker_btn.setEnabled(False)
            h.set_subtitle('<span style="color:%s">%s</span>' % (INFO, text))
    def prep_cache_ready(self):
        self.cache_ok = True
        h = self.cards['holster']; h.switch.setEnabled(True); h.picker_btn.setEnabled(True); self.refresh()

    def show_coach(self):
        c = self.cards['weapons']
        self.coach = CoachMark(self, 'Flip a switch, then start the game.', self._coach_done)
        pos = c.switch.mapTo(self, QPoint(0, 0))
        self.coach.move(pos.x() + 44 - self.coach.width(), pos.y() + 30); self.coach.show(); self.coach.raise_()
    def _coach_done(self): self.cfg['coach_seen'] = True; save_config(self.cfg)

    # state -------------------------------------------------------------
    def holster_selection(self): return self.cfg.get('holster_pants', pants.DEFAULT_SELECTION)

    def weapons_info(self):
        m = self.cfg.get('weapons_mode', 'both')
        names = [G.WEAPON_NAMES[k] for k in ('primary', 'pistol') if m in (k, 'both')]
        return 'Hidden: %s. Weapons still work in-game.' % ', '.join(names)

    def refresh(self, animate=True):
        if self.stack.currentIndex() != 2: return
        self.status = G.status()
        sel = self.holster_selection()
        self.cards['holster'].title.setText('Hide (%s) pants holster' % ('all' if sel == 'all' else len(sel)))
        for prof, c in self.cards.items():
            c.switch.set_on(self.status[prof], animate)
            if prof in self.errors: continue
            c.set_subtitle()
        if self.status['weapons'] and self.cfg.get('weapons_applied') not in (None, self.cfg.get('weapons_mode', 'both')):
            self.cards['weapons'].set_subtitle(f'<span style="color:{ACC}">Settings changed. Toggle off and on to apply.</span>')

    def check_game(self):
        if self.stack.currentIndex() != 2: return
        running = F.process_running('GRW.exe')
        if running == self.game_on: return
        self.game_on = running
        self.lock.setGeometry(self.rect())
        if running:
            self.lock.set_background(self.centralWidget())
            if self.coach: self.coach.hide()
            QToolTip.hideText(); self.lock.fade(True)
        else:
            self.lock.fade(False)

    # jobs --------------------------------------------------------------
    def clicked(self, prof):
        if self.worker or self.game_on: return
        if self.coach: self.coach.dismiss()
        if prof in self.errors:
            self.errors.pop(prof); self.cards[prof].set_error(False)
        self.start_job('off' if self.status.get(prof) else 'on', prof)

    def start_job(self, op, prof):
        if F.process_running('GRW.exe'): self.check_game(); return
        if prof == 'holster' and not self.cache_ok and op != 'off':
            self.toast.show_msg('Still preparing the pants list… one moment.'); return
        if self.prep is not None: self.prep.paused = True   # don't read the archives while we write them
        c = self.cards[prof]; c.set_running(True, show_progress=op != 'off')
        if op == 'scan': c.prog_lbl.setText('Building pants list (first time only, 10-20 min)…')
        for p, other in self.cards.items():
            if p != prof: other.set_dimmed(True)
        settings = {'weapons_mode': self.cfg.get('weapons_mode', 'both'), 'holster_pants': self.holster_selection()}
        self.worker = Worker(op, prof, settings)
        self.worker.progress.connect(c.set_progress)
        self.worker.done.connect(lambda ok, err: self.job_done(op, prof, settings, ok, err))
        self.worker.start()

    def job_done(self, op, prof, settings, ok, err):
        self.worker = None
        if self.prep is not None: self.prep.paused = False
        for c in self.cards.values(): c.set_running(False); c.set_dimmed(False)
        c = self.cards[prof]
        if ok:
            if op in ('on', 'reapply'):
                if prof == 'weapons': self.cfg['weapons_applied'] = settings['weapons_mode']
                if prof == 'holster': self.cfg['holster_applied'] = settings['holster_pants']
            elif op == 'off':
                self.cfg.pop(prof + '_applied', None)
            save_config(self.cfg); self.refresh()
            if op == 'scan': self.open_picker(); return
            self.toast.show_msg('Done. Start the game to see it.'); self.flash_banner()
        else:
            self.errors[prof] = err; c.set_error(True); self.refresh()
            c.set_subtitle(f'<span style="color:{ERR}">Couldn\'t apply. Click the switch to retry.</span> '
                           f'<a href="#" style="color:{MUTED}">Details</a>')
            try: c.sub.linkActivated.disconnect()
            except Exception: pass
            c.sub.linkActivated.connect(lambda _=None, e=err: self.show_details(e))

    def show_details(self, err):
        box = QMessageBox(self); box.setWindowTitle(APP); box.setIcon(QMessageBox.Warning)
        box.setText('Something went wrong. Your original files are safe.'); box.setDetailedText(err); box.exec()

    def flash_banner(self):
        self.banner_lbl.setStyleSheet(f'color: {ACC}; font-size: 9pt; font-weight: 600;')
        QTimer.singleShot(1800, lambda: self.banner_lbl.setStyleSheet(''))

    # dialogs -----------------------------------------------------------
    def open_picker(self):
        if self.worker or self.game_on: return
        if not self.cache_ok:
            self.toast.show_msg('Still preparing the pants list… one moment.'); return
        cache = self.prep.cache if self.prep is not None and self.prep.cache else G.holster_cache(allow_scan=False)
        dlg = PantsPicker(self, G.pants_catalogue(cache), self.holster_selection(), self.prep)
        if dlg.exec() != QDialog.Accepted: return
        new = dlg.selection(); old = self.holster_selection()
        self.cfg['holster_pants'] = new; save_config(self.cfg); self.refresh()
        if self.status.get('holster') and new != self.cfg.get('holster_applied', old):
            box = QMessageBox(self); box.setWindowTitle(APP); box.setText('Reapply now?')
            box.setInformativeText('Your pants selection changed. Reapply the holster removal so it matches?')
            ap = box.addButton('Apply', QMessageBox.AcceptRole); box.addButton('Later', QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == ap: self.start_job('reapply', 'holster')

    def open_settings(self):
        if self.worker or self.game_on: return
        SettingsDialog(self).exec(); self.refresh()

    # window ------------------------------------------------------------
    def resizeEvent(self, e):
        self.lock.setGeometry(self.rect()); super().resizeEvent(e)

    def closeEvent(self, e):
        if self.worker:
            box = QMessageBox(self); box.setWindowTitle(APP); box.setIcon(QMessageBox.Warning)
            box.setText('A task is still running. Closing now may leave files half-patched.')
            keep = box.addButton('Keep running', QMessageBox.RejectRole)
            box.addButton('Close anyway', QMessageBox.DestructiveRole); box.exec()
            if box.clickedButton() == keep: e.ignore(); return
        if self.prep is not None: self.prep.stop = True; self.prep.wait(3000)
        e.accept()

def selftest(game_dir, out):
    """--selftest <game_dir> <out.png>: render one preview without UI (used to verify packaged builds)."""
    os.chdir(game_dir); import render_thumbs as R
    cat = G.pants_catalogue(G.holster_cache(allow_scan=False))
    ok = R.render_group(R.Forges(), 'Apex_Pants_Holster', cat['Apex_Pants_Holster'], out, res('logos'))
    ok = ok and R.render_group(R.Forges(), 'GIGN_DOC_Holster', cat['GIGN_DOC_Holster'], out + '.logo.png', res('logos'))
    sys.exit(0 if ok else 1)

def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--selftest': selftest(sys.argv[2], sys.argv[3])
    if sys.platform == 'win32':
        try:
            import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('GRWRP.App')  # taskbar icon
        except Exception: pass
    app = QApplication(sys.argv); app.setFont(QFont('Segoe UI', 10)); app.setStyleSheet(QSS); app.setWindowIcon(QIcon(res('icon.ico')))
    w = Main(); w.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

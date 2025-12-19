# desktop_goose.py
# Windows 11, Python 3.10+
# pip install PyQt5 pyautogui

import sys, random, time, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets
import pyautogui

# -----------------------------
# Settings
# -----------------------------
@dataclass
class Settings:
    allow_mouse_nudge: bool = False
    min_event_interval_s: int = 45
    max_event_interval_s: int = 120
    goose_speed_px_s: float = 220.0
    goose_idle_prob: float = 0.12
    sprite_scale: float = 1.0
    sprite_dir: Path = Path("./assets")

SET = Settings()

def screen_geometry():
    desktop = QtWidgets.QApplication.desktop()
    return desktop.screenGeometry()

def clamp(n, lo, hi):
    return max(lo, min(hi, n))

# -----------------------------
# Actions
# -----------------------------
class Actions:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.last_event_ts = time.time()
        self.next_event_delay = random.uniform(settings.min_event_interval_s, settings.max_event_interval_s)
        self.dragging_until = 0

    def maybe_trigger_event(self, goose_pos=None):
        now = time.time()
        if now - self.last_event_ts < self.next_event_delay:
            if now < self.dragging_until and goose_pos is not None:
                self.drag_mouse(goose_pos)
            return None

        self.last_event_ts = now
        self.next_event_delay = random.uniform(SET.min_event_interval_s, SET.max_event_interval_s)

        choice = random.choice(["open_notepad", "open_paint", "mouse_nudge", "chase_mouse", "drag_mouse", "nothing"])
        if choice == "open_notepad":
            self.open_notepad_with_text("Hello from Goose!\nHonk honk 🪿")
            return "Opened Notepad with text"
        elif choice == "open_paint":
            subprocess.Popen(["mspaint.exe"])
            return "Opened Paint"
        elif choice == "mouse_nudge":
            if self.settings.allow_mouse_nudge:
                self.mouse_nudge()
                return "Mouse nudged"
            return "Nudge skipped (disabled)"
        elif choice == "chase_mouse":
            return "Goose chasing mouse"
        elif choice == "drag_mouse":
            self.dragging_until = now + random.uniform(5, 10)
            return "Goose dragging mouse!"
        return "Nothing"

    def open_notepad_with_text(self, text):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(text.encode("utf-8"))
        tmp.close()
        subprocess.Popen(["notepad.exe", tmp.name])

    def mouse_nudge(self):
        dx = random.randint(-15, 15)
        dy = random.randint(-15, 15)
        x, y = pyautogui.position()
        rect = screen_geometry()
        nx = clamp(x + dx, rect.left(), rect.right() - 2)
        ny = clamp(y + dy, rect.top(), rect.bottom() - 2)
        pyautogui.moveTo(nx, ny, duration=0.15)

    def drag_mouse(self, goose_pos):
        gx, gy = goose_pos.x(), goose_pos.y()
        pyautogui.moveTo(gx, gy, duration=0.05)

# -----------------------------
# Goose
# -----------------------------
class Goose:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pos = QtCore.QPoint(100, 100)
        self.vel = QtCore.QPoint(0, 0)
        self.dir = 1
        self.state = "walk"
        self.state_timer = 0.0

    def update(self, dt_s: float, bounds: QtCore.QRect):
        self.state_timer -= dt_s
        if self.state_timer <= 0:
            self._choose_next_state()

        if self.state == "chase_mouse":
            mx, my = pyautogui.position()
            dx, dy = mx - self.pos.x(), my - self.pos.y()
            dist = max(1, (dx**2 + dy**2) ** 0.5)
            speed = self.settings.goose_speed_px_s
            vx, vy = (dx / dist) * speed, (dy / dist) * speed
            self.vel = QtCore.QPointF(vx, vy)
            self.dir = 1 if vx >= 0 else -1
        elif self.state == "walk":
            vx = random.uniform(0.6, 1.0) * self.settings.goose_speed_px_s * (1 if self.dir == 1 else -1)
            vy = random.uniform(-0.25, 0.25) * self.settings.goose_speed_px_s * 0.2
            self.vel = QtCore.QPointF(vx, vy)
            if random.random() < 0.02:
                self.dir *= -1
        else:
            self.vel = QtCore.QPointF(random.uniform(-10, 10), random.uniform(-8, 8))

        self.pos.setX(int(clamp(self.pos.x() + self.vel.x() * dt_s, bounds.left() + 4, bounds.right() - 64)))
        self.pos.setY(int(clamp(self.pos.y() + self.vel.y() * dt_s, bounds.top() + 4, bounds.bottom() - 64)))

        if self.pos.x() < bounds.left() + 20: self.dir = 1
        if self.pos.x() > bounds.right() - 80: self.dir = -1

    def _choose_next_state(self):
        r = random.random()
        if r < 0.1:
            self.state = "chase_mouse"; self.state_timer = random.uniform(3.0, 6.0)
        elif r < self.settings.goose_idle_prob:
            self.state = "idle"; self.state_timer = random.uniform(1.2, 3.0)
        else:
            self.state = "walk"; self.state_timer = random.uniform(1.5, 4.0)

# -----------------------------
# Renderer
# -----------------------------
class GooseWindow(QtWidgets.QWidget):
    def __init__(self, settings: Settings):
        super().__init__(None, QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.settings = settings
        self.goose = Goose(settings)
        self.actions = Actions(settings)
        self.anim_t = 0.0

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        rect = screen_geometry()
        self.setGeometry(rect)
        self.move(rect.left(), rect.top())

        self.tray = self._make_tray()

    def _make_tray(self):
        tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon())
        tray.setToolTip("Desktop Goose Clone")
        menu = QtWidgets.QMenu()

        toggle_nudge = QtWidgets.QAction("Toggle mouse nudge")
        toggle_nudge.triggered.connect(self._toggle_nudge)
        menu.addAction(toggle_nudge)

        exit_action = QtWidgets.QAction("Exit")
        exit_action.triggered.connect(QtWidgets.qApp.quit)
        menu.addAction(exit_action)

        tray.setContextMenu(menu)
        tray.show()
        return tray

    def _toggle_nudge(self):
        self.settings.allow_mouse_nudge = not self.settings.allow_mouse_nudge

    def tick(self):
        dt = 0.016
        rect = screen_geometry()
        self.goose.update(dt, rect)
        self.anim_t += dt
        msg = self.actions.maybe_trigger_event(self.goose.pos)
        if msg:
            self.tray.showMessage("Goose", msg, QtWidgets.QSystemTrayIcon.Information, 1500)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        # Simple goose placeholder
        painter.setBrush(QtGui.QColor(255, 255, 255))
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 2))
        painter.drawEllipse(self.goose.pos, 32, 32)
        painter.end()

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = GooseWindow(SET)
    win.showFullScreen()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
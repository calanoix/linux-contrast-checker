import sys
import os
import subprocess
import tempfile

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QGuiApplication, QPainter, QFont, QCursor

LOUPE_PX = 9
LOUPE_SIZE = 180
CELL = LOUPE_SIZE // LOUPE_PX


def capture_screen() -> QPixmap:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    # Stratégie : On essaie d'abord les outils qui gèrent DBus/Portals (KDE/GNOME)
    # puis les outils directs (Sway/Hyprland), puis le legacy (X11).
    methods = [
        ["spectacle", "-b", "-f", "-n", "-o", tmp_path],
        ["gnome-screenshot", "-f", tmp_path],
        ["grim", tmp_path],
    ]

    for cmd in methods:
        try:
            # check=True permet de sauter directement au 'except' si le code retour est != 0
            subprocess.run(cmd, capture_output=True, check=True)
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                pixmap = QPixmap()
                pixmap.load(tmp_path)
                os.unlink(tmp_path)
                return pixmap
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise RuntimeError("No comptabile screenshot tool found, please install spectacle or grim to continue.")


class PickerOverlay(QWidget):
    # Signal émis avec la couleur choisie — permet de communiquer avec le widget parent
    color_picked = pyqtSignal(QColor)

    def __init__(self, screen_pixmap: QPixmap):
        super().__init__()
        self.screen_pixmap = screen_pixmap
        self.screen_image = screen_pixmap.toImage()
        self.cursor_pos = QPoint(0, 0)

        screen = QGuiApplication.primaryScreen()
        self.dpr = self.screen_image.width() / screen.size().width()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.showFullScreen()

    def _color_at_cursor(self) -> QColor:
        x = int(self.cursor_pos.x() * self.dpr)
        y = int(self.cursor_pos.y() * self.dpr)
        return QColor(self.screen_image.pixel(x, y))

    def _pick(self):
        color = self._color_at_cursor()
        self.color_picked.emit(color)
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        x, y = self.cursor_pos.x(), self.cursor_pos.y()
        half = LOUPE_PX // 2

        lx = x + 20
        ly = y + 20
        if lx + LOUPE_SIZE > self.width():
            lx = x - LOUPE_SIZE - 20
        if ly + LOUPE_SIZE + 30 > self.height():
            ly = y - LOUPE_SIZE - 30

        for row in range(LOUPE_PX):
            for col in range(LOUPE_PX):
                px = max(0, min(x - half + col, self.screen_image.width() - 1))
                py = max(0, min(y - half + row, self.screen_image.height() - 1))
                color = QColor(self.screen_image.pixel(int(px * self.dpr), int(py * self.dpr)))
                painter.fillRect(lx + col * CELL, ly + row * CELL, CELL, CELL, color)

        cx = lx + (LOUPE_PX // 2) * CELL
        cy = ly + (LOUPE_PX // 2) * CELL
        painter.setPen(Qt.GlobalColor.white)
        painter.drawRect(cx, cy, CELL - 1, CELL - 1)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(cx - 1, cy - 1, CELL + 1, CELL + 1)

        center_color = self._color_at_cursor()
        band_y = ly + LOUPE_SIZE + 2
        painter.fillRect(lx, band_y, LOUPE_SIZE, 28, center_color)

        lum = 0.299 * center_color.red() + 0.587 * center_color.green() + 0.114 * center_color.blue()
        painter.setPen(Qt.GlobalColor.black if lum > 128 else Qt.GlobalColor.white)
        painter.setFont(QFont("monospace", 10))
        painter.drawText(lx, band_y, LOUPE_SIZE, 28, Qt.AlignmentFlag.AlignCenter, center_color.name().upper())
        painter.end()

    def mouseMoveEvent(self, event):
        self.cursor_pos = event.pos()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._pick()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = {
                Qt.Key.Key_Left:  (-1,  0),
                Qt.Key.Key_Right: ( 1,  0),
                Qt.Key.Key_Up:    ( 0, -1),
                Qt.Key.Key_Down:  ( 0,  1),
            }[key]
            new_pos = QPoint(self.cursor_pos.x() + delta[0], self.cursor_pos.y() + delta[1])
            self.cursor_pos = new_pos
            QCursor.setPos(self.mapToGlobal(new_pos))
            self.update()


def launch_picker(callback):
    """Lance le picker et appelle callback(QColor) quand une couleur est choisie."""
    def start():
        try:
            pixmap = capture_screen()
        except Exception as e:
            print(f"Erreur capture : {e}")
            return

        overlay = launch_picker._overlay = PickerOverlay(pixmap)
        overlay.color_picked.connect(callback)

    QTimer.singleShot(200, start)


# ── Point d'entrée standalone (comportement original) ────────────────────────

def main():
    app = QApplication(sys.argv)

    def on_color(color: QColor):
        QGuiApplication.clipboard().setText(color.name().upper())
        print(f"Couleur copiée : {color.name().upper()}  rgb({color.red()}, {color.green()}, {color.blue()})")
        app.quit()

    launch_picker(on_color)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

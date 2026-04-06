import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from picker import launch_picker


def relative_luminance(color: QColor) -> float:
    def channel(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r = channel(color.red())
    g = channel(color.green())
    b = channel(color.blue())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(c1: QColor, c2: QColor) -> float:
    l1 = relative_luminance(c1)
    l2 = relative_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_level(ratio: float) -> str:
    if ratio >= 7.0:
        return "AAA ✓"
    elif ratio >= 4.5:
        return "AA ✓"
    elif ratio >= 3.0:
        return "AA Large ✓"
    else:
        return "Fail ✗"


class ColorRow(QWidget):
    def __init__(self, label: str):
        super().__init__()
        self.color = QColor("#000000")
        self._last_valid_hex = "#000000"

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(75)

        self.swatch = QLabel()
        self.swatch.setFixedSize(28, 28)
        self._update_swatch()

        self.field = QLineEdit("#000000")
        self.field.setMinimumWidth(60)
        self.field.textEdited.connect(self._on_text_edited)
        self.field.editingFinished.connect(self._on_editing_finished)
        self.field.mousePressEvent = self._on_mouse_press

        self.btn = QPushButton("🖍")
        self.btn.setFixedSize(32, 32)
        self.btn.setToolTip("Pick color")
        self.btn.setAccessibleName(f"Pick {label} color")

        row.addWidget(lbl)
        row.addWidget(self.swatch)
        row.addWidget(self.field)
        row.addWidget(self.btn)

    def _parse_color(self, text: str) -> QColor | None:
        """Accepte #rrggbb, rrggbb, ou rgb(r, g, b)."""
        t = text.strip()
    
        # Format rgb(r, g, b)
        if t.lower().startswith("rgb"):
            import re
            m = re.search(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", t, re.IGNORECASE)
            if m:
                r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if all(0 <= v <= 255 for v in (r, g, b)):
                    return QColor(r, g, b)
            return None
    
        # Format hex
        if not t.startswith("#"):
            t = "#" + t
        color = QColor(t)
        return color if color.isValid() else None

    def _on_text_edited(self, text: str):
        """Validation en temps réel — met à jour swatch si valide."""
        color = self._parse_color(text)
        if color:
            self.color = color
            self._last_valid_hex = color.name().upper()
            self._update_swatch()
            # Notifie le parent pour recalculer le contraste
            self._notify_parent()

    def _on_editing_finished(self):
        """Quand Enter ou perte de focus — normalise ou restaure."""
        color = self._parse_color(self.field.text())
        if color:
            self._last_valid_hex = color.name().upper()
            self.field.setText(self._last_valid_hex)
        else:
            self.field.setText(self._last_valid_hex)

    def _on_mouse_press(self, event):
        QLineEdit.mousePressEvent(self.field, event)
        self.field.selectAll()

    def _notify_parent(self):
        """Remonte au ColorWidget parent pour recalculer."""
        parent = self.parent()
        if parent and hasattr(parent, "_update_contrast"):
            parent._update_contrast()

    def set_color(self, color: QColor):
        self.color = color
        self._last_valid_hex = color.name().upper()
        self.field.setText(self._last_valid_hex)
        self._update_swatch()

    def _update_swatch(self):
        self.swatch.setStyleSheet(
            f"border: 1px solid #888; border-radius: 4px;"
            f"background: {self.color.name()};"
        )


class ColorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux Contrast Checker")
        self.setMinimumWidth(200)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Foreground / Background ───────────────────────────────────────────
        self.fg = ColorRow("Foreground")
        self.bg = ColorRow("Background")
        self.fg.color = QColor("#000000")
        self.bg.color = QColor("#ffffff")
        self.bg.field.setText("#FFFFFF")
        self.bg._update_swatch()

        self.fg.btn.clicked.connect(lambda: self._open_picker(self.fg))
        self.bg.btn.clicked.connect(lambda: self._open_picker(self.bg))

        root.addWidget(self.fg)
        

        # ── Swap ─────────────────────────────────────────────────────────────
        swap_row = QHBoxLayout()
        self.swap_btn = QPushButton("⇅ Swap")
        self.swap_btn.setFixedWidth(60)
        self.swap_btn.clicked.connect(self._swap)
        self.swap_btn.setAccessibleName("Swap foreground and background colors")
        swap_row.addWidget(self.swap_btn)
        swap_row.addStretch()
        root.addLayout(swap_row)
        root.addWidget(self.bg)

        # ── Séparateur ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #888;")
        root.addWidget(sep)

        # ── Résultat ──────────────────────────────────────────────────────────
        # ── Résultat ──────────────────────────────────────────────────────────
        preview_row = QHBoxLayout()
        self.preview = QLabel("Aa")
        self.preview.setFixedSize(48, 48)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.ratio_label = QLabel("—")
        self.ratio_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        preview_row.addWidget(self.preview)
        preview_row.addSpacing(8)
        preview_row.addWidget(self.ratio_label)
        preview_row.addStretch()
        root.addLayout(preview_row)

        self.criteria_labels = {}

        crit_143_row = QHBoxLayout()
        self.crit_143 = QLabel("1.4.3 Contrast (Minimum) - AA")
        self.crit_143.setStyleSheet("font-size: 14px; font-weight: bold;")
        crit_143_row.addWidget(self.crit_143)
        crit_143_row.addStretch()
        root.addLayout(crit_143_row)

        criteria_layout = QVBoxLayout()
        criteria_layout.setSpacing(3)
        row1 = QHBoxLayout()
        badge1 = QLabel()
        badge1.setFixedWidth(60)
        badge1.setStyleSheet("font-size: 12px; font-weight: bold;")
        desc1 = QLabel("Regular text")
        desc1.setStyleSheet("font-size: 12px;")
        row1.addWidget(badge1)
        row1.addWidget(desc1)
        row1.addStretch()
        criteria_layout.addLayout(row1)
        self.criteria_labels["aa_normal"] = badge1
        row2 = QHBoxLayout()
        badge2 = QLabel()
        badge2.setFixedWidth(60)
        badge2.setStyleSheet("font-size: 12px; font-weight: bold;")
        desc2 = QLabel("Large text")
        desc2.setStyleSheet("font-size: 12px;")
        row2.addWidget(badge2)
        row2.addWidget(desc2)
        row2.addStretch()
        criteria_layout.addLayout(row2)
        self.criteria_labels["aa_large"] = badge2
        root.addLayout(criteria_layout)

        crit_146_row = QHBoxLayout()
        self.crit_146 = QLabel("1.4.6 Contrast (Enhanced) - AAA")
        self.crit_146.setStyleSheet("font-size: 14px; font-weight: bold;")
        crit_146_row.addWidget(self.crit_146)
        crit_146_row.addStretch()
        root.addLayout(crit_146_row)

        criteria_layout = QVBoxLayout()
        criteria_layout.setSpacing(3)
        row1 = QHBoxLayout()
        badge1 = QLabel()
        badge1.setFixedWidth(60)
        badge1.setStyleSheet("font-size: 12px; font-weight: bold;")
        desc1 = QLabel("Regular text")
        desc1.setStyleSheet("font-size: 12px;")
        row1.addWidget(badge1)
        row1.addWidget(desc1)
        row1.addStretch()
        criteria_layout.addLayout(row1)
        self.criteria_labels["aaa_normal"] = badge1
        row2 = QHBoxLayout()
        badge2 = QLabel()
        badge2.setFixedWidth(60)
        badge2.setStyleSheet("font-size: 12px; font-weight: bold;")
        desc2 = QLabel("Large text")
        desc2.setStyleSheet("font-size: 12px;")
        row2.addWidget(badge2)
        row2.addWidget(desc2)
        row2.addStretch()
        criteria_layout.addLayout(row2)
        self.criteria_labels["aaa_large"] = badge2
        root.addLayout(criteria_layout)

        crit_1411_row = QHBoxLayout()
        self.crit_1411 = QLabel("1.4.11 Non-text Contrast - AA")
        self.crit_1411.setStyleSheet("font-size: 14px; font-weight: bold;")
        crit_1411_row.addWidget(self.crit_1411)
        crit_1411_row.addStretch()
        root.addLayout(crit_1411_row)

        criteria_layout = QVBoxLayout()
        criteria_layout.setSpacing(3)
        row1 = QHBoxLayout()
        badge1 = QLabel()
        badge1.setFixedWidth(60)
        badge1.setStyleSheet("font-size: 12px; font-weight: bold;")
        desc1 = QLabel("UI components")
        desc1.setStyleSheet("font-size: 12px;")
        row1.addWidget(badge1)
        row1.addWidget(desc1)
        row1.addStretch()
        criteria_layout.addLayout(row1)
        self.criteria_labels["ui"] = badge1
        root.addLayout(criteria_layout)

        self._update_contrast()

    def _open_picker(self, target: ColorRow):
        def on_picked(color: QColor):
            target.set_color(color)
            self._update_contrast()
        launch_picker(on_picked)

    def _swap(self):
        fg_color = QColor(self.fg.color)
        self.fg.set_color(self.bg.color)
        self.bg.set_color(fg_color)
        self._update_contrast()

    def _update_contrast(self):
        ratio = contrast_ratio(self.fg.color, self.bg.color)
        self.ratio_label.setText(f"{ratio:.2f}:1")

        thresholds = {
            "aa_normal":  4.5,
            "aaa_normal": 7.0,
            "aa_large":   3.0,
            "aaa_large":  4.5,
            "ui":         3.0,
        }
        for key, threshold in thresholds.items():
            badge = self.criteria_labels[key]
            if ratio >= threshold:
                badge.setText("✓ Pass")
                badge.setStyleSheet("font-size: 12px; font-weight: bold; color: #2d9e2d;")
            else:
                badge.setText("✗ Fail")
                badge.setStyleSheet("font-size: 12px; font-weight: bold; color: #FE411A;")

        self.preview.setStyleSheet(
            f"border: 1px solid #888; border-radius: 4px;"
            f"background: {self.bg.color.name()}; color: {self.fg.color.name()};"
            f"font-weight: bold; font-size: 20px;"
        )


def main():
    app = QApplication(sys.argv)
    w = ColorWidget()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

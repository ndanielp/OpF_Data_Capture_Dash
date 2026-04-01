"""
app.py — Open Finance Brasil — GUI Desktop (PyQt6)
===================================================
Ponto de entrada da aplicação. Aplica tema dark e exibe a janela principal.

Dependências:
  pip install PyQt6 matplotlib pandas
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# Garante que imports relativos dentro de gui/ encontrem o pacote
sys.path.insert(0, str(Path(__file__).parent))

from gui.main_window import MainWindow


def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    BG      = QColor(30,  30,  46)   # Window / Base
    BG2     = QColor(24,  24,  37)   # Input backgrounds
    SURFACE = QColor(49,  50,  68)   # Buttons / panels
    TEXT    = QColor(205, 214, 244)  # Main text
    SUBTEXT = QColor(166, 173, 200)  # Dim text
    ACCENT  = QColor(137, 180, 250)  # Highlight / links
    RED     = QColor(243, 139, 168)  # Bright / error

    p.setColor(QPalette.ColorRole.Window,          BG)
    p.setColor(QPalette.ColorRole.WindowText,      TEXT)
    p.setColor(QPalette.ColorRole.Base,            BG2)
    p.setColor(QPalette.ColorRole.AlternateBase,   BG)
    p.setColor(QPalette.ColorRole.Text,            TEXT)
    p.setColor(QPalette.ColorRole.PlaceholderText, SUBTEXT)
    p.setColor(QPalette.ColorRole.Button,          SURFACE)
    p.setColor(QPalette.ColorRole.ButtonText,      TEXT)
    p.setColor(QPalette.ColorRole.BrightText,      RED)
    p.setColor(QPalette.ColorRole.ToolTipBase,     BG)
    p.setColor(QPalette.ColorRole.ToolTipText,     TEXT)
    p.setColor(QPalette.ColorRole.Link,            ACCENT)
    p.setColor(QPalette.ColorRole.Highlight,       ACCENT)
    p.setColor(QPalette.ColorRole.HighlightedText, BG)

    # Disabled state
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, SUBTEXT)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       SUBTEXT)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, SUBTEXT)

    app.setPalette(p)
    app.setStyleSheet("""
        QGroupBox {
            border: 1px solid #45475a;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 6px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #89b4fa;
        }
        QPushButton {
            border-radius: 4px;
            padding: 4px 12px;
        }
        QPushButton:hover  { background-color: #585b70; }
        QPushButton:pressed { background-color: #45475a; }
        QComboBox, QSpinBox, QDateEdit, QLineEdit {
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 2px 6px;
        }
        QPlainTextEdit { border: 1px solid #313244; border-radius: 4px; }
        QTabBar::tab {
            padding: 6px 18px;
            border-radius: 4px 4px 0 0;
        }
        QTabBar::tab:selected { background: #313244; color: #89b4fa; }
        QTabBar::tab:!selected { background: #1e1e2e; color: #a6adc8; }
        QSplitter::handle { background: #45475a; }
    """)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Open Finance Brasil")
    _apply_dark_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""
tab_dashboard.py — Aba de visualização de dados.

Inicia um servidor Flask em thread daemon e abre o dashboard no browser padrão.
Toda a lógica de visualização está em dashboard_server.py + gui/dashboard.html.
"""

import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

_PORT = 5432
_URL  = f"http://localhost:{_PORT}"

# ── Design tokens ─────────────────────────────────────────────────────────────
_BG_BASE     = "#13151E"
_BG_SURFACE  = "#1B1F2E"
_BG_ELEVATED = "#242838"
_BG_HOVER    = "#2D3247"
_TXT_PRIMARY = "#EEF0F6"
_TXT_SECOND  = "#8B95B0"
_TXT_MUTED   = "#4A5270"
_TXT_ACCENT  = "#4A9EFF"
_BORDER_SUB  = "#252A3A"
_BORDER_DEF  = "#333B54"


class TabDashboard(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path = db_path
        self._server_started = False
        self._setup_ui()
        # Inicia o servidor imediatamente (thread daemon)
        self._ensure_server()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"background:{_BG_BASE};")
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(400)
        card.setStyleSheet(f"""
            QFrame {{
                background:{_BG_SURFACE};
                border:1px solid {_BORDER_SUB};
                border-radius:12px;
            }}
        """)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(32, 28, 32, 28)
        vl.setSpacing(20)

        # Logo + título
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo = QLabel("OF")
        logo.setFixedSize(28, 28)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"""
            background:{_TXT_ACCENT}; color:white;
            font-size:11px; font-weight:700;
            border-radius:6px;
        """)
        title = QLabel("Open Finance Brasil")
        title.setStyleSheet(f"color:{_TXT_PRIMARY};font-size:15px;font-weight:600;"
                            f"background:transparent;")
        logo_row.addWidget(logo)
        logo_row.addWidget(title)
        logo_row.addStretch()
        vl.addLayout(logo_row)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{_BORDER_SUB};border:none;")
        vl.addWidget(sep)

        # Status do servidor
        self._status_lbl = QLabel("Iniciando servidor…")
        self._status_lbl.setStyleSheet(f"color:{_TXT_MUTED};font-size:12px;background:transparent;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(self._status_lbl)

        # URL clicável
        url_lbl = QLabel(f'<a href="{_URL}" style="color:{_TXT_ACCENT};">{_URL}</a>')
        url_lbl.setTextFormat(Qt.TextFormat.RichText)
        url_lbl.setOpenExternalLinks(True)
        url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_lbl.setStyleSheet("background:transparent;font-size:12px;")
        vl.addWidget(url_lbl)

        # Botão principal
        self._btn = QPushButton("  Abrir no Browser  ↗")
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background:{_TXT_ACCENT};
                border:none; color:white;
                font-size:13px; font-weight:600;
                padding:10px 20px; border-radius:8px;
            }}
            QPushButton:hover {{ background:#3A8EEE; }}
            QPushButton:pressed {{ background:#2A7EDE; }}
        """)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._open_browser)
        vl.addWidget(self._btn)

        # Nota
        note = QLabel("Os dados são lidos diretamente do banco SQLite.\n"
                       "Troque o banco pela barra de status.")
        note.setStyleSheet(f"color:{_TXT_MUTED};font-size:11px;background:transparent;")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        vl.addWidget(note)

        root.addWidget(card)

    # ── Servidor ──────────────────────────────────────────────────────────────

    def _ensure_server(self) -> None:
        import dashboard_server
        dashboard_server.start_server(self._db_path, port=_PORT)
        self._server_started = True
        self._status_lbl.setText("Servidor rodando")
        self._status_lbl.setStyleSheet(
            f"color:#2ECC7F;font-size:12px;background:transparent;"
        )

    # ── Slots ─────────────────────────────────────────────────────────────────

    def set_db_path(self, path: Path) -> None:
        self._db_path = path
        import dashboard_server
        dashboard_server.set_db(path)

    def load_data(self) -> None:
        pass  # O browser busca os dados via fetch

    def _open_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(_URL))

"""
main_window.py — Janela principal com duas abas e barra de status.
"""

import sqlite3
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar,
    QLabel, QPushButton, QFileDialog, QHBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

BASE_DIR     = Path(__file__).parent.parent          # openfinance-poc/
DEFAULT_DB   = BASE_DIR / "data" / "consents.db"


def _ensure_db(path: Path) -> None:
    """Cria o arquivo e as tabelas se ainda não existirem."""
    from build_consents_db import open_db
    con = open_db(path)
    con.close()


class MainWindow(QMainWindow):
    # Sinal emitido quando o usuário troca o caminho do banco
    db_path_changed = pyqtSignal(Path)

    def __init__(self) -> None:
        super().__init__()
        _ensure_db(DEFAULT_DB)
        self._db_path = DEFAULT_DB

        self.setWindowTitle("Open Finance Brasil")
        self.setMinimumSize(1280, 780)

        # ── Abas ──────────────────────────────────────────────────────────────
        # Importação local para evitar dependência circular no módulo
        from gui.tab_coleta    import TabColeta
        from gui.tab_dashboard import TabDashboard

        self._tab_coleta    = TabColeta(self._db_path)
        self._tab_dashboard = TabDashboard(self._db_path)

        tabs = QTabWidget()
        tabs.addTab(self._tab_coleta,    "  Coleta  ")
        tabs.addTab(self._tab_dashboard, "  Dashboard  ")
        tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(tabs)

        # ── Barra de status ───────────────────────────────────────────────────
        self._status_db_label = QLabel()
        self._btn_db          = QPushButton("Trocar / Criar banco…")
        self._btn_db.setFixedHeight(22)
        self._btn_db.clicked.connect(self._choose_db)

        status_widget = QWidget()
        hl = QHBoxLayout(status_widget)
        hl.setContentsMargins(4, 0, 4, 0)
        hl.addWidget(self._status_db_label)
        hl.addWidget(self._btn_db)

        bar = QStatusBar()
        bar.addPermanentWidget(status_widget)
        self.setStatusBar(bar)

        # Conecta sinal de coleta concluída → recarrega dashboard
        self._tab_coleta.collection_finished.connect(
            self._tab_dashboard.load_data
        )
        # Propaga mudança de DB
        self.db_path_changed.connect(self._tab_coleta.set_db_path)
        self.db_path_changed.connect(self._tab_dashboard.set_db_path)

        self._refresh_status()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _choose_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Selecionar ou criar banco SQLite",
            str(self._db_path.parent),
            "SQLite (*.db *.sqlite *.sqlite3);;Todos (*)",
        )
        if path:
            new_path = Path(path)
            _ensure_db(new_path)
            self._db_path = new_path
            self.db_path_changed.emit(self._db_path)
            self._refresh_status()

    def _on_tab_changed(self, idx: int) -> None:
        # Recarrega dados do dashboard ao entrar na aba
        if idx == 1:
            self._tab_dashboard.load_data()

    def _refresh_status(self) -> None:
        exists = self._db_path.exists()
        if exists:
            try:
                con  = sqlite3.connect(str(self._db_path))
                n_c  = con.execute("SELECT count(*) FROM unique_consents").fetchone()[0]
                n_a  = con.execute("SELECT count(*) FROM api_requests").fetchone()[0]
                con.close()
                info = f"  Banco: {self._db_path.name}   consentimentos: {n_c:,}   api_requests: {n_a:,}"
            except Exception:
                info = f"  Banco: {self._db_path.name}  (tabelas ainda não criadas)"
        else:
            info = f"  Banco: {self._db_path.name}  (vazio, pronto para coleta)"
        self._status_db_label.setText(info)

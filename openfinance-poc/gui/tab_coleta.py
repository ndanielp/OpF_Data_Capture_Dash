"""
tab_coleta.py — Aba de configuração e disparo da coleta de dados.

Usa CollectionThread (QThread) para executar a coleta em background e
atualiza WorkerCards em tempo real via sinais Qt.
"""

import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QFrame, QProgressBar, QDateEdit,
    QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QFont

from gui.collection_thread import CollectionThread
from gui.worker_card import WorkerGrid

BASE_DIR = Path(__file__).parent.parent  # openfinance-poc/

# Cores
C_BLUE    = "#89b4fa"
C_GREEN   = "#a6e3a1"
C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"
C_SURFACE = "#313244"
C_OVERLAY = "#45475a"
C_TEXT    = "#cdd6f4"
C_SUBTEXT = "#a6adc8"


class _SummaryBar(QFrame):
    """Barra de resumo: fase + progresso global + tempo + contagem."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            _SummaryBar {{
                background: {C_SURFACE};
                border: 1px solid {C_OVERLAY};
                border-radius: 8px;
            }}
        """)
        self.setFixedHeight(70)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 8)
        root.setSpacing(4)

        # Linha superior: fase + tempo + contagem
        top = QHBoxLayout()
        self._phase_lbl = QLabel("Aguardando início…")
        self._phase_lbl.setStyleSheet(
            f"color: {C_BLUE}; font-weight: bold; font-size: 10pt;"
        )
        self._time_lbl = QLabel("")
        self._time_lbl.setStyleSheet(f"color: {C_SUBTEXT}; font-size: 9pt;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {C_TEXT}; font-size: 9pt;")
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        top.addWidget(self._phase_lbl)
        top.addStretch()
        top.addWidget(self._time_lbl)
        top.addSpacing(16)
        top.addWidget(self._count_lbl)
        root.addLayout(top)

        # Barra global
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 4px;
                background: {C_OVERLAY};
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_BLUE}, stop:1 {C_GREEN});
            }}
        """)
        root.addWidget(self._bar)

    def update(self, phase: str, states: dict, elapsed: float) -> None:
        # Fase
        phase_label = {
            "consents": "Etapa 1 — Consentimentos Únicos",
            "api":      "Etapa 2 — Chamadas de API",
        }.get(phase, phase)
        self._phase_lbl.setText(phase_label)

        # Tempo
        mins, secs = divmod(int(elapsed), 60)
        self._time_lbl.setText(f"⏱ {mins:02d}:{secs:02d}")

        # Progresso
        total = sum(s["rec_total"] for s in states.values())
        done  = sum(s["recs_done"] for s in states.values())
        if total > 0:
            pct = int(done * 100 / total)
            self._bar.setValue(pct)
            self._count_lbl.setText(f"{done} / {total} receptores")
        else:
            self._bar.setValue(0)
            self._count_lbl.setText("")

    def set_message(self, msg: str, color: str = C_BLUE) -> None:
        self._phase_lbl.setText(msg)
        self._phase_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 10pt;"
        )

    def set_done(self, n_consents: int, n_api: int) -> None:
        self._phase_lbl.setText("✓  Coleta concluída")
        self._phase_lbl.setStyleSheet(
            f"color: {C_GREEN}; font-weight: bold; font-size: 10pt;"
        )
        self._bar.setValue(100)
        self._bar.setStyleSheet(self._bar.styleSheet().replace(C_BLUE, C_GREEN))
        parts = []
        if n_consents:
            parts.append(f"{n_consents:,} consentimentos")
        if n_api:
            parts.append(f"{n_api:,} api_requests")
        self._count_lbl.setText("  ·  ".join(parts) + " salvos")

    def reset(self) -> None:
        self._phase_lbl.setText("Aguardando início…")
        self._phase_lbl.setStyleSheet(
            f"color: {C_BLUE}; font-weight: bold; font-size: 10pt;"
        )
        self._time_lbl.setText("")
        self._count_lbl.setText("")
        self._bar.setValue(0)


class TabColeta(QWidget):
    collection_finished = pyqtSignal()

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path = db_path
        self._thread: CollectionThread | None = None
        self._setup_ui()

    # ── Configuração da UI ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        root.addWidget(self._build_config_group())
        root.addLayout(self._build_buttons())

        # Barra de resumo
        self._summary = _SummaryBar()
        root.addWidget(self._summary)

        # Scroll area com worker cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        grid_layout = QVBoxLayout(self._grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        self._worker_grid = WorkerGrid()
        grid_layout.addWidget(self._worker_grid)
        grid_layout.addStretch()

        scroll.setWidget(self._grid_container)
        root.addWidget(scroll, stretch=1)

    def _build_config_group(self) -> QGroupBox:
        grp = QGroupBox("Configuração")
        hl  = QHBoxLayout(grp)
        hl.setSpacing(16)

        # Período
        hl.addWidget(QLabel("Período:"))
        self._period_combo = QComboBox()
        self._period_combo.addItems([
            "Último mês", "Últimos 3 meses", "Últimos 6 meses", "Personalizado…",
        ])
        self._period_combo.setCurrentIndex(1)
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        self._period_combo.setFixedWidth(170)
        hl.addWidget(self._period_combo)

        # Datas customizadas (ocultas por padrão)
        self._start_date = QDateEdit(QDate.currentDate().addMonths(-3))
        self._end_date   = QDateEdit(QDate.currentDate())
        for w in (self._start_date, self._end_date):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
            w.setFixedWidth(110)
        self._lbl_de  = QLabel("De:")
        self._lbl_ate = QLabel("Até:")
        for w in (self._lbl_de, self._start_date, self._lbl_ate, self._end_date):
            hl.addWidget(w)
            w.setVisible(False)

        hl.addSpacing(8)

        # Workers
        hl.addWidget(QLabel("Workers:"))
        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 10)
        self._workers_spin.setValue(3)
        self._workers_spin.setFixedWidth(60)
        hl.addWidget(self._workers_spin)

        hl.addSpacing(8)

        # Etapas
        self._chk_consents = QCheckBox("Consentimentos")
        self._chk_consents.setChecked(True)
        self._chk_api      = QCheckBox("Chamadas de API")
        self._chk_api.setChecked(True)
        hl.addWidget(self._chk_consents)
        hl.addWidget(self._chk_api)

        hl.addStretch()
        return grp

    def _build_buttons(self) -> QHBoxLayout:
        hl = QHBoxLayout()

        self._btn_start = QPushButton("▶   Iniciar Coleta")
        self._btn_start.setMinimumHeight(38)
        self._btn_start.setStyleSheet(
            f"QPushButton {{ background: {C_BLUE}; color: #1e1e2e;"
            " font-weight: bold; border-radius: 6px; padding: 0 20px; }"
            f"QPushButton:hover {{ background: #b6d0ff; }}"
            f"QPushButton:disabled {{ background: {C_OVERLAY}; color: {C_SUBTEXT}; }}"
        )
        self._btn_start.clicked.connect(self._start)

        self._btn_stop = QPushButton("■   Parar")
        self._btn_stop.setMinimumHeight(38)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            f"QPushButton {{ background: {C_RED}; color: #1e1e2e;"
            " font-weight: bold; border-radius: 6px; padding: 0 20px; }"
            f"QPushButton:hover {{ background: #ff9fab; }}"
            f"QPushButton:disabled {{ background: {C_OVERLAY}; color: {C_SUBTEXT}; }}"
        )
        self._btn_stop.clicked.connect(self._stop)

        hl.addWidget(self._btn_start, stretch=3)
        hl.addWidget(self._btn_stop, stretch=1)
        return hl

    # ── Slots ─────────────────────────────────────────────────────────────────

    def set_db_path(self, path: Path) -> None:
        self._db_path = path

    def _on_period_changed(self, idx: int) -> None:
        visible = idx == 3
        for w in (self._lbl_de, self._start_date, self._lbl_ate, self._end_date):
            w.setVisible(visible)

    def _build_dates(self) -> list[str]:
        from utils import resolve_date_range
        idx = self._period_combo.currentIndex()
        month_map = {0: 1, 1: 3, 2: 6}
        if idx in month_map:
            return resolve_date_range(months=month_map[idx], start=None, end=None)
        return resolve_date_range(
            months=None,
            start=self._start_date.date().toString("yyyy-MM-dd"),
            end=self._end_date.date().toString("yyyy-MM-dd"),
        )

    def _start(self) -> None:
        dates = self._build_dates()
        if not dates:
            self._summary.set_message("Nenhuma sexta-feira no período.", C_RED)
            return

        workers       = self._workers_spin.value()
        skip_consents = not self._chk_consents.isChecked()
        skip_api      = not self._chk_api.isChecked()

        # Determina modo inicial para os cards
        first_mode = "api" if skip_consents else "consents"
        self._worker_grid.setup(workers, first_mode)
        self._summary.reset()
        self._summary.set_message("Iniciando workers…")

        self._thread = CollectionThread(
            dates, self._db_path, workers, skip_consents, skip_api, parent=self
        )
        self._thread.state_updated.connect(self._on_state_updated)
        self._thread.phase_complete.connect(self._on_phase_complete)
        self._thread.all_complete.connect(self._on_all_complete)
        self._thread.error_occurred.connect(self._on_error)
        self._thread.status_message.connect(
            lambda msg: self._summary.set_message(msg)
        )
        self._thread.start()

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)

    def _stop(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(3000)
            self._summary.set_message("Coleta interrompida.", C_YELLOW)
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _on_state_updated(self, phase: str, states: dict, elapsed: float) -> None:
        # Reconfigura cards se a fase mudou
        if phase == "api":
            for card in self._worker_grid._cards.values():
                card.set_mode("api")
        self._summary.update(phase, states, elapsed)
        self._worker_grid.update_states(states)

    def _on_phase_complete(self, phase: str, n: int) -> None:
        label = "Consentimentos" if phase == "consents" else "API requests"
        self._summary.set_message(
            f"✓ {label} concluídos — {n:,} registros salvos", C_GREEN
        )

    def _on_all_complete(self, n_consents: int, n_api: int) -> None:
        self._summary.set_done(n_consents, n_api)
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self.collection_finished.emit()

    def _on_error(self, msg: str) -> None:
        self._summary.set_message(f"Erro: {msg}", C_RED)
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

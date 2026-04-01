"""
tab_coleta.py — Aba de configuração e disparo da coleta de dados.

Lança update_db.py como subprocess via QProcess e exibe o output
em tempo real (ANSI strippado) num log scrollável.
"""

import re
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QPlainTextEdit, QDateEdit, QSizePolicy,
)
from PyQt6.QtCore import QProcess, QDate, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

BASE_DIR   = Path(__file__).parent.parent   # openfinance-poc/
SCRIPT     = BASE_DIR / "update_db.py"

_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class TabColeta(QWidget):
    # Emitido quando o processo termina com código 0
    collection_finished = pyqtSignal()

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path = db_path
        self._process: QProcess | None = None
        self._setup_ui()

    # ── Configuração da UI ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        root.addWidget(self._build_config_group())
        root.addLayout(self._build_buttons())
        root.addWidget(self._build_log_group(), stretch=1)

    def _build_config_group(self) -> QGroupBox:
        grp = QGroupBox("Configuração da Coleta")
        form = QFormLayout(grp)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setVerticalSpacing(10)

        # Período
        self._period_combo = QComboBox()
        self._period_combo.addItems([
            "Último mês",
            "Últimos 3 meses",
            "Últimos 6 meses",
            "Personalizado…",
        ])
        self._period_combo.setCurrentIndex(1)
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        form.addRow("Período:", self._period_combo)

        # Datas customizadas (ocultas por padrão)
        self._date_widget = QWidget()
        dl = QHBoxLayout(self._date_widget)
        dl.setContentsMargins(0, 0, 0, 0)
        self._start_date = QDateEdit(QDate.currentDate().addMonths(-3))
        self._end_date   = QDateEdit(QDate.currentDate())
        for w in (self._start_date, self._end_date):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
        dl.addWidget(QLabel("De:"))
        dl.addWidget(self._start_date)
        dl.addWidget(QLabel("  Até:"))
        dl.addWidget(self._end_date)
        dl.addStretch()
        self._date_widget.setVisible(False)
        form.addRow("", self._date_widget)

        # Workers
        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 10)
        self._workers_spin.setValue(5)
        self._workers_spin.setSuffix("  workers")
        self._workers_spin.setFixedWidth(140)
        form.addRow("Paralelismo:", self._workers_spin)

        # Etapas
        self._chk_consents = QCheckBox("Consentimentos")
        self._chk_consents.setChecked(True)
        self._chk_api      = QCheckBox("Chamadas de API")
        self._chk_api.setChecked(True)
        steps = QWidget()
        sl = QHBoxLayout(steps)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self._chk_consents)
        sl.addWidget(self._chk_api)
        sl.addStretch()
        form.addRow("Etapas:", steps)

        return grp

    def _build_buttons(self) -> QHBoxLayout:
        hl = QHBoxLayout()

        self._btn_start = QPushButton("▶   Iniciar Coleta")
        self._btn_start.setMinimumHeight(38)
        self._btn_start.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_start.clicked.connect(self._start)

        self._btn_stop = QPushButton("■   Parar")
        self._btn_stop.setMinimumHeight(38)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop)

        self._btn_clear = QPushButton("Limpar log")
        self._btn_clear.setMinimumHeight(38)
        self._btn_clear.clicked.connect(self._clear_log)

        hl.addWidget(self._btn_start, stretch=3)
        hl.addWidget(self._btn_stop,  stretch=1)
        hl.addWidget(self._btn_clear, stretch=1)
        return hl

    def _build_log_group(self) -> QGroupBox:
        grp = QGroupBox("Log de Execução")
        vl  = QVBoxLayout(grp)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setMaximumBlockCount(5000)
        vl.addWidget(self._log)
        return grp

    # ── Slots ─────────────────────────────────────────────────────────────────

    def set_db_path(self, path: Path) -> None:
        self._db_path = path

    def _on_period_changed(self, idx: int) -> None:
        self._date_widget.setVisible(idx == 3)

    def _build_args(self) -> list[str]:
        idx = self._period_combo.currentIndex()
        period_map = {0: ["--months", "1"],
                      1: ["--months", "3"],
                      2: ["--months", "6"]}
        if idx in period_map:
            args = period_map[idx]
        else:
            args = [
                "--start", self._start_date.date().toString("yyyy-MM-dd"),
                "--end",   self._end_date.date().toString("yyyy-MM-dd"),
            ]

        args += ["--workers", str(self._workers_spin.value()),
                 "--db",      str(self._db_path)]

        if not self._chk_consents.isChecked():
            args.append("--skip-consents")
        if not self._chk_api.isChecked():
            args.append("--skip-api-requests")

        return args

    def _start(self) -> None:
        if not SCRIPT.exists():
            self._append_log(f"[ERRO] Script não encontrado: {SCRIPT}")
            return

        self._log.clear()
        self._append_log(f"$ {sys.executable} {SCRIPT.name} {' '.join(self._build_args())}\n")

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(BASE_DIR))

        # Força UTF-8 e desativa cores Rich para output limpo
        env = self._process.processEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("NO_COLOR", "1")
        self._process.setProcessEnvironment(env)

        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        self._process.start(sys.executable, [str(SCRIPT)] + self._build_args())

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)

    def _stop(self) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._append_log("\n[Processo interrompido pelo usuário]")

    def _clear_log(self) -> None:
        self._log.clear()

    def _on_stdout(self) -> None:
        raw = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._append_log(_strip_ansi(raw))

    def _on_stderr(self) -> None:
        raw = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self._append_log(_strip_ansi(raw))

    def _on_finished(self, exit_code: int, _) -> None:
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        status = "✓ Concluído com sucesso" if exit_code == 0 else f"✗ Encerrado com código {exit_code}"
        self._append_log(f"\n{'─' * 60}\n{status}")
        if exit_code == 0:
            self.collection_finished.emit()

    def _append_log(self, text: str) -> None:
        self._log.moveCursor(QTextCursor.MoveOperation.End)
        self._log.insertPlainText(text)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

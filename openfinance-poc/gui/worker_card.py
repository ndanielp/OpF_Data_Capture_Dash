"""
worker_card.py — Cards visuais de progresso por worker.

WorkerCard  : card individual (badge + receptor + barra + resultados)
WorkerGrid  : grid responsivo de WorkerCards (máx 3 colunas)
"""

from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QProgressBar, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Cores do tema (Catppuccin Mocha)
C_BLUE    = "#89b4fa"
C_GREEN   = "#a6e3a1"
C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"
C_SURFACE = "#313244"
C_OVERLAY = "#45475a"
C_TEXT    = "#cdd6f4"
C_SUBTEXT = "#a6adc8"
C_BG      = "#1e1e2e"


def _label(text: str, color: str = C_TEXT, bold: bool = False,
           size: int = 9, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(align)
    style = f"color: {color}; font-size: {size}pt;"
    if bold:
        style += " font-weight: bold;"
    lbl.setStyleSheet(style)
    return lbl


class WorkerCard(QFrame):
    """Card visual para um único worker."""

    def __init__(self, worker_id: int, parent=None) -> None:
        super().__init__(parent)
        self._wid  = worker_id
        self._mode = "consents"  # "consents" | "api"
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            WorkerCard {{
                background: {C_SURFACE};
                border: 1px solid {C_OVERLAY};
                border-radius: 8px;
            }}
        """)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(4)

        # ── Header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()

        self._badge = QLabel(f" W{self._wid} ")
        self._badge.setStyleSheet(f"""
            background: {C_OVERLAY}; color: {C_SUBTEXT};
            border-radius: 4px; padding: 1px 5px;
            font-weight: bold; font-size: 8pt;
        """)
        self._badge.setFixedHeight(20)

        self._receptor_lbl = _label("iniciando…", C_SUBTEXT, size=9)
        self._receptor_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._fraction_lbl = _label("", C_SUBTEXT, size=8,
                                    align=Qt.AlignmentFlag.AlignRight)
        self._fraction_lbl.setFixedWidth(60)

        header.addWidget(self._badge)
        header.addSpacing(6)
        header.addWidget(self._receptor_lbl)
        header.addWidget(self._fraction_lbl)
        root.addLayout(header)

        # ── Barra de progresso ────────────────────────────────────────────────
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(10)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 4px;
                background: {C_OVERLAY};
                text-align: center; font-size: 7pt; color: transparent;
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_BLUE}, stop:1 {C_GREEN});
            }}
        """)
        root.addWidget(self._bar)

        # ── Área de resultados ────────────────────────────────────────────────
        self._results_lbl = QLabel("")
        self._results_lbl.setWordWrap(True)
        self._results_lbl.setStyleSheet(f"color: {C_SUBTEXT}; font-size: 8pt;")
        self._results_lbl.setFont(QFont("Consolas", 8))
        root.addWidget(self._results_lbl)

    # ── API pública ───────────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> None:
        """Define o modo: 'consents' ou 'api'."""
        self._mode = mode

    def update_state(self, state: dict) -> None:
        status    = state.get("status", "init")
        receptor  = state.get("receptor", "")
        rec_idx   = state.get("rec_idx", 0)
        rec_total = state.get("rec_total", 0)
        recs_done = state.get("recs_done", 0)

        # Badge color
        if status == "done":
            badge_style = f"background: {C_GREEN}; color: #1e1e2e;"
            self._receptor_lbl.setText("concluído")
            self._receptor_lbl.setStyleSheet(f"color: {C_GREEN}; font-size: 9pt;")
        elif status == "working" and receptor:
            badge_style = f"background: {C_BLUE}; color: #1e1e2e;"
            self._receptor_lbl.setText(receptor[:34])
            self._receptor_lbl.setStyleSheet(f"color: {C_TEXT}; font-size: 9pt;")
        else:
            badge_style = f"background: {C_OVERLAY}; color: {C_SUBTEXT};"
            self._receptor_lbl.setText("iniciando…")
            self._receptor_lbl.setStyleSheet(f"color: {C_SUBTEXT}; font-size: 9pt;")

        self._badge.setStyleSheet(
            badge_style +
            " border-radius: 4px; padding: 1px 5px;"
            " font-weight: bold; font-size: 8pt;"
        )

        # Fração e barra
        if rec_total > 0:
            pct = int(recs_done * 100 / rec_total)
            self._fraction_lbl.setText(f"{recs_done}/{rec_total}")
            self._bar.setValue(pct)
        else:
            self._fraction_lbl.setText("")
            self._bar.setValue(0)

        if status == "done":
            self._bar.setStyleSheet(self._bar.styleSheet().replace(C_BLUE, C_GREEN))

        # Resultados
        if self._mode == "consents":
            results = state.get("results", [])
            parts = []
            for sym in results[-60:]:
                if sym == "✓":
                    parts.append(f'<span style="color:{C_GREEN}">✓</span>')
                else:
                    parts.append(f'<span style="color:{C_OVERLAY}">·</span>')
            self._results_lbl.setText("".join(parts))
        else:
            combos = state.get("combos", {})
            self._results_lbl.setText(self._format_combos(combos))

    def _format_combos(self, combos: dict) -> str:
        from build_api_requests_db import APIS, STATUSES
        parts = []
        for api in APIS:
            statuses_html = []
            for st in STATUSES:
                sym = combos.get((api, st), "")
                if sym == "✓":
                    statuses_html.append(
                        f'<span style="color:{C_GREEN}">✓{st}</span>'
                    )
                elif sym == "·":
                    statuses_html.append(
                        f'<span style="color:{C_OVERLAY}">·{st}</span>'
                    )
                else:
                    statuses_html.append(
                        f'<span style="color:{C_OVERLAY}">○{st}</span>'
                    )
            short = api.split("-")[0][:8]
            parts.append(
                f'<span style="color:{C_SUBTEXT}">{short}</span> '
                + " ".join(statuses_html)
            )
        return "  ".join(parts)

    def reset(self, mode: str) -> None:
        self._mode = mode
        self._badge.setStyleSheet(
            f"background: {C_OVERLAY}; color: {C_SUBTEXT};"
            " border-radius: 4px; padding: 1px 5px;"
            " font-weight: bold; font-size: 8pt;"
        )
        self._receptor_lbl.setText("aguardando…")
        self._receptor_lbl.setStyleSheet(f"color: {C_SUBTEXT}; font-size: 9pt;")
        self._fraction_lbl.setText("")
        self._bar.setValue(0)
        self._results_lbl.setText("")


class WorkerGrid(QWidget):
    """Grid de WorkerCards com até 3 colunas."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cards: dict[int, WorkerCard] = {}
        self._layout = QGridLayout(self)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def setup(self, n_workers: int, mode: str) -> None:
        """Cria/recria os cards para N workers no modo indicado."""
        # Limpa layout anterior
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        self._cards.clear()
        cols = min(n_workers, 3)

        for i in range(n_workers):
            wid  = i + 1
            card = WorkerCard(wid)
            card.reset(mode)
            self._cards[wid] = card
            self._layout.addWidget(card, i // cols, i % cols)

    def update_states(self, states: dict) -> None:
        for wid, state in states.items():
            if wid in self._cards:
                self._cards[wid].update_state(state)

"""
tab_dashboard.py — Aba de visualização de dados.

Gráfico 1: Consentimentos únicos por receptor ao longo do tempo (linhas).
Gráfico 2: Volume de chamadas de API — heatmap receptor × API.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QSplitter, QSizePolicy,
)
from PyQt6.QtCore import Qt

matplotlib.rcParams.update({
    "text.color":       "#cdd6f4",
    "axes.labelcolor":  "#cdd6f4",
    "xtick.color":      "#a6adc8",
    "ytick.color":      "#a6adc8",
    "axes.edgecolor":   "#45475a",
    "grid.color":       "#313244",
    "grid.linewidth":   0.5,
    "figure.facecolor": "#1e1e2e",
    "axes.facecolor":   "#181825",
    "legend.facecolor": "#181825",
    "legend.edgecolor": "#45475a",
    "legend.labelcolor":"#cdd6f4",
    "font.size":        9,
})

BG_FIG  = "#1e1e2e"
BG_AX   = "#181825"


def _fmt_number(x: float, _=None) -> str:
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}k"
    return str(int(x))


class _Canvas(FigureCanvas):
    """FigureCanvas com fundo dark já configurado."""
    def __init__(self, fig: Figure) -> None:
        super().__init__(fig)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class TabDashboard(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path       = db_path
        self._df_consents   = pd.DataFrame()
        self._df_api        = pd.DataFrame()
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        root.addWidget(self._build_filter_bar())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_chart1_group())
        splitter.addWidget(self._build_chart2_group())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, stretch=1)

    def _build_filter_bar(self) -> QGroupBox:
        grp = QGroupBox("Filtros")
        hl  = QHBoxLayout(grp)
        hl.setSpacing(12)

        # Receptor
        hl.addWidget(QLabel("Receptor:"))
        self._receptor_combo = QComboBox()
        self._receptor_combo.setMinimumWidth(220)
        self._receptor_combo.currentIndexChanged.connect(self._draw_charts)
        hl.addWidget(self._receptor_combo)

        # Status (para heatmap)
        hl.addWidget(QLabel("Status (API):"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(["200", "500", "Todos"])
        self._status_combo.currentIndexChanged.connect(self._draw_chart2)
        hl.addWidget(self._status_combo)

        hl.addStretch()

        btn = QPushButton("↺  Recarregar dados")
        btn.clicked.connect(self.load_data)
        hl.addWidget(btn)

        return grp

    def _build_chart1_group(self) -> QGroupBox:
        grp = QGroupBox("Consentimentos Únicos por Receptor")
        vl  = QVBoxLayout(grp)
        self._fig1    = Figure(facecolor=BG_FIG, tight_layout=True)
        self._canvas1 = _Canvas(self._fig1)
        vl.addWidget(self._canvas1)
        return grp

    def _build_chart2_group(self) -> QGroupBox:
        grp = QGroupBox("Volume de Chamadas de API — Receptor × API")
        vl  = QVBoxLayout(grp)
        self._fig2    = Figure(facecolor=BG_FIG, tight_layout=True)
        self._canvas2 = _Canvas(self._fig2)
        vl.addWidget(self._canvas2)
        return grp

    # ── Dados ─────────────────────────────────────────────────────────────────

    def set_db_path(self, path: Path) -> None:
        self._db_path = path
        self.load_data()

    def load_data(self) -> None:
        if not self._db_path.exists():
            self._show_empty_charts("Banco não encontrado.\nExecute a coleta primeiro.")
            return

        try:
            con = sqlite3.connect(str(self._db_path))
            self._df_consents = pd.read_sql(
                "SELECT date, receptor, total FROM unique_consents",
                con, parse_dates=["date"],
            )
            self._df_api = pd.read_sql(
                "SELECT date, receptor, api, status, total FROM api_requests",
                con,
            )
            con.close()
        except Exception as exc:
            self._show_empty_charts(f"Erro ao ler banco:\n{exc}")
            return

        self._populate_receptor_combo()
        self._draw_charts()

    def _populate_receptor_combo(self) -> None:
        self._receptor_combo.blockSignals(True)
        prev = self._receptor_combo.currentText()
        self._receptor_combo.clear()
        self._receptor_combo.addItem("Top 10 receptores")

        if not self._df_consents.empty:
            top = (
                self._df_consents.groupby("receptor")["total"]
                .sum().sort_values(ascending=False).index.tolist()
            )
            self._receptor_combo.addItems(top)

        # Restaura seleção anterior se possível
        idx = self._receptor_combo.findText(prev)
        self._receptor_combo.setCurrentIndex(max(0, idx))
        self._receptor_combo.blockSignals(False)

    # ── Gráficos ──────────────────────────────────────────────────────────────

    def _draw_charts(self) -> None:
        self._draw_chart1()
        self._draw_chart2()

    def _draw_chart1(self) -> None:
        self._fig1.clear()
        ax = self._fig1.add_subplot(111)

        if self._df_consents.empty:
            ax.text(0.5, 0.5, "Sem dados de consentimentos",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas1.draw()
            return

        selected = self._receptor_combo.currentText()
        if selected == "Top 10 receptores":
            top10 = (
                self._df_consents.groupby("receptor")["total"]
                .sum().nlargest(10).index
            )
            df = self._df_consents[self._df_consents["receptor"].isin(top10)]
        else:
            df = self._df_consents[self._df_consents["receptor"] == selected]

        if df.empty:
            ax.text(0.5, 0.5, "Sem dados para o receptor selecionado",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas1.draw()
            return

        colors = plt.cm.tab20.colors
        for i, (receptor, grp) in enumerate(df.groupby("receptor")):
            grp = grp.sort_values("date")
            ax.plot(
                grp["date"], grp["total"],
                marker="o", markersize=3, linewidth=1.4,
                color=colors[i % len(colors)],
                label=receptor[:35],
            )

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b/%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        self._fig1.autofmt_xdate(rotation=30, ha="right")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_number))
        ax.set_ylabel("Consentimentos únicos")
        ax.grid(True, axis="y")
        ax.legend(
            fontsize=7, ncol=2,
            loc="upper left",
            framealpha=0.6,
        )

        self._canvas1.draw()

    def _draw_chart2(self) -> None:
        self._fig2.clear()
        ax = self._fig2.add_subplot(111)

        if self._df_api.empty:
            ax.text(0.5, 0.5, "Sem dados de chamadas de API",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas2.draw()
            return

        # Filtra status
        status_txt = self._status_combo.currentText()
        df = self._df_api.copy()
        if status_txt != "Todos":
            df = df[df["status"] == int(status_txt)]

        if df.empty:
            ax.text(0.5, 0.5, f"Sem dados para status {status_txt}",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas2.draw()
            return

        # Filtra receptor (se selecionado um específico)
        selected = self._receptor_combo.currentText()
        if selected != "Top 10 receptores":
            df = df[df["receptor"] == selected]
            if df.empty:
                ax.text(0.5, 0.5, "Sem dados de API para este receptor",
                        ha="center", va="center", transform=ax.transAxes)
                self._canvas2.draw()
                return
            top_receptors = [selected]
        else:
            top_receptors = (
                df.groupby("receptor")["total"].sum()
                .nlargest(15).index.tolist()
            )
            df = df[df["receptor"].isin(top_receptors)]

        pivot = (
            df.groupby(["receptor", "api"])["total"]
            .sum().unstack(fill_value=0)
            .reindex(top_receptors)
            .fillna(0)
        )

        data = pivot.values.astype(float)
        # Escala log para lidar com variância alta (Nubank 67M vs outros)
        data_log = np.log1p(data)

        im = ax.imshow(data_log, aspect="auto", cmap="YlOrRd",
                       interpolation="nearest")

        # Eixos
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(
            [c.replace("-", "\n") for c in pivot.columns],
            fontsize=7, ha="center",
        )
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(
            [r[:28] for r in pivot.index],
            fontsize=7,
        )

        # Anotações com valor real nas células
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = data[i, j]
                if val > 0:
                    txt = _fmt_number(val)
                    brightness = data_log[i, j] / (data_log.max() or 1)
                    color = "#1e1e2e" if brightness > 0.55 else "#cdd6f4"
                    ax.text(j, i, txt, ha="center", va="center",
                            fontsize=6, color=color)

        cb = self._fig2.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
        cb.set_label("Total (escala log)", color="#cdd6f4")
        cb.ax.yaxis.set_tick_params(color="#a6adc8")
        plt.setp(cb.ax.yaxis.get_ticklabels(), color="#a6adc8")

        self._canvas2.draw()

    def _show_empty_charts(self, msg: str) -> None:
        for fig, canvas in ((self._fig1, self._canvas1), (self._fig2, self._canvas2)):
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, msg, ha="center", va="center",
                    transform=ax.transAxes, fontsize=10)
            canvas.draw()

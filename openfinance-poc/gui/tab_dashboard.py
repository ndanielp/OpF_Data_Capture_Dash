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
    QListWidget, QAbstractItemView,
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

BG_FIG = "#1e1e2e"
BG_AX  = "#181825"

# (substring lowercase, hex color, linewidth)
_BRAND = [
    ("bradesco",     "#8B0000", 2.5),
    ("nubank",       "#7C3AED", 1.4),
    ("itaú",         "#F97316", 1.4),
    ("itau",         "#F97316", 1.4),
    ("santander",    "#EF4444", 1.4),
    ("caixa",        "#2563EB", 1.4),
    ("mercado pago", "#38BDF8", 1.4),
    ("picpay",       "#22C55E", 1.4),
]

_FALLBACK_COLORS = [
    "#f9e2af", "#cba6f7", "#f38ba8", "#fab387",
    "#89dceb", "#b4befe", "#eba0ac", "#94e2d5",
    "#a6e3a1", "#89b4fa", "#cdd6f4", "#a6adc8",
]


def _brand_style(receptor: str) -> tuple[str, float] | None:
    name = receptor.lower()
    for key, color, lw in _BRAND:
        if key in name:
            return color, lw
    return None


def _fmt_number(x: float, _=None) -> str:
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}k"
    return str(int(x))


class _Canvas(FigureCanvas):
    def __init__(self, fig: Figure) -> None:
        super().__init__(fig)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class TabDashboard(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path     = db_path
        self._df_consents = pd.DataFrame()
        self._df_api      = pd.DataFrame()
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

        # Lista de receptores com multi-seleção
        hl.addWidget(QLabel("Receptores:"))
        self._receptor_list = QListWidget()
        self._receptor_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._receptor_list.setFixedHeight(90)
        self._receptor_list.setMinimumWidth(240)
        self._receptor_list.setToolTip(
            "Ctrl+clique para selecionar múltiplos.\n"
            "'Top 10 receptores' inclui os 10 maiores + Bradesco."
        )
        self._receptor_list.itemSelectionChanged.connect(self._draw_charts)
        hl.addWidget(self._receptor_list)

        # Status (heatmap)
        hl.addWidget(QLabel("Status (API):"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(["200", "500", "Todos"])
        self._status_combo.currentIndexChanged.connect(self._draw_chart2)
        hl.addWidget(self._status_combo)

        # Escala do heatmap
        hl.addWidget(QLabel("Escala (API):"))
        self._api_scale_combo = QComboBox()
        self._api_scale_combo.addItems(["Valor absoluto", "Por consentimento único"])
        self._api_scale_combo.setToolTip(
            "Por consentimento único: divide o volume de chamadas\n"
            "pelo total de consentimentos (PF + PJ) do receptor."
        )
        self._api_scale_combo.currentIndexChanged.connect(self._draw_chart2)
        hl.addWidget(self._api_scale_combo)

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

        self._populate_receptor_list()
        self._draw_charts()

    def _populate_receptor_list(self) -> None:
        self._receptor_list.blockSignals(True)
        prev_selected = {it.text() for it in self._receptor_list.selectedItems()}
        self._receptor_list.clear()
        self._receptor_list.addItem("Top 10 receptores")

        if not self._df_consents.empty:
            top = (
                self._df_consents.groupby("receptor")["total"]
                .sum().sort_values(ascending=False).index.tolist()
            )
            self._receptor_list.addItems(top)

        # Restaura seleção anterior se possível
        restored = False
        if prev_selected:
            for i in range(self._receptor_list.count()):
                item = self._receptor_list.item(i)
                if item.text() in prev_selected:
                    item.setSelected(True)
                    restored = True
        if not restored:
            self._receptor_list.item(0).setSelected(True)

        self._receptor_list.blockSignals(False)

    # ── Helpers de seleção e cores ────────────────────────────────────────────

    def _selected_receptors(self) -> list[str] | None:
        """None = modo Top 10; list = receptores específicos selecionados."""
        selected = [it.text() for it in self._receptor_list.selectedItems()]
        if not selected or "Top 10 receptores" in selected:
            return None
        return selected

    def _top10_with_bradesco(self, df: pd.DataFrame) -> list[str]:
        """Top 10 por volume total, com Bradesco forçado se não estiver presente."""
        totals = df.groupby("receptor")["total"].sum().sort_values(ascending=False)
        top10  = totals.nlargest(10).index.tolist()
        for r in totals.index:
            if "bradesco" in r.lower() and r not in top10:
                top10 = top10[:9] + [r]
                break
        return top10

    def _receptor_colors(self, receptors: list[str]) -> dict[str, tuple[str, float]]:
        """Retorna {receptor: (color, linewidth)}. Cores de marca fixas; demais aleatórias sem repetição."""
        result: dict[str, tuple[str, float]] = {}
        used:   set[str] = set()
        fb_idx = 0
        for r in receptors:
            style = _brand_style(r)
            if style:
                result[r] = style
                used.add(style[0])
            else:
                while fb_idx < len(_FALLBACK_COLORS) and _FALLBACK_COLORS[fb_idx] in used:
                    fb_idx += 1
                color = _FALLBACK_COLORS[fb_idx % len(_FALLBACK_COLORS)]
                used.add(color)
                fb_idx += 1
                result[r] = (color, 1.4)
        return result

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

        sel = self._selected_receptors()
        if sel is None:
            receptors = self._top10_with_bradesco(self._df_consents)
        else:
            receptors = sel

        df = self._df_consents[self._df_consents["receptor"].isin(receptors)]
        if df.empty:
            ax.text(0.5, 0.5, "Sem dados para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas1.draw()
            return

        styles = self._receptor_colors(receptors)
        for receptor, grp in df.groupby("receptor"):
            color, lw = styles.get(receptor, ("#cdd6f4", 1.4))
            grp = grp.sort_values("date")
            ax.plot(
                grp["date"], grp["total"],
                marker="o", markersize=3,
                linewidth=lw,
                color=color,
                label=receptor[:35],
                zorder=3 if lw > 1.4 else 2,
            )

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b/%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        self._fig1.autofmt_xdate(rotation=30, ha="right")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_number))
        ax.set_ylabel("Consentimentos únicos")
        ax.grid(True, axis="y")
        ax.legend(fontsize=7, ncol=2, loc="upper left", framealpha=0.6)
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

        # Filtra receptores
        sel = self._selected_receptors()
        if sel is None:
            top_receptors = (
                df.groupby("receptor")["total"].sum()
                .nlargest(15).index.tolist()
            )
            # Força Bradesco
            for r in df["receptor"].unique():
                if "bradesco" in r.lower() and r not in top_receptors:
                    top_receptors = top_receptors[:14] + [r]
                    break
        else:
            top_receptors = sel

        df = df[df["receptor"].isin(top_receptors)]
        if df.empty:
            ax.text(0.5, 0.5, "Sem dados de API para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas2.draw()
            return

        pivot = (
            df.groupby(["receptor", "api"])["total"]
            .sum().unstack(fill_value=0)
            .reindex(top_receptors)
            .fillna(0)
        )
        data = pivot.values.astype(float)

        # Normalização por consentimentos únicos
        normalize = self._api_scale_combo.currentText() == "Por consentimento único"
        if normalize and not self._df_consents.empty:
            consents_total = self._df_consents.groupby("receptor")["total"].sum()
            for i, rec in enumerate(pivot.index):
                n = consents_total.get(rec, 0)
                if n > 0:
                    data[i] /= n

        data_log = np.log1p(data)
        im = ax.imshow(data_log, aspect="auto", cmap="YlOrRd", interpolation="nearest")

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(
            [c.replace("-", "\n") for c in pivot.columns],
            fontsize=7, ha="center",
        )
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([r[:28] for r in pivot.index], fontsize=7)

        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = data[i, j]
                if val > 0:
                    txt = f"{val:.2f}" if normalize else _fmt_number(val)
                    brightness = data_log[i, j] / (data_log.max() or 1)
                    color = "#1e1e2e" if brightness > 0.55 else "#cdd6f4"
                    ax.text(j, i, txt, ha="center", va="center", fontsize=6, color=color)

        label = "Chamadas / consentimento único (log)" if normalize else "Total (escala log)"
        cb = self._fig2.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
        cb.set_label(label, color="#cdd6f4")
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

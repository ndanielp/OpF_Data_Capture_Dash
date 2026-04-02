"""
tab_dashboard.py — Aba de visualização de dados.

Gráfico 1: Consentimentos únicos por receptor ao longo do tempo (linhas).
Gráfico 2: Volume de chamadas de API — heatmap receptor × API (agrupado).
Gráfico 3: Resources — barras horizontais por receptor.
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
    QLabel, QPushButton, QSplitter, QSizePolicy,
    QListWidget, QAbstractItemView, QRadioButton, QButtonGroup,
    QCheckBox, QFrame,
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

# ── API grouping ──────────────────────────────────────────────────────────────

API_GROUPS = {
    "Conta":        ["accounts"],
    "Cartão":       ["credit-cards-accounts"],
    "Crédito":      ["loans", "financings", "invoice-financings",
                     "unarranged-accounts-overdraft"],
    "Investimento": ["funds", "bank-fixed-incomes", "credit-fixed-incomes",
                     "variable-incomes", "treasure-titles"],
    "Câmbio":       ["exchanges"],
    "Cadastro":     ["customers"],
}
RESOURCES_API = "resources"
EXCLUDED_APIS = {"consents"}

# Ordem canônica das colunas do heatmap
_ORDERED_APIS: list[str] = [api for apis in API_GROUPS.values() for api in apis]

# Short display names for heatmap column ticks
_API_SHORT: dict[str, str] = {
    "accounts":                    "accounts",
    "credit-cards-accounts":       "credit-cards",
    "loans":                       "loans",
    "financings":                  "financings",
    "invoice-financings":          "invoice-fin.",
    "unarranged-accounts-overdraft": "overdraft",
    "funds":                       "funds",
    "bank-fixed-incomes":          "bank-fixed",
    "credit-fixed-incomes":        "credit-fixed",
    "variable-incomes":            "variable",
    "treasure-titles":             "treasure",
    "exchanges":                   "exchanges",
    "customers":                   "customers",
}

# ── Brand colours ─────────────────────────────────────────────────────────────

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
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


# ── Separator line ────────────────────────────────────────────────────────────

def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #45475a;")
    return line


class TabDashboard(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path     = db_path
        self._df_consents = pd.DataFrame()
        self._df_api      = pd.DataFrame()
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_filter_panel())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_chart_group("Consentimentos Únicos por Receptor",
                                                   "_canvas1", "_fig1"))
        splitter.addWidget(self._build_chart_group("Chamadas de API por Grupo",
                                                   "_canvas2", "_fig2"))
        splitter.addWidget(self._build_chart_group("Resources por Receptor",
                                                   "_canvas3", "_fig3"))
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        root.addWidget(splitter, stretch=1)

    def _build_filter_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(220)
        panel.setStyleSheet("background: #181825; border-right: 1px solid #313244;")
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(10, 12, 10, 12)
        vl.setSpacing(10)

        # ── Receptores ────────────────────────────────────────────────────────
        lbl_r = QLabel("Receptores")
        lbl_r.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 9pt;")
        vl.addWidget(lbl_r)

        self._receptor_list = QListWidget()
        self._receptor_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._receptor_list.setStyleSheet("""
            QListWidget {
                background: #1e1e2e; border: 1px solid #45475a;
                border-radius: 4px; color: #cdd6f4; font-size: 8pt;
            }
            QListWidget::item:selected { background: #313244; }
        """)
        self._receptor_list.setToolTip("Ctrl+clique para múltiplos.\n'Top 10' inclui Bradesco.")
        self._receptor_list.itemSelectionChanged.connect(self._draw_charts)
        vl.addWidget(self._receptor_list, stretch=1)

        vl.addWidget(_hline())

        # ── Status ────────────────────────────────────────────────────────────
        lbl_s = QLabel("Status (API)")
        lbl_s.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 9pt;")
        vl.addWidget(lbl_s)

        self._status_group = QButtonGroup(self)
        for i, txt in enumerate(["200", "500", "Todos"]):
            rb = QRadioButton(txt)
            rb.setStyleSheet("color: #cdd6f4; font-size: 9pt;")
            self._status_group.addButton(rb, i)
            vl.addWidget(rb)
        self._status_group.button(2).setChecked(True)   # "Todos" default
        self._status_group.buttonToggled.connect(
            lambda _btn, checked: self._draw_chart2() or self._draw_chart3() if checked else None
        )

        vl.addWidget(_hline())

        # ── Escala API ────────────────────────────────────────────────────────
        lbl_e = QLabel("Escala API")
        lbl_e.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 9pt;")
        vl.addWidget(lbl_e)

        self._normalize_chk = QCheckBox("Por consentimento único")
        self._normalize_chk.setStyleSheet("color: #cdd6f4; font-size: 9pt;")
        self._normalize_chk.setToolTip(
            "Divide o volume de chamadas pelo total\n"
            "de consentimentos (PF + PJ) do receptor."
        )
        self._normalize_chk.stateChanged.connect(
            lambda _: self._draw_chart2() or self._draw_chart3()
        )
        vl.addWidget(self._normalize_chk)

        vl.addWidget(_hline())

        # ── Botão ─────────────────────────────────────────────────────────────
        btn = QPushButton("↺  Recarregar dados")
        btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 4px;"
            " padding: 5px; font-size: 9pt; }"
            "QPushButton:hover { background: #45475a; }"
        )
        btn.clicked.connect(self.load_data)
        vl.addWidget(btn)

        return panel

    def _build_chart_group(self, title: str, canvas_attr: str, fig_attr: str) -> QGroupBox:
        grp = QGroupBox(title)
        vl  = QVBoxLayout(grp)
        fig = Figure(facecolor=BG_FIG, tight_layout=True)
        canvas = _Canvas(fig)
        setattr(self, fig_attr,    fig)
        setattr(self, canvas_attr, canvas)
        vl.addWidget(canvas)
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _selected_receptors(self) -> list[str] | None:
        """None = modo Top 10; list = receptores específicos."""
        selected = [it.text() for it in self._receptor_list.selectedItems()]
        if not selected or "Top 10 receptores" in selected:
            return None
        return selected

    def _top10_with_bradesco(self, df: pd.DataFrame) -> list[str]:
        totals = df.groupby("receptor")["total"].sum().sort_values(ascending=False)
        top10  = totals.nlargest(10).index.tolist()
        for r in totals.index:
            if "bradesco" in r.lower() and r not in top10:
                top10 = top10[:9] + [r]
                break
        return top10

    def _receptor_colors(self, receptors: list[str]) -> dict[str, tuple[str, float]]:
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

    def _status_filter(self) -> int | None:
        """Returns 200, 500, or None (Todos)."""
        checked_id = self._status_group.checkedId()
        return [200, 500, None][checked_id]

    def _normalize(self) -> bool:
        return self._normalize_chk.isChecked()

    def _consent_totals(self) -> pd.Series:
        if self._df_consents.empty:
            return pd.Series(dtype=float)
        return self._df_consents.groupby("receptor")["total"].sum()

    # ── Gráficos ──────────────────────────────────────────────────────────────

    def _draw_charts(self) -> None:
        self._draw_chart1()
        self._draw_chart2()
        self._draw_chart3()

    def _draw_chart1(self) -> None:
        self._fig1.clear()
        ax = self._fig1.add_subplot(111)

        if self._df_consents.empty:
            ax.text(0.5, 0.5, "Sem dados de consentimentos",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas1.draw()
            return

        sel = self._selected_receptors()
        receptors = self._top10_with_bradesco(self._df_consents) if sel is None else sel
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
                marker="o", markersize=3, linewidth=lw, color=color,
                label=receptor[:35],
                zorder=3 if lw > 1.4 else 2,
            )

        ax.set_ylim(bottom=0)
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

        status = self._status_filter()
        df = self._df_api[~self._df_api["api"].isin(EXCLUDED_APIS | {RESOURCES_API})].copy()
        if status is not None:
            df = df[df["status"] == status]

        if df.empty:
            ax.text(0.5, 0.5, "Sem dados para os filtros selecionados",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas2.draw()
            return

        sel = self._selected_receptors()
        if sel is None:
            top_receptors = self._top10_with_bradesco(
                self._df_consents if not self._df_consents.empty else df
            )
            # Garante que só inclui receptores com dados de API
            top_receptors = [r for r in top_receptors if r in df["receptor"].values]
        else:
            top_receptors = sel

        df = df[df["receptor"].isin(top_receptors)]
        if df.empty:
            ax.text(0.5, 0.5, "Sem dados de API para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas2.draw()
            return

        # Ordem canônica das colunas (apenas as presentes nos dados)
        available_apis = set(df["api"].unique())
        ordered_cols = [a for a in _ORDERED_APIS if a in available_apis]

        pivot = (
            df.groupby(["receptor", "api"])["total"]
            .sum().unstack(fill_value=0)
            .reindex(index=top_receptors, columns=ordered_cols)
            .fillna(0)
        )
        data = pivot.values.astype(float)

        if self._normalize():
            ct = self._consent_totals()
            for i, rec in enumerate(pivot.index):
                n = ct.get(rec, 0)
                if n > 0:
                    data[i] /= n

        data_log = np.log1p(data)
        im = ax.imshow(data_log, aspect="auto", cmap="YlOrRd", interpolation="nearest")

        # Tick labels X (nome curto)
        ax.set_xticks(range(len(ordered_cols)))
        ax.set_xticklabels(
            [_API_SHORT.get(c, c).replace("-", "\n") for c in ordered_cols],
            fontsize=7, ha="center",
        )
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([r[:28] for r in pivot.index], fontsize=7)

        # Separadores e labels de grupo
        col_idx = 0
        for grupo, apis in API_GROUPS.items():
            cols_in_group = [a for a in apis if a in available_apis]
            if not cols_in_group:
                continue
            start = col_idx
            span  = len(cols_in_group)
            center = start + (span - 1) / 2
            n_rows = len(pivot.index)
            # Label do grupo acima do heatmap
            ax.text(center, -1.1, grupo,
                    ha="center", va="bottom", fontsize=7,
                    color="#a6adc8", transform=ax.get_xaxis_transform())
            # Separador antes do grupo (exceto o primeiro)
            if start > 0:
                ax.axvline(start - 0.5, color="#45475a", lw=0.8)
            col_idx += span

        # Anotações de valor nas células
        for i in range(len(pivot.index)):
            for j in range(len(ordered_cols)):
                val = data[i, j]
                if val > 0:
                    txt = f"{val:.2f}" if self._normalize() else _fmt_number(val)
                    brightness = data_log[i, j] / (data_log.max() or 1)
                    color = "#1e1e2e" if brightness > 0.55 else "#cdd6f4"
                    ax.text(j, i, txt, ha="center", va="center", fontsize=6, color=color)

        cb_label = "Chamadas / consentimento (log)" if self._normalize() else "Total (escala log)"
        cb = self._fig2.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
        cb.set_label(cb_label, color="#cdd6f4")
        cb.ax.yaxis.set_tick_params(color="#a6adc8")
        plt.setp(cb.ax.yaxis.get_ticklabels(), color="#a6adc8")

        self._canvas2.draw()

    def _draw_chart3(self) -> None:
        self._fig3.clear()
        ax = self._fig3.add_subplot(111)

        if self._df_api.empty:
            ax.text(0.5, 0.5, "Sem dados de resources",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas3.draw()
            return

        status = self._status_filter()
        df = self._df_api[self._df_api["api"] == RESOURCES_API].copy()
        if status is not None:
            df = df[df["status"] == status]

        if df.empty:
            ax.text(0.5, 0.5, f"Sem dados de resources para o filtro selecionado",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas3.draw()
            return

        sel = self._selected_receptors()
        if sel is None:
            top_receptors = self._top10_with_bradesco(
                self._df_consents if not self._df_consents.empty else df
            )
            top_receptors = [r for r in top_receptors if r in df["receptor"].values]
        else:
            top_receptors = [r for r in sel if r in df["receptor"].values]

        df = df[df["receptor"].isin(top_receptors)]
        if df.empty:
            ax.text(0.5, 0.5, "Sem dados de resources para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes)
            self._canvas3.draw()
            return

        totals = df.groupby("receptor")["total"].sum().reindex(top_receptors).fillna(0)
        values = totals.values.astype(float)

        if self._normalize():
            ct = self._consent_totals()
            for i, rec in enumerate(totals.index):
                n = ct.get(rec, 0)
                if n > 0:
                    values[i] /= n

        styles = self._receptor_colors(list(totals.index))
        colors = [styles.get(r, ("#cdd6f4", 1.4))[0] for r in totals.index]

        bars = ax.barh(range(len(totals)), values, color=colors)
        ax.set_yticks(range(len(totals)))
        ax.set_yticklabels([r[:30] for r in totals.index], fontsize=7)
        ax.invert_yaxis()

        fmt = (lambda x, _: f"{x:.2f}") if self._normalize() else _fmt_number
        ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt))
        ax.set_xlabel(
            "Chamadas / consentimento único" if self._normalize() else "Total de chamadas"
        )
        ax.grid(True, axis="x", alpha=0.4)

        # Valor à direita de cada barra
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_width() * 1.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:.2f}" if self._normalize() else _fmt_number(val),
                    va="center", fontsize=7, color="#cdd6f4",
                )

        self._canvas3.draw()

    def _show_empty_charts(self, msg: str) -> None:
        for fig, canvas in (
            (self._fig1, self._canvas1),
            (self._fig2, self._canvas2),
            (self._fig3, self._canvas3),
        ):
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, msg, ha="center", va="center",
                    transform=ax.transAxes, fontsize=10)
            canvas.draw()

"""
tab_dashboard.py — Aba de visualização de dados.

Layout baseado no mockup interface.html:
  Sidebar esquerda (224px) │ Date bar + 3 chart cards
  ─────────────────────────────────────────────────────
  Busca + lista receptores │ [Período ▸ date range + presets]
  Status radio (200/500/T) │ [Consentimentos — linha]
  Toggle normalização      │ [APIs — heatmap agrupado]
  Botão recarregar         │ [Resources — barras horiz.]
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
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QSizePolicy,
    QListWidget, QAbstractItemView, QRadioButton, QButtonGroup,
    QFrame, QLineEdit, QDateEdit, QFileDialog,
    QStyledItemDelegate, QScrollArea, QStyle,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

# ── Design tokens (interface.html) ────────────────────────────────────────────
BG_BASE     = "#13151E"
BG_SURFACE  = "#1B1F2E"
BG_ELEVATED = "#242838"
BG_HOVER    = "#2D3247"
TXT_PRIMARY = "#EEF0F6"
TXT_SECOND  = "#8B95B0"
TXT_MUTED   = "#4A5270"
TXT_ACCENT  = "#4A9EFF"
BORDER_SUB  = "#252A3A"
BORDER_DEF  = "#333B54"

matplotlib.rcParams.update({
    "text.color":        TXT_SECOND,
    "axes.labelcolor":   TXT_SECOND,
    "xtick.color":       TXT_MUTED,
    "ytick.color":       TXT_MUTED,
    "axes.edgecolor":    BORDER_DEF,
    "grid.color":        BORDER_SUB,
    "grid.linewidth":    0.5,
    "figure.facecolor":  BG_SURFACE,
    "axes.facecolor":    BG_BASE,
    "legend.facecolor":  BG_ELEVATED,
    "legend.edgecolor":  BORDER_DEF,
    "legend.labelcolor": TXT_SECOND,
    "font.size":         9,
})

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

_ORDERED_APIS: list[str] = [api for apis in API_GROUPS.values() for api in apis]

_API_SHORT: dict[str, str] = {
    "accounts":                      "accounts",
    "credit-cards-accounts":         "credit\ncards",
    "loans":                         "loans",
    "financings":                    "financings",
    "invoice-financings":            "invoice\nfin.",
    "unarranged-accounts-overdraft": "overdraft",
    "funds":                         "funds",
    "bank-fixed-incomes":            "bank\nfixed",
    "credit-fixed-incomes":          "credit\nfixed",
    "variable-incomes":              "variable",
    "treasure-titles":               "treasure",
    "exchanges":                     "exchanges",
    "customers":                     "customers",
}

# ── Brand colours (matching interface.html) ───────────────────────────────────
_BRAND = [
    ("bradesco",        "#CC092F", 2.5),
    ("nubank",          "#8B1CF0", 1.6),
    ("itaú",            "#EC7000", 1.6),
    ("itau",            "#EC7000", 1.6),
    ("santander",       "#EC0000", 1.6),
    ("caixa",           "#005CA9", 1.6),
    ("mercado pago",    "#00A9E0", 1.6),
    ("picpay",          "#21C25E", 1.6),
    ("banco do brasil", "#F9A800", 1.6),
]

_FALLBACK_COLORS = [
    "#4A9EFF", "#7B68EE", "#FF5722", "#34B7F1",
    "#9C27B0", "#F9E68C", "#cba6f7", "#f38ba8",
    "#fab387", "#94e2d5", "#b4befe", "#a6e3a1",
]


def _brand_style(receptor: str) -> tuple[str, float] | None:
    name = receptor.lower()
    for key, color, lw in _BRAND:
        if key in name:
            return color, lw
    return None


def _fmt_number(x: float, _=None) -> str:
    if x >= 1_000_000_000:
        return f"{x / 1_000_000_000:.1f}B"
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}k"
    return str(int(x))


# ── Custom widgets ────────────────────────────────────────────────────────────

class _ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._checked = False
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool) -> None:
        if val != self._checked:
            self._checked = val
            self.update()

    def mousePressEvent(self, _) -> None:
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_col = QColor(TXT_ACCENT) if self._checked else QColor(BORDER_DEF)
        p.setBrush(QBrush(track_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 3, 40, 16, 8, 8)
        p.setBrush(QBrush(QColor("white")))
        knob_x = 22 if self._checked else 2
        p.drawEllipse(knob_x, 5, 14, 14)
        p.end()


class _ReceptorDelegate(QStyledItemDelegate):
    _DOT = 5  # radius px

    def __init__(self, colors: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self._colors = colors

    def update_colors(self, colors: dict[str, str]) -> None:
        self._colors = colors

    def paint(self, painter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect  = option.rect
        name  = index.data(Qt.ItemDataRole.DisplayRole) or ""
        color_hex = self._colors.get(name)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor(74, 158, 255, 25))

        # Dot
        dot_col = QColor(color_hex) if color_hex else QColor(BORDER_DEF)
        painter.setBrush(QBrush(dot_col))
        painter.setPen(Qt.PenStyle.NoPen)
        cx = rect.left() + 12 + self._DOT
        cy = rect.center().y()
        painter.drawEllipse(cx - self._DOT, cy - self._DOT,
                            self._DOT * 2, self._DOT * 2)

        # Text
        txt_col = QColor(TXT_PRIMARY) if color_hex else QColor(TXT_MUTED)
        painter.setPen(QPen(txt_col))
        text_rect = QRect(cx + self._DOT + 6, rect.top(),
                          rect.right() - cx - self._DOT - 10, rect.height())
        elided = option.fontMetrics.elidedText(
            name, Qt.TextElideMode.ElideRight, text_rect.width()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, elided)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), 26)


class _Canvas(FigureCanvas):
    def __init__(self, fig: Figure) -> None:
        super().__init__(fig)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{BORDER_SUB}; border:none;")
    return f


# ── Main widget ───────────────────────────────────────────────────────────────

class TabDashboard(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path          = db_path
        self._df_consents      = pd.DataFrame()
        self._df_api           = pd.DataFrame()
        self._receptor_colors: dict[str, str] = {}
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"background:{BG_BASE};")
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._build_sidebar())

        right = QWidget()
        right.setStyleSheet(f"background:{BG_BASE};")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 12, 16, 12)
        rv.setSpacing(10)
        rv.addWidget(self._build_date_bar())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle{background:transparent;height:6px;}")
        splitter.addWidget(self._make_chart_card(
            "Consentimentos Únicos por Receptor",
            "Evolução semanal · top receptores",
            "_fig1", "_canvas1", self._export_consents,
        ))
        splitter.addWidget(self._make_chart_card(
            "Chamadas de API por Grupo",
            "Volume acumulado no período · escala logarítmica",
            "_fig2", "_canvas2", self._export_api,
        ))
        splitter.addWidget(self._make_chart_card(
            "Resources por Receptor",
            "Total de chamadas de API · endpoint /resources",
            "_fig3", "_canvas3", self._export_resources,
        ))
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        rv.addWidget(splitter, stretch=1)
        root.addWidget(right, stretch=1)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(224)
        sidebar.setStyleSheet(f"QFrame{{background:{BG_SURFACE};border-right:1px solid {BORDER_SUB};}}")

        vl = QVBoxLayout(sidebar)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea, QScrollArea > QWidget > QWidget {{background:{BG_SURFACE};border:none;}}
            QScrollBar:vertical {{background:transparent;width:4px;margin:0;}}
            QScrollBar::handle:vertical {{background:{BORDER_DEF};border-radius:2px;min-height:20px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
        """)

        inner = QWidget()
        inner.setStyleSheet(f"background:{BG_SURFACE};")
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(0)

        iv.addWidget(self._sidebar_group("Receptores", self._build_receptor_section(), count=True))
        iv.addWidget(_sep())
        iv.addWidget(self._sidebar_group("Status API",  self._build_status_section()))
        iv.addWidget(_sep())
        iv.addWidget(self._sidebar_group("Escala API",  self._build_escala_section()))
        iv.addStretch()

        scroll.setWidget(inner)
        vl.addWidget(scroll, stretch=1)
        vl.addWidget(_sep())
        vl.addWidget(self._build_sidebar_footer())
        return sidebar

    def _sidebar_group(self, title: str, content: QWidget, count: bool = False) -> QWidget:
        grp = QWidget()
        grp.setStyleSheet(f"background:{BG_SURFACE};")
        vl = QVBoxLayout(grp)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(8)

        hdr = QHBoxLayout()
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"color:{TXT_MUTED};font-size:10px;font-weight:700;"
                          f"letter-spacing:1px;background:transparent;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        if count:
            self._receptor_count_lbl = QLabel("0")
            self._receptor_count_lbl.setStyleSheet(
                f"color:{TXT_MUTED};background:{BG_ELEVATED};"
                f"font-size:10px;padding:1px 6px;border-radius:10px;"
            )
            hdr.addWidget(self._receptor_count_lbl)

        vl.addLayout(hdr)
        vl.addWidget(content)
        return grp

    def _build_receptor_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(6)

        self._receptor_search = QLineEdit()
        self._receptor_search.setPlaceholderText("Filtrar receptores…")
        self._receptor_search.setStyleSheet(f"""
            QLineEdit{{background:{BG_ELEVATED};border:1px solid {BORDER_DEF};
                border-radius:4px;color:{TXT_PRIMARY};font-size:11px;padding:4px 8px;}}
            QLineEdit:focus{{border-color:{TXT_ACCENT};}}
        """)
        self._receptor_search.textChanged.connect(self._filter_receptor_list)
        vl.addWidget(self._receptor_search)

        self._receptor_list = QListWidget()
        self._receptor_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._receptor_list.setMaximumHeight(230)
        self._receptor_list.setToolTip("Ctrl+clique para múltiplos.\n'Top 10' inclui Bradesco.")
        self._receptor_list.setStyleSheet(f"""
            QListWidget{{background:transparent;border:none;outline:none;}}
            QListWidget::item{{padding:0px;border-radius:4px;}}
            QListWidget::item:hover{{background:{BG_HOVER};}}
        """)
        self._receptor_list.itemSelectionChanged.connect(self._draw_charts)
        self._delegate = _ReceptorDelegate({})
        self._receptor_list.setItemDelegate(self._delegate)
        vl.addWidget(self._receptor_list)
        return w

    def _build_status_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(2)

        self._status_group = QButtonGroup(self)
        rb_qss = f"""
            QRadioButton{{color:{TXT_SECOND};font-size:11px;padding:4px 2px;background:transparent;}}
            QRadioButton:checked{{color:{TXT_PRIMARY};}}
            QRadioButton::indicator{{width:14px;height:14px;border-radius:7px;border:2px solid {BORDER_DEF};}}
            QRadioButton::indicator:checked{{border:2px solid {TXT_ACCENT};background:{TXT_ACCENT};}}
        """
        for i, label in enumerate(["200 — Sucesso", "500 — Erro", "Todos"]):
            rb = QRadioButton(label)
            rb.setStyleSheet(rb_qss)
            self._status_group.addButton(rb, i)
            vl.addWidget(rb)
        self._status_group.button(2).setChecked(True)
        self._status_group.buttonToggled.connect(self._on_status_changed)
        return w

    def _build_escala_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)

        info = QWidget()
        info.setStyleSheet("background:transparent;")
        iv = QVBoxLayout(info)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(3)

        lbl = QLabel("Por consentimento único")
        lbl.setStyleSheet(f"color:{TXT_SECOND};font-size:11px;background:transparent;")
        iv.addWidget(lbl)

        desc = QLabel("Normaliza o volume pelo\ntotal de consentimentos\nativos no período")
        desc.setStyleSheet(f"color:{TXT_MUTED};font-size:10px;background:transparent;")
        iv.addWidget(desc)
        hl.addWidget(info, stretch=1)

        self._normalize_toggle = _ToggleSwitch()
        self._normalize_toggle.toggled.connect(self._on_normalize_changed)
        hl.addWidget(self._normalize_toggle, alignment=Qt.AlignmentFlag.AlignTop)
        return w

    def _build_sidebar_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet(f"background:{BG_SURFACE};")
        vl = QVBoxLayout(footer)
        vl.setContentsMargins(14, 10, 14, 12)
        vl.setSpacing(0)

        btn = QPushButton("↺  Recarregar dados")
        btn.setStyleSheet(f"""
            QPushButton{{background:{BG_ELEVATED};border:1px solid {BORDER_DEF};
                color:{TXT_SECOND};font-size:11px;padding:8px 12px;border-radius:8px;}}
            QPushButton:hover{{background:{BG_HOVER};color:{TXT_PRIMARY};}}
        """)
        btn.clicked.connect(self.load_data)
        vl.addWidget(btn)
        return footer

    # ── Date bar ──────────────────────────────────────────────────────────────

    def _build_date_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(46)
        bar.setStyleSheet(f"""
            QFrame{{background:{BG_ELEVATED};border:1px solid {BORDER_SUB};border-radius:8px;}}
        """)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(10)

        period_lbl = QLabel("Período")
        period_lbl.setStyleSheet(f"color:{TXT_MUTED};font-size:10px;font-weight:700;"
                                  f"background:transparent;border:none;")
        hl.addWidget(period_lbl)

        date_qss = f"""
            QDateEdit{{background:{BG_SURFACE};border:1px solid {BORDER_DEF};
                border-radius:4px;color:{TXT_PRIMARY};font-size:11px;padding:3px 6px;}}
            QDateEdit:focus{{border-color:{TXT_ACCENT};}}
            QDateEdit::drop-down{{width:14px;subcontrol-position:right center;}}
        """
        self._date_start_edit = QDateEdit(QDate.currentDate().addMonths(-12))
        self._date_start_edit.setCalendarPopup(True)
        self._date_start_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_start_edit.setStyleSheet(date_qss)
        self._date_start_edit.setFixedWidth(96)

        arr = QLabel("→")
        arr.setStyleSheet(f"color:{TXT_MUTED};background:transparent;border:none;")

        self._date_end_edit = QDateEdit(QDate.currentDate())
        self._date_end_edit.setCalendarPopup(True)
        self._date_end_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_end_edit.setStyleSheet(date_qss)
        self._date_end_edit.setFixedWidth(96)

        hl.addWidget(self._date_start_edit)
        hl.addWidget(arr)
        hl.addWidget(self._date_end_edit)
        hl.addStretch()

        quick_qss = f"""
            QPushButton{{background:transparent;border:1px solid {BORDER_DEF};
                color:{TXT_SECOND};font-size:11px;padding:3px 10px;border-radius:4px;}}
            QPushButton:hover{{background:{BG_HOVER};color:{TXT_PRIMARY};}}
            QPushButton:checked{{background:{TXT_ACCENT};border-color:{TXT_ACCENT};color:white;}}
        """
        self._quick_btns: list[tuple[QPushButton, int]] = []
        for label, months in [("3m", 3), ("6m", 6), ("1a", 12), ("Tudo", 0)]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(quick_qss)
            btn.clicked.connect(lambda _c, m=months, b=btn: self._set_quick_range(m, b))
            hl.addWidget(btn)
            self._quick_btns.append((btn, months))
        self._quick_btns[2][0].setChecked(True)  # "1a" default

        self._date_start_edit.dateChanged.connect(self._on_date_changed)
        self._date_end_edit.dateChanged.connect(self._on_date_changed)
        return bar

    # ── Chart cards ───────────────────────────────────────────────────────────

    def _make_chart_card(
        self, title: str, subtitle: str,
        fig_attr: str, canvas_attr: str,
        export_fn,
    ) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame{{background:{BG_SURFACE};border:1px solid {BORDER_SUB};border-radius:12px;}}
        """)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(18, 12, 18, 12)
        vl.setSpacing(8)

        hdr = QHBoxLayout()
        title_vl = QVBoxLayout()
        title_vl.setSpacing(2)

        tlbl = QLabel(title)
        tlbl.setStyleSheet(f"color:{TXT_PRIMARY};font-size:14px;font-weight:600;"
                           f"background:transparent;border:none;")
        sublbl = QLabel(subtitle)
        sublbl.setStyleSheet(f"color:{TXT_SECOND};font-size:11px;"
                             f"background:transparent;border:none;")
        title_vl.addWidget(tlbl)
        title_vl.addWidget(sublbl)
        hdr.addLayout(title_vl, stretch=1)

        exp_btn = QPushButton("Exportar CSV")
        exp_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;border:1px solid {BORDER_DEF};
                color:{TXT_SECOND};font-size:10px;padding:3px 10px;border-radius:4px;}}
            QPushButton:hover{{background:{BG_HOVER};color:{TXT_PRIMARY};}}
        """)
        exp_btn.clicked.connect(export_fn)
        hdr.addWidget(exp_btn)
        vl.addLayout(hdr)

        fig = Figure(facecolor=BG_SURFACE)
        canvas = _Canvas(fig)
        setattr(self, fig_attr,    fig)
        setattr(self, canvas_attr, canvas)
        vl.addWidget(canvas)
        return card

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _filter_receptor_list(self, text: str) -> None:
        low = text.lower()
        for i in range(self._receptor_list.count()):
            item = self._receptor_list.item(i)
            item.setHidden(bool(low and low not in item.text().lower()))

    def _set_quick_range(self, months: int, clicked: QPushButton) -> None:
        for btn, _ in self._quick_btns:
            btn.setChecked(btn is clicked)
        today = QDate.currentDate()
        self._date_start_edit.blockSignals(True)
        self._date_end_edit.blockSignals(True)
        if months == 0:
            if not self._df_consents.empty:
                mn = self._df_consents["date"].min()
                self._date_start_edit.setDate(QDate(int(mn.year), int(mn.month), int(mn.day)))
            else:
                self._date_start_edit.setDate(today.addYears(-5))
        else:
            self._date_start_edit.setDate(today.addMonths(-months))
        self._date_end_edit.setDate(today)
        self._date_start_edit.blockSignals(False)
        self._date_end_edit.blockSignals(False)
        self._draw_charts()

    def _on_date_changed(self) -> None:
        for btn, _ in self._quick_btns:
            btn.setChecked(False)
        self._draw_charts()

    def _on_status_changed(self, _btn, checked: bool) -> None:
        if checked:
            self._draw_chart2()
            self._draw_chart3()

    def _on_normalize_changed(self, _: bool) -> None:
        self._draw_chart2()
        self._draw_chart3()

    # ── Data ─────────────────────────────────────────────────────────────────

    def set_db_path(self, path: Path) -> None:
        self._db_path = path
        self.load_data()

    def load_data(self) -> None:
        if not self._db_path.exists():
            self._show_empty_charts("Banco não encontrado.\nExecute a coleta primeiro.")
            return
        try:
            con = sqlite3.connect(str(self._db_path))
            try:
                self._df_consents = pd.read_sql(
                    "SELECT date, receptor, total FROM unique_consents",
                    con, parse_dates=["date"],
                )
            except Exception:
                self._df_consents = pd.DataFrame()
            try:
                self._df_api = pd.read_sql(
                    "SELECT date, receptor, api, status, total FROM api_requests",
                    con, parse_dates=["date"],
                )
            except Exception:
                self._df_api = pd.DataFrame()
            con.close()
        except Exception as exc:
            self._show_empty_charts(f"Erro ao ler banco:\n{exc}")
            return

        self._receptor_colors = self._build_color_map()
        self._delegate.update_colors(self._receptor_colors)
        self._populate_receptor_list()
        self._draw_charts()

    def _build_color_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        used: set[str] = set()
        fb_idx = 0
        receptors = list(self._df_consents["receptor"].unique()) if not self._df_consents.empty else []
        for r in receptors:
            style = _brand_style(r)
            if style:
                result[r] = style[0]
                used.add(style[0])
            else:
                while fb_idx < len(_FALLBACK_COLORS) and _FALLBACK_COLORS[fb_idx] in used:
                    fb_idx += 1
                c = _FALLBACK_COLORS[fb_idx % len(_FALLBACK_COLORS)]
                used.add(c)
                fb_idx += 1
                result[r] = c
        return result

    def _populate_receptor_list(self) -> None:
        self._receptor_list.blockSignals(True)
        prev = {it.text() for it in self._receptor_list.selectedItems()}
        self._receptor_list.clear()
        self._receptor_list.addItem("Top 10 receptores")
        if not self._df_consents.empty:
            tops = (
                self._df_consents.groupby("receptor")["total"]
                .sum().sort_values(ascending=False).index.tolist()
            )
            self._receptor_list.addItems(tops)
        self._receptor_count_lbl.setText(str(self._receptor_list.count() - 1))
        restored = False
        if prev:
            for i in range(self._receptor_list.count()):
                item = self._receptor_list.item(i)
                if item.text() in prev:
                    item.setSelected(True)
                    restored = True
        if not restored:
            self._receptor_list.item(0).setSelected(True)
        self._receptor_list.blockSignals(False)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _date_range(self):
        return (
            self._date_start_edit.date().toPyDate(),
            self._date_end_edit.date().toPyDate(),
        )

    def _filter_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "date" not in df.columns:
            return df
        start, end = self._date_range()
        try:
            mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
            return df[mask]
        except Exception:
            return df

    def _selected_receptors(self) -> list[str] | None:
        sel = [it.text() for it in self._receptor_list.selectedItems()]
        if not sel or "Top 10 receptores" in sel:
            return None
        return sel

    def _top10_with_bradesco(self, df: pd.DataFrame) -> list[str]:
        if df.empty:
            return []
        totals = df.groupby("receptor")["total"].sum().sort_values(ascending=False)
        top10  = totals.nlargest(10).index.tolist()
        for r in totals.index:
            if "bradesco" in r.lower() and r not in top10:
                top10 = top10[:9] + [r]
                break
        return top10

    def _plot_styles(self, receptors: list[str]) -> dict[str, tuple[str, float]]:
        result: dict[str, tuple[str, float]] = {}
        used: set[str] = set()
        fb_idx = 0
        for r in receptors:
            style = _brand_style(r)
            if style:
                result[r] = style
                used.add(style[0])
            else:
                while fb_idx < len(_FALLBACK_COLORS) and _FALLBACK_COLORS[fb_idx] in used:
                    fb_idx += 1
                c = _FALLBACK_COLORS[fb_idx % len(_FALLBACK_COLORS)]
                used.add(c)
                fb_idx += 1
                result[r] = (c, 1.6)
        return result

    def _status_filter(self) -> int | None:
        return [200, 500, None][self._status_group.checkedId()]

    def _normalize(self) -> bool:
        return self._normalize_toggle.isChecked()

    def _consent_totals(self) -> pd.Series:
        df = self._filter_df(self._df_consents)
        if df.empty:
            return pd.Series(dtype=float)
        return df.groupby("receptor")["total"].sum()

    # ── Charts ────────────────────────────────────────────────────────────────

    def _draw_charts(self) -> None:
        self._draw_chart1()
        self._draw_chart2()
        self._draw_chart3()

    def _draw_chart1(self) -> None:
        self._fig1.clear()
        ax      = self._fig1.add_subplot(111)
        df_all  = self._filter_df(self._df_consents)

        if df_all.empty:
            ax.text(0.5, 0.5, "Sem dados de consentimentos",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas1.draw()
            return

        sel       = self._selected_receptors()
        receptors = self._top10_with_bradesco(df_all) if sel is None else sel
        df        = df_all[df_all["receptor"].isin(receptors)]

        if df.empty:
            ax.text(0.5, 0.5, "Sem dados para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas1.draw()
            return

        styles = self._plot_styles(receptors)
        for receptor, grp in df.groupby("receptor"):
            color, lw = styles.get(receptor, (TXT_SECOND, 1.6))
            grp = grp.sort_values("date")
            ax.plot(
                grp["date"], grp["total"],
                marker="o", markersize=2.5, linewidth=lw,
                color=color, label=receptor[:30], alpha=0.92,
                zorder=3 if lw > 1.6 else 2,
            )

        ax.set_ylim(bottom=0)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b/%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        self._fig1.autofmt_xdate(rotation=30, ha="right")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_number))
        ax.set_ylabel("Consentimentos únicos", fontsize=8)
        ax.grid(True, axis="y", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(
            fontsize=7, ncol=min(len(receptors), 5),
            loc="upper center", bbox_to_anchor=(0.5, -0.28),
            framealpha=0.8, borderaxespad=0,
        )
        self._fig1.tight_layout(rect=[0, 0.18, 1, 1])
        self._canvas1.draw()

    def _draw_chart2(self) -> None:
        self._fig2.clear()
        ax     = self._fig2.add_subplot(111)
        df_all = self._filter_df(self._df_api)

        if df_all.empty:
            ax.text(0.5, 0.5, "Sem dados de chamadas de API",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas2.draw()
            return

        status = self._status_filter()
        df = df_all[~df_all["api"].isin(EXCLUDED_APIS | {RESOURCES_API})].copy()
        if status is not None:
            df = df[df["status"] == status]

        if df.empty:
            ax.text(0.5, 0.5, "Sem dados para os filtros selecionados",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas2.draw()
            return

        sel = self._selected_receptors()
        if sel is None:
            base = self._filter_df(self._df_consents) if not self._df_consents.empty else df
            top_receptors = self._top10_with_bradesco(base)
            top_receptors = [r for r in top_receptors if r in df["receptor"].values]
        else:
            top_receptors = sel

        df = df[df["receptor"].isin(top_receptors)]
        if df.empty:
            ax.text(0.5, 0.5, "Sem dados de API para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas2.draw()
            return

        available_apis = set(df["api"].unique())
        ordered_cols   = [a for a in _ORDERED_APIS if a in available_apis]

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
        im = ax.imshow(data_log, aspect="auto", cmap="Blues",
                       interpolation="nearest", vmin=0)

        ax.set_xticks(range(len(ordered_cols)))
        ax.set_xticklabels([_API_SHORT.get(c, c) for c in ordered_cols],
                           fontsize=7, ha="center")
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([r[:26] for r in pivot.index], fontsize=7)

        # Group separators and labels
        col_idx = 0
        for grupo, apis in API_GROUPS.items():
            cols = [a for a in apis if a in available_apis]
            if not cols:
                continue
            span   = len(cols)
            center = col_idx + (span - 1) / 2
            ax.text(center, -1.4, grupo,
                    ha="center", va="bottom", fontsize=7, color=TXT_SECOND,
                    transform=ax.get_xaxis_transform())
            if col_idx > 0:
                ax.axvline(col_idx - 0.5, color=BORDER_DEF, lw=0.8, zorder=5)
            col_idx += span

        # Cell annotations
        vmax = data_log.max() or 1
        for i in range(len(pivot.index)):
            for j in range(len(ordered_cols)):
                val = data[i, j]
                if val > 0:
                    txt = f"{val:.2f}" if self._normalize() else _fmt_number(val)
                    brightness = data_log[i, j] / vmax
                    cell_color = BG_BASE if brightness > 0.55 else TXT_PRIMARY
                    ax.text(j, i, txt, ha="center", va="center",
                            fontsize=6, color=cell_color)

        cb_label = "Chamadas / consentimento (log)" if self._normalize() else "Total (escala log)"
        cb = self._fig2.colorbar(im, ax=ax, fraction=0.018, pad=0.02)
        cb.set_label(cb_label, color=TXT_MUTED, fontsize=8)
        cb.ax.yaxis.set_tick_params(color=TXT_MUTED, labelsize=7)
        plt.setp(cb.ax.yaxis.get_ticklabels(), color=TXT_MUTED)

        self._fig2.tight_layout()
        self._canvas2.draw()

    def _draw_chart3(self) -> None:
        self._fig3.clear()
        ax     = self._fig3.add_subplot(111)
        df_all = self._filter_df(self._df_api)

        if df_all.empty:
            ax.text(0.5, 0.5, "Sem dados de resources",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas3.draw()
            return

        status = self._status_filter()
        df = df_all[df_all["api"] == RESOURCES_API].copy()
        if status is not None:
            df = df[df["status"] == status]

        if df.empty:
            ax.text(0.5, 0.5, "Sem dados de resources para o filtro selecionado",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
            self._canvas3.draw()
            return

        sel = self._selected_receptors()
        if sel is None:
            base = self._filter_df(self._df_consents) if not self._df_consents.empty else df
            top_receptors = self._top10_with_bradesco(base)
            top_receptors = [r for r in top_receptors if r in df["receptor"].values]
        else:
            top_receptors = [r for r in sel if r in df["receptor"].values]

        df = df[df["receptor"].isin(top_receptors)]
        if df.empty:
            ax.text(0.5, 0.5, "Sem dados de resources para os receptores selecionados",
                    ha="center", va="center", transform=ax.transAxes, color=TXT_MUTED)
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

        styles     = self._plot_styles(list(totals.index))
        bar_colors = [styles.get(r, (TXT_SECOND, 1.6))[0] for r in totals.index]
        bars       = ax.barh(range(len(totals)), values,
                             color=bar_colors, height=0.62, alpha=0.88)
        ax.set_yticks(range(len(totals)))
        ax.set_yticklabels([r[:28] for r in totals.index], fontsize=7)
        ax.invert_yaxis()

        fmt = (lambda x, _: f"{x:.2f}") if self._normalize() else _fmt_number
        ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt))
        ax.set_xlabel(
            "Chamadas / consentimento único" if self._normalize() else "Total de chamadas",
            fontsize=8,
        )
        ax.grid(True, axis="x", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        x_max = max(values.max(), 1)
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_width() + x_max * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:.2f}" if self._normalize() else _fmt_number(val),
                    va="center", fontsize=7, color=TXT_SECOND,
                )
        self._fig3.tight_layout()
        self._canvas3.draw()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_consents(self) -> None:
        df = self._filter_df(self._df_consents)
        if df.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Consentimentos", "consentimentos.csv", "CSV (*.csv)",
        )
        if path:
            df.to_csv(path, index=False)

    def _export_api(self) -> None:
        df = self._filter_df(self._df_api)
        df = df[~df["api"].isin(EXCLUDED_APIS | {RESOURCES_API})]
        if df.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Chamadas de API", "api_requests.csv", "CSV (*.csv)",
        )
        if path:
            df.to_csv(path, index=False)

    def _export_resources(self) -> None:
        df = self._filter_df(self._df_api)
        df = df[df["api"] == RESOURCES_API]
        if df.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Resources", "resources.csv", "CSV (*.csv)",
        )
        if path:
            df.to_csv(path, index=False)

    def _show_empty_charts(self, msg: str) -> None:
        for fig, canvas in (
            (self._fig1, self._canvas1),
            (self._fig2, self._canvas2),
            (self._fig3, self._canvas3),
        ):
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, msg, ha="center", va="center",
                    transform=ax.transAxes, fontsize=10, color=TXT_MUTED)
            canvas.draw()

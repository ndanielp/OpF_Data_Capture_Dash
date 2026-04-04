"""
server.py — Servidor Flask completo para o Open Finance Brasil.

Expõe:
  GET  /                       → gui/index.html  (SPA)
  GET  /api/stats
  GET  /api/receptors
  GET  /api/consents
  GET  /api/api-requests
  GET  /api/resources
  POST /api/db                 → troca o caminho do banco
  POST /api/collect/start      → inicia coleta
  POST /api/collect/stop       → para coleta
  GET  /api/collect/status     → snapshot do estado
  GET  /api/collect/stream     → SSE de progresso
"""

import json
import logging
import queue
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, Response, jsonify, request, send_from_directory

# ── Logging ────────────────────────────────────────────────────────────────────
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# ── Estado global ──────────────────────────────────────────────────────────────
_db_path: Path = Path("data/consents.db")
_DATA_DIR = (Path(__file__).parent / "data").resolve()
_runner: "CollectionRunner | None" = None
_runner_lock = threading.Lock()

# ── Constantes de dados ────────────────────────────────────────────────────────
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
_ORDERED_APIS: list[str] = [a for apis in API_GROUPS.values() for a in apis]

_API_LABELS: dict[str, str] = {
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

_BRAND = [
    ("bradesco",        "#CC092F"),
    ("nubank",          "#8B1CF0"),
    ("itaú",            "#EC7000"),
    ("itau",            "#EC7000"),
    ("santander",       "#EC0000"),
    ("caixa",           "#005CA9"),
    ("mercado pago",    "#00A9E0"),
    ("picpay",          "#21C25E"),
    ("banco do brasil", "#F9A800"),
    ("belvo",           "#4A9EFF"),
    ("recargapay",      "#7B68EE"),
    ("shopee",          "#FF5722"),
    ("pagseguro",       "#34B7F1"),
    ("cloudwalk",       "#9C27B0"),
]
_FALLBACK_COLORS = [
    "#4A9EFF", "#7B68EE", "#FF5722", "#34B7F1",
    "#9C27B0", "#F9E68C", "#cba6f7", "#f38ba8",
    "#fab387", "#94e2d5", "#b4befe", "#a6e3a1",
]


# ── Helpers de cor ─────────────────────────────────────────────────────────────

def _brand_color(receptor: str) -> str | None:
    name = receptor.lower()
    for key, color in _BRAND:
        if key in name:
            return color
    return None


def _build_color_map(receptors: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set()
    fb_idx = 0
    for r in receptors:
        c = _brand_color(r)
        if c:
            result[r] = c
            used.add(c)
        else:
            while fb_idx < len(_FALLBACK_COLORS) and _FALLBACK_COLORS[fb_idx] in used:
                fb_idx += 1
            c = _FALLBACK_COLORS[fb_idx % len(_FALLBACK_COLORS)]
            used.add(c)
            fb_idx += 1
            result[r] = c
    return result


# ── Leitura do banco ───────────────────────────────────────────────────────────

def _load_consents() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(_db_path), timeout=5.0)
        df = pd.read_sql("SELECT date, receptor, total FROM unique_consents",
                         con, parse_dates=["date"])
        con.close()
        return df
    except Exception:
        logger.exception("Erro ao carregar consentimentos do banco")
        return pd.DataFrame()


def _load_api() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(_db_path), timeout=5.0)
        df = pd.read_sql("SELECT date, receptor, api, status, total FROM api_requests",
                         con, parse_dates=["date"])
        con.close()
        return df
    except Exception:
        logger.exception("Erro ao carregar api_requests do banco")
        return pd.DataFrame()


# ── Helpers de filtragem ───────────────────────────────────────────────────────

def _parse_date(s: str | None, fallback: date) -> date:
    if not s:
        return fallback
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback


def _filter_by_date(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df[mask]


def _parse_receptors(param: str | None) -> list[str] | None:
    if not param:
        return None
    parts = [r.strip() for r in param.split(",") if r.strip()]
    return parts or None


def _top10_with_bradesco(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    totals = df.groupby("receptor")["total"].sum().sort_values(ascending=False)
    top10 = totals.nlargest(10).index.tolist()
    for r in totals.index:
        if "bradesco" in r.lower() and r not in top10:
            top10 = top10[:9] + [r]
            break
    return top10


def _fmt_number(x: float) -> str:
    if x >= 1_000_000_000:
        return f"{x / 1_000_000_000:.1f}B"
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}k"
    return str(int(x))


# ══════════════════════════════════════════════════════════════════════════════
# CollectionRunner
# ══════════════════════════════════════════════════════════════════════════════

class _Cancelled(Exception):
    pass


class CollectionRunner(threading.Thread):
    """Executa a coleta em background e publica eventos SSE para subscribers."""

    def __init__(
        self,
        dates: list[str],
        db_path: Path,
        workers: int,
        skip_consents: bool,
        skip_api: bool,
    ) -> None:
        super().__init__(daemon=True, name="collection-runner")
        self.dates         = dates
        self.db_path       = db_path
        self.workers       = workers
        self.skip_consents = skip_consents
        self.skip_api      = skip_api

        self._stop_event   = threading.Event()
        self._subs_lock    = threading.Lock()
        self._subscribers: list[queue.Queue] = []

        # Estado público (lido por /api/collect/status)
        self.state = {
            "running": True,
            "phase":   "",
            "states":  {},
            "elapsed": 0.0,
            "msg":     "Iniciando…",
            "n_consents": 0,
            "n_api":   0,
            "error":   None,
            "finished": False,
        }

    # ── SSE pub/sub ────────────────────────────────────────────────────────────

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._subs_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._subs_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def _publish(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False)
        with self._subs_lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass

    # ── Control ────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        self._stop_event.set()

    # ── Execution ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            self._run()
        except _Cancelled:
            self.state["running"] = False
            self.state["msg"] = "Coleta interrompida."
            self._publish({"type": "stopped"})
        except Exception as exc:
            self.state["running"] = False
            self.state["error"] = str(exc)
            self._publish({"type": "error", "msg": str(exc)})
        finally:
            self.state["running"] = False
            self.state["finished"] = True

    def _run(self) -> None:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from build_consents_db     import run as run_consents
        from build_api_requests_db import run as run_api_requests

        n_consents = 0
        n_api      = 0

        # ── Etapa 1: Consentimentos ───────────────────────────────────────────
        if not self.skip_consents:
            self._emit_status("Carregando lista de receptores…")

            def cb_consents(states, elapsed):
                if self._stop_event.is_set():
                    raise _Cancelled
                self.state.update(phase="consents", states=states, elapsed=elapsed)
                self._publish({"type": "state", "phase": "consents",
                               "states": states, "elapsed": elapsed})

            n_consents = run_consents(
                self.dates, self.db_path, self.workers,
                on_state_update=cb_consents,
            )
            self.state["n_consents"] = n_consents
            self._publish({"type": "phase_complete", "phase": "consents", "count": n_consents})

        if self._stop_event.is_set():
            raise _Cancelled

        # ── Receptores ativos ─────────────────────────────────────────────────
        start_date = self.dates[0][:10]
        end_date   = self.dates[-1][:10]
        con = sqlite3.connect(str(self.db_path), timeout=5.0)
        rows = con.execute("""
            SELECT DISTINCT receptor, receptor_uuid
            FROM unique_consents
            WHERE total > 0 AND date BETWEEN ? AND ?
            ORDER BY receptor
        """, (start_date, end_date)).fetchall()
        con.close()
        active = [{"label": r[0], "value": r[1]} for r in rows]

        # ── Etapa 2: API Requests ─────────────────────────────────────────────
        if not self.skip_api:
            if not active:
                self._emit_status("Nenhum receptor com consentimentos — etapa API ignorada.")
            else:
                self._emit_status(f"{len(active)} receptores ativos — iniciando API requests…")

                def cb_api(states, elapsed):
                    if self._stop_event.is_set():
                        raise _Cancelled
                    self.state.update(phase="api", states=states, elapsed=elapsed)
                    self._publish({"type": "state", "phase": "api",
                                   "states": states, "elapsed": elapsed})

                n_api = run_api_requests(
                    self.dates, active, self.db_path,
                    workers=self.workers,
                    on_state_update=cb_api,
                )
                self.state["n_api"] = n_api
                self._publish({"type": "phase_complete", "phase": "api", "count": n_api})

        self._publish({"type": "all_complete", "n_consents": n_consents, "n_api": n_api})

    def _emit_status(self, msg: str) -> None:
        self.state["msg"] = msg
        self._publish({"type": "status", "msg": msg})


# ══════════════════════════════════════════════════════════════════════════════
# Flask app
# ══════════════════════════════════════════════════════════════════════════════

_GUI_DIR = Path(__file__).parent / "gui"
app = Flask(__name__, static_folder=None)


# ── Static ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(_GUI_DIR), "index.html")


# ── DB ─────────────────────────────────────────────────────────────────────────

@app.route("/api/db", methods=["POST"])
def set_db_endpoint():
    global _db_path
    path = (request.json or {}).get("path", "")
    if not path:
        return jsonify({"error": "path required"}), 400
    resolved = Path(path).resolve()
    if not str(resolved).startswith(str(_DATA_DIR)):
        return jsonify({"error": "Caminho fora do diretório permitido"}), 400
    if resolved.suffix.lower() != ".db":
        return jsonify({"error": "Apenas arquivos .db são aceitos"}), 400
    _db_path = resolved
    return jsonify({"ok": True, "db": _db_path.name})


# ── Dashboard endpoints ────────────────────────────────────────────────────────

@app.route("/api/stats")
def stats_endpoint():
    try:
        con = sqlite3.connect(str(_db_path), timeout=5.0)
        n_c  = con.execute("SELECT count(*) FROM unique_consents").fetchone()[0]
        n_a  = con.execute("SELECT count(*) FROM api_requests").fetchone()[0]
        last = con.execute("SELECT MAX(date) FROM unique_consents").fetchone()[0] or ""
        con.close()
        return jsonify({"db": _db_path.name, "consents": n_c,
                        "api_requests": n_a, "last_updated": last[:10]})
    except Exception:
        logger.exception("Erro ao consultar stats do banco")
        return jsonify({"db": _db_path.name, "consents": 0,
                        "api_requests": 0, "last_updated": ""})


@app.route("/api/receptors")
def receptors_endpoint():
    df = _load_consents()
    if df.empty:
        return jsonify([])
    all_recs = (df.groupby("receptor")["total"].sum()
                .sort_values(ascending=False).index.tolist())
    colors = _build_color_map(all_recs)
    top10  = set(_top10_with_bradesco(df))
    return jsonify([
        {"label": r, "color": colors.get(r, "#4A5270"), "top": r in top10}
        for r in all_recs
    ])


@app.route("/api/consents")
def consents_endpoint():
    today = date.today()
    start = _parse_date(request.args.get("start"), today - timedelta(days=365))
    end   = _parse_date(request.args.get("end"),   today)
    sel   = _parse_receptors(request.args.get("receptors"))

    df = _load_consents()
    df = _filter_by_date(df, start, end)
    if df.empty:
        return jsonify({"labels": [], "datasets": []})

    receptors = sel if sel else _top10_with_bradesco(df)
    df = df[df["receptor"].isin(receptors)]
    if df.empty:
        return jsonify({"labels": [], "datasets": []})

    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby(["month", "receptor"])["total"].sum().reset_index()
    all_months = sorted(monthly["month"].unique())
    labels = [str(m) for m in all_months]
    colors = _build_color_map(receptors)

    datasets = []
    for r in receptors:
        sub  = monthly[monthly["receptor"] == r].set_index("month")
        data = [int(sub["total"].get(m, 0)) for m in all_months]
        c    = colors.get(r, "#4A9EFF")
        datasets.append({
            "label": r, "data": data,
            "borderColor": c, "backgroundColor": c + "18",
            "borderWidth": 2, "pointRadius": 3, "pointHoverRadius": 5,
            "pointBackgroundColor": c, "pointBorderColor": "transparent",
            "tension": 0.35, "fill": False,
        })
    return jsonify({"labels": labels, "datasets": datasets})


@app.route("/api/api-requests")
def api_requests_endpoint():
    today = date.today()
    start     = _parse_date(request.args.get("start"), today - timedelta(days=365))
    end       = _parse_date(request.args.get("end"),   today)
    sel       = _parse_receptors(request.args.get("receptors"))
    status    = request.args.get("status", "all")
    normalize = request.args.get("normalize", "0") == "1"
    empty = {"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0}

    df_api = _load_api()
    df_api = _filter_by_date(df_api, start, end)
    if df_api.empty:
        return jsonify(empty)

    df = df_api[~df_api["api"].isin(EXCLUDED_APIS | {RESOURCES_API})].copy()
    if status == "200":
        df = df[df["status"] == 200]
    elif status == "500":
        df = df[df["status"] == 500]
    if df.empty:
        return jsonify(empty)

    if sel:
        top_recs = [r for r in sel if r in df["receptor"].values]
    else:
        base = _filter_by_date(_load_consents(), start, end)
        top_recs = _top10_with_bradesco(base if not base.empty else df)
        top_recs = [r for r in top_recs if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_recs)]
    if df.empty:
        return jsonify(empty)

    available = set(df["api"].unique())
    ordered   = [a for a in _ORDERED_APIS if a in available]
    pivot = (df.groupby(["receptor", "api"])["total"]
               .sum().unstack(fill_value=0)
               .reindex(index=top_recs, columns=ordered).fillna(0))
    data = pivot.values.astype(float)

    if normalize:
        ct = _filter_by_date(_load_consents(), start, end)
        ct = ct.groupby("receptor")["total"].sum() if not ct.empty else pd.Series(dtype=float)
        for i, rec in enumerate(pivot.index):
            n = float(ct.get(rec, 0))
            if n > 0:
                data[i] /= n

    groups_info = []
    col_idx = 0
    for grupo, apis in API_GROUPS.items():
        cols = [a for a in apis if a in available]
        if not cols:
            continue
        groups_info.append({"label": grupo, "start": col_idx, "span": len(cols)})
        col_idx += len(cols)

    return jsonify({
        "groups":    groups_info,
        "apis":      [{"id": a, "label": _API_LABELS.get(a, a)} for a in ordered],
        "receptors": list(pivot.index),
        "values":    data.tolist(),
        "max_val":   float(data.max()) if data.size > 0 else 0,
        "normalize": normalize,
    })


@app.route("/api/resources")
def resources_endpoint():
    today = date.today()
    start     = _parse_date(request.args.get("start"), today - timedelta(days=365))
    end       = _parse_date(request.args.get("end"),   today)
    sel       = _parse_receptors(request.args.get("receptors"))
    status    = request.args.get("status", "all")
    normalize = request.args.get("normalize", "0") == "1"
    empty = {"receptors": [], "values": [], "colors": []}

    df_api = _load_api()
    df_api = _filter_by_date(df_api, start, end)
    if df_api.empty:
        return jsonify(empty)

    df = df_api[df_api["api"] == RESOURCES_API].copy()
    if status == "200":
        df = df[df["status"] == 200]
    elif status == "500":
        df = df[df["status"] == 500]
    if df.empty:
        return jsonify(empty)

    if sel:
        top_recs = [r for r in sel if r in df["receptor"].values]
    else:
        base = _filter_by_date(_load_consents(), start, end)
        top_recs = _top10_with_bradesco(base if not base.empty else df)
        top_recs = [r for r in top_recs if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_recs)]
    if df.empty:
        return jsonify(empty)

    totals = df.groupby("receptor")["total"].sum().reindex(top_recs).fillna(0)
    values = totals.values.astype(float)

    if normalize:
        ct = _filter_by_date(_load_consents(), start, end)
        ct = ct.groupby("receptor")["total"].sum() if not ct.empty else pd.Series(dtype=float)
        for i, rec in enumerate(totals.index):
            n = float(ct.get(rec, 0))
            if n > 0:
                values[i] /= n

    cmap = _build_color_map(list(totals.index))
    return jsonify({
        "receptors": list(totals.index),
        "values":    values.tolist(),
        "colors":    [cmap.get(r, "#4A9EFF") for r in totals.index],
        "normalize": normalize,
    })


# ── Collection endpoints ───────────────────────────────────────────────────────

@app.route("/api/collect/start", methods=["POST"])
def collect_start():
    global _runner
    with _runner_lock:
        if _runner and _runner.state["running"]:
            return jsonify({"error": "Coleta já em andamento"}), 409

    body          = request.json or {}
    period        = body.get("period", "3m")
    custom_start  = body.get("start")
    custom_end    = body.get("end")

    # Valida workers: inteiro entre 1 e 10
    try:
        workers = int(body.get("workers", 3))
    except (ValueError, TypeError):
        return jsonify({"error": "Parâmetro 'workers' inválido"}), 400
    workers = max(1, min(workers, 10))

    skip_consents = bool(body.get("skip_consents", False))
    skip_api      = bool(body.get("skip_api", False))

    # Valida formato das datas customizadas
    if period == "custom":
        try:
            if custom_start:
                datetime.strptime(custom_start, "%Y-%m-%d")
            if custom_end:
                datetime.strptime(custom_end, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Formato de data inválido (esperado YYYY-MM-DD)"}), 400

    # Resolve datas
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from utils import resolve_date_range, fridays_between
    from datetime import timezone

    period_map = {"1m": 1, "3m": 3, "6m": 6}
    if period == "custom" and custom_start:
        dates = resolve_date_range(months=None, start=custom_start, end=custom_end)
    elif period in period_map:
        dates = resolve_date_range(months=period_map[period], start=None, end=None)
    else:  # "all"
        today = datetime.now(timezone.utc)
        dates = resolve_date_range(months=24, start=None, end=None)

    if not dates:
        return jsonify({"error": "Nenhuma sexta-feira no período"}), 400

    with _runner_lock:
        _runner = CollectionRunner(dates, _db_path, workers, skip_consents, skip_api)
        _runner.start()

    return jsonify({"ok": True, "dates": len(dates)})


@app.route("/api/collect/stop", methods=["POST"])
def collect_stop():
    global _runner
    with _runner_lock:
        if _runner and _runner.state["running"]:
            _runner.stop()
            return jsonify({"ok": True})
    return jsonify({"ok": True, "msg": "Nenhuma coleta em andamento"})


@app.route("/api/collect/status")
def collect_status():
    global _runner
    with _runner_lock:
        if _runner is None:
            return jsonify({"running": False, "finished": False})
        # Serializa states (remove chaves não-JSON-safe)
        s = dict(_runner.state)
        # combos keys are tuples → convert to str
        safe_states = {}
        for wid, ws in s.get("states", {}).items():
            ws2 = dict(ws)
            if "combos" in ws2:
                ws2["combos"] = {f"{a}:{st}": v for (a, st), v in ws2["combos"].items()}
            safe_states[str(wid)] = ws2
        s["states"] = safe_states
        return jsonify(s)


@app.route("/api/collect/stream")
def collect_stream():
    """SSE endpoint. Cada conexão recebe uma queue dedicada."""

    def generate():
        global _runner
        # Subscreve ao runner atual (se existir)
        with _runner_lock:
            r = _runner
        q = r.subscribe() if r else None

        try:
            while True:
                # Keepalive ping a cada 15 s
                try:
                    if q:
                        data = q.get(timeout=15)
                        yield f"data: {data}\n\n"
                        # Após terminal event, fecha stream
                        try:
                            ev = json.loads(data)
                            if ev.get("type") in ("all_complete", "error", "stopped"):
                                break
                        except Exception:
                            pass
                    else:
                        yield "data: {\"type\":\"ping\"}\n\n"
                        # Verifica se runner foi criado
                        time.sleep(1)
                        with _runner_lock:
                            r = _runner
                        if r and q is None:
                            q = r.subscribe()
                except queue.Empty:
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            if q and r:
                r.unsubscribe(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ── Inicialização ──────────────────────────────────────────────────────────────

_started = False
_start_lock = threading.Lock()


def start(db_path: str | Path = "data/consents.db", port: int = 5432) -> None:
    """Inicia o servidor Flask em thread daemon. Idempotente."""
    global _db_path, _started
    with _start_lock:
        if _started:
            _db_path = Path(db_path)
            return
        _db_path = Path(db_path)
        _started = True

    t = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port,
                               debug=False, use_reloader=False, threaded=True),
        daemon=True,
        name="flask-server",
    )
    t.start()

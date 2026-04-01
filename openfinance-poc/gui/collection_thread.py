"""
collection_thread.py — QThread que executa a coleta em background.

Chama run_consents() e run_api_requests() diretamente (sem subprocess),
interceptando o callback on_state_update para emitir sinais Qt com o
estado de cada worker em tempo real.
"""

import sqlite3
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

BASE_DIR = Path(__file__).parent.parent  # openfinance-poc/


class CollectionThread(QThread):
    # (fase, states_dict, elapsed_segundos)
    state_updated  = pyqtSignal(str, object, float)
    # (fase, n_registros)
    phase_complete = pyqtSignal(str, int)
    # (n_consents, n_api)
    all_complete   = pyqtSignal(int, int)
    # mensagem de erro
    error_occurred = pyqtSignal(str)
    # mensagem informativa (ex: "Carregando receptores…")
    status_message = pyqtSignal(str)

    def __init__(
        self,
        dates: list[str],
        db_path: Path,
        workers: int,
        skip_consents: bool,
        skip_api: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.dates         = dates
        self.db_path       = db_path
        self.workers       = workers
        self.skip_consents = skip_consents
        self.skip_api      = skip_api

    # ── Execução principal ────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _run(self) -> None:
        from build_consents_db    import run as run_consents, open_db
        from build_api_requests_db import run as run_api_requests

        n_consents = 0
        n_api      = 0

        # ── Etapa 1: Consentimentos ───────────────────────────────────────────
        if not self.skip_consents:
            self.status_message.emit("Carregando lista de receptores…")

            def cb_consents(states, elapsed):
                self.state_updated.emit("consents", states, elapsed)

            n_consents = run_consents(
                self.dates, self.db_path, self.workers,
                on_state_update=cb_consents,
            )
            self.phase_complete.emit("consents", n_consents)

        # ── Receptores ativos ─────────────────────────────────────────────────
        start_date = self.dates[0][:10]
        end_date   = self.dates[-1][:10]

        con = sqlite3.connect(str(self.db_path))
        rows = con.execute("""
            SELECT DISTINCT receptor, receptor_uuid
            FROM unique_consents
            WHERE total > 0 AND date BETWEEN ? AND ?
            ORDER BY receptor
        """, (start_date, end_date)).fetchall()
        con.close()

        active_receptors = [{"label": r[0], "value": r[1]} for r in rows]

        # ── Etapa 2: API Requests ─────────────────────────────────────────────
        if not self.skip_api:
            if not active_receptors:
                self.status_message.emit(
                    "Nenhum receptor com consentimentos — etapa de API ignorada."
                )
            else:
                self.status_message.emit(
                    f"{len(active_receptors)} receptores ativos — iniciando API requests…"
                )

                def cb_api(states, elapsed):
                    self.state_updated.emit("api", states, elapsed)

                n_api = run_api_requests(
                    self.dates, active_receptors, self.db_path,
                    workers=self.workers,
                    on_state_update=cb_api,
                )
                self.phase_complete.emit("api", n_api)

        self.all_complete.emit(n_consents, n_api)

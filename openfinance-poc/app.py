"""
app.py — Open Finance Brasil — Web App
=======================================
Ponto de entrada da aplicação. Inicia o servidor Flask e abre o browser.

Uso:
  .venv/Scripts/python app.py
"""

import sys
import time
import webbrowser
from pathlib import Path

# Garante que imports relativos encontrem os módulos do projeto
sys.path.insert(0, str(Path(__file__).parent))

import server

_PORT = 5432
_DB   = Path(__file__).parent / "data" / "consents.db"


def main() -> None:
    server.start(_DB, port=_PORT)
    time.sleep(0.8)
    webbrowser.open(f"http://localhost:{_PORT}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

"""
main.py — Entry point CLI para OpF Data Loading Batch
=====================================================
Orquestra o pipeline de dados do Open Finance Brasil através da linha de comando.
Subcomandos:
  - run: Executa o pipeline de coleta
  - status: Verifica se existem arquivos csv na base de dados (em data/)
  - last-run: Mostra um resumo do último arquivo de log executado na raiz logs/
  - preview: Visualiza as últimas linhas de um CSV (consents ou api_requests)

Nota: o dashboard está em dashboard/ e roda separadamente via uvicorn ou Docker.
"""

import argparse
import sys
import pandas as pd
from pathlib import Path
from colorama import init, Fore, Style

# Adiciona o diretório atual ao path
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import config
from collector import run_collection, run_payment_initiation_collection

# Inicializa o colorama para cores no terminal Windows/Linux
init(autoreset=True)

def cmd_run(args):
    """Executa a coleta."""
    print(f"{Fore.CYAN}Iniciando coleta de dados Open Finance: {args.start_date} até {args.end_date}{Style.RESET_ALL}\n")
    if args.receptor_filter:
        print(f"{Fore.YELLOW}Filtro de receptores: {args.receptor_filter}{Style.RESET_ALL}\n")
    try:
        result = run_collection(
            start_date=args.start_date,
            end_date=args.end_date,
            workers=args.workers,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            receptor_filter=args.receptor_filter,
        )
        
        if "error" in result:
            print(f"\n{Fore.RED}Erro na execução:{Style.RESET_ALL} {result['error']}")
            sys.exit(1)
            
        print(f"\n{Fore.GREEN}=== Resumo da Execução ==={Style.RESET_ALL}")
        for key, value in result.items():
            print(f"  {Fore.YELLOW}{key}:{Style.RESET_ALL} {value}")
            
    except Exception as e:
        print(f"\n{Fore.RED}Exceção fatal:{Style.RESET_ALL} {str(e)}")
        sys.exit(1)

def cmd_run_pi(args):
    """Executa a coleta de Iniciação de Pagamentos (payment-initiation)."""
    print(f"{Fore.CYAN}Iniciando coleta Payment-Initiation: {args.start_date} até {args.end_date}{Style.RESET_ALL}\n")
    if args.receptor_filter:
        print(f"{Fore.YELLOW}Filtro de PISPs: {args.receptor_filter}{Style.RESET_ALL}\n")
    try:
        result = run_payment_initiation_collection(
            start_date=args.start_date,
            end_date=args.end_date,
            workers=args.workers,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            receptor_filter=args.receptor_filter,
        )

        if "error" in result:
            print(f"\n{Fore.RED}Erro na execução:{Style.RESET_ALL} {result['error']}")
            sys.exit(1)

        print(f"\n{Fore.GREEN}=== Resumo da Execução (payment-initiation) ==={Style.RESET_ALL}")
        for key, value in result.items():
            print(f"  {Fore.YELLOW}{key}:{Style.RESET_ALL} {value}")

    except Exception as e:
        print(f"\n{Fore.RED}Exceção fatal:{Style.RESET_ALL} {str(e)}")
        sys.exit(1)


def cmd_status(args):
    """Resume o estado atual dos dados."""
    print(f"{Fore.CYAN}Status Atual do Diretório de Dados{Style.RESET_ALL}\n")
    
    status = {
        "Data Directory": str(config.DATA_DIR),
        "Log Directory":  str(config.LOG_DIR),
    }

    for name, pk in [("consents.csv", "receptor_uuid"), ("api_requests.csv", "receptor_uuid")]:
        csv_path = config.DATA_DIR / name
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            date_min = str(df["date"].min()) if "date" in df.columns else "N/A"
            date_max = str(df["date"].max()) if "date" in df.columns else "N/A"
            receptors = int(df[pk].nunique()) if pk in df.columns else "N/A"
            
            print(f"{Fore.GREEN}{name}:{Style.RESET_ALL}")
            print(f"  Linhas Totais: {len(df)}")
            print(f"  Período:       {date_min} → {date_max}")
            print(f"  Receptores:    {receptors}")
        else:
            print(f"{Fore.RED}{name}:{Style.RESET_ALL} não existe")

    log_global = config.LOG_DIR / "_global"
    print(f"\n{Fore.CYAN}Execuções Recentes:{Style.RESET_ALL}")
    if log_global.exists():
        runs = sorted(log_global.glob("*.log"), reverse=True)
        if runs:
            for r in runs[:5]:
                print(f"  - {r.stem}")
        else:
            print("  Nenhum log global encontrado.")
    else:
        print("  Diretório log global não existe.")

def cmd_last_run(args):
    """Exibe as últimas linhas do último log."""
    log_dir = config.LOG_DIR / "_global"
    if not log_dir.exists():
        print(f"{Fore.RED}Erro:{Style.RESET_ALL} Nenhuma execução encontrada. O diretório {log_dir} não existe.")
        sys.exit(1)

    log_files = sorted(log_dir.glob("*.log"), reverse=True)
    if not log_files:
        print(f"{Fore.RED}Erro:{Style.RESET_ALL} Nenhum log encontrado em {log_dir}")
        sys.exit(1)

    latest = log_files[0]
    print(f"{Fore.CYAN}Último log:{Style.RESET_ALL} {latest.name}\n")
    
    try:
        lines = latest.read_text(encoding="utf-8").splitlines()
        for line in lines[-args.lines:]:
            print(line)
    except Exception as e:
        print(f"{Fore.RED}Erro lendo o log:{Style.RESET_ALL} {str(e)}")

def cmd_preview(args):
    """Exibe preview do CSV."""
    name_map = {
        "consents":        "consents.csv",
        "api_requests":    "api_requests.csv",
        "active_consents": "active_consents.csv",
    }
    name = name_map.get(args.dataset, f"{args.dataset}.csv")
    csv_path = config.DATA_DIR / name

    if not csv_path.exists():
        print(f"{Fore.RED}Erro:{Style.RESET_ALL} {name} ainda não existe em {config.DATA_DIR}.")
        sys.exit(1)

    try:
        df = pd.read_csv(csv_path)
        print(f"{Fore.CYAN}Preview de {name} ({args.rows} últimas linhas de {len(df)} totais):{Style.RESET_ALL}\n")
        # Mostrar usando pandas nativo para formatação fácil (tabular)
        if df.empty:
            print("Arquivo vazio.")
        else:
            print(df.tail(args.rows).to_string(index=False))
    except Exception as e:
        print(f"{Fore.RED}Erro exibindo CSV:{Style.RESET_ALL} {str(e)}")

def main():
    parser = argparse.ArgumentParser(
        description="CLI para Extração Lote (Batch) de Dados do Open Finance Brasil.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(title="Comandos", dest="command", required=True)

    # Sub-comando: run
    parser_run = subparsers.add_parser("run", help="Executa o processo completo de coleta.")
    parser_run.add_argument("--start-date", "-s", type=str, default="4w", help="Data de início (ex: '4w', '3m', 'YYYY-MM-DD').")
    parser_run.add_argument("--end-date", "-e", type=str, default="today", help="Data final (ex: 'today', 'YYYY-MM-DD').")
    parser_run.add_argument("--workers", "-w", type=int, default=1, help="Qtd de workers para processamento em paralelo.")
    parser_run.add_argument("--delay-min", type=float, default=3.0, help="Espera mínima aleatória entre bancos (s).")
    parser_run.add_argument("--delay-max", type=float, default=8.0, help="Espera máxima aleatória entre bancos (s).")
    parser_run.add_argument(
        "--receptor", "-r",
        dest="receptor_filter",
        nargs="+",
        metavar="NAME",
        default=None,
        help="Filtra receptores por nome (substring, case-insensitive). Ex: -r Bradesco Itau",
    )
    parser_run.set_defaults(func=cmd_run)

    # Sub-comando: run-pi (Payment Initiation)
    parser_pi = subparsers.add_parser(
        "run-pi",
        help="Coleta dados de Iniciação de Pagamentos (payment-initiation).",
    )
    parser_pi.add_argument("--start-date", "-s", type=str, default="4w",
                           help="Data de início (ex: '4w', '3m', 'YYYY-MM-DD').")
    parser_pi.add_argument("--end-date", "-e", type=str, default="today",
                           help="Data final (ex: 'today', 'YYYY-MM-DD').")
    parser_pi.add_argument("--workers", "-w", type=int, default=1,
                           help="Qtd de workers para processamento em paralelo.")
    parser_pi.add_argument("--delay-min", type=float, default=3.0,
                           help="Espera mínima aleatória entre PISPs (s).")
    parser_pi.add_argument("--delay-max", type=float, default=8.0,
                           help="Espera máxima aleatória entre PISPs (s).")
    parser_pi.add_argument(
        "--receptor", "-r",
        dest="receptor_filter", nargs="+", metavar="NAME", default=None,
        help="Filtra PISPs por nome (substring, case-insensitive). Ex: -r AILOS PAGSEGURO",
    )
    parser_pi.set_defaults(func=cmd_run_pi)

    # Sub-comando: status
    parser_status = subparsers.add_parser("status", help="Retorna estatísticas locais dos CSVs salvos e execuções.")
    parser_status.set_defaults(func=cmd_status)

    # Sub-comando: last-run
    parser_last = subparsers.add_parser("last-run", help="Mostra os detalhes do último log coletado.")
    parser_last.add_argument("--lines", "-n", type=int, default=50, help="Número de linhas para exibir do final do log.")
    parser_last.set_defaults(func=cmd_last_run)

    # Sub-comando: preview
    parser_preview = subparsers.add_parser("preview", help="Mostra as N últimas linhas de um banco gerado (X.csv).")
    parser_preview.add_argument("dataset", choices=["consents", "api_requests", "active_consents"], help="Qual base exibir.")
    parser_preview.add_argument("--rows", "-r", type=int, default=10, help="Número de linhas a exibir do final.")
    parser_preview.set_defaults(func=cmd_preview)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

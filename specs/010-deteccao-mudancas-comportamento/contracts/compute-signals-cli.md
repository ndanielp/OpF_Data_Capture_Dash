# Contract: `compute_signals.py`

Script de linha de comando no `data-loader/`, no mesmo molde do `sync_to_gcs.py`.

## Uso

```powershell
cd data-loader
python compute_signals.py
```

Sem argumentos obrigatórios. Usa `config.DB_PATH` (mesma resolução do resto do
data-loader: `.env` → padrão local).

## O que faz, em ordem

1. Abre o banco via `scrapers.open_db()` (garante o DDL das tabelas novas).
2. `scrapers.refresh_api_group_weekly(con)` — traz `api_group_weekly` até a última
   semana de `api_requests`.
3. Calcula a trava de cobertura de API por semana.
4. Aplica as regras de `signals.py` sobre o histórico inteiro.
5. Numa única transação: apaga `behavior_signals`, insere todas as linhas, grava
   `behavior_signals_run`. Falha no meio → rollback, a tabela anterior fica intacta.

## Saída (stdout, formato do logging do projeto — números ilustrativos)

```text
08:10:02  INFO   api_group_weekly atualizado até 2026-08-28
08:10:03  INFO   Trava de cobertura de API: 0 semanas bloqueadas
08:10:05  INFO   Alertas calculados: 312 (novos entrantes: 10 | altas: 118 | quedas: 184)
08:10:05  INFO   Semana mais recente (2026-08-28): 3 alertas
08:10:05  INFO   [OK] behavior_signals reconstruída
```

## Códigos de saída

| Código | Quando |
|---|---|
| 0 | Sucesso (inclusive com zero alertas) |
| 1 | Banco não encontrado ou tabela de origem ausente; erro de SQLite (após rollback) |

## Tempo de execução

~2min20s na base real (setembro/2026), quase todo no passo 2 (`refresh_api_group_weekly`).
As regras em si levam segundos.

## Garantias

- **Idempotente**: execuções repetidas sem dado novo produzem as mesmas linhas.
- **Não depende da coleta ter terminado**: usa o que existe na base no momento.
- **Não faz rede**: só lê e escreve o SQLite local.

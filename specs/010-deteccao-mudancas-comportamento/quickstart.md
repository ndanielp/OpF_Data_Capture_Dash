# Quickstart: Detecção de Mudanças de Comportamento

## 1. Calcular os alertas

```powershell
cd data-loader
.\.venv\Scripts\python.exe compute_signals.py
```

Confirmar no log: `api_group_weekly atualizado até` a mesma semana dos consentimentos
(hoje: 2026-08-28) e `[OK] behavior_signals reconstruída`.

## 2. Validar os eventos conhecidos (SC-002)

```powershell
.\.venv\Scripts\python.exe -c "
import sqlite3
con = sqlite3.connect('data/consents.db')
q = '''SELECT week, signal_type, metric, api_group, receptor, round(change_pct*100) pct
       FROM behavior_signals WHERE receptor LIKE ? ORDER BY week'''
for r in ['%INTER%', '%SHOPEE%', '%CLOUDWALK%', '%BELVO%', '%SAFRA%', '%CSF%']:
    for row in con.execute(q, (r,)): print(row)
"
```

Esperado (spec, Independent Tests):

| Receptor | Alerta esperado |
|---|---|
| Banco Inter | `new_entrant` na 6ª semana após a estreia (03/10/2025) |
| Shopee | `new_entrant` na estreia (28/11/2025) |
| CloudWalk | `new_entrant` em 19/07/2024 (3ª observação; 4 semanas no calendário, a série tem um buraco) |
| Belvo | `decrease` de `unique_consents`, −37%, fev/2026 |
| Banco Safra | `decrease` de `unique_consents`, −47%, abr/2026; `decrease` de API em vários grupos, jul/2026 |
| Banco CSF | `decrease` de consentimentos, −83%/−87%, 31/07/2026 |

E **nenhum** `new_entrant` para Google Pay, Midway ou BRB.

## 3. Rodar os testes

```powershell
cd data-loader;  .\.venv\Scripts\python.exe -m pytest tests/test_signals.py -v
cd ..\dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_signals_api.py -v
```

## 4. Validar o endpoint

```powershell
cd dashboard
.\.venv\Scripts\python.exe -m uvicorn server:app --port 8000
curl "http://localhost:8000/api/signals"
curl "http://localhost:8000/api/signals?week=2026-07-31"
curl "http://localhost:8000/api/signals?week=2026-07-31&groups=incumbentes"
```

## 5. Validar o card no navegador (Princípio II — obrigatório)

1. Abrir `http://localhost:8000/` — o card "O que mudou" aparece logo abaixo da barra de período.
2. Mostra a semana mais recente, com as seções Novos entrantes / Altas / Quedas.
3. Escolher 31/07/2026 no seletor: o Banco Safra aparece **numa única linha** em Quedas, citando os grupos de API afetados.
4. Marcar o grupo "Incumbentes" na sidebar: o card passa a mostrar só incumbentes.
5. Semana sem alertas: o card diz explicitamente que não houve mudanças relevantes.

## 6. Publicar

```powershell
cd dashboard
.\deploy.ps1           # código novo + base com behavior_signals
```

Fluxo recorrente depois disso: `main.py run` → `compute_signals.py` → `deploy.ps1 -SyncOnly`.

# Data Model: Tema Pagamentos

## Tabela nova (coletor): `payment_weekly`

Criada em `scrapers.open_db()`; reconstruída inteira por `scrapers.refresh_payment_weekly(con)`.

| Coluna | Tipo | Origem |
|---|---|---|
| date | TEXT | `payment_api_requests.date` (semana) |
| receptor_uuid | TEXT | iniciadora |
| receptor | TEXT | nome mais recente da iniciadora na semana (`MAX`) |
| transmitter_uuid | TEXT | detentora |
| transmitter | TEXT | nome da detentora (`MAX`) |
| api | TEXT | `payments`, `automatic-payments`, `enrollments` |
| endpoint_id | INTEGER | 65, 66, 129, 130, 133, 135, 136, 137, 139 |
| status | INTEGER | 200 ou 500 |
| total | INTEGER | `SUM(total)` |

PK `(date, receptor_uuid, transmitter_uuid, endpoint_id, status)`. Índice em `(endpoint_id, date)`.

Regra: só `endpoint_id` da lista; linhas com `transmitter_uuid = ''` não entram (no nível de API, sem detentora, contariam em dobro).

## Entidades do painel (calculadas em `services/payments.py`)

- **Transação**: `endpoint_id IN (65, 129)`, `status = 200`. `api` = `payments` (65) ou `automatic-payments` (129).
- **Tentativa com falha**: mesmos endpoints, `status = 500`.
- **Etapas do vínculo**: `endpoint_id IN (133, 139, 136, 137)` e encerrados `135`, `status = 200`.
- **Consultas**: 66 (sobre 65) e 130 (sobre 129), `status = 200`.
- **Instituição de pagamento**: uuid que aparece como receptor ou transmissor; `name` = nome mais recente; `short` = `short_name(name)`; `group` = `resolve_institution_group(name)`; `roles` = papéis com transação nas semanas da base (`ini`, `det`).
- **Janela**: as 4 últimas semanas até W; a anterior, as 4 antes dela. Valor por 30 dias = soma × 30/28.
- **Mês**: `YYYY-MM` da semana; valor = soma ÷ `weeks_in_month` × 30/7, onde `weeks_in_month` = semanas distintas daquele mês em `payment_weekly`.
- **Mudança**: `{uuid, name, role, kind: volume|fail|conversion, api|null, direction: up|down, before, after, change, state: alert|watching}`.

## Estado no navegador

- `localStorage['opf:v2:pay-ranking']` = `{pinned: [uuid], excluded: [uuid], initialized: true}` (separado do ranking do tema Dados).
- Recorte (chips) e papel ficam só na página; o papel e a instituição vão na URL da aba Instituição (`?uuid=…&role=ini|det`).
- `sessionStorage['opf:v2:filters']` ganha `pay_role` e `pay_api` (aba Quem lidera?), escritos sem apagar os outros campos.

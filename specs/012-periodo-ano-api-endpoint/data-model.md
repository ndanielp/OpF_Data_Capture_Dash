# Data Model — 012

Mudança aditiva: uma tabela derivada nova, escrita só pelo `data-loader`. Nenhuma tabela existente muda.

## Tabela nova: `api_endpoint_weekly`

Chamadas bem-sucedidas (status 200) por semana × receptor × API × endpoint, sem a API de consentimentos. Reconstruída inteira a cada refresh.

| Coluna | Tipo | Regra |
|---|---|---|
| `date` | TEXT NOT NULL | Sexta-feira da semana (`YYYY-MM-DD`), como nas demais tabelas semanais |
| `receptor_uuid` | TEXT NOT NULL | Instituição receptora |
| `receptor` | TEXT NOT NULL DEFAULT '' | Nome (o maior valor visto, como em `api_status_weekly`) |
| `api` | TEXT NOT NULL | Slug da API (`accounts`, `credit-cards-accounts`, …), nunca `consents` |
| `endpoint_id` | INTEGER NOT NULL | Id do endpoint; **0** = parcela sem endpoint identificado |
| `endpoint` | TEXT NOT NULL DEFAULT '' | Rótulo do endpoint; vazio quando `endpoint_id = 0` |
| `total` | INTEGER NOT NULL DEFAULT 0 | Chamadas na semana |

- **Chave primária**: `(date, receptor_uuid, api, endpoint_id)`. Isso torna o refresh idempotente e impede duplicata.
- **Índices**: `(date)` e `(receptor_uuid, date)`, como em `api_status_weekly`, porque o dashboard lê por semana e por receptor.
- **DDL**: em `scrapers.open_db()`, com `CREATE TABLE IF NOT EXISTS` (o dashboard nunca cria tabela de dados).

### Regra de preenchimento (`scrapers.refresh_api_endpoint_weekly`)

1. **Linhas de endpoint** (`endpoint_id > 0`): `SUM(total)` de `api_requests` com `status = 200` e `api <> 'consents'`, agrupado por `date, receptor_uuid, api, endpoint_id`.
2. **Linha sem endpoint identificado** (`endpoint_id = 0`): para cada `date, receptor_uuid, api` com linha agregada (`COALESCE(endpoint_id, 0) = 0`) em `api_requests` (status 200), `MAX(0, SUM(agregado) − SUM(endpoints))`. Sem linha agregada, não grava a parcela. Só grava quando o valor é maior que zero.
3. O refresh apaga e reinsere tudo na mesma operação (`executescript`, que auto-comita), como `refresh_api_status_weekly`.

### Invariantes (testadas)

- **I1 — fechamento**: para toda tupla `(date, receptor_uuid, api)` com agregado, `SUM(total)` da tabela é **igual** ao agregado quando a soma dos endpoints é menor ou igual a ele, e igual à soma dos endpoints caso contrário.
- **I2 — mesma base do grupo**: somando `api_endpoint_weekly` por grupo de API (pelo mapa `API_GROUPS`) e semana, o resultado é igual a `api_group_weekly.req_week` (que, desde a correção da Decisão 14, soma só `endpoint_id = 0` de `api_requests`). É o que sustenta SC-003.
- **I3 — sem consentimentos**: nenhuma linha com `api = 'consents'`.
- **I4 — idempotência**: rodar o refresh duas vezes sobre a mesma base produz exatamente as mesmas linhas.

### Tamanho e custo

Ordem de 10⁵ linhas (a agregação equivalente sem filtro de status deu 196.412; com `status = 200` é menor), cerca de 0,3% do arquivo. Tempo de reconstrução estimado em 10 a 20 s, a medir no `compute_signals.py`.

## Entidades de leitura (sem armazenamento próprio)

### Catálogo de endpoints

Origem: `endpoint_history` (`api`, `endpoint_id`, `endpoint_label`, `fetched_at`). Para cada `(api, endpoint_id)`, o rótulo do registro mais recente, unido aos `(api, endpoint_id, endpoint)` vistos em `api_endpoint_weekly`. Só entram as APIs de `API_GROUPS` exceto o grupo `Resource`.

### Linha de endpoint (resposta de `/institution/{uuid}/endpoints`)

| Campo | Descrição |
|---|---|
| `endpoint_id` | Id; `0` para "Sem endpoint identificado" |
| `name` | Rótulo, ou "Sem endpoint identificado" |
| `calls_30d` | Chamadas da instituição nas últimas 4 semanas normalizadas para 30 dias |
| `share` | `calls_30d` dividido pelo total da API da instituição |
| `per_consent` | `calls_30d` dividido pela média de únicos (PF + PJ) das mesmas 4 semanas |
| `ref_calls_30d`, `ref_share`, `ref_per_consent` | Os mesmos valores para o comparado escolhido (ecossistema, média do grupo ou outra instituição) |
| `used` | `false` quando `calls_30d` e `ref_calls_30d` são zero (endpoint do catálogo sem uso na janela) |

### Oferta de API (seletor)

`api` (slug), `label` (de `API_LABELS`), `group` (slug do grupo), `color` (de `API_GROUPS`), `calls_30d`. Só as APIs com `calls_30d > 0` para a instituição na janela, ordenadas por volume; a primeira é o padrão.

## Sem mudança

`api_requests`, `api_group_weekly`, `api_status_weekly`, `unique_consents`, `active_consents` e `endpoint_history` permanecem como estão. O legado não lê a tabela nova.

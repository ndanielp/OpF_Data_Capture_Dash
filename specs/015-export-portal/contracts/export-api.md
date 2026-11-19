# Contract: API de exportação (`/api/v2/export/*`)

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Somente leitura. Todas as rotas respondem 503 `{"detail": "Exportação não configurada."}` quando `OPF_EXPORT_CODE` não está definida. Os erros seguem o padrão do `/api/v2`: `{"detail": "<mensagem legível em pt-BR>"}`.

## `POST /api/v2/export/session`

Troca o código por um token de sessão.

**Request** `{"code": "<string, 1–128>"}`

| Status | Corpo |
|---|---|
| 200 | `{"token": "<SessionToken>", "expires_at": "2026-11-20T05:00:00Z"}` |
| 401 | `{"detail": "Código inválido. Confira com quem administra o painel e tente de novo."}` |
| 429 | `{"detail": "Muitas tentativas seguidas. Aguarde 1 minuto para tentar de novo.", "retry_after": 60}` + header `Retry-After: 60` |

- A comparação é feita com `hmac.compare_digest`, e a resposta 401 é a mesma para qualquer código errado (FR-023).
- Cada 401 conta para o bloqueio: 5 em 10 min no mesmo IP bloqueiam por 60 s (FR-028).

## Autenticação das outras rotas

Header `X-Export-Token: <SessionToken>`. Ausente, inválido, vencido ou gerado com outro código: 401 `{"detail": "O código de acesso mudou ou a sessão expirou. Digite o código para continuar."}`. O front volta ao estado `locked` e mantém os filtros (FR-029).

## `GET /api/v2/export/options`

Catálogo para montar a aba. Exige token.

```json
{
  "data_through": "2026-10-30",
  "tables": [
    {"id": "unique", "label": "Consentimentos únicos", "description": "Total semanal por receptor, com PF e PJ.",
     "filters": ["period", "receptors"], "first_date": "2024-01-05", "last_date": "2026-10-30",
     "columns": [{"key": "date", "label": "Semana", "description": "Sexta-feira que fecha a semana."}, "…"]},
    {"id": "pay", "label": "Iniciação de pagamento", "…": "…", "first_date": "2026-01-02", "last_date": "2026-03-27"}
  ],
  "transmitters": [{"uuid": "…", "label": "BRADESCO"}],
  "apis": [{"slug": "accounts", "label": "Conta"}]
}
```

As instituições receptoras vêm do `GET /api/v2/meta` que já existe (`institutions`).

## `GET /api/v2/export/count`

Conta as linhas de cada tabela escolhida. Exige token.

**Query**: `tables=unique,active&start=2025-11-07&end=2026-10-30&receptors=<uuid>,<uuid>&transmitters=&apis=&status=all&level=api`

**200**
```json
{
  "data_through": "2026-10-30",
  "tables": [
    {"id": "unique", "rows": 104, "bytes_estimate": 7280, "period": {"start": "2025-11-07", "end": "2026-10-30"},
     "ignored_filters": []},
    {"id": "active", "rows": 2392, "bytes_estimate": 263120, "period": {"…": "…"}, "ignored_filters": []}
  ],
  "total_rows": 2496,
  "total_bytes_estimate": 270400,
  "large": false
}
```

- `bytes_estimate` = linhas × média de bytes por linha da tabela, uma constante medida na base.
- `large` = `total_rows > 1_000_000` (FR-011).
- Para a tabela `pay` com período fora de 02/01 a 27/03/2026, a resposta traz `rows: 0`.
- 422 para tabela fora da whitelist, data inválida, `start > end` ou lista com mais de 200 itens.
- Resposta em cache por (parâmetros, mtime da base). Alvo: p95 ≤ 500 ms no período padrão (R1).

## `POST /api/v2/export/ticket`

Cria um link de download de 60 s. Exige token.

**Request** (JSON, mesmos campos do `count`) `{"tables": ["unique","active"], "start": "2025-11-07", "end": "2026-10-30", "receptors": ["…"], "transmitters": [], "apis": [], "status": "all", "level": "api"}`

**200** `{"url": "/api/v2/export/file?ticket=<Ticket>", "filename": "opf-dados-2026-10-30.zip", "expires_in": 60}`

O `ticket` assina os parâmetros, que viajam dentro dele e não podem ser alterados na URL.

## `GET /api/v2/export/file?ticket=…`

O download em si. Não exige header: o ticket é a credencial.

| Status | Quando |
|---|---|
| 200 | Streaming do arquivo |
| 401 | Ticket inválido, vencido ou de um código antigo: `{"detail": "Este link de download expirou. Volte à aba Exportar dados e exporte de novo."}` |
| 429 | Duas exportações já em andamento nesta instância: `{"detail": "Outra exportação grande está em andamento. Tente de novo em alguns minutos."}` |

**Headers de resposta**
- Uma tabela: `Content-Type: text/csv; charset=utf-8` e `Content-Disposition: attachment; filename="opf-dados-<tabela>-<data_through>.csv"`.
- Várias tabelas: `Content-Type: application/zip` e `Content-Disposition: attachment; filename="opf-dados-<data_through>.zip"`.
- `X-Rows-Total: <n>` e `X-Bytes-Estimate: <n>`, para a barra de progresso.
- `Cache-Control: no-store`.
- Sem `Content-Length`, porque o tamanho não é conhecido antes do fim do streaming.

**Corpo de uma tabela (CSV)**
```text
﻿# Open Finance Brasil · dados até 30/10/2026 · exportado em 19/11/2026 14:40
# Tabela: Chamadas de API · nível: total por API
# Período: 07/11/2025 a 30/10/2026 · Receptores: NUBANK, MERCADO PAGO · Transmissores: todos · APIs: todas · Status: 200 e 500
# Zeros vieram do portal; semanas sem dado não têm linha.
Semana;Receptor;ID do receptor;Transmissor;ID do transmissor;API;Endpoint;ID do endpoint;Status;Chamadas
2025-11-07;NUBANK;926e3037-…;BRADESCO;…;accounts;;0;200;123456
```

**Corpo de várias tabelas (ZIP)**
```text
opf-dados-2026-10-30.zip
├── LEIAME.txt                      # filtros efetivos por tabela, "não se aplica", dicionário de colunas
├── consentimentos-unicos.csv       # sem linhas '#'
└── consentimentos-ativos.csv
```

**Rotas recusadas**: não existe rota que receba um nome de tabela livre. Um `tables=fetch_attempts` (ou qualquer id fora da whitelist) em `count`, `ticket` ou dentro de um ticket forjado recebe 422 ou 401 (SC-003).

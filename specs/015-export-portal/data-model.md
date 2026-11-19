# Data Model: Portal de exportação de dados

**Feature**: [spec.md](spec.md) · **Date**: 2026-11-19

A feature não cria tabela nem coluna. Só lê as tabelas coletadas que já existem (Princípio V: o dashboard não escreve na base). O modelo abaixo é o que a exportação expõe.

## Tabelas exportáveis (whitelist fechada)

As tabelas exportáveis ficam num dicionário fixo `EXPORT_TABLES` em `dashboard/services/export.py`. Pedir um id fora dele dá 422, e nenhum nome de tabela vem do usuário (FR-003).

| id | Tabela na base | Nome de exibição | Arquivo |
|---|---|---|---|
| `unique` | `unique_consents` | Consentimentos únicos | `consentimentos-unicos` |
| `active` | `active_consents` | Consentimentos ativos | `consentimentos-ativos` |
| `api` | `api_requests` | Chamadas de API | `chamadas-api` |
| `pay` | `payment_api_requests` | Iniciação de pagamento | `iniciacao-pagamento` |

**Nunca exportadas**: `fetch_attempts`, `run_summary`, `endpoint_history`, `api_group_weekly`, `api_status_weekly`, `api_endpoint_weekly`, `behavior_signals`, `behavior_signals_run`, `behavior_watch`, `sqlite_*`.

### Colunas por tabela (FR-004, FR-016, FR-016a)

A coluna `fetched_at` nunca sai.

**unique**: Semana (`date`) · Receptor (`receptor`) · ID do receptor (`receptor_uuid`) · Pessoa física (`cpf`) · Pessoa jurídica (`cnpj`) · Total (`total`)

**active**: Semana · Receptor · ID do receptor · Transmissor (`transmitter`) · ID do transmissor (`transmitter_uuid`) · Total

**api**: Semana · Receptor · ID do receptor · Transmissor · ID do transmissor · API (`api`) · Endpoint (`endpoint`) · ID do endpoint (`endpoint_id`) · Status (`status`) · Chamadas (`total`)
- Nível "total por API": filtra `endpoint_id = 0`, e a coluna Endpoint sai vazia.
- Nível "por endpoint": filtra `endpoint_id <> 0`.

**pay**: as mesmas colunas de **api**, com os rótulos "Iniciadora" e "ID da iniciadora" no lugar de Receptor e ID do receptor, e "Detentora" e "ID da detentora" no lugar de Transmissor e ID do transmissor.

A ordem das linhas é Semana, depois Receptor e Transmissor (quando houver), depois API, ID do endpoint e Status. Ela é estável entre exportações iguais.

### Filtros por tabela (FR-005, FR-006)

| Filtro | Parâmetro | unique | active | api | pay | Coluna |
|---|---|---|---|---|---|---|
| Período | `start`, `end` (AAAA-MM-DD) | ✓ | ✓ | ✓ | ✓ | `date BETWEEN ? AND ?` |
| Receptores | `receptors` (UUIDs) | ✓ | ✓ | ✓ | ✓ | `receptor_uuid IN (…)` |
| Transmissores | `transmitters` (UUIDs) | | ✓ | ✓ | ✓ | `transmitter_uuid IN (…)` |
| APIs | `apis` (slugs) | | | ✓ | ✓ | `api IN (…)` |
| Status | `status` = `all`/`200`/`500` | | | ✓ | ✓ | `status = ?` |
| Nível | `level` = `api`/`endpoint` | | | ✓ | ✓ | `endpoint_id = 0` / `<> 0` |

- Um filtro vazio significa "todos". Um filtro que não se aplica à tabela é ignorado e registrado como "não se aplica" na descrição (US3, cenário 2).
- Todo valor entra por placeholder `?`, e a lista `IN (…)` é montada só com placeholders (Princípio V).
- Período fora da base é ajustado ao primeiro e ao último dado da tabela. `start > end` dá 422.
- Zeros entram e semanas ausentes não viram linha (FR-017a): o `SELECT` não filtra `total`.

## Pedido de exportação

```text
ExportRequest
  tables:        list[id]          # 1–4, ids da whitelist, sem repetição
  start, end:    date | None       # None = primeiro/último dado
  receptors:     list[uuid]        # [] = todos
  transmitters:  list[uuid]
  apis:          list[slug]
  status:        "all" | "200" | "500"   (default "all")
  level:         "api" | "endpoint"      (default "api")
```

Validação: `tables` não vazio; ids de instituição com `[A-Za-z0-9._-]{1,64}` (os UUIDs do portal cabem; o valor só entra por placeholder); `apis` com slug `[a-z0-9-]+`; no máximo 200 itens por lista.

## Credenciais (sem estado no servidor)

```text
key          = HMAC-SHA256(SERVER_SALT, OPF_EXPORT_CODE)      # muda quando o código muda
SessionToken = base64url(json{exp}) + "." + HMAC(key, "session" + payload)    # 12 h
Ticket       = base64url(json{exp, req: ExportRequest}) + "." + HMAC(key, "ticket" + payload)  # 60 s
```

- `SERVER_SALT` é uma constante do código. Ela só separa usos, não é segredo.
- Um token ou ticket com assinatura errada, vencido ou feito com o código antigo é recusado com 401.
- Tentativas erradas ficam em memória por instância: `{ip: [timestamps]}`, com janela de 10 min, 5 erros e bloqueio de 60 s.

## Estados da aba (frontend)

```text
locked ──código válido──▶ ready ──muda filtro──▶ counting ──▶ ready
  ▲                         │
  │                         └─exportar─▶ downloading ──▶ done ──▶ ready
  │                                         │  └─erro/rede─▶ failed ──tentar de novo─▶ downloading
  │                                         └─cancelar─▶ ready
  └── 401 (código trocado/token vencido) ── de qualquer estado; filtros preservados
locked ──5 erros──▶ cooldown (60 s) ──▶ locked
```

- Em `downloading`, os filtros e as tabelas ficam desabilitados (FR-027).
- No download nativo (fora de Chromium), `downloading` dura só até o navegador assumir o arquivo, ou no máximo 3 s.

## Estado compartilhado com as outras abas

- `sessionStorage['opf:v2:filters']`: a aba lê e grava só `period`, `start`, `end` e `receptors`, com spread dos outros campos (Princípio III).
- `sessionStorage['opf:v2:export']`: o token de sessão.
- `localStorage['opf:v2:export-prefs']`: as tabelas marcadas e o nível, que são preferências desta aba.

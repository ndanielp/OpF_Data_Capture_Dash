# Contrato — mudanças na API e na UI do Dashboard 2.0 (feature 012)

Só leitura (GET), JSON, no mesmo FastAPI. O contrato base continua em `specs/011-dashboard-v2/contracts/v2-api.md`; este arquivo descreve apenas o que muda. Nada é removido nem renomeado, então os chamadores atuais continuam válidos.

---

## 1. Período `ytd` (sem mudança de API)

Nenhum endpoint muda. O frontend manda `start=<1º de janeiro do ano de data_through>` e o `end` usual. Todos os endpoints que recebem `start` já resolvem a primeira observação a partir dessa data.

| Item | Valor |
|---|---|
| Chave no estado compartilhado | `opf:v2:filters.period = "ytd"` |
| Rótulo no filtro | "Desde o começo do ano" |
| Rótulo curto (cartões, rodapés) | "no ano" / "desde o começo do ano" |
| Valor desconhecido salvo em sessão | cai em `12m` (comportamento atual) |

---

## 2. `GET /api/v2/evolution` — novo parâmetro `scale`

| Parâmetro | Valores | Padrão | Regra |
|---|---|---|---|
| `scale` | `total`, `per_consent` | `total` | `per_consent` só vale com `metric=api`; com outra métrica → **422** (`'scale' só vale para metric=api.`). Valor fora da lista → 422 |

O frontend envia `scale=per_consent` por padrão para a métrica "Chamadas de API" (Clarifications). Quem não envia `scale` recebe exatamente a resposta de hoje.

### Resposta com `scale=per_consent`

Mesmo formato de hoje. Mudam o significado de alguns campos e acrescentam-se dois:

| Campo | Com `scale=total` (hoje) | Com `scale=per_consent` |
|---|---|---|
| `scale` (novo) | `"total"` | `"per_consent"` |
| `share_available` (novo) | `true` | `false` |
| `headline.ecosystem_growth` | crescimento do volume em 30 dias | crescimento da razão do ecossistema (`from`/`to` em chamadas por consentimento/mês) |
| `headline.top_gainer`, `headline.top_loser` | instituição que mais ganhou/perdeu pp | `null` |
| `series[].values`, `last` | chamadas em 30 dias | chamadas por consentimento/mês; ponto sem dado = `null` (nunca 0) |
| `series[].growth` | `growth_flow` | `growth_stock` sobre a série por consentimento |
| `series[].shares` | participação por ponto | `null` |
| `group_share`, `group_share_change` | blocos de participação por grupo | `[]` |
| `share_changes` | ganhos e perdas em pp | `[]` |
| `quarterly_pace`, `ecosystem_quarterly_pace` | ritmo do volume | ritmo da razão (mesma regra: últimos 3 meses contra os 3 anteriores; "estável" até 3 pontos) |
| `ecosystem_series` (novo, só nesta escala) | ausente | `{"values": [...]}` alinhado a `points`: a razão do ecossistema, para a linha de referência |

**Regras de cálculo** (iguais às de `/ranking` e da aba da instituição, por construção):

- por instituição: `per_consent_30d(chamadas semanais, únicos PF + PJ semanais)`;
- ecossistema: `paired_sums` (só conta instituições com chamadas na semana) e depois `per_consent_30d`;
- semana sem coleta ou sem únicos: `null`.

**Erros**: 422 para `scale` inválido ou fora de `metric=api`; tabela ausente → 200 com `unavailable` como hoje.

---

## 3. `GET /api/v2/institution/{uuid}/endpoints` — novo

Detalhe por endpoint de uma API para a instituição, na janela de 4 semanas normalizadas para 30 dias (a mesma do bloco "Para que usa os dados"). Chamado só ao abrir "Por endpoint" ou trocar de API.

| Parâmetro | Valores | Padrão |
|---|---|---|
| `compare` | `ecosystem`, `group` ou UUID de outra instituição | `ecosystem` |
| `api` | slug de uma API oferecida (ver `apis`) | a de maior volume da instituição |
| `end` | `YYYY-MM-DD` | semana mais recente |

`start` não existe: a visão por endpoint é um retrato da janela, como o mix por grupo.

### Resposta

```json
{
  "week": "2026-09-25",
  "institution": {"uuid": "…", "name": "Bradesco", "group": "incumbentes"},
  "compare": {"kind": "ecosystem", "label": "Ecossistema"},
  "apis": [
    {"api": "accounts", "label": "Contas", "group": "Conta", "color": "#4A9EFF", "calls_30d": 123456.0}
  ],
  "api": "accounts",
  "total": {"calls_30d": 123456.0, "ref_calls_30d": 9876543.0, "per_consent": 1.8, "ref_per_consent": 1.2},
  "endpoints": [
    {"endpoint_id": 12, "name": "Saldos da conta", "calls_30d": 80000.0, "share": 0.648,
     "per_consent": 1.17, "ref_calls_30d": 5000000.0, "ref_share": 0.506, "ref_per_consent": 0.61, "used": true},
    {"endpoint_id": 0, "name": "Sem endpoint identificado", "calls_30d": 300.0, "share": 0.002,
     "per_consent": 0.004, "ref_calls_30d": 12000.0, "ref_share": 0.001, "ref_per_consent": 0.001, "used": true},
    {"endpoint_id": 15, "name": "Limites da conta", "calls_30d": 0.0, "share": 0.0,
     "per_consent": 0.0, "ref_calls_30d": 0.0, "ref_share": 0.0, "ref_per_consent": 0.0, "used": false}
  ],
  "footnote": "Sem o grupo Resource.",
  "unavailable": []
}
```

Os números acima são ilustrativos; o formato é o contrato.

**Regras**

- `apis`: só as APIs de `API_GROUPS` exceto `Resource`, com `calls_30d > 0` para a instituição na janela, ordenadas por volume. Vazio → `api = null`, `endpoints = []` e a tela mostra "Sem chamadas de API nas últimas 4 semanas".
- `endpoints`: **todos** os endpoints do catálogo da API (mais os vistos nos dados), ordenados por `calls_30d` decrescente; os com `used = false` ficam ao final com valor zero. A linha "Sem endpoint identificado" (`endpoint_id = 0`) só aparece quando maior que zero e entra na ordenação pelo valor.
- `share` e `ref_share`: dividem pelo total da API (inclui a linha sem endpoint identificado), então a soma das participações é 1.
- **Invariante (SC-003)**: a soma de `calls_30d` das linhas é igual a `total.calls_30d`, que é igual ao valor da API na visão por grupo para a mesma janela.
- `per_consent`: `calls_30d` ÷ média de únicos (PF + PJ) das mesmas 4 semanas; referência com a base de `paired_sums` do `compare`.
- Comparado sem chamadas na API: `ref_*` = 0, nunca `null` com divisão por zero.

**Erros**

| Caso | Resposta |
|---|---|
| UUID da instituição inexistente | 404 `Instituição não encontrada nesta base.` |
| `compare` inválido | 422, mesma mensagem de `/institution/{uuid}` |
| `api` fora da lista oferecida | 422 `'api' deve ser uma das APIs listadas em 'apis'.` |
| `end` inválido | 422 |
| Tabela `api_endpoint_weekly` ausente | 200 com `apis = []`, `endpoints = []` e `unavailable: ["endpoints"]` |

---

## 4. Contrato de UI (Shell v2, §6.8)

| Tela | Mudança |
|---|---|
| Barra de filtros (3 páginas com período) | A lista vem de `V2.PERIODS`; a opção "Desde o começo do ano" aparece depois de "Últimos 3 meses" e antes de "Desde o início" |
| Como evolui? (métrica "Chamadas de API") | Seletor de escala `Por consentimento/mês` (padrão) · `Volume (30 dias)`, só com a métrica de API; salvo em `opf:v2:filters.evo_scale`; título, subtítulo, imagem e CSV citam a escala |
| Como evolui? (escala por consentimento) | Linha do ecossistema como referência; alternador "participação %", "Participação por grupo", "Quem ganhou e quem perdeu espaço" desativados com o texto "Participação não se aplica a chamadas por consentimento"; cartões de topo mostram o crescimento do ecossistema e, no lugar de ganhou/perdeu, a mesma explicação |
| Como evolui? (período curto) | Com menos de 3 pontos no período, aviso "Poucos dados neste período" no card do gráfico |
| Como opera uma instituição? (bloco "Para que usa os dados") | Seletor `Por grupo de API` (padrão) · `Por endpoint`. Em "Por endpoint": seletor de API (APIs agrupadas por grupo, com a cor do grupo), seletor de unidade já existente (% · API total · API/(PF + PJ)), lista completa de endpoints com barra da instituição e do comparado, linha "Sem endpoint identificado" quando houver e endpoints sem uso ao final em tom atenuado |
| Estado | A visão "Por endpoint" e a API escolhida **não** são persistidas; voltam ao padrão ao trocar de aba. Mantêm-se ao trocar de instituição ou de comparação (se a nova instituição não usar a API escolhida, vale a de maior volume) |
| Exportação | CSV (`;`, vírgula decimal, BOM) e PNG do bloco refletem a escala ou a API selecionada; colunas do CSV de endpoint: API, endpoint, valor da instituição, participação, valor do comparado |
| Cores | Grupo de API por `/api/v2/meta` → `api_groups`; nenhum hex novo |

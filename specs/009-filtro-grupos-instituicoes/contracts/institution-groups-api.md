# Contract: Filtro de Grupos de Instituições

## Novo endpoint — `GET /api/of/institution-groups`

Fonte única de verdade da metadata de grupo, consumida pelo frontend no boot
(mesmo padrão de `/api/of/api-groups` — Principle III).

**Response 200**:

```json
{
  "groups": {
    "incumbentes": { "display": "Incumbentes", "color": "#...", "count": 6 },
    "neo_banks":   { "display": "Neo Banks",   "color": "#...", "count": 7 },
    "itps":        { "display": "ITPs",        "color": "#...", "count": 16 },
    "outros":      { "display": "Outros/Não classificado", "color": "#8B93A0", "count": 34 }
  },
  "institutions": {
    "Bradesco": "incumbentes",
    "Itaú Unibanco": "incumbentes",
    "Nubank": "neo_banks",
    "...": "..."
  }
}
```

- `groups.*.count` é calculado sobre as instituições **presentes na base atual**
  (join com receptores/transmissores distintos), não sobre o total teórico do
  mapeamento — assim reflete a realidade dos dados, não do dicionário estático.
- `institutions` é o mapeamento completo nome→grupo já resolvido para as instituições
  atualmente na base (inclui as classificadas como `outros`), para o frontend não
  precisar reimplementar o match por substring.

## Parâmetro `groups` nos endpoints existentes

Adicionado a todos os endpoints que já aceitam `receptors`:

| Endpoint | Router |
|---|---|
| `GET /api/consents` | server.py |
| `GET /api/api-requests` | server.py |
| `GET /api/resources` | server.py |
| `GET /api/acceleration` | server.py |
| `GET /api/active-consents/evolution` | routers/active_consents.py |
| `GET /api/active-consents/matrix` | routers/active_consents.py |
| `GET /api/active-consents/ranking` | routers/active_consents.py |
| `GET /api/active-consents/intensity` | routers/active_consents.py |

**Query param**: `groups` — string, slugs separados por vírgula (ex.:
`groups=incumbentes,neo_banks`). Ausente ou vazio = nenhum filtro de grupo aplicado
(comportamento atual preservado, FR-005).

**Semântica**:
- União entre os grupos selecionados (FR de US2 da spec: multi-seleção = OR entre grupos).
- Interseção com os demais filtros já existentes (`receptors`, `start`, `end`) — AND
  entre critérios diferentes (FR-006).
- Em `matrix`, `groups` filtra **as duas dimensões independentemente**: uma linha
  (receptor) só aparece se o grupo do receptor está em `groups`; uma coluna
  (transmissor) só aparece se o grupo do transmissor está em `groups`.

**Erros**: um slug desconhecido em `groups` é ignorado silenciosamente (mesmo
comportamento de tolerância a input inválido já usado por `status`/`normalize` nos
endpoints existentes) — não retorna 400.

## Frontend — contrato de estado

`sessionStorage['opf:filters']` ganha o campo `groups: string[]` (slugs), seguindo a
mesma regra da Constituição (Principle III): páginas que não usam o campo devem
preservá-lo (spread) ao escrever o objeto, nunca sobrescrevê-lo.

```js
sessionStorage.setItem('opf:filters', JSON.stringify({...prev, groups: selectedSlugs}));
```

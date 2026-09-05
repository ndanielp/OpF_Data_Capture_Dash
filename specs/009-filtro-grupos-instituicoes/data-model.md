# Data Model: Filtro de Grupos de Instituições

Nenhuma tabela SQLite nova ou alterada — os dois "entities" abaixo vivem inteiramente
em código Python (`dashboard/services/constants.py`), não no banco.

## Grupo de Instituição (enum)

| Slug (usado em query params/JSON) | Display (usado na UI) |
|---|---|
| `incumbentes` | Incumbentes |
| `neo_banks` | Neo Banks |
| `itps` | ITPs |
| `outros` | Outros/Não classificado |

`outros` é o valor implícito para qualquer instituição sem match explícito — nunca
precisa ser listado no mapeamento (FR-002).

## `INSTITUTION_GROUPS` (constante)

Formato — lista de tuplas `(substring_lowercase, grupo_slug)`, avaliada em ordem
(primeiro match vence), mesmo padrão de `BRAND_COLORS`:

```python
INSTITUTION_GROUPS: list[tuple[str, str]] = [
    # Incumbentes
    ("bradesco",         "incumbentes"),
    ("itaú",              "incumbentes"),
    ("itau",              "incumbentes"),
    ("santander",         "incumbentes"),
    ("caixa econ",        "incumbentes"),
    ("banco do brasil",   "incumbentes"),
    ("btg pactual",       "incumbentes"),

    # Neo Banks
    ("nubank",            "neo_banks"),
    ("banco inter",       "neo_banks"),
    ("banco c6",          "neo_banks"),
    ("mercado pago",      "neo_banks"),
    ("pagseguro",         "neo_banks"),
    ("picpay",            "neo_banks"),
    ("recargapay",        "neo_banks"),

    # ITPs
    ("belvo",             "itps"),
    ("klavi",             "itps"),
    ("pluggy",            "itps"),
    ("cumbuca",           "itps"),
    ("delend",            "itps"),
    ("finnet",            "itps"),
    ("lina instituição",  "itps"),
    ("google pay",        "itps"),
    ("iniciador",         "itps"),
    ("celcoin",           "itps"),
    ("cloudwalk",         "itps"),
    ("okto",              "itps"),
    ("pagueveloz",        "itps"),
    ("up.p",              "itps"),
    ("midway",            "itps"),
    ("crystal bmc",       "itps"),
]
```

Fonte completa e revisada linha a linha das 63 instituições:
[`institution-groups-draft.md`](./institution-groups-draft.md) — as 34 instituições em
"Outros" **não** entram na lista acima (comportamento padrão).

**Validação de dados**: nenhuma. Nomes de instituição vêm de `unique_consents.receptor`
e `active_consents`/`api_requests`.{receptor,transmitter} — texto livre já existente,
sem alteração de schema.

## `GROUP_LABELS` / `GROUP_COLORS` (constantes de apresentação)

```python
GROUP_LABELS: dict[str, str] = {
    "incumbentes": "Incumbentes",
    "neo_banks":   "Neo Banks",
    "itps":        "ITPs",
    "outros":      "Outros/Não classificado",
}

GROUP_COLORS: dict[str, str] = {
    "incumbentes": "#...",   # a definir na implementação — 4 cores distintas de API_GROUPS
    "neo_banks":   "#...",
    "itps":        "#...",
    "outros":      "#8B93A0",  # neutro — sinaliza "sem classificação"
}
```

## Função de resolução

```python
def resolve_institution_group(name: str) -> str:
    """Retorna o slug do grupo para um nome de instituição (receptor ou transmissor).
    Match por substring, case-insensitive, primeiro match na lista vence.
    Retorna 'outros' se nenhum padrão bater."""
```

**Call sites previstos** (≥3, justificando a abstração pela Constituição):
1. `server.py` — filtro `groups` em `get_consents`/`get_api_requests`/`get_resources`/`get_acceleration`.
2. `routers/active_consents.py` — filtro `groups` em `evolution`/`matrix`/`ranking`/`intensity`.
3. `routers/openfinance.py` — endpoint `/api/of/institution-groups` (monta o mapeamento completo para o frontend).

## Relacionamentos

```
Instituição (receptor_uuid|transmitter_uuid, nome)  ──resolve_institution_group()──▶  Grupo de Instituição (slug)
```

Relação é **funcional, não persistida**: dado um nome de instituição, o grupo é
recalculado em tempo de request — não há necessidade de manter consistência
transacional com o SQLite, porque a fonte da verdade é o dicionário em código.

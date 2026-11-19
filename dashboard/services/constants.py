"""Shared constants for the OpF dashboard — canonical source of truth.

API_GROUPS is keyed by **DB slug** (same value stored in `api_group_weekly.grp`)
so analytics code can join DB rows to group metadata directly. Each entry
carries a `display` label for the UI, a color, and the list of api ids that
belong to the group (including the virtual `customers-pf`/`customers-pj`
flavors created by the PF/PJ split of the `customers` API).
"""

API_GROUPS: dict[str, dict] = {
    "Conta":        {"display": "Contas",            "color": "#4A9EFF", "apis": ["accounts"]},
    "Cartao":       {"display": "Cartão de Crédito", "color": "#8B5CF6", "apis": ["credit-cards-accounts"]},
    "Credito":      {"display": "Empréstimos",       "color": "#FF6B6B", "apis": ["loans", "financings", "invoice-financings", "unarranged-accounts-overdraft"]},
    "Investimento": {"display": "Investimentos",     "color": "#2ECC7F", "apis": ["bank-fixed-incomes", "credit-fixed-incomes", "variable-incomes", "funds", "treasure-titles"]},
    "Cambio":       {"display": "Câmbio",            "color": "#A855F7", "apis": ["exchanges"]},
    "Identidade":   {"display": "Cadastro",          "color": "#F5A623", "apis": ["customers", "customers-pf", "customers-pj"]},
    "Resource":     {"display": "Resource",          "color": "#14B8A6", "apis": ["resources"]},
}

# Long-form labels for the UI (tooltips, lists, tables). Chart axis labels
# with line breaks no longer exist (they belonged to the removed v1 panel).
API_LABELS: dict[str, str] = {
    "accounts":                      "Contas",
    "credit-cards-accounts":         "Cartão de Crédito",
    "loans":                         "Empréstimos",
    "financings":                    "Financiamentos",
    "invoice-financings":            "Financiamentos de Faturas",
    "unarranged-accounts-overdraft": "Cheque Especial",
    "bank-fixed-incomes":            "Renda Fixa Bancária",
    "credit-fixed-incomes":          "Renda Fixa Crédito",
    "variable-incomes":              "Renda Variável",
    "funds":                         "Fundos",
    "treasure-titles":               "Títulos do Tesouro",
    "customers":                     "Cadastro",
    "exchanges":                     "Câmbio",
}

# Institution → market segment classification for the group filter (feature
# 009-filtro-grupos-instituicoes). Keys are substrings matched case-insensitively
# against receptor/transmitter names.
# Order matters: first match wins. Any institution with no match falls back to
# the "outros" group at lookup time (see resolve_institution_group below) —
# it is intentionally NOT listed here.
#
# Full classification rationale (confirmed line-by-line with product owner on
# 2026-09-05): see specs/009-filtro-grupos-instituicoes/institution-groups-draft.md
INSTITUTION_GROUPS: list[tuple[str, str]] = [
    # Incumbentes — núcleo dos grandes bancos de varejo tradicionais
    ("bradesco",        "incumbentes"),
    ("itaú",            "incumbentes"),
    ("itau",            "incumbentes"),
    ("unibanco",        "incumbentes"),  # cobre variações de encoding de "Itaú Unibanco" na base
    ("santander",       "incumbentes"),
    ("caixa econ",      "incumbentes"),
    ("banco do brasil", "incumbentes"),
    ("btg pactual",     "incumbentes"),

    # Neo Banks — bancos digitais nativos + grandes carteiras/fintechs de marca consolidada
    ("nubank",          "neo_banks"),
    ("banco inter",     "neo_banks"),
    ("banco c6",        "neo_banks"),
    ("mercado pago",    "neo_banks"),
    ("pagseguro",       "neo_banks"),
    ("picpay",          "neo_banks"),
    ("recargapay",      "neo_banks"),

    # ITPs — Instituições de Pagamento especializadas em agregação/iniciação
    ("belvo",                "itps"),
    ("klavi",                "itps"),
    ("pluggy",                "itps"),
    ("cumbuca",               "itps"),
    ("delend",                "itps"),
    ("finnet",                "itps"),
    ("lina instituição",     "itps"),
    ("lina instituicao",     "itps"),
    ("google pay",            "itps"),
    ("iniciador",             "itps"),
    ("celcoin",               "itps"),
    ("cloudwalk",             "itps"),
    ("okto",                  "itps"),
    ("pagueveloz",            "itps"),
    ("up.p",                  "itps"),
    ("midway",                "itps"),
    ("crystal bmc",           "itps"),
]

INSTITUTION_GROUP_SLUGS: tuple[str, ...] = ("incumbentes", "neo_banks", "itps", "outros")

# Dashboard 2.0 (feature 011) — paleta aprovada para o tema claro. Os quatro tons
# diferem também em luminosidade, para continuarem distinguíveis em print e para
# quem não distingue cores.
GROUP_COLORS_V2: dict[str, str] = {
    "neo_banks":   "#5B2BC4",
    "itps":        "#1F8FD6",
    "incumbentes": "#E8913A",
    "outros":      "#A3ABBA",
}

# Variante para o tema escuro. Só o roxo muda: sobre a superfície escura (#1B1F2E) o
# #5B2BC4 dá 2,0:1, abaixo dos 3:1 que um elemento gráfico precisa; o #9B7BFF dá 5,2:1.
GROUP_COLORS_V2_DARK: dict[str, str] = {**GROUP_COLORS_V2, "neo_banks": "#9B7BFF"}

# Ordem de exibição no 2.0 (barras empilhadas, chips, legendas).
GROUP_LABELS_V2: dict[str, str] = {
    "neo_banks":   "Neobancos",
    "itps":        "ITPs",
    "incumbentes": "Incumbentes",
    "outros":      "Outros",
}

# Nomes curtos do 2.0 (rankings e exportação). Substring, sem caixa; primeira
# correspondência vence. Sem correspondência → nome da base em Title Case.
SHORT_NAMES: list[tuple[str, str]] = [
    ("itaú unibanco",      "Itaú"),
    ("itau unibanco",      "Itaú"),
    ("caixa econ",         "Caixa"),
    ("banco btg",          "BTG Pactual"),
    ("banco do brasil",    "Banco do Brasil"),
    ("banco do nordeste",  "Banco do Nordeste"),
    ("banco inter",        "Banco Inter"),
    ("banco safra",        "Banco Safra"),
    ("banco xp",           "Banco XP"),
    ("santander",          "Santander"),
    ("bradesco",           "Bradesco"),
    ("nubank",             "Nubank"),
    ("mercado pago",       "Mercado Pago"),
    ("picpay",             "PicPay"),
    ("recargapay",         "RecargaPay"),
    ("pagseguro",          "PagSeguro"),
    ("cloudwalk",          "CloudWalk"),
    ("belvo",              "Belvo"),
    ("klavi",              "Klavi"),
    ("cumbuca",            "Cumbuca"),
    ("pluggy",             "Pluggy"),
    ("neon pag",           "Neon"),
    ("shopee",             "Shopee"),
    ("sicredi",            "Sicredi"),
    ("sicoob",             "Sicoob"),
    ("banrisul",           "Banrisul"),
    ("agibank",            "Agibank"),
    ("iniciador",          "Iniciador"),
]


def resolve_institution_group(name: str) -> str:
    """Substring lookup against INSTITUTION_GROUPS (same pattern as the brand-color lookup).
    Falls back to 'outros' when no pattern matches — every institution gets a
    group, per feature 009-filtro-grupos-instituicoes FR-002."""
    lname = (name or "").lower()
    for key, grp in INSTITUTION_GROUPS:
        if key in lname:
            return grp
    return "outros"

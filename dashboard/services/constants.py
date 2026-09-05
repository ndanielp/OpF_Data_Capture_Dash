"""Shared constants for the OpF dashboard — canonical source of truth.

API_GROUPS is keyed by **DB slug** (same value stored in `api_group_weekly.grp`)
so analytics code can join DB rows to group metadata directly. Each entry
carries a `display` label for the UI, a color, and the list of api ids that
belong to the group (including the virtual `customers-pf`/`customers-pj`
flavors created by server.py's PF/PJ split).
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
# with line breaks live in server.py as _API_LABELS (display-specific).
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

# APIs excluded from product breakdowns (infra / meta endpoints).
EXCLUDED_APIS: set[str] = {"consents"}
RESOURCES_API: str = "resources"

# Canonical brand colors for the top institutions (used by /api/of/brand-colors).
# Keys are substrings matched case-insensitively against receptor names.
# Order matters: more specific matches should come first.
BRAND_COLORS: list[tuple[str, str]] = [
    ("bradesco",        "#CC092F"),
    ("nubank",          "#820AD1"),
    ("itaú",            "#EC7000"),
    ("itau",            "#EC7000"),
    ("santander",       "#EC0000"),
    ("caixa",           "#005CA9"),
    ("mercado pago",    "#009EE3"),
    ("picpay",          "#21C25E"),
    ("banco do brasil", "#FBBA00"),
    ("belvo",           "#4A9EFF"),
    ("recargapay",      "#7B68EE"),
    ("shopee",          "#FF5722"),
    ("pagseguro",       "#34B7F1"),
    ("cloudwalk",       "#9C27B0"),
]

# Institution → market segment classification for the group filter (feature
# 009-filtro-grupos-instituicoes). Keys are substrings matched case-insensitively
# against receptor/transmitter names, same lookup pattern as BRAND_COLORS above.
# Order matters: first match wins. Any institution with no match falls back to
# the "outros" group at lookup time (see of_analytics.resolve_institution_group) —
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

GROUP_LABELS: dict[str, str] = {
    "incumbentes": "Incumbentes",
    "neo_banks":   "Neo Banks",
    "itps":        "ITPs",
    "outros":      "Outros/Não classificado",
}

# Distinct from API_GROUPS colors — the two "group" concepts (API product group vs.
# institution market segment) can appear side by side on the same page.
GROUP_COLORS: dict[str, str] = {
    "incumbentes": "#1E3A8A",
    "neo_banks":   "#DB2777",
    "itps":        "#D97706",
    "outros":      "#8B93A0",
}

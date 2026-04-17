"""Shared constants for the OpF dashboard — canonical source of truth.

Both Ecossistema (dashboard.html) and Perfil Receptor (receptor_profile.html)
must consume API_GROUPS, API_LABELS and GROUP_COLORS from here so that
group names, API labels and per-group colors are identical across tabs.
"""

# Group name → {color, apis}. Group names are the CANONICAL labels exposed
# to the UI. APIs include both the raw DB names ("customers") and the virtual
# flavors created by server.py's PF/PJ split ("customers-pf", "customers-pj"),
# so both ecossistema (which splits) and perfil (which doesn't) see their
# API names inside the group.
API_GROUPS: dict[str, dict] = {
    "Contas":            {"color": "#4A9EFF", "apis": ["accounts"]},
    "Cartão de Crédito": {"color": "#8B5CF6", "apis": ["credit-cards-accounts"]},
    "Empréstimos":       {"color": "#FF6B6B", "apis": ["loans", "financings", "invoice-financings", "unarranged-accounts-overdraft"]},
    "Investimentos":     {"color": "#2ECC7F", "apis": ["bank-fixed-incomes", "credit-fixed-incomes", "variable-incomes", "funds", "treasure-titles"]},
    "Câmbio":            {"color": "#A855F7", "apis": ["exchanges"]},
    "Cadastro":          {"color": "#F5A623", "apis": ["customers", "customers-pf", "customers-pj"]},
}

# Mapping from api_group_weekly.grp (ASCII, legacy) → canonical display label.
# Used by of_analytics when reading from the pre-aggregated weekly table.
DB_GROUP_TO_DISPLAY: dict[str, str] = {
    "Conta":        "Contas",
    "Cartao":       "Cartão de Crédito",
    "Credito":      "Empréstimos",
    "Investimento": "Investimentos",
    "Cambio":       "Câmbio",
    "Identidade":   "Cadastro",
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

# Flat list in group-display order — used for column ordering in heatmaps.
ORDERED_APIS: list[str] = [api for g in API_GROUPS.values() for api in g["apis"]]

# Reverse lookup: api → group name.
API_TO_GROUP: dict[str, str] = {
    api: name for name, g in API_GROUPS.items() for api in g["apis"]
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

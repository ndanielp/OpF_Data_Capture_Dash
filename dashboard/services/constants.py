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

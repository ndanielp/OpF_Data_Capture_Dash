# Contract: rotas depois da remoção

| Rota | Antes | Depois |
|---|---|---|
| `GET /` | Painel v1 (Ecossistema) | 307 → `/v2` |
| `GET /profile` | Painel v1 (Perfil Receptor) | 307 → `/v2` |
| `GET /active-consents` | Painel v1 (Consentimentos Ativos) | 307 → `/v2` |
| `GET /v2`, `/v2/evolucao`, `/v2/mudancas`, `/v2/instituicao`, `/v2/exportar` | páginas v2 | sem mudança |
| `/api/v2/*`, `/api/v2/export/*` | API v2 e exportação | sem mudança |
| `/static/v2/*` | CSS e JS do v2 | sem mudança |
| `/static/dashboard.html`, `/static/receptor_profile.html`, `/static/active_consents.html` | arquivos estáticos do v1 | 404 |
| `/api/of/*`, `/api/active-consents/*`, `/api/signals`, `/api/receptors`, `/api/consents`, `/api/api-requests`, `/api/api-requests-timeseries`, `/api/resources`, `/api/acceleration`, `/api/efficiency`, `/api/stats` | API v1 | 404 |

Os redirecionamentos descartam a query string. Nenhum outro comportamento muda.

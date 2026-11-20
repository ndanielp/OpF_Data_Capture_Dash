# Data Model: Polimento do tema Pagamentos

Nenhuma tabela nova nem mudança de esquema. Tudo sai de `payment_weekly` (feature 018).

## Estado no navegador

| Campo | Onde | Valor | Abas |
|---|---|---|---|
| `pay_month` | `sessionStorage['opf:v2:filters']` e `?month=` | `AAAA-MM` ou ausente (= últimas 4 semanas, ou último mês nas abas de série) | todas |
| `pay_r` | `sessionStorage` e `?r=` | uuids de iniciadoras escolhidas (vazio = todas) | Evolução, Matriz |
| `pay_c` | `sessionStorage` e `?c=` | uuids de detentoras escolhidas | Evolução, Matriz |
| `cp` | só `?cp=` | contrapartes escolhidas na aba da instituição | Instituição |
| `from`, `to` | só na página | meses da comparação "de / até" | Evolução, Instituição |

Regras:
- Uuid desconhecido ou de papel errado é descartado, e uma linha avisa.
- Um mês fora da base volta ao padrão.

## Respostas (acréscimos)

- **Instituição no `/meta`**: `volume: {ini: [float por mês], det: [float por mês]}`, transações por 30 dias, alinhado a `months`.
- **Matriz (`/flows`)**: `rows[]` e `cols[]` ganham `others_count` na linha ou coluna "Outras" (número de instituições somadas).
- **Ranking do mês**: mesma forma de hoje, com `period: {kind: "month"|"window", month, prev_month}`.
- **Mudanças do mês**: `month`, `months: [{month, alerts}]` (contagem por mês), `alerts` do mês e `watching` só no último mês.

# Contract delta: `/api/v2/payments/*` (feature 019)

Só o que muda em relação a [018/contracts/payments-api.md](../../018-pagamentos-dash/contracts/payments-api.md). Sem os parâmetros novos, cada rota responde exatamente como antes.

## GET /meta

Cada instituição ganha `volume`:

```json
{"uuid": "…", "short": "Nubank", "roles": ["ini", "det"],
 "volume": {"ini": [3.74e6, "…", 8.69e6], "det": [2.6e6, "…", 7.1e6]}}
```

As listas são alinhadas a `months`. O papel sem atuação vem com zeros.

## GET /ranking?month=2026-06

- `month` (opcional, `AAAA-MM` entre os `months`): ranking do mês, normalizado para 30 dias.
  - Crescimento e `ip_share_prev` comparam com o mês anterior: `null` no primeiro mês.
  - `window` vira `{"start": "2026-06-01", "end": "2026-06-30"}`.
  - `period` = `{"kind": "month", "month": "2026-06", "prev_month": "2026-05"}`.
- Sem `month`: `period` = `{"kind": "window"}`.
- Mês fora da base: 422.
- `limit`: 1–500.

## GET /flows?rows=a,b&cols=c&size=8

- `rows` e `cols` (opcionais): uuids na ordem dada, 1–12 de cada lado.
  - O lado sem lista usa as `size` maiores.
  - Uuid desconhecido é ignorado.
  - Mais de 12: 422.
- A linha e a coluna "Outras" ganham `others_count` (inteiro).

## GET /institution/{uuid}?counterparts=a,b

- `counterparts` (opcional, 1–12 uuids do outro papel): linhas = escolhidas + "Outras" (com `others_count`).
- Sem a lista: as 8 maiores + "Outras" (com `others_count`).
- Mais de 12: 422.

## GET /changes?month=2026-08

- `month` (opcional): mudanças confirmadas com W = última semana do mês.
  - `watching` só vem quando `month` é o último mês da base; nos outros meses é `[]`.
- Sempre devolve `months: [{"month": "2026-01", "alerts": 12}, …]`, os meses da base com a contagem de mudanças confirmadas de cada um.
- Mês fora da base: 422.

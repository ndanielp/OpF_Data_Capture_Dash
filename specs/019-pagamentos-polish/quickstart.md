# Quickstart: Polimento do tema Pagamentos

```bash
cd dashboard
.venv/bin/uvicorn server:app --reload --port 8000
```

Base local com `payment_weekly` (se faltar: `cd data-loader && .venv/bin/python compute_signals.py`).

## Conferências manuais

1. `/v2/pagamentos`: escolher "junho/2026" no mês; o total bate com a soma do mês na base × fator mensal. "Mostrar: todas".
2. `/v2/pagamentos/evolucao`: passar o mouse e focar as barras (dica); clicar em julho (destaque nos 4 passos); "+ Adicionar" Google Pay e Nubank (só as duas); "de março até agosto" no passo 2; "Limpar".
3. Ir para `/v2/pagamentos/matriz`: as escolhidas aparecem nas linhas; adicionar Klavi e Sicredi; tentar a 13ª; meses alinhados; sem traço sobre os números; PNG da matriz com as células.
4. Copiar a URL da matriz e abrir em outra aba: mesmo mês e mesmas instituições.
5. `/v2/pagamentos/mudancas`: barra de meses, agosto, agrupamento por instituição, busca.
6. `/v2/pagamentos/instituicao`: adicionar uma contraparte fora das 8 maiores; legenda sem série ausente.
7. 1280 × 800, 800 px e 390 px sem rolagem lateral; teclado nos controles novos.

## Testes

```bash
cd dashboard && .venv/bin/python -m pytest tests -q
```

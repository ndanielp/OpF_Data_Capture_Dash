# Quickstart: Tema Pagamentos

```bash
cd data-loader
python compute_signals.py          # cria/atualiza payment_weekly (além das outras pré-agregações)
cd ../dashboard
uvicorn server:app --reload --port 8000
```

Abrir `http://localhost:8000/v2`, clicar em **Pagamentos** no cabeçalho.

## Conferências manuais

1. `/v2/pagamentos`: total por 30 dias = consulta abaixo × 30/28.
   ```sql
   SELECT SUM(total) FROM payment_weekly
   WHERE endpoint_id IN (65,129) AND status = 200
     AND date > date((SELECT MAX(date) FROM payment_weekly), '-28 days');
   ```
2. Trocar Iniciadoras/Detentoras e a API; fixar uma instituição fora do Top 10.
3. `/v2/pagamentos/matriz`: arrastar a linha do tempo, "Reproduzir", trocar a cor, clicar numa célula, Top 4.
4. `/v2/pagamentos/evolucao`: desligar Google Pay e conferir que os 4 passos mudam; abrir o funil JSR.
5. `/v2/pagamentos/mudancas`: filtros de tipo e papel.
6. `/v2/pagamentos/instituicao?uuid=<nubank>&role=det`: lista "Onde falha", funil JSR, papel Iniciadora.
7. Tema escuro e 390 px de largura em todas.

## Testes

```bash
cd data-loader && python -m pytest tests/test_payment_weekly.py
cd dashboard && python -m pytest tests/test_payments.py
```

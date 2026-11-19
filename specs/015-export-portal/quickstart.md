# Quickstart: Portal de exportação de dados

**Feature**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Rodar localmente

```bash
cd dashboard
uvicorn server:app --reload --port 8000
```

Abra `http://localhost:8000/v2/exportar` (a página não aparece no menu de abas). O código de acesso é fixo e fica só no servidor (`EXPORT_CODE` em `services/export.py`).

## Roteiro de validação manual (Princípio II)

1. **Acesso** (FR-020, FR-023, FR-028): um código errado mostra o erro; 5 erros seguidos bloqueiam por 1 minuto; o código certo libera a aba. A aba fica liberada ao recarregar e pede o código de novo numa aba nova do navegador. "Sair" volta à tela do código.
2. **Uma tabela** (US1): "Consentimentos únicos", 12 meses, receptor NUBANK. Baixa um `.csv` que abre no Excel com acentos corretos e confere com o valor do painel ("Como opera uma instituição?", PF + PJ) numa semana qualquer.
3. **Contagem** (US2): ao trocar filtros, o número de linhas muda em até 2 s. "Chamadas de API" com "Tudo" mostra o aviso de arquivo grande, e o botão continua habilitado.
4. **Várias tabelas** (US3): "Consentimentos únicos" e "Consentimentos ativos" baixam um `.zip` com 2 CSVs e o `LEIAME.txt`. O filtro de transmissor aparece como "não se aplica" para únicos.
5. **Nível** (FR-009): "Chamadas de API" em "Total por API" deixa a coluna Endpoint vazia, e "Por endpoint" a preenche. Os dois níveis nunca saem no mesmo arquivo.
6. **Exportação grande** (SC-005a): "Chamadas de API", "Tudo", "Por endpoint". O download começa em até 10 s, e durante ele a aba "Quem lidera?" abre normalmente em outra janela. No Chrome, a barra de progresso e o "Cancelar" funcionam.
7. **Link repassado**: copie a URL do download e abra-a numa janela anônima 2 minutos depois. Ela responde "Este link de download expirou".
8. **Código trocado** (FR-029): com a aba aberta, mude `EXPORT_CODE` e reinicie o servidor. A próxima contagem pede o código novo e mantém os filtros.
9. **Tema e celular**: tema escuro e largura de 390 px, comparando com o [protótipo](https://claude.ai/artifact/4ZQAboWY8PgPYoxqiHver4).

## Testes automatizados

```bash
cd dashboard
pytest tests/test_v2_export.py -q
```

## Deploy (Cloud Run)

Não há segredo nem variável de ambiente para o código: ele é fixo no servidor. `deploy.sh` e `deploy.ps1` passam `--timeout 3600`, e o resto do deploy não muda.

Trocar o código exige editar `EXPORT_CODE` em `dashboard/services/export.py` e fazer um novo deploy. Quem estava com a aba aberta recebe o pedido do código novo na próxima ação (FR-021, FR-029).

# Quickstart — 014

## Subir e testar

```bash
cd dashboard && source .venv/bin/activate && uvicorn server:app --port 8000
# http://localhost:8000/v2/instituicao
```

## Roteiro manual

1. Escolha uma instituição, uma comparação e um período. Clique em "Exportar slide" (barra de filtros, à direita).
2. O PNG baixado tem 1600×900, título com instituição · período · comparação, subtítulo com a semana e rodapé de fonte.
3. Contém indicadores, evolução, "Quais dados busca" (completo: todos os grupos ou todos os endpoints) e transmissores. **Não** contém alertas, taxa de erro nem chamadas por grupo.
4. Troque a unidade, a métrica da evolução, a visão "Por endpoint" (e a API) e o tema: o slide acompanha a tela.
5. Instituição pequena (poucos dados) e instituição grande: nenhum bloco em branco, nenhum texto cortado.
6. Com a página carregando ou com "Por endpoint" ainda buscando dados, a ação avisa e não baixa.
7. Imagens por bloco das outras abas e deste: iguais às de antes.

## Verificação automatizada (Chromium headless)

Scripts de verificação usados na implementação: captura das 36 imagens por bloco antes e depois (diff de pixels zero) e do slide em 2 temas × visão por grupo/endpoint × instituição grande/pequena (1600×900, texto ≥ 12px, sem alertas e sem taxa de erro).

# Research — 014

## D1. Formato: PNG 16:9, não PPTX
**Decisão**: PNG 1600×900. **Por quê**: é o formato das demais exportações ("funcionar como as demais"), sem biblioteca nova. **Alternativa**: PPTX editável: exige gerar o arquivo no navegador e uma regra de layout própria; fora do escopo.

## D2. Composição própria, sem reduzir a página
**Decisão**: grade 16:9 com os blocos lado a lado, mantendo o texto no tamanho dos tokens. **Por quê**: a página tem ~2.000 px de altura; reduzida a 900 px o texto cai para ~5 px, abaixo do mínimo (12px). **Alternativa**: reduzir por escala, como `exportImage` faz para um bloco: viola o mínimo de texto num bloco só se o conteúdo for muito maior que o quadro, e aqui seria sempre.

## D3. O que cabe: cortar listas, não encolher texto
**Decisão**: depois de montar a grade, cada célula é medida; enquanto o conteúdo passar da altura, remove-se o último item da lista (`ul > li`) e conta-se o que saiu ("+N …" na própria célula). **Por quê**: garante texto ≥ 12px e nenhum corte pela metade (FR-006, FR-007). **Alternativa**: número fixo de itens por bloco: quebra com nomes longos ou com unidades de altura diferentes.

## D4. Gráfico: redesenhar no tamanho da célula
**Decisão**: a página expõe uma função que desenha a evolução num canvas fora da tela com a largura e a altura da célula e devolve um PNG; o slide usa esse PNG. **Por quê**: esticar o canvas da página distorce eixos e rótulos. **Alternativa**: reaproveitar `toDataURL` do canvas da página (como `exportImage`): serve quando o tamanho é parecido, não aqui.

## D5. Conteúdo dos blocos no slide
**Decisão**: clones dos cards da página sem cabeçalho/ações/seletores/rodapé (`.v2-card-head`, `.v2-card-actions`, `button`, `select`, `.v2-field`, `.v2-card-foot`, `.v2-noexport`), com título e subtítulo próprios do bloco no estilo do design system. A visão "Por endpoint" entra como está na tela (a API escolhida aparece no subtítulo do bloco). **Por quê**: SC-005 (valores idênticos à tela) e FR-004.

## D6. Moldura compartilhada
**Decisão**: extrair de `V2.exportImage` o que é comum (quadro 1600×900 com cabeçalho e rodapé, geração do PNG, download). **Por quê**: evita duas cópias. **Risco**: tocar nas exportações atuais. **Controle**: diff de pixels zero nas 36 imagens por bloco (SC-006).

## D7. Botão e estado
**Decisão**: "Exportar slide" ao lado de "Exportar CSV", agrupados à direita (`.v2-fb-actions`); desativado até haver dados; se um bloco ainda carrega (por exemplo, o detalhe por endpoint), a ação avisa e não baixa. **Por quê**: FR-008 e o caso de borda "slide incompleto".

## D8. Regra
**Decisão**: emendar a Constituição §6.8 (1.4.0) e o contrato do shell: a página de instituição passa a ter também "Exportar slide" na barra de filtros. **Por quê**: a regra atual limita a barra a um botão de exportação.

## Resultado da verificação (2026-10-30)

- 36 imagens por bloco das 4 abas (claro e escuro): diff de pixels zero antes e depois da extração da moldura; duas capturas da linha de base também idênticas.
- Slide: 1600×900 em 4 instituições (grande, sem dados, nome longo, pequena com endpoint), claro e escuro, visão por grupo e por endpoint, a 1280 e 390 px: texto mínimo 12px, 0 elementos fora da célula, 0 cortes, sem "Alertas" nem "Taxa de erro".
- Cortes típicos (Nubank, por grupo): mix 3 de 5 grupos, grupos 2 de 5, transmissores 3 de 9; por endpoint, 3 de 7. Pesos de linha 1,2 : 1 deram o melhor equilíbrio.
- Botões na barra: 44 px, sem rolagem horizontal em 1280 e 390 px.

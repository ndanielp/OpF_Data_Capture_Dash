# Feature Specification: Portal de exportação de dados

**Feature Branch**: `015-export-portal`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "Incluir um portal de exportação de dados. Nova tab em que usuário possa selecionar as tabelas e filtros exportar os arquivos com os dados selecionado (somente dados, sem permitir exportar os logs e análises derivadas da coleta)."

## Clarifications

### Session 2026-11-19

- Q: Qual o limite de linhas por tabela numa exportação? → A: Sem limite. Cada tabela pode ser exportada inteira; a aba informa o tamanho antes e avisa quando o arquivo for grande, mas não bloqueia.
- Q: Quem pode usar a exportação? → A: Só quem tiver o código de acesso. A aba aparece para todos, mas contar linhas e exportar exigem o código; o resto do painel continua público.
- Q: Linhas com valor zero informadas pelo portal entram na exportação? → A: Sim. Os zeros saem como vieram do portal; só a ausência de dado (semana não informada) continua sem linha.
- Q: Como as colunas do arquivo se chamam? → A: Rótulos em português, como nos outros CSVs do painel (ex.: "Semana", "Receptor", "ID do receptor", "Pessoa física", "Total").
- Q: O layout do protótipo está aprovado? → A: Sim. A referência visual e as regras de tela estão em [ux-handoff.md](ux-handoff.md) e entram como FR-025 a FR-029.

## Contexto de uso

Hoje o painel só exporta o que cada aba mostra: um CSV por página, já agregado (ranking, evolução, perfil de uma instituição), e imagens dos blocos. Quem precisa dos números de base, por exemplo para cruzar com outra fonte, montar uma análise própria ou conferir um valor com o portal do Open Finance, não tem como obtê-los pelo painel. A nova aba entrega esses números como foram coletados, por semana, receptor, transmissor, API e endpoint, sem os registros internos da coleta e sem as análises que o painel calcula em cima deles.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Exportar uma tabela de dados com filtros (Priority: P1)

Como analista, quero escolher uma tabela de dados coletados, aplicar filtros de período e de instituição e baixar um arquivo só com as linhas escolhidas, para trabalhar com os números fora do painel.

**Why this priority**: É o núcleo da feature. Com uma única tabela exportável já há valor, e as outras histórias só ampliam o que entra no arquivo.

**Independent Test**: Na aba de exportação, informar o código de acesso, escolher "Consentimentos únicos", o período das últimas 12 semanas e um receptor, exportar e conferir que o arquivo traz só as semanas e o receptor escolhidos, com os mesmos totais que o painel mostra para esse receptor e período.

**Acceptance Scenarios**:

1. **Given** a aba de exportação aberta, **When** o usuário escolhe uma tabela, **Then** aparecem só os filtros que se aplicam a ela (por exemplo, "Transmissores" não aparece para "Consentimentos únicos").
2. **Given** uma tabela e filtros escolhidos, **When** o usuário exporta, **Then** baixa um arquivo com uma linha por registro que atende a todos os filtros, e nenhuma linha fora deles.
3. **Given** nenhum receptor escolhido, **When** o usuário exporta, **Then** o arquivo traz todos os receptores, como nas outras abas ("nada selecionado = todos").
4. **Given** uma exportação concluída, **When** o usuário compara um total do arquivo com o mesmo total no painel (mesma métrica, semana e instituição), **Then** os valores são iguais.
5. **Given** filtros que não retornam nenhuma linha, **When** o usuário tenta exportar, **Then** o sistema avisa que não há dados para os filtros escolhidos e nada é baixado.

---

### User Story 2 - Ver o tamanho da exportação antes de baixar (Priority: P2)

Como analista, quero saber quantas linhas e qual o tamanho aproximado da exportação antes de baixar, para decidir se restrinjo os filtros quando o arquivo for grande ou estiver vazio.

**Why this priority**: A tabela de chamadas de API tem milhões de linhas. Sem essa informação, o usuário dispara sem saber uma exportação que leva minutos e gera um arquivo de cerca de 1 GB.

**Independent Test**: Escolher "Chamadas de API" sem filtros e conferir que o número de linhas, o tamanho aproximado e o aviso de arquivo grande aparecem antes de qualquer download, e que a exportação continua disponível. Depois, restringir o período e conferir que os números caem e o aviso some.

**Acceptance Scenarios**:

1. **Given** uma tabela e filtros escolhidos, **When** qualquer filtro muda, **Then** o número de linhas e o tamanho aproximado do arquivo são atualizados sem o usuário precisar pedir.
2. **Given** filtros que resultam num arquivo grande (acima de 1 milhão de linhas no total), **When** o usuário olha a aba, **Then** um aviso informa o tamanho e o tempo de download esperados e sugere restringir período, instituições ou APIs, e a ação de exportar continua disponível.
3. **Given** uma exportação grande em andamento, **When** o arquivo está sendo gerado, **Then** o download começa logo, sem esperar o arquivo inteiro ficar pronto, e o usuário vê que ele está em andamento.

---

### User Story 3 - Exportar várias tabelas de uma vez (Priority: P3)

Como analista, quero escolher mais de uma tabela com os mesmos filtros de período e instituições e receber todas num único download, para não repetir a exportação tabela por tabela.

**Why this priority**: Só economiza tempo. Tudo o que entrega também pode ser feito exportando cada tabela em separado.

**Independent Test**: Escolher "Consentimentos únicos" e "Consentimentos ativos" com o mesmo período e receptor, exportar e conferir que o download traz um arquivo por tabela, cada um só com as linhas filtradas.

**Acceptance Scenarios**:

1. **Given** duas ou mais tabelas escolhidas, **When** o usuário exporta, **Then** recebe um único download com um arquivo por tabela e um arquivo de descrição dos filtros e das colunas.
2. **Given** um filtro que só existe numa das tabelas (por exemplo, API), **When** o usuário exporta várias tabelas, **Then** esse filtro vale só para a tabela a que se aplica, e o arquivo de descrição diz isso.

---

### Edge Cases

- **Dupla contagem nas chamadas de API**: a tabela de chamadas guarda, para cada API, o total da API e uma linha por endpoint que divide esse mesmo total. A exportação precisa deixar claro qual nível está no arquivo e nunca misturar os dois sem identificação. Por padrão, o usuário recebe só o total por API.
- **Semana sem dado**: uma semana em que a instituição não aparece não vira linha com zero. A ausência é mantida, como no resto do painel.
- **Zero informado pelo portal**: quando o portal informou zero para uma semana (por exemplo, um par receptor × transmissor sem consentimentos ativos), a linha sai com o valor 0. Zero informado e semana sem dado são coisas diferentes no arquivo.
- **Instituição presente só em parte do período**: a exportação traz só as semanas em que ela tem dado, sem preencher as outras.
- **Base atualizada durante o uso**: se a base mudar entre a contagem de linhas e o download, o arquivo reflete a base no momento do download, e a data dos dados no arquivo de descrição mostra isso.
- **Período invertido ou fora da base**: datas fora do intervalo coletado são ajustadas ao primeiro e ao último dado disponível, e início posterior ao fim não é aceito.
- **Download interrompido ou com erro**: o usuário vê uma mensagem legível, não um código de erro, e pode tentar de novo.
- **Tabela inteira sem filtros**: exportar todas as chamadas de API (~6,3 milhões de linhas, cerca de 1 GB) é permitido e conclui sem erro, mesmo levando minutos.
- **Várias exportações grandes ao mesmo tempo**: o painel continua respondendo às outras abas enquanto elas são geradas.
- **Tela estreita (celular)**: os controles continuam usáveis, com alvos de toque de 44 px.
- **Código errado ou trocado**: com código errado, a aba avisa e não mostra filtros, contagens nem dados. Se o código for trocado durante o uso, a próxima contagem ou exportação pede o código novo, e uma exportação já em andamento termina normalmente.
- **Link direto de exportação compartilhado**: um link de download copiado por quem tem o código MUST NOT funcionar para quem não tem.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O painel MUST ter uma página de exportação de dados no Dashboard 2.0, em `/v2/exportar`, **fora do menu de abas**: ela só é acessível pela URL (decisão do dono do produto em 2026-11-19, que substitui a quinta aba do protótipo).
- **FR-002**: A aba MUST oferecer exatamente estas tabelas de dados coletados: Consentimentos únicos, Consentimentos ativos, Chamadas de API (dados transacionais) e Chamadas de API de iniciação de pagamento.
- **FR-003**: A aba MUST NOT oferecer, por nenhum caminho, os registros internos da coleta (tentativas de chamada, resumos de execução, histórico de metadados de endpoints) nem as análises derivadas (agregações por grupo ou status, alertas de mudança de comportamento, condições "em observação"). Um pedido direto ao sistema por uma dessas tabelas MUST ser recusado.
- **FR-004**: Os arquivos exportados MUST NOT conter colunas de controle da coleta, como o momento em que cada linha foi coletada.
- **FR-005**: Para cada tabela, o usuário MUST poder filtrar por período (semana inicial e final) e por receptores. Também MUST poder filtrar por transmissores (consentimentos ativos e chamadas de API), por APIs e endpoints, e por status de resposta (as duas tabelas de chamadas de API).
- **FR-006**: A aba MUST mostrar apenas os filtros que se aplicam às tabelas escolhidas.
- **FR-007**: O período MUST oferecer os mesmos atalhos das outras abas do Dashboard 2.0 (12 meses, 6 meses, 3 meses, desde o começo do ano, tudo), além de datas livres.
- **FR-008**: A seleção de instituições MUST funcionar como nas outras abas: nenhuma escolhida significa todas, e a busca é por nome.
- **FR-009**: Para as chamadas de API, o usuário MUST escolher o nível: "total por API" (padrão) ou "por endpoint". O arquivo MUST identificar o nível, e as linhas dos dois níveis MUST NOT ser misturadas no mesmo arquivo.
- **FR-010**: Antes do download, a aba MUST mostrar o número de linhas que cada tabela escolhida terá com os filtros atuais, atualizado a cada mudança de filtro.
- **FR-011**: A exportação MUST NOT ter limite de linhas: qualquer tabela MUST poder ser exportada inteira, inclusive a de chamadas de API. Acima de 1 milhão de linhas no total, a aba MUST mostrar o tamanho e o tempo de download esperados e sugerir filtros, sem bloquear.
- **FR-011a**: Exportações grandes MUST começar a baixar sem esperar o arquivo inteiro ficar pronto. Uma exportação MUST NOT deixar o painel indisponível nem lento para os outros usuários enquanto é gerada.
- **FR-012**: O arquivo MUST seguir o padrão de CSV do Dashboard 2.0: separador `;`, vírgula decimal e codificação que abre corretamente com acentos em planilhas.
- **FR-013**: Uma exportação de várias tabelas MUST chegar num único download, com um arquivo por tabela e um arquivo de descrição.
- **FR-014**: Toda exportação MUST incluir uma descrição com a data dos dados, os filtros aplicados a cada tabela, o nível das chamadas de API e o significado de cada coluna. Numa tabela única, a descrição MAY estar no cabeçalho do próprio arquivo.
- **FR-015**: Os nomes dos arquivos MUST seguir o padrão `opf-dados-<tabela>-<AAAA-MM-DD>.csv` (tabela única) e `opf-dados-<AAAA-MM-DD>.zip` (várias tabelas), em que a data é a dos dados.
- **FR-016**: Cada linha exportada MUST trazer o nome e o identificador das instituições envolvidas, para que o arquivo possa ser cruzado com outras fontes sem depender do painel.
- **FR-016a**: As colunas MUST ter rótulos em português, no mesmo estilo dos outros CSVs do painel (por exemplo "Semana", "Receptor", "ID do receptor", "Transmissor", "ID do transmissor", "API", "Endpoint", "Status", "Pessoa física", "Pessoa jurídica", "Total"). Os rótulos MUST ser os mesmos em toda exportação da mesma tabela, e o arquivo de descrição MUST explicar cada um.
- **FR-017**: Os valores exportados MUST ser os mesmos usados pelas outras abas para a mesma métrica, semana e instituição.
- **FR-017a**: Linhas com valor zero informadas pelo portal MUST ser exportadas, sem filtro que as remova. A contagem de linhas (FR-010) MUST incluí-las.
- **FR-018**: Os filtros escolhidos na aba MUST reaproveitar o período e as instituições já escolhidos nas outras abas, e as mudanças feitas aqui MUST valer para elas, como no resto do Dashboard 2.0.
- **FR-019**: A aba MUST mostrar estado de carregamento enquanto conta linhas ou prepara o arquivo, e mensagens de erro legíveis em caso de falha.
- **FR-020**: A contagem de linhas e a exportação MUST exigir um código de acesso. Sem o código válido, a aba mostra só o campo para digitá-lo, e nenhum dado nem contagem é entregue. Pedidos diretos ao sistema sem o código MUST ser recusados.
- **FR-021**: O código é fixo (`EXPORTAR`), decidido pelo dono do produto em 2026-11-19, conferido só no servidor e nunca enviado à página. Trocá-lo exige nova versão do painel e invalida o acesso de quem usava o anterior. (Substitui o código definido fora do código-fonte e trocável sem nova versão.)
- **FR-022**: Depois de digitar o código válido, o usuário MUST continuar com acesso enquanto a aba estiver aberta no navegador, sem digitá-lo a cada exportação, e MUST poder sair (esquecer o código) quando quiser.
- **FR-023**: Tentativas com código errado MUST receber uma mensagem legível, sem indicar se o código está "quase certo". Tentativas repetidas MUST ser desaceleradas para impedir que alguém descubra o código por tentativa e erro.
- **FR-024**: As outras abas do painel MUST continuar públicas e sem código.
- **FR-025**: A aba MUST seguir o layout de [ux-handoff.md](ux-handoff.md): período na barra de filtros, seguido dos blocos "1. Tabelas", "2. Filtros" e "3. Resumo", com o resumo sempre visível ao rolar (no celular, uma barra fixa no rodapé com o total e o botão de exportar).
- **FR-026**: A aba MUST abrir com só "Consentimentos únicos" marcada.
- **FR-027**: Durante um download, os filtros e as tabelas MUST ficar travados até o fim ou o cancelamento, e o usuário MUST poder cancelar o download.
- **FR-028**: Depois de várias tentativas seguidas com código errado, a aba MUST bloquear novas tentativas por 1 minuto e informar a espera.
- **FR-029**: Quando o código muda durante o uso, a aba MUST pedir o código novo e manter os filtros já escolhidos.

### Key Entities

- **Tabela exportável**: um conjunto de dados coletados que o usuário pode baixar. Tem nome de exibição, descrição, colunas exportadas e os filtros que aceita. Existem quatro: consentimentos únicos, consentimentos ativos, chamadas de API e chamadas de iniciação de pagamento.
- **Consentimentos únicos**: total semanal de consentimentos por receptor, com a divisão entre pessoa física e jurídica.
- **Consentimentos ativos**: total semanal de consentimentos ativos por par receptor × transmissor.
- **Chamadas de API**: total semanal de chamadas por receptor × transmissor × API × endpoint × status de resposta, em dois níveis (total da API e por endpoint).
- **Chamadas de iniciação de pagamento**: mesma estrutura das chamadas de API, para a iniciadora de pagamento × detentora de conta.
- **Filtro de exportação**: período, instituições (receptores e transmissores), APIs e endpoints, status de resposta e nível. É aplicado a cada tabela escolhida na parte que se aplica a ela.
- **Descrição da exportação**: data dos dados, tabelas incluídas, filtros efetivos por tabela, nível das chamadas e dicionário de colunas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um usuário que nunca usou a aba consegue exportar uma tabela filtrada por período e instituição em menos de 1 minuto, sem ajuda.
- **SC-002**: Em 100% dos testes de conferência, os totais do arquivo batem com os do painel para a mesma métrica, semana e instituição.
- **SC-003**: Nenhum caminho da aba entrega registros internos da coleta ou análises derivadas. Uma tentativa direta de pedir essas tabelas é recusada em 100% dos casos.
- **SC-004**: O número de linhas aparece em até 2 segundos depois de cada mudança de filtro, no período padrão.
- **SC-005**: Qualquer exportação, de qualquer tamanho, começa a baixar em até 10 segundos.
- **SC-005a**: A exportação completa da maior tabela (chamadas de API, sem filtros) termina sem erro, e enquanto ela roda as outras abas continuam abrindo no tempo de sempre.
- **SC-006**: 100% dos arquivos de chamadas de API identificam o nível, e nenhum arquivo mistura o total da API com as linhas por endpoint.
- **SC-007**: Sem o código válido, 100% das tentativas de contar linhas ou exportar, pela aba ou direto ao sistema, são recusadas sem entregar dados.

## Assumptions

- A aba fica só no Dashboard 2.0. As páginas legadas não mudam.
- O painel continua público, como hoje; só a exportação exige código. Há um único código compartilhado (não há contas nem permissões por pessoa), e quem administra o painel o distribui fora do sistema.
- O "histórico de metadados de endpoints" (catálogo de nomes de endpoints com o momento em que foi visto) é tratado como registro da coleta e fica fora. Os nomes de API e endpoint chegam ao usuário como colunas das tabelas de chamadas.
- O formato é CSV, igual ao das outras abas. Planilha nativa e outros formatos ficam fora desta versão.
- A granularidade é a da coleta (semanal). A exportação não agrega nem recalcula valores, como a normalização para 30 dias ou por consentimento, porque isso é análise derivada.
- A exportação só lê a base, então a regra de que o painel nunca escreve na base continua valendo.
- Incluir uma quinta aba exige emendar a regra do Shell v2 da constituição (§6.8), que hoje lista as quatro abas. A emenda faz parte desta feature.

# Feature Specification: Remover o painel v1 (legado)

**Feature Branch**: `016-remove-v1-dashboard`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "Remover o painel v1 (legado). Apagar do código e do Git as páginas v1 (/, /profile, /active-consents e seus HTML), as APIs que só elas usam, os serviços e testes que só elas usam, o link 'Painel legado' do Dashboard 2.0, as seções do legado na constituição e no CLAUDE.md, e as specs antigas que só descrevem o painel v1. A raiz '/', '/profile' e '/active-consents' passam a redirecionar para /v2. O Dashboard 2.0 e a coleta de dados continuam funcionando sem mudança de comportamento."

## Clarifications

### Session 2026-11-19

- Q: O que a raiz "/" deve fazer depois da remoção? → A: Redirecionar para `/v2`. `/profile` e `/active-consents` também redirecionam para `/v2`.
- Q: O que significa "inclusive do Git"? → A: Apagar o código e também as specs antigas que só descrevem telas do v1. O histórico de commits é preservado (nada é reescrito, nenhum push forçado).
- Q: A partir de qual base? → A: Da `main`, que já contém o portal de exportação (PR #33 mesclado).

## Contexto

O painel passou a ter duas gerações: o v1 (três páginas, "Ecossistema", "Perfil Receptor" e "Consentimentos Ativos", em `/`, `/profile` e `/active-consents`) e o Dashboard 2.0 (`/v2*`), organizado por pergunta analítica. O v2 já cobre o que o v1 mostrava e mais. Manter os dois custa: cerca de 6 mil linhas de páginas, dezenas de rotas de API, serviços e testes que só o v1 usa, uma constituição que descreve dois "shells" de interface, e specs antigas que descrevem telas que ninguém mais deve consultar. A página inicial ainda abre o v1, e o v2 traz um link "Painel legado" para voltar a ele.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quem usa o Dashboard 2.0 não percebe mudança (Priority: P1)

Como analista que usa o Dashboard 2.0 e o portal de exportação, quero que tudo continue funcionando igual depois da remoção do v1.

**Why this priority**: É a garantia da feature. Remover código legado só vale se nada do que está em uso quebrar.

**Independent Test**: Abrir `/v2`, `/v2/evolucao`, `/v2/mudancas`, `/v2/instituicao` e `/v2/exportar` e conferir que os números, os filtros e as exportações são os mesmos de antes da remoção, para as mesmas escolhas; rodar toda a bateria de testes que sobrar.

**Acceptance Scenarios**:

1. **Given** a base de dados atual, **When** o usuário abre cada página do Dashboard 2.0 com os mesmos filtros de antes, **Then** vê os mesmos valores, gráficos e alertas.
2. **Given** o portal de exportação, **When** o usuário exporta qualquer tabela, **Then** o arquivo é igual ao de antes da remoção.
3. **Given** o Dashboard 2.0 aberto, **When** o usuário olha o cabeçalho, **Then** não há mais o link "Painel legado", e as quatro abas e a barra de filtros continuam como estavam.
4. **Given** a coleta de dados, **When** uma coleta termina e a base é sincronizada, **Then** o Dashboard 2.0 mostra os dados novos, sem nenhuma mudança na coleta.

---

### User Story 2 - Links e favoritos antigos continuam levando a algum lugar (Priority: P1)

Como pessoa que tem o endereço do painel antigo salvo, quero ser levada ao painel atual em vez de ver um erro.

**Why this priority**: O endereço raiz é o mais divulgado. Sem redirecionamento, quem entra pelo link de sempre vê um erro.

**Independent Test**: Abrir `/`, `/profile`, `/active-consents` (com e sem parâmetros na URL) e conferir que o navegador termina em `/v2`.

**Acceptance Scenarios**:

1. **Given** o endereço raiz, **When** alguém o abre, **Then** é levado ao Dashboard 2.0 (`/v2`).
2. **Given** `/profile` ou `/active-consents`, com ou sem parâmetros, **When** alguém os abre, **Then** é levado a `/v2`.
3. **Given** um endereço de API do v1 que deixou de existir (por exemplo, o de receptores, o de consentimentos ou o de chamadas de API do painel antigo), **When** é chamado, **Then** responde que não existe, sem erro de servidor e sem dados.

---

### User Story 3 - O repositório não carrega mais o v1 (Priority: P2)

Como mantenedor, quero que o código, os testes, a documentação e as especificações reflitam só o painel que existe, para que ninguém gaste tempo entendendo ou mantendo o v1.

**Why this priority**: É o motivo da remoção, mas só pode ser feito com segurança depois que as histórias 1 e 2 estão garantidas.

**Independent Test**: Procurar no repositório as páginas, rotas, funções, testes, textos de constituição, instruções do `CLAUDE.md` e specs que existiam só para o v1 e conferir que não restou nenhum; conferir que os módulos que o v2 e a exportação usam continuam presentes.

**Acceptance Scenarios**:

1. **Given** o repositório depois da remoção, **When** o mantenedor procura as três páginas do v1, **Then** os arquivos não existem mais.
2. **Given** as rotas de API, **When** o mantenedor lista o que o servidor expõe, **Then** só restam as do Dashboard 2.0, do portal de exportação, os redirecionamentos e os arquivos estáticos do v2.
3. **Given** a constituição, **When** o mantenedor a lê, **Then** descreve um único shell de interface (o do Dashboard 2.0), sem as regras exclusivas das páginas do v1, e a versão e a data da emenda estão atualizadas.
4. **Given** o `CLAUDE.md`, **When** um agente ou pessoa o lê, **Then** não encontra instruções, tabelas ou comandos sobre o painel v1.
5. **Given** a pasta de especificações, **When** o mantenedor a lista, **Then** as specs que só descrevem telas do v1 não estão mais lá, e as que também definem comportamento ainda usado (coleta, deploy, classificação de instituições, detecção de mudanças, Dashboard 2.0 e portal de exportação) continuam.
6. **Given** o histórico do Git, **When** o mantenedor consulta commits anteriores, **Then** os arquivos removidos continuam acessíveis neles.

---

### Edge Cases

- **Código compartilhado**: partes dos serviços do v1 (por exemplo, a classificação de instituições em grupos e as constantes de cores e de grupos de API) são usadas pelo Dashboard 2.0. Elas MUST continuar existindo, mesmo que o resto do módulo seja apagado.
- **Tabelas derivadas da coleta**: as tabelas que o v1 lia e o v2 também lê (agregações por grupo, por status e por endpoint, alertas) MUST continuar sendo geradas pela coleta. Esta feature não muda a coleta nem a base.
- **Links internos do v2 para o v1**: qualquer link, texto ou aviso do v2 que mande o usuário ao v1 MUST ser removido ou reescrito.
- **Texto que ainda menciona o legado**: comentários, mensagens e documentação que falam do "painel legado" MUST ser removidos ou atualizados, sem apagar o que descreve o v2.
- **Preferências guardadas no navegador**: o v1 guardava filtros em chaves próprias do navegador. Elas deixam de ser usadas e MAY ficar órfãs no navegador de quem as tinha; isso não afeta o v2, que usa chaves próprias.
- **Parâmetros nos links antigos**: um link antigo com parâmetros (por exemplo, instituição ou período) MUST redirecionar para `/v2` sem erro. Os parâmetros do v1 não são convertidos.
- **Implantação**: o serviço no Cloud Run MUST continuar subindo, baixando a base e respondendo depois da remoção, sem nova configuração.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O servidor MUST deixar de servir as três páginas do v1 (Ecossistema, Perfil Receptor e Consentimentos Ativos), e seus arquivos MUST ser apagados do repositório.
- **FR-002**: Os endereços `/`, `/profile` e `/active-consents` MUST redirecionar para `/v2`, com ou sem parâmetros na URL.
- **FR-003**: Todas as rotas de API que só o v1 usa MUST ser apagadas, de modo que chamá-las responda "não existe" e não devolva dados. Isso inclui as do painel antigo de consentimentos, de chamadas de API, de receptores, de grupos e cores, de consentimentos ativos e de sinais de comportamento.
- **FR-004**: As rotas do Dashboard 2.0 (`/v2*`, `/api/v2/*`) e do portal de exportação MUST continuar iguais, e os arquivos estáticos do Dashboard 2.0 MUST continuar sendo servidos.
- **FR-005**: O código de serviço, de rotas, de pré-aquecimento de cache e de constantes que só o v1 usa MUST ser apagado. O que o Dashboard 2.0 ou o portal de exportação usam MUST permanecer, mesmo que tenha vindo do v1.
- **FR-006**: Os testes que só cobrem o v1 MUST ser apagados, e todos os testes que sobrarem MUST passar.
- **FR-007**: O link "Painel legado" do cabeçalho do Dashboard 2.0 MUST ser removido, sem alterar as abas, o botão de tema nem os dados de data do cabeçalho.
- **FR-008**: A constituição MUST ser emendada para tirar as regras exclusivas do v1 (o shell legado, suas cores e sua persistência de filtros) e deixar um único shell, com a versão, a data e o relatório de impacto da emenda atualizados.
- **FR-009**: O `CLAUDE.md` MUST ser atualizado para não descrever o v1 (páginas, rotas, serviços, tabelas "usadas pelo painel legado") e o ponteiro do plano atual MUST apontar para o plano desta feature.
- **FR-010**: As especificações que só descrevem telas do v1 MUST ser apagadas do repositório, assim como os documentos de apoio exclusivos do v1 (o PRD e o exemplo de HTML do perfil de receptor da pasta de especificações em português). As specs que também definem comportamento ainda usado MUST ficar.
- **FR-011**: O histórico de commits MUST ser preservado: a remoção entra como novo commit numa branch e num pull request, sem reescrever o histórico nem fazer push forçado.
- **FR-012**: A coleta de dados, a sincronização com o GCS, o formato da base e o deploy no Cloud Run MUST continuar funcionando sem mudança de comportamento.
- **FR-013**: Nenhuma referência ao v1 MUST sobrar no que continua: nem importações, nem links, nem textos de ajuda, nem comentários que mandem ao painel removido.

### Key Entities

- **Painel v1**: o conjunto formado pelas três páginas antigas, suas rotas de API, seus serviços, seus testes, suas regras de interface na constituição e suas specs.
- **Dashboard 2.0**: o painel que permanece, com as abas "Quem lidera?", "Como evolui?", "O que mudou?", "Como opera uma instituição?" e o portal de exportação (fora do menu).
- **Código compartilhado**: o que nasceu para o v1 mas é usado pelo Dashboard 2.0 e fica (classificação de instituições em grupos, constantes de cores e de grupos de API).
- **Redirecionamento**: a resposta que leva endereços antigos ao Dashboard 2.0.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Depois da remoção, abrir `/`, `/profile` e `/active-consents` leva a `/v2` em 100% dos casos, sem erro, com ou sem parâmetros.
- **SC-002**: Em 100% das conferências, as páginas do Dashboard 2.0 e os arquivos do portal de exportação mostram os mesmos valores de antes da remoção para os mesmos filtros.
- **SC-003**: 100% dos testes que permanecem passam, e nenhum teste do v2 ou da exportação foi apagado.
- **SC-004**: Uma busca no repositório pelo nome das três páginas do v1, pelas rotas de API removidas e pelo texto "Painel legado" não encontra nada fora do histórico do Git.
- **SC-005**: O repositório perde pelo menos 6 mil linhas de código de interface e de serviços, além das specs antigas, sem nenhuma linha nova de funcionalidade.
- **SC-006**: O serviço no Cloud Run sobe e responde a `/v2` e ao redirecionamento da raiz no deploy seguinte à remoção, sem configuração nova.
- **SC-007**: Nenhum arquivo apagado deixa de estar acessível no histórico do Git.

## Assumptions

- O Dashboard 2.0 já cobre o uso diário do v1; ninguém depende das telas antigas.
- As specs apagadas são as 002, 003, 004, 005 e 006 (telas de consentimentos ativos do v1) e os documentos da pasta de especificações em português. As specs 001 (coleta de consentimentos ativos), 008 (deploy), 009 (classificação de instituições), 010 (detecção de mudanças), 011 em diante ficam, porque definem comportamento que o v2 e a coleta ainda usam. As partes dessas specs que citam telas do v1 não são editadas: elas são registro histórico.
- A coleta de dados e a base não mudam: nenhuma tabela, coluna ou índice é criado ou apagado por esta feature. Tabelas que só o v1 lia, mas que a coleta ainda gera, permanecem.
- Parâmetros em links antigos não são convertidos para filtros do v2.
- A emenda da constituição é uma mudança MAIOR de versão, por remover um princípio de interface (o shell legado).
- O trabalho acontece numa branch própria (`016-remove-v1-dashboard`), a partir da `main` com o portal de exportação já incorporado, e entra por pull request.

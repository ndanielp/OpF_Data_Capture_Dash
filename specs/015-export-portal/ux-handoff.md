# UX handoff: Exportar dados

**Feature**: [spec.md](spec.md) · **Protótipo**: [canvas "Exportar dados — UX"](https://claude.ai/artifact/4ZQAboWY8PgPYoxqiHver4) (privado; compartilhar pelo menu Share)
**Validado em**: 2026-11-19

O protótipo é a referência visual. Este arquivo registra o que precisa sair igual na implementação. Os números do protótipo são ilustrativos.

## Onde fica

- Quinta aba do Dashboard 2.0, rótulo **"Exportar dados"**, rota `/v2/exportar`, depois de "Como opera uma instituição?" em todas as páginas v2.
- Mesma casca das outras abas (Constituição §6.8): cabeçalho com marca, abas e "Dados até … · atualizado em …", botão de tema e "Painel legado", depois `.v2-main` com no máximo 1280 px.

## Telas e estados

| # | Quadro do canvas | Quando aparece |
|---|---|---|
| 1 | Acesso com código | Sempre que não há código válido nesta aba do navegador |
| 2 | Escolher tabelas e filtros | Depois do código válido |
| 3 | Exportação grande / download | Total acima de 1 milhão de linhas, durante e depois do download |
| 4 | Erros e estados vazios | Código errado, muitas tentativas, código trocado, contando linhas, sem dados, download interrompido |
| 5 | Celular | Abaixo de 720 px |

### 1. Acesso com código

- Título e subtítulo da página iguais aos da tela 2 ("Exportar dados" e "Baixe os números como foram coletados, por semana. Registros da coleta e análises do painel não entram.").
- Card centralizado, com no máximo 460 px de largura: ícone de cadeado, "Acesso por código", um texto explicando que a exportação é restrita e as outras abas continuam abertas, um campo de senha com o rótulo "Código de acesso" e o botão primário "Entrar".
- Erro: "Código inválido. Confira com quem administra o painel e tente de novo." (fundo `--down-bg`, `role="alert"`).
- Ajuda: "O acesso vale enquanto esta aba estiver aberta. Você pode sair a qualquer momento."
- Nenhum filtro, contagem ou dado aparece antes do código válido.

### 2. Escolher tabelas e filtros

Ordem na página:

1. **Barra de filtros** (`.v2-filterbar`): o período, com o controle segmentado "12 meses · 6 meses · 3 meses · Desde jan · Tudo" e os campos "De" e "Até", que é o mesmo período compartilhado com as outras abas. À direita, "Acesso liberado" (cadeado, cor `--new`) e o link "Sair".
2. Título e subtítulo da página.
3. Duas colunas: à esquerda (flexível) os cards **"1. Tabelas"** e **"2. Filtros"**, e à direita (320 a 360 px, fixa ao rolar a página) o card **"3. Resumo"**.

**1. Tabelas**: grade de 4 opções com caixa de seleção, cada uma com nome, uma linha de descrição e uma linha "Filtros: …". A opção marcada ganha a borda `--text`.

| Tabela | Descrição | Linha de apoio |
|---|---|---|
| Consentimentos únicos | Total semanal por receptor, com PF e PJ. | Filtros: período, receptores |
| Consentimentos ativos | Total semanal por receptor × transmissor. | Filtros: período, receptores, transmissores |
| Chamadas de API | Por receptor × transmissor × API × endpoint × status. | Filtros: todos, mais o nível (total ou endpoint) |
| Iniciação de pagamento | Iniciadora × detentora × API × endpoint × status. | Dados de <primeira> a <última semana> |

Abrem com "Consentimentos únicos" marcada. O protótipo abre com duas tabelas só para mostrar o .zip.

**2. Filtros**: aparecem só os filtros das tabelas marcadas. O rótulo de cada um diz a que tabelas se aplica (ex.: "Transmissores · ativos, chamadas").

- **Receptores**: chips removíveis (`.v2-chip-tag` com ×) e "+ Adicionar receptor" (`.v2-chip-add`), que abre o mesmo popover de busca das outras abas. Sem nenhum chip aparece "Todos os receptores".
- **Transmissores**: mesmo padrão, com "Todos os transmissores".
- **APIs e endpoints**: "Todas as APIs" e "+ Escolher APIs".
- **Status da resposta**: controle segmentado "200 e 500 · 200 · 500".
- **Nível das chamadas de API** (só com "Chamadas de API" marcada): bloco com destaque `.v2-accent` e controle segmentado "Total por API · Por endpoint", com uma linha de ajuda:
  - Total por API: "Uma linha por API. Some à vontade: não há dupla contagem."
  - Por endpoint: "Uma linha por endpoint. A soma pode ficar um pouco abaixo do total da API: algumas chamadas não são atribuídas a um endpoint pelo portal." O protótipo dizia que a soma dava o total, mas em 30/10/2026 ela dá 97,9% (ver research R6).

**3. Resumo** (`aria-live="polite"`):

- Subtítulo com o período e "N receptores" ou "todos os receptores".
- Uma linha por tabela marcada: nome, linhas (pt-BR), observação ("linhas", "linhas · total por API", "sem dados no período") e tamanho aproximado.
- Linha "Total" com o número de linhas em 22 px e o tamanho.
- Aviso de arquivo grande, acima de 1 milhão de linhas, em `--osc-bg`: "Arquivo grande: <tamanho>, cerca de <tempo> para baixar. Dá para exportar assim mesmo, ou reduzir período, receptores ou APIs." O aviso não bloqueia.
- Botão primário com ícone de download: "Exportar CSV" para uma tabela e "Exportar N arquivos (.zip)" para várias. Fica desabilitado sem tabela marcada ou com 0 linhas.
- Nome do arquivo embaixo do botão (`opf-dados-<tabela>-<data>.csv` ou `opf-dados-<data>.zip`).
- Rodapé: "CSV com ; e vírgula decimal. Valores zero informados pelo portal entram; semanas sem dado, não." e uma linha explicando onde vem a descrição (o cabeçalho do CSV, ou um arquivo dentro do .zip).

### 3. Exportação grande e download

- **Antes**: o aviso de arquivo grande, com o botão habilitado.
- **Durante**: um bloco "Baixando…" com "<baixado> de cerca de <total>", barra de progresso (`role="progressbar"`) e o texto "O arquivo já está chegando pelo navegador. Você pode continuar usando as outras abas.". Os botões viram "Cancelar download" e "Exportando…" (desabilitado). **Os filtros ficam travados até o fim ou o cancelamento.**
- **Depois**: "Download concluído." com linhas, nome e tamanho, em `--new-bg`, e o botão "Exportar de novo".
- **Navegadores sem gravação direta em disco** (Safari e Firefox): o navegador baixa sozinho. A aba mostra "Download iniciado: acompanhe o progresso e cancele pelo gerenciador de downloads do navegador." e destrava os filtros em 3 s. A barra de progresso e o "Cancelar download" dentro da página aparecem só no Chrome e no Edge (ver research R5).

### 4. Erros e estados vazios

| Estado | Mensagem | Ação |
|---|---|---|
| Código errado | Código inválido. Confira com quem administra o painel e tente de novo. | Campo continua editável |
| Muitas tentativas | Muitas tentativas seguidas. Aguarde 1 minuto para tentar de novo. | Campo e botão desabilitados durante a espera |
| Código trocado durante o uso | O código de acesso mudou. Digite o código novo para continuar. Seus filtros foram mantidos. | Volta ao campo de código; os filtros são preservados |
| Contando linhas | Atualizando a contagem com os filtros novos… | Varredura de carregamento do card (`.loading`), números em "—", botão desabilitado |
| Sem dados | Não há dados para os filtros escolhidos. + dica específica quando houver (ex.: período dos pagamentos) | Botão desabilitado |
| Download interrompido | O download parou no meio (<baixado> de cerca de <total>). O arquivo baixado está incompleto: apague-o e exporte de novo. | "Tentar de novo" |

### 5. Celular (abaixo de 720 px)

- Tudo numa coluna: barra de filtros, título, "1. Tabelas", "2. Filtros", "3. Resumo".
- O controle de período quebra em duas linhas, e "De" e "Até" ficam lado a lado.
- **Barra fixa no rodapé** com o total de linhas, o tamanho e o número de arquivos, mais o botão de exportar ("Exportar CSV" ou "Exportar .zip").
- Todos os alvos de toque com pelo menos 44 px.

## Regras de interação

- Qualquer mudança de tabela ou filtro atualiza a contagem na hora, sem botão "Aplicar" (§6.8).
- O período e os receptores leem e gravam `sessionStorage['opf:v2:filters']`, preservando os campos das outras abas.
- O código fica guardado só nesta aba do navegador e "Sair" o esquece. Ele não vai para `localStorage`.
- Tema claro e escuro com os tokens do `v2.css`, sem cor fixa nova.
- Acessibilidade: controles nativos (`button`, `input`, `label`, `fieldset`/`legend`), `aria-pressed` nos segmentados, `aria-invalid` no código errado, `role="alert"` nos erros e `role="status"` no resumo e no progresso.

## Componentes do Dashboard 2.0 reaproveitados

`.v2-header`, `.v2-tabs`, `.v2-filterbar`, `.v2-field`, `.v2-seg`, `.v2-chip-tag`, `.v2-chip-add`, o popover de busca (`V2` em `shell.js`), `.v2-card` com `.loading`, `.v2-btn`, `.v2-error`, `.v2-accent`.

Componentes novos (ficam em `v2.css`): a opção de tabela com caixa de seleção, a linha do resumo, a barra de progresso e a barra fixa do celular.

# Research: Portal de exportação de dados

**Feature**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Date**: 2026-11-19

As medições foram feitas na base local de 19/11/2026: 4,85 GB, `api_requests` com 6.277.798 linhas.

## R1. Volume e custo das consultas

- **Decision**: contar e ler direto nas tabelas coletadas, com `COUNT(*)` e `SELECT` filtrado e parametrizado, sem tabela pré-agregada nova.
- **Rationale**: as consultas foram medidas com a base no cache do sistema operacional:

  | Consulta | Tempo | Linhas |
  |---|---|---|
  | `COUNT(*)` de `api_requests`, total por API (`endpoint_id = 0`), base inteira | 0,53 s | 1.397.047 |
  | idem, 12 meses | 0,15 s | 709.363 |
  | idem, 12 meses, 1 receptor | 0,10 s | 28.097 |
  | `COUNT(*)` de `api_requests`, tudo | 0,41 s | 6.277.798 |
  | `COUNT(*)` de `active_consents`, 12 meses | 0,02 s | 64.296 |
  | leitura de `api_requests`, 3 meses, todos os níveis | 1,0 s | 896.733 |

  A exportação não agrega nada (lê linha a linha), então a regra de pré-agregação do Princípio IV não se aplica a ela. A contagem é um `COUNT(*)` coberto por índice já existente: `idx_api_date`, `idx_api_by_receptor`, `idx_active_date_receptor`, `idx_consents_date_rec`, `idx_pi_api_by_receptor`.
- **Alternatives considered**: (a) uma tabela de contagens por semana × receptor, que é complexidade nova para ganhar meio segundo; (b) estimar as linhas sem `COUNT`, o que fica impreciso com filtros de transmissor e API.
- **Consequence**: a contagem fica sob o limite de 500 ms p95 no período padrão (12 meses). O caso "base inteira sem filtro" passa um pouco, mas é a exceção e o SC-004 aceita até 2 s. O resultado vai para um cache `TTLCache` com chave (filtros, mtime da base), como no resto do Dashboard 2.0.

## R2. Gerar arquivos grandes sem estourar memória

- **Decision**: resposta em streaming (`StreamingResponse` com um gerador síncrono, que o FastAPI roda no threadpool). O cursor SQLite é lido em lotes de 5.000 linhas, com `csv.writer` sobre um buffer de texto que é esvaziado a cada lote. Para várias tabelas, o `zipfile.ZipFile` escreve num destino não posicionável (descritores de dados ativados automaticamente), também esvaziado a cada lote.
- **Rationale**: a memória fica constante, por volta do tamanho de um lote, qualquer que seja o tamanho do arquivo. O primeiro byte sai em menos de 1 s, o que atende o SC-005 (download começa em até 10 s). Só usa a biblioteca padrão (`csv`, `zipfile`, `io`), então não entra dependência nova nem muda a Stack.
- **Alternatives considered**: (a) gerar o arquivo inteiro antes de enviar, que estoura memória e atrasa o primeiro byte; (b) gerar no disco e servir depois, que exige escrita na instância, limpeza e espera; (c) `pandas.to_csv` em pedaços, mais lento e mais pesado em memória que `csv.writer`.

## R3. Não deixar o painel lento durante uma exportação (FR-011a, SC-005a)

- **Decision**: cada exportação abre a própria conexão SQLite somente leitura (`mode=ro`), e há no máximo 2 exportações simultâneas por instância (um `threading.BoundedSemaphore`). A terceira recebe 429 com a mensagem "Outra exportação grande está em andamento. Tente de novo em alguns minutos.". O tempo limite de requisição do Cloud Run sobe de 300 s (padrão) para 3.600 s em `deploy.sh` e `deploy.ps1`.
- **Rationale**: o gerador roda no threadpool (40 threads por padrão), e o SQLite em `mode=ro` não bloqueia leituras concorrentes. Com 2 exportações, sobram CPU e threads para as outras abas, que têm 2 vCPUs por instância. A base inteira de chamadas (~1 GB) passa dos 300 s padrão numa conexão comum.
- **Alternatives considered**: (a) fila de exportação com job assíncrono, que exige estado compartilhado entre instâncias e escrita fora do SQLite; (b) não limitar, com risco de duas ou três exportações completas derrubarem a resposta das outras abas.

## R4. Código de acesso (FR-020 a FR-024, FR-028, FR-029)

- **Decision**:
  - O código vem da variável de ambiente `OPF_EXPORT_CODE`. Ela fica no Secret Manager e é passada ao Cloud Run com `--set-secrets`. Sem ela, a aba mostra "Exportação não configurada" e as rotas respondem 503.
  - `POST /api/v2/export/session` compara o código com `hmac.compare_digest` e devolve um token assinado: HMAC-SHA256 com chave derivada do próprio código, com validade de 12 h.
  - Trocar o código invalida todos os tokens sozinho, porque a chave muda. Isso atende FR-021 e FR-029 sem guardar estado.
  - O token fica em `sessionStorage['opf:v2:export']` (só nesta aba do navegador; "Sair" apaga) e vai no header `X-Export-Token`.
- **Rationale**: o Cloud Run tem até 3 instâncias sem estado compartilhado. O token assinado vale em qualquer uma, e a troca do código é só uma nova revisão de variável. A troca do segredo cria uma revisão nova, mas não exige build: a imagem é a mesma.
- **Tentativas erradas (FR-023, FR-028)**: um contador em memória por IP do cliente (primeiro valor de `X-Forwarded-For`). Depois de 5 erros em 10 minutos, bloqueia por 60 s, com resposta 429 e `retry_after`. Com até 3 instâncias, um atacante pode chegar a 15 tentativas por janela, o que é aceitável para um código de 12 caracteres ou mais. Fica como recomendação em [quickstart.md](quickstart.md).
- **Alternatives considered**: (a) login com conta Google (IAP), mais seguro mas fora do pedido de "um código"; (b) sessão guardada no servidor, que se perde entre instâncias; (c) senha básica HTTP, que o navegador guarda e é difícil de "esquecer" (FR-022).

## R5. Download com progresso e link que não pode ser repassado

- **Decision**:
  - O download é um `GET /api/v2/export/file?ticket=…`. O ticket é um HMAC dos filtros e da validade, com 60 s e a mesma chave do token, pedido com o token por `POST /api/v2/export/ticket`.
  - **No Chrome e no Edge** (`window.showSaveFilePicker`), a página pede onde salvar, lê a resposta com `fetch` e grava em disco aos poucos. Com isso ela mostra o progresso (bytes recebidos sobre o tamanho estimado), cancela (`AbortController`) e sabe quando terminou, para destravar os filtros.
  - **Nos outros navegadores**, a página navega para a URL do ticket e o próprio navegador baixa. A aba mostra "Download iniciado: acompanhe no navegador", e os filtros destravam em 3 s.
- **Rationale**: um GET é o único jeito de o navegador baixar em streaming sem guardar o arquivo na memória da página. O ticket de 60 s faz um link copiado parar de funcionar quase na hora (caso de borda "Link direto compartilhado"), sem estado no servidor. O `fetch` direto para um Blob guardaria 1 GB na memória da aba.
- **Alternatives considered**: (a) `fetch` para Blob, que estoura memória no navegador nos arquivos grandes; (b) ticket de uso único, que exige estado compartilhado entre instâncias; (c) token de sessão na URL, que vaza no histórico e vale por 12 h.
- **Impacto no UX**: no download nativo, o progresso e o cancelamento ficam no gerenciador de downloads do navegador. O [ux-handoff.md](ux-handoff.md) foi atualizado.

## R6. Nível "por endpoint" e o total da API

- **Finding**: em 30/10/2026, a soma das linhas por endpoint dá 97,9% do total das APIs (8,53 bi de 8,71 bi). O restante são chamadas que o portal não atribui a nenhum endpoint, e nenhuma combinação tem endpoints acima do total.
- **Decision**: "Por endpoint" exporta só as linhas de endpoint (`endpoint_id <> 0`), sem linha de resto calculada, porque calcular o resto seria análise derivada. A linha de ajuda passa a ser: "Uma linha por endpoint. A soma pode ficar um pouco abaixo do total da API: algumas chamadas não são atribuídas a um endpoint pelo portal." O arquivo de descrição diz o mesmo.
- **Alternatives considered**: incluir a linha "sem endpoint", que tornaria os dois níveis somáveis, mas cria um número que o portal não publica.

## R7. Formato do CSV e da descrição (FR-012, FR-014, FR-016a)

- **Decision**:
  - O CSV usa UTF-8 com BOM, separador `;`, fim de linha `\r\n`, números inteiros sem separador de milhar e datas `AAAA-MM-DD`, e os rótulos das colunas são em português.
  - **Tabela única**: o CSV começa com linhas de descrição iniciadas por `#` (data dos dados, tabela, filtros, nível), depois o cabeçalho e os dados. O `pandas.read_csv(comment="#")` lê direto.
  - **Várias tabelas**: um `.zip` com um CSV por tabela (sem as linhas `#`) e um `LEIAME.txt` com a descrição de tudo e o dicionário de colunas.
- **Rationale**: o separador e a codificação são os mesmos do "Exportar CSV" das outras abas, e o Excel em pt-BR abre direto. Os totais são inteiros, então a vírgula decimal não aparece na prática. Ela vale para um campo decimal futuro.
- **Alternatives considered**: um arquivo de descrição separado também para uma tabela só, que faria até a menor exportação virar `.zip`.

## R8. Constituição: a quinta aba

- **Decision**: emendar o §6.8 (MINOR). A lista de abas ganha "Exportar dados → `/v2/exportar`", e a regra de Export ganha uma exceção: a aba de exportação não tem "Exportar CSV" na barra de filtros, porque o próprio conteúdo da aba é a exportação, e o botão fica no card "3. Resumo". A emenda entra no mesmo PR da feature.
- **Rationale**: o §6.8 exige as quatro abas em toda página v2 e um "Exportar CSV" por página na barra de filtros, e a nova aba quebraria as duas regras sem a emenda.

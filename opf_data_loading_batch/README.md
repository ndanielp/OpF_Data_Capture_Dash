# Open Finance Data Loading & Dashboard

Este projeto gerencia a automação de coleta de dados do Open Finance e disponibiliza um **Dashboard Analítico** para acompanhar em tempo real as informações, volume de requisições, instituições e performance estrutural processada. Tudo de forma embutida e isolada baseada em Docker.

---

## 🛠 Pré-requisitos

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (Para subir as imagens do sistema independente do seu Windows).
- **[Ngrok](https://download.ngrok.com/)** *(Opcional)* - Necessário apenas caso você deseje gerar um link público para acessar o sistema de fora da sua rede.

---

## 🚀 Como Executar o Sistema Web (Dashboard)

A configuração está construída para economizar tempo usando os atalhos em batch (`.bat`) do Windows.

### Passo 1: Revisores de Ambiente
Basta garantir que o arquivo `.env` conste na pasta principal (você pode copiar o `.env.example` para `.env`). Ele controla como a aplicação se comporta localmente (onde salvar logs e referenciar o banco SQLite).

### Passo 2: Iniciar a Aplicação Base
Dê **dois cliques** no arquivo:
> `start_docker_dashboard.bat`

Ele vai lidar com tudo para você. Se for a primeira vez que você roda na máquina, o Docker vai construir as imagens. Caso contrário, subirá instantaneamente.

### Passo 3: Utilizando a Interface
Com a tela preta funcionando em aberto, você pode acessar seu sistema pelo navegador:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🌐 Como Expor seu Dashboard na Internet (Ngrok)

Caso tenha necessidade de mostrar essa plataforma num computador externo ou celular remotamente:

1. Certifique-se de que o **Dashboard está rodando perfeitamente** na Etapa Anterior.
2. Dê **dois cliques** no arquivo:
   > `start_ngrok.bat`
3. O terminal especial revelará um endereço temporário público e seguro *(ex: `https://abcd-xyz.ngrok-free.app`)* redirecionando para a sua máquina.

---

## ⚙️ Rodando a Coleta em Fundo (Modo Batch)

O serviço conta com um módulo de contêiner autônomo (não-web). Se a sua intenção é somente acordar as máquinas em modo oculto e varrer os dados periodicamente:

Abra o seu terminal na pasta do projeto e use:
```bash
docker compose up batch
```
Desta vez as automações e coletores de dados vão arrancar, fazer a coleta e se autodestruir sozinhos quando a tarefa terminar de popular a sua base analítica.

**Período de Coleta Padrão:**
Por padrão, este comando extrai os dados das **últimas 4 semanas** (até a data de hoje). 
Caso deseje alterar este período definitivo no Docker, edite o arquivo `docker-compose.yml`, localizando a seção `batch:` e alterando a instrução `command:` para o formato:
`command: ["python", "main.py", "run", "--start-date", "2024-01-01", "--end-date", "2024-12-31"]`

---

### Encerrando o Serviços
Se não for mais usar o sistema e quiser parar tudo com segurança para liberar a porta do computador, rode no terminal:
```bash
docker compose down
```

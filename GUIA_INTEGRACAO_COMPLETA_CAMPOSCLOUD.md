# Integração completa — ZYNEX Bot, Manager e API de Transcripts

## Distribuição do plano de 4 GB

- Manager: 768 MB
- MongoDB: 1024 MB
- Bot de vendas: 1024 MB
- API de transcripts: 512 MB
- Reserva: 768 MB

## 1. Aplicação do bot de vendas

Na Campos Cloud:

- Ambiente: Python
- Versão: 3.11/recomendada
- Memória: 1024 MB
- Arquivo principal: `bot.py`
- Website/API: ativado
- Porta: `3000`
- Subdomínio: `zynexsales`
- Auto Restart: ativado
- Comando inicial: `python -u bot.py`
- Instalação: `pip install --no-cache-dir -r requirements.txt`

Importe as variáveis de `.env.camposcloud.example` e substitua todos os marcadores.

Teste público:

`https://zynexsales.camposcloud.app/health`

A resposta precisa mostrar `ok: true`, `service: zynex-sales-private-api` e, após o bot conectar, `ready: true`.

## 2. API de transcripts

Crie uma SEGUNDA aplicação na Campos Cloud:

- Ambiente: Node.js
- Versão: 20 ou mais recente
- Memória: 512 MB
- Arquivo principal: `src/index.js`
- Website/API: ativado
- Porta: `3000`
- Auto Restart: ativado
- Comando inicial: `npm run start`
- Instalação: `npm ci --omit=dev`

Importe `.env.camposcloud.example` do pacote da API. Depois de a Campos Cloud gerar o domínio, coloque a URL real em `PUBLIC_BASE_URL` e no bot em `TRANSCRIPT_API_URL`.

A chave `TRANSCRIPT_API_KEY` deve ser idêntica nas duas aplicações.

Teste:

`https://SUBDOMINIO-TRANSCRIPTS.camposcloud.app/health`

## 3. MongoDB

O bot e a API podem usar o mesmo servidor MongoDB, mas com bancos diferentes:

- Bot: `MONGO_DATABASE=zynex_sales`
- API de transcripts: `MONGO_DATABASE=zynex_transcripts`
- Manager: mantenha o banco próprio já configurado

A mesma `MONGO_URL` pode ser usada nas aplicações, desde que o usuário do Mongo tenha acesso aos bancos necessários.

## 4. Integração do Manager com o bot

No bot:

- `SALES_BOT_API_KEY`: chave com pelo menos 32 caracteres
- `MANAGER_APPLICATION_ID`: ID da aplicação cadastrada no Manager
- `MANAGER_API_URL`: domínio público do Manager, sem barra final
- `MANAGER_INTERNAL_API_KEY`: chave aceita pelo Manager no header `x-api-key`
- `MANAGER_SALES_API_KEY`: segredo HMAC de compras

No Manager, cadastre:

- URL do bot: `https://zynexsales.camposcloud.app`
- ID externo/aplicação: o mesmo valor de `MANAGER_APPLICATION_ID`
- Chave do bot: o mesmo valor de `SALES_BOT_API_KEY`
- Chave interna para compras: o mesmo valor de `MANAGER_INTERNAL_API_KEY`
- Segredo de assinatura: o mesmo valor de `MANAGER_SALES_API_KEY`

O bot envia compras para:

`POST {MANAGER_API_URL}/internal/v1/purchases`

O Manager consulta o bot pelas rotas:

- `GET /internal/v1/applications/{ID}/status`
- `POST /internal/v1/applications/{ID}/restart`
- `POST /internal/v1/applications/{ID}/suspend`
- `POST /internal/v1/applications/{ID}/activate`
- `GET /internal/v1/applications/{ID}/logs`

## 5. Vincular o produto vendido ao Manager

A compra só é enviada ao Manager quando o produto ou campo possui `manager_integration`:

```json
"manager_integration": {
  "plan_slug": "vendas",
  "period_days": 30,
  "application_name": "ZYNEX BOT",
  "discord_application_id": "ID_DA_APLICACAO_DISCORD",
  "hosting_external_id": "MESMO_MANAGER_APPLICATION_ID"
}
```

`plan_slug` precisa existir no Manager. O bloco pode ficar no produto inteiro ou no campo/opção específica. Sem `plan_slug`, a compra é entregue normalmente, mas não cria licença/assinatura no Manager.

## 6. Tickets e transcripts no Discord

Depois de o bot ficar online:

1. Execute `/botconfig`.
2. Abra a área de tickets.
3. Configure categoria, cargos de atendimento, canal de logs e mensagem do painel.
4. Ative a geração de transcript no fechamento.
5. Dê ao bot permissões de Ver canal, Ler histórico, Enviar mensagens, Incorporar links, Anexar arquivos e Gerenciar canais.
6. Abra um ticket de teste, envie mensagens e feche.
7. Confira se o link abre no domínio da API de transcripts.

## 7. Ordem correta de inicialização

1. MongoDB
2. Manager
3. API de transcripts
4. Bot de vendas

Depois de alterar variáveis, reinicie a aplicação correspondente.

## 8. Diagnóstico

- `/health` do bot não abre: confirme Website/API, porta 3000 e `PRIVATE_API_PORT=3000`.
- Bot abre, mas `ready=false`: verifique token, intents e logs do Discord.
- `storage` não é `mongo`: confira `STORAGE_DRIVER` e `MONGO_URL`.
- Transcript retorna 401: as duas `TRANSCRIPT_API_KEY` são diferentes.
- Manager não recebe compra: confirme as três chaves e o bloco `manager_integration` do produto.
- Manager retorna 401: chave interna ou assinatura HMAC não coincide.
- Manager retorna 404 ao consultar o bot: o ID da rota não coincide com `MANAGER_APPLICATION_ID`.

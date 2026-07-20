# Configuração da Carteira Integrada — PurinCash

## Variáveis

```env
PURINCASH_API_KEY=
PURINCASH_API_URL=https://api.purincash.com/v1
PURINCASH_CALLBACK_URL=
PURINCASH_WEBHOOK_SECRET=
PURINCASH_PIX_KEY=
PURINCASH_OPERATION_FEE_PERCENT=0.60
PURINCASH_OPERATION_FEE_FIXED=0.25
```

`PURINCASH_OPERATION_FEE_PERCENT` e `PURINCASH_OPERATION_FEE_FIXED` controlam apenas a taxa operacional exibida e usada na prévia. Ajuste esses valores conforme o plano da conta.

A interface não possui mais o botão **Definir Taxa da Loja**. A responsabilidade da taxa operacional continua disponível no painel.

## Fluxo de cobrança

1. O checkout calcula a taxa da loja e apresenta a prévia ao cliente.
2. O bot cria o pagamento PIX pela Carteira Integrada.
3. O código copia e cola e o QR Code são exibidos no carrinho.
4. A confirmação ocorre por webhook e também pode ser consultada pelo monitor de pagamentos.
5. O processamento é idempotente para evitar entrega duplicada.

## Webhook

Endpoint implementado:

```text
POST /webhooks/purincash
```

Cabeçalhos validados:

```text
X-Webhook-Signature
X-Webhook-Id
```

O domínio do callback precisa ser público e HTTPS. Em hospedagens com proxy reverso, encaminhe a rota para `PRIVATE_API_PORT`.

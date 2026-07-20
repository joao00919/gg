# Bot de Vendas ZYNEX na Shard

1. Configure `.env` usando `.env.example`.
2. Use a mesma `SALES_BOT_API_KEY` configurada no ZYNEX Manager.
3. Configure `MANAGER_API_URL`, `MANAGER_INTERNAL_API_KEY` e `MANAGER_SALES_API_KEY`.
4. Para um produto que deve liberar uma aplicação no Manager, adicione em seu produto ou campo:

```json
"manager_integration": {
  "plan_slug": "vendas",
  "period_days": 30,
  "application_name": "ZYNEX BOT",
  "discord_application_id": "ID_DA_APLICACAO",
  "hosting_external_id": "ID_CONFIGURADO_EM_MANAGER_APPLICATION_ID"
}
```

Após o pagamento ser aprovado, a compra é enviada ao Manager com idempotência. O Manager cria cliente, aplicação, licença, assinatura e libera `/apps`.

A API privada da Shard permite ao Manager consultar status, reiniciar, suspender, ativar e obter logs sem compartilhar o token do Discord.

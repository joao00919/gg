# API de Transcripts na Campos Cloud

1. Publique o pacote `ZYNEX_Transcript_API_CamposCloud.zip` em uma aplicação Node.js separada.
2. Configure na API:

```env
PUBLIC_BASE_URL=https://DOMINIO-DA-API
TRANSCRIPT_API_KEY=CHAVE_FORTE
TRANSCRIPT_TTL_HOURS=72
STORAGE_DRIVER=mongo
MONGO_URL=mongodb+srv://...
MONGO_DATABASE=zynex_transcripts
```

3. Configure nesta aplicação do bot:

```env
TRANSCRIPT_API_URL=https://DOMINIO-DA-API
TRANSCRIPT_API_KEY=A_MESMA_CHAVE_FORTE
```

4. Reinicie as duas aplicações.
5. Teste `https://DOMINIO-DA-API/health`.
6. No Discord, ative os transcripts no painel de tickets e defina o canal de logs.

A variável de ambiente tem prioridade sobre `configs/config_api.json`, portanto não é necessário editar o código ao trocar o domínio.

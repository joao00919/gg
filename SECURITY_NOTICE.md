# Segurança

- O pacote não contém `.env`, tokens, senhas, webhooks privados, certificados bancários ou dados de clientes.
- Credenciais que estavam embutidas em integrações opcionais foram removidas e substituídas por variáveis de ambiente.
- O token Discord nunca deve ser gravado no `config.json` nem enviado ao GitHub.
- A sincronização de emojis, alteração de descrição e monitoramento do perfil estão desativados por padrão.
- O modo local grava somente em `data/local_database.json`.
- Para produção, use MongoDB com `STORAGE_DRIVER=mongo` e configure as credenciais no painel da hospedagem.
- Redefina qualquer token ou chave que tenha aparecido em prints, logs ou versões antigas.
